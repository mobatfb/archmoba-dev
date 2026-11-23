(() => {
  "use strict";
  // Runs in the ISOLATED extension world. Website scripts never receive the
  // pairing token or network permissions. Only controller states are posted.
  const CHANNEL = "FUTUREO_BRIDGE_SNAPSHOT_V1";
  let inFlight = false;
  let lastGood = false;

  function deliver(pads) {
    window.postMessage({
      channel: CHANNEL,
      pads,
      time: Date.now()
    }, "*");
  }

  function poll() {
    if (inFlight) return;
    inFlight = true;
    try {
      chrome.runtime.sendMessage({type:"FUTUREO_POLL"}, (reply) => {
        inFlight = false;
        if (chrome.runtime.lastError) {
          if (lastGood) deliver([]);
          lastGood = false;
          return;
        }
        if (reply?.ok && Array.isArray(reply.pads)) {
          lastGood = true;
          deliver(reply.pads);
        } else {
          if (lastGood) deliver([]);
          lastGood = false;
        }
      });
    } catch {
      inFlight = false;
    }
  }

  // Page opt-in is checked by the extension worker against the TOP tab URL.
  // If disabled, do not poll or expose any input data on the website.
  try {
    chrome.runtime.sendMessage({type:"FUTUREO_ENABLED"}, (answer) => {
      if (chrome.runtime.lastError || !answer?.allowed) return;
      poll();
      window.setInterval(poll, 60);
    });
  } catch {
    // A restricted page prevents the extension from starting.
  }
})();
