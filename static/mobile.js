const joinSection = document.getElementById("join-section");
const controlSection = document.getElementById("control-section");
const joinBtn = document.getElementById("join-btn");
const roomCodeInput = document.getElementById("room-code-input");
const roomPasswordInput = document.getElementById("room-password-input");
const deviceNameInput = document.getElementById("device-name-input");
const infoPc = document.getElementById("info-pc");
const infoRoom = document.getElementById("info-room");
const infoAgent = document.getElementById("info-agent");
const statusLine = document.getElementById("status-line");
const trackpad = document.getElementById("trackpad");
const keyboard = document.getElementById("keyboard");
const layoutSelect = document.getElementById("layout-select");

let ws = null;
let joined = false;
const activeModifiers = new Set();

const modifierKeys = new Set(["ctrl", "shift", "alt", "cmd"]);

const layouts = {
  qwerty: [
    [
      { label: "Esc", value: "escape" },
      { label: "F1", value: "f1" }, { label: "F2", value: "f2" }, { label: "F3", value: "f3" },
      { label: "F4", value: "f4" }, { label: "F5", value: "f5" }, { label: "F6", value: "f6" },
      { label: "F7", value: "f7" }, { label: "F8", value: "f8" }, { label: "F9", value: "f9" },
      { label: "F10", value: "f10" }, { label: "F11", value: "f11" }, { label: "F12", value: "f12" },
      { label: "PrtSc", value: "print_screen", width: "w3" }
    ],
    [
      { label: "`", value: "`" }, { label: "1", value: "1" }, { label: "2", value: "2" },
      { label: "3", value: "3" }, { label: "4", value: "4" }, { label: "5", value: "5" },
      { label: "6", value: "6" }, { label: "7", value: "7" }, { label: "8", value: "8" },
      { label: "9", value: "9" }, { label: "0", value: "0" }, { label: "-", value: "-" },
      { label: "=", value: "=" }, { label: "Backspace", value: "backspace", width: "w4" },
      { label: "NumLock", value: "num_lock", width: "w3" }, { label: "N7", value: "numpad_7" },
      { label: "N8", value: "numpad_8" }, { label: "N9", value: "numpad_9" }, { label: "N/", value: "numpad_divide" }
    ],
    [
      { label: "Tab", value: "tab", width: "w3" }, { label: "Q", value: "q" }, { label: "W", value: "w" },
      { label: "E", value: "e" }, { label: "R", value: "r" }, { label: "T", value: "t" },
      { label: "Y", value: "y" }, { label: "U", value: "u" }, { label: "I", value: "i" },
      { label: "O", value: "o" }, { label: "P", value: "p" }, { label: "[", value: "[" },
      { label: "]", value: "]" }, { label: "\\", value: "\\" }, { label: "N4", value: "numpad_4" },
      { label: "N5", value: "numpad_5" }, { label: "N6", value: "numpad_6" }, { label: "N*", value: "numpad_multiply" }
    ],
    [
      { label: "Caps", value: "caps_lock", width: "w4" }, { label: "A", value: "a" }, { label: "S", value: "s" },
      { label: "D", value: "d" }, { label: "F", value: "f" }, { label: "G", value: "g" },
      { label: "H", value: "h" }, { label: "J", value: "j" }, { label: "K", value: "k" },
      { label: "L", value: "l" }, { label: ";", value: ";" }, { label: "'", value: "'" },
      { label: "Enter", value: "enter", width: "w4" }, { label: "N1", value: "numpad_1" },
      { label: "N2", value: "numpad_2" }, { label: "N3", value: "numpad_3" }, { label: "N-", value: "numpad_subtract" }
    ],
    [
      { label: "Shift", value: "shift", width: "w5" }, { label: "Z", value: "z" }, { label: "X", value: "x" },
      { label: "C", value: "c" }, { label: "V", value: "v" }, { label: "B", value: "b" },
      { label: "N", value: "n" }, { label: "M", value: "m" }, { label: ",", value: "," },
      { label: ".", value: "." }, { label: "/", value: "/" }, { label: "Shift", value: "shift", width: "w5" },
      { label: "Up", value: "up" }, { label: "N0", value: "numpad_0", width: "w3" },
      { label: "N.", value: "numpad_decimal" }, { label: "N+", value: "numpad_add", width: "w3" }
    ],
    [
      { label: "Ctrl", value: "ctrl", width: "w3" }, { label: "Win", value: "cmd", width: "w3" },
      { label: "Alt", value: "alt", width: "w3" }, { label: "Space", value: "space", width: "w6" },
      { label: "Alt", value: "alt", width: "w3" }, { label: "Menu", value: "menu", width: "w3" },
      { label: "Ctrl", value: "ctrl", width: "w3" }, { label: "Left", value: "left" },
      { label: "Down", value: "down" }, { label: "Right", value: "right" }, { label: "Ins", value: "insert" },
      { label: "Del", value: "delete" }, { label: "Home", value: "home" }, { label: "End", value: "end" },
      { label: "PgUp", value: "page_up" }, { label: "PgDn", value: "page_down" }, { label: "NEnter", value: "numpad_enter", width: "w4" }
    ]
  ],
  azerty: [
    [
      { label: "Esc", value: "escape" },
      { label: "F1", value: "f1" }, { label: "F2", value: "f2" }, { label: "F3", value: "f3" },
      { label: "F4", value: "f4" }, { label: "F5", value: "f5" }, { label: "F6", value: "f6" },
      { label: "F7", value: "f7" }, { label: "F8", value: "f8" }, { label: "F9", value: "f9" },
      { label: "F10", value: "f10" }, { label: "F11", value: "f11" }, { label: "F12", value: "f12" },
      { label: "PrtSc", value: "print_screen", width: "w3" }
    ],
    [
      { label: "2", value: "2" }, { label: "&", value: "&" }, { label: "E", value: "e" },
      { label: "\"", value: "\"" }, { label: "'", value: "'" }, { label: "(", value: "(" },
      { label: "-", value: "-" }, { label: "_", value: "_" }, { label: "^", value: "^" },
      { label: ")", value: ")" }, { label: "=", value: "=" }, { label: "$", value: "$" },
      { label: "*", value: "*" }, { label: "Backspace", value: "backspace", width: "w4" },
      { label: "NumLock", value: "num_lock", width: "w3" }, { label: "N7", value: "numpad_7" },
      { label: "N8", value: "numpad_8" }, { label: "N9", value: "numpad_9" }, { label: "N/", value: "numpad_divide" }
    ],
    [
      { label: "Tab", value: "tab", width: "w3" }, { label: "A", value: "a" }, { label: "Z", value: "z" },
      { label: "E", value: "e" }, { label: "R", value: "r" }, { label: "T", value: "t" },
      { label: "Y", value: "y" }, { label: "U", value: "u" }, { label: "I", value: "i" },
      { label: "O", value: "o" }, { label: "P", value: "p" }, { label: "^", value: "^" },
      { label: "$", value: "$" }, { label: "\\", value: "\\" }, { label: "N4", value: "numpad_4" },
      { label: "N5", value: "numpad_5" }, { label: "N6", value: "numpad_6" }, { label: "N*", value: "numpad_multiply" }
    ],
    [
      { label: "Caps", value: "caps_lock", width: "w4" }, { label: "Q", value: "q" }, { label: "S", value: "s" },
      { label: "D", value: "d" }, { label: "F", value: "f" }, { label: "G", value: "g" },
      { label: "H", value: "h" }, { label: "J", value: "j" }, { label: "K", value: "k" },
      { label: "L", value: "l" }, { label: "M", value: "m" }, { label: "U", value: "u" },
      { label: "Enter", value: "enter", width: "w4" }, { label: "N1", value: "numpad_1" },
      { label: "N2", value: "numpad_2" }, { label: "N3", value: "numpad_3" }, { label: "N-", value: "numpad_subtract" }
    ],
    [
      { label: "Shift", value: "shift", width: "w5" }, { label: "W", value: "w" }, { label: "X", value: "x" },
      { label: "C", value: "c" }, { label: "V", value: "v" }, { label: "B", value: "b" },
      { label: "N", value: "n" }, { label: ",", value: "," }, { label: ";", value: ";" },
      { label: ":", value: ":" }, { label: "!", value: "!" }, { label: "Shift", value: "shift", width: "w5" },
      { label: "Up", value: "up" }, { label: "N0", value: "numpad_0", width: "w3" },
      { label: "N.", value: "numpad_decimal" }, { label: "N+", value: "numpad_add", width: "w3" }
    ],
    [
      { label: "Ctrl", value: "ctrl", width: "w3" }, { label: "Win", value: "cmd", width: "w3" },
      { label: "Alt", value: "alt", width: "w3" }, { label: "Space", value: "space", width: "w6" },
      { label: "Alt", value: "alt", width: "w3" }, { label: "Menu", value: "menu", width: "w3" },
      { label: "Ctrl", value: "ctrl", width: "w3" }, { label: "Left", value: "left" },
      { label: "Down", value: "down" }, { label: "Right", value: "right" }, { label: "Ins", value: "insert" },
      { label: "Del", value: "delete" }, { label: "Home", value: "home" }, { label: "End", value: "end" },
      { label: "PgUp", value: "page_up" }, { label: "PgDn", value: "page_down" }, { label: "NEnter", value: "numpad_enter", width: "w4" }
    ]
  ]
};

