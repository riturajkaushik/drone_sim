from fastapi import WebSocket
import json
from drone_state import DroneState, Waypoint, SpawnDroneRequest, SpawnDronesRequest, FollowWaypointsRequest
from pydantic import ValidationError


class DroneWSHandler:
    def __init__(self):
        self.connections: list[WebSocket] = []
        self.sim_state_connections: list[WebSocket] = []
        self.drones: dict[str, DroneState] = {}
        self.surveillance_polygon: list[list[float]] | None = None
        self.nav_corridors: dict[str, dict] | None = None
        self.entry_point: list[float] | None = None
        self.exit_point: list[float] | None = None
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
            # Update backend state tracking
            if drone_id in self.drones:
                state = self.drones[drone_id]
                state.current_waypoint_index = idx
                state.lat = wp.get("lat", state.lat)
                state.lon = wp.get("lon", state.lon)
                # If this was the last waypoint, mark as not flying
                if idx >= len(state.waypoints) - 1:
                    state.is_flying = False
                    state.current_waypoint_index = None
            print(f"Drone {drone_id} reached waypoint #{idx}: ({wp.get('lat')}, {wp.get('lon')})")

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
        self.nav_corridors = None
        self.entry_point = None
        self.exit_point = None
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

        result = await self.dispatch_waypoints(req)
        if "error" in result:
            await self._send_error(ws, result["error"])
            return

        await self._send_to(ws, {
            "type": "follow_waypoints_response",
            "drones": result["drones"],
        })
        print(f"follow_waypoints: dispatched waypoints to {list(req.waypoints.keys())}")

    async def dispatch_waypoints(self, req: FollowWaypointsRequest) -> dict:
        """Validate and dispatch waypoints to drones. Returns result dict.

        Used by both the WS handler and the REST endpoint.
        """
        missing = [did for did in req.waypoints if did not in self.drones]
        if missing:
            return {"error": f"Unknown drone ID(s): {missing}"}

        for drone_id, coord_list in req.waypoints.items():
            waypoints_dicts = [{"lat": c[0], "lon": c[1]} for c in coord_list]
            await self.set_waypoints(drone_id, waypoints_dicts)

        return {
            "drones": {
                did: len(wps) for did, wps in req.waypoints.items()
            },
        }

    async def spawn_drones(self, req: SpawnDronesRequest) -> list[dict]:
        """Register and broadcast new drones. Returns list of spawned drone info dicts.

        Raises ValueError on validation failures (duplicate IDs, occupied locations).
        """
        requests: list[SpawnDroneRequest] = req.drones

        # Collect IDs — assign where missing, check duplicates
        assigned: list[tuple[str, list[float]]] = []
        new_ids: set[str] = set()

        for spawn_req in requests:
            drone_id = spawn_req.drone_id or self._generate_drone_id()

            if drone_id in self.drones:
                raise ValueError(f"Drone ID '{drone_id}' already exists.")
            if drone_id in new_ids:
                raise ValueError(f"Duplicate drone ID '{drone_id}' in request.")

            new_ids.add(drone_id)
            assigned.append((drone_id, spawn_req.spawn_loc))

        # Check location uniqueness against existing drones and within request
        all_locations: list[tuple[float, float]] = [
            (s.lat, s.lon) for s in self.drones.values()
        ]
        for drone_id, spawn_loc in assigned:
            loc_tuple = (spawn_loc[0], spawn_loc[1])
            if loc_tuple in all_locations:
                raise ValueError(
                    f"Spawn location ({spawn_loc[0]}, {spawn_loc[1]}) is already occupied."
                )
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

        print(f"Spawned {len(response_drones)} drone(s): "
              f"{[d['drone_id'] for d in response_drones]}")

        return response_drones

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
            self.drones[drone_id].current_waypoint_index = 0
            self.drones[drone_id].is_flying = True
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

    # --- Sim-state WebSocket helpers ---

    def register_sim_state(self, ws: WebSocket):
        self.sim_state_connections.append(ws)
        print(f"Sim-state client connected. Total: {len(self.sim_state_connections)}")

    def unregister_sim_state(self, ws: WebSocket):
        if ws in self.sim_state_connections:
            self.sim_state_connections.remove(ws)
        print(f"Sim-state client disconnected. Total: {len(self.sim_state_connections)}")

    def get_sim_state(self) -> dict:
        """Build the full simulation state snapshot."""
        drones = []
        for drone_id, state in self.drones.items():
            all_waypoints = [{"lat": wp.lat, "lon": wp.lon} for wp in state.waypoints]
            idx = state.current_waypoint_index
            if idx is not None and state.is_flying:
                completed = all_waypoints[:idx]
                pending = all_waypoints[idx:]
            elif not state.is_flying and len(all_waypoints) > 0:
                completed = all_waypoints
                pending = []
            else:
                completed = []
                pending = all_waypoints
            drones.append({
                "id": drone_id,
                "lat": state.lat,
                "lon": state.lon,
                "speed": state.speed,
                "is_flying": state.is_flying,
                "current_waypoint_index": state.current_waypoint_index,
                "waypoints": all_waypoints,
                "completed_waypoints": completed,
                "pending_waypoints": pending,
            })
        return {
            "type": "sim_state",
            "drones": drones,
            "surveillance_polygon": self.surveillance_polygon,
            "nav_corridors": self.nav_corridors,
            "entry_point": self.entry_point,
            "exit_point": self.exit_point,
        }

    async def broadcast_sim_state(self):
        """Push the current sim state to all sim-state WebSocket clients."""
        if not self.sim_state_connections:
            return
        state = self.get_sim_state()
        data = json.dumps(state)
        disconnected = []
        for ws in self.sim_state_connections:
            try:
                await ws.send_text(data)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self.unregister_sim_state(ws)
