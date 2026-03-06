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

    NUMPY_OK = True
except Exception:
    NUMPY_OK = False

try:
    import soundcard as sc

    SOUNDCARD_OK = True
except Exception:
    SOUNDCARD_OK = False

try:
    import sounddevice as sd

    SOUNDDEVICE_OK = True
except Exception:
    SOUNDDEVICE_OK = False


keyboard = KeyboardController()
mouse = MouseController()
held_keys: dict[str, object] = {}
held_mouse_buttons: set[str] = set()


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


def key_down(value: str) -> None:
    parsed = parse_key(value)
    if parsed is None:
        print(f"[WARN] Unknown key down: {value}")
        return
    key_id = value.lower()
    if key_id in held_keys:
        return
    keyboard.press(parsed)
    held_keys[key_id] = parsed


def key_up(value: str) -> None:
    key_id = value.lower()
    parsed = held_keys.pop(key_id, None)
    if parsed is None:
        parsed = parse_key(value)
    if parsed is None:
        return
    keyboard.release(parsed)


def release_all_held_keys() -> None:
    for _, parsed in list(held_keys.items()):
        try:
            keyboard.release(parsed)
        except Exception:
            pass
    held_keys.clear()


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


def mouse_button_down(button_name: str) -> None:
    button_map = {
        "left": Button.left,
        "right": Button.right,
        "middle": Button.middle,
    }
    button = button_map.get(button_name, Button.left)
    if button_name in held_mouse_buttons:
        return
    mouse.press(button)
    held_mouse_buttons.add(button_name)


def mouse_button_up(button_name: str) -> None:
    button_map = {
        "left": Button.left,
        "right": Button.right,
        "middle": Button.middle,
    }
    button = button_map.get(button_name, Button.left)
    try:
        mouse.release(button)
    finally:
        held_mouse_buttons.discard(button_name)


def release_all_mouse_buttons() -> None:
    for button_name in list(held_mouse_buttons):
        mouse_button_up(button_name)


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
    fps: int = 30


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
                "monitor_width": int(mon["width"]),
                "monitor_height": int(mon["height"]),
                "cursor": cursor_payload,
                "monitors": monitor_map,
                "follow_cursor": config.follow_cursor,
            }
    except Exception as ex:
        print(f"[WARN] Screen capture failed: {ex}")
        return None


def _audio_worker_soundcard(
    out_queue: queue.Queue[bytes], stop_event: threading.Event, status_queue: queue.Queue[str], sample_rate: int
) -> None:
    speaker = sc.default_speaker()
    if speaker is None:
        status_queue.put("error:No default speaker device found.")
        return
    status_queue.put(f"backend:soundcard ({speaker.name})")
    mic = sc.get_microphone(str(getattr(speaker, "id", speaker.name)), include_loopback=True)
    with mic.recorder(samplerate=sample_rate, channels=2, blocksize=1024) as rec:
        while not stop_event.is_set():
            data = rec.record(numframes=1024)
            mono = data.mean(axis=1)
            pcm = np.clip(mono * 32767.0, -32768, 32767).astype(np.int16).tobytes()
            try:
                out_queue.put(pcm, timeout=0.2)
            except queue.Full:
                continue


def _find_sounddevice_loopback_device() -> int | None:
    if not SOUNDDEVICE_OK:
        return None
    try:
        devices = sd.query_devices()
        hostapis = sd.query_hostapis()
        for idx, dev in enumerate(devices):
            if int(dev.get("max_input_channels", 0)) < 1:
                continue
            name = str(dev.get("name", "")).lower()
            host_idx = int(dev.get("hostapi", -1))
            host_name = ""
            if 0 <= host_idx < len(hostapis):
                host_name = str(hostapis[host_idx].get("name", "")).lower()
            if "loopback" in name and "wasapi" in host_name:
                return idx
    except Exception:
        return None
    return None


def _audio_worker_sounddevice(
    out_queue: queue.Queue[bytes], stop_event: threading.Event, status_queue: queue.Queue[str], sample_rate: int
) -> None:
    try:
        device_idx = _find_sounddevice_loopback_device()
        if device_idx is None:
            default_out = sd.default.device[1]
            if default_out is None or int(default_out) < 0:
                status_queue.put("error:No WASAPI loopback device available.")
                return
            device_idx = int(default_out)
        dev_info = sd.query_devices(device_idx)
        wasapi = sd.WasapiSettings(loopback=True)
        status_queue.put(f"backend:sounddevice-wasapi ({dev_info['name']})")

        def callback(indata, frames, _time, _status):
            if stop_event.is_set():
                return
            if indata is None or len(indata) == 0:
                return
            mono = indata[:, 0] if indata.ndim > 1 else indata
            if mono.dtype != np.int16:
                mono = np.clip(mono, -1.0, 1.0)
                mono = (mono * 32767).astype(np.int16)
            data = mono.tobytes()
            try:
                out_queue.put_nowait(data)
            except queue.Full:
                pass

        with sd.InputStream(
            device=device_idx,
            channels=1,
            samplerate=sample_rate,
            blocksize=1024,
            dtype="float32",
            extra_settings=wasapi,
            callback=callback,
        ):
            while not stop_event.is_set():
                time.sleep(0.05)
    except Exception as ex:
        status_queue.put(f"error:{ex}")


