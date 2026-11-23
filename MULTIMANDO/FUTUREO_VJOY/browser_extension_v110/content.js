(() => {
  "use strict";
  // Automatic on every regular HTTP(S) game page: NO pairing or site toggles.
  // This script cannot call localhost itself. It asks its extension worker.
  const CHANNEL = "FUTUREO_BRIDGE_SNAPSHOT_V1";
  let inFlight = false;
  let previousOk = false;

  function deliver(pads) {
    window.postMessage({channel: CHANNEL, pads, time: Date.now()}, "*");
  }

  function poll() {
    if (inFlight) return;
    inFlight = true;
    try {
      chrome.runtime.sendMessage({type:"FUTUREO_POLL"}, (reply) => {
        inFlight = false;
        if (chrome.runtime.lastError) {
          if (previousOk) deliver([]);
          previousOk = false;
          return;
        }
        if (reply?.ok && Array.isArray(reply.pads)) {
          previousOk = true;
          deliver(reply.pads);
        } else {
          if (previousOk) deliver([]);
          previousOk = false;
        }
      });
    } catch {
      inFlight = false;
    }
  }

  poll();
  window.setInterval(poll, 60);
})();
