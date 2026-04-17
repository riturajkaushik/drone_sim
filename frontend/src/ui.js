/**
 * UI controls — binds DOM elements to drone actions.
 * Works standalone without backend.
 */
export class UI {
  constructor(drone) {
    this.drone = drone;
    this.waypointQueue = [];

    // Fly To
    this.flyLatInput = document.getElementById('fly-lat');
    this.flyLonInput = document.getElementById('fly-lon');
    this.flyBtn = document.getElementById('fly-btn');

    // Speed
    this.speedSlider = document.getElementById('speed-slider');
    this.speedValue = document.getElementById('speed-value');

    // Waypoints
    this.wpLatInput = document.getElementById('wp-lat');
    this.wpLonInput = document.getElementById('wp-lon');
    this.addWpBtn = document.getElementById('add-wp-btn');
    this.clearWpBtn = document.getElementById('clear-wp-btn');
    this.flyWpBtn = document.getElementById('fly-wp-btn');
    this.waypointList = document.getElementById('waypoint-list');

    // Status
    this.statusLat = document.getElementById('status-lat');
    this.statusLon = document.getElementById('status-lon');
    this.statusSpeed = document.getElementById('status-speed');
    this.statusState = document.getElementById('status-state');

    // WS Status
    this.wsStatus = document.getElementById('ws-status');

    this._bindEvents();
  }

  _bindEvents() {
    // Fly to
    this.flyBtn.addEventListener('click', () => {
      const lat = parseFloat(this.flyLatInput.value);
      const lon = parseFloat(this.flyLonInput.value);
      if (!isNaN(lat) && !isNaN(lon)) {
        this.drone.setTarget(lat, lon);
      }
    });

    // Speed slider
    this.speedSlider.addEventListener('input', () => {
      const speed = parseInt(this.speedSlider.value, 10);
      this.speedValue.textContent = `${speed} m/s`;
      this.drone.setSpeed(speed);
    });

    // Add waypoint
    this.addWpBtn.addEventListener('click', () => {
      const lat = parseFloat(this.wpLatInput.value);
      const lon = parseFloat(this.wpLonInput.value);
      if (!isNaN(lat) && !isNaN(lon)) {
        this.waypointQueue.push({ lat, lon });
        this._renderWaypointList();
      }
    });

    // Clear waypoints
    this.clearWpBtn.addEventListener('click', () => {
      this.waypointQueue = [];
      this._renderWaypointList();
    });

    // Fly waypoints
    this.flyWpBtn.addEventListener('click', () => {
      if (this.waypointQueue.length > 0) {
        this.drone.setWaypoints(this.waypointQueue);
      }
    });
  }

  _renderWaypointList() {
    this.waypointList.innerHTML = '';
    this.waypointQueue.forEach((wp, i) => {
      const li = document.createElement('li');
      li.innerHTML = `
        <span>#${i + 1}: ${wp.lat.toFixed(4)}, ${wp.lon.toFixed(4)}</span>
        <span class="wp-remove" data-index="${i}">✕</span>
      `;
      li.querySelector('.wp-remove').addEventListener('click', () => {
        this.waypointQueue.splice(i, 1);
        this._renderWaypointList();
      });
      this.waypointList.appendChild(li);
    });
  }

  updateStatus(status) {
    this.statusLat.textContent = status.lat.toFixed(6);
    this.statusLon.textContent = status.lon.toFixed(6);
    this.statusSpeed.textContent = `${status.speed.toFixed(1)} m/s`;
    this.statusState.textContent = status.is_flying ? 'Flying' : 'Idle';
  }

  setWsConnected(connected) {
    this.wsStatus.textContent = connected ? 'Connected' : 'Disconnected';
    this.wsStatus.className = connected ? 'connected' : '';
  }
}
