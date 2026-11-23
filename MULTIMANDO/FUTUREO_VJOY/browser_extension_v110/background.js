"use strict";

// Automatic FUTUREO bridge. No secret, login, account or site allowlist.
// Only the extension worker fetches localhost. Ordinary pages cannot use
// the extension's network permission.
const SOURCE_URL = "http://127.0.0.1:38471/state";
let inFlight = null;
let lastResult = null;
let lastAt = 0;

function sanitize(data) {
  if (!data || !Array.isArray(data.pads)) throw new Error("Sin datos de mando");
  const used = new Set();
  return data.pads.slice(0, 8).flatMap((item) => {
    if (!item || !Number.isInteger(item.slot) || item.slot < 1
        || item.slot > 8 || used.has(item.slot)
        || !Array.isArray(item.buttons) || !Array.isArray(item.axes)) return [];
    used.add(item.slot);
    return [{
      slot: item.slot,
      name: "FUTUREO_VJOY" + item.slot,
      buttons: Array.from({length:16}, (_,i) => item.buttons[i] ? 1 : 0),
      axes: [
        Number.isFinite(item.axes[0]) ? Math.max(-1,Math.min(1,item.axes[0])) : 0,
        Number.isFinite(item.axes[1]) ? Math.max(-1,Math.min(1,item.axes[1])) : 0
      ],
      hat: Number.isInteger(item.hat) && item.hat >= 0 && item.hat <= 8
        ? item.hat : 0
    }];
  });
}

async function fetchPads() {
  const now = Date.now();
  const backoff = lastResult?.ok ? 35 : 350;
  if (lastResult && now - lastAt < backoff) return lastResult;
  if (inFlight) return inFlight;

  inFlight = (async () => {
    const abort = new AbortController();
    const timeout = setTimeout(() => abort.abort(), 1200);
    try {
      const reply = await fetch(SOURCE_URL, {
        method: "GET",
        cache: "no-store",
        signal: abort.signal
      });
      if (reply.status === 403) {
        return {ok:false,error:"Otra version de FUTUREO esta abierta. Cierra v0.8.2 y abre v0.8.3."};
      }
      if (!reply.ok) return {ok:false,error:"Puente local: HTTP " + reply.status};
      const raw = await reply.json();
      return {ok:true,pads:sanitize(raw),time:Number(raw.timestamp)||Date.now()};
    } catch {
      return {ok:false,error:"Abre FUTUREO VJOY v0.8.3 para conectar automaticamente."};
    } finally {
      clearTimeout(timeout);
    }
  })();

  try {
    const result = await inFlight;
    lastAt = Date.now();
    lastResult = result;
    return result;
  } finally {
    inFlight = null;
  }
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || (message.type !== "FUTUREO_POLL"
                   && message.type !== "FUTUREO_DIAGNOSTIC")) return;
  // The popup and extension-owned content scripts are the only supported
  // callers. No externally_connectable website access is granted.
  fetchPads().then(sendResponse).catch(() => {
    sendResponse({ok:false,error:"Error interno del puente FUTUREO"});
  });
  return true;
});
