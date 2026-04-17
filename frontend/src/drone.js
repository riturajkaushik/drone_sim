import * as THREE from 'three';
import { latLonToWorld, worldToLatLon } from './coordinates.js';

const ARRIVAL_THRESHOLD = 0.05; // world units

export class Drone {
  constructor(scene) {
    this.lat = 60.1620;
    this.lon = 24.8900;
    this.speed = 10.0; // m/s (1 world unit ≈ 100m for this map scale)
    this.isFlying = false;
    this.waypoints = [];        // [{lat, lon}, ...]
    this.currentWaypointIndex = -1;
    this.targetWorld = null;

    this.onWaypointReached = null; // callback(waypoint, index)
    this.onStatusChanged = null;   // callback(status)

    // Create drone sprite
    const loader = new THREE.TextureLoader();
    const texture = loader.load('/drone.webp');
    texture.colorSpace = THREE.SRGBColorSpace;

    const material = new THREE.SpriteMaterial({ map: texture });
    this.sprite = new THREE.Sprite(material);
    this.sprite.scale.set(1.2, 1.2, 1);

    // Set initial position
    const pos = latLonToWorld(this.lat, this.lon);
    this.sprite.position.set(pos.x, pos.y, 1); // z=1 to be above the map

    scene.add(this.sprite);
  }

  setTarget(lat, lon) {
    this.waypoints = [{ lat, lon }];
    this.currentWaypointIndex = 0;
    this.targetWorld = latLonToWorld(lat, lon);
    this.isFlying = true;
    this._notifyStatusChanged();
  }

  setWaypoints(waypoints) {
    if (!waypoints || waypoints.length === 0) return;
    this.waypoints = [...waypoints];
    this.currentWaypointIndex = 0;
    this.targetWorld = latLonToWorld(waypoints[0].lat, waypoints[0].lon);
    this.isFlying = true;
    this._notifyStatusChanged();
  }

  setSpeed(speed) {
    this.speed = Math.max(1, Math.min(100, speed));
    this._notifyStatusChanged();
  }

  getStatus() {
    return {
      lat: this.lat,
      lon: this.lon,
      speed: this.speed,
      is_flying: this.isFlying,
      current_waypoint_index: this.currentWaypointIndex,
      waypoints: this.waypoints,
    };
  }

  update(deltaTime) {
    if (!this.isFlying || !this.targetWorld) return;

    const currentX = this.sprite.position.x;
    const currentY = this.sprite.position.y;
    const targetX = this.targetWorld.x;
    const targetY = this.targetWorld.y;

    const dx = targetX - currentX;
    const dy = targetY - currentY;
    const distance = Math.sqrt(dx * dx + dy * dy);

    if (distance < ARRIVAL_THRESHOLD) {
      // Arrived at waypoint
      this.sprite.position.x = targetX;
      this.sprite.position.y = targetY;

      const latLon = worldToLatLon(targetX, targetY);
      this.lat = latLon.lat;
      this.lon = latLon.lon;

      const reachedWp = this.waypoints[this.currentWaypointIndex];
      const reachedIdx = this.currentWaypointIndex;

      // Fire callback
      if (this.onWaypointReached) {
        this.onWaypointReached(reachedWp, reachedIdx);
      }

      // Move to next waypoint or stop
      if (this.currentWaypointIndex < this.waypoints.length - 1) {
        this.currentWaypointIndex++;
        const next = this.waypoints[this.currentWaypointIndex];
        this.targetWorld = latLonToWorld(next.lat, next.lon);
      } else {
        this.isFlying = false;
        this.targetWorld = null;
        this.currentWaypointIndex = -1;
      }

      this._notifyStatusChanged();
      return;
    }

    // Move toward target
    // Speed is in m/s; 1 world unit ≈ map_width / (lon_range * ~70km at this latitude)
    // For simplicity: speed slider value maps to world units/second with a scaling factor
    const worldSpeed = this.speed * 0.01; // tunable scaling factor
    const step = worldSpeed * deltaTime;
    const ratio = Math.min(step / distance, 1);

    this.sprite.position.x += dx * ratio;
    this.sprite.position.y += dy * ratio;

    // Update lat/lon
    const latLon = worldToLatLon(this.sprite.position.x, this.sprite.position.y);
    this.lat = latLon.lat;
    this.lon = latLon.lon;
  }

  _notifyStatusChanged() {
    if (this.onStatusChanged) {
      this.onStatusChanged(this.getStatus());
    }
  }
}
