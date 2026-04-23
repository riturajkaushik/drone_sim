from surveillance_polygon import SurveillancePolygon


def main():
    # 5-point polygon around Lauttasaari, Helsinki
    polygon = SurveillancePolygon(
        [
            {"lat": 60.1600, "lon": 24.8700},
            {"lat": 60.1650, "lon": 24.8900},
            {"lat": 60.1620, "lon": 24.9100},
            {"lat": 60.1550, "lon": 24.9000},
            {"lat": 60.1560, "lon": 24.8750},
        ],
        entry_point={"lat": (60.1600 + 60.1650) / 2, "lon": (24.8700 + 24.8900) / 2},
        exit_point={"lat": (60.1620 + 60.1550) / 2, "lon": (24.9100 + 24.9000) / 2},
    )
    polygon.partition(length_x=100, length_y=100, overlap_percentage=20)
    polygon.plan_route()
    polygon.render()


if __name__ == "__main__":
    main()
