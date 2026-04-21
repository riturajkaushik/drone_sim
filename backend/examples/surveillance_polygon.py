"""
Example: Set up a surveillance area polygon, spawn a drone, and fly random waypoints.

This script demonstrates the full surveillance workflow:
  1. Reset the simulator to a clean state.
  2. Define a surveillance polygon (a geographic area of interest) and send it
     to the backend via the new REST endpoint. The backend stores it and
     broadcasts it to the frontend, which renders it on the map.
  3. Spawn a drone at a location inside the polygon.
  4. Generate a set of random waypoints within the polygon's bounding box.
  5. Command the drone to follow those waypoints and listen for progress events
     until every waypoint has been reached.

Usage:
    1. Start the backend:   cd backend && uvicorn main:app --reload --port 8000
    2. Start the frontend:  cd frontend && npm run dev
    3. Run this script:     python examples/surveillance_polygon.py
"""

import asyncio
import json
import random

import requests
import websockets

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Backend URLs
REST_BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000/ws/drone"

# Surveillance polygon — an irregular 6-sided area in Lauttasaari (Helsinki).
# Each vertex is [latitude, longitude].  The shape is intentionally non-rectangular
# to demonstrate that the system handles arbitrary polygons, not just axis-aligned boxes.
SURVEILLANCE_POLYGON = [
    [60.1550, 24.8750],   # south-west — slightly indented
    [60.1540, 24.8950],   # south — dips lower in the middle
    [60.1570, 24.9150],   # south-east — juts eastward
    [60.1680, 24.9100],   # north-east — pulls back west
    [60.1710, 24.8900],   # north — peaks northward
    [60.1660, 24.8680],   # north-west — angled inward
]

# Drone spawn location — must be inside the map bounds.
# We place it near the center of the surveillance polygon.
DRONE_SPAWN_LAT = 60.1630
DRONE_SPAWN_LON = 24.8900

# How many random waypoints to generate inside the polygon's bounding box.
NUM_RANDOM_WAYPOINTS = 8

# Seed for reproducibility (set to None for truly random waypoints each run).
RANDOM_SEED = 42


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def compute_bounding_box(polygon: list[list[float]]) -> dict:
    """Compute the axis-aligned bounding box of a polygon.

    Args:
        polygon: List of [lat, lon] vertices.

    Returns:
        Dict with min_lat, max_lat, min_lon, max_lon.
    """
    lats = [v[0] for v in polygon]
    lons = [v[1] for v in polygon]
    return {
        "min_lat": min(lats),
        "max_lat": max(lats),
        "min_lon": min(lons),
        "max_lon": max(lons),
    }


def generate_random_waypoints(
    bbox: dict, count: int, seed: int | None = None
) -> list[list[float]]:
    """Generate random [lat, lon] waypoints uniformly distributed inside a bounding box.

    Args:
        bbox:  Bounding box dict with min_lat, max_lat, min_lon, max_lon.
        count: Number of waypoints to generate.
        seed:  Optional random seed for reproducibility.

    Returns:
        List of [lat, lon] pairs.
    """
    rng = random.Random(seed)
    waypoints = []
    for _ in range(count):
        lat = rng.uniform(bbox["min_lat"], bbox["max_lat"])
        lon = rng.uniform(bbox["min_lon"], bbox["max_lon"])
        # Round to 4 decimal places (~11 m precision) for readability
        waypoints.append([round(lat, 4), round(lon, 4)])
    return waypoints


# ---------------------------------------------------------------------------
# Main workflow
# ---------------------------------------------------------------------------

