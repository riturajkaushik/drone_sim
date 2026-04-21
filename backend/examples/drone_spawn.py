"""
Example: Spawn 3 drones via the backend REST API and print their IDs and creation status.

Usage:
    1. Start the backend:  cd backend && uvicorn main:app --reload --port 8000
    2. Run this script:    python examples/drone_spawn.py
"""

import requests

REST_BASE_URL = "http://localhost:8000"

DRONES_TO_SPAWN = [
    {"spawn_loc": [60.1620, 24.8900]},
    {"spawn_loc": [60.1650, 24.9000], "drone_id": "scout-1"},
    {"spawn_loc": [60.1580, 24.8700]},
]


def main():
    print(f"Sending spawn request for {len(DRONES_TO_SPAWN)} drone(s)...")
    resp = requests.post(
        f"{REST_BASE_URL}/spawn-drones",
        json={"drones": DRONES_TO_SPAWN},
    )
    resp.raise_for_status()
    data = resp.json()

    print(f"\n{'Drone ID':<20} {'Location':<30} {'Status'}")
    print("-" * 60)
    for drone in data["drones"]:
        loc = drone["spawn_loc"]
        print(f"{drone['drone_id']:<20} ({loc[0]:.4f}, {loc[1]:.4f})          Created")
    print(f"\nSuccessfully spawned {len(data['drones'])} drone(s).")


if __name__ == "__main__":
    main()