function wsUrl(path) {
  const scheme = location.protocol === "https:" ? "wss" : "ws";
  return `${scheme}://${location.host}${path}`;
}

function setStatus(text, isError = false) {
  statusLine.textContent = text;
  statusLine.style.color = isError ? "#ff8ea2" : "#49b3ff";
}

function connect() {
  ws = new WebSocket(wsUrl("/ws/mobile"));
  ws.onopen = () => setStatus("Connected to server.");
  ws.onclose = () => {
    setStatus("Disconnected. Reconnecting...");
    joined = false;
    setTimeout(connect, 1500);
  };
  ws.onerror = () => setStatus("WebSocket error", true);
  ws.onmessage = (event) => onMessage(event.data);
}

function onMessage(raw) {
  let data = {};
  try {
    data = JSON.parse(raw);
  } catch (e) {
    return;
  }
  if (data.type === "joined_room") {
    joined = true;
    joinSection.classList.add("hidden");
    controlSection.classList.remove("hidden");
    infoPc.textContent = data.pc_name;
    infoRoom.textContent = data.room_code;
    infoAgent.textContent = data.agent_connected ? "online" : "offline";
    setStatus(`Joined room ${data.room_code}.`);
    return;
  }
  if (data.type === "room_status") {
    infoAgent.textContent = data.agent_connected ? "online" : "offline";
    return;
  }
  if (data.type === "room_closed") {
    setStatus(data.message || "Room closed.");
    joined = false;
    controlSection.classList.add("hidden");
    joinSection.classList.remove("hidden");
    return;
  }
  if (data.type === "warning") {
    setStatus(data.message || "Warning", true);
    return;
  }
  if (data.type === "error") {
    setStatus(data.message || "Error", true);
  }
}

