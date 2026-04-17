from shapely.geometry import Polygon
from pyproj import Transformer
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.collections import PatchCollection


class SpacePolygon:
    """A polygon defined by ordered GPS coordinates (lat/lon)."""

    def __init__(self, coordinates: list[dict]):
        """
        Args:
            coordinates: Ordered list of {"lat": float, "lon": float} dicts
                         defining the polygon vertices in traversal order.

        Raises:
            ValueError: If fewer than 3 coordinates or missing keys.
        """
        if len(coordinates) < 3:
            raise ValueError("A polygon requires at least 3 coordinates.")

        for i, coord in enumerate(coordinates):
            if "lat" not in coord or "lon" not in coord:
                raise ValueError(
                    f"Coordinate at index {i} missing 'lat' or 'lon' key."
                )

        self.coordinates = coordinates
        # Shapely uses (x, y) = (lon, lat) per GIS convention
        ring = [(c["lon"], c["lat"]) for c in coordinates]
        self._polygon = Polygon(ring)

    def render(self) -> None:
        """Plot the polygon on a matplotlib figure with labeled axes."""
        fig, ax = plt.subplots(1, 1, figsize=(8, 6))

        lons = [c["lon"] for c in self.coordinates] + [self.coordinates[0]["lon"]]
        lats = [c["lat"] for c in self.coordinates] + [self.coordinates[0]["lat"]]

        ax.fill(lons, lats, alpha=0.3, color="steelblue", label="Polygon")
        ax.plot(lons, lats, color="steelblue", linewidth=1.5)
        ax.scatter(
            [c["lon"] for c in self.coordinates],
            [c["lat"] for c in self.coordinates],
            color="darkblue",
            zorder=5,
            s=30,
            label="Vertices",
        )

        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.set_title("SpacePolygon")
        ax.legend()
        ax.set_aspect("equal")
        plt.tight_layout()
        plt.show()

    def area(self) -> float:
        """Calculate the polygon area in square meters using UTM projection.

        Returns:
            Area in square meters.
        """
        centroid = self._polygon.centroid
        centroid_lon, centroid_lat = centroid.x, centroid.y

        # Determine UTM zone from centroid longitude
        utm_zone = int((centroid_lon + 180) / 6) + 1
        hemisphere = "north" if centroid_lat >= 0 else "south"
        utm_crs = f"+proj=utm +zone={utm_zone} +{hemisphere} +datum=WGS84"

        transformer = Transformer.from_crs("EPSG:4326", utm_crs, always_xy=True)
        projected_coords = [
            transformer.transform(c["lon"], c["lat"]) for c in self.coordinates
        ]

        projected_polygon = Polygon(projected_coords)
        return projected_polygon.area

    def bounding_box(self) -> dict:
        """Compute the axis-aligned bounding box of the polygon.

        Returns:
            Dict with keys: min_lat, max_lat, min_lon, max_lon.
        """
        lats = [c["lat"] for c in self.coordinates]
        lons = [c["lon"] for c in self.coordinates]
        return {
            "min_lat": min(lats),
            "max_lat": max(lats),
            "min_lon": min(lons),
            "max_lon": max(lons),
        }
