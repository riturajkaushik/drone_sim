"""
Example: Set up a surveillance area polygon, spawn a drone, and fly random waypoints.

This script demonstrates the full surveillance workflow:
  1. Reset the simulator to a clean state.
  2. Define a surveillance polygon (a geographic area of interest) and send it
     to the backend via the REST endpoint.
  3. Spawn a drone at a location inside the polygon.
  4. Generate a set of random waypoints within the polygon's bounding box.
  5. Command the drone to follow those waypoints via the REST API.
  6. Monitor progress using the sim-state WebSocket.

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

REST_BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000/ws/drone"
SIM_STATE_URL = "ws://localhost:8000/ws/sim-state"

# Surveillance polygon — an irregular 6-sided area in Lauttasaari (Helsinki).
# Each vertex is [latitude, longitude].
SURVEILLANCE_POLYGON = [
    [60.1550, 24.8750],
    [60.1540, 24.8950],
    [60.1570, 24.9150],
    [60.1680, 24.9100],
    [60.1710, 24.8900],
    [60.1660, 24.8680],
]

# Drone spawn location — near the center of the surveillance polygon.
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
    """Compute the axis-aligned bounding box of a polygon."""
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
    """Generate random [lat, lon] waypoints uniformly distributed inside a bounding box."""
    rng = random.Random(seed)
    waypoints = []
    for _ in range(count):
        lat = rng.uniform(bbox["min_lat"], bbox["max_lat"])
        lon = rng.uniform(bbox["min_lon"], bbox["max_lon"])
        waypoints.append([round(lat, 4), round(lon, 4)])
    return waypoints


# ---------------------------------------------------------------------------
# Main workflow
# ---------------------------------------------------------------------------

async def main():
    # ------------------------------------------------------------------
    # Step 1: Reset the simulator via WS
    # ------------------------------------------------------------------
    print("[Step 1] Resetting simulator...")
    async with websockets.connect(WS_URL) as ws:
        await ws.send(json.dumps({"type": "reset_sim"}))
        while True:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5.0))
            if msg["type"] == "reset_sim_response":
                print(f"  Cleared {msg['cleared_drones']} previous drone(s)")
                break

    # ------------------------------------------------------------------
    # Step 2: Set the surveillance polygon via REST API
    # ------------------------------------------------------------------
    print("\n[Step 2] Setting surveillance polygon via REST API...")
    resp = requests.post(
        f"{REST_BASE_URL}/surveillance-polygon",
        json={"surveillance_polygon": SURVEILLANCE_POLYGON},
    )
    resp.raise_for_status()
    data = resp.json()
    print(f"  Polygon accepted — {data['vertices']} vertices")

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
    # Step 5: Set waypoints via REST API
    # ------------------------------------------------------------------
    print(f"\n[Step 5] Setting waypoints for '{drone_id}' via REST API...")
    resp = requests.post(
        f"{REST_BASE_URL}/set-waypoints",
        json={"waypoints": {drone_id: waypoints}},
    )
    resp.raise_for_status()
    data = resp.json()
    for did, count in data["drones"].items():
        print(f"  {did}: {count} waypoint(s) dispatched")

    # ------------------------------------------------------------------
    # Step 6: Monitor progress via sim-state WebSocket
    # ------------------------------------------------------------------
    total = len(waypoints)
    print(f"\n[Step 6] Monitoring via sim-state WebSocket "
          f"(expecting {total} waypoints)...\n")

    async with websockets.connect(SIM_STATE_URL) as ws:
        while True:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=120.0)
            except asyncio.TimeoutError:
                print("  Timed out waiting for state updates.")
                break

            state = json.loads(raw)
            for drone in state.get("drones", []):
                if drone["id"] == drone_id:
                    completed = len(drone.get("completed_waypoints", []))
                    print(f"  [{completed}/{total}] "
                          f"pos=({drone['lat']:.4f}, {drone['lon']:.4f}) | "
                          f"{'Flying' if drone['is_flying'] else 'Idle'}")
                    if not drone["is_flying"]:
                        print("\nAll waypoints reached. Surveillance patrol complete!")
                        return


if __name__ == "__main__":
    asyncio.run(main())
