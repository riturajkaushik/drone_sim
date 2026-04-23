/**
 * UI controls — binds DOM elements to drone manager actions.
 * Works standalone without backend.
 */
export class UI {
  constructor(manager, polygonOverlay, corridorManager, mapPicker) {
    this.manager = manager;
    this.polygonOverlay = polygonOverlay;
    this.corridorManager = corridorManager;
    this.mapPicker = mapPicker;
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

    // Polygon
    this.polyLatInput = document.getElementById('poly-lat');
    this.polyLonInput = document.getElementById('poly-lon');
    this.addPolyPointBtn = document.getElementById('add-poly-point-btn');
    this.createPolyBtn = document.getElementById('create-poly-btn');
    this.removePolyBtn = document.getElementById('remove-poly-btn');
    this.polygonPointList = document.getElementById('polygon-point-list');

    // Nav Corridors
    this.newCorridorBtn = document.getElementById('new-corridor-btn');
    this.corridorSelect = document.getElementById('corridor-select');
    this.corridorLatInput = document.getElementById('corridor-lat');
    this.corridorLonInput = document.getElementById('corridor-lon');
    this.addCorridorPointBtn = document.getElementById('add-corridor-point-btn');
    this.createCorridorBtn = document.getElementById('create-corridor-btn');
    this.removeCorridorBtn = document.getElementById('remove-corridor-btn');
    this.corridorPointList = document.getElementById('corridor-point-list');
    this.corridorList = document.getElementById('corridor-list');

    // Picker buttons
    this.polyPickBtn = document.getElementById('poly-pick-btn');
    this.corridorPickBtn = document.getElementById('corridor-pick-btn');

    // Status
    this.statusDisplay = document.getElementById('status-display');

    // WS Status
    this.wsStatus = document.getElementById('ws-status');

    // Reset
    this.resetSimBtn = document.getElementById('reset-sim-btn');

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
        this._previewWaypoints(droneId);
      }
    });

    // Clear waypoints
    this.clearWpBtn.addEventListener('click', () => {
      const droneId = this.wpDroneSelect.value;
      if (droneId) {
        this.waypointQueues.set(droneId, []);
      }
      this._renderWaypointList();
      this._previewWaypoints(droneId);
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

    // Polygon: add point
    this.addPolyPointBtn.addEventListener('click', () => {
      const lat = parseFloat(this.polyLatInput.value);
      const lon = parseFloat(this.polyLonInput.value);
      if (!isNaN(lat) && !isNaN(lon)) {
        this.polygonOverlay.addVertex(lat, lon);
        this._renderPolygonPointList();
        this._updatePolyButtons();
      }
    });

    // Polygon: create
    this.createPolyBtn.addEventListener('click', () => {
      this.polygonOverlay.create();
      this._updatePolyButtons();
      if (this._activePickerMode === 'polygon') this.mapPicker.deactivate();
    });

    // Polygon: remove
    this.removePolyBtn.addEventListener('click', () => {
      this.polygonOverlay.remove();
      this._renderPolygonPointList();
      this._updatePolyButtons();
      if (this._activePickerMode === 'polygon') this.mapPicker.deactivate();
    });

    // Nav Corridors: new corridor
    this.newCorridorBtn.addEventListener('click', () => {
      this.corridorManager.addCorridor();
      this._updateCorridorSelect();
      this._renderCorridorList();
      this._renderCorridorPointList();
      this._updateCorridorButtons();
    });

    // Nav Corridors: select change
    this.corridorSelect.addEventListener('change', () => {
      this._renderCorridorPointList();
      this._updateCorridorButtons();
    });

    // Nav Corridors: add point
    this.addCorridorPointBtn.addEventListener('click', () => {
      const id = this.corridorSelect.value;
      const entry = this.corridorManager.getCorridor(id);
      if (!entry) return;
      const lat = parseFloat(this.corridorLatInput.value);
      const lon = parseFloat(this.corridorLonInput.value);
      if (!isNaN(lat) && !isNaN(lon)) {
        entry.overlay.addVertex(lat, lon);
        this._renderCorridorPointList();
        this._updateCorridorButtons();
      }
    });

    // Nav Corridors: create
    this.createCorridorBtn.addEventListener('click', () => {
      const id = this.corridorSelect.value;
      const entry = this.corridorManager.getCorridor(id);
      if (!entry) return;
      entry.overlay.create();
      this._renderCorridorList();
      this._updateCorridorButtons();
      if (this._activePickerMode === 'corridor') this.mapPicker.deactivate();
    });

    // Nav Corridors: remove selected corridor
    this.removeCorridorBtn.addEventListener('click', () => {
      const id = this.corridorSelect.value;
      if (!id) return;
      this.corridorManager.removeCorridor(id);
      this._updateCorridorSelect();
      this._renderCorridorList();
      this._renderCorridorPointList();
      this._updateCorridorButtons();
      if (this._activePickerMode === 'corridor') this.mapPicker.deactivate();
    });

    // Picker: surveillance polygon
    this.polyPickBtn.addEventListener('click', () => {
      if (this.mapPicker.isActive() && this._activePickerMode === 'polygon') {
        this.mapPicker.deactivate();
        return;
      }
      this._activePickerMode = 'polygon';
      this._setPickerButtonStates(this.polyPickBtn);
      this.mapPicker.activate(
        (lat, lon) => {
          this.polygonOverlay.addVertex(lat, lon);
          this._renderPolygonPointList();
          this._updatePolyButtons();
        },
        () => this._clearPickerButtonStates()
      );
    });

    // Picker: nav corridor
    this.corridorPickBtn.addEventListener('click', () => {
      if (this.mapPicker.isActive() && this._activePickerMode === 'corridor') {
        this.mapPicker.deactivate();
        return;
      }
      const id = this.corridorSelect.value;
      const entry = this.corridorManager.getCorridor(id);
      if (!entry) return;
      this._activePickerMode = 'corridor';
      this._setPickerButtonStates(this.corridorPickBtn);
      this.mapPicker.activate(
        (lat, lon) => {
          const currentId = this.corridorSelect.value;
          const currentEntry = this.corridorManager.getCorridor(currentId);
          if (!currentEntry) return;
          currentEntry.overlay.addVertex(lat, lon);
          this._renderCorridorPointList();
          this._updateCorridorButtons();
        },
        () => this._clearPickerButtonStates()
      );
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

  /** Public method to refresh drone list and selects (e.g. after WS spawn). */
  refreshDroneList() {
    this._renderDroneList();
    this._updateDroneSelects();
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
        this._previewWaypoints(droneId);
      });
      this.waypointList.appendChild(li);
    });
  }

  _previewWaypoints(droneId) {
    const drone = this.manager.getDrone(droneId);
    if (!drone) return;
    if (drone.isFlying) return; // don't override active flight visuals
    const queue = this.waypointQueues.get(droneId) || [];
    drone.previewWaypoints(queue);
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

  /**
   * Reset all UI state: waypoint queues, drone list, polygon, corridors, selects.
   * Does NOT touch the managers/overlays — caller is responsible for clearing those.
   */
  resetAll() {
    this.waypointQueues.clear();
    this._renderDroneList();
    this._updateDroneSelects();
    this._renderWaypointList();
    this._renderPolygonPointList();
    this._updatePolyButtons();
    this._updateCorridorSelect();
    this._renderCorridorList();
    this._renderCorridorPointList();
    this._updateCorridorButtons();
  }

  _renderPolygonPointList() {
    this.polygonPointList.innerHTML = '';
    const verts = this.polygonOverlay.getVertices();
    verts.forEach((v, i) => {
      const li = document.createElement('li');
      li.innerHTML = `
        <span>#${i + 1}: ${v.lat.toFixed(4)}, ${v.lon.toFixed(4)}</span>
        <span class="poly-remove" data-index="${i}">✕</span>
      `;
      li.querySelector('.poly-remove').addEventListener('click', () => {
        this.polygonOverlay.removeVertex(i);
        this._renderPolygonPointList();
        this._updatePolyButtons();
      });
      this.polygonPointList.appendChild(li);
    });
  }

  _updatePolyButtons() {
    const count = this.polygonOverlay.getVertices().length;
    this.createPolyBtn.disabled = count < 3 || this.polygonOverlay.isCreated();
  }

  // --- Nav Corridor helpers ---

  _updateCorridorSelect() {
    const corridors = this.corridorManager.getAllCorridors();
    const prev = this.corridorSelect.value;
    this.corridorSelect.innerHTML = '';
    for (const c of corridors) {
      const opt = document.createElement('option');
      opt.value = c.id;
      opt.textContent = c.id;
      this.corridorSelect.appendChild(opt);
    }
    // Select last corridor if previous selection gone
    if (corridors.some(c => c.id === prev)) {
      this.corridorSelect.value = prev;
    } else if (corridors.length > 0) {
      this.corridorSelect.value = corridors[corridors.length - 1].id;
    }
  }

  _renderCorridorPointList() {
    this.corridorPointList.innerHTML = '';
    const id = this.corridorSelect.value;
    const entry = this.corridorManager.getCorridor(id);
    if (!entry) return;
    const verts = entry.overlay.getVertices();
    verts.forEach((v, i) => {
      const li = document.createElement('li');
      li.innerHTML = `
        <span>#${i + 1}: ${v.lat.toFixed(4)}, ${v.lon.toFixed(4)}</span>
        <span class="corridor-pt-remove" data-index="${i}">✕</span>
      `;
      li.querySelector('.corridor-pt-remove').addEventListener('click', () => {
        entry.overlay.removeVertex(i);
        this._renderCorridorPointList();
        this._updateCorridorButtons();
      });
      this.corridorPointList.appendChild(li);
    });
  }

  _renderCorridorList() {
    this.corridorList.innerHTML = '';
    for (const c of this.corridorManager.getAllCorridors()) {
      const li = document.createElement('li');
      const status = c.overlay.isCreated() ? '✔' : `${c.overlay.getVertices().length} pts`;
      li.innerHTML = `
        <span><span class="corridor-color-dot"></span>${c.id} (${status})</span>
        <span class="corridor-remove" data-id="${c.id}">✕</span>
      `;
      li.querySelector('.corridor-remove').addEventListener('click', () => {
        this.corridorManager.removeCorridor(c.id);
        this._updateCorridorSelect();
        this._renderCorridorList();
        this._renderCorridorPointList();
        this._updateCorridorButtons();
      });
      this.corridorList.appendChild(li);
    }
  }

  _updateCorridorButtons() {
    const id = this.corridorSelect.value;
    const entry = this.corridorManager.getCorridor(id);
    if (!entry) {
      this.createCorridorBtn.disabled = true;
      this.addCorridorPointBtn.disabled = true;
      return;
    }
    this.addCorridorPointBtn.disabled = false;
    const count = entry.overlay.getVertices().length;
    this.createCorridorBtn.disabled = count < 3 || entry.overlay.isCreated();
  }

  // --- Picker button helpers ---

  _setPickerButtonStates(activeBtn) {
    this.polyPickBtn.classList.remove('active');
    this.corridorPickBtn.classList.remove('active');
    activeBtn.classList.add('active');
  }

  _clearPickerButtonStates() {
    this.polyPickBtn.classList.remove('active');
    this.corridorPickBtn.classList.remove('active');
    this._activePickerMode = null;
  }
}
