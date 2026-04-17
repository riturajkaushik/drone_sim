/**
 * WebSocket client for backend communication.
 * Gracefully degrades — frontend works without backend.
 */
export class WSClient {
  constructor(drone, ui, url = 'ws://localhost:8000/ws/drone') {
    this.drone = drone;
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
    const { type } = message;

    switch (type) {
      case 'set_waypoints': {
        const waypoints = message.waypoints || [];
        this.drone.setWaypoints(waypoints);
        // Also update the UI waypoint queue display
        this.ui.waypointQueue = [...waypoints];
        this.ui._renderWaypointList();
        break;
      }

      case 'set_velocity': {
        const speed = message.speed;
        if (speed !== undefined) {
          this.drone.setSpeed(speed);
          this.ui.speedSlider.value = speed;
          this.ui.speedValue.textContent = `${speed} m/s`;
        }
        break;
      }

      case 'get_status': {
        const status = this.drone.getStatus();
        this.send({
          type: 'status_response',
          ...status,
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

  sendWaypointReached(waypoint, index) {
    this.send({
      type: 'waypoint_reached',
      waypoint,
      index,
    });
  }
}
