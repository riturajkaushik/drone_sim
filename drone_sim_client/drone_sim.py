import json
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
from algos.polygon import MissionPolygons

import requests
import sys

BACKEND_URL = "http://localhost:8000"

class drone_sim:
    def __init__(self, backend_url=BACKEND_URL, approach_cooridor_id="corridor_1", exit_corridor_id="corridor_2"):
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
        # mission.partition_surveillance(length_x=100, length_y=100, overlap_percentage=20)
        # mission.plan_surveillance_route()

        corridors = self.sim_config.get("navCorridors", [])
        approach_corridor = None
        exit_corridor = None

        for c in corridors:
            if c.get("id") == self.approach_cooridor_id:
                approach_corridor = c
            elif c.get("id") == self.exit_corridor_id:
                exit_corridor = c
        
        if not approach_corridor or not exit_corridor:
            print("Approach or exit corridor not defined in config.")
            sys.exit(1)

        

if __name__ == "__main__":
    sim = drone_sim()