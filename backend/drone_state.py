from pydantic import BaseModel
from typing import Optional


class Waypoint(BaseModel):
    lat: float
    lon: float


class DroneState(BaseModel):
    lat: float = 60.1620
    lon: float = 24.8900
    speed: float = 10.0
    is_flying: bool = False
    waypoints: list[Waypoint] = []
    current_waypoint_index: Optional[int] = None
