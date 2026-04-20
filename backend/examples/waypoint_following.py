"""
Example: Spawn two drones and send them on different waypoint routes.

Usage:
    1. Start the backend:   cd backend && uvicorn main:app --reload --port 8000
    2. Start the frontend:  cd frontend && npm run dev
    3. Run this script:     python examples/waypoint_following.py
"""

import asyncio
import json
import websockets

WS_URL = "ws://localhost:8000/ws/drone"

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
    async with websockets.connect(WS_URL) as ws:
        # --- Step 1: Spawn drones ---
        spawn_req = {"type": "spawn_drones", "drones": DRONES_TO_SPAWN}
        print(f"Spawning {len(DRONES_TO_SPAWN)} drone(s)...")
        await ws.send(json.dumps(spawn_req))

        # Wait for spawn confirmation
        while True:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5.0))
            if msg["type"] == "spawn_drones_response":
                for d in msg["drones"]:
                    print(f"  Spawned {d['drone_id']} at {d['spawn_loc']}")
                break
            elif msg["type"] == "error":
                print(f"  Error: {msg['message']}")
                return

        # --- Step 2: Send follow_waypoints ---
        follow_req = {"type": "follow_waypoints", "waypoints": WAYPOINTS}
        print(f"\nSending waypoints to {list(WAYPOINTS.keys())}...")
        await ws.send(json.dumps(follow_req))

        # Wait for follow_waypoints confirmation
        while True:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5.0))
            if msg["type"] == "follow_waypoints_response":
                for drone_id, count in msg["drones"].items():
                    print(f"  {drone_id}: {count} waypoint(s) dispatched")
                break
            elif msg["type"] == "error":
                print(f"  Error: {msg['message']}")
                return

        # --- Step 3: Listen for waypoint_reached events ---
        print("\nListening for waypoint events (Ctrl+C to stop)...\n")
        remaining = {did: len(wps) for did, wps in WAYPOINTS.items()}

        while any(r > 0 for r in remaining.values()):
            try:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=60.0))
            except asyncio.TimeoutError:
                print("Timed out waiting for waypoint events.")
                break

            if msg["type"] == "waypoint_reached":
                did = msg.get("drone_id", "?")
                wp = msg.get("waypoint", {})
                idx = msg.get("index", -1)
                print(f"  {did} reached waypoint #{idx}: ({wp.get('lat', 0):.4f}, {wp.get('lon', 0):.4f})")
                if did in remaining:
                    remaining[did] = max(0, remaining[did] - 1)

        print("\nAll waypoints reached. Done.")


if __name__ == "__main__":
    asyncio.run(main())
