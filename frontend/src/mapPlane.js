import * as THREE from 'three';
import { MAP_WIDTH, MAP_HEIGHT } from './coordinates.js';

/**
 * Create the map plane with the map.png texture.
 */
export function createMapPlane(scene) {
  const loader = new THREE.TextureLoader();
  const texture = loader.load('/map.png');
  texture.colorSpace = THREE.SRGBColorSpace;

  const geometry = new THREE.PlaneGeometry(MAP_WIDTH, MAP_HEIGHT);
  const material = new THREE.MeshBasicMaterial({ map: texture });
  const plane = new THREE.Mesh(geometry, material);

  plane.position.set(0, 0, 0);
  scene.add(plane);

  return plane;
}
