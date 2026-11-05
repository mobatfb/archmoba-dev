/* AMBOT | Controles del laboratorio y API del cerebro. */
'use strict';
(function () {
  const el = id => document.getElementById(id);
  const names = {N:'NORTE', E:'ESTE', S:'SUR', O:'OESTE'};
  const angle = {N:'0deg', E:'90deg', S:'180deg', O:'270deg'};
  let engine = null, ready = false, autoTimer = null, busy = false;
  let pending = Promise.resolve(), lastKey = 0;
  function log(who, txt, type) {
    if (!txt) return;
    const area = el('logs'), line = document.createElement('div'), b = document.createElement('b');
    line.className = 'line ' + (type || '');
    b.textContent = who + ' · ';
    line.appendChild(b); line.appendChild(document.createTextNode(txt)); area.appendChild(line);
    while (area.children.length > 48) area.removeChild(area.firstChild);
    area.scrollTop = area.scrollHeight;
  }
  async function request(url, body) {
    const opt = body === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)};
    const res = await fetch(url, opt);
    if (!res.ok) throw new Error('Respuesta HTTP ' + res.status);
    return res.json();
  }
  function status(data, snap) {
    if (!engine) return;
    const bot = data.robot || {};
    if (!ready) { engine.setMap(data.mapa); ready=true; snap=true; }
    engine.setRobot(bot, !!snap);
    const bat = Number(bot.bateria || 0);
    el('battery').textContent = bat.toFixed(1).replace('.0','');
    el('batteryBar').style.width = Math.max(0, Math.min(100, bat)) + '%';
    el('batteryBar').style.background = bat < 15 ? 'linear-gradient(90deg,#ca6071,#ffb574)' : 'linear-gradient(90deg,#1597d9,#53ebdc)';
    el('distance').textContent = bot.distancia_cm == null ? '—' : bot.distancia_cm;
    el('dir').textContent = names[bot.orientacion] || bot.orientacion;
    el('dirHud').textContent = names[bot.orientacion] || bot.orientacion;
    el('steps').textContent = bot.pasos || 0;
    el('posHud').textContent = 'X: ' + String(bot.x || 0).padStart(2,'0') + ' / Z: ' + String(bot.y || 0).padStart(2,'0');
    el('needle').style.transform = 'rotate(' + (angle[bot.orientacion] || '0deg') + ')';
    el('thought').textContent = data.decision && data.decision.razon || 'Sin información';
    if (autoTimer && bat < 1.5) toggleAuto(false);
  }
  function connected() {
    el('serverDot').classList.remove('off');
    el('serverText').textContent = 'CEREBRO CONECTADO';
    el('offline').style.display = 'none';
  }
  function failed(err) {
    el('serverDot').classList.add('off');
    el('serverText').textContent = 'DESCONECTADO';
    el('offline').style.display = 'block';
    log('ERROR', err.message || String(err), 'warn');
    toggleAuto(false);
  }
  function command(txt, record) {
    pending = pending.catch(()=>{}).then(async function () {
      busy=true;
      try {
        if (record !== false) log('TÚ', txt);
        const data = await request('/api/comando', {comando: txt});
        connected(); status(data);
        if (data.respuesta) log('AMBOT', data.respuesta, data.respuesta.startsWith('SEGURIDAD') ? 'warn' : 'success');
        return data;
      } catch (e) { failed(e); throw e; }
      finally { busy=false; }
    });
    return pending.catch(()=>null);
  }
  function toggleAuto(on) {
    if (!on) {
      if (autoTimer) clearInterval(autoTimer);
      autoTimer = null;
      el('auto').textContent = '▶ AUTO';
      el('auto').classList.remove('active'); return;
    }
    if (autoTimer || !ready) return;
    el('auto').textContent = 'Ⅱ PAUSAR';
    el('auto').classList.add('active');
    log('SISTEMA', 'Exploración autónoma activada.', 'success');
    command('explora');
    autoTimer = setInterval(()=>{ if(!busy) command('explora', false); }, 850);
  }
  function reset() {
    toggleAuto(false);
    pending = pending.catch(()=>{}).then(async function() {
      try {
        const result = await request('/api/reiniciar', {});
        connected(); status(result, true);
        log('SISTEMA', result.respuesta, 'success');
      } catch(e) { failed(e); }
    });
  }
  function setup() {
    try { engine = new AMBOT3D.Engine(el('ambotCanvas')); }
    catch(e) { failed(e); return; }
    const buttons = {forward:'avanza',left:'gira izquierda',right:'gira derecha',back:'retrocede',explore:'explora',think:'explora'};
    Object.keys(buttons).forEach(id=>el(id).addEventListener('click', ()=>command(buttons[id])));
    el('auto').addEventListener('click', ()=>toggleAuto(!autoTimer));
    el('stop').addEventListener('click', ()=>{toggleAuto(false);log('SISTEMA','Movimiento automático detenido.');});
    el('reset').addEventListener('click',reset);
    el('commandForm').addEventListener('submit', e => {
      e.preventDefault();
      const input=el('command'), txt=input.value.trim();
      if (txt) { input.value=''; command(txt); }
    });
    document.addEventListener('keydown',e=>{
      const tag=(document.activeElement && document.activeElement.tagName || '').toUpperCase();
      if(tag==='INPUT'||tag==='TEXTAREA'||e.ctrlKey||e.metaKey||e.altKey)return;
      const key=e.key.toLowerCase();
      const map={'w':'avanza','arrowup':'avanza','s':'retrocede','arrowdown':'retrocede','a':'gira izquierda','arrowleft':'gira izquierda','d':'gira derecha','arrowright':'gira derecha','e':'explora'};
      if(key===' '){e.preventDefault();if(!e.repeat)toggleAuto(!autoTimer);return;}
      if(key==='r'){e.preventDefault();if(!e.repeat)engine.resetCamera();return;}
      if(map[key]){
        e.preventDefault();const now=performance.now();
        if(now-lastKey<155)return; lastKey=now; command(map[key],false);
      }
    });
    request('/api/estado').then(data=>{
      status(data,true);connected();
      log('SISTEMA','Stickman en línea. Usa W / A / S / D, E o EXPLORAR.','success');
    }).catch(failed);
  }
  document.addEventListener('DOMContentLoaded',setup);
})();
