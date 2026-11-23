(() => {
  "use strict";
  // Runs in Chrome/Edge MAIN world at document_start so the game's own
  // javascript calls this wrapper. Does not patch the OS or native HID driver.
  if (window.__FUTUREO_GAMEPAD_SHIM_V1__) return;
  Object.defineProperty(window, "__FUTUREO_GAMEPAD_SHIM_V1__", {value:true});

  const CHANNEL = "FUTUREO_BRIDGE_SNAPSHOT_V1";
  const originals = {
    getGamepads: typeof navigator.getGamepads === "function"
      ? navigator.getGamepads : null,
    webkitGetGamepads: typeof navigator.webkitGetGamepads === "function"
      ? navigator.webkitGetGamepads : null
  };
  const virtual = new Map();
  let enabled = false;
  let lastUpdate = 0;

  const clamp = (n) => Number.isFinite(n) ? Math.max(-1, Math.min(1,n)) : 0;
  const isPressed = (x) => x === true || x === 1;
  const button = () => ({pressed:false, touched:false, value:0});
  const keyFor = (slot) => "FUTUREO_VJOY" + slot;

  function createPad(slot) {
    // Gamepad() is not publicly constructible; a JS facade is used.
    // The prototype is retained for best-effort instanceof checks.
    const proto = typeof Gamepad === "function" ? Gamepad.prototype : Object.prototype;
    const pad = Object.create(proto);
    Object.defineProperties(pad, {
      id: {value:keyFor(slot) + " (FUTUREO Browser Bridge)", enumerable:true},
      index: {value:slot - 1, writable:true, enumerable:true},
      connected: {value:true, writable:true, enumerable:true},
      mapping: {value:"standard", enumerable:true},
      buttons: {value:Array.from({length:20},button), enumerable:true},
      axes: {value:[0,0,0,0], enumerable:true},
      timestamp: {value:performance.now(), writable:true, enumerable:true},
      vibrationActuator: {value:null, enumerable:true},
      hapticActuators: {value:[], enumerable:true}
    });
    return pad;
  }

  function updateButton(pad, index, pressed) {
    const b = pad.buttons[index];
    if (!b) return;
    b.pressed = !!pressed;
    b.touched = !!pressed;
    b.value = pressed ? 1 : 0;
  }

  function fromNativeOrder(original, i) {
    return !!original?.[i];
  }

  function updatePad(pad, snapshot) {
    const b = snapshot.buttons;
    // The v0.8.x order: X,Y,L,A,B,R,SELECT,START,L3,R3,HOME,
    // TOUCH,SHARE,P1,P2,EXTRA.
    // Standard Gamepad order: A,B,X,Y,L1,R1,L2,R2,BACK,START,
    // L3,R3,UP,DOWN,LEFT,RIGHT,HOME, then three extras.
    const map = [3,4,0,1,2,5,13,14,6,7,8,9];
    for (let i = 0; i < map.length; i++)
      updateButton(pad, i, fromNativeOrder(b,map[i]));

    const hat = Number.isInteger(snapshot.hat) ? snapshot.hat : 0;
    const up = hat === 1 || hat === 2 || hat === 8;
    const right = hat === 2 || hat === 3 || hat === 4;
    const down = hat === 4 || hat === 5 || hat === 6;
    const left = hat === 6 || hat === 7 || hat === 8;
    updateButton(pad, 12, up);
    updateButton(pad, 13, down);
    updateButton(pad, 14, left);
    updateButton(pad, 15, right);
    updateButton(pad, 16, fromNativeOrder(b,10));
    updateButton(pad, 17, fromNativeOrder(b,11));
    updateButton(pad, 18, fromNativeOrder(b,12));
    updateButton(pad, 19, fromNativeOrder(b,15));
    pad.axes[0] = clamp(snapshot.axes?.[0]);
    pad.axes[1] = clamp(snapshot.axes?.[1]);
    pad.axes[2] = 0;
    pad.axes[3] = 0;
    pad.timestamp = performance.now();
    pad.connected = true;
  }

  function notify(type, pad) {
    try {
      let event;
      // The constructor of GamepadEvent usually refuses JS-made Gamepad
      // objects. An Event with the standard .gamepad property is a fallback.
      try {
        event = new GamepadEvent(type, {gamepad:pad});
      } catch {
        event = new Event(type);
        Object.defineProperty(event, "gamepad", {value:pad, enumerable:true});
      }
      window.dispatchEvent(event);
    } catch {
      // An incompatible page cannot break the extension or the game.
    }
  }

  function copyNative() {
    const fn = originals.getGamepads || originals.webkitGetGamepads;
    if (!fn) return [];
    const value = fn.call(navigator);
    return value ? Array.from(value) : [];
  }

  function mergedGetGamepads() {
    if (!enabled) {
      if (originals.getGamepads) return originals.getGamepads.call(navigator);
      if (originals.webkitGetGamepads) return originals.webkitGetGamepads.call(navigator);
      return [];
    }
    // If Permissions-Policy blocks gamepad in an embedded frame, do not
    // override that website policy.
    if (document.permissionsPolicy &&
        typeof document.permissionsPolicy.allowsFeature === "function" &&
        !document.permissionsPolicy.allowsFeature("gamepad"))
      return copyNative();

    const result = copyNative();
    const placed = new Set();
    for (let i = 0; i < result.length; i++) {
      const native = result[i];
      const match = native?.id?.match(/FUTUREO[_\s-]*VJOY\s*([1-8])/i);
      if (!match) continue;
      const slot = Number(match[1]);
      const facade = virtual.get(slot);
      if (!facade) continue;
      facade.index = i;
      result[i] = facade;
      placed.add(slot);
    }
    for (const [slot, facade] of [...virtual.entries()].sort((a,b)=>a[0]-b[0])) {
      if (placed.has(slot)) continue;
      let index = result.indexOf(null);
      if (index < 0) index = result.length;
      facade.index = index;
      result[index] = facade;
    }
    return result;
  }

  function override(prototype, key) {
    if (!prototype) return;
    try {
      Object.defineProperty(prototype, key, {
        configurable:true,
        writable:true,
        value:mergedGetGamepads
      });
    } catch {
      try {
        Object.defineProperty(navigator, key, {
          configurable:true, writable:true, value:mergedGetGamepads
        });
      } catch { /* host policy may reject overriding; diagnostics will show */ }
    }
  }

  override(Navigator.prototype, "getGamepads");
  if ("webkitGetGamepads" in Navigator.prototype || "webkitGetGamepads" in navigator)
    override(Navigator.prototype,"webkitGetGamepads");

  function acceptSnapshot(pads) {
    const newSlots = new Set();
    for (const snapshot of pads.slice(0,8)) {
      if (!Number.isInteger(snapshot.slot) || snapshot.slot < 1 || snapshot.slot > 8)
        continue;
      const slot = snapshot.slot;
      newSlots.add(slot);
      let pad = virtual.get(slot);
      const firstTime = !pad;
      if (!pad) {
        pad = createPad(slot);
        virtual.set(slot,pad);
      }
      updatePad(pad,snapshot);
      if (firstTime) {
        // The page may register event listeners while parsing its scripts;
        // defer early notifications until DOM content is ready.
        const emit = () => {
          if (pad.connected) notify("gamepadconnected",pad);
        };
        if (document.readyState === "loading")
          document.addEventListener("DOMContentLoaded",emit,{once:true});
        else emit();
      }
    }
    for (const [slot,pad] of virtual) {
      if (newSlots.has(slot)) continue;
      pad.connected = false;
      virtual.delete(slot);
      notify("gamepaddisconnected",pad);
    }
  }

  window.addEventListener("message", (event) => {
    if (event.source !== window || event.data?.channel !== CHANNEL) return;
    const frame = event.data;
    if (!Array.isArray(frame.pads)) return;
    enabled = true;
    lastUpdate = Date.now();
    acceptSnapshot(frame.pads);
  });

  // An unexpectedly closed EXE releases its virtual Gamepad objects.
  window.setInterval(() => {
    if (!enabled) return;
    if (Date.now() - lastUpdate > 1800) acceptSnapshot([]);
  }, 500);
})();
