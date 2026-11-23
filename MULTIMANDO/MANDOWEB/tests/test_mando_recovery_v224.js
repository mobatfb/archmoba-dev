/* Pruebas sin navegador ni clave: mando fallback y servidor WebSocket */
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const path=require("node:path");
const base=path.join(__dirname,"..");
const source=fs.readFileSync(path.join(base,"assets/mando-rescate.js"),"utf8");
const loader=fs.readFileSync(path.join(base,"assets/mando-recovery.js"),"utf8");

class Element {
  constructor(id) {
    this.id=id;
    this.textContent="";
    this.value="";
    this.hidden=false;
    this.disabled=false;
    this.dataset={};
    this.checked=false;
    this.open=false;
    this.handlers={};
    this.style={};
    this.classes=new Set();
    this.classList={
      add:x=>this.classes.add(x),
      remove:x=>this.classes.delete(x),
      contains:x=>this.classes.has(x),
      toggle:(x,val)=>{
        const yes=val===undefined?!this.classes.has(x):val;
        if(yes)this.classes.add(x);else this.classes.delete(x);
        return yes;
      }
    };
  }
  addEventListener(event,fn){this.handlers[event]=fn;}
  dispatch(event,args={}){if(this.handlers[event])this.handlers[event](args);}
  setAttribute(){}
  setPointerCapture(){}
  getBoundingClientRect(){return {left:0,top:0,width:200,height:200};}
  showModal(){this.open=true;}
  close(){this.open=false;}
  appendChild(){}
  closest(){return null;}
}
class Storage {
  constructor(){this.items={};}
  getItem(k){return this.items[k]||null;}
  setItem(k,v){this.items[k]=v;}
  removeItem(k){delete this.items[k];}
}
class Sock {
  static OPEN=1;
  constructor(url){
    this.url=url;this.readyState=1;this.sent=[];
    Sock.sockets.push(this);
  }
  send(v){this.sent.push(v);}
  close(){
    this.readyState=3;
    if(this.onclose)this.onclose({});
  }
  emit(data){this.onmessage({data});}
}
Sock.sockets=[];
function mock() {
 const ids=[
 "nickname","autoRoom","directUrl","manualRoom","connectBtn","disconnectBtn",
 "connectionPill","connectionText","connectionError","mySlot","myStatus",
 "timeLeft","clockStatus","queueCount","myQueuePosition","feedback","roomId",
 "connectionSource","turnDialog","turnCountdown","slotIndicator","joystick",
 "joystickThumb","dpad","directionHint","modeHelp","queueDialog","queueKeepBtn",
 "queueYieldBtn","queueResponseLeft","keyDialog","openKeys","closeKeys",
 "saveKeys","resetKeys","keyGrid","keyMessage"
 ];
 const map=Object.fromEntries(ids.map(x=>[x,new Element(x)]));
 map.nickname.value="Bryan2022";map.autoRoom.checked=true;
 const button=new Element("actionA");button.dataset.action="button_a";
 const candidate=new Element("control_php");
 candidate.src="https://tiendavibechic.com/multimando/control.php?v=6.2.0";
 const inserted=[];
 const dom=new Element("dom"),win=new Element("window");
 const context={
  document:{
    getElementById:id=>map[id]||null,
    querySelectorAll:selector=>selector==="[data-action]"?[button]:[],
    querySelector:selector=>selector.includes("control.php")?candidate:null,
    createElement:id=>new Element(id),
    head:{appendChild:x=>inserted.push(x)},
    addEventListener:(event,fn)=>dom.addEventListener(event,fn),
    hidden:false
  },
  window:win,URL,location:{href:"https://tiendavibechic.com/multimando/"},
  localStorage:new Storage(),sessionStorage:new Storage(),
  Date,Math,JSON,Number,Set,Map,Array,Uint8Array,
  performance:{now:()=>Date.now()},
  AbortSignal:{timeout:()=>undefined},
  fetch:async()=>({ok:true,json:async()=>({url:"https://room.trycloudflare.com/"})}),
  WebSocket:Sock,
  setInterval:()=>1,clearInterval:()=>{},
  setTimeout:()=>1,clearTimeout:()=>{},
  console
 };
 return {context,map,button,dom,win,candidate,inserted};
}
async function main() {
 Sock.sockets=[];
 const t=mock();
 vm.runInNewContext(source,t.context,{filename:"mando-rescate.js"});
 assert.equal(t.context.window.__MULTIMANDO_RESCUE_ACTIVE__,true);
 t.map.connectBtn.dispatch("click");
 await new Promise(resolve=>setImmediate(resolve));
 assert.equal(Sock.sockets.length,1,"CONECTAR debe abrir WebSocket al tunel");
 const ws=Sock.sockets[0];
 assert.equal(ws.url,"wss://room.trycloudflare.com/");
 ws.onopen();
 const hello=JSON.parse(ws.sent[0]);
 assert.equal(hello.type,"hello");
 assert.equal(hello.name,"Bryan2022");
 assert.equal(hello.heartbeat,true);
 ws.emit(JSON.stringify({type:"welcome",you:1,room_id:"roomXYZ",
   resume_token:"1234567890abcdef1234567890abcdef",turn_duration:600,version:"2.2.1"}));
 assert.equal(t.map.connectionText.textContent,"CONECTADO");
 ws.emit(JSON.stringify([1,0,0,600,0,0]));
 assert.equal(t.map.mySlot.textContent,"P1");
 t.button.dispatch("pointerdown",{pointerId:8,preventDefault(){}});
 assert.ok(ws.sent.includes("a1"),"El boton A activa comando del anfitrion");
 t.button.dispatch("pointerup",{pointerId:8});
 assert.ok(ws.sent.includes("a0"),"El boton A libera comando del anfitrion");
 const joy=t.map.joystick;
 joy.dispatch("pointerdown",{pointerId:2,clientX:180,clientY:100,preventDefault(){}});
 assert.ok(ws.sent.some(x=>x instanceof Uint8Array&&x[0]===0xa1),
   "El joystick envia paquete binario A1");
 joy.dispatch("pointerup",{pointerId:2});
 t.map.disconnectBtn.dispatch("click");
 assert.ok(ws.sent.includes("bye"),"Salir libera el mando");

 // 404 -> fallback. 200 JS -> el modulo original conserva prioridad.
 for(const mode of ["404","ok","html"]) {
  const env=mock();
  env.context.fetch=async()=>mode==="404"?{ok:false,status:404}:
    mode==="html"?{ok:true,headers:{get:()=> "text/html"},text:async()=>"<html>404</html>"}:
    {ok:true,headers:{get:()=> "text/javascript"},text:async()=>"(function(){})();"};
  vm.runInNewContext(loader,env.context,{filename:"mando-recovery.js"});
  await new Promise(resolve=>setImmediate(resolve));
  const count=env.inserted.filter(e=>String(e.src).includes("mando-rescate.js")).length;
  assert.equal(count,mode==="ok"?0:1,mode);
 }
 console.log("OK: mando CONECTAR, hello/welcome, A, joystick, SALIR; fallback 404/HTML; JS correcto no reemplazado");
}
main().catch(err=>{console.error(err);process.exitCode=1;});
