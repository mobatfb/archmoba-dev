"use strict";
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const assert = require("node:assert/strict");

const folder = path.join(__dirname, "..", "browser_extension_v110");
const read = (name) => fs.readFileSync(path.join(folder,name),"utf8");
const manifest = JSON.parse(read("manifest.json"));

assert.equal(manifest.manifest_version,3);
assert.equal(manifest.version,"1.1.0");
assert.equal(manifest.host_permissions[0],"http://127.0.0.1/*");
assert.equal(manifest.permissions?.length || 0,0,"No account, tabs or storage permissions");
assert.equal(manifest.content_scripts[0].world,"MAIN");
assert.equal(manifest.content_scripts[0].run_at,"document_start");
assert.equal(manifest.content_scripts[1].world,"ISOLATED");

for (const name of ["background.js","content.js","popup.js"]) {
  const code = read(name);
  assert.equal(/bridgeToken|allowedSites|FUTUREO_ENABLED|CLAVE WEB/.test(code),false,
    "No pairing or per-site toggles in " + name);
}

// Test the gamepad facade exactly as a game page would see it.
const listeners = new Map();
const events = [];
function Navigator() {}
Navigator.prototype.getGamepads = function () { return [null]; };
function Gamepad() {}
const navigator = new Navigator();
class Event { constructor(type) { this.type=type; } }
const windowMain = {
  addEventListener:(name,listener)=>listeners.set(name,listener),
  setInterval:()=>1,
  dispatchEvent:(e)=>events.push(e)
};
const main = vm.createContext({
  window:windowMain,navigator,Navigator,Gamepad,Event,
  document:{readyState:"complete",permissionsPolicy:{allowsFeature:()=>true}},
  performance:{now:()=>150.5},console,Date,Math,Map,Set,Object,Array,Number
});
vm.runInContext(read("page-shim.js"),main,{filename:"page-shim.js"});
assert.equal(navigator.getGamepads().filter(Boolean).length,0);
const send= listeners.get("message");
const buttons=Array(16).fill(0);
buttons[3]=1; // A
buttons[4]=1; // B
send({source:windowMain,data:{channel:"FUTUREO_BRIDGE_SNAPSHOT_V1",pads:[
  {slot:1,name:"FUTUREO_VJOY1",buttons,axes:[.8,-.5],hat:2},
  {slot:2,name:"FUTUREO_VJOY2",buttons:Array(16).fill(0),axes:[0,0],hat:0}
]}});
let pads=Array.from(navigator.getGamepads()).filter(Boolean);
assert.equal(pads.length,2);
assert.equal(pads[0].mapping,"standard");
assert.equal(pads[0].buttons.length,20);
assert.equal(pads[0].buttons[0].pressed,true);
assert.equal(pads[0].buttons[1].pressed,true);
assert.equal(pads[0].buttons[12].pressed,true);
assert.equal(pads[0].buttons[15].pressed,true);
assert.equal(pads[0].axes[0],.8);
assert.equal(pads[0].axes[1],-.5);
assert.equal(events.filter(e=>e.type==="gamepadconnected").length,2);
send({source:windowMain,data:{channel:"FUTUREO_BRIDGE_SNAPSHOT_V1",pads:[]}});
assert.equal(Array.from(navigator.getGamepads()).filter(Boolean).length,0);

// Test the isolated content script starts polling IMMEDIATELY without pairing.
let polls = 0;
const transferred=[];
vm.runInNewContext(read("content.js"),{
  chrome:{runtime:{
    sendMessage:(message,callback)=>{
      assert.equal(message.type,"FUTUREO_POLL");
      polls++;
      callback({ok:true,pads:[{slot:1,name:"FUTUREO_VJOY1",buttons,axes:[0,0],hat:0}]});
    },
    lastError:null
  }},
  window:{
    postMessage:(value)=>transferred.push(value),
    setInterval:()=>1
  },
  Date,Array,console
},{filename:"content.js"});
assert.equal(polls,1,"Page must connect without any user action");
assert.equal(transferred[0].pads[0].name,"FUTUREO_VJOY1");

// Test extension worker uses localhost without secret headers.
let handler;
const fetched=[];
const chrome={
  runtime:{onMessage:{addListener:(callback)=>{handler=callback;}}}
};
const background=vm.createContext({
  chrome,console,Date,Math,Array,Set,Number,Promise,
  AbortController,
  setTimeout,clearTimeout,
  fetch:async (url,options)=>{
    fetched.push({url,options});
    return {ok:true,status:200,json:async ()=>({
      timestamp:200,pads:[{slot:1,buttons,axes:[.2,-.2],hat:7}]
    })};
  }
});
vm.runInContext(read("background.js"),background,{filename:"background.js"});

function ask(type) {
  return new Promise((resolve,reject)=>{
    const value=handler({type}, {tab:{id:1}},resolve);
    if(!value) reject(new Error("Background not handling "+type));
    setTimeout(()=>reject(new Error("Timeout waiting worker")),2500);
  });
}
(async()=>{
  const result=await ask("FUTUREO_POLL");
  assert.equal(result.ok,true);
  assert.equal(result.pads[0].name,"FUTUREO_VJOY1");
  assert.equal(fetched[0].url,"http://127.0.0.1:38471/state");
  assert.equal(fetched[0].options.headers,undefined,"No key needed");
  const diag=await ask("FUTUREO_DIAGNOSTIC");
  assert.equal(diag.ok,true);
  console.log("OK: zero setup, MV3 localhost permission, automatic frame poll, standard mapping, D-pad and axes.");
})().catch((err)=>{console.error(err);process.exitCode=1;});
