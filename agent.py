import argparse
import asyncio
import base64
import contextlib
import json
import queue
import threading
import time
from dataclasses import dataclass
from io import BytesIO
from urllib.parse import urlparse

import mss
import websockets
from PIL import Image
from pynput.keyboard import Controller as KeyboardController
from pynput.keyboard import Key, KeyCode
from pynput.mouse import Button
from pynput.mouse import Controller as MouseController

try:
    import numpy as np
    import soundcard as sc

    AUDIO_IMPORT_OK = True
except Exception:
    AUDIO_IMPORT_OK = False


keyboard = KeyboardController()
mouse = MouseController()


SPECIAL_KEYS = {
    "escape": Key.esc,
    "tab": Key.tab,
    "caps_lock": Key.caps_lock,
    "shift": Key.shift,
    "ctrl": Key.ctrl,
    "alt": Key.alt,
    "cmd": Key.cmd,
    "space": Key.space,
    "enter": Key.enter,
    "backspace": Key.backspace,
    "delete": Key.delete,
    "insert": Key.insert,
    "home": Key.home,
    "end": Key.end,
    "page_up": Key.page_up,
    "page_down": Key.page_down,
    "up": Key.up,
    "down": Key.down,
    "left": Key.left,
    "right": Key.right,
    "menu": Key.menu,
    "num_lock": Key.num_lock,
    "print_screen": Key.print_screen,
    "numpad_enter": Key.enter,
    "numpad_add": "+",
    "numpad_subtract": "-",
    "numpad_multiply": "*",
    "numpad_divide": "/",
    "numpad_decimal": ".",
    "numpad_0": "0",
    "numpad_1": "1",
    "numpad_2": "2",
    "numpad_3": "3",
    "numpad_4": "4",
    "numpad_5": "5",
    "numpad_6": "6",
    "numpad_7": "7",
    "numpad_8": "8",
    "numpad_9": "9",
}


def parse_key(value: str):
    v = value.lower()
    if v in SPECIAL_KEYS:
        raw = SPECIAL_KEYS[v]
        if isinstance(raw, str):
            return KeyCode.from_char(raw)
        return raw
    if v.startswith("f") and v[1:].isdigit():
        f_idx = int(v[1:])
        if 1 <= f_idx <= 24:
            return getattr(Key, f"f{f_idx}")
    if len(value) == 1:
        return KeyCode.from_char(value)
    if len(v) == 1:
        return KeyCode.from_char(v)
    return None


def tap_key(value: str) -> None:
    parsed = parse_key(value)
    if parsed is None:
        print(f"[WARN] Unknown key: {value}")
        return
    keyboard.press(parsed)
    keyboard.release(parsed)


def press_combo(modifiers: list[str], key_value: str) -> None:
    modifier_objs = []
    for mod in modifiers:
        parsed = parse_key(mod)
        if parsed is not None:
            modifier_objs.append(parsed)
    main_key = parse_key(key_value)
    if main_key is None:
        print(f"[WARN] Unknown combo key: {key_value}")
        return
    for m in modifier_objs:
        keyboard.press(m)
    keyboard.press(main_key)
    keyboard.release(main_key)
    for m in reversed(modifier_objs):
        keyboard.release(m)


def do_mouse_click(button_name: str) -> None:
    button_map = {
        "left": Button.left,
        "right": Button.right,
        "middle": Button.middle,
    }
    button = button_map.get(button_name, Button.left)
    mouse.click(button)


def to_ws_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    if parsed.scheme in ("ws", "wss"):
        scheme = parsed.scheme
    elif parsed.scheme == "https":
        scheme = "wss"
    else:
        scheme = "ws"
    host = parsed.netloc or parsed.path.strip("/")
    return f"{scheme}://{host}/ws/agent"


@dataclass
class StreamConfig:
    selected_monitor_id: int | None = None
    follow_cursor: bool = True
    audio_enabled: bool = False
    fps: int = 15


def list_monitors() -> list[dict]:
    with mss.mss() as sct:
        monitors = []
        for idx, mon in enumerate(sct.monitors[1:], start=1):
            monitors.append(
                {
                    "id": idx,
                    "label": f"Display {idx}",
                    "left": int(mon["left"]),
                    "top": int(mon["top"]),
                    "width": int(mon["width"]),
                    "height": int(mon["height"]),
                }
            )
        return monitors


def monitor_containing(monitors: list[dict], x: int, y: int) -> int | None:
    for mon in monitors:
        left = mon["left"]
        top = mon["top"]
        right = left + mon["width"]
        bottom = top + mon["height"]
        if left <= x < right and top <= y < bottom:
            return int(mon["id"])
    return None


