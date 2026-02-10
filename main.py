from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict
import asyncio
import time

app = FastAPI()

# mobile -> websocket
active_connections: Dict[str, WebSocket] = {}
last_seen: Dict[str, float] = {}

PING_TIMEOUT = 60          # seconds
CLEANUP_INTERVAL = 30      # seconds


@app.websocket("/ws/{mobile}")
async def websocket_endpoint(websocket: WebSocket, mobile: str):
    # ✅ Validate mobile number
    if not mobile.isdigit() or len(mobile) < 10:
        await websocket.close(code=1008)
        return

    await websocket.accept()

    # ✅ Register connection
    active_connections[mobile] = websocket
    last_seen[mobile] = time.time()

    # 🔔 Broadcast presence on connect
    await broadcast_online_users()

    try:
        while True:
            data = await websocket.receive_json()
            last_seen[mobile] = time.time()

            # 💓 Heartbeat
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            # 📡 Client explicitly requests online users (IMPORTANT FIX)
            if data.get("type") == "get_online_users":
                users = list(active_connections.keys())
                await websocket.send_json({
                    "type": "online_users",
                    "users": [u for u in users if u != mobile]
                })
                continue

            # 💬 Message handling
            if data.get("type") == "message":
                to_mobile = data.get("to")
                text = data.get("text")

                if not to_mobile or not text or to_mobile == mobile:
                    continue

                message = {
                    "type": "message",
                    "from": mobile,
                    "text": text
                }

                if to_mobile in active_connections:
                    try:
                        await active_connections[to_mobile].send_json(message)
                    except:
                        cleanup_user(to_mobile)

    except WebSocketDisconnect:
        pass
    finally:
        cleanup_user(mobile)
        await broadcast_online_users()


def cleanup_user(mobile: str):
    active_connections.pop(mobile, None)
    last_seen.pop(mobile, None)


async def broadcast_online_users():
    users = list(active_connections.keys())

    for mobile, ws in list(active_connections.items()):
        try:
            await ws.send_json({
                "type": "online_users",
                "users": [u for u in users if u != mobile]
            })
        except:
            cleanup_user(mobile)


# 🧹 Background cleanup task (Render-safe)
@app.on_event("startup")
async def start_cleanup_task():
    asyncio.create_task(cleanup_inactive_users())


async def cleanup_inactive_users():
    while True:
        now = time.time()
        inactive = []

        for mobile, last_time in list(last_seen.items()):
            if now - last_time > PING_TIMEOUT:
                inactive.append(mobile)

        for mobile in inactive:
            cleanup_user(mobile)

        if inactive:
            await broadcast_online_users()

        await asyncio.sleep(CLEANUP_INTERVAL)


# ✅ Health check (Render friendly)
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "connections": len(active_connections)
    }
