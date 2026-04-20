# CLAUDE.md — AI Development Context

This file provides context for AI agents (Claude, Copilot, etc.) working on this codebase.

---

## Project Overview

A multi-drone simulation platform with four components:

1. **Frontend** — 2D visualization: drone sprites fly over a map image rendered with Three.js. Works standalone without the backend.
2. **Backend** — FastAPI server that relays commands/events between the client SDK and the frontend drones via WebSocket.
3. **Client SDK (`drone_sim_client/`)** — Python SDK acting as a "command center": sets missions, gets drone updates, updates missions, runs algorithms locally, and creates navigation plans. Talks to the backend which in turn talks to the drones (simulated in the frontend).
4. **Algos (`algos/`)** — Standalone experimentation space for drone navigation algorithms (e.g., area partitioning, route planning). Not part of the application stack directly — code from here is intended to be used in the backend and client SDK.

**Architecture:** Client SDK → Backend → Frontend (simulated drones). Each drone is identified by a unique ID and can be managed independently.

**Tech stack:** Three.js (r170+) + Vite (frontend), FastAPI + uvicorn (backend), Python SDK (client), WebSocket protocol.

---

## Directory Layout

```
drone_sim/
├── frontend/              # Vite + Three.js app (drone visualization)
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
├── backend/               # FastAPI backend (command/event relay)
│   ├── main.py            # FastAPI app, WS endpoint /ws/drone, CORS
│   ├── ws_handler.py      # DroneWSHandler: message routing, send_to_all, command methods
│   ├── drone_state.py     # Pydantic models: DroneState, Waypoint
│   └── requirements.txt   # fastapi, uvicorn[standard], websockets
├── algos/                 # Navigation algorithm experimentation (standalone)
│   ├── main.py            # Entry point — demo of SpacePolygon partitioning & route planning
│   ├── space_partition.py # SpacePolygon class: polygon partitioning, TSP route planning
│   ├── pyproject.toml     # Deps: matplotlib, pyproj, shapely
│   └── requirements.txt   # Pip requirements
├── drone_sim_client/      # Python client SDK (command center) — in development
│   └── (empty)            # Intended: SDK to talk to backend, set missions, run algos locally
├── map.png                # Original source map image
├── drone.webp             # Original source drone image
├── README.md              # User-facing documentation
└── CLAUDE.md              # This file
```

---

## Key Architecture Decisions

1. **Simulation runs in the browser.** The frontend owns the animation loop and drone physics. The backend is a command/event relay, not a simulation server.

2. **Three-layer architecture.** Client SDK → Backend → Frontend. The client SDK is the "command center" that issues missions and runs algorithms. The backend relays commands to the frontend which simulates the drones visually.

3. **Multi-drone by design.** Each drone is identified by a unique ID and can be managed independently. The system is designed to support one or more concurrent drones.

4. **Orthographic camera.** 2D top-down view. No perspective. Camera at z=10 looking at origin.

5. **Coordinate system.** World origin (0,0) is the center of the map. The map plane spans `MAP_WIDTH` × `MAP_HEIGHT` world units (19.62 × 11.52), derived from the image pixel dimensions. `coordinates.js` provides bidirectional linear mapping between lat/lon and world coords.

6. **WebSocket-only protocol.** No REST endpoints. All backend↔frontend communication is JSON over `ws://localhost:8000/ws/drone`.

7. **Standalone frontend.** All UI controls (fly-to, waypoints, speed) work without the backend. WebSocket connection is optional with 3-second auto-reconnect.

8. **Fixed drone orientation.** The drone sprite does not rotate toward its travel direction.

9. **Algos are standalone.** The `algos/` folder is an independent experimentation space — not wired into the app stack. Algorithms developed here are intended to be ported into the backend and client SDK once validated.

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

## Algos (`algos/`)

A standalone experimentation space for drone navigation algorithms. Not wired into the app stack — algorithms validated here are intended to be ported into the backend and client SDK.

**Current contents:**

- **`space_partition.py`** — `SpacePolygon` class: defines a polygon from GPS coordinates with entry/exit points, partitions it into overlapping rectangles (configurable size & overlap), and plans an optimized route through all partition centers using nearest-neighbor + 2-opt TSP heuristics.
- **`main.py`** — Demo entry point: creates a polygon around Lauttasaari, partitions it into 100m×100m cells with 20% overlap, plans a route, and renders the result with matplotlib.
- **`pyproject.toml`** — Python ≥3.13, deps: matplotlib, pyproj, shapely.

**Key class: `SpacePolygon`**
```python
polygon = SpacePolygon(coordinates=[...], entry_point={...}, exit_point={...})
polygon.partition(length_x=100, length_y=100, overlap_percentage=20)
polygon.plan_route()   # Returns ordered list of {lat, lon} waypoints
polygon.render()       # Matplotlib visualization
```

---

## Client SDK (`drone_sim_client/`) — In Development

A Python SDK acting as the "command center" for the drone simulation platform. Currently an empty directory; the intended architecture is:

- **Talks to the backend** via WebSocket to send missions, receive drone updates, and modify active missions.
- **Runs algorithms locally** (e.g., from `algos/`) to create navigation plans before dispatching them to drones.
- **Manages multiple drones** — each drone identified by a unique ID, managed independently.
- **Intended capabilities:** set missions, get real-time status updates, update/cancel missions, run navigation algorithms locally, create and dispatch navigation plans.

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
- **Multi-drone not yet implemented** — architecture is designed for multi-drone (unique IDs, independent management) but frontend/backend currently support a single drone
- **Client SDK not yet implemented** — `drone_sim_client/` is an empty placeholder
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
