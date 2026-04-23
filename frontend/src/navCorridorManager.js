import * as THREE from 'three';
import { PolygonOverlay } from './polygonOverlay.js';
import { latLonToWorld } from './coordinates.js';

const CORRIDOR_COLOR = 0x00cccc;
const MARKER_Z = 0.9;
const LABEL_Z = 0.95;
const ENTRY_COLOR = '#11bbaa';
const EXIT_COLOR = '#dd7722';

/**
 * Manages multiple Nav Corridor polygon overlays, each with optional entry/exit points.
 */
export class NavCorridorManager {
  constructor(scene) {
    this.scene = scene;
    this._corridors = new Map(); // id → { id, overlay, entryPoint, exitPoint, _entrySprite, _entryLabel, _exitSprite, _exitLabel }
    this._nextId = 1;
    this._entryTexture = this._makeCircleTexture(ENTRY_COLOR);
    this._exitTexture = this._makeCircleTexture(EXIT_COLOR);
  }

  _makeCircleTexture(color) {
    const size = 64;
    const canvas = document.createElement('canvas');
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext('2d');
    ctx.beginPath();
    ctx.arc(size / 2, size / 2, size / 2 - 4, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
    ctx.lineWidth = 3;
    ctx.strokeStyle = '#ffffff';
    ctx.stroke();
    return new THREE.CanvasTexture(canvas);
  }

  _makeLabelTexture(text, color) {
    const canvas = document.createElement('canvas');
    canvas.width = 256;
    canvas.height = 48;
    const ctx = canvas.getContext('2d');
    ctx.font = 'bold 22px sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = '#000000';
    ctx.fillText(text, 129, 25);
    ctx.fillStyle = color;
    ctx.fillText(text, 128, 24);
    return new THREE.CanvasTexture(canvas);
  }

  addCorridor() {
    const id = `corridor-${this._nextId++}`;
    const overlay = new PolygonOverlay(this.scene, { color: CORRIDOR_COLOR });
    this._corridors.set(id, {
      id, overlay,
      entryPoint: null, exitPoint: null,
      _entrySprite: null, _entryLabel: null,
      _exitSprite: null, _exitLabel: null,
    });
    return { id, overlay };
  }

  removeCorridor(id) {
    const entry = this._corridors.get(id);
    if (!entry) return false;
    this._removeMarker(entry, 'entry');
    this._removeMarker(entry, 'exit');
    entry.overlay.dispose();
    this._corridors.delete(id);
    return true;
  }

  getCorridor(id) {
    return this._corridors.get(id) || null;
  }

  getAllCorridors() {
    return Array.from(this._corridors.values());
  }

  // --- Entry/Exit per corridor ---

  setCorridorEntryPoint(id, lat, lon) {
    const c = this._corridors.get(id);
    if (!c) return;
    this._removeMarker(c, 'entry');
    c.entryPoint = { lat, lon };
    const pos = latLonToWorld(lat, lon);

    const mat = new THREE.SpriteMaterial({ map: this._entryTexture, transparent: true });
    c._entrySprite = new THREE.Sprite(mat);
    c._entrySprite.scale.set(0.35, 0.35, 1);
    c._entrySprite.position.set(pos.x, pos.y, MARKER_Z);
    this.scene.add(c._entrySprite);

    const labelTex = this._makeLabelTexture(`Entry: ${id}`, ENTRY_COLOR);
    const labelMat = new THREE.SpriteMaterial({ map: labelTex, transparent: true });
    c._entryLabel = new THREE.Sprite(labelMat);
    c._entryLabel.scale.set(1.2, 0.25, 1);
    c._entryLabel.position.set(pos.x, pos.y + 0.3, LABEL_Z);
    this.scene.add(c._entryLabel);
  }

  setCorridorExitPoint(id, lat, lon) {
    const c = this._corridors.get(id);
    if (!c) return;
    this._removeMarker(c, 'exit');
    c.exitPoint = { lat, lon };
    const pos = latLonToWorld(lat, lon);

    const mat = new THREE.SpriteMaterial({ map: this._exitTexture, transparent: true });
    c._exitSprite = new THREE.Sprite(mat);
    c._exitSprite.scale.set(0.35, 0.35, 1);
    c._exitSprite.position.set(pos.x, pos.y, MARKER_Z);
    this.scene.add(c._exitSprite);

    const labelTex = this._makeLabelTexture(`Exit: ${id}`, EXIT_COLOR);
    const labelMat = new THREE.SpriteMaterial({ map: labelTex, transparent: true });
    c._exitLabel = new THREE.Sprite(labelMat);
    c._exitLabel.scale.set(1.2, 0.25, 1);
    c._exitLabel.position.set(pos.x, pos.y + 0.3, LABEL_Z);
    this.scene.add(c._exitLabel);
  }

  getCorridorEntryPoint(id) {
    const c = this._corridors.get(id);
    return c && c.entryPoint ? { ...c.entryPoint } : null;
  }

  getCorridorExitPoint(id) {
    const c = this._corridors.get(id);
    return c && c.exitPoint ? { ...c.exitPoint } : null;
  }

  clearCorridorEntryExit(id) {
    const c = this._corridors.get(id);
    if (!c) return;
    this._removeMarker(c, 'entry');
    this._removeMarker(c, 'exit');
    c.entryPoint = null;
    c.exitPoint = null;
  }

  _removeMarker(c, type) {
    const spriteKey = `_${type}Sprite`;
    const labelKey = `_${type}Label`;
    if (c[spriteKey]) {
      this.scene.remove(c[spriteKey]);
      c[spriteKey].material.dispose();
      c[spriteKey] = null;
    }
    if (c[labelKey]) {
      this.scene.remove(c[labelKey]);
      c[labelKey].material.map.dispose();
      c[labelKey].material.dispose();
      c[labelKey] = null;
    }
    if (type === 'entry') c.entryPoint = null;
    if (type === 'exit') c.exitPoint = null;
  }

  // --- State serialization ---

  getState() {
    const corridors = [];
    for (const c of this._corridors.values()) {
      corridors.push({
        id: c.id,
        vertices: c.overlay.getVertices(),
        created: c.overlay.isCreated(),
        entryPoint: c.entryPoint ? { ...c.entryPoint } : null,
        exitPoint: c.exitPoint ? { ...c.exitPoint } : null,
      });
    }
    return { corridors, nextId: this._nextId };
  }

  restoreFromState(data) {
    if (!data || !data.corridors) return;
    if (data.nextId) this._nextId = data.nextId;
    for (const c of data.corridors) {
      const overlay = new PolygonOverlay(this.scene, { color: CORRIDOR_COLOR });
      for (const v of c.vertices) {
        overlay.addVertex(v.lat, v.lon);
      }
      if (c.created) {
        overlay.create();
      }
      this._corridors.set(c.id, {
        id: c.id, overlay,
        entryPoint: null, exitPoint: null,
        _entrySprite: null, _entryLabel: null,
        _exitSprite: null, _exitLabel: null,
      });
      // Restore entry/exit markers
      if (c.entryPoint && c.entryPoint.lat != null) {
        this.setCorridorEntryPoint(c.id, c.entryPoint.lat, c.entryPoint.lon);
      }
      if (c.exitPoint && c.exitPoint.lat != null) {
        this.setCorridorExitPoint(c.id, c.exitPoint.lat, c.exitPoint.lon);
      }
    }
  }

  removeAll() {
    for (const entry of this._corridors.values()) {
      this._removeMarker(entry, 'entry');
      this._removeMarker(entry, 'exit');
      entry.overlay.dispose();
    }
    this._corridors.clear();
    this._nextId = 1;
  }

  get size() {
    return this._corridors.size;
  }

  dispose() {
    this.removeAll();
    this._entryTexture.dispose();
    this._exitTexture.dispose();
  }
}
