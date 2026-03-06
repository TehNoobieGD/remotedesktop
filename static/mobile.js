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
const rotateWarning = document.getElementById("rotate-warning");
const screenPreview = document.getElementById("screen-preview");
const previewEmpty = document.getElementById("preview-empty");
const cursorDot = document.getElementById("cursor-dot");
const monitorSelect = document.getElementById("monitor-select");
const followCursorToggle = document.getElementById("follow-cursor-toggle");
const audioToggle = document.getElementById("audio-toggle");

let ws = null;
let joined = false;
let lastJoinPayload = null;
let monitors = [];
let suppressMonitorEvents = false;
let audioAvailable = false;
let audioEnabled = false;
let audioCtx = null;
let audioNextTime = 0;
const activeModifiers = new Set();
const modifierKeys = new Set(["ctrl", "shift", "alt", "cmd"]);

const layouts = {
  qwerty: [
    [{ label: "Esc", value: "escape" }, { label: "F1", value: "f1" }, { label: "F2", value: "f2" }, { label: "F3", value: "f3" }, { label: "F4", value: "f4" }, { label: "F5", value: "f5" }, { label: "F6", value: "f6" }, { label: "F7", value: "f7" }, { label: "F8", value: "f8" }, { label: "F9", value: "f9" }, { label: "F10", value: "f10" }, { label: "F11", value: "f11" }, { label: "F12", value: "f12" }, { label: "PrtSc", value: "print_screen", units: 2 }],
    [{ label: "`", value: "`" }, { label: "1", value: "1" }, { label: "2", value: "2" }, { label: "3", value: "3" }, { label: "4", value: "4" }, { label: "5", value: "5" }, { label: "6", value: "6" }, { label: "7", value: "7" }, { label: "8", value: "8" }, { label: "9", value: "9" }, { label: "0", value: "0" }, { label: "-", value: "-" }, { label: "=", value: "=" }, { label: "Backspace", value: "backspace", units: 2 }, { label: "N7", value: "numpad_7" }, { label: "N8", value: "numpad_8" }, { label: "N9", value: "numpad_9" }, { label: "N/", value: "numpad_divide" }],
    [{ label: "Tab", value: "tab", units: 1.6 }, { label: "Q", value: "q" }, { label: "W", value: "w" }, { label: "E", value: "e" }, { label: "R", value: "r" }, { label: "T", value: "t" }, { label: "Y", value: "y" }, { label: "U", value: "u" }, { label: "I", value: "i" }, { label: "O", value: "o" }, { label: "P", value: "p" }, { label: "[", value: "[" }, { label: "]", value: "]" }, { label: "\\", value: "\\" }, { label: "N4", value: "numpad_4" }, { label: "N5", value: "numpad_5" }, { label: "N6", value: "numpad_6" }, { label: "N*", value: "numpad_multiply" }],
    [{ label: "Caps", value: "caps_lock", units: 1.9 }, { label: "A", value: "a" }, { label: "S", value: "s" }, { label: "D", value: "d" }, { label: "F", value: "f" }, { label: "G", value: "g" }, { label: "H", value: "h" }, { label: "J", value: "j" }, { label: "K", value: "k" }, { label: "L", value: "l" }, { label: ";", value: ";" }, { label: "'", value: "'" }, { label: "Enter", value: "enter", units: 2 }, { label: "N1", value: "numpad_1" }, { label: "N2", value: "numpad_2" }, { label: "N3", value: "numpad_3" }, { label: "N-", value: "numpad_subtract" }],
    [{ label: "Shift", value: "shift", units: 2.3 }, { label: "Z", value: "z" }, { label: "X", value: "x" }, { label: "C", value: "c" }, { label: "V", value: "v" }, { label: "B", value: "b" }, { label: "N", value: "n" }, { label: "M", value: "m" }, { label: ",", value: "," }, { label: ".", value: "." }, { label: "/", value: "/" }, { label: "Shift", value: "shift", units: 2.1 }, { label: "Up", value: "up" }, { label: "N0", value: "numpad_0", units: 2 }, { label: "N.", value: "numpad_decimal" }, { label: "N+", value: "numpad_add" }],
    [{ label: "Ctrl", value: "ctrl", units: 1.4 }, { label: "Win", value: "cmd", units: 1.2 }, { label: "Alt", value: "alt", units: 1.2 }, { label: "Space", value: "space", units: 5 }, { label: "Alt", value: "alt", units: 1.2 }, { label: "Menu", value: "menu", units: 1.2 }, { label: "Ctrl", value: "ctrl", units: 1.4 }, { label: "Left", value: "left" }, { label: "Down", value: "down" }, { label: "Right", value: "right" }, { label: "Ins", value: "insert" }, { label: "Del", value: "delete" }, { label: "Home", value: "home" }, { label: "End", value: "end" }, { label: "PgUp", value: "page_up" }, { label: "PgDn", value: "page_down" }, { label: "NEnt", value: "numpad_enter", units: 1.8 }]
  ],
  azerty: [
    [{ label: "Esc", value: "escape" }, { label: "F1", value: "f1" }, { label: "F2", value: "f2" }, { label: "F3", value: "f3" }, { label: "F4", value: "f4" }, { label: "F5", value: "f5" }, { label: "F6", value: "f6" }, { label: "F7", value: "f7" }, { label: "F8", value: "f8" }, { label: "F9", value: "f9" }, { label: "F10", value: "f10" }, { label: "F11", value: "f11" }, { label: "F12", value: "f12" }, { label: "PrtSc", value: "print_screen", units: 2 }],
    [{ label: "2", value: "2" }, { label: "&", value: "&" }, { label: '"', value: '"' }, { label: "'", value: "'" }, { label: "(", value: "(" }, { label: "-", value: "-" }, { label: "_", value: "_" }, { label: ")", value: ")" }, { label: "=", value: "=" }, { label: "Backspace", value: "backspace", units: 2.4 }, { label: "N7", value: "numpad_7" }, { label: "N8", value: "numpad_8" }, { label: "N9", value: "numpad_9" }, { label: "N/", value: "numpad_divide" }],
    [{ label: "Tab", value: "tab", units: 1.6 }, { label: "A", value: "a" }, { label: "Z", value: "z" }, { label: "E", value: "e" }, { label: "R", value: "r" }, { label: "T", value: "t" }, { label: "Y", value: "y" }, { label: "U", value: "u" }, { label: "I", value: "i" }, { label: "O", value: "o" }, { label: "P", value: "p" }, { label: "^", value: "^" }, { label: "$", value: "$" }, { label: "\\", value: "\\" }, { label: "N4", value: "numpad_4" }, { label: "N5", value: "numpad_5" }, { label: "N6", value: "numpad_6" }, { label: "N*", value: "numpad_multiply" }],
    [{ label: "Caps", value: "caps_lock", units: 1.9 }, { label: "Q", value: "q" }, { label: "S", value: "s" }, { label: "D", value: "d" }, { label: "F", value: "f" }, { label: "G", value: "g" }, { label: "H", value: "h" }, { label: "J", value: "j" }, { label: "K", value: "k" }, { label: "L", value: "l" }, { label: "M", value: "m" }, { label: "U", value: "u" }, { label: "Enter", value: "enter", units: 2 }, { label: "N1", value: "numpad_1" }, { label: "N2", value: "numpad_2" }, { label: "N3", value: "numpad_3" }, { label: "N-", value: "numpad_subtract" }],
    [{ label: "Shift", value: "shift", units: 2.3 }, { label: "W", value: "w" }, { label: "X", value: "x" }, { label: "C", value: "c" }, { label: "V", value: "v" }, { label: "B", value: "b" }, { label: "N", value: "n" }, { label: ",", value: "," }, { label: ";", value: ";" }, { label: ":", value: ":" }, { label: "!", value: "!" }, { label: "Shift", value: "shift", units: 2.1 }, { label: "Up", value: "up" }, { label: "N0", value: "numpad_0", units: 2 }, { label: "N.", value: "numpad_decimal" }, { label: "N+", value: "numpad_add" }],
    [{ label: "Ctrl", value: "ctrl", units: 1.4 }, { label: "Win", value: "cmd", units: 1.2 }, { label: "Alt", value: "alt", units: 1.2 }, { label: "Space", value: "space", units: 5 }, { label: "Alt", value: "alt", units: 1.2 }, { label: "Menu", value: "menu", units: 1.2 }, { label: "Ctrl", value: "ctrl", units: 1.4 }, { label: "Left", value: "left" }, { label: "Down", value: "down" }, { label: "Right", value: "right" }, { label: "Ins", value: "insert" }, { label: "Del", value: "delete" }, { label: "Home", value: "home" }, { label: "End", value: "end" }, { label: "PgUp", value: "page_up" }, { label: "PgDn", value: "page_down" }, { label: "NEnt", value: "numpad_enter", units: 1.8 }]
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

function detectDeviceName() {
  const ua = navigator.userAgent || "";
  const platform = navigator.platform || "";
  let base = "Phone";
  if (/iPhone/i.test(ua)) base = "iPhone";
  else if (/iPad/i.test(ua)) base = "iPad";
  else if (/Android/i.test(ua)) base = "Android";
  else if (/Windows/i.test(platform)) base = "Windows Device";
  else if (/Mac/i.test(platform)) base = "Mac Device";
  return base;
}

function updateOrientationState() {
  if (!joined) return;
  const isLandscape = window.matchMedia("(orientation: landscape)").matches;
  rotateWarning.classList.toggle("hidden", isLandscape);
}

function connect() {
  ws = new WebSocket(wsUrl("/ws/mobile"));
  ws.onopen = () => {
    setStatus("Connected to server.");
    if (lastJoinPayload) {
      ws.send(JSON.stringify(lastJoinPayload));
    }
  };
  ws.onclose = () => {
    setStatus("Disconnected. Reconnecting...");
    setTimeout(connect, 1200);
  };
  ws.onerror = () => setStatus("WebSocket error", true);
  ws.onmessage = (event) => onMessage(event.data);
}

function onMessage(raw) {
  let data = {};
  try {
    data = JSON.parse(raw);
  } catch (_err) {
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
    updateOrientationState();
    refreshAudioButton();
    return;
  }
  if (data.type === "room_status") {
    infoAgent.textContent = data.agent_connected ? "online" : "offline";
    audioAvailable = Boolean(data.audio_available);
    refreshAudioButton();
    if (Array.isArray(data.monitors)) {
      monitors = data.monitors;
      renderMonitorOptions(data.selected_monitor_id, data.follow_cursor);
    }
    return;
  }
  if (data.type === "screen_frame") {
    if (typeof data.jpeg === "string" && data.jpeg.length) {
      screenPreview.src = `data:image/jpeg;base64,${data.jpeg}`;
      previewEmpty.classList.add("hidden");
      paintCursor(data.cursor);
    }
    return;
  }
  if (data.type === "audio_chunk") {
    handleAudioChunk(data);
    return;
  }
  if (data.type === "room_closed") {
    setStatus(data.message || "Room closed.");
    joined = false;
    audioEnabled = false;
    activeModifiers.clear();
    controlSection.classList.add("hidden");
    joinSection.classList.remove("hidden");
    previewEmpty.classList.remove("hidden");
    cursorDot.classList.add("hidden");
    refreshAudioButton();
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

function sendAudioSubscribe(enabled) {
  if (!ws || ws.readyState !== WebSocket.OPEN || !joined) return;
  ws.send(JSON.stringify({ type: "audio_subscribe", enabled: Boolean(enabled) }));
}

function sendMonitorConfig() {
  if (!ws || ws.readyState !== WebSocket.OPEN || !joined) return;
  const monitorId = Number(monitorSelect.value || "0");
  const payload = {
    type: "monitor_config",
    follow_cursor: Boolean(followCursorToggle.checked),
    monitor_id: Number.isFinite(monitorId) && monitorId > 0 ? monitorId : null
  };
  ws.send(JSON.stringify(payload));
}

function renderMonitorOptions(selectedMonitorId, followCursor) {
  const selected = Number(selectedMonitorId || 0);
  suppressMonitorEvents = true;
  monitorSelect.innerHTML = "";
  for (const mon of monitors) {
    if (!mon || typeof mon.id !== "number") continue;
    const opt = document.createElement("option");
    opt.value = String(mon.id);
    const label = mon.label || `Display ${mon.id}`;
    opt.textContent = `${label} (${mon.width}x${mon.height})`;
    monitorSelect.appendChild(opt);
  }
  if (selected > 0) {
    monitorSelect.value = String(selected);
  }
  if (typeof followCursor === "boolean") {
    followCursorToggle.checked = followCursor;
  }
  monitorSelect.disabled = Boolean(followCursorToggle.checked);
  suppressMonitorEvents = false;
}

function paintCursor(cursor) {
  if (!cursor || cursor.visible === false) {
    cursorDot.classList.add("hidden");
    return;
  }
  const xNorm = Number(cursor.x_norm);
  const yNorm = Number(cursor.y_norm);
  if (!Number.isFinite(xNorm) || !Number.isFinite(yNorm)) {
    cursorDot.classList.add("hidden");
    return;
  }
  const x = Math.max(0, Math.min(1, xNorm)) * screenPreview.clientWidth;
  const y = Math.max(0, Math.min(1, yNorm)) * screenPreview.clientHeight;
  cursorDot.style.left = `${x}px`;
  cursorDot.style.top = `${y}px`;
  cursorDot.classList.remove("hidden");
}

function refreshAudioButton() {
  if (!audioToggle) return;
  audioToggle.disabled = !audioAvailable || !joined;
  if (!audioAvailable) {
    audioToggle.textContent = "Audio Unavailable";
  } else if (audioEnabled) {
    audioToggle.textContent = "Disable Audio";
  } else {
    audioToggle.textContent = "Enable Audio";
  }
}

function ensureAudioContext() {
  if (audioCtx) return audioCtx;
  audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000 });
  audioNextTime = audioCtx.currentTime;
  return audioCtx;
}

function decodePcm16Base64(base64Text) {
  const bin = atob(base64Text);
  const byteLen = bin.length;
  const out = new Int16Array(byteLen / 2);
  for (let i = 0; i < out.length; i++) {
    const lo = bin.charCodeAt(i * 2);
    const hi = bin.charCodeAt(i * 2 + 1);
    const val = (hi << 8) | lo;
    out[i] = val >= 32768 ? val - 65536 : val;
  }
  return out;
}

function handleAudioChunk(data) {
  if (!audioEnabled || !audioCtx) return;
  const pcm64 = data.pcm16;
  const sampleRate = Number(data.sample_rate || 24000);
  if (typeof pcm64 !== "string" || !pcm64.length) return;
  const pcm = decodePcm16Base64(pcm64);
  if (!pcm.length) return;

  const buffer = audioCtx.createBuffer(1, pcm.length, sampleRate);
  const channel = buffer.getChannelData(0);
  for (let i = 0; i < pcm.length; i++) {
    channel[i] = pcm[i] / 32768;
  }

  const source = audioCtx.createBufferSource();
  source.buffer = buffer;
  source.connect(audioCtx.destination);
  const now = audioCtx.currentTime;
  if (audioNextTime < now - 0.3) {
    audioNextTime = now + 0.02;
  }
  source.start(audioNextTime);
  audioNextTime += buffer.duration;
}

joinBtn.addEventListener("click", () => {
  const roomCode = roomCodeInput.value.trim().toUpperCase();
  const password = roomPasswordInput.value.trim();
  const deviceName = (deviceNameInput.value.trim() || detectDeviceName()).slice(0, 40);
  if (!roomCode || !password) {
    setStatus("Enter room code and password.", true);
    return;
  }
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    setStatus("Connection not ready.", true);
    return;
  }
  const payload = {
    type: "join_room",
    room_code: roomCode,
    password,
    device_name: deviceName
  };
  lastJoinPayload = payload;
  ws.send(JSON.stringify(payload));
});

audioToggle.addEventListener("click", async () => {
  if (!joined || !audioAvailable) return;
  if (!audioEnabled) {
    try {
      const ctx = ensureAudioContext();
      await ctx.resume();
      audioEnabled = true;
      sendAudioSubscribe(true);
      setStatus("Audio enabled.");
    } catch (_err) {
      setStatus("Could not start audio.", true);
      audioEnabled = false;
    }
  } else {
    audioEnabled = false;
    sendAudioSubscribe(false);
    setStatus("Audio disabled.");
  }
  refreshAudioButton();
});

function renderKeyboard() {
  const layout = layouts[layoutSelect.value] || layouts.qwerty;
  keyboard.innerHTML = "";
  for (const row of layout) {
    const rowEl = document.createElement("div");
    rowEl.className = "kb-row";
    for (const key of row) {
      const btn = document.createElement("button");
      btn.className = "kb-key";
      btn.textContent = key.label;
      btn.dataset.value = key.value;
      btn.style.flex = `${key.units || 1} ${key.units || 1} 0`;
      if (modifierKeys.has(key.value) && activeModifiers.has(key.value)) {
        btn.classList.add("mod-active");
      }
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
    renderKeyboard();
    return;
  }
  if (activeModifiers.size) {
    sendControl({ kind: "key_combo", modifiers: [...activeModifiers], key: value });
    activeModifiers.clear();
    renderKeyboard();
  } else {
    sendControl({ kind: "key_tap", key: value });
  }
}

layoutSelect.addEventListener("change", renderKeyboard);
renderKeyboard();

monitorSelect.addEventListener("change", () => {
  if (suppressMonitorEvents) return;
  sendMonitorConfig();
});

followCursorToggle.addEventListener("change", () => {
  if (suppressMonitorEvents) return;
  monitorSelect.disabled = Boolean(followCursorToggle.checked);
  sendMonitorConfig();
});

for (const btn of document.querySelectorAll("[data-mouse]")) {
  btn.addEventListener("click", () => {
    sendControl({ kind: "mouse_click", button: btn.dataset.mouse });
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
const sensitivity = 1.3;

function startMove(x, y) {
  pointerActive = true;
  lastX = x;
  lastY = y;
}

function moveTo(x, y) {
  if (!pointerActive) return;
  const dx = (x - lastX) * sensitivity;
  const dy = (y - lastY) * sensitivity;
  lastX = x;
  lastY = y;
  if (Math.abs(dx) < 0.2 && Math.abs(dy) < 0.2) return;
  sendControl({ kind: "mouse_move", dx, dy });
}

function stopMove() {
  pointerActive = false;
}

trackpad.addEventListener("pointerdown", (event) => {
  trackpad.setPointerCapture(event.pointerId);
  startMove(event.clientX, event.clientY);
});

trackpad.addEventListener("pointermove", (event) => {
  moveTo(event.clientX, event.clientY);
});

trackpad.addEventListener("pointerup", () => stopMove());
trackpad.addEventListener("pointercancel", () => stopMove());
trackpad.addEventListener("pointerleave", () => stopMove());

trackpad.addEventListener("touchstart", (event) => {
  event.preventDefault();
  const t = event.touches[0];
  if (!t) return;
  startMove(t.clientX, t.clientY);
}, { passive: false });

trackpad.addEventListener("touchmove", (event) => {
  event.preventDefault();
  const t = event.touches[0];
  if (!t) return;
  moveTo(t.clientX, t.clientY);
}, { passive: false });

trackpad.addEventListener("touchend", () => stopMove());
trackpad.addEventListener("touchcancel", () => stopMove());

if (!deviceNameInput.value.trim()) {
  deviceNameInput.value = detectDeviceName();
} else if (deviceNameInput.value === "My Phone") {
  deviceNameInput.value = detectDeviceName();
}

window.addEventListener("orientationchange", updateOrientationState);
window.addEventListener("resize", updateOrientationState);

connect();
refreshAudioButton();
