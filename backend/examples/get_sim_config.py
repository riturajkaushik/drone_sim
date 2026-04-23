"""
Example: Retrieve the simulator configuration via REST API.

Fetches the current sim config (map bounds, surveillance polygon, nav corridors)
from the GET /sim-config endpoint and prints it.

Usage:
    1. Start the backend:  cd backend && uvicorn main:app --reload --port 8000
    2. (Optional) Set up a mission first — e.g. run full_mission_setup.py
    3. Run this script:    python examples/get_sim_config.py
"""

import json
import sys

import requests

REST_BASE_URL = "http://localhost:8000"


def main():
    print("Fetching simulator config...\n")
    try:
        resp = requests.get(f"{REST_BASE_URL}/sim-config", timeout=5)
        resp.raise_for_status()
    except requests.ConnectionError:
        print("ERROR: Could not connect to backend. Is it running on port 8000?")
        sys.exit(1)

    config = resp.json()
    print(json.dumps(config, indent=2))

    # --- Access individual fields ---
    print("\n--- Map Bounds ---")
    bounds = config["mapBounds"]
    print(f"  Top-left:     ({bounds['topLeft']['lat']}, {bounds['topLeft']['lon']})")
    print(f"  Bottom-right: ({bounds['bottomRight']['lat']}, {bounds['bottomRight']['lon']})")

    print("\n--- Surveillance Polygon ---")
    surveillance = config.get("surveillance", [])
    if surveillance:
        print(f"  {len(surveillance)} vertices")
        for i, v in enumerate(surveillance):
            # Support both {lat, lon} objects and [lat, lon] arrays
            if isinstance(v, dict):
                print(f"    #{i}: ({v['lat']}, {v['lon']})")
            else:
                print(f"    #{i}: ({v[0]}, {v[1]})")
    else:
        print("  (none set)")

    entry = config.get("surveillanceEntryPoint")
    exit_ = config.get("surveillanceExitPoint")
    if entry:
        print(f"  Entry point: ({entry['lat']}, {entry['lon']})")
    if exit_:
        print(f"  Exit point:  ({exit_['lat']}, {exit_['lon']})")

    print("\n--- Navigation Corridors ---")
    corridors = config.get("navCorridors", [])
    if corridors:
        for c in corridors:
            print(f"  {c['id']}: {len(c['vertices'])} vertices")
            ep = c.get("entryPoint")
            xp = c.get("exitPoint")
            if ep:
                print(f"    Entry: ({ep['lat']}, {ep['lon']})")
            if xp:
                print(f"    Exit:  ({xp['lat']}, {xp['lon']})")
    else:
        print("  (none set)")


if __name__ == "__main__":
    main()
