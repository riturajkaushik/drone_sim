from formation_sim import Position, Formation, Velocity, Q, interpolate_waypoints, waypoint_formation, matrix_from_quaternion
import numpy as np
import matplotlib.pyplot as plt

def main():
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


if __name__ == "__main__":
    main()
