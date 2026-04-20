/**
 * UI controls — binds DOM elements to drone manager actions.
 * Works standalone without backend.
 */
export class UI {
  constructor(manager) {
    this.manager = manager;
    this.waypointQueues = new Map(); // droneId → [{lat, lon}, ...]

    // Capture Area
    this.captureXInput = document.getElementById('capture-x');
    this.captureYInput = document.getElementById('capture-y');
    this.setCaptureBtn = document.getElementById('set-capture-btn');

    // Drones
    this.droneLatInput = document.getElementById('drone-lat');
    this.droneLonInput = document.getElementById('drone-lon');
    this.addDroneBtn = document.getElementById('add-drone-btn');
    this.droneError = document.getElementById('drone-error');
    this.droneList = document.getElementById('drone-list');

    // Drone Scale
    this.droneScaleSlider = document.getElementById('drone-scale-slider');
    this.droneScaleValue = document.getElementById('drone-scale-value');

    // Fly To
    this.flyDroneSelect = document.getElementById('fly-drone-select');
    this.flyLatInput = document.getElementById('fly-lat');
    this.flyLonInput = document.getElementById('fly-lon');
    this.flyBtn = document.getElementById('fly-btn');

    // Speed
    this.speedSlider = document.getElementById('speed-slider');
    this.speedValue = document.getElementById('speed-value');

    // Waypoints
    this.wpDroneSelect = document.getElementById('wp-drone-select');
    this.wpLatInput = document.getElementById('wp-lat');
    this.wpLonInput = document.getElementById('wp-lon');
    this.addWpBtn = document.getElementById('add-wp-btn');
    this.clearWpBtn = document.getElementById('clear-wp-btn');
    this.flyWpBtn = document.getElementById('fly-wp-btn');
    this.waypointList = document.getElementById('waypoint-list');

    // Status
    this.statusDisplay = document.getElementById('status-display');

    // WS Status
    this.wsStatus = document.getElementById('ws-status');

    this._bindEvents();
  }

  _bindEvents() {
    // Capture area
    this.setCaptureBtn.addEventListener('click', () => {
      const x = parseFloat(this.captureXInput.value) || 0;
      const y = parseFloat(this.captureYInput.value) || 0;
      this.manager.setCaptureArea(x, y);
    });

    // Drone scale
    this.droneScaleSlider.addEventListener('input', () => {
      const percent = parseInt(this.droneScaleSlider.value, 10);
      this.droneScaleValue.textContent = `${percent}%`;
      this.manager.setScale(percent);
    });

    // Add drone
    this.addDroneBtn.addEventListener('click', () => {
      const lat = parseFloat(this.droneLatInput.value);
      const lon = parseFloat(this.droneLonInput.value);
      if (isNaN(lat) || isNaN(lon)) {
        this._showDroneError('Please enter valid lat/lon values.');
        return;
      }
      const result = this.manager.addDrone(lat, lon);
      if (result.error) {
        this._showDroneError(result.error);
      } else {
        this._clearDroneError();
        this._renderDroneList();
        this._updateDroneSelects();
      }
    });

    // Fly to
    this.flyBtn.addEventListener('click', () => {
      const droneId = this.flyDroneSelect.value;
      const drone = this.manager.getDrone(droneId);
      if (!drone) return;
      const lat = parseFloat(this.flyLatInput.value);
      const lon = parseFloat(this.flyLonInput.value);
      if (!isNaN(lat) && !isNaN(lon)) {
        drone.setTarget(lat, lon);
      }
    });

    // Speed slider — applies to all drones
    this.speedSlider.addEventListener('input', () => {
      const speed = parseInt(this.speedSlider.value, 10);
      this.speedValue.textContent = `${speed} m/s`;
      for (const drone of this.manager.getAllDrones()) {
        drone.setSpeed(speed);
      }
    });

    // Add waypoint
    this.addWpBtn.addEventListener('click', () => {
      const droneId = this.wpDroneSelect.value;
      if (!droneId) return;
      const lat = parseFloat(this.wpLatInput.value);
      const lon = parseFloat(this.wpLonInput.value);
      if (!isNaN(lat) && !isNaN(lon)) {
        if (!this.waypointQueues.has(droneId)) {
          this.waypointQueues.set(droneId, []);
        }
        this.waypointQueues.get(droneId).push({ lat, lon });
        this._renderWaypointList();
      }
    });

    // Clear waypoints
    this.clearWpBtn.addEventListener('click', () => {
      const droneId = this.wpDroneSelect.value;
      if (droneId) {
        this.waypointQueues.set(droneId, []);
      }
      this._renderWaypointList();
    });

    // Fly waypoints
    this.flyWpBtn.addEventListener('click', () => {
      const droneId = this.wpDroneSelect.value;
      const drone = this.manager.getDrone(droneId);
      const queue = this.waypointQueues.get(droneId);
      if (drone && queue && queue.length > 0) {
        drone.setWaypoints(queue);
      }
    });

    // Update waypoint list when drone selection changes
    this.wpDroneSelect.addEventListener('change', () => {
      this._renderWaypointList();
    });
  }

