import hashlib
import json
import secrets
import string
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(title="Remote Control Hub")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


def hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000
    ).hex()


def verify_password(password: str, salt: str, hashed: str) -> bool:
    return hash_password(password, salt) == hashed


def random_code(length: int = 6) -> str:
    chars = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(chars) for _ in range(length))


@dataclass
class MobileClient:
    client_id: str
    name: str
    websocket: WebSocket
    audio_enabled: bool = False


@dataclass
class Room:
    code: str
    pc_name: str
    salt: str
    password_hash: str
    created_at: float
    host_socket: WebSocket | None = None
    agent_socket: WebSocket | None = None
    mobiles: dict[str, MobileClient] = field(default_factory=dict)
    latest_frame_jpeg: str | None = None
    latest_frame_ts: float | None = None
    latest_frame_cursor: dict[str, Any] | None = None
    latest_frame_monitor_id: int | None = None
    latest_frame_monitor_width: int | None = None
    latest_frame_monitor_height: int | None = None
    available_monitors: list[dict[str, Any]] = field(default_factory=list)
    selected_monitor_id: int | None = None
    follow_cursor: bool = True
    audio_available: bool = False
    audio_allowed: bool = False
    audio_error: str | None = None

    def mobile_payload(self) -> list[dict[str, Any]]:
        return [
            {"id": m.client_id, "name": m.name}
            for m in sorted(self.mobiles.values(), key=lambda v: v.name.lower())
        ]


rooms: dict[str, Room] = {}
ws_to_room: dict[int, str] = {}
ws_to_mobile_id: dict[int, str] = {}


async def safe_send(websocket: WebSocket | None, payload: dict[str, Any]) -> bool:
    if websocket is None:
        return False
    try:
        await websocket.send_json(payload)
        return True
    except Exception:
        return False


def room_status(room: Room) -> dict[str, Any]:
    return {
        "type": "room_status",
        "room_code": room.code,
        "pc_name": room.pc_name,
        "agent_connected": room.agent_socket is not None,
        "mobile_count": len(room.mobiles),
        "mobiles": room.mobile_payload(),
        "created_at": room.created_at,
        "monitors": room.available_monitors,
        "selected_monitor_id": room.selected_monitor_id,
        "follow_cursor": room.follow_cursor,
        "audio_available": room.audio_available,
        "audio_allowed": room.audio_allowed,
        "audio_error": room.audio_error,
        "audio_subscribers": sum(1 for m in room.mobiles.values() if m.audio_enabled),
    }


async def broadcast_room_status(room: Room) -> None:
    payload = room_status(room)
    await safe_send(room.host_socket, payload)
    await safe_send(room.agent_socket, payload)
    for mobile in list(room.mobiles.values()):
        await safe_send(mobile.websocket, payload)


async def broadcast_screen_frame(room: Room, payload: dict[str, Any]) -> None:
    for mobile in list(room.mobiles.values()):
        await safe_send(mobile.websocket, payload)


def room_audio_needed(room: Room) -> bool:
    return room.audio_allowed and any(m.audio_enabled for m in room.mobiles.values())


async def push_agent_config(room: Room) -> None:
    await safe_send(
        room.agent_socket,
        {
            "type": "agent_config",
            "monitor_id": room.selected_monitor_id,
            "follow_cursor": room.follow_cursor,
            "audio_enabled": room_audio_needed(room),
        },
    )


async def broadcast_audio_chunk(room: Room, payload: dict[str, Any]) -> None:
    for mobile in list(room.mobiles.values()):
        if mobile.audio_enabled:
            await safe_send(mobile.websocket, payload)


def create_room(pc_name: str, password: str) -> Room:
    while True:
        code = random_code()
        if code not in rooms:
            break

    salt = secrets.token_hex(16)
    password_hash = hash_password(password, salt)
    room = Room(
        code=code,
        pc_name=pc_name.strip()[:60] or "My PC",
        salt=salt,
        password_hash=password_hash,
        created_at=time.time(),
    )
    rooms[code] = room
    return room


def is_mobile_user_agent(user_agent: str) -> bool:
    ua = user_agent.lower()
    markers = ("android", "iphone", "ipad", "mobile")
    return any(m in ua for m in markers)


