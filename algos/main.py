from polygon import MissionPolygons


def main():
    # Surveillance polygon around Lauttasaari, Helsinki
    mission = MissionPolygons(
        coordinates=[
            {"lat": 60.1600, "lon": 24.8700},
            {"lat": 60.1650, "lon": 24.8900},
            {"lat": 60.1620, "lon": 24.9100},
            {"lat": 60.1550, "lon": 24.9000},
            {"lat": 60.1560, "lon": 24.8750},
        ],
        entry_point={"lat": (60.1600 + 60.1650) / 2, "lon": (24.8700 + 24.8900) / 2},
        exit_point={"lat": (60.1620 + 60.1550) / 2, "lon": (24.9100 + 24.9000) / 2},
    )

    # Partition and plan the surveillance route
    mission.partition_surveillance(length_x=100, length_y=100, overlap_percentage=20)
    mission.plan_surveillance_route()

    # Add a U-shaped navigation corridor. Entry and exit are at the top of each
    # arm — a straight line between them cuts outside the polygon, so the path
    # planner must route all the way down one arm, around the bottom, and back
    # up the other arm.
    mission.add_nav_polygon(
        polygon_id="approach",
        points=[
            # Right arm outer edge (top → bottom)
            {"lat": 60.1640, "lon": 24.8750},
            {"lat": 60.1620, "lon": 24.8760},
            {"lat": 60.1600, "lon": 24.8755},
            {"lat": 60.1580, "lon": 24.8740},
            # Bottom curve (right → left)
            {"lat": 60.1565, "lon": 24.8710},
            {"lat": 60.1558, "lon": 24.8660},
            {"lat": 60.1560, "lon": 24.8610},
            {"lat": 60.1570, "lon": 24.8570},
            # Left arm outer edge (bottom → top)
            {"lat": 60.1585, "lon": 24.8540},
            {"lat": 60.1605, "lon": 24.8530},
            {"lat": 60.1625, "lon": 24.8535},
            {"lat": 60.1645, "lon": 24.8550},
            # Left arm inner edge (top → bottom)
            {"lat": 60.1635, "lon": 24.8580},
            {"lat": 60.1620, "lon": 24.8575},
            {"lat": 60.1605, "lon": 24.8580},
            {"lat": 60.1592, "lon": 24.8595},
            # Inner bottom curve (left → right)
            {"lat": 60.1582, "lon": 24.8620},
            {"lat": 60.1578, "lon": 24.8660},
            {"lat": 60.1582, "lon": 24.8700},
            # Right arm inner edge (bottom → top)
            {"lat": 60.1595, "lon": 24.8720},
            {"lat": 60.1610, "lon": 24.8730},
            {"lat": 60.1630, "lon": 24.8725},
        ],
        entry_point={"lat": 60.1640, "lon": 24.8565},
        exit_point={"lat": 60.1635, "lon": 24.8738},
    )
    # Nav path planning settings
    NUM_SAMPLES = 100        # random sample points for path planning
    BORDER_DISTANCE = 50.0   # min distance from polygon edges in meters
    MIN_PATH_POINTS = 10     # minimum waypoints in the path for smoothness

    mission.plan_nav_path(
        "approach",
        num_samples=NUM_SAMPLES,
        border_distance=BORDER_DISTANCE,
        min_path_points=MIN_PATH_POINTS,
    )

    mission.render()


if __name__ == "__main__":
    main()
