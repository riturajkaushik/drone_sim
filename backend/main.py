from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import asyncio
import json
from ws_handler import DroneWSHandler
from drone_state import SurveillancePolygonRequest, NavCorridorsRequest, NavCorridorData, SpawnDronesRequest, FollowWaypointsRequest, EntryExitPointsRequest

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
    # Store the full NavCorridorData objects
    handler.nav_corridors = {
        cid: data.model_dump() for cid, data in req.nav_corridors.items()
    }
    # Broadcast in new format: {corridorId: {vertices, entry_point, exit_point}}
    await handler.send_to_all({
        "type": "set_nav_corridors",
        "nav_corridors": handler.nav_corridors,
    })
    return {
        "status": "ok",
        "corridors": {
            cid: len(data.vertices) for cid, data in req.nav_corridors.items()
        },
        "nav_corridors": handler.nav_corridors,
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


@app.post("/set-waypoints")
async def set_waypoints(req: FollowWaypointsRequest):
    """Set waypoints for one or more drones via REST API.

    Payload: {"waypoints": {"drone-1": [[lat, lon], ...], "drone-2": [[lat, lon], ...], ...}}
    """
    result = await handler.dispatch_waypoints(req)
    if "error" in result:
        return JSONResponse(status_code=400, content={"status": "error", "message": result["error"]})
    return {
        "status": "ok",
        "drones": result["drones"],
    }


@app.post("/entry-exit-points")
async def set_entry_exit_points(req: EntryExitPointsRequest):
    """Store entry/exit points for the surveillance area and broadcast to all frontends."""
    handler.entry_point = req.entry_point
    handler.exit_point = req.exit_point
    await handler.send_to_all({
        "type": "set_entry_exit_points",
        "entry_point": req.entry_point,
        "exit_point": req.exit_point,
    })
    return {
        "status": "ok",
        "entry_point": req.entry_point,
        "exit_point": req.exit_point,
    }


@app.get("/")
async def root():
    return {"status": "Drone simulation backend running"}


@app.websocket("/ws/sim-state")
async def sim_state_websocket(websocket: WebSocket):
    """WebSocket that streams the full simulation state every 500ms."""
    await websocket.accept()
    handler.register_sim_state(websocket)
    try:
        # Send initial state immediately
        state = handler.get_sim_state()
        await websocket.send_text(json.dumps(state))

        # Push state updates periodically
        while True:
            await asyncio.sleep(0.5)
            state = handler.get_sim_state()
            await websocket.send_text(json.dumps(state))
    except WebSocketDisconnect:
        handler.unregister_sim_state(websocket)
    except Exception:
        handler.unregister_sim_state(websocket)
