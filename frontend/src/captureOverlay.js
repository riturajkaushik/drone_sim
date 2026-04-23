import * as THREE from 'three';
import { MAP_WIDTH, MAP_HEIGHT } from './coordinates.js';

/**
 * Renders a canvas-backed overlay on the map showing areas captured by drone cameras.
 * Dots are painted onto an off-screen canvas as drones move, then displayed via a
 * PlaneGeometry textured with that canvas.
 */
export class CaptureOverlay {
  constructor(scene) {
    this.scene = scene;

    // Canvas resolution — proportional to map aspect ratio
    this._canvasWidth = 2048;
    this._canvasHeight = Math.round(2048 * (MAP_HEIGHT / MAP_WIDTH));

    this._canvas = document.createElement('canvas');
    this._canvas.width = this._canvasWidth;
    this._canvas.height = this._canvasHeight;
    this._ctx = this._canvas.getContext('2d');

    this._texture = new THREE.CanvasTexture(this._canvas);
    this._texture.minFilter = THREE.LinearFilter;
    this._texture.magFilter = THREE.LinearFilter;

    const geometry = new THREE.PlaneGeometry(MAP_WIDTH, MAP_HEIGHT);
    const material = new THREE.MeshBasicMaterial({
      map: this._texture,
      transparent: true,
      depthWrite: false,
    });

    this._mesh = new THREE.Mesh(geometry, material);
    this._mesh.position.set(0, 0, 0.3);
    scene.add(this._mesh);

    this._dirty = false;
  }

  /**
   * Paint a grid of dots onto the canvas for the capture area at the given world position.
   * @param {number} worldX - drone world X
   * @param {number} worldY - drone world Y
   * @param {number} captureW - capture area width in world units
   * @param {number} captureH - capture area height in world units
   * @param {number} color - hex color (e.g. 0x4a9eff)
   */
  stampDots(worldX, worldY, captureW, captureH, color) {
    const ctx = this._ctx;
    const cw = this._canvasWidth;
    const ch = this._canvasHeight;

    // World → canvas pixel mapping
    // World origin (0,0) is center of map. Canvas (0,0) is top-left.
    const worldToCanvasX = (wx) => ((wx / MAP_WIDTH) + 0.5) * cw;
    const worldToCanvasY = (wy) => ((-wy / MAP_HEIGHT) + 0.5) * ch;

    const cx = worldToCanvasX(worldX);
    const cy = worldToCanvasY(worldY);
    const halfW = (captureW / MAP_WIDTH) * cw * 0.5;
    const halfH = (captureH / MAP_HEIGHT) * ch * 0.5;

    // Dot grid parameters
    const dotSpacing = Math.max(halfW, halfH) * 0.12; // dense spacing
    const dotRadius = Math.max(1, dotSpacing * 0.12);  // small dots

    ctx.fillStyle = '#404040';
    ctx.globalAlpha = 1.0;

    const startX = cx - halfW;
    const endX = cx + halfW;
    const startY = cy - halfH;
    const endY = cy + halfH;

    for (let x = startX; x <= endX; x += dotSpacing) {
      for (let y = startY; y <= endY; y += dotSpacing) {
        ctx.beginPath();
        ctx.arc(x, y, dotRadius, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    this._dirty = true;
  }

  /**
   * Call once per frame to upload the canvas texture if it changed.
   */
  updateTexture() {
    if (this._dirty) {
      this._texture.needsUpdate = true;
      this._dirty = false;
    }
  }

  /**
   * Clear all painted dots.
   */
  clear() {
    this._ctx.clearRect(0, 0, this._canvasWidth, this._canvasHeight);
    this._texture.needsUpdate = true;
  }

  /**
   * Rebuild the overlay plane after map dimensions change.
   */
  rebuild() {
    this.scene.remove(this._mesh);
    this._mesh.geometry.dispose();
    this._mesh.material.dispose();
    this._texture.dispose();

    this._canvasHeight = Math.round(2048 * (MAP_HEIGHT / MAP_WIDTH));
    this._canvas.width = this._canvasWidth;
    this._canvas.height = this._canvasHeight;
    this._ctx = this._canvas.getContext('2d');

    this._texture = new THREE.CanvasTexture(this._canvas);
    this._texture.minFilter = THREE.LinearFilter;
    this._texture.magFilter = THREE.LinearFilter;

    const geometry = new THREE.PlaneGeometry(MAP_WIDTH, MAP_HEIGHT);
    const material = new THREE.MeshBasicMaterial({
      map: this._texture,
      transparent: true,
      depthWrite: false,
    });

    this._mesh = new THREE.Mesh(geometry, material);
    this._mesh.position.set(0, 0, 0.3);
    this.scene.add(this._mesh);
  }

  dispose() {
    this.scene.remove(this._mesh);
    this._mesh.geometry.dispose();
    this._mesh.material.dispose();
    this._texture.dispose();
  }
}
