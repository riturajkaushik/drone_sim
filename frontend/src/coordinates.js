// Map corner coordinates (Lauttasaari, Helsinki area)
const MAP_BOUNDS = {
  topLeft:     { lat: 60.1720, lon: 24.8550 },
  topRight:    { lat: 60.1720, lon: 24.9250 },
  bottomLeft:  { lat: 60.1520, lon: 24.8550 },
  bottomRight: { lat: 60.1520, lon: 24.9250 },
};

// Map image dimensions in world units (Three.js)
// We'll use the actual pixel dimensions scaled to convenient world units
const MAP_WIDTH = 19.62;   // world units (matching 1962px aspect)
const MAP_HEIGHT = 11.52;  // world units (matching 1152px aspect)

// Derived constants for meter↔world conversion
const METERS_PER_DEG_LAT = 111_320;
const CENTER_LAT = (MAP_BOUNDS.topLeft.lat + MAP_BOUNDS.bottomRight.lat) / 2;
const METERS_PER_DEG_LON = METERS_PER_DEG_LAT * Math.cos(CENTER_LAT * Math.PI / 180);

const LAT_RANGE = MAP_BOUNDS.topLeft.lat - MAP_BOUNDS.bottomRight.lat; // positive
const LON_RANGE = MAP_BOUNDS.bottomRight.lon - MAP_BOUNDS.topLeft.lon; // positive

const MAP_WIDTH_METERS = LON_RANGE * METERS_PER_DEG_LON;
const MAP_HEIGHT_METERS = LAT_RANGE * METERS_PER_DEG_LAT;

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