function sendControl(eventPayload) {
  if (!ws || ws.readyState !== WebSocket.OPEN || !joined) return;
  ws.send(JSON.stringify({ type: "control", event: eventPayload }));
}

joinBtn.addEventListener("click", () => {
  const roomCode = roomCodeInput.value.trim().toUpperCase();
  const password = roomPasswordInput.value.trim();
  const deviceName = deviceNameInput.value.trim() || "Phone";
  if (!roomCode || !password) {
    setStatus("Enter room code and password.", true);
    return;
  }
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    setStatus("Connection not ready.", true);
    return;
  }
  ws.send(
    JSON.stringify({
      type: "join_room",
      room_code: roomCode,
      password,
      device_name: deviceName
    })
  );
});

function renderKeyboard() {
  const layout = layouts[layoutSelect.value] || layouts.qwerty;
  keyboard.innerHTML = "";
  for (const row of layout) {
    const rowEl = document.createElement("div");
    rowEl.className = "kb-row";
    for (const key of row) {
      const btn = document.createElement("button");
      btn.className = `kb-key ${key.width || ""}`.trim();
      btn.textContent = key.label;
      btn.dataset.value = key.value;
      btn.addEventListener("click", () => handleKeyPress(key.value));
      rowEl.appendChild(btn);
    }
    keyboard.appendChild(rowEl);
  }
}

function handleKeyPress(value) {
  if (modifierKeys.has(value)) {
    if (activeModifiers.has(value)) {
      activeModifiers.delete(value);
      setStatus(`Modifier released: ${value}`);
    } else {
      activeModifiers.add(value);
      setStatus(`Modifier active: ${[...activeModifiers].join(" + ")}`);
    }
    return;
  }

  if (activeModifiers.size) {
    sendControl({
      kind: "key_combo",
      modifiers: [...activeModifiers],
      key: value
    });
    activeModifiers.clear();
  } else {
    sendControl({ kind: "key_tap", key: value });
  }
}

layoutSelect.addEventListener("change", renderKeyboard);
renderKeyboard();

for (const btn of document.querySelectorAll("[data-mouse]")) {
  btn.addEventListener("click", () => {
    const button = btn.dataset.mouse;
    sendControl({ kind: "mouse_click", button });
  });
}

for (const btn of document.querySelectorAll("[data-scroll]")) {
  btn.addEventListener("click", () => {
    const dy = Number(btn.dataset.scroll || "0");
    sendControl({ kind: "mouse_scroll", dx: 0, dy });
  });
}

let pointerActive = false;
let lastX = 0;
let lastY = 0;
const sensitivity = 1.35;

trackpad.addEventListener("pointerdown", (event) => {
  pointerActive = true;
  lastX = event.clientX;
  lastY = event.clientY;
  trackpad.setPointerCapture(event.pointerId);
});

trackpad.addEventListener("pointermove", (event) => {
  if (!pointerActive) return;
  const dx = (event.clientX - lastX) * sensitivity;
  const dy = (event.clientY - lastY) * sensitivity;
  lastX = event.clientX;
  lastY = event.clientY;
  if (Math.abs(dx) < 0.1 && Math.abs(dy) < 0.1) return;
  sendControl({ kind: "mouse_move", dx, dy });
});

function endPointer(event) {
  pointerActive = false;
  try {
    trackpad.releasePointerCapture(event.pointerId);
  } catch (e) {
    // Ignore capture release errors on some mobile browsers.
  }
}

trackpad.addEventListener("pointerup", endPointer);
trackpad.addEventListener("pointercancel", endPointer);
trackpad.addEventListener("pointerleave", endPointer);

connect();
