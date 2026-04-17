# CLAUDE.md — AI Development Context

This file provides context for AI agents (Claude, Copilot, etc.) working on this codebase.

---

## Project Overview

A 2D drone simulation: a drone sprite flies over a map image rendered with Three.js. A FastAPI backend communicates via WebSocket to control the drone. The frontend works standalone without the backend.

**Tech stack:** Three.js (r170+) + Vite (frontend), FastAPI + uvicorn (backend), WebSocket protocol.

---

## Directory Layout

```
threejs/
├── frontend/              # Vite + Three.js app
│   ├── index.html         # Single page — canvas + overlay control panel
│   ├── style.css          # All UI styles (dark theme, glassmorphism panel)
│   ├── vite.config.js     # Vite config — publicDir: 'assets', port: 3000
│   ├── package.json       # Deps: three, vite
│   ├── assets/            # Static files (Vite serves from publicDir)
│   │   ├── map.png        # 1962×1152 RGBA map of Lauttasaari, Helsinki
│   │   └── drone.webp     # Drone image (currently has white background)
│   └── src/
│       ├── main.js        # Entry point: scene, camera, renderer, animation loop, wiring
│       ├── mapPlane.js    # Loads map.png as texture → PlaneGeometry (MAP_WIDTH × MAP_HEIGHT)
│       ├── drone.js       # Drone class: position, speed, waypoints, movement, sprite
│       ├── coordinates.js # latLonToWorld() / worldToLatLon() — linear mapping
│       ├── ui.js          # UI class: DOM bindings for all controls
│       └── wsClient.js    # WSClient class: WebSocket with auto-reconnect
├── backend/
│   ├── main.py            # FastAPI app, WS endpoint /ws/drone, CORS
│   ├── ws_handler.py      # DroneWSHandler: message routing, send_to_all, command methods
│   ├── drone_state.py     # Pydantic models: DroneState, Waypoint
│   └── requirements.txt   # fastapi, uvicorn[standard], websockets
├── map.png                # Original source map image
├── drone.webp             # Original source drone image
├── README.md              # User-facing documentation
└── CLAUDE.md              # This file
```

---

## Key Architecture Decisions

1. **Simulation runs in the browser.** The frontend owns the animation loop and drone physics. The backend is a command/event relay, not a simulation server.

2. **Orthographic camera.** 2D top-down view. No perspective. Camera at z=10 looking at origin.

3. **Coordinate system.** World origin (0,0) is the center of the map. The map plane spans `MAP_WIDTH` × `MAP_HEIGHT` world units (19.62 × 11.52), derived from the image pixel dimensions. `coordinates.js` provides bidirectional linear mapping between lat/lon and world coords.

4. **WebSocket-only protocol.** No REST endpoints. All backend↔frontend communication is JSON over `ws://localhost:8000/ws/drone`.

5. **Standalone frontend.** All UI controls (fly-to, waypoints, speed) work without the backend. WebSocket connection is optional with 3-second auto-reconnect.

6. **Fixed drone orientation.** The drone sprite does not rotate toward its travel direction.

---

## Coordinate Mapping Details

Map bounds (Lauttasaari, Helsinki):
- Top-left: (60.1720, 24.8550)
- Bottom-right: (60.1520, 24.9250)

```
latLonToWorld(lat, lon) → {x, y}   // world coordinates, origin at center
worldToLatLon(x, y) → {lat, lon}   // GPS coordinates
```

The mapping is linear interpolation. For the small geographic area (~2km), this is accurate enough. If the map changes to a larger area, consider using a proper map projection (e.g., Web Mercator).

World coordinate axes:
- **x** increases left → right (east)
- **y** increases bottom → top (north, matching Three.js convention)
- **z** is depth: map at z=0, drone at z=1

---

## Drone Class API (`frontend/src/drone.js`)

```javascript
class Drone {
  // Properties
  lat, lon            // Current GPS position
  speed               // m/s (1–100, clamped)
  isFlying            // Boolean
  waypoints           // Array of {lat, lon}
  currentWaypointIndex // -1 when idle
  sprite              // THREE.Sprite

  // Methods
  setTarget(lat, lon)       // Fly to single point (replaces waypoints)
  setWaypoints([{lat,lon}]) // Set waypoint queue, start flying
  setSpeed(speed)           // Update speed (clamped 1–100)
  getStatus()               // Returns full state object
  update(deltaTime)         // Called each frame — moves drone toward target

  // Callbacks (assign externally)
  onWaypointReached(waypoint, index)  // Fires when drone arrives at a waypoint
  onStatusChanged(status)             // Fires on any state change
}
```

