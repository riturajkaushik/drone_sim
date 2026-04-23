import * as THREE from 'three';
import { createMapPlane, replaceMapPlane } from './mapPlane.js';
import { DroneManager } from './droneManager.js';
import { PolygonOverlay } from './polygonOverlay.js';
import { NavCorridorManager } from './navCorridorManager.js';
import { UI } from './ui.js';
import { WSClient } from './wsClient.js';
import { MAP_WIDTH, MAP_HEIGHT, updateMapConfig, resetMapConfig } from './coordinates.js';
import { MapPicker } from './mapPicker.js';
import { EntryExitMarkers } from './entryExitMarkers.js';
import { saveState, restoreState, clearState } from './statePersistence.js';
import { setDefaultDroneTexture, getDefaultDroneTexture } from './drone.js';
import { exportConfig, importConfig } from './configIO.js';
import { saveLoadedConfig, getLoadedConfig, clearLoadedConfig } from './configStore.js';

// Scene setup
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x1a1a2e);

// Track current asset URLs for export
let _currentMapURL = '/map.png';
let _currentDroneURL = '/drone.png';

// Orthographic camera for 2D top-down view
let viewHeight = MAP_HEIGHT * 1.1;
const aspect = window.innerWidth / window.innerHeight;
let viewWidth = viewHeight * aspect;

const camera = new THREE.OrthographicCamera(
  -viewWidth / 2, viewWidth / 2,
  viewHeight / 2, -viewHeight / 2,
  0.1, 100
);
camera.position.set(0, 0, 10);
camera.lookAt(0, 0, 0);

// Renderer
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(window.devicePixelRatio);
document.getElementById('canvas-container').appendChild(renderer.domElement);

// Create map, drone manager, polygon overlay, corridor manager, and map picker
createMapPlane(scene);
const manager = new DroneManager(scene);
const polygonOverlay = new PolygonOverlay(scene);
const corridorManager = new NavCorridorManager(scene);
const entryExitMarkers = new EntryExitMarkers(scene);
const mapPicker = new MapPicker(camera, renderer.domElement);

// UI
const ui = new UI(manager, polygonOverlay, corridorManager, mapPicker, entryExitMarkers);

// WebSocket client (connects in background, frontend works without it)
const wsClient = new WSClient(manager, ui, polygonOverlay, corridorManager, entryExitMarkers);
wsClient.connect();

/**
 * Resize the camera to match current MAP_WIDTH/MAP_HEIGHT.
 */
function resizeCamera() {
  viewHeight = MAP_HEIGHT * 1.1;
  const asp = window.innerWidth / window.innerHeight;
  viewWidth = viewHeight * asp;
  camera.left = -viewWidth / 2;
  camera.right = viewWidth / 2;
  camera.top = viewHeight / 2;
  camera.bottom = -viewHeight / 2;
  camera.updateProjectionMatrix();
}

// Track load version to prevent stale async callbacks
let _applyVersion = 0;

// Revoke previous object URLs to prevent memory leaks
let _prevMapBlobURL = null;
let _prevDroneBlobURL = null;

function _revokeOldURLs() {
  if (_prevMapBlobURL) { URL.revokeObjectURL(_prevMapBlobURL); _prevMapBlobURL = null; }
  if (_prevDroneBlobURL) { URL.revokeObjectURL(_prevDroneBlobURL); _prevDroneBlobURL = null; }
}

/**
 * Apply a loaded config: update bounds, textures, overlays.
 * Returns a promise that resolves when the config is fully applied.
 */
function applyConfig(config, mapBlobURL, droneBlobURL) {
  // Bump version so any in-flight apply from a prior call is ignored
  const version = ++_applyVersion;

  // Revoke old blob URLs
  _revokeOldURLs();

  // Clear existing scene objects
  manager.removeAll();
  polygonOverlay.remove();
  corridorManager.removeAll();
  entryExitMarkers.removeAll();
  ui.resetAll();
  clearState();

  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      if (version !== _applyVersion) { resolve(); return; } // stale — skip

      const width = img.naturalWidth / 100;
      const height = img.naturalHeight / 100;

      updateMapConfig(config.mapBounds, width, height);
      replaceMapPlane(scene, mapBlobURL);
      resizeCamera();

      // Update drone texture
      setDefaultDroneTexture(droneBlobURL);
      _currentMapURL = mapBlobURL;
      _currentDroneURL = droneBlobURL;
      _prevMapBlobURL = mapBlobURL;
      _prevDroneBlobURL = droneBlobURL;

      // Restore capture area
      if (config.captureArea) {
        manager.setCaptureArea(config.captureArea.x, config.captureArea.y);
        ui.captureXInput.value = config.captureArea.x;
        ui.captureYInput.value = config.captureArea.y;
      }

      // Restore surveillance polygon
      if (config.surveillance && config.surveillance.length > 0) {
        for (const v of config.surveillance) {
          polygonOverlay.addVertex(v.lat, v.lon);
        }
        polygonOverlay.create();
        ui._renderPolygonPointList();
        ui._updatePolyButtons();
      }

      // Restore surveillance entry/exit points
      const survEntry = config.surveillanceEntryPoint
        || (config.entryExitPoints && config.entryExitPoints.entry);  // backward compat
      const survExit = config.surveillanceExitPoint
        || (config.entryExitPoints && config.entryExitPoints.exit);  // backward compat
      if (survEntry && survEntry.lat != null && survEntry.lon != null) {
        entryExitMarkers.setEntryPoint(survEntry.lat, survEntry.lon);
      }
      if (survExit && survExit.lat != null && survExit.lon != null) {
        entryExitMarkers.setExitPoint(survExit.lat, survExit.lon);
      }
      ui._renderEntryExitDisplay();

      // Restore nav corridors (restoreFromState handles entryPoint/exitPoint)
      if (config.navCorridors && config.navCorridors.length > 0) {
        corridorManager.restoreFromState({
          corridors: config.navCorridors,
          nextId: config.navCorridors.length + 1,
        });
        ui._updateCorridorSelect();
        ui._renderCorridorList();
        ui._renderCorridorPointList();
        ui._updateCorridorButtons();
        ui._renderCorridorEntryExitDisplay();
      }

      resolve();
    };
    img.onerror = () => {
      if (version !== _applyVersion) { resolve(); return; }
      reject(new Error('Failed to decode map image'));
    };
    img.src = mapBlobURL;
  });
}