def audio_capture_worker(
    out_queue: queue.Queue[bytes], stop_event: threading.Event, status_queue: queue.Queue[str], sample_rate: int = 24000
) -> None:
    if SOUNDCARD_OK and NUMPY_OK:
        try:
            _audio_worker_soundcard(out_queue, stop_event, status_queue, sample_rate)
            return
        except Exception as ex:
            status_queue.put(f"error:soundcard backend failed: {ex}")
    if SOUNDDEVICE_OK and NUMPY_OK:
        try:
            _audio_worker_sounddevice(out_queue, stop_event, status_queue, sample_rate)
            return
        except Exception as ex:
            status_queue.put(f"error:sounddevice backend failed: {ex}")
    status_queue.put("error:No supported audio capture backend is available.")


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
                        elif kind == "mouse_button_down":
                            mouse_button_down(str(event.get("button", "left")))
                        elif kind == "mouse_button_up":
                            mouse_button_up(str(event.get("button", "left")))
                        elif kind == "mouse_scroll":
                            dx = int(float(event.get("dx", 0)))
                            dy = int(float(event.get("dy", 0)))
                            mouse.scroll(dx, dy)
                        elif kind == "key_tap":
                            tap_key(str(event.get("key", "")))
                        elif kind == "key_down":
                            key_down(str(event.get("key", "")))
                        elif kind == "key_up":
                            key_up(str(event.get("key", "")))
                        elif kind == "key_combo":
                            modifiers = event.get("modifiers", [])
                            if isinstance(modifiers, list):
                                press_combo([str(m) for m in modifiers], str(event.get("key", "")))
                finally:
                    release_all_held_keys()
                    release_all_mouse_buttons()
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
                "audio_available": (SOUNDCARD_OK and NUMPY_OK) or (SOUNDDEVICE_OK and NUMPY_OK),
                "audio_error": None,
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
                            "audio_available": (SOUNDCARD_OK and NUMPY_OK) or (SOUNDDEVICE_OK and NUMPY_OK),
                            "audio_error": None,
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
                        "monitor_width": frame["monitor_width"],
                        "monitor_height": frame["monitor_height"],
                    }
                )
            )
        await asyncio.sleep(interval)


async def stream_audio(ws, config: StreamConfig) -> None:
    if not ((SOUNDCARD_OK and NUMPY_OK) or (SOUNDDEVICE_OK and NUMPY_OK)):
        await ws.send(
            json.dumps(
                {
                    "type": "audio_state",
                    "available": False,
                    "error": "Audio capture backend not installed on host PC.",
                }
            )
        )
        return

    pcm_queue: queue.Queue[bytes] = queue.Queue(maxsize=40)
    status_queue: queue.Queue[str] = queue.Queue(maxsize=20)
    stop_event = threading.Event()
    worker = threading.Thread(
        target=audio_capture_worker,
        args=(pcm_queue, stop_event, status_queue, 24000),
        daemon=True,
    )
    worker.start()
    last_audio_data = time.time()
    warned_no_data = False
    await ws.send(json.dumps({"type": "audio_state", "available": True, "error": None}))
    try:
        while True:
            while not status_queue.empty():
                msg = status_queue.get_nowait()
                if msg.startswith("backend:"):
                    await ws.send(
                        json.dumps(
                            {
                                "type": "audio_state",
                                "available": True,
                                "error": msg.replace("backend:", "Using ").strip(),
                            }
                        )
                    )
                elif msg.startswith("error:"):
                    await ws.send(
                        json.dumps(
                            {
                                "type": "audio_state",
                                "available": False,
                                "error": msg.replace("error:", "").strip(),
                            }
                        )
                    )
            if not config.audio_enabled:
                await asyncio.sleep(0.2)
                continue

            try:
                pcm = await asyncio.to_thread(pcm_queue.get, True, 1.0)
            except queue.Empty:
                if time.time() - last_audio_data > 3:
                    if not warned_no_data:
                        await ws.send(
                            json.dumps(
                                {
                                    "type": "audio_state",
                                    "available": True,
                                    "error": "Waiting for desktop audio output...",
                                }
                            )
                        )
                        warned_no_data = True
                continue
            last_audio_data = time.time()
            if warned_no_data:
                warned_no_data = False
                await ws.send(json.dumps({"type": "audio_state", "available": True, "error": None}))

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
    parser.add_argument("--fps", type=int, default=30, help="Target preview FPS (default 30)")
    args = parser.parse_args()

    asyncio.run(run_agent(args.server, args.room, args.password, args.fps))


if __name__ == "__main__":
    main()
