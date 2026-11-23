/* MULTIMANDO loader de recuperacion v2.2.4.
 * El modulo cifrado ORIGINAL tiene prioridad.
 * Si control.php responde 404/503/HTML, inyecta respaldo sin secreto.
 */
(()=>{
"use strict";
const candidate=document.querySelector('script[src^="control.php"]');
if(!candidate)return;
let started=false;
function fallback(reason){
 if(started)return;
 started=true;
 const js=document.createElement("script");
 js.src="assets/mando-rescate.js?v=2.2.4";
 js.async=true;
 js.onerror=()=>{
  const feedback=document.getElementById("feedback");
  if(feedback)feedback.textContent="No se pudo cargar el mando de respaldo. Comprueba assets/mando-rescate.js.";
 };
 document.head.appendChild(js);
 const feedback=document.getElementById("feedback");
 if(feedback)feedback.textContent="Recuperando mando web por problema en control.php ("+reason+")...";
}
candidate.addEventListener("error",()=>fallback("script no disponible"));
async function checkModule(){
 try{
  const res=await fetch(candidate.src,{cache:"no-store",credentials:"same-origin",
    signal:AbortSignal.timeout(9500)});
  const type=(res.headers.get("content-type")||"").toLowerCase();
  if(!res.ok){fallback("HTTP "+res.status);return;}
  if(type.includes("text/html") || type.includes("application/xhtml")){
   fallback("el servidor responde HTML");return;
  }
  const script=await res.text();
  if(!script.trim() || /^\s*console\.error\s*\(/.test(script)){
   fallback("PHP no genero el mando");return;
  }
  // Codigo del mando disponible: NO instalar el respaldo.
 }catch(e){
  // Fallo de red de la comprobacion. No desactivar el mando original.
  // El evento error del script principal activa el respaldo si falla.
 }
}
checkModule();
})();