def pick_monitor_id(monitors: list[dict], config: StreamConfig, cursor_x: int, cursor_y: int) -> int:
    if not monitors:
        return 1
    ids = {int(m["id"]) for m in monitors}
    if config.follow_cursor:
        current = monitor_containing(monitors, cursor_x, cursor_y)
        if current is not None:
            return current
    if config.selected_monitor_id in ids:
        return int(config.selected_monitor_id)
    return int(monitors[0]["id"])


def capture_frame_with_cursor(config: StreamConfig) -> dict | None:
    try:
        with mss.mss() as sct:
            monitor_map = []
            for idx, mon in enumerate(sct.monitors[1:], start=1):
                monitor_map.append(
                    {
                        "id": idx,
                        "label": f"Display {idx}",
                        "left": int(mon["left"]),
                        "top": int(mon["top"]),
                        "width": int(mon["width"]),
                        "height": int(mon["height"]),
                    }
                )
            if not monitor_map:
                return None

            cursor_x, cursor_y = mouse.position
            selected_id = pick_monitor_id(monitor_map, config, int(cursor_x), int(cursor_y))
            mon = monitor_map[selected_id - 1]

            shot = sct.grab(mon)
            image = Image.frombytes("RGB", shot.size, shot.rgb)
            image.thumbnail((1280, 720))
            output = BytesIO()
            image.save(output, format="JPEG", quality=60, optimize=True)
            jpeg_b64 = base64.b64encode(output.getvalue()).decode("ascii")

            rel_x = int(cursor_x) - int(mon["left"])
            rel_y = int(cursor_y) - int(mon["top"])
            visible = 0 <= rel_x < int(mon["width"]) and 0 <= rel_y < int(mon["height"])
            cursor_payload = {
                "visible": bool(visible),
                "x_norm": max(0.0, min(1.0, rel_x / max(1, int(mon["width"])))),
                "y_norm": max(0.0, min(1.0, rel_y / max(1, int(mon["height"])))),
            }

            return {
                "jpeg": jpeg_b64,
                "monitor_id": selected_id,
                "cursor": cursor_payload,
                "monitors": monitor_map,
                "follow_cursor": config.follow_cursor,
            }
    except Exception as ex:
        print(f"[WARN] Screen capture failed: {ex}")
        return None


def audio_capture_worker(
    out_queue: queue.Queue[bytes], stop_event: threading.Event, sample_rate: int = 24000
) -> None:
    if not AUDIO_IMPORT_OK:
        return
    try:
        speaker = sc.default_speaker()
        if speaker is None:
            return
        mic = sc.get_microphone(str(speaker.name), include_loopback=True)
        with mic.recorder(samplerate=sample_rate, channels=2, blocksize=1024) as rec:
            while not stop_event.is_set():
                data = rec.record(numframes=1024)
                mono = data.mean(axis=1)
                pcm = np.clip(mono * 32767.0, -32768, 32767).astype(np.int16).tobytes()
                try:
                    out_queue.put(pcm, timeout=0.2)
                except queue.Full:
                    continue
    except Exception as ex:
        print(f"[WARN] Audio worker stopped: {ex}")


async def run_agent(server: str, room_code: str, password: str, fps: int) -> None:
    ws_url = to_ws_url(server)
    config = StreamConfig(fps=max(1, int(fps)))
    print(f"[INFO] Connecting to {ws_url}")
    while True:
        try:
            async with websockets.connect(ws_url, ping_interval=20, ping_timeout=20) as ws:
                await ws.send(
                    json.dumps(
                        {
                            "type": "agent_auth",
                            "room_code": room_code.upper(),
                            "password": password,
                        }
                    )
                )
                print("[INFO] Agent connected and authenticated.")
                await safe_send_agent_info(ws, config)
                stream_task = asyncio.create_task(stream_screen(ws, config, fps=config.fps))
                audio_task = asyncio.create_task(stream_audio(ws, config))
                try:
                    async for raw in ws:
                        data = json.loads(raw)
                        msg_type = data.get("type")
                        if msg_type == "error":
                            print(f"[ERROR] {data.get('message', 'Unknown server error')}")
                            break
                        if msg_type == "room_closed":
                            print("[INFO] Room closed by host.")
                            break
                        if msg_type == "agent_config":
                            monitor_id = data.get("monitor_id")
                            follow = data.get("follow_cursor")
                            audio_enabled = data.get("audio_enabled")
                            if isinstance(monitor_id, int) and monitor_id > 0:
                                config.selected_monitor_id = monitor_id
                            if isinstance(follow, bool):
                                config.follow_cursor = follow
                            if isinstance(audio_enabled, bool):
                                config.audio_enabled = audio_enabled
                            await safe_send_agent_info(ws, config)
                            continue
                        if msg_type != "control":
                            continue

                        event = data.get("event", {})
                        kind = event.get("kind")
                        if kind == "mouse_move":
                            dx = int(float(event.get("dx", 0)))
                            dy = int(float(event.get("dy", 0)))
                            mouse.move(dx, dy)
                        elif kind == "mouse_click":
                            do_mouse_click(str(event.get("button", "left")))
                        elif kind == "mouse_scroll":
                            dx = int(float(event.get("dx", 0)))
                            dy = int(float(event.get("dy", 0)))
                            mouse.scroll(dx, dy)
                        elif kind == "key_tap":
                            tap_key(str(event.get("key", "")))
                        elif kind == "key_combo":
                            modifiers = event.get("modifiers", [])
                            if isinstance(modifiers, list):
                                press_combo([str(m) for m in modifiers], str(event.get("key", "")))
                finally:
                    stream_task.cancel()
                    audio_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await stream_task
                    with contextlib.suppress(asyncio.CancelledError):
                        await audio_task
        except Exception as ex:
            print(f"[WARN] Disconnected: {ex}")
            await asyncio.sleep(2)