@app.get("/", response_class=RedirectResponse)
async def index(request: Request) -> RedirectResponse:
    user_agent = request.headers.get("user-agent", "")
    if is_mobile_user_agent(user_agent):
        return RedirectResponse("/mobile")
    return RedirectResponse("/pc")


@app.get("/pc", response_class=HTMLResponse)
async def pc_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("pc.html", {"request": request})


@app.get("/mobile", response_class=HTMLResponse)
async def mobile_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("mobile.html", {"request": request})


@app.get("/api/rooms", response_class=JSONResponse)
async def list_rooms() -> JSONResponse:
    payload = []
    for room in rooms.values():
        payload.append(
            {
                "room_code": room.code,
                "pc_name": room.pc_name,
                "agent_connected": room.agent_socket is not None,
                "mobile_count": len(room.mobiles),
                "created_at": room.created_at,
            }
        )
    payload.sort(key=lambda r: r["created_at"], reverse=True)
    return JSONResponse({"rooms": payload})


@app.websocket("/ws/pc")
async def ws_pc(websocket: WebSocket) -> None:
    await websocket.accept()
    current_room: Room | None = None
    socket_id = id(websocket)

    try:
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            msg_type = data.get("type")

            if msg_type == "create_room":
                pc_name = str(data.get("pc_name", "")).strip()
                password = str(data.get("password", "")).strip()
                if len(password) < 4:
                    await safe_send(
                        websocket,
                        {"type": "error", "message": "Password must be at least 4 chars."},
                    )
                    continue

                if current_room:
                    await safe_send(
                        websocket,
                        {"type": "error", "message": "Room already created for this session."},
                    )
                    continue

                room = create_room(pc_name=pc_name or "My PC", password=password)
                room.host_socket = websocket
                ws_to_room[socket_id] = room.code
                current_room = room

                await safe_send(
                    websocket,
                    {
                        "type": "room_created",
                        "room_code": room.code,
                        "pc_name": room.pc_name,
                    },
                )
                await broadcast_room_status(room)
            elif msg_type == "close_room":
                if not current_room:
                    continue
                code = current_room.code
                for mobile in list(current_room.mobiles.values()):
                    await safe_send(
                        mobile.websocket,
                        {"type": "room_closed", "message": "Host closed this room."},
                    )
                await safe_send(
                    current_room.agent_socket,
                    {"type": "room_closed", "message": "Host closed this room."},
                )
                rooms.pop(code, None)
                ws_to_room.pop(socket_id, None)
                current_room = None
            elif msg_type == "ping":
                await safe_send(websocket, {"type": "pong"})
            elif msg_type == "set_audio_allowed":
                if not current_room:
                    continue
                enabled = bool(data.get("enabled"))
                current_room.audio_allowed = enabled
                await push_agent_config(current_room)
                await broadcast_room_status(current_room)
            else:
                await safe_send(websocket, {"type": "error", "message": "Unknown message type."})
    except WebSocketDisconnect:
        pass
    finally:
        code = ws_to_room.pop(socket_id, None)
        if code and code in rooms:
            room = rooms[code]
            if room.host_socket is websocket:
                for mobile in list(room.mobiles.values()):
                    await safe_send(
                        mobile.websocket,
                        {"type": "room_closed", "message": "Host disconnected."},
                    )
                await safe_send(
                    room.agent_socket,
                    {"type": "room_closed", "message": "Host disconnected."},
                )
                rooms.pop(code, None)


