import copy
import math

from shapely.geometry import Polygon, box, LineString, Point, MultiPoint
from pyproj import Transformer
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.collections import PatchCollection


class SurveillancePolygon:
    """A polygon defined by ordered GPS coordinates (lat/lon)."""

    def __init__(
        self,
        coordinates: list[dict],
        entry_point: dict,
        exit_point: dict,
    ):
        """
        Args:
            coordinates: Ordered list of {"lat": float, "lon": float} dicts
                         defining the polygon vertices in traversal order.
            entry_point: {"lat": float, "lon": float} where the drone enters.
            exit_point:  {"lat": float, "lon": float} where the drone exits.

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

        for name, pt in [("entry_point", entry_point), ("exit_point", exit_point)]:
            if "lat" not in pt or "lon" not in pt:
                raise ValueError(f"{name} missing 'lat' or 'lon' key.")

        self.coordinates = coordinates
        self.entry_point = entry_point
        self.exit_point = exit_point
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

        # Render bounding box
        bb = self.bounding_box()
        bb_lons = [bb["min_lon"], bb["max_lon"], bb["max_lon"], bb["min_lon"], bb["min_lon"]]
        bb_lats = [bb["min_lat"], bb["min_lat"], bb["max_lat"], bb["max_lat"], bb["min_lat"]]
        ax.plot(bb_lons, bb_lats, color="tomato", linewidth=1.5, linestyle="--", label="Bounding Box")

        # Render partitions if available
        if hasattr(self, "partitions") and self.partitions:
            rect_patches = []
            for part in self.partitions:
                corners = part["corners"]
                lons_r = [c["lon"] for c in corners]
                lats_r = [c["lat"] for c in corners]
                rect = mpatches.Polygon(
                    list(zip(lons_r, lats_r)),
                    closed=True,
                )
                rect_patches.append(rect)
            pc = PatchCollection(
                rect_patches,
                edgecolor="green",
                facecolor="green",
                alpha=0.15,
                linewidth=0.8,
                label="Partitions",
            )
            ax.add_collection(pc)
            # PatchCollection doesn't support label in legend, add a proxy
            ax.plot([], [], color="green", linewidth=1.5, label="Partitions")

        # Render rectangle centers
        if hasattr(self, "_centers") and self._centers:
            ax.scatter(
                [c["lon"] for c in self._centers],
                [c["lat"] for c in self._centers],
                color="red",
                marker="x",
                s=20,
                zorder=6,
                linewidths=0.8,
                label="Centers",
            )

        # Render entry and exit points
        ax.scatter(
            [self.entry_point["lon"]],
            [self.entry_point["lat"]],
            color="blue",
            marker="o",
            s=70,
            zorder=7,
            label="Entry",
        )
        ax.scatter(
            [self.exit_point["lon"]],
            [self.exit_point["lat"]],
            facecolors="none",
            edgecolors="blue",
            marker="o",
            s=70,
            zorder=7,
            linewidths=1.5,
            label="Exit",
        )

        # Render planned route
        if hasattr(self, "_route") and self._route:
            ax.plot(
                [p["lon"] for p in self._route],
                [p["lat"] for p in self._route],
                color="darkorange",
                linewidth=0.8,
                zorder=5,
                label="Route",
            )

        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.set_title("SpacePolygon")
        ax.legend()
        ax.set_aspect("equal")
        plt.tight_layout()
        plt.show()

    def partition(
        self,
        length_x: float,
        length_y: float,
        overlap_percentage: float = 20.0,
    ) -> None:
        """Partition the bounding box into overlapping rectangles.

        The rectangles are sized length_x × length_y (in meters) and placed so
        that every part of the bounding box is covered.  When an integer number
        of rectangles doesn't fit exactly, the last column/row overflows beyond
        the bounding box boundary.

        Args:
            length_x: Rectangle width in meters (longitude direction).
            length_y: Rectangle height in meters (latitude direction).
            overlap_percentage: Percentage overlap between adjacent rectangles
                                in each dimension (0–100). Default 20%.
        """
        bb = self.bounding_box()

        # Convert meter dimensions to degree offsets
        METERS_PER_DEG_LAT = 111_320.0
        center_lat = (bb["min_lat"] + bb["max_lat"]) / 2.0
        meters_per_deg_lon = METERS_PER_DEG_LAT * math.cos(math.radians(center_lat))

        delta_lat = length_y / METERS_PER_DEG_LAT
        delta_lon = length_x / meters_per_deg_lon

        overlap_frac = overlap_percentage / 100.0
        stride_lat = delta_lat * (1.0 - overlap_frac)
        stride_lon = delta_lon * (1.0 - overlap_frac)

        partitions: list[dict] = []
        lat = bb["min_lat"]
        while lat < bb["max_lat"]:
            lon = bb["min_lon"]
            while lon < bb["max_lon"]:
                corners = [
                    {"lat": lat, "lon": lon},
                    {"lat": lat, "lon": lon + delta_lon},
                    {"lat": lat + delta_lat, "lon": lon + delta_lon},
                    {"lat": lat + delta_lat, "lon": lon},
                ]
                partitions.append({"corners": corners})
                lon += stride_lon
            lat += stride_lat

        self.partitions = self._adjust_partitions(partitions, delta_lat, delta_lon)

        self._centers = [
            {
                "lat": sum(c["lat"] for c in p["corners"]) / 4.0,
                "lon": sum(c["lon"] for c in p["corners"]) / 4.0,
            }
            for p in self.partitions
        ]

    def get_centers(self) -> list[dict]:
        """Return a deep copy of the rectangle centers.

        Each center is a {"lat": float, "lon": float} dict.
        The returned list is independent of the internal state.
        """
        if not hasattr(self, "_centers"):
            return []
        return copy.deepcopy(self._centers)

    # ------------------------------------------------------------------
    # Route planning (TSP)
    # ------------------------------------------------------------------

    def plan_route(self) -> list[dict]:
        """Find a short route visiting all rectangle centers.

        Uses nearest-neighbor heuristic followed by 2-opt local search.
        The route starts at ``entry_point`` and ends at ``exit_point``.

        Returns:
            Ordered list of {"lat": float, "lon": float} from entry to exit.

        Raises:
            RuntimeError: If ``partition()`` has not been called yet.
        """
        if not hasattr(self, "_centers") or not self._centers:
            raise RuntimeError("Call partition() before plan_route().")

        nodes = (
            [self.entry_point]
            + list(copy.deepcopy(self._centers))
            + [self.exit_point]
        )
        n = len(nodes)

        # Pre-compute distance matrix
        dist = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                d = self._coord_dist(nodes[i], nodes[j])
                dist[i][j] = d
                dist[j][i] = d

        # Nearest-neighbor starting from node 0 (entry), ending at node n-1 (exit)
        route = self._nearest_neighbor(n, dist)

        # 2-opt improvement (keep first and last fixed)
        route = self._two_opt(route, dist)

        self._route = [nodes[i] for i in route]
        return copy.deepcopy(self._route)

    def get_route(self) -> list[dict]:
        """Return a deep copy of the planned route.

        Each element is a {"lat": float, "lon": float} dict.
        """
        if not hasattr(self, "_route"):
            return []
        return copy.deepcopy(self._route)

    @staticmethod
    def _coord_dist(a: dict, b: dict) -> float:
        """Euclidean distance between two lat/lon dicts (good enough for small areas)."""
        dlat = a["lat"] - b["lat"]
        dlon = a["lon"] - b["lon"]
        return math.sqrt(dlat * dlat + dlon * dlon)

    @staticmethod
    def _nearest_neighbor(n: int, dist: list[list[float]]) -> list[int]:
        """Nearest-neighbor heuristic with fixed start (0) and end (n-1)."""
        visited = [False] * n
        route = [0]
        visited[0] = True
        visited[n - 1] = True  # reserve exit for last

        for _ in range(n - 2):
            last = route[-1]
            best_j = -1
            best_d = float("inf")
            for j in range(n):
                if not visited[j] and dist[last][j] < best_d:
                    best_d = dist[last][j]
                    best_j = j
            route.append(best_j)
            visited[best_j] = True

        route.append(n - 1)
        return route

    @staticmethod
    def _two_opt(route: list[int], dist: list[list[float]]) -> list[int]:
        """2-opt local search. Keeps route[0] and route[-1] fixed."""
        n = len(route)
        improved = True
        while improved:
            improved = False
            for i in range(1, n - 2):
                for j in range(i + 1, n - 1):
                    # Cost of current edges: (i-1,i) + (j,j+1)
                    # Cost after reversal:   (i-1,j) + (i,j+1)
                    d_old = dist[route[i - 1]][route[i]] + dist[route[j]][route[j + 1]]
                    d_new = dist[route[i - 1]][route[j]] + dist[route[i]][route[j + 1]]
                    if d_new < d_old - 1e-12:
                        route[i : j + 1] = route[i : j + 1][::-1]
                        improved = True
        return route

    # ------------------------------------------------------------------
    # Partition adjustment helpers
    # ------------------------------------------------------------------

    def _adjust_partitions(
        self, partitions: list[dict], delta_lat: float, delta_lon: float
    ) -> list[dict]:
        """Filter and adjust partitions so every rectangle's center is reachable.

        1. Remove rectangles that don't intersect the polygon.
        2. For rectangles whose center is outside the polygon, shift along the
           axis of least movement to place the center on the polygon boundary.
        """
        boundary = self._polygon.boundary
        adjusted: list[dict] = []

        for part in partitions:
            rect_poly = self._corners_to_polygon(part["corners"])

            if not rect_poly.intersects(self._polygon):
                continue

            center = rect_poly.centroid
            if self._polygon.contains(center):
                adjusted.append(part)
                continue

            shifted = self._shift_to_boundary(part["corners"], center, boundary)
            if shifted is not None:
                adjusted.append({"corners": shifted})

        return adjusted

    @staticmethod
    def _corners_to_polygon(corners: list[dict]) -> Polygon:
        ring = [(c["lon"], c["lat"]) for c in corners]
        return Polygon(ring)

    def _shift_to_boundary(
        self,
        corners: list[dict],
        center: Point,
        boundary: LineString,
    ) -> list[dict] | None:
        """Shift a rectangle along the axis of least movement to place its
        center on the polygon boundary. Returns new corners or None."""
        cx, cy = center.x, center.y  # lon, lat

        best_offset_lon = None
        best_offset_lat = None

        # Horizontal line (constant lat) — find boundary intersections
        h_line = LineString([(cx - 1, cy), (cx + 1, cy)])
        h_inter = boundary.intersection(h_line)
        if not h_inter.is_empty:
            pts = self._extract_points(h_inter)
            if pts:
                nearest = min(pts, key=lambda p: abs(p.x - cx))
                best_offset_lon = nearest.x - cx

        # Vertical line (constant lon) — find boundary intersections
        v_line = LineString([(cx, cy - 1), (cx, cy + 1)])
        v_inter = boundary.intersection(v_line)
        if not v_inter.is_empty:
            pts = self._extract_points(v_inter)
            if pts:
                nearest = min(pts, key=lambda p: abs(p.y - cy))
                best_offset_lat = nearest.y - cy

        if best_offset_lon is None and best_offset_lat is None:
            return None

        # Pick axis with least movement
        if best_offset_lat is None:
            d_lon, d_lat = best_offset_lon, 0.0
        elif best_offset_lon is None:
            d_lon, d_lat = 0.0, best_offset_lat
        elif abs(best_offset_lon) <= abs(best_offset_lat):
            d_lon, d_lat = best_offset_lon, 0.0
        else:
            d_lon, d_lat = 0.0, best_offset_lat

        return [
            {"lat": c["lat"] + d_lat, "lon": c["lon"] + d_lon} for c in corners
        ]

    @staticmethod
    def _extract_points(geom) -> list[Point]:
        """Extract Point objects from a geometry (Point, MultiPoint, etc.)."""
        if geom.is_empty:
            return []
        if geom.geom_type == "Point":
            return [geom]
        if geom.geom_type == "MultiPoint":
            return list(geom.geoms)
        # GeometryCollection — extract only points
        points = []
        for g in getattr(geom, "geoms", []):
            if g.geom_type == "Point":
                points.append(g)
        return points

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_utm_transformers(self):
        """Return (to_utm, to_wgs, utm_crs) transformers for this polygon."""
        centroid = self._polygon.centroid
        centroid_lon, centroid_lat = centroid.x, centroid.y
        utm_zone = int((centroid_lon + 180) / 6) + 1
        hemisphere = "north" if centroid_lat >= 0 else "south"
        utm_crs = f"+proj=utm +zone={utm_zone} +{hemisphere} +datum=WGS84"

        to_utm = Transformer.from_crs("EPSG:4326", utm_crs, always_xy=True)
        to_wgs = Transformer.from_crs(utm_crs, "EPSG:4326", always_xy=True)
        return to_utm, to_wgs, utm_crs

    def area(self) -> float:
        """Calculate the polygon area in square meters using UTM projection.

        Returns:
            Area in square meters.
        """
        transformer, _, _ = self._get_utm_transformers()
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
