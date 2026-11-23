/* MULTIMANDO FUTUREO STREAM v2.2 - vision publica y baja latencia.
 * Canal /stream: PUSH binario, sin hello, sin nombre, sin mandos, sin polling JPEG.
 * Un fotograma pendiente como MAXIMO y otro en decodificacion: si llega uno
 * mas reciente, se descarta el antiguo antes de mostrarlo.
 */
(() => {
  "use strict";
  const root = document.getElementById("futureoStream");
  const canvas = document.getElementById("futureoStreamImage");
  const status = document.getElementById("futureoStreamStatus");
  const badge = document.getElementById("futureoStreamBadge");
  const expand = document.getElementById("futureoStreamSettings");
  if (!root || !canvas || !status || !canvas.getContext) return;
  const ctx = canvas.getContext("2d", { alpha: false, desynchronized: true });
  if (!ctx) return;

  const ENDPOINT = "sala.php";
  const MAGIC = [70, 74, 50, 50]; // FJ22
  const MAX_PACKET = 180020;
  let ws = null, connecting = false, stopped = false, generation = 0;
  let pending = null, decoding = false;
  let frameCounter = 0, lastRenderedSeq = -1, lastFrameAt = 0;
  let fpsStart = performance.now(), painted = 0, fpsVisible = 0;
  let lastHudAt = 0, baselineAge = Infinity, recentAges = [];
  let extraDelay = null, lastApproxAge = null, dropped = 0;
  let stalled = 0;

  function update(message, live) {
    if (status.textContent !== message) status.textContent = message;
    root.classList.toggle("futureo-live", !!live);
    if (badge) badge.textContent = live ? "EN VIVO" : "SIN TRANSMISION";
  }

  function clearPicture(message) {
    pending = null;
    canvas.hidden = true;
    update(message, false);
  }

  function urlForStream(value) {
    try {
      const parsed = new URL(value, location.href);
      if (parsed.protocol === "https:") parsed.protocol = "wss:";
      if (parsed.protocol !== "wss:" ||
          !/^[a-z0-9-]+\.trycloudflare\.com$/i.test(parsed.hostname)) return null;
      parsed.pathname = "/stream";
      parsed.search = "";
      parsed.hash = "";
      return parsed.toString();
    } catch { return null; }
  }

  async function getStreamAddress() {
    const auto = document.getElementById("autoRoom");
    const manual = document.getElementById("directUrl");
    if (auto && !auto.checked) {
      return urlForStream(manual ? manual.value.trim() : "");
    }
    const response = await fetch(ENDPOINT, {
      cache: "no-store",
      credentials: "same-origin",
      signal: AbortSignal.timeout(8000)
    });
    if (!response.ok) throw new Error("Sala publica no disponible");
    const data = await response.json();
    return urlForStream(data.url || "");
  }

  function parseFrame(buffer) {
    if (!(buffer instanceof ArrayBuffer) || buffer.byteLength > MAX_PACKET ||
        buffer.byteLength < 4) return null;
    const bytes = new Uint8Array(buffer);
    if (bytes.length >= 20 && MAGIC.every((n, i) => bytes[i] === n)) {
      const view = new DataView(buffer);
      const seq = view.getUint32(4, false);
      const stamp = view.getUint32(8, false) * 4294967296 +
                    view.getUint32(12, false);
      const processing = view.getUint16(16, false);
      const fps = view.getUint16(18, false);
      if (bytes[20] !== 255 || bytes[21] !== 216) return null;
      return {
        seq, stamp, processing, fps, offset: 20,
        blob: new Blob([buffer.slice(20)], { type: "image/jpeg" })
      };
    }
    // Retrocompatibilidad: JPEG sin cabecera de FUTUREO v2.1.
    if (bytes[0] !== 255 || bytes[1] !== 216) return null;
    frameCounter++;
    return {
      seq: frameCounter, stamp: null, processing: 0, fps: 0, offset: 0,
      blob: new Blob([buffer], { type: "image/jpeg" })
    };
  }

  function acceptFrame(raw, token) {
    if (token !== generation || stopped || document.hidden) return;
    const frame = parseFrame(raw);
    if (!frame || frame.seq <= lastRenderedSeq) return;

    // Tiempos de dos dispositivos pueden tener relojes desajustados.
    // Solo el EXCESO sobre el minimo reciente puede usarse para descartes.
    const apparentAge = frame.stamp ? Date.now() - frame.stamp : null;
    if (apparentAge !== null && Number.isFinite(apparentAge)) {
      recentAges.push(apparentAge);
      if (recentAges.length > 45) recentAges.shift();
      baselineAge = Math.min(...recentAges);
      lastApproxAge = apparentAge >= 0 && apparentAge <= 2500 ?
        apparentAge : null;
      extraDelay = Math.max(0, apparentAge - baselineAge);
      // No mostrar una captura que se acumulo por cientos de milisegundos
      // frente a los frames que esta misma conexion recibia anteriormente.
      // Mostrar alguno si no hay ninguno visible para evitar pantalla vacia.
      if (extraDelay > Math.max(320, Math.round(2000 / Math.max(1, frame.fps))) &&
          performance.now() - lastFrameAt < 400) {
        dropped++;
        stalled++;
        if (stalled >= 10 && ws && ws.readyState === WebSocket.OPEN) {
          stalled = 0;
          ws.close(1000, "Reinicio para eliminar cola atrasada");
        }
        return;
      }
    }
    stalled = 0;
    frame.token = token;
    if (pending) dropped++;
    pending = frame; // Reemplazar, NO colocar en una cola.
    drainLatest();
  }

  function decodeJPEG(blob) {
    if (typeof createImageBitmap === "function") {
      return createImageBitmap(blob);
    }
    // Respaldo para navegadores sin createImageBitmap.
    return new Promise((resolve, reject) => {
      const url = URL.createObjectURL(blob);
      const img = new Image();
      img.onload = () => { URL.revokeObjectURL(url); resolve(img); };
      img.onerror = () => { URL.revokeObjectURL(url); reject(new Error("JPEG invalido")); };
      img.src = url;
    });
  }

  async function drainLatest() {
    if (decoding) return;
    decoding = true;
    try {
      while (pending && !stopped && !document.hidden) {
        const job = pending;
        pending = null;
        let bitmap;
        try {
          bitmap = await decodeJPEG(job.blob);
          if (job.token !== generation ||
              (pending && pending.seq > job.seq) ||
              job.seq <= lastRenderedSeq) {
            dropped++;
            continue;
          }
          const width = bitmap.width;
          const height = bitmap.height;
          if (canvas.width !== width || canvas.height !== height) {
            canvas.width = width;
            canvas.height = height;
          }
          ctx.drawImage(bitmap, 0, 0, width, height);
          canvas.hidden = false;
          lastRenderedSeq = job.seq;
          lastFrameAt = performance.now();
          painted++;
          if (lastFrameAt - fpsStart >= 1200) {
            fpsVisible = painted * 1000 / Math.max(1, lastFrameAt - fpsStart);
            painted = 0;
            fpsStart = lastFrameAt;
          }
          if (lastFrameAt - lastHudAt >= 950) {
            const rate = fpsVisible ? fpsVisible.toFixed(1) : "—";
            const additional = extraDelay === null ? "" :
              " · cola adicional ~" + Math.round(extraDelay) + " ms";
            const visualAge = lastApproxAge === null ? "" :
              " · edad aprox " + Math.round(lastApproxAge) + " ms";
            update("En vivo · " + rate + " FPS" + visualAge + additional, true);
            lastHudAt = lastFrameAt;
          } else if (!root.classList.contains("futureo-live")) {
            update("Imagen en directo · modo de baja latencia", true);
          }
        } catch (_) {
          if (!root.classList.contains("futureo-live")) {
            update("Esperando siguiente fotograma valido...", false);
          }
        } finally {
          if (bitmap && typeof bitmap.close === "function") bitmap.close();
        }
      }
    } finally {
      decoding = false;
    }
  }

  async function connect() {
    if (stopped || document.hidden || connecting || ws) return;
    connecting = true;
    try {
      const url = await getStreamAddress();
      if (stopped || document.hidden) return;
      if (!url) {
        update("Esperando sala publicada para ver el juego...", false);
        return;
      }
      const socket = new WebSocket(url);
      socket.binaryType = "arraybuffer";
      ws = socket;
      const myGeneration = ++generation;
      lastRenderedSeq = -1;
      pending = null;
      recentAges = [];
      baselineAge = Infinity;
      extraDelay = null;
      lastApproxAge = null;
      fpsStart = performance.now();
      painted = 0; fpsVisible = 0; lastHudAt = 0; stalled = 0;
      socket.onopen = () => {
        if (ws === socket) update("Canal abierto. Esperando imagen...", false);
      };
      socket.onmessage = event => {
        if (ws !== socket || myGeneration !== generation) return;
        if (typeof event.data === "string") {
          try {
            const msg = JSON.parse(event.data);
            if (msg.type === "futureo_stream" && !msg.active)
              clearPicture("El anfitrion no esta transmitiendo");
          } catch { /* texto inesperado, no afecta la imagen */ }
          return;
        }
        if (event.data instanceof ArrayBuffer) {
          acceptFrame(event.data, myGeneration);
        } else if (event.data instanceof Blob) {
          event.data.arrayBuffer().then(data => acceptFrame(data, myGeneration))
            .catch(() => {});
        }
      };
      socket.onerror = () => {
        if (ws === socket) update("Reconectando visor del juego...", false);
      };
      socket.onclose = () => {
        if (ws !== socket) return;
        ws = null;
        ++generation;
        pending = null;
        clearPicture("Esperando senal del anfitrion...");
      };
    } catch {
      if (!stopped) update("Esperando transmision publica...", false);
    } finally {
      connecting = false;
    }
  }

  const reconnect = setInterval(() => {
    if (stopped || document.hidden) return;
    if (!ws) connect();
    else if (ws.readyState === WebSocket.OPEN &&
             lastFrameAt && performance.now() - lastFrameAt > 20000) {
      update("Conexion activa, esperando nuevos fotogramas...", false);
    }
  }, 2800);

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      if (ws) {
        const old = ws;
        ws = null;
        ++generation;
        pending = null;
        old.close(1000, "Visor en segundo plano");
      }
    } else connect();
  });

  window.addEventListener("pagehide", () => {
    stopped = true;
    ++generation;
    pending = null;
    clearInterval(reconnect);
    if (ws) ws.close(1000, "Pagina cerrada");
    ws = null;
  }, { once: true });

  if (expand) expand.addEventListener("click", () => {
    const opened = root.classList.toggle("futureo-stream-expanded");
    expand.textContent = opened ? "REDUCIR" : "AMPLIAR";
  });

  connect(); // Se ejecuta al abrir la pagina, SIN pulsar CONECTAR.
})();
