
import math
import numpy as np
from pytransform3d.transformations import transform_from
from pytransform3d.rotations import matrix_from_quaternion

class Velocity:
    def __init__(self, x, y, z=0):
        self.x = x
        self.y = y
        self.z = z

class Q:
    def __init__(self, w, x, y, z=0):
        """Quaternion orientation in 3D space."""
        self.w = w
        self.x = x
        self.y = y
        self.z = z

class Position:
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z

def q_from_axis_angle(u, theta):
    """Convert an angle in radians to a quaternion representation (w, x, y, z) for 3D space.
    
    Args:
        u: A 3D unit vector representing the axis of rotation.
        theta: The angle of rotation in radians.

    """
    half_angle = theta / 2
    w = math.cos(half_angle)
    x = u[0] * math.sin(half_angle)
    y = u[1] * math.sin(half_angle)
    z = u[2] * math.sin(half_angle)
    return Q(w, x, y, z)

def axis_angle_from_q(q: Q):
    """Convert a quaternion representation (w, x, y, z) to an axis-angle representation (u, theta) for 3D space.
    
    Args:
        q: A quaternion representing the orientation in 3D space.
    Returns:
        u: A 3D unit vector representing the axis of rotation.
        theta: The angle of rotation in radians.
    """
    theta = 2 * math.acos(q.w)
    sin_half_theta = math.sqrt(1 - q.w * q.w)
    if sin_half_theta < 1e-6:
        # If the angle is very small, the axis can be arbitrary
        return np.array([1, 0, 0]), 0
    u = np.array([q.x, q.y, q.z]) / sin_half_theta
    return u, theta


class Drone:
    def __init__(self, id, position: Position, velocity: Velocity=Velocity(0,0), orientation: Q=Q(1,0,0,0)):
        self.id = id 
        self.position = position
        self.velocity = velocity
        self.orientation = orientation
        self.target_velocity = velocity
        self.target_orientation = orientation

    def target_velocity(self, new_velocity: Velocity):
        self.target_velocity = new_velocity
    
    def target_orientation(self, new_orientation: Q):
        self.target_orientation = new_orientation

    def step(self, dt):
        # Update orientation towards target orientation
        self.orientation.w += (self.target_orientation.w - self.orientation.w) * dt
        self.orientation.x += (self.target_orientation.x - self.orientation.x) * dt
        self.orientation.y += (self.target_orientation.y - self.orientation.y) * dt
        self.orientation.z += (self.target_orientation.z - self.orientation.z) * dt
        
        # Update velocity towards target velocity
        self.velocity.x += (self.target_velocity.x - self.velocity.x) * dt
        self.velocity.y += (self.target_velocity.y - self.velocity.y) * dt
        self.position.x += self.velocity.x * dt
        self.position.y += self.velocity.y * dt


class Formation:
    def __init__(self, formation_id: str, frame_postion: Position = Position(0,0, 0), frame_orientation: Q = Q(1,0,0,0)):
        self.formation_id = formation_id
        self.frame_position = frame_postion
        self.frame_orientation = frame_orientation
        self.positions = {}

    def add(self, drone_id, local_position: Position, local_orientation: Q):
        self.positions[drone_id] = {"position": local_position, "orientation": local_orientation}

def waypoint_formation(current_waypoint, next_waypoint, formation):
    """Generate target positions and orientations for each drone in the formation based on the current and next waypoints.
    
    Args:
        current_waypoint: The current waypoint as a Position object.
        next_waypoint: The next waypoint as a Position object.
        formation: The Formation object containing the local positions and orientations of the drones.
    Returns:
        A dictionary mapping each drone ID to its target global position and orientation.
    """
    # Calculate the direction vector from current to next waypoint
    direction = np.array([next_waypoint.x - current_waypoint.x, next_waypoint.y - current_waypoint.y], dtype=float)
    distance = np.linalg.norm(direction)
    if distance > 0:
        direction /= distance  # Normalize the direction vector

    # Calculate the angle of the formation based on the direction
    # Subtract π/2 so that the formation's y-axis aligns with the waypoint direction
    angle = math.atan2(direction[1], direction[0]) - math.pi / 2
    formation_orientation = q_from_axis_angle(np.array([0, 0, 1]), angle)

    targets = {}
    for drone_id, info in formation.positions.items():
        local_pos = info["position"]
        local_ori = info["orientation"]

        # Rotate local position by formation orientation
        rot_matrix = matrix_from_quaternion([formation_orientation.w, formation_orientation.x, formation_orientation.y, formation_orientation.z])[:3, :3]
        global_pos = np.dot(rot_matrix, np.array([local_pos.x, local_pos.y, local_pos.z])) + np.array([current_waypoint.x, current_waypoint.y, current_waypoint.z])

        # Combine orientations (for simplicity, we just use the formation orientation)
        global_ori = formation_orientation

        targets[drone_id] = {"position": Position(global_pos[0], global_pos[1], global_pos[2]), "orientation": global_ori}

    return targets

