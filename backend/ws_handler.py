from fastapi import WebSocket
import json
from drone_state import DroneState, Waypoint


class DroneWSHandler:
    def __init__(self):
        self.connections: list[WebSocket] = []
        self.drone_state = DroneState()

    def register(self, ws: WebSocket):
        self.connections.append(ws)
        print(f"Client connected. Total: {len(self.connections)}")

    def unregister(self, ws: WebSocket):
        if ws in self.connections:
            self.connections.remove(ws)
        print(f"Client disconnected. Total: {len(self.connections)}")

    async def handle_message(self, ws: WebSocket, message: dict):
        msg_type = message.get("type")

        if msg_type == "status_response":
            self.drone_state.lat = message.get("lat", self.drone_state.lat)
            self.drone_state.lon = message.get("lon", self.drone_state.lon)
            self.drone_state.speed = message.get("speed", self.drone_state.speed)
            self.drone_state.is_flying = message.get("is_flying", self.drone_state.is_flying)
            print(f"Drone status: ({self.drone_state.lat:.4f}, {self.drone_state.lon:.4f}) "
                  f"speed={self.drone_state.speed} flying={self.drone_state.is_flying}")

        elif msg_type == "waypoint_reached":
            wp = message.get("waypoint", {})
            idx = message.get("index", -1)
            print(f"Drone reached waypoint #{idx}: ({wp.get('lat')}, {wp.get('lon')})")

        else:
            print(f"Unknown message type: {msg_type}")

    async def send_to_all(self, message: dict):
        """Send a message to all connected clients."""
        data = json.dumps(message)
        disconnected = []
        for ws in self.connections:
            try:
                await ws.send_text(data)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self.unregister(ws)

    async def set_waypoints(self, waypoints: list[dict]):
        """Command the drone to fly to a sequence of waypoints."""
        self.drone_state.waypoints = [Waypoint(**wp) for wp in waypoints]
        await self.send_to_all({
            "type": "set_waypoints",
            "waypoints": waypoints,
        })

    async def set_velocity(self, speed: float):
        """Command the drone to change speed."""
        self.drone_state.speed = speed
        await self.send_to_all({
            "type": "set_velocity",
            "speed": speed,
        })

    async def get_status(self):
        """Request status from the drone frontend."""
        await self.send_to_all({
            "type": "get_status",
        })