@app.websocket("/ws/mobile")
async def ws_mobile(websocket: WebSocket) -> None:
    await websocket.accept()
    socket_id = id(websocket)
    joined_room: Room | None = None
    mobile_id: str | None = None
    mobile_name: str = "Phone"

    try:
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            msg_type = data.get("type")

            if msg_type == "join_room":
                if joined_room:
                    await safe_send(websocket, {"type": "error", "message": "Already joined."})
                    continue

                room_code = str(data.get("room_code", "")).strip().upper()
                password = str(data.get("password", "")).strip()
                mobile_name = (str(data.get("device_name", "")).strip() or "Phone")[:40]
                room = rooms.get(room_code)
                if room is None:
                    await safe_send(websocket, {"type": "error", "message": "Room not found."})
                    continue
                if not verify_password(password, room.salt, room.password_hash):
                    await safe_send(websocket, {"type": "error", "message": "Wrong password."})
                    continue

                joined_room = room
                mobile_id = uuid.uuid4().hex[:8]
                ws_to_room[socket_id] = room.code
                ws_to_mobile_id[socket_id] = mobile_id
                room.mobiles[mobile_id] = MobileClient(
                    client_id=mobile_id, name=mobile_name, websocket=websocket, audio_enabled=False
                )

                await safe_send(
                    websocket,
                    {
                        "type": "joined_room",
                        "room_code": room.code,
                        "pc_name": room.pc_name,
                        "mobile_id": mobile_id,
                        "agent_connected": room.agent_socket is not None,
                    },
                )
                if room.latest_frame_jpeg:
                    await safe_send(
                        websocket,
                        {
                            "type": "screen_frame",
                            "jpeg": room.latest_frame_jpeg,
                            "ts": room.latest_frame_ts,
                            "cursor": room.latest_frame_cursor,
                            "monitor_id": room.latest_frame_monitor_id,
                            "monitor_width": room.latest_frame_monitor_width,
                            "monitor_height": room.latest_frame_monitor_height,
                        },
                    )
                await broadcast_room_status(room)
            elif msg_type == "control":
                if not joined_room or not mobile_id:
                    await safe_send(websocket, {"type": "error", "message": "Join a room first."})
                    continue
                event = data.get("event", {})
                if not isinstance(event, dict):
                    continue

                forwarded = await safe_send(
                    joined_room.agent_socket,
                    {
                        "type": "control",
                        "from_mobile_id": mobile_id,
                        "from_mobile_name": mobile_name,
                        "event": event,
                    },
                )
                if not forwarded:
                    await safe_send(
                        websocket,
                        {
                            "type": "warning",
                            "message": "PC agent is offline. Start agent.py on host machine.",
                        },
                    )
            elif msg_type == "monitor_config":
                if not joined_room:
                    await safe_send(websocket, {"type": "error", "message": "Join a room first."})
                    continue

                monitor_id_raw = data.get("monitor_id")
                follow_cursor = data.get("follow_cursor")
                monitor_id: int | None = None
                if isinstance(monitor_id_raw, (int, float)):
                    monitor_id = int(monitor_id_raw)
                if isinstance(follow_cursor, bool):
                    joined_room.follow_cursor = follow_cursor
                if monitor_id is not None and monitor_id > 0:
                    joined_room.selected_monitor_id = monitor_id

                await safe_send(
                    joined_room.agent_socket,
                    {
                        "type": "agent_config",
                        "monitor_id": joined_room.selected_monitor_id,
                        "follow_cursor": joined_room.follow_cursor,
                        "audio_enabled": room_audio_needed(joined_room),
                    },
                )
                await broadcast_room_status(joined_room)
            elif msg_type == "audio_subscribe":
                if not joined_room or not mobile_id:
                    await safe_send(websocket, {"type": "error", "message": "Join a room first."})
                    continue
                enabled = bool(data.get("enabled"))
                if enabled and not joined_room.audio_allowed:
                    await safe_send(
                        websocket,
                        {"type": "warning", "message": "Host has not enabled audio for this room."},
                    )
                    continue
                mobile_obj = joined_room.mobiles.get(mobile_id)
                if mobile_obj is not None:
                    mobile_obj.audio_enabled = enabled
                await push_agent_config(joined_room)
                await broadcast_room_status(joined_room)
            elif msg_type == "ping":
                await safe_send(websocket, {"type": "pong"})
            else:
                await safe_send(websocket, {"type": "error", "message": "Unknown message type."})
    except WebSocketDisconnect:
        pass
    finally:
        code = ws_to_room.pop(socket_id, None)
        mid = ws_to_mobile_id.pop(socket_id, None)
        if code and mid and code in rooms:
            room = rooms[code]
            room.mobiles.pop(mid, None)
            await broadcast_room_status(room)


