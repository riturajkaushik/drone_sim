import copy
import heapq
import math

from shapely.geometry import Polygon, LineString, Point
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.collections import PatchCollection
from pyproj import Transformer


class MissionPolygons:
    """Manages a surveillance polygon and N navigation polygons for drone missions.

    The surveillance polygon defines the area to be surveyed (supports partitioning
    and route planning). Navigation polygons define safe corridors for reaching
    the surveillance area; each has an entry/exit point and supports path planning
    that keeps the route within polygon bounds.
    """

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def __init__(
        self,
        coordinates: list[dict],
        entry_point: dict,
        exit_point: dict,
    ):
        """
        Args:
            coordinates: Ordered list of {"lat": float, "lon": float} dicts
                         defining the surveillance polygon vertices.
            entry_point: {"lat": float, "lon": float} where the drone enters
                         the surveillance area.
            exit_point:  {"lat": float, "lon": float} where the drone exits
                         the surveillance area.
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

        self.surveillance_polygon = {
            "coordinates": coordinates,
            "entry_point": entry_point,
            "exit_point": exit_point,
        }

        ring = [(c["lon"], c["lat"]) for c in coordinates]
        self._surveillance_shapely = Polygon(ring)

        self._nav_polygons: dict[str, dict] = {}

    # ------------------------------------------------------------------
    # Navigation polygon management
    # ------------------------------------------------------------------

    def add_nav_polygon(
        self,
        polygon_id: str,
        points: list[dict],
        entry_point: dict,
        exit_point: dict,
    ) -> None:
        """Add a navigation polygon.

        Args:
            polygon_id: Unique identifier for this nav polygon.
            points: Ordered list of {"lat": float, "lon": float} defining the
                    polygon boundary.
            entry_point: {"lat": float, "lon": float} entry into this corridor.
            exit_point:  {"lat": float, "lon": float} exit from this corridor.
        """
        if len(points) < 3:
            raise ValueError("A polygon requires at least 3 coordinates.")

        for i, coord in enumerate(points):
            if "lat" not in coord or "lon" not in coord:
                raise ValueError(
                    f"Coordinate at index {i} missing 'lat' or 'lon' key."
                )

        for name, pt in [("entry_point", entry_point), ("exit_point", exit_point)]:
            if "lat" not in pt or "lon" not in pt:
                raise ValueError(f"{name} missing 'lat' or 'lon' key.")

        ring = [(c["lon"], c["lat"]) for c in points]
        shapely_poly = Polygon(ring)

        self._nav_polygons[polygon_id] = {
            "points": points,
            "entry_point": entry_point,
            "exit_point": exit_point,
            "shapely": shapely_poly,
            "path": None,
        }

    def get_nav_polygon_ids(self) -> list[str]:
        """Return the IDs of all registered nav polygons."""
        return list(self._nav_polygons.keys())

    # ------------------------------------------------------------------
    # Nav path planning (sampled points + visibility graph + Dijkstra)
    # ------------------------------------------------------------------

    def plan_nav_path(
        self,
        polygon_id: str,
        num_samples: int = 300,
        border_distance: float = 5.0,
        min_path_points: int = 0,
    ) -> list[dict]:
        """Plan a smooth path from entry to exit within a nav polygon.

        Samples many random interior points (rejecting those too close to the
        border), then builds a visibility graph over entry + samples + exit and
        finds the shortest path with Dijkstra.

        Args:
            polygon_id: ID of the nav polygon to plan within.
            num_samples: Number of random sample points to generate inside the
                         polygon for path planning. More samples → smoother
                         paths but slower computation.
            border_distance: Minimum distance in meters that sampled points
                             must be from the polygon boundary. Controls how
                             far the path stays from edges. Automatically
                             reduced if the polygon is too narrow.
            min_path_points: Minimum number of points in the final path
                             (including entry and exit). If the shortest path
                             has fewer points, intermediate points are
                             interpolated along the path segments to reach this
                             count. Use higher values for smoother paths.
                             0 means no minimum (use path as-is).

        Returns:
            Ordered list of {"lat": float, "lon": float} waypoints from entry
            to exit.
        """
        if polygon_id not in self._nav_polygons:
            raise KeyError(f"Nav polygon '{polygon_id}' not found.")

        nav = self._nav_polygons[polygon_id]
        poly = nav["shapely"]
        entry = nav["entry_point"]
        exit_pt = nav["exit_point"]

        # Convert border_distance from meters to degrees
        METERS_PER_DEG_LAT = 111_320.0
        centroid = poly.centroid
        meters_per_deg_lon = METERS_PER_DEG_LAT * math.cos(
            math.radians(centroid.y)
        )
        # Use average of lat/lon degree sizes as the buffer distance
        border_deg = border_distance / ((METERS_PER_DEG_LAT + meters_per_deg_lon) / 2.0)

        # Progressively shrink margin until we get a usable inner polygon
        margin = border_deg
        inner_poly = None
        while margin > border_deg * 0.1:
            candidate = poly.buffer(-margin)
            if not candidate.is_empty and candidate.area > 0:
                inner_poly = candidate
                break
            margin *= 0.5
        if inner_poly is None:
            inner_poly = poly

        # Sample random interior points inside the inner polygon
        import random
        rng = random.Random(42)
        minx, miny, maxx, maxy = poly.bounds
        samples: list[dict] = []
        attempts = 0
        max_attempts = num_samples * 30
        while len(samples) < num_samples and attempts < max_attempts:
            attempts += 1
            lon = rng.uniform(minx, maxx)
            lat = rng.uniform(miny, maxy)
            pt = Point(lon, lat)
            if inner_poly.contains(pt):
                samples.append({"lat": lat, "lon": lon})

        # Build node list: entry + samples + exit
        nodes = [entry] + samples + [exit_pt]
        n = len(nodes)

        # Build visibility graph.
        # Between sample points: use inner_poly so that connecting segments
        # also respect the border distance (not just the endpoints).
        # For edges involving entry (0) or exit (n-1): use the original poly
        # since they may be near the border.
        adj: list[list[tuple[int, float]]] = [[] for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                is_endpoint_edge = (i == 0 or j == n - 1)
                vis_poly = poly if is_endpoint_edge else inner_poly
                if self._is_visible(nodes[i], nodes[j], vis_poly):
                    d = self._coord_dist(nodes[i], nodes[j])
                    adj[i].append((j, d))
                    adj[j].append((i, d))

        # Dijkstra from node 0 (entry) to node n-1 (exit)
        path_indices = self._dijkstra(adj, 0, n - 1)

        if path_indices is None:
            raise RuntimeError(
                f"No valid path found within nav polygon '{polygon_id}'."
            )

        path = [copy.deepcopy(nodes[i]) for i in path_indices]

        # Enforce minimum path points by interpolating along segments
        if min_path_points > 0 and len(path) < min_path_points:
            path = self._interpolate_path(path, min_path_points)

        nav["path"] = path
        return copy.deepcopy(path)

    @staticmethod
    def _interpolate_path(
        path: list[dict], min_points: int
    ) -> list[dict]:
        """Add evenly-spaced intermediate points along a path.

        Points are distributed proportionally to segment length so that the
        overall spacing is uniform. The first and last segments (touching
        entry/exit) are not subdivided to avoid placing points near the
        polygon border.
        """
        if len(path) < 2 or min_points <= len(path):
            return path

        # Segments eligible for subdivision (skip first and last)
        seg_lengths = []
        for i in range(len(path) - 1):
            dlat = path[i + 1]["lat"] - path[i]["lat"]
            dlon = path[i + 1]["lon"] - path[i]["lon"]
            seg_lengths.append(math.sqrt(dlat * dlat + dlon * dlon))

        # Only subdivide interior segments (indices 1..n-2)
        interior_start = 1 if len(path) > 2 else 0
        interior_end = len(seg_lengths) - 1 if len(path) > 2 else len(seg_lengths)
        interior_total = sum(seg_lengths[interior_start:interior_end])

        if interior_total < 1e-15 or interior_start >= interior_end:
            return path

        points_to_add = min_points - len(path)

        new_path: list[dict] = [path[0]]
        for seg_idx in range(len(seg_lengths)):
            if interior_start <= seg_idx < interior_end and points_to_add > 0:
                seg_share = seg_lengths[seg_idx] / interior_total
                seg_new = max(0, round(seg_share * points_to_add))

                for k in range(1, seg_new + 1):
                    t = k / (seg_new + 1)
                    new_path.append({
                        "lat": path[seg_idx]["lat"] + t * (path[seg_idx + 1]["lat"] - path[seg_idx]["lat"]),
                        "lon": path[seg_idx]["lon"] + t * (path[seg_idx + 1]["lon"] - path[seg_idx]["lon"]),
                    })
            new_path.append(path[seg_idx + 1])

        return new_path

    @staticmethod
    def _is_visible(a: dict, b: dict, polygon: Polygon) -> bool:
        """Check if the line segment from a to b lies within the polygon."""
        line = LineString([(a["lon"], a["lat"]), (b["lon"], b["lat"])])
        # Use a tiny negative buffer to handle floating-point edge cases
        return polygon.buffer(1e-10).contains(line)

    @staticmethod
    def _dijkstra(
        adj: list[list[tuple[int, float]]], start: int, end: int
    ) -> list[int] | None:
        """Shortest path via Dijkstra. Returns list of node indices or None."""
        n = len(adj)
        dist = [float("inf")] * n
        prev = [-1] * n
        dist[start] = 0.0
        heap = [(0.0, start)]

        while heap:
            d, u = heapq.heappop(heap)
            if d > dist[u]:
                continue
            if u == end:
                break
            for v, w in adj[u]:
                nd = d + w
                if nd < dist[v]:
                    dist[v] = nd
                    prev[v] = u
                    heapq.heappush(heap, (nd, v))

        if dist[end] == float("inf"):
            return None

        path = []
        cur = end
        while cur != -1:
            path.append(cur)
            cur = prev[cur]
        path.reverse()
        return path

    # ------------------------------------------------------------------
    # Surveillance polygon: partitioning
    # ------------------------------------------------------------------

    def partition_surveillance(
        self,
        length_x: float,
        length_y: float,
        overlap_percentage: float = 20.0,
    ) -> None:
        """Partition the surveillance polygon bounding box into overlapping rectangles.

        Args:
            length_x: Rectangle width in meters (longitude direction).
            length_y: Rectangle height in meters (latitude direction).
            overlap_percentage: Overlap between adjacent rectangles (0–100).
        """
        bb = self.surveillance_bounding_box()

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

        self._surveillance_partitions = self._adjust_partitions(
            partitions, delta_lat, delta_lon
        )

        self._surveillance_centers = [
            {
                "lat": sum(c["lat"] for c in p["corners"]) / 4.0,
                "lon": sum(c["lon"] for c in p["corners"]) / 4.0,
            }
            for p in self._surveillance_partitions
        ]

    def get_surveillance_centers(self) -> list[dict]:
        """Return a deep copy of the surveillance rectangle centers."""
        if not hasattr(self, "_surveillance_centers"):
            return []
        return copy.deepcopy(self._surveillance_centers)

    # ------------------------------------------------------------------
    # Surveillance polygon: route planning (TSP)
    # ------------------------------------------------------------------

    def plan_surveillance_route(self) -> list[dict]:
        """Plan a route visiting all surveillance partition centers.

        Uses nearest-neighbor heuristic followed by 2-opt local search.
        The route starts at entry_point and ends at exit_point.

        Returns:
            Ordered list of {"lat": float, "lon": float} from entry to exit.
        """
        if not hasattr(self, "_surveillance_centers") or not self._surveillance_centers:
            raise RuntimeError(
                "Call partition_surveillance() before plan_surveillance_route()."
            )

        entry = self.surveillance_polygon["entry_point"]
        exit_pt = self.surveillance_polygon["exit_point"]

        nodes = [entry] + list(copy.deepcopy(self._surveillance_centers)) + [exit_pt]
        n = len(nodes)

        dist = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                d = self._coord_dist(nodes[i], nodes[j])
                dist[i][j] = d
                dist[j][i] = d

        route = self._nearest_neighbor(n, dist)
        route = self._two_opt(route, dist)

        self._surveillance_route = [nodes[i] for i in route]
        return copy.deepcopy(self._surveillance_route)

    def get_surveillance_route(self) -> list[dict]:
        """Return a deep copy of the planned surveillance route."""
        if not hasattr(self, "_surveillance_route"):
            return []
        return copy.deepcopy(self._surveillance_route)

    # ------------------------------------------------------------------
    # Surveillance helpers (TSP)
    # ------------------------------------------------------------------

    @staticmethod
    def _coord_dist(a: dict, b: dict) -> float:
        """Euclidean distance between two lat/lon dicts."""
        dlat = a["lat"] - b["lat"]
        dlon = a["lon"] - b["lon"]
        return math.sqrt(dlat * dlat + dlon * dlon)

    @staticmethod
    def _nearest_neighbor(n: int, dist: list[list[float]]) -> list[int]:
        """Nearest-neighbor heuristic with fixed start (0) and end (n-1)."""
        visited = [False] * n
        route = [0]
        visited[0] = True
        visited[n - 1] = True

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
                    d_old = (
                        dist[route[i - 1]][route[i]] + dist[route[j]][route[j + 1]]
                    )
                    d_new = (
                        dist[route[i - 1]][route[j]] + dist[route[i]][route[j + 1]]
                    )
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
        """Filter and adjust partitions so every rectangle's center is reachable."""
        boundary = self._surveillance_shapely.boundary
        adjusted: list[dict] = []

        for part in partitions:
            rect_poly = self._corners_to_polygon(part["corners"])

            if not rect_poly.intersects(self._surveillance_shapely):
                continue

            center = rect_poly.centroid
            if self._surveillance_shapely.contains(center):
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
        """Shift a rectangle to place its center on the polygon boundary."""
        cx, cy = center.x, center.y

        best_offset_lon = None
        best_offset_lat = None

        h_line = LineString([(cx - 1, cy), (cx + 1, cy)])
        h_inter = boundary.intersection(h_line)
        if not h_inter.is_empty:
            pts = self._extract_points(h_inter)
            if pts:
                nearest = min(pts, key=lambda p: abs(p.x - cx))
                best_offset_lon = nearest.x - cx

        v_line = LineString([(cx, cy - 1), (cx, cy + 1)])
        v_inter = boundary.intersection(v_line)
        if not v_inter.is_empty:
            pts = self._extract_points(v_inter)
            if pts:
                nearest = min(pts, key=lambda p: abs(p.y - cy))
                best_offset_lat = nearest.y - cy

        if best_offset_lon is None and best_offset_lat is None:
            return None

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
        """Extract Point objects from a geometry."""
        if geom.is_empty:
            return []
        if geom.geom_type == "Point":
            return [geom]
        if geom.geom_type == "MultiPoint":
            return list(geom.geoms)
        points = []
        for g in getattr(geom, "geoms", []):
            if g.geom_type == "Point":
                points.append(g)
        return points

    # ------------------------------------------------------------------
    # General helpers
    # ------------------------------------------------------------------

    def _get_utm_transformers(self):
        """Return (to_utm, to_wgs, utm_crs) transformers for the surveillance polygon."""
        centroid = self._surveillance_shapely.centroid
        centroid_lon, centroid_lat = centroid.x, centroid.y
        utm_zone = int((centroid_lon + 180) / 6) + 1
        hemisphere = "north" if centroid_lat >= 0 else "south"
        utm_crs = f"+proj=utm +zone={utm_zone} +{hemisphere} +datum=WGS84"

        to_utm = Transformer.from_crs("EPSG:4326", utm_crs, always_xy=True)
        to_wgs = Transformer.from_crs(utm_crs, "EPSG:4326", always_xy=True)
        return to_utm, to_wgs, utm_crs

    def surveillance_area(self) -> float:
        """Calculate the surveillance polygon area in square meters."""
        transformer, _, _ = self._get_utm_transformers()
        coords = self.surveillance_polygon["coordinates"]
        projected = [transformer.transform(c["lon"], c["lat"]) for c in coords]
        return Polygon(projected).area

    def surveillance_bounding_box(self) -> dict:
        """Axis-aligned bounding box of the surveillance polygon."""
        coords = self.surveillance_polygon["coordinates"]
        lats = [c["lat"] for c in coords]
        lons = [c["lon"] for c in coords]
        return {
            "min_lat": min(lats),
            "max_lat": max(lats),
            "min_lon": min(lons),
            "max_lon": max(lons),
        }

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self) -> None:
        """Render the surveillance polygon, nav polygons, and all planned paths."""
        fig, ax = plt.subplots(1, 1, figsize=(10, 8))

        self._render_surveillance(ax)
        self._render_nav_polygons(ax)

        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.set_title("MissionPolygons")
        ax.legend(fontsize=8)
        ax.set_aspect("equal")
        plt.tight_layout()
        plt.show()

    def _render_surveillance(self, ax) -> None:
        """Draw the surveillance polygon, partitions, centers, and route."""
        coords = self.surveillance_polygon["coordinates"]
        entry = self.surveillance_polygon["entry_point"]
        exit_pt = self.surveillance_polygon["exit_point"]

        lons = [c["lon"] for c in coords] + [coords[0]["lon"]]
        lats = [c["lat"] for c in coords] + [coords[0]["lat"]]

        ax.fill(lons, lats, alpha=0.2, color="steelblue", label="Surveillance area")
        ax.plot(lons, lats, color="steelblue", linewidth=1.5)
        ax.scatter(
            [c["lon"] for c in coords],
            [c["lat"] for c in coords],
            color="darkblue", zorder=5, s=30,
        )

        # Bounding box
        bb = self.surveillance_bounding_box()
        bb_lons = [bb["min_lon"], bb["max_lon"], bb["max_lon"], bb["min_lon"], bb["min_lon"]]
        bb_lats = [bb["min_lat"], bb["min_lat"], bb["max_lat"], bb["max_lat"], bb["min_lat"]]
        ax.plot(bb_lons, bb_lats, color="tomato", linewidth=1, linestyle="--", label="Bounding box")

        # Partitions
        if hasattr(self, "_surveillance_partitions") and self._surveillance_partitions:
            patches = []
            for part in self._surveillance_partitions:
                corners = part["corners"]
                rect = mpatches.Polygon(
                    [(c["lon"], c["lat"]) for c in corners], closed=True,
                )
                patches.append(rect)
            pc = PatchCollection(
                patches, edgecolor="green", facecolor="green",
                alpha=0.12, linewidth=0.6,
            )
            ax.add_collection(pc)
            ax.plot([], [], color="green", linewidth=1.5, label="Partitions")

        # Centers
        if hasattr(self, "_surveillance_centers") and self._surveillance_centers:
            ax.scatter(
                [c["lon"] for c in self._surveillance_centers],
                [c["lat"] for c in self._surveillance_centers],
                color="red", marker="x", s=18, zorder=6, linewidths=0.7,
                label="Centers",
            )

        # Entry / exit
        ax.scatter(
            [entry["lon"]], [entry["lat"]],
            color="blue", marker="o", s=70, zorder=7, label="Surv. entry",
        )
        ax.scatter(
            [exit_pt["lon"]], [exit_pt["lat"]],
            facecolors="none", edgecolors="blue", marker="o",
            s=70, zorder=7, linewidths=1.5, label="Surv. exit",
        )

        # Surveillance route
        if hasattr(self, "_surveillance_route") and self._surveillance_route:
            ax.plot(
                [p["lon"] for p in self._surveillance_route],
                [p["lat"] for p in self._surveillance_route],
                color="darkorange", linewidth=0.8, zorder=5, label="Surv. route",
            )

    def _render_nav_polygons(self, ax) -> None:
        """Draw all navigation polygons and their planned paths."""
        colors = ["purple", "teal", "brown", "olive", "crimson", "darkgreen"]

        for idx, (pid, nav) in enumerate(self._nav_polygons.items()):
            color = colors[idx % len(colors)]
            pts = nav["points"]
            entry = nav["entry_point"]
            exit_pt = nav["exit_point"]

            lons = [p["lon"] for p in pts] + [pts[0]["lon"]]
            lats = [p["lat"] for p in pts] + [pts[0]["lat"]]

            ax.fill(lons, lats, alpha=0.15, color=color)
            ax.plot(lons, lats, color=color, linewidth=1.2, label=f"Nav: {pid}")

            ax.scatter(
                [entry["lon"]], [entry["lat"]],
                color=color, marker="^", s=60, zorder=7,
            )
            ax.scatter(
                [exit_pt["lon"]], [exit_pt["lat"]],
                facecolors="none", edgecolors=color, marker="^",
                s=60, zorder=7, linewidths=1.5,
            )

            # Planned nav path
            if nav["path"]:
                ax.plot(
                    [p["lon"] for p in nav["path"]],
                    [p["lat"] for p in nav["path"]],
                    color=color, linewidth=1.5, linestyle="--",
                    zorder=5, label=f"Nav path: {pid}",
                )
                # Cross markers for intermediate waypoints (exclude entry/exit)
                intermediate = nav["path"][1:-1]
                if intermediate:
                    ax.scatter(
                        [p["lon"] for p in intermediate],
                        [p["lat"] for p in intermediate],
                        color=color, marker="x", s=50, zorder=8,
                        linewidths=1.5, label=f"Nav waypoints: {pid}",
                    )
