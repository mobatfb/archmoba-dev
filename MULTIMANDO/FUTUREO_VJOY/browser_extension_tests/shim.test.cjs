"use strict";
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const assert = require("node:assert/strict");

const folder = path.join(__dirname, "..", "browser_extension_v100");
const manifest = JSON.parse(fs.readFileSync(path.join(folder, "manifest.json"), "utf8"));
assert.equal(manifest.manifest_version, 3);
assert.deepEqual(manifest.permissions.sort(), ["storage","tabs"]);
assert.equal(manifest.content_scripts[0].world, "MAIN");
assert.equal(manifest.content_scripts[0].run_at, "document_start");
assert.equal(manifest.content_scripts[1].world, "ISOLATED");

const listeners = new Map();
const dispatched = [];
function Navigator() {}
Navigator.prototype.getGamepads = function () { return [null]; };
function Gamepad() {}
const navigator = new Navigator();
class Event {
  constructor(type) { this.type = type; }
}
const win = {
  addEventListener: (name, cb) => listeners.set(name, cb),
  setInterval: () => 1,
  dispatchEvent: (e) => dispatched.push(e)
};
const ctx = vm.createContext({
  window: win, navigator, Navigator, Gamepad, Event,
  document: {readyState: "complete",
    permissionsPolicy: {allowsFeature: () => true}},
  performance: {now: () => 123.5},
  console, Date, Math, Map, Set, Object, Array, Number,
});
vm.runInContext(fs.readFileSync(path.join(folder, "page-shim.js"),"utf8"),ctx, {
  filename:"page-shim.js"
});
assert.equal(navigator.getGamepads().filter(Boolean).length, 0, "Disabled sites show native pads only");
const send = listeners.get("message");
assert.equal(typeof send, "function");

const original = Array(16).fill(0);
original[3] = 1; // A
original[4] = 1; // B
original[11] = 1; // TOUCH
send({source:win, data: {channel:"FUTUREO_BRIDGE_SNAPSHOT_V1",pads: [
  {slot:1,name:"FUTUREO_VJOY1",buttons:original,axes:[.5,-.6],hat:2},
  {slot:2,name:"FUTUREO_VJOY2",buttons:Array(16).fill(0),axes:[0,0],hat:0}
]}});
let items = Array.from(navigator.getGamepads()).filter(Boolean);
assert.equal(items.length,2);
assert.equal(items[0].id.includes("FUTUREO_VJOY1"),true);
assert.equal(items[0].mapping,"standard");
assert.equal(items[0].buttons.length,20);
assert.equal(items[0].axes.length,4);
assert.equal(items[0].buttons[0].pressed,true);
assert.equal(items[0].buttons[1].pressed,true);
assert.equal(items[0].buttons[17].pressed,true);
assert.equal(items[0].buttons[12].pressed,true, "Hat NE => North");
assert.equal(items[0].buttons[15].pressed,true, "Hat NE => East");
assert.equal(items[0].buttons[14].pressed,false,"Hat NE => not West");
assert.equal(items[0].axes[0],.5);
assert.equal(items[0].axes[1],-.6);
assert.equal(dispatched.filter(e=>e.type==="gamepadconnected").length,2);
send({source:win,data:{channel:"FUTUREO_BRIDGE_SNAPSHOT_V1",pads:[]}});
items = Array.from(navigator.getGamepads()).filter(Boolean);
assert.equal(items.length,0);
assert.equal(dispatched.filter(e=>e.type==="gamepaddisconnected").length,2);
console.log("OK: MV3 manifest, 8-pad layout, standard buttons, hat diagonals, axes, events.");
