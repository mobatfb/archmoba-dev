/* FUTUREO v3: FULL/DELTA/SMART, colores, frame base, JPEG anterior, visor anonimo. */
"use strict";
const assert = require("node:assert/strict");
const vm = require("node:vm");
const fs = require("node:fs");
const path = require("node:path");
const source = fs.readFileSync(
  path.join(__dirname, "..", "assets", "futureo-stream-v3.js"), "utf8");

const colors = [], renders = [];
const classes = new Set();
const root = { classList: {
  toggle(name, value) {
    const yes = value === undefined ? !classes.has(name) : !!value;
    if (yes) classes.add(name); else classes.delete(name);
    return yes;
  },
  contains(name) { return classes.has(name); }
}};
const status = { textContent: "" }, badge = { textContent: "" };
const canvas = {
  hidden: true, width: 0, height: 0,
  getContext() {
    return {
      drawImage(image, x, y, w, h) {
        renders.push(["draw", x, y, w, h, image.width, image.height]);
      },
      fillRect(x, y, w, h) {
        colors.push([x, y, w, h, this.fillStyle]);
      },
      getImageData(_x, _y, w, h) {
        return { data: new Uint8ClampedArray(w * h * 4) };
      },
      putImageData(data) {
        renders.push(["pixels", data.data.length]);
      }
    };
  }
};
const expand = { textContent: "", addEventListener(event, fn) {
  if (event === "click") this.click = fn;
} };
const elements = {
  futureoStream: root, futureoStreamImage: canvas,
  futureoStreamStatus: status, futureoStreamBadge: badge,
  futureoStreamSettings: expand, autoRoom: { checked: true },
  directUrl: { value: "" }
};
const sockets = [];
let tick = null;
class WS {
  static OPEN = 1;
  constructor(url) {
    this.url = url; this.readyState = 1; this.binaryType = "blob";
    this.sent = []; sockets.push(this);
  }
  send(value) { this.sent.push(value); }
  close() {
    this.readyState = 3;
    if (this.onclose) this.onclose();
  }
  message(value) { this.onmessage({ data: value }); }
}
function pack(kind, seq, base, count, payload, width = 320, height = 180) {
  const out = new ArrayBuffer(32 + payload.length);
  const b = new Uint8Array(out);
  b.set([70, 83, 51, 48], 0);
  const view = new DataView(out);
  view.setUint8(4, kind);
  view.setUint8(5, 2); // SMART STREAM
  view.setUint16(6, width, false);
  view.setUint16(8, height, false);
  view.setUint32(10, seq, false);
  view.setUint32(14, base, false);
  const stamp = Date.now() - 50;
  view.setUint32(18, Math.floor(stamp / 4294967296), false);
  view.setUint32(22, stamp % 4294967296, false);
  view.setUint16(26, 4, false);
  view.setUint16(28, 15, false);
  view.setUint16(30, count, false);
  b.set(payload, 32);
  return out;
}
const jpg = [255, 216, 0, 0, 255, 217];
const palette = [255, 0, 0, 0, 255, 0];
function full(seq) {
  const p = [0, 2, ...palette, ...jpg];
  return pack(0, seq, seq, 2, p);
}
function pal(seq, base, x, y, colorIndex) {
  const offset = y * 320 + x;
  return pack(2, seq, base, 1,
    [offset >> 8, offset & 255, colorIndex]);
}
function rgb(seq, base, x, y, r, g, b) {
  const offset = y * 320 + x;
  return pack(1, seq, base, 1,
    [offset >> 8, offset & 255, r, g, b]);
}
function region(seq, base, x, y, w, h) {
  return pack(3, seq, base, 1,
    [0, x, 0, y, 0, w, 0, h, 255, 216, 1, w, h, 255, 217]);
}
function legacy(seq) {
  const out = new ArrayBuffer(20 + jpg.length), b = new Uint8Array(out);
  b.set([70, 74, 50, 50], 0);
  const view = new DataView(out), stamp = Date.now() - 55;
  view.setUint32(4, seq, false);
  view.setUint32(8, Math.floor(stamp / 4294967296), false);
  view.setUint32(12, stamp % 4294967296, false);
  view.setUint16(18, 15, false);
  b.set(jpg, 20);
  return out;
}
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const sandbox = {
  document: {
    hidden: false,
    getElementById(id) { return elements[id]; },
    addEventListener() {}
  },
  window: { addEventListener() {} },
  location: { href: "https://tiendavibechic.com/multimando/" },
  WebSocket: WS,
  Blob, ArrayBuffer, Uint8Array, Uint8ClampedArray, DataView, URL,
  Date, Math, Number, Promise, console,
  performance: { now: () => Date.now() },
  setInterval(fn) { tick = fn; return 1; },
  clearInterval() {},
  AbortSignal: { timeout() { return undefined; } },
  fetch: async () => ({
    ok: true, json: async () => ({ url: "https://anfitrion.trycloudflare.com/" })
  }),
  createImageBitmap: async blob => {
    await sleep(5);
    const bytes = new Uint8Array(await blob.arrayBuffer());
    if (bytes[2] === 1) {
      return { width: bytes[3], height: bytes[4], close() {} };
    }
    return { width: 320, height: 180, close() {} };
  },
  Image: class {}
};

