from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import json
from ws_handler import DroneWSHandler
from drone_state import SurveillancePolygonRequest, NavCorridorsRequest, SpawnDronesRequest

app = FastAPI(title="Drone Simulation Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

handler = DroneWSHandler()


@app.websocket("/ws/drone")
async def drone_websocket(websocket: WebSocket):
    await websocket.accept()
    handler.register(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            await handler.handle_message(websocket, message)
    except WebSocketDisconnect:
        handler.unregister(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        handler.unregister(websocket)


@app.post("/surveillance-polygon")
async def set_surveillance_polygon(req: SurveillancePolygonRequest):
    """Store a surveillance area polygon and broadcast it to all connected frontends."""
    handler.surveillance_polygon = req.surveillance_polygon
    await handler.send_to_all({
        "type": "set_surveillance_polygon",
        "surveillance_polygon": req.surveillance_polygon,
    })
    return {
        "status": "ok",
        "vertices": len(req.surveillance_polygon),
        "surveillance_polygon": req.surveillance_polygon,
    }


@app.post("/nav-corridors")
async def set_nav_corridors(req: NavCorridorsRequest):
    """Store navigation corridors and broadcast them to all connected frontends."""
    handler.nav_corridors = req.nav_corridors
    await handler.send_to_all({
        "type": "set_nav_corridors",
        "nav_corridors": req.nav_corridors,
    })
    return {
        "status": "ok",
        "corridors": {
            cid: len(verts) for cid, verts in req.nav_corridors.items()
        },
        "nav_corridors": req.nav_corridors,
    }


@app.post("/spawn-drones")
async def spawn_drones(req: SpawnDronesRequest):
    """Spawn drones and broadcast them to all connected frontends."""
    try:
        drones = await handler.spawn_drones(req)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"status": "error", "message": str(e)})
    return {
        "status": "ok",
        "drones": drones,
    }


@app.get("/")
async def root():
    return {"status": "Drone simulation backend running"}
