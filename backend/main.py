from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import json
from ws_handler import DroneWSHandler

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


@app.get("/")
async def root():
    return {"status": "Drone simulation backend running"}
