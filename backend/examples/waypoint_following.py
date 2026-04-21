"""
Example: Spawn two drones and send them on different waypoint routes.

Uses REST API for all commands (reset, spawn, set waypoints) and optionally
connects to the sim-state WebSocket for monitoring progress.

Usage:
    1. Start the backend:   cd backend && uvicorn main:app --reload --port 8000
    2. Start the frontend:  cd frontend && npm run dev
    3. Run this script:     python examples/waypoint_following.py
"""

import asyncio
import json

import requests
import websockets

REST_BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000/ws/drone"
SIM_STATE_URL = "ws://localhost:8000/ws/sim-state"

DRONES_TO_SPAWN = [
    {"spawn_loc": [60.1620, 24.8800], "drone_id": "alpha"},
    {"spawn_loc": [60.1660, 24.9000], "drone_id": "bravo"},
]

# Two different waypoint routes around Lauttasaari
WAYPOINTS = {
    "alpha": [
        [60.1640, 24.8850],
        [60.1660, 24.8900],
        [60.1680, 24.8950],
        [60.1660, 24.9000],
        [60.1640, 24.8950],
    ],
    "bravo": [
        [60.1640, 24.9050],
        [60.1620, 24.9100],
        [60.1600, 24.9050],
        [60.1580, 24.9000],
        [60.1600, 24.8950],
    ],
}


async def main():
    # We still need the drone WS for reset (which is a WS-only command)
    async with websockets.connect(WS_URL) as ws:
        # --- Step 0: Reset simulator ---
        print("Resetting simulator...")
        await ws.send(json.dumps({"type": "reset_sim"}))
        while True:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5.0))
            if msg["type"] == "reset_sim_response":
                print(f"  Cleared {msg['cleared_drones']} previous drone(s)")
                break

    # --- Step 1: Spawn drones via REST API ---
    print(f"\nSpawning {len(DRONES_TO_SPAWN)} drone(s) via REST API...")
    resp = requests.post(
        f"{REST_BASE_URL}/spawn-drones",
        json={"drones": DRONES_TO_SPAWN},
    )
    resp.raise_for_status()
    data = resp.json()
    for d in data["drones"]:
        print(f"  Spawned {d['drone_id']} at {d['spawn_loc']}")

    # --- Step 2: Set waypoints via REST API ---
    print(f"\nSetting waypoints for {list(WAYPOINTS.keys())} via REST API...")
    resp = requests.post(
        f"{REST_BASE_URL}/set-waypoints",
        json={"waypoints": WAYPOINTS},
    )
    resp.raise_for_status()
    data = resp.json()
    for drone_id, count in data["drones"].items():
        print(f"  {drone_id}: {count} waypoint(s) dispatched")

    # --- Step 3: Monitor progress via sim-state WebSocket ---
    print("\nMonitoring progress via sim-state WebSocket (Ctrl+C to stop)...\n")
    total_waypoints = {did: len(wps) for did, wps in WAYPOINTS.items()}

    async with websockets.connect(SIM_STATE_URL) as ws:
        while True:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=120.0)
            except asyncio.TimeoutError:
                print("Timed out waiting for state updates.")
                break

            state = json.loads(raw)
            all_done = True
            for drone in state.get("drones", []):
                did = drone["id"]
                if did in total_waypoints:
                    completed = len(drone.get("completed_waypoints", []))
                    total = total_waypoints[did]
                    status = "Idle" if not drone["is_flying"] else "Flying"
                    print(f"  {did}: {status} | "
                          f"pos=({drone['lat']:.4f}, {drone['lon']:.4f}) | "
                          f"waypoints: {completed}/{total}")
                    if drone["is_flying"]:
                        all_done = False

            if all_done:
                break

    print("\nAll waypoints reached. Done.")


if __name__ == "__main__":
    asyncio.run(main())
