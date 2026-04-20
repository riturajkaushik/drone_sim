import * as THREE from 'three';
import { latLonToWorld, worldToLatLon, metersToWorldX, metersToWorldY } from './coordinates.js';

const ARRIVAL_THRESHOLD = 0.005; // world units — small enough to avoid visible snap

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

    // ID label above the drone
    this._label = this._createLabel(id);
    this._label.position.set(pos.x, pos.y + this._baseScale * 0.6, 2);
    scene.add(this._label);
  }

  _createLabel(text) {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    canvas.width = 256;
    canvas.height = 64;

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.font = 'bold 36px sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    // Outline for readability
    ctx.strokeStyle = 'rgba(0, 0, 0, 0.8)';
    ctx.lineWidth = 4;
    ctx.strokeText(text, canvas.width / 2, canvas.height / 2);
    ctx.fillStyle = '#ffffff';
    ctx.fillText(text, canvas.width / 2, canvas.height / 2);

    const texture = new THREE.CanvasTexture(canvas);
    const material = new THREE.SpriteMaterial({ map: texture, transparent: true });
    const sprite = new THREE.Sprite(material);
    sprite.scale.set(1.2, 0.3, 1);
    return sprite;
  }

  setCaptureArea(widthMeters, heightMeters) {
    if (this._captureBox) {
      this.scene.remove(this._captureBox);
      this._captureBox.material.map.dispose();
      this._captureBox.material.dispose();
      this._captureBox.geometry.dispose();
      this._captureBox = null;
    }

    this._captureWidthWorld = metersToWorldX(widthMeters);
    this._captureHeightWorld = metersToWorldY(heightMeters);

    if (widthMeters <= 0 || heightMeters <= 0) return;

    const canvasSize = 256;
    const canvas = document.createElement('canvas');
    canvas.width = canvasSize;
    canvas.height = canvasSize;
    const ctx = canvas.getContext('2d');

    const margin = 8;
    const radius = 14;

    // Rounded-corner border only
    const colorHex = '#' + this.color.toString(16).padStart(6, '0');
    ctx.strokeStyle = colorHex;
    ctx.lineWidth = 4;
    ctx.globalAlpha = 0.8;
    ctx.beginPath();
    ctx.roundRect(margin, margin, canvasSize - margin * 2, canvasSize - margin * 2, radius);
    ctx.stroke();

    const texture = new THREE.CanvasTexture(canvas);
    const geometry = new THREE.PlaneGeometry(this._captureWidthWorld, this._captureHeightWorld);
    const material = new THREE.MeshBasicMaterial({
      map: texture,
      transparent: true,
      depthWrite: false,
    });

    this._captureBox = new THREE.Mesh(geometry, material);
    this._captureBox.position.set(this.sprite.position.x, this.sprite.position.y, 0.5);
    this.scene.add(this._captureBox);
  }

  /**
   * Scale the drone sprite by a percentage (100 = default size).
   */
  setScale(percent) {
    this._scalePercent = Math.max(10, Math.min(500, percent));
    const s = this._baseScale * (this._scalePercent / 100);
    this.sprite.scale.set(s, s, 1);
    this._updateLabelPosition();
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
        0.5,
      );
    }
    this._updateLabelPosition();
  }

  _updateLabelPosition() {
    const s = this._baseScale * (this._scalePercent / 100);
    this._label.position.set(
      this.sprite.position.x,
      this.sprite.position.y + s * 0.6,
      2,
    );
  }

  dispose() {
    this.scene.remove(this.sprite);
    this.sprite.material.dispose();

    this.scene.remove(this._label);
    this._label.material.map.dispose();
    this._label.material.dispose();

    if (this._captureBox) {
      this.scene.remove(this._captureBox);
      this._captureBox.material.map.dispose();
      this._captureBox.material.dispose();
      this._captureBox.geometry.dispose();
    }
  }

  _notifyStatusChanged() {
    if (this.onStatusChanged) {
      this.onStatusChanged(this.getStatus());
    }
  }
}