def interpolate_waypoints(waypoints, smoothness=1):
    """Interpolate between waypoints to create a smooth path for the formation.
    
    Args:
        waypoints: A list of Position objects representing the waypoints.
    Returns:
        A list of Position objects representing the interpolated path.
    """
    if not waypoints:
        return []

    interpolated_path = [waypoints[0]]
    for i in range(1, len(waypoints)):
        start = waypoints[i - 1]
        end = waypoints[i]
        steps = int(np.linalg.norm([end.x - start.x, end.y - start.y]) * smoothness)  # Adjust the multiplier for smoothness
        for j in range(1, steps + 1):
            t = j / steps
            interpolated_path.append(Position(
                start.x + t * (end.x - start.x),
                start.y + t * (end.y - start.y),
                start.z + t * (end.z - start.z)
            ))
    return interpolated_path

waypoints = [Position(0, 0, 0), Position(5, 8, 0), Position(10, 6, 0), Position(15, 10, 0), Position(20, 0, 0)]

interpolated_path = interpolate_waypoints(waypoints)

formation = Formation("V-Formation")
formation.add("drone1", Position(0, 1, 0), Q(1, 0, 0, 0))
formation.add("drone2", Position(-1, 0, 0), Q(1, 0, 0, 0))
formation.add("drone3", Position(1, 0, 0), Q(1, 0, 0, 0))
formation.add("drone4", Position(-2, -1, 0), Q(1, 0, 0, 0))
formation.add("drone5", Position(2, -1, 0), Q(1, 0, 0, 0))

# Plotting the waypoints and interpolated path
import matplotlib.pyplot as plt
waypoint_x = [wp.x for wp in waypoints]
waypoint_y = [wp.y for wp in waypoints]
interpolated_x = [wp.x for wp in interpolated_path]
interpolated_y = [wp.y for wp in interpolated_path] 
plt.figure(figsize=(10, 6))
plt.plot(waypoint_x, waypoint_y, 'ro-', label='Waypoints')
plt.plot(interpolated_x, interpolated_y, 'bx-', label='Interpolated Path')
plt.title('Waypoints and Interpolated Path')
plt.xlabel('X')
plt.ylabel('Y')
plt.legend()
plt.grid()

# Plot the formation at the first waypoint
targets = waypoint_formation(interpolated_path[20], interpolated_path[21], formation)
drone_x = []
drone_y = []
drone_u = []  # x-component of arrow direction
drone_v = []  # y-component of arrow direction

for drone_id, target in targets.items():
    pos = target["position"]
    ori = target["orientation"]
    
    # Calculate the y-axis direction in the drone's local frame
    # Rotate the unit y-vector [0, 1, 0] by the drone's orientation
    rot_matrix = matrix_from_quaternion([ori.w, ori.x, ori.y, ori.z])[:3, :3]
    y_axis = np.dot(rot_matrix, np.array([0, 1, 0]))
    
    drone_x.append(pos.x)
    drone_y.append(pos.y)
    drone_u.append(y_axis[0])
    drone_v.append(y_axis[1])

plt.quiver(drone_x, drone_y, drone_u, drone_v, color='green', scale=30, width=0.003, label='Drones')
plt.title('Formation Targets at First Waypoint')
plt.xlabel('X')
plt.ylabel('Y')
plt.legend()
plt.grid()
plt.show()