async def main():
    # ------------------------------------------------------------------
    # Step 0: Connect to the backend WebSocket
    # ------------------------------------------------------------------
    print("Connecting to backend WebSocket...")
    async with websockets.connect(WS_URL) as ws:

        # ------------------------------------------------------------------
        # Step 1: Reset the simulator
        # ------------------------------------------------------------------
        # Clearing all drones and state ensures a clean starting point.
        print("\n[Step 1] Resetting simulator...")
        await ws.send(json.dumps({"type": "reset_sim"}))
        while True:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5.0))
            if msg["type"] == "reset_sim_response":
                print(f"  Cleared {msg['cleared_drones']} previous drone(s)")
                break

        # ------------------------------------------------------------------
        # Step 2: Set the surveillance polygon via REST API
        # ------------------------------------------------------------------
        # We use the new POST /surveillance-polygon endpoint.  The backend
        # stores the polygon and broadcasts it to all connected frontends,
        # which render it as a filled overlay on the map.
        print("\n[Step 2] Setting surveillance polygon via REST API...")
        resp = requests.post(
            f"{REST_BASE_URL}/surveillance-polygon",
            json={"surveillance_polygon": SURVEILLANCE_POLYGON},
        )
        resp.raise_for_status()
        data = resp.json()
        print(f"  Polygon accepted — {data['vertices']} vertices")

        # The frontend will also receive a WebSocket broadcast with the
        # polygon, so we may see a WS message come through.  We drain any
        # pending messages before moving on.
        await asyncio.sleep(0.2)

        # ------------------------------------------------------------------
        # Step 3: Spawn a drone inside the surveillance area via REST API
        # ------------------------------------------------------------------
        drone_id = "surveyor-1"
        print(f"\n[Step 3] Spawning drone '{drone_id}' at "
              f"({DRONE_SPAWN_LAT}, {DRONE_SPAWN_LON}) via REST API...")
        resp = requests.post(
            f"{REST_BASE_URL}/spawn-drones",
            json={"drones": [
                {"spawn_loc": [DRONE_SPAWN_LAT, DRONE_SPAWN_LON], "drone_id": drone_id}
            ]},
        )
        resp.raise_for_status()
        data = resp.json()
        for d in data["drones"]:
            print(f"  Spawned {d['drone_id']} at {d['spawn_loc']}")

        # ------------------------------------------------------------------
        # Step 4: Generate random waypoints inside the polygon's bounding box
        # ------------------------------------------------------------------
        bbox = compute_bounding_box(SURVEILLANCE_POLYGON)
        waypoints = generate_random_waypoints(bbox, NUM_RANDOM_WAYPOINTS, RANDOM_SEED)

        print(f"\n[Step 4] Generated {len(waypoints)} random waypoints:")
        for i, wp in enumerate(waypoints):
            print(f"  #{i}: ({wp[0]:.4f}, {wp[1]:.4f})")

        # ------------------------------------------------------------------
        # Step 5: Command the drone to follow the waypoints
        # ------------------------------------------------------------------
        # The follow_waypoints message expects a dict mapping drone IDs to
        # their waypoint lists.  Each waypoint is [lat, lon].
        print(f"\n[Step 5] Sending waypoints to '{drone_id}'...")
        follow_req = {
            "type": "follow_waypoints",
            "waypoints": {drone_id: waypoints},
        }
        await ws.send(json.dumps(follow_req))

        # Wait for follow_waypoints confirmation.
        while True:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5.0))
            if msg["type"] == "follow_waypoints_response":
                for did, count in msg["drones"].items():
                    print(f"  {did}: {count} waypoint(s) dispatched")
                break
            elif msg["type"] == "error":
                print(f"  Error: {msg['message']}")
                return

        # ------------------------------------------------------------------
        # Step 6: Listen for waypoint_reached events until all are done
        # ------------------------------------------------------------------
        print(f"\n[Step 6] Listening for waypoint events "
              f"(expecting {len(waypoints)} total)...\n")
        remaining = len(waypoints)

        while remaining > 0:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=120.0)
            except asyncio.TimeoutError:
                print("  Timed out waiting for waypoint events.")
                break

            msg = json.loads(raw)

            if msg["type"] == "waypoint_reached":
                did = msg.get("drone_id", "?")
                wp = msg.get("waypoint", {})
                idx = msg.get("index", -1)
                remaining -= 1
                print(f"  [{len(waypoints) - remaining}/{len(waypoints)}] "
                      f"{did} reached waypoint #{idx}: "
                      f"({wp.get('lat', 0):.4f}, {wp.get('lon', 0):.4f})")

        print("\nAll waypoints reached. Surveillance patrol complete!")


if __name__ == "__main__":
    asyncio.run(main())
