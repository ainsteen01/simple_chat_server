from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict

app = FastAPI()

# mobile_number -> WebSocket
active_connections: Dict[str, WebSocket] = {}

@app.websocket("/ws/{mobile}")
async def websocket_endpoint(websocket: WebSocket, mobile: str):
    await websocket.accept()

    # Store connection
    active_connections[mobile] = websocket
    await broadcast_online_users()

    try:
        while True:
            data = await websocket.receive_json()

            if data["type"] == "message":
                to_mobile = data["to"]

                message = {
                    "type": "message",
                    "from": mobile,
                    "text": data["text"]
                }

                if to_mobile in active_connections:
                    await active_connections[to_mobile].send_json(message)

    except WebSocketDisconnect:
        active_connections.pop(mobile, None)
        await broadcast_online_users()


async def broadcast_online_users():
    users = list(active_connections.keys())
    for ws in active_connections.values():
        await ws.send_json({
            "type": "online_users",
            "users": users
        })