(async () => {
  vm.runInNewContext(source, sandbox, { filename: "futureo-stream-v3.js" });
  await sleep(12);
  assert.equal(sockets.length, 1);
  const sock = sockets[0];
  assert.equal(sock.url, "wss://anfitrion.trycloudflare.com/stream");
  assert.equal(sock.binaryType, "arraybuffer");
  sock.onopen();
  assert.deepEqual(sock.sent, ["FV3"],
    "El visor solo negocia capacidad; jamas envia comandos de mando");

  // Cliente nuevo primero recibe un keyframe con paleta de 2 colores.
  sock.message(JSON.stringify({ type: "futureo_stream",
                                active: true, mode: "smart", protocol: 3 }));
  sock.message(full(1));
  await sleep(18);
  assert.equal(canvas.hidden, false);
  assert.equal(canvas.width, 320);
  assert.equal(canvas.height, 180);
  assert.ok(classes.has("futureo-live"));
  const orig = renders.length;

  // Registro PAL 2B posicion + 1B indice, color verde de paleta 1.
  sock.message(pal(2, 1, 64, 80, 1));
  await sleep(8);
  assert.deepEqual(colors.at(-1), [64, 80, 1, 1, "rgb(0,255,0)"]);
  assert.ok(renders.length > orig);

  // RGB cuando el color no forma parte de la paleta.
  sock.message(rgb(3, 1, 245, 132, 12, 34, 56));
  await sleep(8);
  assert.deepEqual(colors.at(-1), [245, 132, 1, 1, "rgb(12,34,56)"]);

  sock.message(region(4, 1, 10, 20, 16, 12));
  await sleep(15);
  assert.ok(renders.some(r => r[0] === "draw" &&
                             r[1] === 10 && r[2] === 20 &&
                             r[3] === 16 && r[4] === 12));

  // Dos actualizaciones pueden saltarse: ambas usan el mismo base_seq=1.
  sock.message(pal(5, 1, 1, 1, 0));
  sock.message(pal(6, 1, 2, 2, 1));
  await sleep(12);
  assert.deepEqual(colors.at(-1), [2, 2, 1, 1, "rgb(0,255,0)"]);

  // Un nuevo keyframe reemplaza el anterior y reinicia la referencia.
  sock.message(full(7));
  await sleep(16);
  const numColors = colors.length;
  sock.message(pal(8, 1, 5, 5, 0)); // Referencia antigua: no aplicar.
  await sleep(10);
  assert.equal(colors.length, numColors);
  sock.message(pal(9, 7, 33, 55, 0));
  await sleep(8);
  assert.deepEqual(colors.at(-1), [33, 55, 1, 1, "rgb(255,0,0)"]);

  // Reversa temporal a JPEG antiguo FJ22 tras actualizar anfitrion.
  sock.message(legacy(10));
  await sleep(16);
  assert.equal(canvas.hidden, false);

  // Evento STOP descarta cualquier captura pendiente.
  sock.message(region(11, 10, 12, 12, 16, 12));
  sock.message(JSON.stringify({ type: "futureo_stream", active: false }));
  await sleep(20);
  assert.equal(canvas.hidden, true);
  assert.ok(!classes.has("futureo-live"));

  expand.click();
  assert.ok(classes.has("futureo-stream-expanded"));
  assert.equal(typeof tick, "function");
  console.log("OK: visor /stream FS30 FULL PAL RGB REGION, skip, keyframe, FJ22 y STOP");
})().catch(error => { console.error(error); process.exitCode = 1; });
