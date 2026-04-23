"""
Example: Full mission with entry/exit points, nav corridors, and two drones.

This script demonstrates a complete two-drone surveillance mission:
  1. Reset the simulator to a clean state.
  2. Create a surveillance area polygon (the area drones will patrol).
  3. Create two navigation corridors — an entry corridor and an exit corridor.
  4. Set entry and exit points on the surveillance area boundary.
  5. Spawn two drones near the entry point.
  6. Build flight plans for each drone:
       entry_point → corridor waypoints → patrol waypoints → exit_point
  7. Monitor both drones via the sim-state WebSocket until they reach the exit.

Usage:
    1. Start the backend:   cd backend && uvicorn main:app --reload --port 8000
    2. Start the frontend:  cd frontend && npm run dev
    3. Run this script:     python examples/entry_exit_waypoints.py
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

# Surveillance polygon — irregular hexagonal area in central Lauttasaari.
SURVEILLANCE_POLYGON = [
    [60.1600, 24.8850],
    [60.1590, 24.9000],
    [60.1610, 24.9100],
    [60.1670, 24.9080],
    [60.1690, 24.8950],
    [60.1660, 24.8820],
]

# Entry corridor — a narrow quad leading from the south-west map edge
# into the surveillance area.
ENTRY_CORRIDOR = [
    [60.1535, 24.8600],
    [60.1545, 24.8600],
    [60.1610, 24.8855],
    [60.1600, 24.8855],
]

# Exit corridor — a narrow quad leading from the surveillance area
# toward the north-east map edge.
EXIT_CORRIDOR = [
    [60.1670, 24.9075],
    [60.1680, 24.9075],
    [60.1710, 24.9200],
    [60.1700, 24.9200],
]

# Entry point — where drones enter the surveillance area (south-west edge).
ENTRY_POINT = [60.1600, 24.8850]

# Exit point — where drones leave the surveillance area (north-east edge).
EXIT_POINT = [60.1670, 24.9080]

# Drone spawn locations — two drones near the start of the entry corridor.
DRONE_1_SPAWN = [60.1540, 24.8600]
DRONE_2_SPAWN = [60.1538, 24.8610]

# Number of random patrol waypoints per drone inside the surveillance area.
NUM_PATROL_WAYPOINTS = 5

RANDOM_SEED = 42


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def compute_bounding_box(polygon: list[list[float]]) -> dict:
    """Compute the axis-aligned bounding box of a polygon."""
    lats = [v[0] for v in polygon]
    lons = [v[1] for v in polygon]
    return {
        "min_lat": min(lats), "max_lat": max(lats),
        "min_lon": min(lons), "max_lon": max(lons),
    }


def generate_random_waypoints(
    bbox: dict, count: int, seed: int | None = None,
) -> list[list[float]]:
    """Generate random waypoints within a bounding box."""
    rng = random.Random(seed)
    return [
        [round(rng.uniform(bbox["min_lat"], bbox["max_lat"]), 4),
         round(rng.uniform(bbox["min_lon"], bbox["max_lon"]), 4)]
        for _ in range(count)
    ]


def corridor_centerline(corridor: list[list[float]]) -> list[list[float]]:
    """Extract a flyable centerline from a narrow corridor polygon.

    Assumes the corridor is a quad: first two vertices form one end,
    last two form the other end. Returns midpoints as waypoints.
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
    # ------------------------------------------------------------------
    # Step 1: Reset the simulator via WebSocket
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
    # Step 2: Create the surveillance area polygon with entry/exit via REST
    # ------------------------------------------------------------------
    print("\n[Step 2] Setting surveillance polygon with entry/exit points...")
    resp = requests.post(
        f"{REST_BASE_URL}/surveillance-polygon",
        json={
            "surveillance_polygon": SURVEILLANCE_POLYGON,
            "entry_point": ENTRY_POINT,
            "exit_point": EXIT_POINT,
        },
    )
    resp.raise_for_status()
    data = resp.json()
    print(f"  Polygon accepted — {data['vertices']} vertices")
    if data.get("entry_point"):
        print(f"  Entry: ({data['entry_point'][0]:.4f}, {data['entry_point'][1]:.4f})")
    if data.get("exit_point"):
        print(f"  Exit:  ({data['exit_point'][0]:.4f}, {data['exit_point'][1]:.4f})")

    # ------------------------------------------------------------------
    # Step 3: Create navigation corridors via REST
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Step 4: Spawn two drones near the entry point
    # ------------------------------------------------------------------
    drone_1_id = "alpha"
    drone_2_id = "bravo"
    print(f"\n[Step 4] Spawning drones '{drone_1_id}' and '{drone_2_id}'...")
    resp = requests.post(
        f"{REST_BASE_URL}/spawn-drones",
        json={"drones": [
            {"spawn_loc": DRONE_1_SPAWN, "drone_id": drone_1_id},
            {"spawn_loc": DRONE_2_SPAWN, "drone_id": drone_2_id},
        ]},
    )
    resp.raise_for_status()
    for d in resp.json()["drones"]:
        print(f"  Spawned {d['drone_id']} at ({d['spawn_loc'][0]:.4f}, {d['spawn_loc'][1]:.4f})")

    # ------------------------------------------------------------------
    # Step 5: Build flight plans
    #
    # Each drone follows:
    #   entry_point → entry corridor centerline → random patrol → exit corridor → exit_point
    #
    # The two drones get different random patrol waypoints so they cover
    # different parts of the surveillance area.
    # ------------------------------------------------------------------
    entry_waypoints = corridor_centerline(ENTRY_CORRIDOR)
    exit_waypoints = corridor_centerline(EXIT_CORRIDOR)
    bbox = compute_bounding_box(SURVEILLANCE_POLYGON)

    # Generate distinct patrol waypoints for each drone (different seeds).
    patrol_1 = generate_random_waypoints(bbox, NUM_PATROL_WAYPOINTS, seed=RANDOM_SEED)
    patrol_2 = generate_random_waypoints(bbox, NUM_PATROL_WAYPOINTS, seed=RANDOM_SEED + 1)

    # Full flight plans: start at entry_point, fly through entry corridor,
    # patrol, fly through exit corridor, end at exit_point.
    plan_1 = [ENTRY_POINT] + entry_waypoints + patrol_1 + exit_waypoints + [EXIT_POINT]
    plan_2 = [ENTRY_POINT] + entry_waypoints + patrol_2 + exit_waypoints + [EXIT_POINT]

    print(f"\n[Step 5] Flight plans:")
    print(f"  {drone_1_id}: {len(plan_1)} waypoints "
          f"(1 entry + {len(entry_waypoints)} corridor + {len(patrol_1)} patrol "
          f"+ {len(exit_waypoints)} corridor + 1 exit)")
    print(f"  {drone_2_id}: {len(plan_2)} waypoints "
          f"(1 entry + {len(entry_waypoints)} corridor + {len(patrol_2)} patrol "
          f"+ {len(exit_waypoints)} corridor + 1 exit)")

    for label, plan in [(drone_1_id, plan_1), (drone_2_id, plan_2)]:
        print(f"\n  {label} waypoints:")
        for i, wp in enumerate(plan):
            print(f"    #{i:02d}: ({wp[0]:.4f}, {wp[1]:.4f})")

    # ------------------------------------------------------------------
    # Step 6: Dispatch waypoints via REST
    # ------------------------------------------------------------------
    print(f"\n[Step 6] Dispatching waypoints...")
    resp = requests.post(
        f"{REST_BASE_URL}/set-waypoints",
        json={"waypoints": {
            drone_1_id: plan_1,
            drone_2_id: plan_2,
        }},
    )
    resp.raise_for_status()
    for did, count in resp.json()["drones"].items():
        print(f"  {did}: {count} waypoint(s) dispatched")

    # ------------------------------------------------------------------
    # Step 7: Monitor via sim-state WebSocket until both drones finish
    # ------------------------------------------------------------------
    total_1 = len(plan_1)
    total_2 = len(plan_2)
    print(f"\n[Step 7] Monitoring mission progress...\n")

    finished = set()
    async with websockets.connect(SIM_STATE_URL) as ws:
        while True:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=120.0)
            except asyncio.TimeoutError:
                print("  Timed out waiting for state updates.")
                break

            state = json.loads(raw)
            for drone in state.get("drones", []):
                did = drone["id"]
                if did not in (drone_1_id, drone_2_id):
                    continue

                total = total_1 if did == drone_1_id else total_2
                completed = len(drone.get("completed_waypoints", []))
                flying = drone["is_flying"]

                print(f"  [{did:6s}] [{completed:02d}/{total:02d}] "
                      f"pos=({drone['lat']:.4f}, {drone['lon']:.4f}) | "
                      f"{'Flying' if flying else 'Idle'}")

                if not flying and did not in finished:
                    finished.add(did)
                    print(f"  >>> {did} reached exit point — mission complete!")

            if finished == {drone_1_id, drone_2_id}:
                print("\n✅ Both drones completed their missions!")
                print("   Entry → Corridor → Patrol → Corridor → Exit")
                return


if __name__ == "__main__":
    asyncio.run(main())
