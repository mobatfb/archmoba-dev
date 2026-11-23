/* MULTIMANDO FUTUREO - Control web de rescate 2.2.4
 * Se habilita solo si el PHP cifrado no responde HTTP 200 / JS.
 * Usa el MISMO protocolo de mandos. No modifica /stream.
 */
(()=>{
"use strict";
if (window.__MULTIMANDO_RESCUE_ACTIVE__) return;
window.__MULTIMANDO_RESCUE_ACTIVE__=true;
const el=id=>document.getElementById(id);
const u={
 nick:el("nickname"),auto:el("autoRoom"),url:el("directUrl"),manual:el("manualRoom"),
 connect:el("connectBtn"),exit:el("disconnectBtn"),pill:el("connectionPill"),
 conn:el("connectionText"),error:el("connectionError"),slot:el("mySlot"),
 status:el("myStatus"),time:el("timeLeft"),clock:el("clockStatus"),
 queue:el("queueCount"),pos:el("myQueuePosition"),feedback:el("feedback"),
 room:el("roomId"),source:el("connectionSource"),turn:el("turnDialog"),
 number:el("turnCountdown"),indicator:el("slotIndicator"),
 stick:el("joystick"),thumb:el("joystickThumb"),dpad:el("dpad"),
 hint:el("directionHint"),help:el("modeHelp"),queueDialog:el("queueDialog"),
 keep:el("queueKeepBtn"),yield:el("queueYieldBtn"),queueResponse:el("queueResponseLeft"),
 keys:el("keyDialog"),keysOpen:el("openKeys"),keysClose:el("closeKeys"),
 keysSave:el("saveKeys"),keysReset:el("resetKeys"),keyGrid:el("keyGrid"),
 keyMessage:el("keyMessage")
};
if(!u.connect||!u.nick)return;
const codes={ar:"u",ab:"d",iz:"i",de:"e",button_x:"x",button_y:"y",button_lb:"l",
 button_a:"a",button_b:"b",button_rb:"r",select:"s",start:"t"};
const keyDefaults={KeyW:"ar",KeyS:"ab",KeyA:"iz",KeyD:"de",
 ArrowUp:"ar",ArrowDown:"ab",ArrowLeft:"iz",ArrowRight:"de",
 KeyU:"button_x",KeyI:"button_y",KeyO:"button_lb",KeyJ:"button_a",
 KeyK:"button_b",KeyL:"button_rb",Enter:"start",Backspace:"select"};
let keymap={...keyDefaults};
try{const x=JSON.parse(localStorage.getItem("mm_rescue_keys")||"null");
 if(x&&typeof x==="object")for(const [key,val] of Object.entries(x))
   if(key.length<=30&&codes[val])keymap[key]=val;
}catch{}
let ws=null,trying=false,joined=false,manualLeave=true;
let player="",resumeToken="",roomId="",retryUntil=0,retryTimer=null;
let heartTimer=null,lastHeartbeat=0,attempts=0;
let assigned=0,waiting=0,queueTotal=0,seconds=600,countdown=0,activation=0,stateAt=0;
let mode="analog",held=new Set(),keyHeld=new Set(),digital=new Set(),stickPointer=null;
let previousAxes=[0,0],axisAt=0,queueSince=0,queueAsk=0,keyCapture=null;
const say=(node,v)=>{if(node)node.textContent=v;};
function explain(v){if(u.error){u.error.hidden=false;u.error.textContent=v;}say(u.feedback,v);}
function clearError(){if(u.error){u.error.hidden=true;u.error.textContent="";}}
function badge(v,t){
 say(u.conn,t);
 u.pill?.classList.toggle("online",v==="online");
 u.pill?.classList.toggle("pending",v==="pending");
 u.connect.disabled=v==="online"||v==="pending";
 if(u.exit)u.exit.disabled=v==="offline";
}
function wsUrl(raw){
 try{
  const url=new URL(raw,location.href);
  if(url.protocol==="https:")url.protocol="wss:";
  if(url.protocol!=="wss:"||url.username||url.password||url.port||
   !/^[a-z0-9-]+\.trycloudflare\.com$/i.test(url.hostname))return null;
  url.pathname="/";url.search="";url.hash="";
  return url.toString();
 }catch{return null;}
}
async function getUrl(){
 if(u.auto&&!u.auto.checked)return wsUrl(u.url?.value.trim()||"");
 const res=await fetch("sala.php",{cache:"no-store",credentials:"same-origin",
  signal:AbortSignal.timeout(9000)});
 if(!res.ok)throw Error("sala.php: HTTP "+res.status);
 const data=await res.json();
 return wsUrl(data.url||"");
}
function getSavedToken(){
 try{const obj=JSON.parse(sessionStorage.getItem("mm_rescue_session")||"null");
  return obj?.name===player&&typeof obj.token==="string"?obj.token:"";
 }catch{return "";}
}
function saveToken(){
 try{sessionStorage.setItem("mm_rescue_session",JSON.stringify({name:player,token:resumeToken}));}catch{}
}
function removeToken(){
 resumeToken="";try{sessionStorage.removeItem("mm_rescue_session");}catch{}
}
function send(v){
 if(!ws||ws.readyState!==WebSocket.OPEN||!joined)return false;
 try{ws.send(v);return true;}catch{return false;}
}
function allowed(){return joined&&assigned>0&&countdown<=0;}
function press(action){
 if(!codes[action]||!allowed()||held.has(action))return;
 held.add(action);send(codes[action]+"1");
}
function lift(action){
 if(!codes[action]||!held.has(action))return;
 held.delete(action);send(codes[action]+"0");
}
function axes(x,y,force=false){
 if(!force&&mode!=="analog")return;
 const t=performance.now();
 x=Math.min(127,Math.max(-127,Math.round(x)));y=Math.min(127,Math.max(-127,Math.round(y)));
 if(!force&&t-axisAt<31&&(x!==0||y!==0))return;
 if(!force&&x===previousAxes[0]&&y===previousAxes[1])return;
 axisAt=t;previousAxes=[x,y];
 if(allowed()||(x===0&&y===0))send(new Uint8Array([0xa1,x&255,y&255]));
}
function directional(x,y){
 const next=new Set();
 if(x>0.35)next.add("de");else if(x< -0.35)next.add("iz");
 if(y>0.35)next.add("ar");else if(y< -0.35)next.add("ab");
 for(const key of digital)if(!next.has(key))lift(key);
 for(const key of next)if(!digital.has(key))press(key);
 digital=next;
}
function release(){
 for(const action of [...held])lift(action);
 keyHeld.clear();digital.clear();axes(0,0,true);
 if(u.thumb)u.thumb.style.transform="";
}
function setMode(m){
 if(!["analog","dpad","mixed"].includes(m))return;
 release();mode=m;send(m==="analog"?"m1":"m0");
 document.querySelectorAll("[data-direction-mode]").forEach(b=>{
  const active=b.dataset.directionMode===m;
  b.classList.toggle("selected",active);b.setAttribute("aria-pressed",String(active));
 });
 if(u.stick)u.stick.hidden=m==="dpad";
 if(u.dpad)u.dpad.hidden=m!=="dpad";
 say(u.hint,m==="analog"?"ANALÓGICO · MOVIMIENTO PROPORCIONAL":
 m==="mixed"?"MIXTO · PALANCA CON 8 DIRECCIONES":"CRUCETA DIGITAL");
}
function showDialog(dialog){if(dialog&&!dialog.open)try{dialog.showModal()}catch{}}
function hideDialog(dialog){if(dialog?.open)try{dialog.close()}catch{}}
function pad(v){return String(v).padStart(2,"0");}
function drawState(){
 say(u.slot,assigned?"P"+assigned:"—");
 say(u.status,!joined?"Sin asignar":assigned?"Asignado P"+assigned:"En espera");
 say(u.indicator,assigned?"P"+assigned:"SIN TURNO");
 u.indicator?.classList.toggle("active",assigned>0);
 say(u.queue,joined?String(queueTotal):"—");
 say(u.pos,!joined?"Sin conexión":assigned?"Control asignado":
  waiting?"Posición "+waiting:"Sin turno");
 const elapsed=stateAt?Math.max(0,Math.floor((Date.now()-stateAt)/1000)):0;
 const counter=assigned&&countdown===0&&activation===0&&queueTotal>0?
  Math.max(0,seconds-elapsed):seconds;
 say(u.time,joined&&assigned?pad(Math.floor(counter/60))+":"+pad(counter%60):"--:--");
 say(u.clock,countdown>0?"Comienza en "+Math.max(1,countdown-elapsed)+" s":
  activation>0?"Pulsa un botón para activar":!queueTotal?"Sin cola: reloj pausado":"Turno del anfitrión");
 if(joined&&assigned&&countdown>0){
  say(u.number,String(Math.max(1,countdown-elapsed)));showDialog(u.turn);
 }else hideDialog(u.turn);
 if(joined&&waiting>0&&!assigned){
  if(!queueSince)queueSince=Date.now();
  if(Date.now()-queueSince>=300000&&!queueAsk){
   queueAsk=Date.now();showDialog(u.queueDialog);
  }
  if(queueAsk){
   const r=Math.max(0,60-Math.floor((Date.now()-queueAsk)/1000));
   say(u.queueResponse,r);
   if(r===0){send("q0");queueAsk=0;hideDialog(u.queueDialog);}
  }
 }else{queueSince=queueAsk=0;hideDialog(u.queueDialog);}
}
function newState(data){
 assigned=Number(data[0]||0);waiting=Number(data[1]||0);
 queueTotal=Number(data[2]||0);seconds=Number(data[3]||0);
 activation=Number(data[4]||0);countdown=Number(data[5]||0);
 stateAt=Date.now();drawState();
}
function reset(){
 joined=false;assigned=waiting=queueTotal=0;seconds=600;activation=countdown=0;
 stateAt=Date.now();queueSince=queueAsk=0;
 hideDialog(u.turn);hideDialog(u.queueDialog);drawState();
}
function heartbeat(){
 clearInterval(heartTimer);
 heartTimer=setInterval(()=>{
  if(!joined||!ws||ws.readyState!==WebSocket.OPEN)return;
  if(Date.now()-lastHeartbeat>8300){try{ws.close(4000,"heartbeat timeout")}catch{};return;}
  send("h");
 },2000);
}
async function connect(resume=false){
 if(trying||ws||manualLeave)return;
 trying=true;badge("pending",resume?"RECONECTANDO":"CONECTANDO");clearError();
 let address;
 try{address=await getUrl();if(!address)throw Error("La sala no tiene enlace Cloudflare válido.");}
 catch(e){
  trying=false;
  if(resume){retry();return;}
  manualLeave=true;badge("offline","SIN CONEXIÓN");explain(e.message);return;
 }
 if(manualLeave){trying=false;return;}
 let sock;
 try{sock=new WebSocket(address);}catch(e){
  trying=false;manualLeave=true;badge("offline","SIN CONEXIÓN");
  explain("No se pudo abrir WebSocket: "+e.message);return;
 }
 ws=sock;trying=false;
 sock.onopen=()=>{
  if(ws!==sock)return;
  const hello={type:"hello",name:player,heartbeat:true};
  const token=resume?(resumeToken||getSavedToken()):getSavedToken();
  if(token)hello.resume_token=token;
  try{sock.send(JSON.stringify(hello));}catch{}
 };
 sock.onmessage=ev=>{
  if(ws!==sock)return;
  if(ev.data==="h"){lastHeartbeat=Date.now();return;}
  if(typeof ev.data!=="string")return;
  let data;
  try{data=JSON.parse(ev.data)}catch{return;}
  if(Array.isArray(data)&&data.length===6){newState(data);return;}
  if(!data||typeof data!=="object")return;
  if(data.type==="welcome"){
   joined=true;lastHeartbeat=Date.now();resumeToken=String(data.resume_token||"");
   saveToken();roomId=String(data.room_id||"");
   say(u.room,"SALA "+roomId.slice(0,10));
   badge("online","CONECTADO");say(u.feedback,"Conectado al anfitrión. "+(data.resumed?"Sesión recuperada.":"Turno administrado por Python."));
   retryUntil=0;attempts=0;clearTimeout(retryTimer);
   send(mode==="analog"?"m1":"m0");heartbeat();return;
  }
  if(data.type==="error"){
   manualLeave=true;explain(String(data.message||"Conexión rechazada por anfitrión"));return;
  }
  if(data.type==="queue_left"){manualLeave=true;explain("Saliste de la cola.");try{sock.close()}catch{}}
  if(data.type==="queue_kept")say(u.feedback,"Tu posición en cola se mantiene.");
  if(data.type==="queue_cannot_yield")explain(data.message||"No es posible ceder turno.");
  if(data.type==="controls_reset"){release();say(u.feedback,"Controles neutralizados por seguridad.");}
 };
 sock.onerror=()=>{if(ws===sock)say(u.feedback,"WebSocket interrumpido, verificando conexión...");};
 sock.onclose=()=>{
  if(ws!==sock)return;
  ws=null;clearInterval(heartTimer);heartTimer=null;
  const wasJoined=joined;release();reset();badge("offline","SIN CONEXIÓN");
  if(manualLeave)return;
  if(wasJoined){
   if(!retryUntil)retryUntil=Date.now()+30000;
   retry();
  }else{
   manualLeave=true;explain("El anfitrión cerró la conexión antes de enviar welcome. Comprueba el enlace y los puestos REMOTO.");
  }
 };
}
function retry(){
 if(manualLeave)return;
 if(retryUntil&&Date.now()>retryUntil){
  manualLeave=true;badge("offline","SIN CONEXIÓN");explain("Sin conexión. Pulsa CONECTAR otra vez.");return;
 }
 clearTimeout(retryTimer);attempts++;
 retryTimer=setTimeout(()=>connect(true),Math.min(3500,1200+attempts*350));
}
u.connect.addEventListener("click",()=>{
 if(trying||ws)return;
 const name=u.nick.value.trim().replace(/\s+/g," ");
 if(!name||name.length>10){explain("Nombre de jugador: entre 1 y 10 caracteres.");return;}
 player=name;manualLeave=false;retryUntil=0;connect();
});
u.exit?.addEventListener("click",()=>{
 manualLeave=true;clearTimeout(retryTimer);clearInterval(heartTimer);
 release();
 if(ws){
  const prev=ws;ws=null;
  try{if(prev.readyState===WebSocket.OPEN)prev.send("bye");prev.close(1000,"Salir")}catch{}
 }
 removeToken();reset();badge("offline","SIN CONEXIÓN");say(u.feedback,"Mando desconectado.");
});
u.auto?.addEventListener("change",()=>{
 if(u.manual)u.manual.hidden=u.auto.checked;
 say(u.source,u.auto.checked?"API MULTIMANDO":"URL MANUAL");
});
document.querySelectorAll("[data-direction-mode]").forEach(b=>b.addEventListener("click",()=>setMode(b.dataset.directionMode)));
document.querySelectorAll("[data-action]").forEach(b=>{
 const action=b.dataset.action, pointers=new Set();
 b.addEventListener("pointerdown",e=>{
  if(!allowed())return;
  e.preventDefault();pointers.add(e.pointerId);try{b.setPointerCapture(e.pointerId)}catch{}
  b.classList.add("engaged");press(action);
 });
 const end=e=>{
  if(!pointers.has(e.pointerId))return;
  pointers.delete(e.pointerId);
  if(!pointers.size){b.classList.remove("engaged");lift(action);}
 };
 ["pointerup","pointercancel","lostpointercapture"].forEach(name=>b.addEventListener(name,end));
 b.addEventListener("contextmenu",e=>e.preventDefault());
});
document.querySelectorAll("[data-pad-dir]").forEach(b=>{
 const dir=b.dataset.padDir;
 b.addEventListener("pointerdown",e=>{
  if(mode!=="dpad"||!allowed())return;
  e.preventDefault();try{b.setPointerCapture(e.pointerId)}catch{}
  b.classList.add("engaged");press(dir);
 });
 const end=()=>{b.classList.remove("engaged");lift(dir)};
 ["pointerup","pointercancel","lostpointercapture"].forEach(k=>b.addEventListener(k,end));
});
function moveStick(e){
 const rect=u.stick.getBoundingClientRect();
 const radius=Math.max(1,Math.min(rect.width,rect.height)/2);
 let x=(e.clientX-rect.left-rect.width/2)/radius;
 let y=-(e.clientY-rect.top-rect.height/2)/radius;
 const length=Math.hypot(x,y);
 if(length>1){x/=length;y/=length;}
 if(length<0.14){x=0;y=0;}
 if(u.thumb)u.thumb.style.transform="translate("+(x*radius*.26)+"px,"+(-y*radius*.26)+"px)";
 if(mode==="analog")axes(x*127,y*127);
 else directional(x,y);
}
if(u.stick){
 u.stick.addEventListener("pointerdown",e=>{
  if(!allowed()||mode==="dpad"||stickPointer!==null)return;
  e.preventDefault();stickPointer=e.pointerId;
  try{u.stick.setPointerCapture(e.pointerId)}catch{}
  u.stick.classList.add("engaged");moveStick(e);
 });
 u.stick.addEventListener("pointermove",e=>{
  if(e.pointerId===stickPointer)moveStick(e);
 });
 const end=e=>{
  if(e.pointerId!==stickPointer)return;
  stickPointer=null;u.stick.classList.remove("engaged");
  if(u.thumb)u.thumb.style.transform="";
  axes(0,0,true);directional(0,0);
 };
 ["pointerup","pointercancel","lostpointercapture"].forEach(k=>u.stick.addEventListener(k,end));
}
document.addEventListener("keydown",e=>{
 if(keyCapture){
  e.preventDefault();keymap[e.code]=keyCapture;keyCapture=null;renderKeys();return;
 }
 if(e.repeat||e.target?.closest?.("input,textarea,select,[contenteditable]"))return;
 const action=keymap[e.code];if(!action||!allowed())return;
 e.preventDefault();keyHeld.add(e.code);press(action);
});
document.addEventListener("keyup",e=>{
 if(!keyHeld.has(e.code))return;
 keyHeld.delete(e.code);const action=keymap[e.code];
 if(action){e.preventDefault();lift(action);}
});
window.addEventListener("blur",release);
document.addEventListener("visibilitychange",()=>{if(document.hidden)release();});
function renderKeys(){
 if(!u.keyGrid)return;u.keyGrid.textContent="";
 for(const action of Object.keys(codes)){
  const key=Object.entries(keymap).find(row=>row[1]===action)?.[0]||"Sin asignar";
  const b=document.createElement("button");b.type="button";b.textContent=action+": "+key;
  b.addEventListener("click",()=>{keyCapture=action;say(u.keyMessage,"Pulsa la tecla para "+action)});
  u.keyGrid.appendChild(b);
 }
}
u.keysOpen?.addEventListener("click",()=>{renderKeys();showDialog(u.keys);});
u.keysClose?.addEventListener("click",()=>hideDialog(u.keys));
u.keysSave?.addEventListener("click",()=>{
 try{localStorage.setItem("mm_rescue_keys",JSON.stringify(keymap))}catch{}
 hideDialog(u.keys);
});
u.keysReset?.addEventListener("click",()=>{keymap={...keyDefaults};renderKeys();});
u.keep?.addEventListener("click",()=>{
 send("q1");queueSince=Date.now();queueAsk=0;hideDialog(u.queueDialog);
});
u.yield?.addEventListener("click",()=>{send("q0");queueAsk=0;hideDialog(u.queueDialog)});
setMode("analog");
badge("offline","SIN CONEXIÓN");
say(u.feedback,"Mando de respaldo activo. Escribe tu nombre y pulsa CONECTAR.");
if(u.manual)u.manual.hidden=u.auto.checked;
setInterval(drawState,450);
})();
