import { Drone } from './drone.js';
import { isInBounds } from './coordinates.js';

/**
 * Manages multiple drones identified by unique IDs.
 */
export class DroneManager {
  constructor(scene) {
    this.scene = scene;
    this.drones = new Map(); // id → Drone
    this._nextId = 1;
    this._captureWidthMeters = 0;
    this._captureHeightMeters = 0;
    this._scalePercent = 100;
  }

  /**
   * Add a new drone at the given position.
   * @param {number} lat
   * @param {number} lon
   * @param {string|null} id - Optional explicit ID. Auto-generated if null.
   * @returns {{ drone: Drone } | { error: string }}
   */
  addDrone(lat, lon, id = null) {
    if (!isInBounds(lat, lon)) {
      return { error: `Coordinates (${lat.toFixed(4)}, ${lon.toFixed(4)}) are outside the visible map area.` };
    }

    if (id && this.drones.has(id)) {
      return { error: `Drone ID '${id}' already exists.` };
    }

    if (!id) {
      id = `drone-${this._nextId++}`;
    }
    const drone = new Drone(this.scene, id, lat, lon);

    // Apply current capture area setting
    if (this._captureWidthMeters > 0 && this._captureHeightMeters > 0) {
      drone.setCaptureArea(this._captureWidthMeters, this._captureHeightMeters);
    }

    // Apply current scale
    if (this._scalePercent !== 100) {
      drone.setScale(this._scalePercent);
    }

    this.drones.set(id, drone);
    return { drone };
  }

  removeDrone(id) {
    const drone = this.drones.get(id);
    if (!drone) return false;
    drone.dispose();
    this.drones.delete(id);
    return true;
  }

  getDrone(id) {
    return this.drones.get(id) || null;
  }

  getAllDrones() {
    return Array.from(this.drones.values());
  }

  /**
   * Set capture area dimensions for all drones.
   */
  setCaptureArea(widthMeters, heightMeters) {
    this._captureWidthMeters = widthMeters;
    this._captureHeightMeters = heightMeters;
    for (const drone of this.drones.values()) {
      drone.setCaptureArea(widthMeters, heightMeters);
    }
  }

  /**
   * Set scale percentage for all drones.
   */
  setScale(percent) {
    this._scalePercent = percent;
    for (const drone of this.drones.values()) {
      drone.setScale(percent);
    }
  }

  /**
   * Update all drones. Called each frame.
   */
  updateAll(deltaTime) {
    for (const drone of this.drones.values()) {
      drone.update(deltaTime);
    }
  }

  get size() {
    return this.drones.size;
  }
}