// --- Config buttons ---

document.getElementById('download-config-btn').addEventListener('click', async () => {
  try {
    await exportConfig(manager, polygonOverlay, corridorManager, entryExitMarkers, _currentMapURL, _currentDroneURL);
  } catch (err) {
    console.error('Failed to export config:', err);
    alert('Failed to export configuration: ' + err.message);
  }
});

document.getElementById('load-config-btn').addEventListener('click', () => {
  document.getElementById('config-file-input').click();
});

document.getElementById('config-file-input').addEventListener('change', async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  e.target.value = ''; // reset so same file can be re-selected

  try {
    const { config, mapBlob, droneBlob } = await importConfig(file);
    const mapBlobURL = URL.createObjectURL(mapBlob);
    const droneBlobURL = URL.createObjectURL(droneBlob);

    await applyConfig(config, mapBlobURL, droneBlobURL);
    await saveLoadedConfig(config, mapBlob, droneBlob);
  } catch (err) {
    console.error('Failed to import config:', err);
    alert('Failed to load configuration: ' + err.message);
  }
});

// Restore loaded config from IndexedDB on startup
(async () => {
  try {
    const loaded = await getLoadedConfig();
    if (loaded) {
      await applyConfig(loaded.config, loaded.mapBlobURL, loaded.droneBlobURL);
      return; // skip localStorage restore — loaded config takes precedence
    }
  } catch (err) {
    console.warn('Failed to restore loaded config:', err);
  }

  // Fall back to localStorage state restore
  restoreState(manager, ui, polygonOverlay, corridorManager, entryExitMarkers);
})();

// Reset Simulator button
document.getElementById('reset-sim-btn').addEventListener('click', async () => {
  _applyVersion++; // cancel any in-flight applyConfig
  _revokeOldURLs();

  manager.removeAll();
  polygonOverlay.remove();
  corridorManager.removeAll();
  entryExitMarkers.removeAll();
  ui.resetAll();
  clearState();

  // Clear loaded config and restore defaults
  try {
    await clearLoadedConfig();
  } catch (err) {
    console.warn('Failed to clear loaded config:', err);
  }

  // Reset to default map/drone
  resetMapConfig();
  replaceMapPlane(scene, '/map.png');
  setDefaultDroneTexture('/drone.png');
  _currentMapURL = '/map.png';
  _currentDroneURL = '/drone.png';
  resizeCamera();

  wsClient.send({ type: 'reset_sim' });
});

// Auto-save state periodically and on page unload
let _saveTimer = null;
function scheduleSave() {
  if (_saveTimer) return;
  _saveTimer = setTimeout(() => {
    _saveTimer = null;
    saveState(manager, ui, polygonOverlay, corridorManager, entryExitMarkers);
  }, 1000);
}
window.addEventListener('beforeunload', () => saveState(manager, ui, polygonOverlay, corridorManager, entryExitMarkers));

// Animation loop
const clock = new THREE.Clock();

function animate() {
  requestAnimationFrame(animate);

  const dt = clock.getDelta();
  manager.updateAll(dt);

  // Continuously update status display
  ui.updateStatus();

  // Throttled auto-save (every ~1s)
  scheduleSave();

  renderer.render(scene, camera);
}

animate();

// Handle window resize
window.addEventListener('resize', () => {
  const newAspect = window.innerWidth / window.innerHeight;
  const newViewWidth = viewHeight * newAspect;

  camera.left = -newViewWidth / 2;
  camera.right = newViewWidth / 2;
  camera.top = viewHeight / 2;
  camera.bottom = -viewHeight / 2;
  camera.updateProjectionMatrix();

  renderer.setSize(window.innerWidth, window.innerHeight);
});
