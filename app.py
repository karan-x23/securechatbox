import asyncio
import re
from collections import defaultdict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Private Two-Person Chat")
app.mount("/static", StaticFiles(directory="static"), name="static")
ROOM_RE = re.compile(r"^[a-f0-9]{32}$")
rooms: dict[str, set[WebSocket]] = defaultdict(set)
locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

@app.get("/")
async def home():
    return FileResponse("static/index.html")

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.websocket("/ws/{room_id}")
async def chat_socket(websocket: WebSocket, room_id: str):
    if not ROOM_RE.fullmatch(room_id):
        await websocket.close(code=1008)
        return
    await websocket.accept()
    async with locks[room_id]:
        if len(rooms[room_id]) >= 2:
            await websocket.send_json({"type": "error", "message": "This room already has two connected people."})
            await websocket.close(code=1008)
            return
        rooms[room_id].add(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            # Only relay encrypted payloads. The server does not decrypt or store them.
            if not isinstance(data, dict) or data.get("type") != "ciphertext":
                continue
            payload = data.get("payload")
            if not isinstance(payload, dict) or not isinstance(payload.get("iv"), str) or not isinstance(payload.get("data"), str):
                continue
            async with locks[room_id]:
                peers = list(rooms[room_id])
            for peer in peers:
                if peer is not websocket:
                    try:
                        await peer.send_json({"type": "ciphertext", "payload": payload})
                    except Exception:
                        pass
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        async with locks[room_id]:
            rooms[room_id].discard(websocket)
            if not rooms[room_id]:
                rooms.pop(room_id, None)
                locks.pop(room_id, None)
