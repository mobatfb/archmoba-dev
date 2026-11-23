"use strict";

const $ = (id) => document.getElementById(id);
let currentTab = null;
let siteOrigin = "";

function result(text, kind = "") {
  const node = $("result");
  node.textContent = text;
  node.className = "result" + (kind ? " " + kind : "");
}

async function init() {
  try {
    const settings = await chrome.storage.local.get({
      bridgeToken: "", allowedSites: []
    });
    $("token").value = settings.bridgeToken || "";
    const tabs = await chrome.tabs.query({active:true, currentWindow:true});
    currentTab = tabs[0] || null;
    const url = new URL(currentTab?.url || "about:blank");
    const supported = url.protocol === "http:" || url.protocol === "https:";
    if (supported) {
      siteOrigin = url.origin;
      $("site").textContent = siteOrigin;
      $("enabled").checked = (settings.allowedSites || []).includes(siteOrigin);
    } else {
      $("site").textContent = "Abre una página HTTP/HTTPS del juego.";
      $("enabled").disabled = true;
    }
    if (settings.bridgeToken) {
      result("Clave guardada. Pulsa Comprobar puente local.");
    }
  } catch (error) {
    $("enabled").disabled = true;
    result("No se pudo consultar la pestaña: " + error.message, "err");
  }
}

$("show").addEventListener("click", () => {
  const input = $("token");
  const visible = input.type === "text";
  input.type = visible ? "password" : "text";
  $("show").textContent = visible ? "Ver" : "Ocultar";
});

$("saveToken").addEventListener("click", async () => {
  const token = $("token").value.trim().toUpperCase();
  if (!/^[0-9A-F]{64}$/.test(token)) {
    result("Clave inválida. Pulsa CLAVE WEB en FUTUREO v0.8.2 y pégala aquí.", "err");
    return;
  }
  try {
    await chrome.storage.local.set({bridgeToken:token});
    result("Clave guardada. El navegador no comparte la clave con el juego.", "ok");
  } catch (error) {
    result("No se pudo guardar la clave: " + error.message, "err");
  }
});

$("enabled").addEventListener("change", async () => {
  const enabled = $("enabled").checked;
  if (!siteOrigin || !currentTab) return;
  try {
    const {allowedSites = []} = await chrome.storage.local.get({allowedSites:[]});
    const next = new Set(allowedSites);
    if (enabled) next.add(siteOrigin);
    else next.delete(siteOrigin);
    await chrome.storage.local.set({allowedSites:[...next]});
    result(enabled
      ? "Sitio autorizado. Recargando para conectar antes de iniciar el juego."
      : "Sitio desautorizado. Recargando para retirar el puente.", "ok");
    await chrome.tabs.reload(currentTab.id);
  } catch (error) {
    $("enabled").checked = !enabled;
    result("No se pudo activar el sitio: " + error.message, "err");
  }
});

$("test").addEventListener("click", async () => {
  result("Consultando el puente local…");
  try {
    const state = await chrome.runtime.sendMessage({type:"FUTUREO_DIAGNOSTIC"});
    if (!state?.ok) {
      result(state?.error || "No se recibió respuesta del puente local.", "err");
      return;
    }
    const pads = state.pads || [];
    if (pads.length === 0) {
      result("Puente vinculado y activo.\nTodavía no hay mandos iniciados. Créalos en FUTUREO.", "ok");
      return;
    }
    result("¡Puente conectado!\n" + pads.length + " mando(s):\n"
      + pads.map(p => p.name).join("\n")
      + "\n\nActiva el sitio del juego y recarga la página.", "ok");
  } catch (error) {
    result("No se pudo contactar al servicio: " + error.message, "err");
  }
});

$("tester").addEventListener("click", async () => {
  try {
    await chrome.tabs.create({url:"https://hardwaretester.com/gamepad"});
  } catch (error) {
    result("No se pudo abrir el comprobador: " + error.message, "err");
  }
});

init();
