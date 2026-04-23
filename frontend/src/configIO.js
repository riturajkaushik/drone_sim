import JSZip from 'jszip';
import { getMapBounds } from './coordinates.js';

/**
 * Build the config.json object from current simulation state.
 */
function buildConfigJSON(manager, polygonOverlay, corridorManager, entryExitMarkers, mapFileName, droneFileName) {
  const bounds = getMapBounds();
  const config = {
    mapFileName,
    droneFileName,
    mapBounds: {
      topLeft: { lat: bounds.topLeft.lat, lon: bounds.topLeft.lon },
      bottomRight: { lat: bounds.bottomRight.lat, lon: bounds.bottomRight.lon },
    },
    captureArea: {
      x: manager._captureWidthMeters,
      y: manager._captureHeightMeters,
    },
    surveillance: [],
    navCorridors: [],
  };

  // Surveillance polygon
  const polyVerts = polygonOverlay.getVertices();
  if (polyVerts.length > 0) {
    config.surveillance = polyVerts;
  }

  // Nav corridors
  for (const c of corridorManager.getAllCorridors()) {
    config.navCorridors.push({
      id: c.id,
      vertices: c.overlay.getVertices(),
      created: c.overlay.isCreated(),
      entryPoint: c.entryPoint ? { ...c.entryPoint } : null,
      exitPoint: c.exitPoint ? { ...c.exitPoint } : null,
    });
  }

  // Entry/exit points
  if (entryExitMarkers) {
    const entry = entryExitMarkers.getEntryPoint();
    const exit = entryExitMarkers.getExitPoint();
    if (entry || exit) {
      config.entryExitPoints = { entry, exit };
    }
  }

  return config;
}

/**
 * Fetch an image as a Blob. Supports both URLs and object URLs.
 */
async function fetchImageBlob(url) {
  const response = await fetch(url);
  return response.blob();
}

/**
 * Export the current simulation config as a ZIP download.
 * @param {DroneManager} manager
 * @param {PolygonOverlay} polygonOverlay
 * @param {NavCorridorManager} corridorManager
 * @param {string} mapTextureURL - Current map texture URL (default or loaded)
 * @param {string} droneTextureURL - Current drone texture URL (default or loaded)
 */
export async function exportConfig(manager, polygonOverlay, corridorManager, entryExitMarkers, mapTextureURL, droneTextureURL) {
  const mapFileName = 'map.png';
  const droneFileName = 'drone.png';

  const config = buildConfigJSON(manager, polygonOverlay, corridorManager, entryExitMarkers, mapFileName, droneFileName);

  // Fetch image blobs
  const [mapBlob, droneBlob] = await Promise.all([
    fetchImageBlob(mapTextureURL),
    fetchImageBlob(droneTextureURL),
  ]);

  // Build ZIP
  const zip = new JSZip();
  zip.file('config.json', JSON.stringify(config, null, 2));
  zip.file(mapFileName, mapBlob);
  zip.file(droneFileName, droneBlob);

  const blob = await zip.generateAsync({ type: 'blob' });

  // Trigger download
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'drone_sim_config.zip';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/**
 * Import a ZIP file and extract config + images.
 * @param {File} zipFile - The ZIP file from a file input
 * @returns {Promise<{config: object, mapBlob: Blob, droneBlob: Blob}>}
 */
export async function importConfig(zipFile) {
  const zip = await JSZip.loadAsync(zipFile);

  // Read config.json
  const configFile = zip.file('config.json');
  if (!configFile) {
    throw new Error('ZIP does not contain config.json');
  }
  const configText = await configFile.async('text');
  const config = JSON.parse(configText);

  // Validate required fields
  if (!config.mapFileName || !config.droneFileName || !config.mapBounds) {
    throw new Error('config.json is missing required fields (mapFileName, droneFileName, mapBounds)');
  }
  const { topLeft, bottomRight } = config.mapBounds;
  if (!topLeft || !bottomRight ||
      typeof topLeft.lat !== 'number' || typeof topLeft.lon !== 'number' ||
      typeof bottomRight.lat !== 'number' || typeof bottomRight.lon !== 'number' ||
      isNaN(topLeft.lat) || isNaN(topLeft.lon) ||
      isNaN(bottomRight.lat) || isNaN(bottomRight.lon)) {
    throw new Error('config.json has invalid mapBounds (expected numeric lat/lon in topLeft and bottomRight)');
  }

  // Read image files
  const mapFile = zip.file(config.mapFileName);
  if (!mapFile) {
    throw new Error(`ZIP does not contain map image: ${config.mapFileName}`);
  }
  const mapBlob = await mapFile.async('blob');

  const droneFile = zip.file(config.droneFileName);
  if (!droneFile) {
    throw new Error(`ZIP does not contain drone image: ${config.droneFileName}`);
  }
  const droneBlob = await droneFile.async('blob');

  return { config, mapBlob, droneBlob };
}
