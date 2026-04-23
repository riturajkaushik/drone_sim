from pydantic import BaseModel, field_validator
from typing import Optional

# Map bounds (Lauttasaari, Helsinki)
LAT_MIN, LAT_MAX = 60.1520, 60.1720
LON_MIN, LON_MAX = 24.8550, 24.9250


class Waypoint(BaseModel):
    lat: float
    lon: float


class DroneState(BaseModel):
    id: str
    lat: float = 60.1620
    lon: float = 24.8900
    speed: float = 10.0
    is_flying: bool = False
    waypoints: list[Waypoint] = []
    current_waypoint_index: Optional[int] = None


class SpawnDroneRequest(BaseModel):
    spawn_loc: list[float]  # [lat, lon]
    drone_id: Optional[str] = None

    @field_validator("spawn_loc")
    @classmethod
    def validate_spawn_loc(cls, v: list[float]) -> list[float]:
        if len(v) != 2:
            raise ValueError("spawn_loc must be [lat, lon]")
        lat, lon = v
        if not (LAT_MIN <= lat <= LAT_MAX):
            raise ValueError(f"lat {lat} out of bounds [{LAT_MIN}, {LAT_MAX}]")
        if not (LON_MIN <= lon <= LON_MAX):
            raise ValueError(f"lon {lon} out of bounds [{LON_MIN}, {LON_MAX}]")
        return v


class SpawnDronesRequest(BaseModel):
    """Validates the payload for the POST /spawn-drones endpoint.
    drones: list of SpawnDroneRequest objects.
    """
    drones: list[SpawnDroneRequest]


class SpawnDronesResponse(BaseModel):
    drones: list[dict]  # [{"drone_id": str, "spawn_loc": [lat, lon]}, ...]


class SurveillancePolygonRequest(BaseModel):
    """Validates the payload for the POST /surveillance-polygon endpoint.
    surveillance_polygon: [[lat, lon], [lat, lon], ...] — at least 3 vertices.
    """
    surveillance_polygon: list[list[float]]

    @field_validator("surveillance_polygon")
    @classmethod
    def validate_polygon(cls, v: list[list[float]]) -> list[list[float]]:
        if len(v) < 3:
            raise ValueError("A surveillance polygon requires at least 3 vertices")
        for i, coord in enumerate(v):
            if len(coord) != 2:
                raise ValueError(f"Vertex {i}: expected [lat, lon], got {coord}")
            lat, lon = coord
            if not (LAT_MIN <= lat <= LAT_MAX):
                raise ValueError(f"Vertex {i}: lat {lat} out of bounds [{LAT_MIN}, {LAT_MAX}]")
            if not (LON_MIN <= lon <= LON_MAX):
                raise ValueError(f"Vertex {i}: lon {lon} out of bounds [{LON_MIN}, {LON_MAX}]")
        return v


class NavCorridorData(BaseModel):
    """Data for a single navigation corridor: vertices + optional entry/exit points."""
    vertices: list[list[float]]
    entry_point: Optional[list[float]] = None
    exit_point: Optional[list[float]] = None

    @field_validator("vertices")
    @classmethod
    def validate_vertices(cls, v: list[list[float]]) -> list[list[float]]:
        if len(v) < 3:
            raise ValueError(f"Requires at least 3 vertices, got {len(v)}")
        for i, coord in enumerate(v):
            if len(coord) != 2:
                raise ValueError(f"Vertex {i}: expected [lat, lon], got {coord}")
            lat, lon = coord
            if not (LAT_MIN <= lat <= LAT_MAX):
                raise ValueError(f"Vertex {i}: lat {lat} out of bounds [{LAT_MIN}, {LAT_MAX}]")
            if not (LON_MIN <= lon <= LON_MAX):
                raise ValueError(f"Vertex {i}: lon {lon} out of bounds [{LON_MIN}, {LON_MAX}]")
        return v

    @field_validator("entry_point", "exit_point")
    @classmethod
    def validate_optional_point(cls, v: Optional[list[float]], info) -> Optional[list[float]]:
        if v is None:
            return v
        if len(v) != 2:
            raise ValueError(f"{info.field_name} must be [lat, lon]")
        lat, lon = v
        if not (LAT_MIN <= lat <= LAT_MAX):
            raise ValueError(f"{info.field_name}: lat {lat} out of bounds [{LAT_MIN}, {LAT_MAX}]")
        if not (LON_MIN <= lon <= LON_MAX):
            raise ValueError(f"{info.field_name}: lon {lon} out of bounds [{LON_MIN}, {LON_MAX}]")
        return v


