"""
Example: Full mission — surveillance polygon, navigation corridors, drone patrol.

This script demonstrates a complete drone mission workflow:
  1. Reset the simulator.
  2. Set a surveillance polygon (the area of interest).
  3. Set two navigation corridors — an entry corridor to reach the surveillance
     area and an exit corridor to leave it.
  4. Spawn a drone at the start of the entry corridor.
  5. Generate random waypoints inside the surveillance polygon's bounding box.
  6. Build the full flight plan: entry corridor → random surveillance waypoints → exit corridor.
  7. Command the drone to follow the plan and listen for progress until done.

Usage:
    1. Start the backend:   cd backend && uvicorn main:app --reload --port 8000
    2. Start the frontend:  cd frontend && npm run dev
    3. Run this script:     python examples/nav_corridors.py
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

# Surveillance polygon — irregular area in central Lauttasaari.
SURVEILLANCE_POLYGON = [
    [60.1600, 24.8850],
    [60.1590, 24.9000],
    [60.1610, 24.9100],
    [60.1670, 24.9080],
    [60.1690, 24.8950],
    [60.1660, 24.8820],
]

# Entry corridor — a narrow polygon leading from the south-west map edge
# into the surveillance area.
ENTRY_CORRIDOR = [
    [60.1535, 24.8600],
    [60.1545, 24.8600],
    [60.1610, 24.8855],
    [60.1600, 24.8855],
]

# Exit corridor — a narrow polygon leading from the surveillance area
# toward the north-east map edge.
EXIT_CORRIDOR = [
    [60.1670, 24.9075],
    [60.1680, 24.9075],
    [60.1710, 24.9200],
    [60.1700, 24.9200],
]

# Drone spawn — start of the entry corridor.
DRONE_SPAWN_LAT = 60.1540
DRONE_SPAWN_LON = 24.8600

# Number of random surveillance waypoints inside the polygon's bounding box.
NUM_RANDOM_WAYPOINTS = 6

RANDOM_SEED = 7


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def compute_bounding_box(polygon: list[list[float]]) -> dict:
    lats = [v[0] for v in polygon]
    lons = [v[1] for v in polygon]
    return {
        "min_lat": min(lats), "max_lat": max(lats),
        "min_lon": min(lons), "max_lon": max(lons),
    }


def generate_random_waypoints(
    bbox: dict, count: int, seed: int | None = None,
) -> list[list[float]]:
    rng = random.Random(seed)
    return [
        [round(rng.uniform(bbox["min_lat"], bbox["max_lat"]), 4),
         round(rng.uniform(bbox["min_lon"], bbox["max_lon"]), 4)]
        for _ in range(count)
    ]


def corridor_centerline(corridor: list[list[float]]) -> list[list[float]]:
    """Extract a flyable centerline from a corridor polygon.

    Assumes the corridor is defined as a narrow quad: the first two vertices
    form one end, the last two form the other end. The centerline connects the
    midpoints of opposite edges.
    """
    n = len(corridor)
    half = n // 2
    points = []
    for i in range(half):
        j = n - 1 - i
        mid_lat = (corridor[i][0] + corridor[j][0]) / 2
        mid_lon = (corridor[i][1] + corridor[j][1]) / 2
        points.append([round(mid_lat, 4), round(mid_lon, 4)])
    return points


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    print("Connecting to backend WebSocket...")
    async with websockets.connect(WS_URL) as ws:

        # Step 1: Reset
        print("\n[Step 1] Resetting simulator...")
        await ws.send(json.dumps({"type": "reset_sim"}))
        while True:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5.0))
            if msg["type"] == "reset_sim_response":
                print(f"  Cleared {msg['cleared_drones']} previous drone(s)")
                break

        # Step 2: Set surveillance polygon
        print("\n[Step 2] Setting surveillance polygon...")
        resp = requests.post(
            f"{REST_BASE_URL}/surveillance-polygon",
            json={"surveillance_polygon": SURVEILLANCE_POLYGON},
        )
        resp.raise_for_status()
        data = resp.json()
        print(f"  Polygon accepted — {data['vertices']} vertices")
        await asyncio.sleep(0.2)

        # Step 3: Set navigation corridors
        print("\n[Step 3] Setting navigation corridors...")
        resp = requests.post(
            f"{REST_BASE_URL}/nav-corridors",
            json={
                "nav_corridors": {
                    "entry": ENTRY_CORRIDOR,
                    "exit": EXIT_CORRIDOR,
                },
            },
        )
        resp.raise_for_status()
        data = resp.json()
        for cid, vcount in data["corridors"].items():
            print(f"  {cid}: {vcount} vertices")
        await asyncio.sleep(0.2)

        # Step 4: Spawn drone at the entry corridor start via REST API
        drone_id = "patrol-1"
        print(f"\n[Step 4] Spawning drone '{drone_id}' at "
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

        # Step 5: Build flight plan
        entry_waypoints = corridor_centerline(ENTRY_CORRIDOR)
        exit_waypoints = corridor_centerline(EXIT_CORRIDOR)
        bbox = compute_bounding_box(SURVEILLANCE_POLYGON)
        patrol_waypoints = generate_random_waypoints(bbox, NUM_RANDOM_WAYPOINTS, RANDOM_SEED)

        flight_plan = entry_waypoints + patrol_waypoints + exit_waypoints

        print(f"\n[Step 5] Flight plan ({len(flight_plan)} waypoints):")
        print(f"  Entry corridor:  {len(entry_waypoints)} wp")
        print(f"  Patrol (random): {len(patrol_waypoints)} wp")
        print(f"  Exit corridor:   {len(exit_waypoints)} wp")
        for i, wp in enumerate(flight_plan):
            print(f"    #{i:02d}: ({wp[0]:.4f}, {wp[1]:.4f})")

        # Step 6: Dispatch waypoints
        print(f"\n[Step 6] Sending flight plan to '{drone_id}'...")
        await ws.send(json.dumps({
            "type": "follow_waypoints",
            "waypoints": {drone_id: flight_plan},
        }))
        while True:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5.0))
            if msg["type"] == "follow_waypoints_response":
                for did, count in msg["drones"].items():
                    print(f"  {did}: {count} waypoint(s) dispatched")
                break
            elif msg["type"] == "error":
                print(f"  Error: {msg['message']}")
                return

        # Step 7: Listen for progress
        total = len(flight_plan)
        reached = 0
        print(f"\n[Step 7] Listening for waypoint events ({total} total)...\n")

        while reached < total:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=120.0)
            except asyncio.TimeoutError:
                print("  Timed out waiting for waypoint events.")
                break

            msg = json.loads(raw)
            if msg["type"] == "waypoint_reached":
                reached += 1
                did = msg.get("drone_id", "?")
                wp = msg.get("waypoint", {})
                idx = msg.get("index", -1)
                phase = (
                    "ENTRY" if reached <= len(entry_waypoints)
                    else "EXIT" if reached > len(entry_waypoints) + len(patrol_waypoints)
                    else "PATROL"
                )
                print(f"  [{reached:02d}/{total:02d}] [{phase:6s}] {did} → "
                      f"wp#{idx} ({wp.get('lat', 0):.4f}, {wp.get('lon', 0):.4f})")

        print("\nMission complete! Drone entered via corridor, patrolled, and exited.")


if __name__ == "__main__":
    asyncio.run(main())
