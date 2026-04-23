import * as THREE from 'three';
import { MAP_WIDTH, MAP_HEIGHT } from './coordinates.js';

let _mapPlane = null;

/**
 * Create the map plane with the map.png texture.
 * Returns the plane mesh for later reference.
 */
export function createMapPlane(scene, textureURL = '/map.png') {
  const loader = new THREE.TextureLoader();
  const texture = loader.load(textureURL);
  texture.colorSpace = THREE.SRGBColorSpace;

  const geometry = new THREE.PlaneGeometry(MAP_WIDTH, MAP_HEIGHT);
  const material = new THREE.MeshBasicMaterial({ map: texture });
  const plane = new THREE.Mesh(geometry, material);

  plane.position.set(0, 0, 0);
  scene.add(plane);

  _mapPlane = plane;
  return plane;
}

/**
 * Replace the map texture and resize the plane to match new MAP_WIDTH/MAP_HEIGHT.
 * Call after updateMapConfig() has been invoked.
 */
export function replaceMapPlane(scene, textureURL) {
  if (_mapPlane) {
    scene.remove(_mapPlane);
    _mapPlane.material.map.dispose();
    _mapPlane.material.dispose();
    _mapPlane.geometry.dispose();
    _mapPlane = null;
  }
  return createMapPlane(scene, textureURL);
}

/**
 * Get the current map plane mesh.
 */
export function getMapPlane() {
  return _mapPlane;
}
