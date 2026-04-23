import json
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
from algos.polygon import MissionPolygons

import requests
import sys

BACKEND_URL = "http://localhost:8000"

class drone_sim:
    def __init__(self, backend_url=BACKEND_URL, approach_cooridor_id="corridor-1", exit_corridor_id="corridor-2"):
        self.backend_url = backend_url.rstrip("/")
        self.approach_cooridor_id = approach_cooridor_id
        self.exit_corridor_id = exit_corridor_id
        self.sim_config = self._fetch_sim_config()
        self.backend_url = backend_url.rstrip("/")
        print(f"Initialized drone simulation with config: {self.sim_config}")

    def _fetch_sim_config(self):
        """Fetch the simulation configuration from the backend."""
        try:
            resp = requests.get(f"{self.backend_url}/sim-config", timeout=5)
            resp.raise_for_status()
        except requests.ConnectionError:
            print("ERROR: Could not connect to backend. Is it running on port 8000?")
            sys.exit(1)

        config = resp.json()
        return config
    
    def plan_path(self):
        """Example method to plan an approach path based on the sim config."""
        # For demonstration, we'll just print the surveillance entry point and nav corridor entries
        surveillance_entry = self.sim_config.get("surveillanceEntryPoint")
        surveillance_exit = self.sim_config.get("surveillanceExitPoint")    
        surveillance_polygon = self.sim_config.get("surveillance", [])

        if not surveillance_entry or not surveillance_exit or not surveillance_polygon:
            print("Surveillance entry or exit point or polygon not defined in config.")
            sys.exit(1)

        mission = MissionPolygons(
            coordinates=surveillance_polygon,
            entry_point=surveillance_entry,
            exit_point=surveillance_exit,
        )

        # # Partition and plan the surveillance route
        mission.partition_surveillance(length_x=300, length_y=160, overlap_percentage=20)
        surveillance_path = mission.plan_surveillance_route()

        corridors = self.sim_config.get("navCorridors", [])
        approach_corridor = None
        exit_corridor = None

        for c in corridors:
            if c.get("id") == self.approach_cooridor_id:
                approach_corridor = c
                assert approach_corridor.get("entryPoint") and approach_corridor.get("exitPoint"), "Approach corridor must have entry and exit points defined."
            elif c.get("id") == self.exit_corridor_id:
                exit_corridor = c
                assert exit_corridor.get("entryPoint") and exit_corridor.get("exitPoint"), "Exit corridor must have entry and exit points defined."
        
        if not approach_corridor or not exit_corridor:
            print("Approach or exit corridor not defined in config.")
            sys.exit(1)

        mission.add_nav_polygon(
                polygon_id="approach",
                points=approach_corridor.get("vertices", []),
                entry_point=approach_corridor.get("entryPoint"),
                exit_point=approach_corridor.get("exitPoint"),
            )
        # Nav path planning settings
        NUM_SAMPLES = 100        # random sample points for path planning
        BORDER_DISTANCE = 50.0   # min distance from polygon edges in meters
        MIN_PATH_POINTS = 10     # minimum waypoints in the path for smoothness

        approach_path = mission.plan_nav_path(
            "approach",
            num_samples=NUM_SAMPLES,
            border_distance=BORDER_DISTANCE,
            min_path_points=MIN_PATH_POINTS,
        )

        mission.add_nav_polygon(
                polygon_id="exit",
                points=exit_corridor.get("vertices", []),
                entry_point=exit_corridor.get("entryPoint"),
                exit_point=exit_corridor.get("exitPoint"),
            )
        exit_path = mission.plan_nav_path(
            "exit",
            num_samples=NUM_SAMPLES,
            border_distance=BORDER_DISTANCE,
            min_path_points=MIN_PATH_POINTS,
        )

        # mission.render()



        combined_path = [[p["lat"], p["lon"]] for p in approach_path] + [[p["lat"], p["lon"]] for p in surveillance_path] + [[p["lat"], p["lon"]] for p in exit_path]
        
        waypoints = {
            "drone-1": combined_path,
        }


        # Spawn a drone and set its waypoints
        DRONES_TO_SPAWN = [
            {"spawn_loc": [approach_path[0]["lat"], approach_path[0]["lon"]], "drone_id": "drone-1"},
        ]

        resp = requests.post(
            f"{self.backend_url}/spawn-drones",
            json={"drones": DRONES_TO_SPAWN},
        )

        print(resp.json())

        # Set waypoints via REST API
        resp = requests.post(
            f"{self.backend_url}/set-waypoints",
            json={"waypoints": waypoints},
        )

        print(resp.json())


if __name__ == "__main__":
    sim = drone_sim()
    sim.plan_path()