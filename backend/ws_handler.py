from fastapi import WebSocket
import json
from drone_state import DroneState, Waypoint, SpawnDroneRequest, FollowWaypointsRequest
from pydantic import ValidationError


class DroneWSHandler:
    def __init__(self):
        self.connections: list[WebSocket] = []
        self.drones: dict[str, DroneState] = {}
        self.surveillance_polygon: list[list[float]] | None = None
        self._next_id = 1

    def _generate_drone_id(self) -> str:
        while True:
            drone_id = f"drone-{self._next_id}"
            self._next_id += 1
            if drone_id not in self.drones:
                return drone_id

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
            drones_data = message.get("drones", [])
            for d in drones_data:
                drone_id = d.get("id")
                if drone_id and drone_id in self.drones:
                    state = self.drones[drone_id]
                    state.lat = d.get("lat", state.lat)
                    state.lon = d.get("lon", state.lon)
                    state.speed = d.get("speed", state.speed)
                    state.is_flying = d.get("is_flying", state.is_flying)
            print(f"Status update for {len(drones_data)} drone(s)")

        elif msg_type == "waypoint_reached":
            drone_id = message.get("drone_id", "unknown")
            wp = message.get("waypoint", {})
            idx = message.get("index", -1)
            print(f"Drone {drone_id} reached waypoint #{idx}: ({wp.get('lat')}, {wp.get('lon')})")

        elif msg_type == "spawn_drones":
            await self._handle_spawn_drones(ws, message)

        elif msg_type == "follow_waypoints":
            await self._handle_follow_waypoints(ws, message)

        elif msg_type == "reset_sim":
            await self._handle_reset_sim(ws)

        else:
            print(f"Unknown message type: {msg_type}")

    async def _handle_reset_sim(self, ws: WebSocket):
        drone_count = len(self.drones)
        self.drones.clear()
        self.surveillance_polygon = None
        self._next_id = 1

        # Tell all frontends to reset
        await self.send_to_all({"type": "reset_sim"})

        # Confirm to the requester
        await self._send_to(ws, {
            "type": "reset_sim_response",
            "cleared_drones": drone_count,
        })
        print(f"Simulator reset: cleared {drone_count} drone(s)")

    async def _handle_follow_waypoints(self, ws: WebSocket, message: dict):
        raw_waypoints = message.get("waypoints", {})
        try:
            req = FollowWaypointsRequest(waypoints=raw_waypoints)
        except ValidationError as e:
            await self._send_error(ws, f"Invalid follow_waypoints payload: {e.errors()}")
            return

        # Verify all drone IDs exist before sending any commands
        missing = [did for did in req.waypoints if did not in self.drones]
        if missing:
            await self._send_error(ws, f"Unknown drone ID(s): {missing}")
            return

        # Fan out set_waypoints per drone
        for drone_id, coord_list in req.waypoints.items():
            waypoints_dicts = [{"lat": c[0], "lon": c[1]} for c in coord_list]
            await self.set_waypoints(drone_id, waypoints_dicts)

        await self._send_to(ws, {
            "type": "follow_waypoints_response",
            "drones": {
                did: len(wps) for did, wps in req.waypoints.items()
            },
        })
        print(f"follow_waypoints: dispatched waypoints to {list(req.waypoints.keys())}")

    async def _handle_spawn_drones(self, ws: WebSocket, message: dict):
        raw_drones = message.get("drones", [])
        if not raw_drones:
            await self._send_error(ws, "No drones provided in spawn request.")
            return

        # Validate each request via Pydantic
        requests: list[SpawnDroneRequest] = []
        for i, raw in enumerate(raw_drones):
            try:
                requests.append(SpawnDroneRequest(**raw))
            except ValidationError as e:
                await self._send_error(ws, f"Invalid drone at index {i}: {e.errors()}")
                return

        # Collect IDs — assign where missing, check duplicates
        assigned: list[tuple[str, list[float]]] = []
        new_ids: set[str] = set()

        for req in requests:
            drone_id = req.drone_id or self._generate_drone_id()

            if drone_id in self.drones:
                await self._send_error(ws, f"Drone ID '{drone_id}' already exists.")
                return
            if drone_id in new_ids:
                await self._send_error(ws, f"Duplicate drone ID '{drone_id}' in request.")
                return

            new_ids.add(drone_id)
            assigned.append((drone_id, req.spawn_loc))

        # Check location uniqueness against existing drones and within request
        all_locations: list[tuple[float, float]] = [
            (s.lat, s.lon) for s in self.drones.values()
        ]
        for drone_id, spawn_loc in assigned:
            loc_tuple = (spawn_loc[0], spawn_loc[1])
            if loc_tuple in all_locations:
                await self._send_error(
                    ws,
                    f"Spawn location ({spawn_loc[0]}, {spawn_loc[1]}) is already occupied.",
                )
                return
            all_locations.append(loc_tuple)

        # All checks passed — register drones
        response_drones = []
        for drone_id, spawn_loc in assigned:
            self.drones[drone_id] = DroneState(
                id=drone_id, lat=spawn_loc[0], lon=spawn_loc[1]
            )
            response_drones.append({
                "drone_id": drone_id,
                "spawn_loc": spawn_loc,
            })

        # Broadcast to all frontends so they create the drone sprites
        await self.send_to_all({
            "type": "spawn_drones",
            "drones": response_drones,
        })

        # Send confirmation back to the requester
        await self._send_to(ws, {
            "type": "spawn_drones_response",
            "drones": response_drones,
        })

        print(f"Spawned {len(response_drones)} drone(s): "
              f"{[d['drone_id'] for d in response_drones]}")

    async def _send_error(self, ws: WebSocket, error_msg: str):
        await self._send_to(ws, {"type": "error", "message": error_msg})

    async def _send_to(self, ws: WebSocket, message: dict):
        try:
            await ws.send_text(json.dumps(message))
        except Exception:
            self.unregister(ws)

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

    async def set_waypoints(self, drone_id: str, waypoints: list[dict]):
        """Command a drone to fly to a sequence of waypoints."""
        if drone_id in self.drones:
            self.drones[drone_id].waypoints = [Waypoint(**wp) for wp in waypoints]
        await self.send_to_all({
            "type": "set_waypoints",
            "drone_id": drone_id,
            "waypoints": waypoints,
        })

    async def set_velocity(self, drone_id: str, speed: float):
        """Command a drone to change speed."""
        if drone_id in self.drones:
            self.drones[drone_id].speed = speed
        await self.send_to_all({
            "type": "set_velocity",
            "drone_id": drone_id,
            "speed": speed,
        })

    async def get_status(self):
        """Request status from the drone frontend."""
        await self.send_to_all({
            "type": "get_status",
        })
