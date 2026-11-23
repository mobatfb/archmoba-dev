/* Smoke test del visor publico v2.2: sin pulsar CONECTAR ni mandar input. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

const source = fs.readFileSync(
  path.join(__dirname, "..", "assets", "futureo-stream.js"), "utf8");
const draws = [];
const statuses = { textContent: "" };
const badge = { textContent: "" };
const classes = new Set();
const root = { classList: {
  toggle(name, flag) {
    if (flag === undefined) flag = !classes.has(name);
    if (flag) classes.add(name); else classes.delete(name);
    return !!flag;
  },
  contains(name) { return classes.has(name); }
}};
const canvas = {
  width: 0, height: 0, hidden: true,
  getContext() {
    return { drawImage(_img, _x, _y, w, h) { draws.push([w, h]); } };
  }
};
const expand = {
  textContent: "", addEventListener(_event, fn) { this.click = fn; }
};
const elements = {
  futureoStream: root,
  futureoStreamImage: canvas,
  futureoStreamStatus: statuses,
  futureoStreamBadge: badge,
  futureoStreamSettings: expand,
  autoRoom: { checked: true },
  directUrl: { value: "" },
};
let sockets = [];
class WS {
  static OPEN = 1;
  static CONNECTING = 0;
  constructor(url) {
    this.url = url;
    this.readyState = 1;
    this.binaryType = "blob";
    sockets.push(this);
  }
  send() { throw new Error("El espectador NO debe enviar mensajes"); }
  close() { this.readyState = 3; if (this.onclose) this.onclose(); }
  message(data) { this.onmessage({ data }); }
}
function headerFrame(seq) {
  const result = new ArrayBuffer(24);
  const bytes = new Uint8Array(result);
  [70, 74, 50, 50].forEach((n, i) => bytes[i] = n);
  const view = new DataView(result);
  view.setUint32(4, seq, false);
  const epoch = Date.now() - 100;
  view.setUint32(8, Math.floor(epoch / 4294967296), false);
  view.setUint32(12, epoch % 4294967296, false);
  view.setUint16(16, 3, false);
  view.setUint16(18, 15, false);
  bytes.set([255, 216, 255, 217], 20);
  return result;
}
function sleep(ms) { return new Promise(resolve => setTimeout(resolve, ms)); }

const sandbox = {
  document: {
    hidden: false,
    getElementById(id) { return elements[id]; },
    addEventListener() {},
  },
  window: { addEventListener() {} },
  location: { href: "https://tiendavibechic.com/multimando/" },
  WebSocket: WS,
  Blob, ArrayBuffer, Uint8Array, DataView, URL,
  Date, Math, Number, Promise, console,
  performance: { now: () => Date.now() },
  setInterval: () => 1, clearInterval: () => {},
  AbortSignal: { timeout() { return undefined; } },
  fetch: async () => ({
    ok: true, json: async () => ({ url: "https://sala.trycloudflare.com/" })
  }),
  createImageBitmap: async () => {
    await sleep(22); // Decode mas lento que llegada de los fotogramas.
    return { width: 320, height: 180, close() {} };
  },
  Image: class {}
};

(async () => {
  vm.runInNewContext(source, sandbox, { filename: "futureo-stream.js" });
  await sleep(5);
  assert.equal(sockets.length, 1, "La pagina abre el visor sin login");
  const ws = sockets[0];
  assert.equal(ws.url, "wss://sala.trycloudflare.com/stream");
  assert.equal(ws.binaryType, "arraybuffer");
  ws.onopen();
  ws.message(headerFrame(1));
  ws.message(headerFrame(2));
  ws.message(headerFrame(3));
  await sleep(85);
  assert.equal(draws.length, 1,
    "Debe mostrar solo el ultimo de varios fotogramas recibidos");
  assert.equal(canvas.hidden, false);
  assert.equal(canvas.width, 320);
  assert.equal(canvas.height, 180);
  assert.ok(classes.has("futureo-live"));

  // Una captura desactivada NO puede volver a aparecer porque termina
  // de decodificarse mas tarde que el aviso STOP.
  ws.message(headerFrame(4));
  ws.message(JSON.stringify({ type: "futureo_stream", active: false }));
  await sleep(55);
  assert.equal(draws.length, 1, "No pintar JPG despues de STOP");
  assert.equal(canvas.hidden, true);
  assert.ok(!classes.has("futureo-live"));

  expand.click();
  assert.ok(classes.has("futureo-stream-expanded"));
  console.log("OK: visor anonimo, URL /stream, latest-frame, STOP y pantalla ampliada");
})().catch(e => { console.error(e); process.exitCode = 1; });
