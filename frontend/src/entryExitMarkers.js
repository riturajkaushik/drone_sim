import * as THREE from 'three';
import { latLonToWorld } from './coordinates.js';

const MARKER_Z = 0.9;
const LABEL_Z = 0.95;

/**
 * Manages entry and exit point markers on the Three.js map.
 * Entry = green filled circle, Exit = red filled circle, both with text labels.
 */
export class EntryExitMarkers {
  constructor(scene) {
    this.scene = scene;
    this._entryPoint = null; // {lat, lon}
    this._exitPoint = null;  // {lat, lon}
    this._entrySprite = null;
    this._exitSprite = null;
    this._entryLabel = null;
    this._exitLabel = null;

    this._entryTexture = this._makeCircleTexture('#22cc44');
    this._exitTexture = this._makeCircleTexture('#ee3333');
  }

  _makeCircleTexture(color) {
    const size = 64;
    const canvas = document.createElement('canvas');
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext('2d');

    // Filled circle
    ctx.beginPath();
    ctx.arc(size / 2, size / 2, size / 2 - 4, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();

    // White border
    ctx.lineWidth = 3;
    ctx.strokeStyle = '#ffffff';
    ctx.stroke();

    return new THREE.CanvasTexture(canvas);
  }

  _makeLabelTexture(text, color) {
    const canvas = document.createElement('canvas');
    canvas.width = 128;
    canvas.height = 48;
    const ctx = canvas.getContext('2d');
    ctx.font = 'bold 28px sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    // Text shadow for readability
    ctx.fillStyle = '#000000';
    ctx.fillText(text, 65, 25);
    ctx.fillStyle = color;
    ctx.fillText(text, 64, 24);

    return new THREE.CanvasTexture(canvas);
  }

  setEntryPoint(lat, lon) {
    this._removeEntry();
    this._entryPoint = { lat, lon };
    const pos = latLonToWorld(lat, lon);

    // Marker sprite
    const mat = new THREE.SpriteMaterial({ map: this._entryTexture, transparent: true });
    this._entrySprite = new THREE.Sprite(mat);
    this._entrySprite.scale.set(0.4, 0.4, 1);
    this._entrySprite.position.set(pos.x, pos.y, MARKER_Z);
    this.scene.add(this._entrySprite);

    // Label sprite
    const labelTex = this._makeLabelTexture('Entry', '#22cc44');
    const labelMat = new THREE.SpriteMaterial({ map: labelTex, transparent: true });
    this._entryLabel = new THREE.Sprite(labelMat);
    this._entryLabel.scale.set(0.8, 0.3, 1);
    this._entryLabel.position.set(pos.x, pos.y + 0.35, LABEL_Z);
    this.scene.add(this._entryLabel);
  }

  setExitPoint(lat, lon) {
    this._removeExit();
    this._exitPoint = { lat, lon };
    const pos = latLonToWorld(lat, lon);

    const mat = new THREE.SpriteMaterial({ map: this._exitTexture, transparent: true });
    this._exitSprite = new THREE.Sprite(mat);
    this._exitSprite.scale.set(0.4, 0.4, 1);
    this._exitSprite.position.set(pos.x, pos.y, MARKER_Z);
    this.scene.add(this._exitSprite);

    const labelTex = this._makeLabelTexture('Exit', '#ee3333');
    const labelMat = new THREE.SpriteMaterial({ map: labelTex, transparent: true });
    this._exitLabel = new THREE.Sprite(labelMat);
    this._exitLabel.scale.set(0.8, 0.3, 1);
    this._exitLabel.position.set(pos.x, pos.y + 0.35, LABEL_Z);
    this.scene.add(this._exitLabel);
  }

  setPoints(entryLat, entryLon, exitLat, exitLon) {
    this.setEntryPoint(entryLat, entryLon);
    this.setExitPoint(exitLat, exitLon);
  }

  getEntryPoint() {
    return this._entryPoint ? { ...this._entryPoint } : null;
  }

  getExitPoint() {
    return this._exitPoint ? { ...this._exitPoint } : null;
  }

  removeAll() {
    this._removeEntry();
    this._removeExit();
  }

  _removeEntry() {
    if (this._entrySprite) {
      this.scene.remove(this._entrySprite);
      this._entrySprite.material.dispose();
      this._entrySprite = null;
    }
    if (this._entryLabel) {
      this.scene.remove(this._entryLabel);
      this._entryLabel.material.map.dispose();
      this._entryLabel.material.dispose();
      this._entryLabel = null;
    }
    this._entryPoint = null;
  }

  _removeExit() {
    if (this._exitSprite) {
      this.scene.remove(this._exitSprite);
      this._exitSprite.material.dispose();
      this._exitSprite = null;
    }
    if (this._exitLabel) {
      this.scene.remove(this._exitLabel);
      this._exitLabel.material.map.dispose();
      this._exitLabel.material.dispose();
      this._exitLabel = null;
    }
    this._exitPoint = null;
  }

  dispose() {
    this.removeAll();
    this._entryTexture.dispose();
    this._exitTexture.dispose();
  }
}
