const statusLine = document.getElementById("status-line");
const createSection = document.getElementById("create-section");
const roomSection = document.getElementById("room-section");
const createBtn = document.getElementById("create-room-btn");
const closeBtn = document.getElementById("close-room-btn");
const pcNameInput = document.getElementById("pc-name");
const roomPasswordInput = document.getElementById("room-password");
const roomCodeEl = document.getElementById("room-code");
const roomPcNameEl = document.getElementById("room-pc-name");
const agentStatusEl = document.getElementById("agent-status");
const deviceList = document.getElementById("device-list");
const emptyDevices = document.getElementById("empty-devices");

let ws = null;
let roomCreated = false;

function detectPcName() {
  const platform = navigator.platform || "PC";
  const ua = navigator.userAgent || "";
  let browser = "Browser";
  if (ua.includes("Edg")) browser = "Edge";
  else if (ua.includes("Chrome")) browser = "Chrome";
  else if (ua.includes("Firefox")) browser = "Firefox";
  else if (ua.includes("Safari")) browser = "Safari";
  return `${platform} (${browser})`;
}

function wsUrl(path) {
  const scheme = location.protocol === "https:" ? "wss" : "ws";
  return `${scheme}://${location.host}${path}`;
}

function setStatus(text, isError = false) {
  statusLine.textContent = text;
  statusLine.style.color = isError ? "#ff8ea2" : "#49b3ff";
}

function connect() {
  ws = new WebSocket(wsUrl("/ws/pc"));
  ws.onopen = () => setStatus("Connected to server.");
  ws.onclose = () => {
    setStatus("Disconnected. Reconnecting...");
    setTimeout(connect, 1500);
  };
  ws.onerror = () => setStatus("WebSocket error.", true);
  ws.onmessage = (event) => onMessage(event.data);
}

function onMessage(raw) {
  let data = {};
  try {
    data = JSON.parse(raw);
  } catch (e) {
    return;
  }
  if (data.type === "room_created") {
    roomCreated = true;
    roomCodeEl.textContent = data.room_code;
    roomPcNameEl.textContent = data.pc_name;
    createSection.classList.add("hidden");
    roomSection.classList.remove("hidden");
    setStatus(`Room ${data.room_code} created.`);
    return;
  }
  if (data.type === "room_status") {
    agentStatusEl.textContent = data.agent_connected ? "online" : "offline";
    renderMobiles(data.mobiles || []);
    return;
  }
  if (data.type === "error") {
    setStatus(data.message || "Server error", true);
    return;
  }
  if (data.type === "room_closed") {
    setStatus(data.message || "Room closed.");
    resetUi();
  }
}

function resetUi() {
  roomCreated = false;
  createSection.classList.remove("hidden");
  roomSection.classList.add("hidden");
  roomCodeEl.textContent = "-";
  roomPcNameEl.textContent = "-";
  agentStatusEl.textContent = "offline";
  renderMobiles([]);
}

function renderMobiles(mobiles) {
  deviceList.innerHTML = "";
  if (!mobiles.length) {
    emptyDevices.classList.remove("hidden");
    return;
  }
  emptyDevices.classList.add("hidden");
  for (const mobile of mobiles) {
    const li = document.createElement("li");
    li.textContent = `${mobile.name} (${mobile.id})`;
    deviceList.appendChild(li);
  }
}

createBtn.addEventListener("click", () => {
  const pcName = pcNameInput.value.trim();
  const password = roomPasswordInput.value.trim();
  if (!password || password.length < 4) {
    setStatus("Use a password with at least 4 characters.", true);
    return;
  }
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    setStatus("Socket not ready yet.", true);
    return;
  }
  if (roomCreated) {
    setStatus("Room already exists in this tab.", true);
    return;
  }
  ws.send(
    JSON.stringify({
      type: "create_room",
      pc_name: pcName || "My PC",
      password,
    })
  );
});

closeBtn.addEventListener("click", () => {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify({ type: "close_room" }));
  resetUi();
  setStatus("Room closed.");
});

connect();

if (!pcNameInput.value.trim() || pcNameInput.value === "My PC") {
  pcNameInput.value = detectPcName();
}
