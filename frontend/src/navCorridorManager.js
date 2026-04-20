import { PolygonOverlay } from './polygonOverlay.js';

const CORRIDOR_COLOR = 0x00cccc;

/**
 * Manages multiple Nav Corridor polygon overlays.
 */
export class NavCorridorManager {
  constructor(scene) {
    this.scene = scene;
    this._corridors = new Map(); // id → { id, overlay }
    this._nextId = 1;
  }

  addCorridor() {
    const id = `corridor-${this._nextId++}`;
    const overlay = new PolygonOverlay(this.scene, { color: CORRIDOR_COLOR });
    this._corridors.set(id, { id, overlay });
    return { id, overlay };
  }

  removeCorridor(id) {
    const entry = this._corridors.get(id);
    if (!entry) return false;
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

  getState() {
    const corridors = [];
    for (const { id, overlay } of this._corridors.values()) {
      corridors.push({
        id,
        vertices: overlay.getVertices(),
        created: overlay.isCreated(),
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
      this._corridors.set(c.id, { id: c.id, overlay });
    }
  }

  get size() {
    return this._corridors.size;
  }
}
