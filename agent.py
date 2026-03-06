import argparse
import asyncio
import json
from urllib.parse import urlparse

import websockets
from pynput.keyboard import Controller as KeyboardController
from pynput.keyboard import Key, KeyCode
from pynput.mouse import Button
from pynput.mouse import Controller as MouseController


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


async def run_agent(server: str, room_code: str, password: str) -> None:
    ws_url = to_ws_url(server)
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
                async for raw in ws:
                    data = json.loads(raw)
                    msg_type = data.get("type")
                    if msg_type == "error":
                        print(f"[ERROR] {data.get('message', 'Unknown server error')}")
                        break
                    if msg_type == "room_closed":
                        print("[INFO] Room closed by host.")
                        break
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
        except Exception as ex:
            print(f"[WARN] Disconnected: {ex}")
            await asyncio.sleep(2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Remote desktop input agent.")
    parser.add_argument("--server", required=True, help="Render URL, e.g. https://your-app.onrender.com")
    parser.add_argument("--room", required=True, help="Room code")
    parser.add_argument("--password", required=True, help="Room password")
    args = parser.parse_args()

    asyncio.run(run_agent(args.server, args.room, args.password))


if __name__ == "__main__":
    main()
