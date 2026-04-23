// Default map corner coordinates (Lauttasaari, Helsinki area)
const DEFAULT_MAP_BOUNDS = {
  topLeft:     { lat: 60.1720, lon: 24.8550 },
  bottomRight: { lat: 60.1520, lon: 24.9250 },
};

const DEFAULT_MAP_WIDTH = 19.62;   // world units (matching 1962px aspect)
const DEFAULT_MAP_HEIGHT = 11.52;  // world units (matching 1152px aspect)

// Mutable state — updated via updateMapConfig()
let MAP_BOUNDS = {
  topLeft:     { ...DEFAULT_MAP_BOUNDS.topLeft },
  topRight:    { lat: DEFAULT_MAP_BOUNDS.topLeft.lat, lon: DEFAULT_MAP_BOUNDS.bottomRight.lon },
  bottomLeft:  { lat: DEFAULT_MAP_BOUNDS.bottomRight.lat, lon: DEFAULT_MAP_BOUNDS.topLeft.lon },
  bottomRight: { ...DEFAULT_MAP_BOUNDS.bottomRight },
};

let MAP_WIDTH = DEFAULT_MAP_WIDTH;
let MAP_HEIGHT = DEFAULT_MAP_HEIGHT;

// Derived values — recomputed by _recomputeDerived()
const METERS_PER_DEG_LAT = 111_320;
let CENTER_LAT, METERS_PER_DEG_LON, LAT_RANGE, LON_RANGE, MAP_WIDTH_METERS, MAP_HEIGHT_METERS;

function _recomputeDerived() {
  CENTER_LAT = (MAP_BOUNDS.topLeft.lat + MAP_BOUNDS.bottomRight.lat) / 2;
  METERS_PER_DEG_LON = METERS_PER_DEG_LAT * Math.cos(CENTER_LAT * Math.PI / 180);
  LAT_RANGE = MAP_BOUNDS.topLeft.lat - MAP_BOUNDS.bottomRight.lat;
  LON_RANGE = MAP_BOUNDS.bottomRight.lon - MAP_BOUNDS.topLeft.lon;
  MAP_WIDTH_METERS = LON_RANGE * METERS_PER_DEG_LON;
  MAP_HEIGHT_METERS = LAT_RANGE * METERS_PER_DEG_LAT;
}

_recomputeDerived();

/**
 * Update map configuration at runtime.
 * @param {{ topLeft: {lat, lon}, bottomRight: {lat, lon} }} bounds
 * @param {number} width  - world units (pixels / 100)
 * @param {number} height - world units (pixels / 100)
 */
export function updateMapConfig(bounds, width, height) {
  MAP_BOUNDS.topLeft = { ...bounds.topLeft };
  MAP_BOUNDS.bottomRight = { ...bounds.bottomRight };
  MAP_BOUNDS.topRight = { lat: bounds.topLeft.lat, lon: bounds.bottomRight.lon };
  MAP_BOUNDS.bottomLeft = { lat: bounds.bottomRight.lat, lon: bounds.topLeft.lon };
  MAP_WIDTH = width;
  MAP_HEIGHT = height;
  _recomputeDerived();
}

/**
 * Reset map configuration to built-in defaults.
 */
export function resetMapConfig() {
  updateMapConfig(DEFAULT_MAP_BOUNDS, DEFAULT_MAP_WIDTH, DEFAULT_MAP_HEIGHT);
}

/**
 * Convert lat/lon to Three.js world coordinates.
 * Origin (0,0) is at the center of the map.
 */
export function latLonToWorld(lat, lon) {
  const { topLeft, bottomRight } = MAP_BOUNDS;

  // Normalize to 0–1 range
  const nx = (lon - topLeft.lon) / (bottomRight.lon - topLeft.lon);
  const ny = (lat - topLeft.lat) / (bottomRight.lat - topLeft.lat);

  // Map to world coordinates (centered at origin)
  // x goes left-to-right, y goes top-to-bottom (but Three.js y is up)
  const x = (nx - 0.5) * MAP_WIDTH;
  const y = -(ny - 0.5) * MAP_HEIGHT; // negate because lat decreases downward

  return { x, y };
}

/**
 * Convert Three.js world coordinates back to lat/lon.
 */
export function worldToLatLon(x, y) {
  const { topLeft, bottomRight } = MAP_BOUNDS;

  const nx = (x / MAP_WIDTH) + 0.5;
  const ny = -(y / MAP_HEIGHT) + 0.5;

  const lon = topLeft.lon + nx * (bottomRight.lon - topLeft.lon);
  const lat = topLeft.lat + ny * (bottomRight.lat - topLeft.lat);

  return { lat, lon };
}

/**
 * Convert meters to world units in the X (longitude) direction.
 * Accounts for latitude-dependent longitude scaling.
 */
export function metersToWorldX(meters) {
  return (meters / MAP_WIDTH_METERS) * MAP_WIDTH;
}

/**
 * Convert meters to world units in the Y (latitude) direction.
 */
export function metersToWorldY(meters) {
  return (meters / MAP_HEIGHT_METERS) * MAP_HEIGHT;
}

/**
 * Check if a lat/lon coordinate is within the visible map bounds.
 */
export function isInBounds(lat, lon) {
  return (
    lat >= MAP_BOUNDS.bottomRight.lat &&
    lat <= MAP_BOUNDS.topLeft.lat &&
    lon >= MAP_BOUNDS.topLeft.lon &&
    lon <= MAP_BOUNDS.bottomRight.lon
  );
}

export { MAP_BOUNDS, MAP_WIDTH, MAP_HEIGHT };

/**
 * Getters for current map dimensions (useful when callers cache the import).
 */
export function getMapWidth() { return MAP_WIDTH; }
export function getMapHeight() { return MAP_HEIGHT; }
export function getMapBounds() { return MAP_BOUNDS; }
