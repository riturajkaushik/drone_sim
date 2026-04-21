"""
Example: Connect to the sim-state WebSocket and print live simulation state.

This script demonstrates the /ws/sim-state WebSocket endpoint which streams
the full simulation state every 500ms. It shows:
  - All drone positions, velocities, and flight status
  - Completed and pending waypoints per drone
  - Surveillance polygon (if set)
  - Navigation corridors (if set)

Run this alongside any other example script to see the state updates in real time.

Usage:
    1. Start the backend:   cd backend && uvicorn main:app --reload --port 8000
    2. Start the frontend:  cd frontend && npm run dev
    3. Run this script:     python examples/sim_state_monitor.py
    4. In another terminal, run an example like waypoint_following.py
"""

import asyncio
import json

import websockets

SIM_STATE_URL = "ws://localhost:8000/ws/sim-state"


def format_state(state: dict) -> str:
    """Format a sim state snapshot into a readable string."""
    lines = []
    lines.append("=" * 70)

    # Drones
    drones = state.get("drones", [])
    lines.append(f"Drones: {len(drones)}")
    for drone in drones:
        completed = len(drone.get("completed_waypoints", []))
        pending = len(drone.get("pending_waypoints", []))
        total = len(drone.get("waypoints", []))
        status = "Flying" if drone["is_flying"] else "Idle"
        lines.append(
            f"  {drone['id']:>12s} | "
            f"pos=({drone['lat']:.4f}, {drone['lon']:.4f}) | "
            f"speed={drone['speed']:.0f} m/s | "
            f"{status:7s} | "
            f"wp: {completed}/{total} done, {pending} pending"
        )

    # Surveillance polygon
    polygon = state.get("surveillance_polygon")
    if polygon:
        lines.append(f"Surveillance polygon: {len(polygon)} vertices")
    else:
        lines.append("Surveillance polygon: not set")

    # Nav corridors
    corridors = state.get("nav_corridors")
    if corridors:
        corridor_info = ", ".join(
            f"{cid}({len(verts)} pts)" for cid, verts in corridors.items()
        )
        lines.append(f"Nav corridors: {corridor_info}")
    else:
        lines.append("Nav corridors: not set")

    lines.append("=" * 70)
    return "\n".join(lines)


async def main():
    print(f"Connecting to sim-state WebSocket at {SIM_STATE_URL}...")
    print("Press Ctrl+C to stop.\n")

    async with websockets.connect(SIM_STATE_URL) as ws:
        while True:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=30.0)
            except asyncio.TimeoutError:
                print("No state update received in 30s, still waiting...")
                continue

            state = json.loads(raw)
            print(format_state(state))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nMonitor stopped.")
