"use strict";

// FUTUREO Bridge: ONLY the extension's own service worker can read the
// localhost state endpoint. The secret never enters the web page context.
const FUTUREO_URL = "http://127.0.0.1:38471/state";
let configuration;
let lastData;
let lastFetchTime = 0;
let flight = null;

async function config() {
  if (!configuration) {
    configuration = chrome.storage.local.get({
      bridgeToken: "",
      allowedSites: []
    });
  }
  return configuration;
}

chrome.storage.onChanged.addListener((changes, area) => {
  if (area !== "local") return;
  if ("bridgeToken" in changes || "allowedSites" in changes) {
    configuration = null;
    lastData = null;
    lastFetchTime = 0;
  }
});

function allowedForUrl(settings, url) {
  try {
    const parsed = new URL(url);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") return false;
    return Array.isArray(settings.allowedSites)
      && settings.allowedSites.includes(parsed.origin);
  } catch {
    return false;
  }
}

function cleanPads(value) {
  if (!value || !Array.isArray(value.pads)) throw new Error("Datos de mandos invalidos");
  const seen = new Set();
  return value.pads.slice(0, 8).flatMap((item) => {
    if (!item || !Number.isInteger(item.slot) || item.slot < 1 || item.slot > 8
        || seen.has(item.slot)) return [];
    seen.add(item.slot);
    if (!Array.isArray(item.buttons) || !Array.isArray(item.axes)) return [];
    return [{
      slot: item.slot,
      name: "FUTUREO_VJOY" + item.slot,
      buttons: Array.from({length: 16}, (_, i) => item.buttons[i] ? 1 : 0),
      axes: [
        Number.isFinite(item.axes[0]) ? Math.max(-1, Math.min(1, item.axes[0])) : 0,
        Number.isFinite(item.axes[1]) ? Math.max(-1, Math.min(1, item.axes[1])) : 0
      ],
      hat: Number.isInteger(item.hat) && item.hat >= 0 && item.hat <= 8
        ? item.hat : 0
    }];
  });
}

async function readLocalBridge(token) {
  if (!/^[\dA-Fa-f]{64}$/.test(token)) {
    return {ok: false, error: "Copia la clave desde FUTUREO VJOY v0.8.2"};
  }

  if (flight) return flight;
  const now = Date.now();
  if (lastData && now - lastFetchTime < 45) return lastData;

  flight = (async () => {
    const stop = new AbortController();
    const watchdog = setTimeout(() => stop.abort(), 1200);
    try {
      const response = await fetch(FUTUREO_URL, {
        method: "GET",
        cache: "no-store",
        signal: stop.signal,
        headers: { "X-Futureo-Token": token }
      });
      if (response.status === 403) {
        return {ok: false, error: "Clave no autorizada; copiala de FUTUREO nuevamente"};
      }
      if (!response.ok) return {ok: false, error: "Puente local: HTTP " + response.status};
      const raw = await response.json();
      return {ok: true, pads: cleanPads(raw), time: Number(raw.timestamp) || Date.now()};
    } catch (error) {
      return {ok: false, error: "Puente no disponible: abre FUTUREO VJOY v0.8.2"};
    } finally {
      clearTimeout(watchdog);
    }
  })();

  try {
    const result = await flight;
    lastFetchTime = Date.now();
    lastData = result;
    return result;
  } finally {
    flight = null;
  }
}

chrome.runtime.onMessage.addListener((message, sender, reply) => {
  if (!message || typeof message.type !== "string") return;

  if (message.type === "FUTUREO_ENABLED") {
    (async () => {
      const settings = await config();
      reply({allowed: !!sender.tab && allowedForUrl(settings, sender.tab.url)});
    })().catch(() => reply({allowed:false}));
    return true;
  }

  if (message.type === "FUTUREO_POLL") {
    (async () => {
      const settings = await config();
      if (!sender.tab || !allowedForUrl(settings, sender.tab.url)) {
        reply({ok:false, disabled:true});
        return;
      }
      reply(await readLocalBridge(settings.bridgeToken));
    })().catch(() => reply({ok:false, error:"Error del servicio de la extension"}));
    return true;
  }

  if (message.type === "FUTUREO_DIAGNOSTIC") {
    (async () => {
      const settings = await config();
      reply(await readLocalBridge(settings.bridgeToken));
    })().catch(() => reply({ok:false, error:"Error de diagnostico"}));
    return true;
  }
});
