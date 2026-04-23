/**
 * WebSocket client for backend communication.
 * Gracefully degrades — frontend works without backend.
 */
export class WSClient {
  constructor(manager, ui, polygonOverlay, corridorManager, entryExitMarkers, url = 'ws://localhost:8000/ws/drone') {
    this.manager = manager;
    this.ui = ui;
    this.polygonOverlay = polygonOverlay;
    this.corridorManager = corridorManager;
    this.entryExitMarkers = entryExitMarkers;
    this.url = url;
    this.ws = null;
    this.reconnectDelay = 3000;
    this._reconnectTimer = null;
  }

  connect() {
    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        console.log('WebSocket connected');
        this.ui.setWsConnected(true);
      };

      this.ws.onclose = () => {
        console.log('WebSocket disconnected');
        this.ui.setWsConnected(false);
        this._scheduleReconnect();
      };

      this.ws.onerror = () => {
        // onclose will fire after this
      };

      this.ws.onmessage = (event) => {
        this._handleMessage(JSON.parse(event.data));
      };
    } catch (e) {
      console.warn('WebSocket connection failed:', e);
      this.ui.setWsConnected(false);
      this._scheduleReconnect();
    }
  }

  _scheduleReconnect() {
    if (this._reconnectTimer) return;
    this._reconnectTimer = setTimeout(() => {
      this._reconnectTimer = null;
      this.connect();
    }, this.reconnectDelay);
  }

  _handleMessage(message) {
    const { type, drone_id } = message;
    // If a drone_id is specified, target that drone; otherwise first drone
    const drone = drone_id
      ? this.manager.getDrone(drone_id)
      : this.manager.getAllDrones()[0];

    switch (type) {
      case 'set_waypoints': {
        if (!drone) break;
        const waypoints = message.waypoints || [];
        drone.setWaypoints(waypoints);
        break;
      }

      case 'set_velocity': {
        if (!drone) break;
        const speed = message.speed;
        if (speed !== undefined) {
          drone.setSpeed(speed);
          this.ui.speedSlider.value = speed;
          this.ui.speedValue.textContent = `${speed} m/s`;
        }
        break;
      }

      case 'get_status': {
        // Return status for all drones
        const statuses = this.manager.getAllDrones().map(d => d.getStatus());
        this.send({
          type: 'status_response',
          drones: statuses,
        });
        break;
      }

      case 'spawn_drones': {
        const drones = message.drones || [];
        for (const d of drones) {
          const [lat, lon] = d.spawn_loc;
          // Skip if this drone already exists locally (e.g. we sent the command)
          if (this.manager.getDrone(d.drone_id)) continue;
          const result = this.manager.addDrone(lat, lon, d.drone_id);
          if (result.error) {
            console.warn(`Failed to spawn drone ${d.drone_id}:`, result.error);
          } else {
            // Wire waypoint callback to send over WS
            const droneId = d.drone_id;
            result.drone.onWaypointReached = (wp, idx) => {
              this.sendWaypointReached(droneId, wp, idx);
            };
          }
        }
        this.ui.refreshDroneList();
        break;
      }

      case 'reset_sim': {
        this.manager.removeAll();
        this.polygonOverlay.remove();
        this.corridorManager.removeAll();
        this.entryExitMarkers.removeAll();
        this.ui.resetAll();
        console.log('Simulator reset via backend');
        break;
      }

      case 'set_surveillance_polygon': {
        const polygon = message.surveillance_polygon || [];
        this.polygonOverlay.remove();
        for (const [lat, lon] of polygon) {
          this.polygonOverlay.addVertex(lat, lon);
        }
        if (polygon.length >= 3) {
          this.polygonOverlay.create();
        }
        console.log(`Surveillance polygon set with ${polygon.length} vertices`);
        break;
      }

      case 'set_nav_corridors': {
        const corridors = message.nav_corridors || {};
        this.corridorManager.removeAll();
        for (const [corridorId, data] of Object.entries(corridors)) {
          const { overlay } = this.corridorManager.addCorridor();
          // Support both new format {vertices, entry_point, exit_point} and legacy [vertices]
          const vertices = Array.isArray(data) ? data : (data.vertices || []);
          for (const v of vertices) {
            const [lat, lon] = Array.isArray(v) ? v : [v.lat, v.lon];
            overlay.addVertex(lat, lon);
          }
          if (vertices.length >= 3) {
            overlay.create();
          }
          // Get the ID of the corridor we just added (last one)
          const allCorridors = this.corridorManager.getAllCorridors();
          const addedId = allCorridors[allCorridors.length - 1].id;
          // Set entry/exit if provided (new format)
          if (!Array.isArray(data)) {
            if (data.entry_point && data.entry_point.length === 2) {
              this.corridorManager.setCorridorEntryPoint(addedId, data.entry_point[0], data.entry_point[1]);
            }
            if (data.exit_point && data.exit_point.length === 2) {
              this.corridorManager.setCorridorExitPoint(addedId, data.exit_point[0], data.exit_point[1]);
            }
          }
        }
        this.ui._updateCorridorSelect();
        this.ui._renderCorridorList();
        this.ui._renderCorridorEntryExitDisplay();
        console.log(`Nav corridors set: ${Object.keys(corridors).join(', ')}`);
        break;
      }

      case 'set_entry_exit_points': {
        const entry = message.entry_point;
        const exit = message.exit_point;
        this.entryExitMarkers.removeAll();
        if (entry && entry.length === 2) {
          this.entryExitMarkers.setEntryPoint(entry[0], entry[1]);
        }
        if (exit && exit.length === 2) {
          this.entryExitMarkers.setExitPoint(exit[0], exit[1]);
        }
        this.ui._renderEntryExitDisplay();
        console.log(`Entry/exit points set: entry=(${entry}), exit=(${exit})`);
        break;
      }

      default:
        console.warn('Unknown WS message type:', type);
    }
  }

  send(message) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    }
  }

  sendWaypointReached(droneId, waypoint, index) {
    this.send({
      type: 'waypoint_reached',
      drone_id: droneId,
      waypoint,
      index,
    });
  }
}
