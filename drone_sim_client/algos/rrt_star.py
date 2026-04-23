"""Informed RRT* path planner for navigation corridors.

Implements the Informed RRT* algorithm (Gammell et al., 2014) for planning
collision-free paths through polygonal corridors while maintaining a minimum
distance from the polygon boundary.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from shapely.geometry import LineString, Point, Polygon


@dataclass
class RRTNode:
    """A node in the RRT* search tree."""

    lat: float
    lon: float
    parent: RRTNode | None = None
    cost: float = 0.0
    children: list[RRTNode] = field(default_factory=list)

    @property
    def pos(self) -> tuple[float, float]:
        return (self.lon, self.lat)


class InformedRRTStar:
    """Informed RRT* path planner operating on Shapely polygons in lat/lon.

    Builds an RRT* tree from start to goal inside a polygonal corridor.
    After an initial solution is found, samples are drawn from the prolate
    hyperellipsoid defined by the current best cost, dramatically improving
    convergence in narrow/concave corridors.

    Args:
        polygon: The full corridor polygon (Shapely, coords in (lon, lat)).
        inner_polygon: The corridor polygon buffered inward by the border
            distance. Sample points are generated only inside this region.
            May be the same as *polygon* if the corridor is too narrow to
            buffer.
        start: Start point as {"lat": float, "lon": float}.
        goal: Goal point as {"lat": float, "lon": float}.
        step_size: Maximum extension distance per tree step (in degrees).
        neighbor_radius: Radius for the near-neighbor rewiring search (degrees).
        max_iterations: Number of RRT* iterations to run.
        seed: Random seed for reproducibility.
    """

    def __init__(
        self,
        polygon: Polygon,
        inner_polygon: Polygon,
        start: dict,
        goal: dict,
        step_size: float,
        neighbor_radius: float,
        max_iterations: int = 1000,
        seed: int = 42,
    ):
        self.polygon = polygon
        self.inner_polygon = inner_polygon
        self.start = start
        self.goal = goal
        self.step_size = step_size
        self.neighbor_radius = neighbor_radius
        self.max_iterations = max_iterations
        self.rng = random.Random(seed)

        self._start_node = RRTNode(lat=start["lat"], lon=start["lon"], cost=0.0)
        self._goal_node: RRTNode | None = None
        self._nodes: list[RRTNode] = [self._start_node]
        self._best_cost = float("inf")

        # Goal connection threshold
        self._goal_threshold = step_size * 1.5

        # Pre-compute ellipse parameters for informed sampling
        self._c_min = self._dist(start, goal)
        self._center_lon = (start["lon"] + goal["lon"]) / 2.0
        self._center_lat = (start["lat"] + goal["lat"]) / 2.0

        # Rotation angle of the ellipse (start-to-goal direction)
        dx = goal["lon"] - start["lon"]
        dy = goal["lat"] - start["lat"]
        self._theta = math.atan2(dy, dx)

        # Polygon bounds for uniform sampling fallback
        self._minx, self._miny, self._maxx, self._maxy = polygon.bounds

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def plan(self) -> list[dict]:
        """Run Informed RRT* and return the path as [{lat, lon}, ...].

        Returns:
            Ordered waypoints from start to goal.

        Raises:
            RuntimeError: If no path is found after max_iterations.
        """
        goal_threshold = self._goal_threshold

        for _ in range(self.max_iterations):
            # Sample: informed ellipsoid if we have a solution, else uniform
            sample = self._sample_informed()

            nearest = self._nearest(sample)
            new_point = self._steer(nearest, sample)

            # Reject points outside the inner polygon (border distance)
            # unless the parent is the start node (which may be on the border)
            new_sp = Point(new_point["lon"], new_point["lat"])
            is_from_start = nearest is self._start_node
            if not is_from_start and not self.inner_polygon.contains(new_sp):
                continue

            if not self._collision_free_segment(nearest, new_point):
                continue

            # Find nearby nodes for RRT* rewiring
            near_nodes = self._near(new_point)

            # Choose best parent among near nodes
            new_node = RRTNode(lat=new_point["lat"], lon=new_point["lon"])
            best_parent = nearest
            best_cost = nearest.cost + self._node_dist(nearest, new_node)

            for node in near_nodes:
                candidate_cost = node.cost + self._node_dist(node, new_node)
                if candidate_cost < best_cost and self._collision_free_segment(
                    node, new_point
                ):
                    best_parent = node
                    best_cost = candidate_cost

            new_node.parent = best_parent
            new_node.cost = best_cost
            best_parent.children.append(new_node)
            self._nodes.append(new_node)

            # Rewire nearby nodes through new_node if cheaper
            self._rewire(new_node, near_nodes)

            # Check if we can connect to goal
            dist_to_goal = self._node_dist_to_point(
                new_node, self.goal
            )
            if dist_to_goal <= goal_threshold:
                if self._collision_free_to_goal(new_node):
                    candidate_cost = new_node.cost + dist_to_goal
                    if candidate_cost < self._best_cost:
                        self._best_cost = candidate_cost
                        # Create or update goal node
                        if self._goal_node is None:
                            self._goal_node = RRTNode(
                                lat=self.goal["lat"],
                                lon=self.goal["lon"],
                                parent=new_node,
                                cost=candidate_cost,
                            )
                            new_node.children.append(self._goal_node)
                            self._nodes.append(self._goal_node)
                        else:
                            # Detach from old parent
                            if self._goal_node.parent is not None:
                                old_parent = self._goal_node.parent
                                if self._goal_node in old_parent.children:
                                    old_parent.children.remove(self._goal_node)
                            self._goal_node.parent = new_node
                            self._goal_node.cost = candidate_cost
                            new_node.children.append(self._goal_node)

        if self._goal_node is None:
            raise RuntimeError(
                "Informed RRT* failed to find a path within "
                f"{self.max_iterations} iterations."
            )

        path = self._extract_path()
        path = self._smooth_path(path)
        return path

    # ------------------------------------------------------------------
    # Sampling
    # ------------------------------------------------------------------

    def _sample_informed(self) -> dict:
        """Sample a point: from the informed ellipsoid if a solution exists."""
        if self._best_cost < float("inf"):
            # Informed sampling within ellipsoid
            for _ in range(100):
                pt = self._sample_ellipsoid()
                sp = Point(pt["lon"], pt["lat"])
                if self.inner_polygon.contains(sp):
                    return pt
            # Fallback to uniform if ellipsoid samples keep missing
        return self._sample_uniform()

    def _sample_uniform(self) -> dict:
        """Uniform random sample inside the inner polygon."""
        for _ in range(1000):
            lon = self.rng.uniform(self._minx, self._maxx)
            lat = self.rng.uniform(self._miny, self._maxy)
            if self.inner_polygon.contains(Point(lon, lat)):
                return {"lat": lat, "lon": lon}
        # Last resort: return polygon centroid
        c = self.inner_polygon.centroid
        return {"lat": c.y, "lon": c.x}

    def _sample_ellipsoid(self) -> dict:
        """Sample uniformly from the prolate hyperellipsoid (2D ellipse).

        The ellipse is defined by start and goal as foci, with the major
        axis length equal to the current best path cost.
        """
        c_best = self._best_cost
        c_min = self._c_min

        if c_best <= c_min or c_min < 1e-15:
            return self._sample_uniform()

        # Semi-axes of the ellipse
        a = c_best / 2.0  # semi-major
        b = math.sqrt(c_best * c_best - c_min * c_min) / 2.0  # semi-minor

        # Sample uniformly in the unit disk, then scale
        r = math.sqrt(self.rng.random())
        angle = self.rng.uniform(0, 2 * math.pi)
        x_ball = r * math.cos(angle)
        y_ball = r * math.sin(angle)

        # Scale to ellipse
        x_ell = a * x_ball
        y_ell = b * y_ball

        # Rotate and translate to world frame
        cos_t = math.cos(self._theta)
        sin_t = math.sin(self._theta)
        lon = self._center_lon + x_ell * cos_t - y_ell * sin_t
        lat = self._center_lat + x_ell * sin_t + y_ell * cos_t

        return {"lat": lat, "lon": lon}

    # ------------------------------------------------------------------
    # Tree operations
    # ------------------------------------------------------------------

    def _nearest(self, point: dict) -> RRTNode:
        """Find the nearest node in the tree to the given point."""
        best_node = self._nodes[0]
        best_dist = self._node_dist_to_point(best_node, point)
        for node in self._nodes[1:]:
            d = self._node_dist_to_point(node, point)
            if d < best_dist:
                best_dist = d
                best_node = node
        return best_node

    def _near(self, point: dict) -> list[RRTNode]:
        """Find all nodes within neighbor_radius of the given point.

        Uses the RRT* adaptive radius: min(gamma * (log(n)/n)^(1/d), step_size).
        """
        n = len(self._nodes)
        if n < 2:
            return list(self._nodes)

        # RRT* radius formula (2D): gamma * sqrt(log(n)/n)
        gamma = self.neighbor_radius * 2.0
        radius = min(
            gamma * math.sqrt(math.log(n) / n),
            self.step_size * 2.0,
        )
        # Don't let radius shrink below a useful minimum
        radius = max(radius, self.step_size * 0.5)

        result = []
        for node in self._nodes:
            if self._node_dist_to_point(node, point) <= radius:
                result.append(node)
        return result

    def _steer(self, from_node: RRTNode, to_point: dict) -> dict:
        """Steer from from_node toward to_point, capped at step_size."""
        dx = to_point["lon"] - from_node.lon
        dy = to_point["lat"] - from_node.lat
        dist = math.sqrt(dx * dx + dy * dy)

        if dist <= self.step_size:
            return {"lat": to_point["lat"], "lon": to_point["lon"]}

        ratio = self.step_size / dist
        return {
            "lat": from_node.lat + dy * ratio,
            "lon": from_node.lon + dx * ratio,
        }

    def _rewire(self, new_node: RRTNode, near_nodes: list[RRTNode]) -> None:
        """Rewire near nodes through new_node if it provides a cheaper path."""
        for node in near_nodes:
            if node is new_node or node is self._start_node:
                continue
            new_cost = new_node.cost + self._node_dist(new_node, node)
            if new_cost < node.cost:
                new_pt = {"lat": node.lat, "lon": node.lon}
                if self._collision_free_segment(new_node, new_pt):
                    # Detach from old parent
                    if node.parent is not None and node in node.parent.children:
                        node.parent.children.remove(node)
                    node.parent = new_node
                    node.cost = new_cost
                    new_node.children.append(node)
                    self._propagate_cost(node)

    def _propagate_cost(self, node: RRTNode) -> None:
        """Recursively update costs of descendants after rewiring."""
        for child in node.children:
            child.cost = node.cost + self._node_dist(node, child)
            self._propagate_cost(child)

    # ------------------------------------------------------------------
    # Collision checking
    # ------------------------------------------------------------------

    def _collision_free_segment(self, from_node: RRTNode, to_point: dict) -> bool:
        """Check if the segment from a node to a point lies within the corridor."""
        line = LineString(
            [(from_node.lon, from_node.lat), (to_point["lon"], to_point["lat"])]
        )
        return self.polygon.buffer(1e-10).contains(line)

    def _collision_free_to_goal(self, from_node: RRTNode) -> bool:
        """Check segment to goal using the full polygon (goal may be near border)."""
        line = LineString(
            [(from_node.lon, from_node.lat), (self.goal["lon"], self.goal["lat"])]
        )
        return self.polygon.buffer(1e-10).contains(line)

    # ------------------------------------------------------------------
    # Path extraction and smoothing
    # ------------------------------------------------------------------

    def _extract_path(self) -> list[dict]:
        """Trace back from goal to start, return ordered start→goal."""
        path = []
        node = self._goal_node
        while node is not None:
            path.append({"lat": node.lat, "lon": node.lon})
            node = node.parent
        path.reverse()
        return path

    def _smooth_path(self, path: list[dict]) -> list[dict]:
        """Greedy shortcutting: skip intermediate nodes when direct path is clear.

        Uses the inner polygon for middle segments to maintain border distance,
        and the full polygon for segments touching start/goal.
        """
        if len(path) <= 2:
            return path

        smoothed = [path[0]]
        i = 0
        while i < len(path) - 1:
            furthest = i + 1
            for j in range(len(path) - 1, i + 1, -1):
                segment = LineString(
                    [
                        (path[i]["lon"], path[i]["lat"]),
                        (path[j]["lon"], path[j]["lat"]),
                    ]
                )
                # Use full polygon for segments touching start/goal
                is_endpoint_seg = (i == 0 or j == len(path) - 1)
                check_poly = self.polygon if is_endpoint_seg else self.inner_polygon
                if check_poly.buffer(1e-10).contains(segment):
                    furthest = j
                    break
            smoothed.append(path[furthest])
            i = furthest

        return smoothed

    # ------------------------------------------------------------------
    # Distance helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _dist(a: dict, b: dict) -> float:
        dlat = a["lat"] - b["lat"]
        dlon = a["lon"] - b["lon"]
        return math.sqrt(dlat * dlat + dlon * dlon)

    @staticmethod
    def _node_dist(a: RRTNode, b: RRTNode) -> float:
        dlat = a.lat - b.lat
        dlon = a.lon - b.lon
        return math.sqrt(dlat * dlat + dlon * dlon)

    @staticmethod
    def _node_dist_to_point(node: RRTNode, point: dict) -> float:
        dlat = node.lat - point["lat"]
        dlon = node.lon - point["lon"]
        return math.sqrt(dlat * dlat + dlon * dlon)