@app.websocket("/ws/agent")
async def ws_agent(websocket: WebSocket) -> None:
    await websocket.accept()
    socket_id = id(websocket)
    joined_room: Room | None = None

    try:
        auth_text = await websocket.receive_text()
        auth = json.loads(auth_text)
        if auth.get("type") != "agent_auth":
            await safe_send(websocket, {"type": "error", "message": "Expected agent_auth first."})
            await websocket.close()
            return

        room_code = str(auth.get("room_code", "")).strip().upper()
        password = str(auth.get("password", "")).strip()
        room = rooms.get(room_code)
        if room is None or not verify_password(password, room.salt, room.password_hash):
            await safe_send(websocket, {"type": "error", "message": "Invalid room or password."})
            await websocket.close()
            return

        room.agent_socket = websocket
        joined_room = room
        ws_to_room[socket_id] = room.code

        await safe_send(
            websocket,
            {
                "type": "agent_connected",
                "room_code": room.code,
                "pc_name": room.pc_name,
            },
        )
        await broadcast_room_status(room)
        await push_agent_config(room)

        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            msg_type = data.get("type")
            if msg_type == "ping":
                await safe_send(websocket, {"type": "pong"})
            elif msg_type == "agent_info" and joined_room is not None:
                monitors = data.get("monitors", [])
                selected = data.get("selected_monitor_id")
                follow = data.get("follow_cursor")
                audio_available = data.get("audio_available")
                audio_error = data.get("audio_error")
                if isinstance(monitors, list):
                    joined_room.available_monitors = [
                        m for m in monitors if isinstance(m, dict)
                    ]
                if isinstance(selected, int):
                    joined_room.selected_monitor_id = selected
                if isinstance(follow, bool):
                    joined_room.follow_cursor = follow
                if isinstance(audio_available, bool):
                    joined_room.audio_available = audio_available
                if isinstance(audio_error, str):
                    joined_room.audio_error = audio_error
                elif audio_error is None:
                    joined_room.audio_error = None
                await broadcast_room_status(joined_room)
            elif msg_type == "screen_frame" and joined_room is not None:
                jpeg = data.get("jpeg")
                if isinstance(jpeg, str) and jpeg:
                    joined_room.latest_frame_jpeg = jpeg
                    joined_room.latest_frame_ts = float(data.get("ts", time.time()))
                    cursor = data.get("cursor")
                    monitor_id = data.get("monitor_id")
                    monitor_width = data.get("monitor_width")
                    monitor_height = data.get("monitor_height")
                    if isinstance(cursor, dict):
                        joined_room.latest_frame_cursor = cursor
                    else:
                        joined_room.latest_frame_cursor = None
                    if isinstance(monitor_id, int):
                        joined_room.latest_frame_monitor_id = monitor_id
                    if isinstance(monitor_width, (int, float)):
                        joined_room.latest_frame_monitor_width = int(monitor_width)
                    if isinstance(monitor_height, (int, float)):
                        joined_room.latest_frame_monitor_height = int(monitor_height)
                    await broadcast_screen_frame(
                        joined_room,
                        {
                            "type": "screen_frame",
                            "jpeg": jpeg,
                            "ts": joined_room.latest_frame_ts,
                            "cursor": joined_room.latest_frame_cursor,
                            "monitor_id": joined_room.latest_frame_monitor_id,
                            "monitor_width": joined_room.latest_frame_monitor_width,
                            "monitor_height": joined_room.latest_frame_monitor_height,
                        },
                    )
            elif msg_type == "audio_chunk" and joined_room is not None:
                pcm16 = data.get("pcm16")
                sample_rate = data.get("sample_rate")
                channels = data.get("channels")
                if isinstance(pcm16, str) and pcm16:
                    await broadcast_audio_chunk(
                        joined_room,
                        {
                            "type": "audio_chunk",
                            "pcm16": pcm16,
                            "sample_rate": int(sample_rate) if isinstance(sample_rate, (int, float)) else 24000,
                            "channels": int(channels) if isinstance(channels, (int, float)) else 1,
                            "ts": float(data.get("ts", time.time())),
                        },
                    )
            elif msg_type == "audio_state" and joined_room is not None:
                available = data.get("available")
                error = data.get("error")
                if isinstance(available, bool):
                    joined_room.audio_available = available
                if isinstance(error, str):
                    joined_room.audio_error = error
                elif error is None:
                    joined_room.audio_error = None
                await broadcast_room_status(joined_room)
    except WebSocketDisconnect:
        pass
    finally:
        code = ws_to_room.pop(socket_id, None)
        if code and code in rooms:
            room = rooms[code]
            if room.agent_socket is websocket:
                room.agent_socket = None
                await broadcast_room_status(room)
