/* MULTIMANDO STREAM v2.1 - publico, SOLO LECTURA, sin turnos ni boton CONECTAR.
 * Una unica conexion WebSocket /stream mediante Cloudflare.
 * Cada JPEG llega en PUSH; NO solicita frames por HTTP.
 */
(() => {
  "use strict";
  const root = document.getElementById("futureoStream");
  const image = document.getElementById("futureoStreamImage");
  const status = document.getElementById("futureoStreamStatus");
  const badge = document.getElementById("futureoStreamBadge");
  const settings = document.getElementById("futureoStreamSettings");
  if (!root || !image || !status) return;
  let ws = null, previewUrl = "", attempts = 0, stopped = false, lastFrame = 0;
  const endpoint = "sala.php";
  function update(message, live) {
    status.textContent = message;
    root.classList.toggle("futureo-live", !!live);
    if (badge) badge.textContent = live ? "EN VIVO" : "SIN TRANSMISION";
  }
  function urlForStream(value) {
    try {
      const parsed = new URL(value, window.location.href);
      if (parsed.protocol === "https:") parsed.protocol = "wss:";
      if (parsed.protocol !== "wss:" || !/^[a-z0-9-]+\.trycloudflare\.com$/i.test(parsed.hostname)) return null;
      parsed.pathname = "/stream";
      parsed.search = "";
      parsed.hash = "";
      return parsed.toString();
    } catch { return null; }
  }
  async function getRoom() {
    const auto = document.getElementById("autoRoom");
    const manual = document.getElementById("directUrl");
    if (auto && !auto.checked) return urlForStream(manual && manual.value ? manual.value.trim() : "");
    const res = await fetch(endpoint, {cache: "no-store", credentials: "same-origin", signal: AbortSignal.timeout(8500)});
    if (!res.ok) throw new Error("No hay sala publica");
    const data = await res.json();
    return urlForStream(data.url || "");
  }
  async function connect() {
    if (stopped || document.hidden) return;
    if (ws) return;
    try {
      const url = await getRoom();
      if (!url) { update("Esperando una sala publicada...", false); return; }
      const socket = new WebSocket(url);
      socket.binaryType = "blob";
      ws = socket;
      socket.onopen = () => { attempts = 0; update("Conectado al canal de imagen. Esperando captura...", false); };
      socket.onmessage = (event) => {
        if (socket !== ws) return;
        if (typeof event.data === "string") {
          try {
            const msg = JSON.parse(event.data);
            if (msg.type === "futureo_stream" && !msg.active) {
              image.removeAttribute("src");
              image.hidden = true;
              if (previewUrl) { URL.revokeObjectURL(previewUrl); previewUrl = ""; }
              update("El anfitrion no esta transmitiendo", false);
            }
          } catch {}
          return;
        }
        const jpeg = event.data;
        if (!(jpeg instanceof Blob) || jpeg.size > 180000 || jpeg.size < 2) return;
        const nextUrl = URL.createObjectURL(jpeg);
        const previous = previewUrl;
        previewUrl = nextUrl;
        image.onload = () => { if (previous) URL.revokeObjectURL(previous); };
        image.onerror = () => { if (previous) URL.revokeObjectURL(previous); };
        image.src = nextUrl;
        image.hidden = false;
        lastFrame = Date.now();
        update("Imagen en directo - modo ligero", true);
      };
      socket.onerror = () => { update("Reintentando imagen...", false); };
      socket.onclose = () => {
        if (ws === socket) ws = null;
        if (!stopped) update("Esperando señal del anfitrion...", false);
      };
    } catch { update("Esperando transmisión...", false); }
  }
  const retry = setInterval(() => {
    if (stopped || document.hidden) return;
    if (!ws) { attempts++; connect(); }
    else if (ws.readyState !== WebSocket.CONNECTING && ws.readyState !== WebSocket.OPEN) { ws = null; }
    else if (ws.readyState === WebSocket.OPEN && lastFrame && Date.now() - lastFrame > 20000) {
      update("Enlace activo: esperando fotogramas...", false);
    }
  }, 4500);
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      if (ws) { const old = ws; ws = null; old.close(1000, "Pausa"); }
    } else connect();
  });
  window.addEventListener("pagehide", () => {
    stopped = true; clearInterval(retry);
    if (ws) ws.close(1000, "Pagina cerrada");
    if (previewUrl) URL.revokeObjectURL(previewUrl);
  }, {once: true});
  if (settings) settings.addEventListener("click", () => {
    const expanded = root.classList.toggle("futureo-stream-expanded");
    settings.textContent = expanded ? "REDUCIR" : "AMPLIAR";
  });
  connect();
})();