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

export { MAP_BOUNDS, MAP_WIDTH, MAP_HEIGHT };
