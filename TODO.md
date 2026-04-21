[x] Read the space partition code and how to create the polygon int he algo directory. We need to implement the create of a polygon maually from the frontend. We will add the points (lat lon) and press create. When we add a point, it shoud be rendered. When we press create, entire polygon should be rendered. We should also be able to remove the polygon. Polygon should persit between page refresh

[x] Create option on the frontend to create another polygon called "Nav Corridor". There can be one or more nav corridors. 

[x] Implement backend routes to create drones in the frontend (via web socket link). payload should be list of dones with spawn location in lat and lon. example ["spawn_log": [<lat>, <lon>], "drone_id": <optional unique id str>}, ...]. It should throw error if 
    - Drone exists i the same location
    - Drone id exits already
    
    The api should return the drone id. The drone id shouild be createed if not provided. Otehrise use the provided one and return the same. Implement appropriate pydantic schemas.

[x] Implement the route called follow_waypoints which takes a list of lat lon and in the fronend end the drone to immnediately follow the waypoints. Example payload {<drone_id1>: [[lat, lon], [lat1, lon1], ....], <drone_id2>: ...}. Implemet appropriate pydanti schemas. Also write an exampe script in example dir called "waypoint_following.py" where youy first spawn two drones and set twoi different lsists of waypoints to them.

[x] When a set of waypoints are set for a drone, it sould be renredered on the frontend in the same color as the drone capture box and connected via dotted line - starting from the drone.

[x] In frontend, implement a reset simulator button which will clear all the dorn and waypoints data - incluing ids, polygons everything. Implement the corresponiging api for backend. Finally use that clear api in the exampple scripts before spawning new dones. 

[x] Create a rest api end point in the backend to setup the Surveillance area polygon. Payload {"surveillance_polygon": [[lat, lon], ...]}. Write example script in the examples dir to create a surveillance area polygon. Then spawn a drone and follwo a set of random waypoints. Wriote enough comments to understand the script.

[x] Create rest api end point to create the nav corridors. The payload is a lost of polygons ["corridor_0": [[lat, lon], ...], "corridor_2": [[lat, lon], ...]]. Implement proper pydantic schema and implement example script. It should set a surveillance polygon, set two nav corridors to reach and exit the surveillance area and spawn one drop and follow a random waypoints list

[ ] Make drone spawning a REST api endpoint in the backend for the client. Accordingly, Update the examples scripts

[x] Implement set waypoints as REST API endpoint (`POST /set-waypoints`). Implement sim state WebSocket (`/ws/sim-state`) streaming drone locations, waypoints (completed/pending), velocities, surveillance area, and nav corridors. Updated example scripts to use REST for waypoints and sim-state WS for monitoring. 