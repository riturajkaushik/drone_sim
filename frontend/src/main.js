import * as THREE from 'three';
import { createMapPlane } from './mapPlane.js';
import { Drone } from './drone.js';
import { UI } from './ui.js';
import { WSClient } from './wsClient.js';
import { MAP_WIDTH, MAP_HEIGHT } from './coordinates.js';

// Scene setup
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x1a1a2e);

// Orthographic camera for 2D top-down view
const aspect = window.innerWidth / window.innerHeight;
const viewHeight = MAP_HEIGHT * 1.1; // slightly larger than map for padding
const viewWidth = viewHeight * aspect;

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

// Create map and drone
createMapPlane(scene);
const drone = new Drone(scene);

// UI
const ui = new UI(drone);

// WebSocket client (connects in background, frontend works without it)
const wsClient = new WSClient(drone, ui);
wsClient.connect();

// Drone callbacks
drone.onWaypointReached = (waypoint, index) => {
  console.log(`Waypoint #${index} reached:`, waypoint);
  wsClient.sendWaypointReached(waypoint, index);
};

drone.onStatusChanged = (status) => {
  ui.updateStatus(status);
};

// Animation loop
const clock = new THREE.Clock();

function animate() {
  requestAnimationFrame(animate);

  const dt = clock.getDelta();
  drone.update(dt);

  // Continuously update status display
  ui.updateStatus(drone.getStatus());

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
