from space_partition import SpacePolygon


def main():
    # 5-point polygon around Lauttasaari, Helsinki
    polygon = SpacePolygon([
        {"lat": 60.1600, "lon": 24.8700},
        {"lat": 60.1650, "lon": 24.8900},
        {"lat": 60.1620, "lon": 24.9100},
        {"lat": 60.1550, "lon": 24.9000},
        {"lat": 60.1560, "lon": 24.8750},
    ])
    polygon.render()


if __name__ == "__main__":
    main()
