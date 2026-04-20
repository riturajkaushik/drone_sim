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
