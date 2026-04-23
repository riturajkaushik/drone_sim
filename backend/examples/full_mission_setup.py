"""
Example: Full mission setup with two nav corridors, surveillance area, and entry/exit points.

Demonstrates setting up a complete drone mission with:
  1. A surveillance area polygon with entry and exit points.
  2. Two navigation corridors — approach and departure — each with their own entry/exit points.
  3. A drone that flies: approach corridor → surveillance area → departure corridor.

The corridor entry/exit points use the new per-corridor format:
    {"nav_corridors": {"id": {"vertices": [...], "entry_point": [...], "exit_point": [...]}}}

Usage:
    1. Start the backend:   cd backend && uvicorn main:app --reload --port 8000
    2. Start the frontend:  cd frontend && npm run dev
    3. Run this script:     python examples/full_mission_setup.py
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

# Surveillance polygon — area in central Lauttasaari.
SURVEILLANCE_POLYGON = [
    [60.1600, 24.8850],
    [60.1590, 24.9000],
    [60.1610, 24.9100],
    [60.1670, 24.9080],
    [60.1690, 24.8950],
    [60.1660, 24.8820],
]

# Surveillance entry/exit points — on the polygon boundary.
SURVEILLANCE_ENTRY = [60.1600, 24.8850]
SURVEILLANCE_EXIT = [60.1670, 24.9080]

# Approach corridor — leads from the south-west into the surveillance area.
APPROACH_CORRIDOR = {
    "vertices": [
        [60.1535, 24.8600],
        [60.1545, 24.8600],
        [60.1610, 24.8855],
        [60.1600, 24.8855],
    ],
    "entry_point": [60.1540, 24.8600],
    "exit_point": [60.1605, 24.8855],
}

# Departure corridor — leads from the surveillance area toward the north-east.
DEPARTURE_CORRIDOR = {
    "vertices": [
        [60.1670, 24.9075],
        [60.1680, 24.9075],
        [60.1710, 24.9200],
        [60.1700, 24.9200],
    ],
    "entry_point": [60.1675, 24.9075],
    "exit_point": [60.1705, 24.9200],
}

# Drone spawn location — start of the approach corridor.
DRONE_SPAWN = [60.1540, 24.8600]

# Number of random patrol waypoints inside the surveillance area.
NUM_PATROL_WAYPOINTS = 6
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


def corridor_centerline(vertices: list[list[float]]) -> list[list[float]]:
    """Extract a flyable centerline from a narrow corridor polygon.

    Assumes the corridor is a quad: first two vertices form one end,
    last two form the other end. Returns midpoints as waypoints.
    """
    n = len(vertices)
    half = n // 2
    points = []
    for i in range(half):
        j = n - 1 - i
        mid_lat = (vertices[i][0] + vertices[j][0]) / 2
        mid_lon = (vertices[i][1] + vertices[j][1]) / 2
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
    # Step 2: Create the surveillance area polygon
    # ------------------------------------------------------------------
    print("\n[Step 2] Setting surveillance polygon with entry/exit points...")
    resp = requests.post(
        f"{REST_BASE_URL}/surveillance-polygon",
        json={
            "surveillance_polygon": SURVEILLANCE_POLYGON,
            "entry_point": SURVEILLANCE_ENTRY,
            "exit_point": SURVEILLANCE_EXIT,
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
    # Step 3: Create two navigation corridors with entry/exit points
    # ------------------------------------------------------------------
    print("\n[Step 3] Setting navigation corridors (with entry/exit points)...")
    resp = requests.post(
        f"{REST_BASE_URL}/nav-corridors",
        json={
            "nav_corridors": {
                "approach": APPROACH_CORRIDOR,
                "departure": DEPARTURE_CORRIDOR,
            },
        },
    )
    resp.raise_for_status()
    data = resp.json()
    for cid, vcount in data["corridors"].items():
        corridor_data = data["nav_corridors"][cid]
        entry_pt = corridor_data.get("entry_point", "none")
        exit_pt = corridor_data.get("exit_point", "none")
        print(f"  {cid}: {vcount} vertices, entry={entry_pt}, exit={exit_pt}")

    # ------------------------------------------------------------------
    # Step 4: Spawn a drone at the start of the approach corridor
    # ------------------------------------------------------------------
    drone_id = "scout"
    print(f"\n[Step 4] Spawning drone '{drone_id}'...")
    resp = requests.post(
        f"{REST_BASE_URL}/spawn-drones",
        json={"drones": [
            {"spawn_loc": DRONE_SPAWN, "drone_id": drone_id},
        ]},
    )
    resp.raise_for_status()
    for d in resp.json()["drones"]:
        print(f"  Spawned {d['drone_id']} at ({d['spawn_loc'][0]:.4f}, {d['spawn_loc'][1]:.4f})")

    # ------------------------------------------------------------------
    # Step 5: Build the flight plan
    #
    # Route: approach corridor → surveillance patrol → departure corridor
    # ------------------------------------------------------------------
    approach_waypoints = corridor_centerline(APPROACH_CORRIDOR["vertices"])
    departure_waypoints = corridor_centerline(DEPARTURE_CORRIDOR["vertices"])
    bbox = compute_bounding_box(SURVEILLANCE_POLYGON)
    patrol_waypoints = generate_random_waypoints(bbox, NUM_PATROL_WAYPOINTS, seed=RANDOM_SEED)

    flight_plan = (
        [APPROACH_CORRIDOR["entry_point"]]
        + approach_waypoints
        + [SURVEILLANCE_ENTRY]
        + patrol_waypoints
        + [SURVEILLANCE_EXIT]
        + departure_waypoints
        + [DEPARTURE_CORRIDOR["exit_point"]]
    )

    print(f"\n[Step 5] Flight plan ({len(flight_plan)} waypoints):")
    print(f"  1 approach entry + {len(approach_waypoints)} approach corridor "
          f"+ 1 surv entry + {len(patrol_waypoints)} patrol "
          f"+ 1 surv exit + {len(departure_waypoints)} departure corridor + 1 departure exit")
    for i, wp in enumerate(flight_plan):
        print(f"    #{i:02d}: ({wp[0]:.4f}, {wp[1]:.4f})")

    # ------------------------------------------------------------------
    # Step 6: Dispatch waypoints
    # ------------------------------------------------------------------
    print(f"\n[Step 6] Dispatching waypoints...")
    resp = requests.post(
        f"{REST_BASE_URL}/set-waypoints",
        json={"waypoints": {drone_id: flight_plan}},
    )
    resp.raise_for_status()
    for did, count in resp.json()["drones"].items():
        print(f"  {did}: {count} waypoint(s) dispatched")

    # ------------------------------------------------------------------
    # Step 7: Monitor via sim-state WebSocket until the drone finishes
    # ------------------------------------------------------------------
    total = len(flight_plan)
    print(f"\n[Step 7] Monitoring mission progress...\n")

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
                if did != drone_id:
                    continue

                completed = len(drone.get("completed_waypoints", []))
                flying = drone["is_flying"]

                print(f"  [{did:6s}] [{completed:02d}/{total:02d}] "
                      f"pos=({drone['lat']:.4f}, {drone['lon']:.4f}) | "
                      f"{'Flying' if flying else 'Idle'}")

                if not flying and completed > 0:
                    print(f"\n✅ {did} completed the mission!")
                    print("   Approach corridor → Surveillance patrol → Departure corridor")
                    return


if __name__ == "__main__":
    asyncio.run(main())
