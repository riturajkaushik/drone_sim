import { worldToLatLon } from './coordinates.js';

/**
 * MapPicker — dropper/picker tool for selecting lat/lon points by clicking
 * on the map canvas. Shows a floating tooltip with lat/lon near the cursor.
 */
export class MapPicker {
  constructor(camera, canvas) {
    this._camera = camera;
    this._canvas = canvas;
    this._active = false;
    this._callback = null; // (lat, lon) => void
    this._onDeactivate = null;

    // Tooltip element
    this._tooltip = document.getElementById('picker-tooltip');

    // Bind handlers so we can add/remove them
    this._onMouseMove = this._handleMouseMove.bind(this);
    this._onMouseClick = this._handleClick.bind(this);
    this._onKeyDown = this._handleKeyDown.bind(this);
  }

  /**
   * Activate dropper mode.
   * @param {function(lat, lon)} callback - called on each map click
   * @param {function} [onDeactivate] - called when dropper is deactivated
   */
  activate(callback, onDeactivate) {
    if (this._active) this.deactivate();

    this._active = true;
    this._callback = callback;
    this._onDeactivate = onDeactivate || null;

    this._canvas.style.cursor = 'crosshair';
    this._canvas.addEventListener('mousemove', this._onMouseMove);
    this._canvas.addEventListener('click', this._onMouseClick);
    document.addEventListener('keydown', this._onKeyDown);
  }

  deactivate() {
    if (!this._active) return;
    this._active = false;

    this._canvas.style.cursor = '';
    this._canvas.removeEventListener('mousemove', this._onMouseMove);
    this._canvas.removeEventListener('click', this._onMouseClick);
    document.removeEventListener('keydown', this._onKeyDown);

    this._tooltip.style.display = 'none';
    this._callback = null;

    if (this._onDeactivate) {
      const cb = this._onDeactivate;
      this._onDeactivate = null;
      cb();
    }
  }

  isActive() {
    return this._active;
  }

  /**
   * Convert a mouse event on the canvas to lat/lon.
   */
  _screenToLatLon(event) {
    const rect = this._canvas.getBoundingClientRect();
    // Normalized device coordinates (-1 to +1)
    const ndcX = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    const ndcY = -(((event.clientY - rect.top) / rect.height) * 2 - 1);

    const cam = this._camera;
    const worldX = ndcX * (cam.right - cam.left) / 2 + (cam.right + cam.left) / 2;
    const worldY = ndcY * (cam.top - cam.bottom) / 2 + (cam.top + cam.bottom) / 2;

    return worldToLatLon(worldX, worldY);
  }

  _handleMouseMove(event) {
    const { lat, lon } = this._screenToLatLon(event);

    this._tooltip.textContent = `${lat.toFixed(4)}, ${lon.toFixed(4)}`;
    this._tooltip.style.display = 'block';
    this._tooltip.style.left = `${event.clientX + 16}px`;
    this._tooltip.style.top = `${event.clientY - 10}px`;
  }

  _handleClick(event) {
    // Ignore if click somehow reaches control panel area
    if (event.target.closest('#control-panel')) return;

    const { lat, lon } = this._screenToLatLon(event);
    if (this._callback) {
      this._callback(lat, lon);
    }
  }

  _handleKeyDown(event) {
    if (event.key === 'Escape') {
      this.deactivate();
    }
  }
}