  _showDroneError(message) {
    this.droneError.textContent = message;
    this.droneError.style.display = 'block';
    setTimeout(() => this._clearDroneError(), 4000);
  }

  _clearDroneError() {
    this.droneError.textContent = '';
    this.droneError.style.display = 'none';
  }

  _renderDroneList() {
    this.droneList.innerHTML = '';
    for (const drone of this.manager.getAllDrones()) {
      const li = document.createElement('li');
      const colorHex = '#' + drone.color.toString(16).padStart(6, '0');
      li.innerHTML = `
        <span><span class="drone-color-dot" style="background:${colorHex}"></span>${drone.id} (${drone.lat.toFixed(4)}, ${drone.lon.toFixed(4)})</span>
        <span class="drone-remove" data-id="${drone.id}">✕</span>
      `;
      li.querySelector('.drone-remove').addEventListener('click', () => {
        this.manager.removeDrone(drone.id);
        this.waypointQueues.delete(drone.id);
        this._renderDroneList();
        this._updateDroneSelects();
      });
      this.droneList.appendChild(li);
    }
  }

  _updateDroneSelects() {
    const drones = this.manager.getAllDrones();
    for (const select of [this.flyDroneSelect, this.wpDroneSelect]) {
      const prev = select.value;
      select.innerHTML = '';
      for (const d of drones) {
        const opt = document.createElement('option');
        opt.value = d.id;
        opt.textContent = d.id;
        select.appendChild(opt);
      }
      // Restore previous selection if still valid
      if (drones.some(d => d.id === prev)) {
        select.value = prev;
      }
    }
  }

  _renderWaypointList() {
    this.waypointList.innerHTML = '';
    const droneId = this.wpDroneSelect.value;
    const queue = this.waypointQueues.get(droneId) || [];
    queue.forEach((wp, i) => {
      const li = document.createElement('li');
      li.innerHTML = `
        <span>#${i + 1}: ${wp.lat.toFixed(4)}, ${wp.lon.toFixed(4)}</span>
        <span class="wp-remove" data-index="${i}">✕</span>
      `;
      li.querySelector('.wp-remove').addEventListener('click', () => {
        queue.splice(i, 1);
        this._renderWaypointList();
      });
      this.waypointList.appendChild(li);
    });
  }

  updateStatus() {
    const drones = this.manager.getAllDrones();
    if (drones.length === 0) {
      this.statusDisplay.innerHTML = '<div class="status-empty">No drones added</div>';
      return;
    }
    this.statusDisplay.innerHTML = drones.map(d => {
      const colorHex = '#' + d.color.toString(16).padStart(6, '0');
      return `<div class="drone-status-item">
        <span class="drone-color-dot" style="background:${colorHex}"></span>
        <strong>${d.id}</strong>:
        ${d.lat.toFixed(4)}, ${d.lon.toFixed(4)} |
        ${d.speed.toFixed(0)} m/s |
        ${d.isFlying ? 'Flying' : 'Idle'}
      </div>`;
    }).join('');
  }

  setWsConnected(connected) {
    this.wsStatus.textContent = connected ? 'Connected' : 'Disconnected';
    this.wsStatus.className = connected ? 'connected' : '';
  }
}
