
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import re
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

TITLE = "SecureChatBox"
ROOM_RE = re.compile(r"^[a-f0-9]{32}$")
PARTICIPANT_RE = re.compile(r"^[a-f0-9]{32}$")
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{40,100}$")
HISTORY_LIMIT = 200
HEARTBEAT_TIMEOUT = 75
DB_PATH = os.environ.get("DATABASE_PATH", "./data/securechatbox.sqlite3")
AUTH_PEPPER = os.environ.get("AUTH_PEPPER", "")

app = FastAPI(title=TITLE)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Each room has a lock for in-process socket/session bookkeeping. SQLite serializes
# writes across requests; use one app worker unless moving this state to Redis.
room_locks: dict[str, asyncio.Lock] = {}
room_sockets: dict[str, dict[str, WebSocket]] = {}


def _db_path() -> Path:
    path = Path(DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


@contextmanager
def db() -> Any:
    conn = sqlite3.connect(_db_path(), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 15000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with db() as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS rooms (
                room_id TEXT PRIMARY KEY,
                auth_hash TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS participants (
                room_id TEXT NOT NULL,
                participant_id TEXT NOT NULL,
                display_name TEXT NOT NULL,
                first_seen REAL NOT NULL,
                last_seen REAL NOT NULL,
                PRIMARY KEY (room_id, participant_id),
                FOREIGN KEY (room_id) REFERENCES rooms(room_id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS messages (
                message_id TEXT PRIMARY KEY,
                room_id TEXT NOT NULL,
                sender_id TEXT NOT NULL,
                ciphertext_json TEXT NOT NULL,
                client_message_id TEXT,
                created_at REAL NOT NULL,
                FOREIGN KEY (room_id) REFERENCES rooms(room_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_messages_room_time
                ON messages(room_id, created_at);
            CREATE TABLE IF NOT EXISTS receipts (
                message_id TEXT NOT NULL,
                participant_id TEXT NOT NULL,
                delivered_at REAL,
                read_at REAL,
                PRIMARY KEY (message_id, participant_id),
                FOREIGN KEY (message_id) REFERENCES messages(message_id) ON DELETE CASCADE
            );
            """
        )
        message_columns = {row["name"] for row in conn.execute("PRAGMA table_info(messages)").fetchall()}
        if "client_message_id" not in message_columns:
            conn.execute("ALTER TABLE messages ADD COLUMN client_message_id TEXT")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_sender_client_id "
            "ON messages(room_id, sender_id, client_message_id)"
        )


def token_hash(token: str) -> str:
    # The client sends a PBKDF2-derived, room-specific verifier, never its password
    # or AES message key. Pepper adds protection to a database-only disclosure.
    return hashlib.sha256((AUTH_PEPPER + token).encode("utf-8")).hexdigest()


def _room_lock(room_id: str) -> asyncio.Lock:
    return room_locks.setdefault(room_id, asyncio.Lock())


def _valid_payload(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    iv, data = payload.get("iv"), payload.get("data")
    if not isinstance(iv, str) or not isinstance(data, str):
        return False
    if len(iv) > 64 or len(data) > 30_000:
        return False
    return True


def _history(room_id: str, participant_id: str) -> list[dict[str, Any]]:
    with db() as conn:
        rows = conn.execute(
            """SELECT m.message_id, m.sender_id, m.ciphertext_json, m.client_message_id, m.created_at,
                      r.delivered_at, r.read_at
               FROM messages m LEFT JOIN receipts r
                 ON r.message_id=m.message_id
                AND r.participant_id = CASE
                    WHEN m.sender_id=? THEN (
                        SELECT p.participant_id FROM participants p
                        WHERE p.room_id=? AND p.participant_id<>? LIMIT 1
                    ) ELSE ? END
               WHERE m.room_id=? ORDER BY m.created_at DESC LIMIT ?""",
            (participant_id, room_id, participant_id, participant_id, room_id, HISTORY_LIMIT),
        ).fetchall()
    items = []
    for row in reversed(rows):
        items.append({
            "message_id": row["message_id"],
            "client_message_id": row["client_message_id"],
            "sender_id": row["sender_id"],
            "payload": json.loads(row["ciphertext_json"]),
            "created_at": row["created_at"],
            "delivered": bool(row["delivered_at"]),
            "read": bool(row["read_at"]),
        })
    return items


def _presence(room_id: str) -> list[dict[str, Any]]:
    with db() as conn:
        rows = conn.execute(
            "SELECT participant_id, display_name FROM participants WHERE room_id=?",
            (room_id,),
        ).fetchall()
    online_ids = set(room_sockets.get(room_id, {}))
    return [
        {"id": row["participant_id"], "name": row["display_name"], "online": row["participant_id"] in online_ids}
        for row in rows
    ]


async def _broadcast(room_id: str, packet: dict[str, Any], exclude: str | None = None) -> None:
    async with _room_lock(room_id):
        sockets = list((room_sockets.get(room_id) or {}).items())
    for participant_id, socket in sockets:
        if participant_id == exclude:
            continue
        try:
            await socket.send_json(packet)
        except Exception:
            # The receive loop will clean up this stale connection.
            pass


@app.on_event("startup")
async def startup() -> None:
    init_db()


@app.get("/")
async def home() -> FileResponse:
    return FileResponse("static/index.html")


@app.get("/health")
async def health() -> dict[str, str]:
    with db() as conn:
        conn.execute("SELECT 1").fetchone()
    return {"status": "ok", "storage": "ok"}



PUBLIC_SITE_URL = "https://securechatbox-ki63.onrender.com"

@app.get("/robots.txt", response_class=PlainTextResponse)
async def robots_txt() -> str:
    # Keep private WebSocket endpoints out of crawler discovery.
    return (
        "User-agent: *\\n"
        "Allow: /\\n"
        "Disallow: /ws/\\n"
        f"Sitemap: {PUBLIC_SITE_URL}/sitemap.xml\\n"
    )


@app.get("/sitemap.xml")
async def sitemap_xml() -> Response:
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f'<url><loc>{PUBLIC_SITE_URL}/</loc></url>'
        '</urlset>'
    )
    return Response(content=xml, media_type="application/xml")

@app.websocket("/ws/{room_id}")
async def chat_socket(websocket: WebSocket, room_id: str) -> None:
    if not ROOM_RE.fullmatch(room_id):
        await websocket.close(code=1008)
        return
    await websocket.accept()
    participant_id: str | None = None
    display_name = "Guest"
    try:
        try:
            hello = await asyncio.wait_for(websocket.receive_json(), timeout=12)
        except (asyncio.TimeoutError, ValueError):
            await websocket.close(code=1008, reason="Authentication handshake timed out")
            return

        if not isinstance(hello, dict) or hello.get("type") != "hello":
            await websocket.close(code=1008, reason="Authentication required")
            return
        action = hello.get("action")
        participant_id = hello.get("participant_id")
        display_name = str(hello.get("name", "Guest")).strip()[:32] or "Guest"
        auth_token = hello.get("auth_token")
        if action not in {"create", "join"} or not isinstance(participant_id, str) or not PARTICIPANT_RE.fullmatch(participant_id):
            await websocket.close(code=1008, reason="Invalid participant information")
            return
        if not isinstance(auth_token, str) or not TOKEN_RE.fullmatch(auth_token):
            await websocket.close(code=1008, reason="Invalid room credential")
            return

        hashed = token_hash(auth_token)
        with db() as conn:
            room = conn.execute("SELECT auth_hash FROM rooms WHERE room_id=?", (room_id,)).fetchone()
            if action == "create":
                if room:
                    await websocket.close(code=1008, reason="Room already exists. Reconnect instead.")
                    return
                conn.execute("INSERT INTO rooms(room_id, auth_hash, created_at) VALUES(?,?,?)", (room_id, hashed, time.time()))
            elif not room or not hmac.compare_digest(room["auth_hash"], hashed):
                await websocket.close(code=1008, reason="Room not found or secret phrase is incorrect")
                return

            existing = conn.execute(
                "SELECT 1 FROM participants WHERE room_id=? AND participant_id=?",
                (room_id, participant_id),
            ).fetchone()
            count = conn.execute("SELECT COUNT(*) AS n FROM participants WHERE room_id=?", (room_id,)).fetchone()["n"]
            if not existing and count >= 2:
                await websocket.close(code=1008, reason="This private room already has two participants")
                return
            now = time.time()
            conn.execute(
                """INSERT INTO participants(room_id, participant_id, display_name, first_seen, last_seen)
                   VALUES(?,?,?,?,?) ON CONFLICT(room_id, participant_id)
                   DO UPDATE SET display_name=excluded.display_name, last_seen=excluded.last_seen""",
                (room_id, participant_id, display_name, now, now),
            )

        async with _room_lock(room_id):
            peers = room_sockets.setdefault(room_id, {})
            old_socket = peers.get(participant_id)
            peers[participant_id] = websocket
        if old_socket and old_socket is not websocket:
            try:
                await old_socket.close(code=4001, reason="Reconnected from another tab/device session")
            except Exception:
                pass

        await websocket.send_json({
            "type": "ready",
            "participant_id": participant_id,
            "history": _history(room_id, participant_id),
            "participants": _presence(room_id),
        })
        await _broadcast(room_id, {"type": "presence", "participants": _presence(room_id)}, exclude=participant_id)

        while True:
            try:
                packet = await asyncio.wait_for(websocket.receive_json(), timeout=HEARTBEAT_TIMEOUT)
            except asyncio.TimeoutError:
                # Mobile browsers may suspend background tabs. Expire the socket so
                # the other participant receives an accurate Offline presence state.
                try:
                    await websocket.close(code=4000, reason="Heartbeat timed out")
                except Exception:
                    pass
                break
            if not isinstance(packet, dict):
                continue
            kind = packet.get("type")
            if kind == "ping":
                await websocket.send_json({"type": "pong", "at": time.time()})
            elif kind == "message":
                payload = packet.get("payload")
                if not _valid_payload(payload):
                    await websocket.send_json({"type": "error", "message": "Invalid encrypted message"})
                    continue
                client_message_id = packet.get("client_message_id")
                if not isinstance(client_message_id, str) or not re.fullmatch(r"[a-f0-9]{16,64}", client_message_id):
                    await websocket.send_json({"type": "error", "message": "Invalid message identifier"})
                    continue
                message_id = str(uuid.uuid4())
                created_at = time.time()
                with db() as conn:
                    existing_message = conn.execute(
                        "SELECT message_id, created_at, ciphertext_json FROM messages "
                        "WHERE room_id=? AND sender_id=? AND client_message_id=?",
                        (room_id, participant_id, client_message_id),
                    ).fetchone()
                    if existing_message:
                        message_id = existing_message["message_id"]
                        created_at = existing_message["created_at"]
                        payload = json.loads(existing_message["ciphertext_json"])
                    else:
                        conn.execute(
                            "INSERT INTO messages(message_id, room_id, sender_id, ciphertext_json, client_message_id, created_at) "
                            "VALUES(?,?,?,?,?,?)",
                            (message_id, room_id, participant_id, json.dumps(payload, separators=(",", ":")), client_message_id, created_at),
                        )
                await websocket.send_json({"type": "message_ack", "message_id": message_id, "client_message_id": client_message_id, "created_at": created_at})
                await _broadcast(room_id, {
                    "type": "message", "message_id": message_id,
                    "client_message_id": client_message_id,
                    "sender_id": participant_id, "payload": payload,
                    "created_at": created_at,
                }, exclude=participant_id)
            elif kind in {"delivered", "read"}:
                message_id = packet.get("message_id")
                if not isinstance(message_id, str) or len(message_id) > 64:
                    continue
                stamp = time.time()
                with db() as conn:
                    row = conn.execute(
                        "SELECT room_id, sender_id FROM messages WHERE message_id=?",
                        (message_id,),
                    ).fetchone()
                    if not row or row["room_id"] != room_id or row["sender_id"] == participant_id:
                        continue
                    if kind == "delivered":
                        conn.execute(
                            "INSERT INTO receipts(message_id, participant_id, delivered_at) VALUES(?,?,?) "
                            "ON CONFLICT(message_id, participant_id) DO UPDATE SET delivered_at=COALESCE(receipts.delivered_at, excluded.delivered_at)",
                            (message_id, participant_id, stamp),
                        )
                    else:
                        conn.execute(
                            "INSERT INTO receipts(message_id, participant_id, delivered_at, read_at) VALUES(?,?,?,?) "
                            "ON CONFLICT(message_id, participant_id) DO UPDATE SET delivered_at=COALESCE(receipts.delivered_at, excluded.delivered_at), read_at=COALESCE(receipts.read_at, excluded.read_at)",
                            (message_id, participant_id, stamp, stamp),
                        )
                await _broadcast(room_id, {"type": "receipt", "message_id": message_id, "status": kind}, exclude=participant_id)
            elif kind == "typing":
                await _broadcast(room_id, {"type": "typing", "participant_id": participant_id, "active": bool(packet.get("active"))}, exclude=participant_id)
    except WebSocketDisconnect:
        pass
    except Exception:
        # Do not leak database paths, secrets, or message material to clients.
        try:
            await websocket.close(code=1011, reason="Server error")
        except Exception:
            pass
    finally:
        if participant_id:
            async with _room_lock(room_id):
                peers = room_sockets.get(room_id, {})
                if peers.get(participant_id) is websocket:
                    peers.pop(participant_id, None)
                if not peers:
                    room_sockets.pop(room_id, None)
            with db() as conn:
                conn.execute(
                    "UPDATE participants SET last_seen=? WHERE room_id=? AND participant_id=?",
                    (time.time(), room_id, participant_id),
                )
            await _broadcast(room_id, {"type": "presence", "participants": _presence(room_id)}, exclude=participant_id)
