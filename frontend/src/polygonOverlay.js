import * as THREE from 'three';
import { latLonToWorld } from './coordinates.js';

const DEFAULT_COLOR = 0xff6644;
const VERTEX_Z = 0.8;
const LINE_Z = 0.7;
const FILL_Z = 0.3;

/**
 * Manages a user-drawn polygon overlay on the Three.js map.
 * Supports adding/removing vertices, rendering a preview (dots + dashed lines),
 * and finalizing into a filled polygon.
 */
export class PolygonOverlay {
  constructor(scene, options = {}) {
    this.scene = scene;
    this.vertices = []; // [{lat, lon}]
    this._created = false;

    this._color = options.color ?? DEFAULT_COLOR;
    this._colorHex = '#' + this._color.toString(16).padStart(6, '0');

    // Three.js objects
    this._dotSprites = [];   // one per vertex
    this._previewLine = null; // dashed line connecting vertices
    this._fillMesh = null;    // filled polygon after create()
    this._borderLine = null;  // solid border after create()

    // Shared dot texture
    this._dotTexture = this._makeDotTexture();
  }

  _makeDotTexture() {
    const size = 64;
    const canvas = document.createElement('canvas');
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext('2d');
    ctx.beginPath();
    ctx.arc(size / 2, size / 2, size / 2 - 2, 0, Math.PI * 2);
    ctx.fillStyle = this._colorHex;
    ctx.fill();
    const texture = new THREE.CanvasTexture(canvas);
    return texture;
  }

  /**
   * Add a vertex and update the preview rendering.
   */
  addVertex(lat, lon) {
    this.vertices.push({ lat, lon });
    this._addDot(lat, lon);
    this._updatePreviewLine();
    return this.vertices.length;
  }

  /**
   * Remove a vertex by index and update the preview.
   */
  removeVertex(index) {
    if (index < 0 || index >= this.vertices.length) return;
    this.vertices.splice(index, 1);

    // Remove and dispose the dot sprite
    const dot = this._dotSprites.splice(index, 1)[0];
    if (dot) {
      this.scene.remove(dot);
      dot.material.dispose();
    }

    this._updatePreviewLine();
  }

  /**
   * Finalize the polygon: render fill + solid border, hide preview line.
   */
  create() {
    if (this.vertices.length < 3) return false;

    this._removePreviewLine();
    this._removeFill();

    // Build shape from world coordinates
    const worldPts = this.vertices.map(v => latLonToWorld(v.lat, v.lon));
    const shape = new THREE.Shape();
    shape.moveTo(worldPts[0].x, worldPts[0].y);
    for (let i = 1; i < worldPts.length; i++) {
      shape.lineTo(worldPts[i].x, worldPts[i].y);
    }
    shape.closePath();

    // Filled mesh
    const geometry = new THREE.ShapeGeometry(shape);
    const material = new THREE.MeshBasicMaterial({
      color: this._color,
      transparent: true,
      opacity: 0.2,
      side: THREE.DoubleSide,
      depthWrite: false,
    });
    this._fillMesh = new THREE.Mesh(geometry, material);
    this._fillMesh.position.z = FILL_Z;
    this.scene.add(this._fillMesh);

    // Solid border
    const borderPts = [...worldPts, worldPts[0]].map(p => new THREE.Vector3(p.x, p.y, LINE_Z));
    const borderGeom = new THREE.BufferGeometry().setFromPoints(borderPts);
    const borderMat = new THREE.LineBasicMaterial({ color: this._color, linewidth: 2 });
    this._borderLine = new THREE.Line(borderGeom, borderMat);
    this.scene.add(this._borderLine);

    this._created = true;
    return true;
  }

  /**
   * Remove everything: dots, lines, fill. Reset state.
   */
  remove() {
    // Dots
    for (const dot of this._dotSprites) {
      this.scene.remove(dot);
      dot.material.dispose();
    }
    this._dotSprites = [];

    this._removePreviewLine();
    this._removeFill();

    this.vertices = [];
    this._created = false;
  }

  getVertices() {
    return this.vertices.map(v => ({ ...v }));
  }

  isCreated() {
    return this._created;
  }

  // --- Private helpers ---

  _addDot(lat, lon) {
    const pos = latLonToWorld(lat, lon);
    const material = new THREE.SpriteMaterial({
      map: this._dotTexture,
      transparent: true,
    });
    const sprite = new THREE.Sprite(material);
    sprite.scale.set(0.25, 0.25, 1);
    sprite.position.set(pos.x, pos.y, VERTEX_Z);
    this.scene.add(sprite);
    this._dotSprites.push(sprite);
  }

  _updatePreviewLine() {
    this._removePreviewLine();
    if (this.vertices.length < 2) return;

    const pts = this.vertices.map(v => {
      const w = latLonToWorld(v.lat, v.lon);
      return new THREE.Vector3(w.x, w.y, LINE_Z);
    });

    const geometry = new THREE.BufferGeometry().setFromPoints(pts);
    const material = new THREE.LineDashedMaterial({
      color: this._color,
      dashSize: 0.15,
      gapSize: 0.1,
      linewidth: 1,
    });
    this._previewLine = new THREE.Line(geometry, material);
    this._previewLine.computeLineDistances();
    this.scene.add(this._previewLine);
  }

  _removePreviewLine() {
    if (this._previewLine) {
      this.scene.remove(this._previewLine);
      this._previewLine.geometry.dispose();
      this._previewLine.material.dispose();
      this._previewLine = null;
    }
  }

  _removeFill() {
    if (this._fillMesh) {
      this.scene.remove(this._fillMesh);
      this._fillMesh.geometry.dispose();
      this._fillMesh.material.dispose();
      this._fillMesh = null;
    }
    if (this._borderLine) {
      this.scene.remove(this._borderLine);
      this._borderLine.geometry.dispose();
      this._borderLine.material.dispose();
      this._borderLine = null;
    }
  }

  dispose() {
    this.remove();
    this._dotTexture.dispose();
  }
}
