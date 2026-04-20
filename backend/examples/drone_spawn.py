"""
Example: Spawn 3 drones via the backend WebSocket and print their IDs and creation status.

Usage:
    1. Start the backend:  cd backend && uvicorn main:app --reload --port 8000
    2. Run this script:    python examples/drone_spawn.py
"""

import asyncio
import json
import websockets

WS_URL = "ws://localhost:8000/ws/drone"

DRONES_TO_SPAWN = [
    {"spawn_loc": [60.1620, 24.8900]},
    {"spawn_loc": [60.1650, 24.9000], "drone_id": "scout-1"},
    {"spawn_loc": [60.1580, 24.8700]},
]


async def main():
    async with websockets.connect(WS_URL) as ws:
        request = {"type": "spawn_drones", "drones": DRONES_TO_SPAWN}
        print(f"Sending spawn request for {len(DRONES_TO_SPAWN)} drone(s)...")
        await ws.send(json.dumps(request))

        # Listen for the response (spawn_drones broadcast + spawn_drones_response)
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
            msg = json.loads(raw)

            if msg["type"] == "spawn_drones_response":
                print(f"\n{'Drone ID':<20} {'Location':<30} {'Status'}")
                print("-" * 60)
                for drone in msg["drones"]:
                    loc = drone["spawn_loc"]
                    print(f"{drone['drone_id']:<20} ({loc[0]:.4f}, {loc[1]:.4f})          Created")
                print(f"\nSuccessfully spawned {len(msg['drones'])} drone(s).")
                break

            elif msg["type"] == "error":
                print(f"Error: {msg['message']}")
                break


if __name__ == "__main__":
    asyncio.run(main())
