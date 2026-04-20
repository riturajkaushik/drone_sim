/**
 * WebSocket client for backend communication.
 * Gracefully degrades — frontend works without backend.
 */
export class WSClient {
  constructor(manager, ui, url = 'ws://localhost:8000/ws/drone') {
    this.manager = manager;
    this.ui = ui;
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