**Movement:** Each frame, `update(dt)` moves the sprite toward `targetWorld` at `speed * 0.01` world units/second. When within `ARRIVAL_THRESHOLD` (0.05 world units), it snaps to the target, fires `onWaypointReached`, and advances to the next waypoint or stops.

**Speed scaling:** `worldSpeed = speed * 0.01`. At speed=10, the drone moves 0.1 world units/sec. The map is ~19.62 world units wide, so crossing the full map takes ~196 seconds at speed 10. Adjust the `0.01` factor in `drone.js` line 115 to change this.

---

## WebSocket Message Protocol

### Backend → Frontend

| Type | Payload | Effect |
|------|---------|--------|
| `set_waypoints` | `{waypoints: [{lat, lon}, ...]}` | Drone starts flying through waypoints sequentially |
| `set_velocity` | `{speed: number}` | Updates drone speed and UI slider |
| `get_status` | (none) | Frontend responds with `status_response` |

### Frontend → Backend

| Type | Payload | Trigger |
|------|---------|---------|
| `waypoint_reached` | `{waypoint: {lat, lon}, index: number}` | Drone arrives at a waypoint |
| `status_response` | `{lat, lon, speed, is_flying, current_waypoint_index, waypoints}` | Reply to `get_status` |

---

## Backend Internals (`backend/`)

- **`main.py`**: FastAPI app. Single WS endpoint `/ws/drone`. Uses `DroneWSHandler` singleton.
- **`ws_handler.py`**: `DroneWSHandler` manages connections list. `handle_message()` routes incoming messages. Has helper methods `set_waypoints()`, `set_velocity()`, `get_status()` that can be called programmatically (useful for future REST or scheduled tasks).
- **`drone_state.py`**: Pydantic models. `DroneState` tracks the backend's view of drone state (updated via `status_response` messages). `Waypoint` is a simple lat/lon pair.

The handler's `send_to_all()` broadcasts to all connected WS clients and auto-cleans disconnected ones.

---

## Running the Project

```bash
# Frontend (port 3000, works alone)
cd frontend && npm run dev

# Backend (port 8000, optional)
cd backend && uvicorn main:app --reload
```

---

## Common Modifications

### Change map image
1. Replace `frontend/assets/map.png` with the new image
2. Update `MAP_BOUNDS` in `frontend/src/coordinates.js` with the GPS corners of the new map
3. Update `MAP_WIDTH` and `MAP_HEIGHT` if the aspect ratio changes (values are pixels / 100)

### Change drone image
1. Replace `frontend/assets/drone.webp` (or use `.png` for transparency)
2. If using a different filename, update the path in `drone.js` constructor (`loader.load('/drone.webp')`)
3. Adjust `this.sprite.scale.set(1.2, 1.2, 1)` for desired visual size

### Adjust drone speed scaling
Edit `frontend/src/drone.js` line 115:
```javascript
const worldSpeed = this.speed * 0.01; // increase multiplier for faster movement
```

### Change arrival threshold
Edit `frontend/src/drone.js` line 4:
```javascript
const ARRIVAL_THRESHOLD = 0.05; // decrease for more precision, increase if drone "misses" waypoints
```

### Add a new WebSocket command
1. Add the message type handler in `frontend/src/wsClient.js` `_handleMessage()` switch
2. Add the corresponding handler in `backend/ws_handler.py` `handle_message()`
3. If needed, add a helper method on `DroneWSHandler` for programmatic use

### Add new UI controls
1. Add HTML elements in `frontend/index.html` inside `#control-panel`
2. Add DOM bindings and event listeners in `frontend/src/ui.js`
3. Style in `frontend/style.css`

---

## Known Limitations & TODOs

- **Drone image has white background** — needs transparent PNG replacement
- **No map pan/zoom** — camera is fixed; could add OrbitControls or custom pan
- **No path visualization** — no trail or line showing the drone's trajectory
- **Single drone only** — architecture supports one drone; multi-drone needs refactoring
- **No input validation for out-of-bounds coordinates** — drone can fly off the visible map
- **No authentication** on the WebSocket endpoint
- **Linear coordinate mapping** — fine for ~2km area, not suitable for large-scale maps
- **Speed scaling is approximate** — the `0.01` factor is tuned for visual feel, not real-world accuracy

---

## Testing Notes

- The frontend can be tested fully without the backend (all controls work standalone)
- Backend WebSocket can be tested with any WS client (wscat, Python websockets, browser console)
- Coordinate round-trip accuracy verified: `worldToLatLon(latLonToWorld(lat, lon))` matches to < 0.0001°
- Frontend builds successfully with `npm run build` (Vite production build)
