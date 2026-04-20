import * as THREE from 'three';
import { latLonToWorld, worldToLatLon, metersToWorldX, metersToWorldY } from './coordinates.js';

const ARRIVAL_THRESHOLD = 0.05; // world units

// Colors for distinguishing multiple drones
const DRONE_COLORS = [
  0x4a9eff, 0x22aa44, 0xff6644, 0xaa44ff, 0xffaa00,
  0x00cccc, 0xff44aa, 0x88cc00, 0x6644ff, 0xff8800,
];
let colorIndex = 0;

export class Drone {
  constructor(scene, id, lat = 60.1620, lon = 24.8900) {
    this.id = id;
    this.scene = scene;
    this.lat = lat;
    this.lon = lon;
    this.speed = 10.0;
    this.isFlying = false;
    this.waypoints = [];
    this.currentWaypointIndex = -1;
    this.targetWorld = null;
    this.color = DRONE_COLORS[colorIndex++ % DRONE_COLORS.length];

    this.onWaypointReached = null;
    this.onStatusChanged = null;

    // Create drone sprite
    const loader = new THREE.TextureLoader();
    const texture = loader.load('/drone.png');
    texture.colorSpace = THREE.SRGBColorSpace;

    const material = new THREE.SpriteMaterial({ map: texture, transparent: true });
    this.sprite = new THREE.Sprite(material);
    this._baseScale = 1.2;
    this._scalePercent = 100;
    this.sprite.scale.set(this._baseScale, this._baseScale, 1);

    const pos = latLonToWorld(this.lat, this.lon);
    this.sprite.position.set(pos.x, pos.y, 1);
    scene.add(this.sprite);

    // Capture area bounding box (initially invisible)
    this._captureBox = null;
    this._captureWidthWorld = 0;
    this._captureHeightWorld = 0;


  }

  setCaptureArea(widthMeters, heightMeters) {
    // Remove old box if exists
    if (this._captureBox) {
      this.scene.remove(this._captureBox);
      this._captureBox.geometry.dispose();
      this._captureBox.material.dispose();
      this._captureBox = null;
    }

    this._captureWidthWorld = metersToWorldX(widthMeters);
    this._captureHeightWorld = metersToWorldY(heightMeters);

    if (widthMeters <= 0 || heightMeters <= 0) return;

    const hw = this._captureWidthWorld / 2;
    const hh = this._captureHeightWorld / 2;

    const points = [
      new THREE.Vector3(-hw, -hh, 1.5),
      new THREE.Vector3( hw, -hh, 1.5),
      new THREE.Vector3( hw,  hh, 1.5),
      new THREE.Vector3(-hw,  hh, 1.5),
    ];

    const geometry = new THREE.BufferGeometry().setFromPoints(points);
    const material = new THREE.LineBasicMaterial({
      color: this.color,
      linewidth: 1,
      transparent: true,
      opacity: 0.7,
    });
    this._captureBox = new THREE.LineLoop(geometry, material);
    this._captureBox.position.set(
      this.sprite.position.x,
      this.sprite.position.y,
      0,
    );
    this.scene.add(this._captureBox);
  }

  /**
   * Scale the drone sprite by a percentage (100 = default size).
   */
  setScale(percent) {
    this._scalePercent = Math.max(10, Math.min(500, percent));
    const s = this._baseScale * (this._scalePercent / 100);
    this.sprite.scale.set(s, s, 1);
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
      id: this.id,
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
      this.sprite.position.x = targetX;
      this.sprite.position.y = targetY;

      const latLon = worldToLatLon(targetX, targetY);
      this.lat = latLon.lat;
      this.lon = latLon.lon;

      const reachedWp = this.waypoints[this.currentWaypointIndex];
      const reachedIdx = this.currentWaypointIndex;

      if (this.onWaypointReached) {
        this.onWaypointReached(reachedWp, reachedIdx);
      }

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
      this._updateCaptureBoxPosition();
      return;
    }

    const worldSpeed = this.speed * 0.01;
    const step = worldSpeed * deltaTime;
    const ratio = Math.min(step / distance, 1);

    this.sprite.position.x += dx * ratio;
    this.sprite.position.y += dy * ratio;

    const latLon = worldToLatLon(this.sprite.position.x, this.sprite.position.y);
    this.lat = latLon.lat;
    this.lon = latLon.lon;

    this._updateCaptureBoxPosition();
  }

  _updateCaptureBoxPosition() {
    if (this._captureBox) {
      this._captureBox.position.set(
        this.sprite.position.x,
        this.sprite.position.y,
        0,
      );
    }
  }

  dispose() {
    this.scene.remove(this.sprite);
    this.sprite.material.dispose();

    if (this._captureBox) {
      this.scene.remove(this._captureBox);
      this._captureBox.geometry.dispose();
      this._captureBox.material.dispose();
    }
  }

  _notifyStatusChanged() {
    if (this.onStatusChanged) {
      this.onStatusChanged(this.getStatus());
    }
  }
}
