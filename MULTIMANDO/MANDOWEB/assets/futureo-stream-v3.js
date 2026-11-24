/* FUTUREO STREAM v3.0 -- FULL, DELTA, SMART (PALETTE 256).
 * Compativel con FJ22 e JPEG puro do anfitriao anterior.
 *
 * Novo protocolo FS30: cabecalho binario 32 bytes (big-endian)
 *   magic[4], tipo u8, flags u8, width u16, height u16,
 *   seq u32, base_seq u32, timestamp_ms u64, process_ms u16,
 *   fps u16, count u16; dados seguem cabecalho.
 *
 * FULL: u16 paleta_len + RGB[paleta_len*3] + JPG.
 * RGB:  count*(pos_u16/u24 + RGB3).
 * PAL:  count*(pos_u16/u24 + palette_index_u8).
 * REGION: x,y,w,h (u16) + JPEG da regiao.
 * HOLD: frame igual ao keyframe, nenhum corpo.
 *
 * Cada DELTA e INDEPENDENTE, baseado no ultimo keyframe (base_seq).
 * Isso permite descartar frames atrasados sem perder a composicao.
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

  const MAGIC_OLD = [70, 74, 50, 50];    // FJ22
  const MAGIC_NEW = [70, 83, 51, 48];    // FS30
  const MAX_PACKET = 181000;
  const FULL = 0, RGB = 1, PAL = 2, REGION = 3, HOLD = 4;
  let ws = null, connecting = false, stopped = false, generation = 0, epoch = 0;
  let baseImage = null, baseSeq = -1, palette = new Uint8Array();
  let pendingBase = null, pendingFrame = null, decoding = false;
  let lastSeq = -1, lastFrameAt = 0, frameCounter = 0, dropped = 0;
  let mode = "FULL", painted = 0, fpsVisible = 0, fpsStart = performance.now();
  let lastHudAt = 0, extraDelay = null, recentAges = [];
  let streamStart = 0;

  function update(message, live) {
    if (status.textContent !== message) status.textContent = message;
    root.classList.toggle("futureo-live", !!live);
    if (badge) badge.textContent = live ? "EN VIVO" : "SIN TRANSMISION";
  }

  function discardBitmap(bitmap) {
    if (bitmap && typeof bitmap.close === "function") bitmap.close();
  }

  function resetImage(message) {
    ++epoch;
    pendingBase = null;
    pendingFrame = null;
    discardBitmap(baseImage);
    baseImage = null;
    baseSeq = -1;
    lastSeq = -1;
    palette = new Uint8Array();
    canvas.hidden = true;
    extraDelay = null;
    recentAges = [];
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
    } catch (_) { return null; }
  }

  async function getStreamAddress() {
    const auto = document.getElementById("autoRoom");
    const manual = document.getElementById("directUrl");
    if (auto && !auto.checked) {
      return urlForStream(manual ? manual.value.trim() : "");
    }
    const response = await fetch("sala.php", {
      cache: "no-store", credentials: "same-origin",
      signal: AbortSignal.timeout(8000)
    });
    if (!response.ok) throw new Error("Sala publica no disponible");
    const data = await response.json();
    return urlForStream(data.url || "");
  }

  function matchMagic(bytes, magic) {
    return magic.every((value, i) => bytes[i] === value);
  }

  function parseFrame(raw) {
    if (!(raw instanceof ArrayBuffer) || raw.byteLength < 4 ||
        raw.byteLength > MAX_PACKET) return null;
    const bytes = new Uint8Array(raw);
    const view = new DataView(raw);
    if (bytes.length >= 32 && matchMagic(bytes, MAGIC_NEW)) {
      const kind = view.getUint8(4);
      const streamMode = view.getUint8(5);
      const width = view.getUint16(6, false);
      const height = view.getUint16(8, false);
      const seq = view.getUint32(10, false);
      const base = view.getUint32(14, false);
      const stamp = view.getUint32(18, false) * 4294967296 +
                    view.getUint32(22, false);
      const fps = view.getUint16(28, false);
      const count = view.getUint16(30, false);
      if (kind > HOLD || streamMode > 2 || !width || !height || width > 640 || height > 360 ||
          count > 7000 || fps > 60) return null;
      const common = { kind, width, height, seq, baseSeq: base, stamp,
                       fps, count, raw, offset: 32, v3: true,
                       codec: ["FULL", "DELTA", "SMART"][streamMode] };
      if (kind === FULL) {
        if (base !== seq || raw.byteLength < 36) return null;
        const paletteCount = view.getUint16(32, false);
        if (paletteCount > 256 || count !== paletteCount) return null;
        const jpegStart = 34 + paletteCount * 3;
        if (jpegStart + 2 > raw.byteLength ||
            bytes[jpegStart] !== 255 || bytes[jpegStart + 1] !== 216) return null;
        common.colors = new Uint8Array(raw.slice(34, jpegStart));
        common.blob = new Blob([raw.slice(jpegStart)], { type: "image/jpeg" });
      } else if (kind === RGB || kind === PAL) {
        const positionBytes = width * height <= 65535 ? 2 : 3;
        const recordSize = positionBytes + (kind === PAL ? 1 : 3);
        if (32 + count * recordSize !== raw.byteLength || base === 0) return null;
        common.positionBytes = positionBytes;
      } else if (kind === REGION) {
        if (count !== 1 || raw.byteLength < 42 || base === 0) return null;
        common.x = view.getUint16(32, false);
        common.y = view.getUint16(34, false);
        common.rectW = view.getUint16(36, false);
        common.rectH = view.getUint16(38, false);
        if (!common.rectW || !common.rectH ||
            common.x + common.rectW > width ||
            common.y + common.rectH > height ||
            bytes[40] !== 255 || bytes[41] !== 216) return null;
        common.blob = new Blob([raw.slice(40)], { type: "image/jpeg" });
      } else if (raw.byteLength !== 32 || count !== 0 || base === 0) {
        return null;
      }
      return common;
    }
    if (bytes.length >= 22 && matchMagic(bytes, MAGIC_OLD)) {
      const seq = view.getUint32(4, false);
      const stamp = view.getUint32(8, false) * 4294967296 +
                    view.getUint32(12, false);
      if (bytes[20] !== 255 || bytes[21] !== 216) return null;
      return {
        kind: FULL, seq, baseSeq: seq, stamp,
        width: 0, height: 0, fps: view.getUint16(18, false), v3: false,
        colors: new Uint8Array(),
        blob: new Blob([raw.slice(20)], { type: "image/jpeg" })
      };
    }
    if (bytes[0] === 255 && bytes[1] === 216) {
      ++frameCounter;
      return {
        kind: FULL, seq: frameCounter, baseSeq: frameCounter,
        stamp: 0, fps: 0, width: 0, height: 0, v3: false,
        colors: new Uint8Array(),
        blob: new Blob([raw], { type: "image/jpeg" })
      };
    }
    return null;
  }

  function noteFrame() {
    lastFrameAt = performance.now();
    painted++;
    if (lastFrameAt - fpsStart >= 1200) {
      fpsVisible = painted * 1000 / Math.max(1, lastFrameAt - fpsStart);
      painted = 0;
      fpsStart = lastFrameAt;
    }
    if (lastFrameAt - lastHudAt > 950) {
      const rate = fpsVisible ? fpsVisible.toFixed(1) : "—";
      const lag = extraDelay === null ? "" :
        " · cola aprox " + Math.round(extraDelay) + " ms";
      update(mode + " · " + rate + " FPS" + lag, true);
      lastHudAt = lastFrameAt;
    } else if (!root.classList.contains("futureo-live")) {
      update("Imagen en directo · FUTUREO " + mode, true);
    }
  }

  function readPosition(data, off, size) {
    if (size === 2) return (data[off] << 8) | data[off + 1];
    return (data[off] * 65536) + (data[off + 1] << 8) + data[off + 2];
  }

  function validPixelRecords(job) {
    const values = new Uint8Array(job.raw, 32);
    const recordSize = job.positionBytes + (job.kind === PAL ? 1 : 3);
    for (let i = 0; i < job.count; i++) {
      const offset = i * recordSize;
      const pos = readPosition(values, offset, job.positionBytes);
      if (pos >= job.width * job.height) return false;
      if (job.kind === PAL &&
          values[offset + job.positionBytes] * 3 + 2 >= palette.length) return false;
    }
    return true;
  }

  function paintPixels(job) {
    if (!baseImage || !validPixelRecords(job)) return false;
    const bytes = new Uint8Array(job.raw, 32);
    const stride = job.positionBytes + (job.kind === PAL ? 1 : 3);
    ctx.drawImage(baseImage, 0, 0, job.width, job.height);
    const perPixel = job.count <= 80;
    let imageData = null;
    if (!perPixel) {
      if (!ctx.getImageData || !ctx.putImageData) return false;
      imageData = ctx.getImageData(0, 0, job.width, job.height);
    }
    for (let i = 0; i < job.count; i++) {
      const start = i * stride;
      const pos = readPosition(bytes, start, job.positionBytes);
      const x = pos % job.width;
      const y = Math.floor(pos / job.width);
      const colorAt = start + job.positionBytes;
      const palAt = job.kind === PAL ? bytes[colorAt] * 3 : 0;
      const red = job.kind === PAL ? palette[palAt] : bytes[colorAt];
      const green = job.kind === PAL ? palette[palAt + 1] : bytes[colorAt + 1];
      const blue = job.kind === PAL ? palette[palAt + 2] : bytes[colorAt + 2];
      if (perPixel) {
        ctx.fillStyle = "rgb(" + red + "," + green + "," + blue + ")";
        ctx.fillRect(x, y, 1, 1);
      } else {
        const pixel = pos * 4;
        imageData.data[pixel] = red;
        imageData.data[pixel + 1] = green;
        imageData.data[pixel + 2] = blue;
        imageData.data[pixel + 3] = 255;
      }
    }
    if (imageData) ctx.putImageData(imageData, 0, 0);
    return true;
  }

  function decodeJPEG(blob) {
    if (typeof createImageBitmap === "function") return createImageBitmap(blob);
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
      while (!stopped && !document.hidden && (pendingBase || pendingFrame)) {
        const full = pendingBase;
        if (full) {
          pendingBase = null;
          let decoded = null;
          try {
            decoded = await decodeJPEG(full.blob);
            if (full.token !== generation || full.epoch !== epoch ||
                (pendingBase && pendingBase.seq > full.seq) ||
                (full.seq <= lastSeq && baseSeq === full.seq)) {
              dropped++;
              continue;
            }
            if (full.v3 && (decoded.width !== full.width ||
                            decoded.height !== full.height)) {
              throw new Error("Resolucion del keyframe invalida");
            }
            const oldImage = baseImage;
            baseImage = decoded;
            decoded = null; // La imagen queda guardada hasta siguiente keyframe.
            discardBitmap(oldImage);
            baseSeq = full.seq;
            palette = full.colors || new Uint8Array();
            if (canvas.width !== baseImage.width || canvas.height !== baseImage.height) {
              canvas.width = baseImage.width;
              canvas.height = baseImage.height;
            }
            ctx.drawImage(baseImage, 0, 0, baseImage.width, baseImage.height);
            canvas.hidden = false;
            lastSeq = full.seq;
            if (pendingFrame && pendingFrame.baseSeq !== baseSeq &&
                pendingFrame.baseSeq < baseSeq) pendingFrame = null;
            noteFrame();
          } catch (error) {
            if (!root.classList.contains("futureo-live"))
              update("Esperando fotograma completo valido...", false);
          } finally {
            discardBitmap(decoded);
          }
          continue;
        }
        const job = pendingFrame;
        if (!job) continue;
        if (!baseImage || baseSeq !== job.baseSeq) {
          if (job.baseSeq < baseSeq) pendingFrame = null;
          // Si falta un keyframe, no se puede reconstruir. /stream es TCP:
          // el servidor enviara un nuevo keyframe al reconectar.
          break;
        }
        pendingFrame = null;
        if (job.seq <= lastSeq || job.token !== generation || job.epoch !== epoch) {
          dropped++;
          continue;
        }
        try {
          if (job.kind === RGB || job.kind === PAL) {
            if (!paintPixels(job)) throw new Error("Delta de pixel invalido");
          } else if (job.kind === HOLD) {
            ctx.drawImage(baseImage, 0, 0, job.width, job.height);
          } else if (job.kind === REGION) {
            let bitmap = null;
            try {
              bitmap = await decodeJPEG(job.blob);
              if (job.token !== generation || job.epoch !== epoch ||
                  job.baseSeq !== baseSeq ||
                  (pendingFrame && pendingFrame.seq > job.seq)) {
                dropped++;
                continue;
              }
              if (bitmap.width !== job.rectW || bitmap.height !== job.rectH)
                throw new Error("Dimension de region invalida");
              ctx.drawImage(baseImage, 0, 0, job.width, job.height);
              ctx.drawImage(bitmap, job.x, job.y, job.rectW, job.rectH);
            } finally {
              discardBitmap(bitmap);
            }
          }
          canvas.hidden = false;
          lastSeq = job.seq;
          noteFrame();
        } catch (_) {
          update("Esperando resincronizacion de imagen...", false);
        }
      }
    } finally {
      decoding = false;
    }
  }

  function acceptFrame(raw, token) {
    if (token !== generation || stopped || document.hidden) return;
    const frame = parseFrame(raw);
    if (!frame || frame.seq <= lastSeq) return;
    if (frame.codec) mode = frame.codec;
    const apparent = frame.stamp ? Date.now() - frame.stamp : null;
    if (apparent !== null && Number.isFinite(apparent)) {
      recentAges.push(apparent);
      if (recentAges.length > 45) recentAges.shift();
      const baseline = Math.min(...recentAges);
      extraDelay = Math.max(0, apparent - baseline);
      // Un keyframe no puede descartarse por edad: seria perder el punto
      // de referencia de todos los DELTA posteriores.
      if (frame.kind !== FULL &&
          extraDelay > Math.max(320, Math.round(2000 / Math.max(1, frame.fps))) &&
          performance.now() - lastFrameAt < 400) {
        dropped++;
        return;
      }
    }
    frame.token = token;
    frame.epoch = epoch;
    if (frame.kind === FULL) {
      if (pendingBase) dropped++;
      pendingBase = frame;
      // Guardar el ultimo delta SOLO si se refiere al nuevo keyframe.
      if (pendingFrame && pendingFrame.baseSeq !== frame.seq) pendingFrame = null;
    } else {
      if (pendingFrame) dropped++;
      pendingFrame = frame;
    }
    drainLatest();
  }

  async function connect() {
    if (stopped || document.hidden || connecting || ws) return;
    connecting = true;
    try {
      const address = await getStreamAddress();
      if (stopped || document.hidden) return;
      if (!address) {
        update("Esperando sala publicada para ver el juego...", false);
        return;
      }
      const socket = new WebSocket(address);
      socket.binaryType = "arraybuffer";
      ws = socket;
      const token = ++generation;
      resetImage("Conectando visor del juego...");
      fpsVisible = 0; painted = 0; fpsStart = performance.now(); lastHudAt = 0;
      streamStart = performance.now();
      socket.onopen = () => {
        if (ws !== socket) return;
        // En hosts v2.2 se ignora este hello, y se mantiene FJ22.
        try { socket.send("FV3"); } catch (_) {}
        update("Canal abierto. Esperando imagen...", false);
      };
      socket.onmessage = event => {
        if (ws !== socket || token !== generation) return;
        if (typeof event.data === "string") {
          try {
            const msg = JSON.parse(event.data);
            if (msg.type === "futureo_stream") {
              mode = typeof msg.mode === "string" ? msg.mode.toUpperCase() : "FULL";
              if (!msg.active) resetImage("El anfitrion no esta transmitiendo");
              else if (!baseImage && !pendingBase)
                update("Captura iniciada. Esperando imagen...", false);
            }
          } catch (_) {}
          return;
        }
        if (event.data instanceof ArrayBuffer) {
          acceptFrame(event.data, token);
        } else if (event.data instanceof Blob) {
          event.data.arrayBuffer().then(data => acceptFrame(data, token))
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
        resetImage("Esperando señal del anfitrion...");
      };
    } catch (_) {
      if (!stopped) update("Esperando transmision publica...", false);
    } finally {
      connecting = false;
    }
  }

  const reconnect = setInterval(() => {
    if (stopped || document.hidden) return;
    if (!ws) return void connect();
    if (ws.readyState === WebSocket.OPEN && lastFrameAt &&
        performance.now() - lastFrameAt > 20000) {
      update("Conexion abierta, esperando fotogramas...", false);
    }
    if (ws.readyState === WebSocket.OPEN && pendingFrame && !baseImage &&
        performance.now() - streamStart > 5000) {
      ws.close(1000, "Falta keyframe para reconstruir");
    }
  }, 2800);

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      if (ws) {
        const previous = ws;
        ws = null;
        ++generation;
        previous.close(1000, "Visor en segundo plano");
      }
      resetImage("Visor en segundo plano");
    } else connect();
  });

  window.addEventListener("pagehide", () => {
    stopped = true;
    ++generation;
    clearInterval(reconnect);
    if (ws) ws.close(1000, "Pagina cerrada");
    ws = null;
    resetImage("Visor cerrado");
  }, { once: true });

  if (expand) expand.addEventListener("click", () => {
    const opened = root.classList.toggle("futureo-stream-expanded");
    expand.textContent = opened ? "REDUCIR" : "AMPLIAR";
  });
  connect(); // La transmision se ve incluso antes de pulsar CONECTAR mando.
})();
