"use strict";
const statusNode = document.getElementById("status");
const padsNode = document.getElementById("pads");
const dot = document.getElementById("dot");

async function refresh() {
  try {
    const reply = await chrome.runtime.sendMessage({type:"FUTUREO_DIAGNOSTIC"});
    padsNode.replaceChildren();
    if (!reply?.ok) {
      statusNode.textContent = reply?.error || "Abre FUTUREO VJOY v0.8.3.";
      statusNode.className = "status err";
      dot.className = "dot err";
      return;
    }
    const pads = reply.pads || [];
    statusNode.textContent = pads.length
      ? "CONECTADO AUTOMÁTICAMENTE · " + pads.length + " mando(s)"
      : "Puente conectado. Inicia tus mandos en FUTUREO.";
    statusNode.className = "status ok";
    dot.className = "dot ok";
    for (const pad of pads) {
      const row = document.createElement("div");
      row.className = "pad";
      row.textContent = pad.name;
      padsNode.appendChild(row);
    }
  } catch {
    statusNode.textContent = "El puente local no responde. Abre FUTUREO VJOY v0.8.3.";
    statusNode.className = "status err";
    dot.className = "dot err";
  }
}

document.getElementById("tester").addEventListener("click", () => {
  chrome.tabs.create({url:"https://hardwaretester.com/gamepad"});
});
refresh();
window.setInterval(refresh, 1500);