class NavCorridorsRequest(BaseModel):
    """Validates the payload for the POST /nav-corridors endpoint.

    Accepts two formats:
      New: {"nav_corridors": {"id": {"vertices": [...], "entry_point": [...], "exit_point": [...]}, ...}}
      Legacy: {"nav_corridors": {"id": [[lat, lon], ...], ...}}
    """
    nav_corridors: dict[str, NavCorridorData | list[list[float]]]

    @field_validator("nav_corridors")
    @classmethod
    def normalize_nav_corridors(cls, v):
        if not v:
            raise ValueError("nav_corridors must contain at least one corridor")
        normalized = {}
        for corridor_id, data in v.items():
            if isinstance(data, NavCorridorData):
                normalized[corridor_id] = data
            elif isinstance(data, list):
                normalized[corridor_id] = NavCorridorData(vertices=data)
            else:
                raise ValueError(f"Corridor '{corridor_id}': invalid format")
        return normalized


class EntryExitPointsRequest(BaseModel):
    """Validates the payload for the POST /entry-exit-points endpoint.
    entry_point: [lat, lon] — the entry point for the surveillance area.
    exit_point: [lat, lon] — the exit point for the surveillance area.
    """
    entry_point: list[float]
    exit_point: list[float]

    @field_validator("entry_point", "exit_point")
    @classmethod
    def validate_point(cls, v: list[float], info) -> list[float]:
        if len(v) != 2:
            raise ValueError(f"{info.field_name} must be [lat, lon]")
        lat, lon = v
        if not (LAT_MIN <= lat <= LAT_MAX):
            raise ValueError(f"{info.field_name}: lat {lat} out of bounds [{LAT_MIN}, {LAT_MAX}]")
        if not (LON_MIN <= lon <= LON_MAX):
            raise ValueError(f"{info.field_name}: lon {lon} out of bounds [{LON_MIN}, {LON_MAX}]")
        return v


class FollowWaypointsRequest(BaseModel):
    """Validates the payload for follow_waypoints messages.
    waypoints: {drone_id: [[lat, lon], [lat, lon], ...], ...}
    """
    waypoints: dict[str, list[list[float]]]

    @field_validator("waypoints")
    @classmethod
    def validate_waypoints(cls, v: dict[str, list[list[float]]]) -> dict[str, list[list[float]]]:
        if not v:
            raise ValueError("waypoints must contain at least one drone")
        for drone_id, wp_list in v.items():
            if not wp_list:
                raise ValueError(f"Drone '{drone_id}' has an empty waypoint list")
            for i, coord in enumerate(wp_list):
                if len(coord) != 2:
                    raise ValueError(
                        f"Drone '{drone_id}', waypoint {i}: expected [lat, lon], got {coord}"
                    )
                lat, lon = coord
                if not (LAT_MIN <= lat <= LAT_MAX):
                    raise ValueError(
                        f"Drone '{drone_id}', waypoint {i}: lat {lat} out of bounds [{LAT_MIN}, {LAT_MAX}]"
                    )
                if not (LON_MIN <= lon <= LON_MAX):
                    raise ValueError(
                        f"Drone '{drone_id}', waypoint {i}: lon {lon} out of bounds [{LON_MIN}, {LON_MAX}]"
                    )
        return v
