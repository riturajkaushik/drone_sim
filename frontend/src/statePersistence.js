const STORAGE_KEY = 'drone_sim_state';

/**
 * Clear saved state from localStorage.
 */
export function clearState() {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch (e) {
    // silently ignore
  }
}

/**
 * Save the full application state to localStorage.
 */
export function saveState(manager, ui, polygonOverlay, corridorManager) {
  const state = {
    drones: manager.getAllDrones().map(d => ({
      id: d.id,
      lat: d.lat,
      lon: d.lon,
      speed: d.speed,
    })),
    captureArea: {
      x: manager._captureWidthMeters,
      y: manager._captureHeightMeters,
    },
    scalePercent: manager._scalePercent,
    speedSlider: parseInt(ui.speedSlider.value, 10),
    waypointQueues: Object.fromEntries(ui.waypointQueues),
    nextId: manager._nextId,
    polygon: {
      vertices: polygonOverlay.getVertices(),
      created: polygonOverlay.isCreated(),
    },
    corridors: corridorManager.getState(),
  };

  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch (e) {
    // localStorage might be full or unavailable — silently ignore
  }
}

/**
 * Restore application state from localStorage.
 * Recreates drones and applies settings.
 * @returns {boolean} true if state was restored
 */
export function restoreState(manager, ui, polygonOverlay, corridorManager) {
  let raw;
  try {
    raw = localStorage.getItem(STORAGE_KEY);
  } catch (e) {
    return false;
  }

  if (!raw) return false;

  let state;
  try {
    state = JSON.parse(raw);
  } catch (e) {
    return false;
  }

  // Restore nextId counter so new drones don't collide
  if (state.nextId) {
    manager._nextId = state.nextId;
  }

  // Restore capture area
  if (state.captureArea) {
    const { x, y } = state.captureArea;
    manager.setCaptureArea(x, y);
    ui.captureXInput.value = x;
    ui.captureYInput.value = y;
  }

  // Restore scale
  if (state.scalePercent) {
    manager.setScale(state.scalePercent);
    ui.droneScaleSlider.value = state.scalePercent;
    ui.droneScaleValue.textContent = `${state.scalePercent}%`;
  }

  // Restore speed slider
  if (state.speedSlider) {
    ui.speedSlider.value = state.speedSlider;
    ui.speedValue.textContent = `${state.speedSlider} m/s`;
  }

  // Restore drones
  if (state.drones && state.drones.length > 0) {
    for (const d of state.drones) {
      const result = manager.addDrone(d.lat, d.lon);
      if (result.drone) {
        result.drone.setSpeed(d.speed);
      }
    }
    ui._renderDroneList();
    ui._updateDroneSelects();
  }

  // Restore waypoint queues
  if (state.waypointQueues) {
    for (const [droneId, queue] of Object.entries(state.waypointQueues)) {
      if (manager.getDrone(droneId)) {
        ui.waypointQueues.set(droneId, queue);
      }
    }
    ui._renderWaypointList();
  }

  // Restore polygon
  if (state.polygon && state.polygon.vertices && state.polygon.vertices.length > 0) {
    for (const v of state.polygon.vertices) {
      polygonOverlay.addVertex(v.lat, v.lon);
    }
    if (state.polygon.created) {
      polygonOverlay.create();
    }
    ui._renderPolygonPointList();
    ui._updatePolyButtons();
  }

  // Restore nav corridors
  if (state.corridors) {
    corridorManager.restoreFromState(state.corridors);
    ui._updateCorridorSelect();
    ui._renderCorridorList();
    ui._renderCorridorPointList();
    ui._updateCorridorButtons();
  }

  return true;
}