async def safe_send_agent_info(ws, config: StreamConfig) -> None:
    monitors = await asyncio.to_thread(list_monitors)
    selected = config.selected_monitor_id
    valid_ids = {int(m["id"]) for m in monitors}
    if selected not in valid_ids and monitors:
        selected = int(monitors[0]["id"])
        config.selected_monitor_id = selected
    await ws.send(
        json.dumps(
            {
                "type": "agent_info",
                "monitors": monitors,
                "selected_monitor_id": selected,
                "follow_cursor": config.follow_cursor,
                "audio_available": AUDIO_IMPORT_OK,
            }
        )
    )


async def stream_screen(ws, config: StreamConfig, fps: int = 5) -> None:
    interval = 1 / max(1, fps)
    last_monitor_layout = ""
    last_sent_info = 0.0
    while True:
        frame = await asyncio.to_thread(capture_frame_with_cursor, config)
        if frame:
            monitor_layout = json.dumps(frame["monitors"], sort_keys=True)
            now = time.time()
            if monitor_layout != last_monitor_layout or now - last_sent_info > 5:
                last_monitor_layout = monitor_layout
                last_sent_info = now
                await ws.send(
                    json.dumps(
                        {
                            "type": "agent_info",
                            "monitors": frame["monitors"],
                            "selected_monitor_id": frame["monitor_id"],
                            "follow_cursor": frame["follow_cursor"],
                            "audio_available": AUDIO_IMPORT_OK,
                        }
                    )
                )
            await ws.send(
                json.dumps(
                    {
                        "type": "screen_frame",
                        "jpeg": frame["jpeg"],
                        "ts": time.time(),
                        "cursor": frame["cursor"],
                        "monitor_id": frame["monitor_id"],
                    }
                )
            )
        await asyncio.sleep(interval)


async def stream_audio(ws, config: StreamConfig) -> None:
    if not AUDIO_IMPORT_OK:
        return

    pcm_queue: queue.Queue[bytes] = queue.Queue(maxsize=40)
    stop_event = threading.Event()
    worker = threading.Thread(
        target=audio_capture_worker,
        args=(pcm_queue, stop_event, 24000),
        daemon=True,
    )
    worker.start()
    try:
        while True:
            if not config.audio_enabled:
                await asyncio.sleep(0.2)
                continue

            try:
                pcm = await asyncio.to_thread(pcm_queue.get, True, 1.0)
            except queue.Empty:
                continue

            await ws.send(
                json.dumps(
                    {
                        "type": "audio_chunk",
                        "pcm16": base64.b64encode(pcm).decode("ascii"),
                        "sample_rate": 24000,
                        "channels": 1,
                        "ts": time.time(),
                    }
                )
            )
    finally:
        stop_event.set()


def main() -> None:
    parser = argparse.ArgumentParser(description="Remote desktop input agent.")
    parser.add_argument("--server", required=True, help="Render URL, e.g. https://your-app.onrender.com")
    parser.add_argument("--room", required=True, help="Room code")
    parser.add_argument("--password", required=True, help="Room password")
    parser.add_argument("--fps", type=int, default=15, help="Target preview FPS (default 15)")
    args = parser.parse_args()

    asyncio.run(run_agent(args.server, args.room, args.password, args.fps))


if __name__ == "__main__":
    main()
