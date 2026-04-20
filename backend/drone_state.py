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


class NavCorridorsRequest(BaseModel):
    """Validates the payload for the POST /nav-corridors endpoint.
    nav_corridors: {"corridor_0": [[lat, lon], ...], "corridor_1": [[lat, lon], ...], ...}
    Each corridor is an ordered list of vertices forming a polygon (at least 3 vertices).
    """
    nav_corridors: dict[str, list[list[float]]]

    @field_validator("nav_corridors")
    @classmethod
    def validate_nav_corridors(cls, v: dict[str, list[list[float]]]) -> dict[str, list[list[float]]]:
        if not v:
            raise ValueError("nav_corridors must contain at least one corridor")
        for corridor_id, vertices in v.items():
            if len(vertices) < 3:
                raise ValueError(
                    f"Corridor '{corridor_id}': requires at least 3 vertices, got {len(vertices)}"
                )
            for i, coord in enumerate(vertices):
                if len(coord) != 2:
                    raise ValueError(
                        f"Corridor '{corridor_id}', vertex {i}: expected [lat, lon], got {coord}"
                    )
                lat, lon = coord
                if not (LAT_MIN <= lat <= LAT_MAX):
                    raise ValueError(
                        f"Corridor '{corridor_id}', vertex {i}: lat {lat} out of bounds [{LAT_MIN}, {LAT_MAX}]"
                    )
                if not (LON_MIN <= lon <= LON_MAX):
                    raise ValueError(
                        f"Corridor '{corridor_id}', vertex {i}: lon {lon} out of bounds [{LON_MIN}, {LON_MAX}]"
                    )
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
