[x] Read the space partition code and how to create the polygon int he algo directory. We need to implement the create of a polygon maually from the frontend. We will add the points (lat lon) and press create. When we add a point, it shoud be rendered. When we press create, entire polygon should be rendered. We should also be able to remove the polygon. Polygon should persit between page refresh

[x] Create option on the frontend to create another polygon called "Nav Corridor". There can be one or more nav corridors. 

[x] Implement backend routes to create drones in the frontend (via web socket link). payload should be list of dones with spawn location in lat and lon. example ["spawn_log": [<lat>, <lon>], "drone_id": <optional unique id str>}, ...]. It should throw error if 
    - Drone exists i the same location
    - Drone id exits already
    
    The api should return the drone id. The drone id shouild be createed if not provided. Otehrise use the provided one and return the same. Implement appropriate pydantic schemas.

[ ] Implement the route called follow_waypoints which takes a list of lat lon and in the fronend end the drone to immnediately follow the waypoints. Example payload {<drone_id1>: [[lat, lon], [lat1, lon1], ....], <drone_id2>: ...}. Implemet appropriate pydanti schemas. Also write an exampe script in example dir called "waypoint_following.py" where youy first spawn two drones and set twoi different lsists of waypoints to them.