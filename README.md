# 🛸 Drone Map Simulation

A 2D drone flight simulation built with **Three.js** (frontend) and **FastAPI** (backend). A drone sprite flies over a real map image (Lauttasaari, Helsinki), navigating to GPS coordinates entered by the user or commanded by the backend via WebSocket.

![Stack](https://img.shields.io/badge/Frontend-Three.js%20+%20Vite-blue) ![Stack](https://img.shields.io/badge/Backend-FastAPI-green) ![Protocol](https://img.shields.io/badge/Protocol-WebSocket-orange)

---

## Features

- **2D map rendering** — `map.png` displayed as a textured plane using an orthographic Three.js camera
- **Drone sprite** — flies over the map with configurable speed; position tracked in lat/lon
- **Fly-to** — enter latitude/longitude and click "Fly" to send the drone to that location
- **Waypoint system** — queue multiple waypoints, drone visits them sequentially
- **Speed control** — slider to adjust drone speed from 1–100 m/s in real-time
- **Live status** — displays current lat, lon, speed, and flying/idle state
- **WebSocket backend** — FastAPI server can remotely command the drone and receive callbacks
- **Standalone frontend** — all controls work without the backend running (WebSocket is optional with auto-reconnect)

---

## Project Structure

```
threejs/
├── frontend/                  # Three.js + Vite frontend
│   ├── index.html             # Main page with UI overlay
│   ├── style.css              # Dark-themed control panel styles
│   ├── vite.config.js         # Vite configuration
│   ├── package.json           # Dependencies (three, vite)
│   ├── assets/                # Static assets served by Vite
│   │   ├── map.png            # Map image (Lauttasaari, Helsinki)
│   │   └── drone.webp         # Drone sprite image
│   └── src/
│       ├── main.js            # Entry point — scene, camera, renderer, animation loop
│       ├── mapPlane.js        # Creates the textured map plane
│       ├── drone.js           # Drone class — movement, waypoints, speed, callbacks
│       ├── coordinates.js     # Lat/lon ↔ Three.js world coordinate conversion
│       ├── ui.js              # UI controls — fly-to, speed, waypoint manager, status
│       └── wsClient.js        # WebSocket client with auto-reconnect
├── backend/                   # FastAPI backend
│   ├── main.py                # App + WebSocket endpoint
│   ├── ws_handler.py          # WebSocket message handler + drone command methods
│   ├── drone_state.py         # Pydantic models (DroneState, Waypoint)
│   └── requirements.txt       # Python dependencies
├── map.png                    # Original map image
├── drone.webp                 # Original drone image
├── README.md
└── CLAUDE.md                  # AI development context
```

---

## Prerequisites

- **Node.js** ≥ 18 (with npm)
- **Python** ≥ 3.10

---

## Quick Start

### 1. Install dependencies

```bash
# Frontend
cd frontend
npm install

# Backend
cd ../backend
pip install -r requirements.txt
```

### 2. Run the frontend (standalone — no backend needed)

```bash
cd frontend
npm run dev
```

Open **http://localhost:3000** in your browser. You'll see the map with the drone, and all controls work immediately.

### 3. Run the backend (optional — for remote control)

```bash
cd backend
uvicorn main:app --reload --port 8000
```

The frontend will automatically connect via WebSocket (status indicator in the control panel turns green).

---

## UI Controls

| Control | Description |
|---------|-------------|
| **Fly To** | Enter lat/lon and click "🚀 Fly" to send the drone to that coordinate |
| **Speed slider** | Adjust drone speed 1–100 m/s; takes effect immediately |
| **Add Waypoint** | Enter lat/lon and click "+ Add" to queue a waypoint |
| **Clear** | Remove all queued waypoints |
| **▶ Fly Waypoints** | Start flying through all queued waypoints in order |
| **Status panel** | Shows current lat, lon, speed, and flying/idle state |
| **Backend indicator** | Shows WebSocket connection status (Connected/Disconnected) |

---

## Map Coordinate System

The map image covers the **Lauttasaari area in Helsinki, Finland** with these assumed corner coordinates:

| Corner | Latitude | Longitude |
|--------|----------|-----------|
| Top-left | 60.1720°N | 24.8550°E |
| Top-right | 60.1720°N | 24.9250°E |
| Bottom-left | 60.1520°N | 24.8550°E |
| Bottom-right | 60.1520°N | 24.9250°E |

Coordinates are mapped using linear interpolation, which is sufficient for this small geographic area. To recalibrate, edit `MAP_BOUNDS` in `frontend/src/coordinates.js`.

### Example coordinates to try

| Location | Lat | Lon |
|----------|-----|-----|
| Center of map | 60.1620 | 24.8900 |
| Lauttasaari metro | 60.1590 | 24.8830 |
| Northern shore | 60.1700 | 24.8700 |
| Southern tip | 60.1540 | 24.8800 |

---

## WebSocket Protocol

All communication between frontend and backend uses **JSON messages over WebSocket** at `ws://localhost:8000/ws/drone`.

### Backend → Frontend (commands)

#### Set waypoints
```json
{
  "type": "set_waypoints",
  "waypoints": [
    {"lat": 60.1700, "lon": 24.8700},
    {"lat": 60.1590, "lon": 24.8830},
    {"lat": 60.1540, "lon": 24.8800}
  ]
}
```

#### Set velocity
```json
{
  "type": "set_velocity",
  "speed": 25
}
```

#### Request status
```json
{
  "type": "get_status"
}
```

### Frontend → Backend (responses/events)

#### Status response (reply to `get_status`)
```json
{
  "type": "status_response",
  "lat": 60.1620,
  "lon": 24.8900,
  "speed": 10.0,
  "is_flying": true,
  "current_waypoint_index": 1,
  "waypoints": [{"lat": 60.17, "lon": 24.87}, {"lat": 60.159, "lon": 24.883}]
}
```

#### Waypoint reached callback
```json
{
  "type": "waypoint_reached",
  "waypoint": {"lat": 60.1700, "lon": 24.8700},
  "index": 0
}
```

---

## Testing with the Backend

You can test backend commands using a Python script or any WebSocket client:

```python
import asyncio
import websockets
import json

async def test():
    async with websockets.connect("ws://localhost:8000/ws/drone") as ws:
        # Set waypoints
        await ws.send(json.dumps({
            "type": "set_waypoints",
            "waypoints": [
                {"lat": 60.1700, "lon": 24.8700},
                {"lat": 60.1540, "lon": 24.8800}
            ]
        }))

        # Listen for waypoint_reached callbacks
        while True:
            msg = json.loads(await ws.recv())
            print(f"Received: {msg}")

asyncio.run(test())
```

---

## Architecture Notes

- **Simulation runs entirely in the browser** — the frontend owns the drone animation loop. The backend sends commands and receives events but does not simulate physics.
- **Orthographic camera** — provides a true 2D top-down view with no perspective distortion.
- **Sprite rendering** — the drone is a Three.js `Sprite` (always faces camera), rendered at z=1 above the map plane at z=0.
- **Graceful degradation** — if the backend is unavailable, the frontend works fully standalone with auto-reconnect every 3 seconds.
- **Fixed orientation** — the drone does not rotate to face its direction of travel.

---

## Development

```bash
# Frontend dev server with HMR
cd frontend && npm run dev

# Backend with auto-reload
cd backend && uvicorn main:app --reload

# Production build (frontend)
cd frontend && npm run build
```

---

## Future Improvements

- Replace `drone.webp` with a transparent-background PNG
- Add map zoom/pan controls
- Add drone trail/path visualization
- Implement altitude (z-axis) support
- Add multiple drone support
- Calibrate map coordinates to exact GPS bounds
- Add heading/bearing display
- Implement geofencing (restrict drone to map bounds)
