from shapely.geometry import Polygon, Point

from polygon import MissionPolygons


def _find_shared_point(surv_coords, nav_points, nav_exit):
    """Find the point on the surveillance border within the nav polygon
    nearest to the nav corridor exit.

    This ensures the nav corridor exit connects directly to the surveillance
    entry at a point that lies on the surveillance boundary and inside the
    nav polygon.
    """
    surv_ring = [(c["lon"], c["lat"]) for c in surv_coords]
    nav_ring = [(p["lon"], p["lat"]) for p in nav_points]

    surv_poly = Polygon(surv_ring)
    nav_poly = Polygon(nav_ring)
    exit_pt = Point(nav_exit["lon"], nav_exit["lat"])

    intersection = surv_poly.boundary.intersection(nav_poly)
    if intersection.is_empty:
        raise ValueError(
            "Surveillance boundary and nav polygon do not overlap — "
            "cannot compute a shared entry/exit point."
        )

    nearest = intersection.interpolate(intersection.project(exit_pt))
    return {"lat": round(nearest.y, 6), "lon": round(nearest.x, 6)}


def main():
    # Surveillance polygon around Lauttasaari, Helsinki
    surv_coords = [
        {"lat": 60.1600, "lon": 24.8700},
        {"lat": 60.1650, "lon": 24.8900},
        {"lat": 60.1620, "lon": 24.9100},
        {"lat": 60.1550, "lon": 24.9000},
        {"lat": 60.1560, "lon": 24.8750},
    ]

    # Add a U-shaped navigation corridor. Entry and exit are at the top of each
    # arm — a straight line between them cuts outside the polygon, so the path
    # planner must route all the way down one arm, around the bottom, and back
    # up the other arm.
    nav_points = [
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
    ]
    nav_entry = {"lat": 60.1640, "lon": 24.8565}
    nav_exit_approx = {"lat": 60.1635, "lon": 24.8738}

    # Compute the shared point: on the surveillance border and within the nav polygon
    shared_point = _find_shared_point(surv_coords, nav_points, nav_exit_approx)

    mission = MissionPolygons(
        coordinates=surv_coords,
        entry_point=shared_point,
        exit_point={"lat": (60.1620 + 60.1550) / 2, "lon": (24.9100 + 24.9000) / 2},
    )

    # Partition and plan the surveillance route
    mission.partition_surveillance(length_x=100, length_y=100, overlap_percentage=20)
    mission.plan_surveillance_route()

    mission.add_nav_polygon(
        polygon_id="approach",
        points=nav_points,
        entry_point=nav_entry,
        exit_point=shared_point,
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
