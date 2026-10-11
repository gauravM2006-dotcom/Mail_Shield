// Socket.IO client connector and event dispatcher
let socket = null;
const listeners = {};

export function initSocket() {
  if (typeof io === "undefined") {
    console.warn("Socket.IO client library not loaded.");
    return null;
  }
  if (!socket) {
    socket = io({ credentials: true });

    socket.on("connect", () => {
      console.log("Connected to Mail Shield realtime hub.");
      updateRealtimeDot(true);
    });

    socket.on("disconnect", () => {
      console.log("Disconnected from Mail Shield realtime hub.");
      updateRealtimeDot(false);
    });

    socket.on("mail:new", (data) => trigger("mail:new", data));
    socket.on("mail:batch", (data) => trigger("mail:batch", data));
    socket.on("account:status", (data) => trigger("account:status", data));
    socket.on("scan:progress", (data) => trigger("scan:progress", data));
    socket.on("scan:result", (data) => trigger("scan:result", data));
    socket.on("scan:done", (data) => trigger("scan:done", data));
  }
  return socket;
}

export function onEvent(eventName, callback) {
  if (!listeners[eventName]) {
    listeners[eventName] = [];
  }
  listeners[eventName].push(callback);
}

function trigger(eventName, payload) {
  if (listeners[eventName]) {
    listeners[eventName].forEach((cb) => {
      try {
        cb(payload);
      } catch (err) {
        console.error(`Error in event listener for ${eventName}:`, err);
      }
    });
  }
}

function updateRealtimeDot(isLive) {
  const dot = document.getElementById("realtime-status-dot");
  if (dot) {
    dot.className = isLive ? "status-dot live" : "status-dot disconnected";
    dot.title = isLive ? "Realtime Live Sync Active" : "Reconnecting Realtime...";
  }
}
