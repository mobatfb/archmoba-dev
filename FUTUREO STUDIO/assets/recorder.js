/* FUTUREO STUDIO v0.1.25 - measured acoustic round-trip compensation */
(() => {
    const root = document.querySelector('.voice-recorder');
    if (!root) return;
    const $ = id => document.getElementById('voice-' + id);
    const canvas = $('canvas'), ctx = canvas.getContext('2d'), audio = $('audio');
    const record = $('record'), play = $('play'), stop = $('stop'), home = $('home'), clock = $('clock'), status = $('status'), saved = $('saved'), recovery = $('recovery'), download = $('download'), trackName = $('track-name');
    const importButton=$('import'), importInput=$('files');
    let importPreview=null, maxMp3Bytes=25*1024*1024;
    const trackRows = Array.from(document.querySelectorAll('[data-track-row]'));
    const endpoint = 'recordings.php?' + new URLSearchParams({project: root.dataset.project}).toString();
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    const supported = window.isSecureContext && navigator.mediaDevices?.getUserMedia && AudioCtx && window.AudioWorkletNode && window.crypto?.getRandomValues;
    const palette = {1:{accent:'#33d5ff',fill:'#10323e',live:'#123c47',wave:'#32d7e8',liveWave:'#ff6785',name:'Pista 1'},2:{accent:'#c39cff',fill:'#241936',live:'#302140',wave:'#c8a7ff',liveWave:'#ff93d2',name:'Pista 2'},3:{accent:'#ffd166',fill:'#3a2d14',live:'#46361a',wave:'#ffd166',liveWave:'#ffe4a8',name:'Pista 3'},4:{accent:'#76e39a',fill:'#143021',live:'#193b29',wave:'#76e39a',liveWave:'#b6f4c8',name:'Pista 4'}};
    let selectedTrack = 1, clips = [], take = null, phase = 'loading', maxBytes = 0, position = 0, extent = 30, playback = null, playToken = 0, localUrl = null;
    let drag = null, selectedClip = null, seekingPointer = null, tool = 'pointer', editPointer = null, cutPreview = null;
    const undoButton=$('undo'), redoButton=$('redo');
    let historyState={undo_count:0,redo_count:0,undo_id:null,redo_id:null};
    const toolButtons = Array.from(root.querySelectorAll('.daw-tool[data-tool]'));
    const toolHints = {pointer:'Puntero: selecciona clips o cambia el cursor.',hand:'Mano: arrastra un clip a otra posición o pista.',cut:'Cúter: pulsa dentro de un clip para dividirlo.',erase:'Borrar: pulsa un clip para quitarlo de la línea de tiempo.'};
    function setTool(next){if(!toolHints[next]||!['idle','playing'].includes(phase))return;if(drag)cancelDrag();tool=next;editPointer=null;cutPreview=null;msg(toolHints[tool]);update();}
    toolButtons.forEach(b=>b.addEventListener('click',()=>setTool(b.dataset.tool)));
    let playbackContext = null, playbackFrame = 0;
    const syncInfo=$('sync-info'),syncDetails=$('sync'),syncButton=$('calibrate'),syncCancel=$('calibrate-cancel'),syncSummary=syncDetails.querySelector('summary');
    const Sync=window.FutureoSync;
    let calibration=null;
    const micConstraints={audio:{channelCount:1,latency:{ideal:.01},echoCancellation:false,noiseSuppression:false,autoGainControl:false},video:false};
    const validLatency=n=>typeof n==='number'&&Number.isFinite(n)&&n>=0&&n<=.75;
    const outputDelay=context=>(validLatency(context.baseLatency)?context.baseLatency:0)+(validLatency(context.outputLatency)?context.outputLatency:0);
    function syncStatus(text,measured=false){syncInfo.textContent=text;syncSummary.textContent=measured?'SYNC ✓':'SYNC';syncDetails.dataset.measured=String(measured);}
    function compensation(t,p,accompaniment,measured){
        const reported=t.media.getAudioTracks()[0]?.getSettings?.().latency;
        // Acoustic measurement already includes the input and output hardware paths.
        // Add only the fixed delay of the actual mix graph, never hardware estimates again.
        if(accompaniment){
            if(!measured)throw Error('Primero calibra la latencia de tu dispositivo en SYNC.');
            const acousticFrames=Math.round(measured.seconds*t.rate),graphFrames=Math.round((p.graphLatency||0)*t.rate);
            const frames=acousticFrames+graphFrames;
            return {frames,ms:Math.round(frames/t.rate*1000),method:'acoustic',acousticFrames};
        }
        // Without accompaniment there is no outgoing reference; use input-only timing.
        const frames=Math.round((validLatency(reported)?reported:0)*t.rate);
        return {frames,ms:Math.round(frames/t.rate*1000),method:'input_estimate',inputKnown:validLatency(reported)};
    }
    async function calibrate(){
        if(!supported||!Sync||!['idle','playing'].includes(phase))return;
        if(phase==='playing')pause();
        const job={controller:new AbortController(),media:null};calibration=job;phase='calibrating';syncDetails.open=true;
        syncStatus('Preparando el micrófono…');msg('Calibración acústica: preparando la entrada y salida de audio.');update();
        try{
            if(!playbackContext||playbackContext.state==='closed')playbackContext=new AudioCtx({latencyHint:'interactive'});
            const context=playbackContext;await context.resume();
            if(context.state!=='running')throw Error('El navegador suspendió el audio. Pulsa Calibrar nuevamente.');
            if(job.controller.signal.aborted)throw Error('Calibración cancelada.');
            job.media=await navigator.mediaDevices.getUserMedia(micConstraints);
            if(job.controller.signal.aborted)throw Error('Calibración cancelada.');
            const route=await Sync.route(context,job.media);Sync.forget(route);
            const result=await Sync.measure(context,job.media,job.controller.signal,stage=>{syncStatus(stage);msg(stage);});
            if(job.controller.signal.aborted)throw Error('Calibración cancelada.');
            const after=await Sync.route(context,job.media);
            if(after.key!==route.key)throw Error('Cambió el dispositivo durante la prueba. Calibra nuevamente.');
            if(job.controller.signal.aborted)throw Error('Calibración cancelada.');
            const savedResult=Sync.save(route,result);
            const ms=(savedResult.seconds*1000).toFixed(1),summary=ms+' ms medidos · '+savedResult.matches+'/4 pulsos · variación '+savedResult.spreadMs.toFixed(1)+' ms.';
            syncStatus(summary+(route.persistent?' Guardado en este navegador.':' Guardado para esta sesión.')+' Ya puedes grabar.',true);
            msg('Calibración completada: '+summary+' La compensación se aplicará automáticamente.','ok');
        }catch(e){const text=e.name==='NotAllowedError'?'Autoriza el micrófono para calibrar.':e.message;syncStatus(text);msg(text,'error');}
        finally{job.media?.getTracks().forEach(tr=>tr.stop());if(calibration===job)calibration=null;phase='idle';update();}
    }
    function cancelCalibration(){if(calibration){calibration.controller.abort();syncStatus('Cancelando calibración…');calibration.media?.getTracks().forEach(tr=>tr.stop());}}
    syncButton.addEventListener('click',calibrate);syncCancel.addEventListener('click',cancelCalibration);
    navigator.mediaDevices?.addEventListener?.('devicechange',()=>{
        // Permission changes can also emit devicechange. Compare the actual route
        // before/after measurement instead of cancelling a first-time permission grant.
        if(phase==='idle')syncStatus('Se comprobará la calibración del dispositivo al grabar.');
    });
    function audibleTime(context,p){
        const render=context.currentTime, fallback=Math.max(0,render-outputDelay(context));
        let time=fallback;
        try{
            const stamp=context.getOutputTimestamp?.(),now=performance.now();
            if(stamp&&Number.isFinite(stamp.contextTime)&&stamp.contextTime>0&&Number.isFinite(stamp.performanceTime)&&stamp.performanceTime>0&&Math.abs(now-stamp.performanceTime)<500){
                const projected=stamp.contextTime+(now-stamp.performanceTime)/1000;
                if(projected>=0&&projected<=render+.02)time=Math.min(render,projected);
            }
        }catch(_){}
        return Math.max(0,time-(p?.graphLatency||0));
    }
    function waitWorklet(node,type,send){
        return new Promise((resolve,reject)=>{
            const done=()=>{clearTimeout(timer);node.port.removeEventListener('message',receive);};
            const receive=e=>{if(e.data?.type===type){done();resolve(e.data);}else if(e.data?.type==='arm-error'){done();reject(Error('No se pudo armar el reloj de grabación.'));}};
            const timer=setTimeout(()=>{done();reject(Error('El motor de captura no respondió. Intenta grabar de nuevo.'));},3000);
            node.port.addEventListener('message',receive);node.port.start();if(send)node.port.postMessage(send);
        });
    }
    const decodedCache = new Map();
    const cacheLimit = 128 * 1024 * 1024;
    const playbackLimit = 384 * 1024 * 1024;
    const states = {1:{mute:false,fx:false},2:{mute:false,fx:false},3:{mute:false,fx:false},4:{mute:false,fx:false}};
    const duration = c => Math.max(0, Number(c.duration_ms || 0) / 1000);
    const sourceOffset = c => Math.max(0,Number(c.source_offset_ms||0)/1000);
    const trimmed = c => c.clip_duration_ms != null;
    const playableDuration = (c,b) => Math.max(0,Math.min(trimmed(c)?duration(c):b.duration,b.duration-sourceOffset(c)));
    const startAt = c => Math.max(0, Number(c.start_ms || 0) / 1000);
    const endAt = c => startAt(c) + duration(c);
    const projectTotal = () => Math.max(0, ...clips.map(endAt), take ? take.start + take.captured / take.rate / 2 : 0);
    const format = s => { s = Math.max(0, s); return String(Math.floor(s / 60)).padStart(2, '0') + ':' + String(Math.floor(s % 60)).padStart(2, '0') + '.' + Math.floor((s % 1) * 10); };
    const vertical = () => document.body.dataset.orientation === 'vertical';
    function msg(s, state = '') { status.textContent = s; status.dataset.state = state; }
    function sanitizeTrack(n){ n = Number(n) || 1; return n >= 1 && n <= 4 ? n : 1; }
    function isMuted(track){ return !!states[sanitizeTrack(track)].mute; }
    function isFx(track){ return !!states[sanitizeTrack(track)].fx; }
    function hasAudio(c){ return c.mime === 'audio/wav' ? Number(c.pcm_bytes ?? Math.max(0, Number(c.size || 0) - 44)) > 0 || duration(c) > 0 : Number(c.size || 0) > 0 || duration(c) > 0; }
    function activePlayableClips(){ return clips.filter(c => hasAudio(c) && !isMuted(c.track)); }
    function normalizeClips(items){
        const legacyOffsets = {1:0,2:0,3:0,4:0};
        return items.map(item => {
            const track = sanitizeTrack(item.track || 1);
            let start_ms = Number(item.start_ms);
            if (item.start_ms == null || !Number.isFinite(start_ms) || start_ms < 0) {
                start_ms = Math.round(legacyOffsets[track] * 1000);
                legacyOffsets[track] += duration(item);
            }
            return {...item, track, start_ms, peaks:Array.isArray(item.peaks) ? item.peaks : []};
        });
    }
    function sortClips(){ clips.sort((a,b)=>(startAt(a)-startAt(b)) || ((a.track||1)-(b.track||1)) || ((a.created_at||'').localeCompare(b.created_at||''))); }
    function syncTrackButtons(){
        trackRows.forEach(row => {
            const track = sanitizeTrack(row.dataset.trackRow);
            const rec = row.querySelector('[data-action="rec"]');
            const mute = row.querySelector('[data-action="mute"]');
            const fx = row.querySelector('[data-action="fx"]');
            const armed = track === selectedTrack;
            row.classList.toggle('is-armed', armed);
            row.classList.toggle('is-muted', states[track].mute);
            row.classList.toggle('is-fx', states[track].fx);
            rec.classList.toggle('is-armed', armed);
            rec.setAttribute('aria-pressed', armed ? 'true' : 'false');
            rec.disabled = !['idle','playing'].includes(phase);
            mute.classList.toggle('is-on', states[track].mute);
            mute.setAttribute('aria-pressed', states[track].mute ? 'true' : 'false');
            fx.classList.toggle('is-on', states[track].fx);
            fx.setAttribute('aria-pressed', states[track].fx ? 'true' : 'false');
            fx.disabled=!['idle','playing'].includes(phase); fx.setAttribute('aria-haspopup','dialog');
        });
        let note = palette[selectedTrack].name;
        if (states[selectedTrack].mute) note += ' · mute';
        if (states[selectedTrack].fx) note += ' · fx';
        trackName.textContent = note;
    }
    function ensureExtent(){ extent = Math.max(30, Math.ceil((Math.max(projectTotal(),position) + 5) / 10) * 10); }
    function update(){
        const live = phase === 'recording', idle = phase === 'idle';
        if (!idle || tool !== 'cut') cutPreview=null;
        importButton.disabled=!AudioCtx||maxBytes<1024||!['idle','playing'].includes(phase);
        record.disabled = !supported || maxBytes < 1024 || !(idle || live || phase === 'playing');
        record.classList.toggle('is-recording', live);
        record.setAttribute('aria-label', live ? 'Detener grabación' : 'Grabar voz');
        record.title = live ? 'Detener grabación' : 'Grabar voz';
        play.disabled = phase !== 'playing' && (!idle || activePlayableClips().length <= 0);
        play.textContent = phase === 'playing' ? 'Ⅱ' : '▶';
        play.setAttribute('aria-label', phase === 'playing' ? 'Pausar' : 'Reproducir');
        stop.disabled = !['recording','playing','calibrating'].includes(phase);
        syncButton.disabled=!supported||!Sync||!['idle','playing'].includes(phase);
        syncCancel.hidden=phase!=='calibrating';
        home.disabled = !idle && phase !== 'playing';
        recovery.hidden = phase !== 'recovery';
        clock.textContent = format(position);
        if (take) saved.textContent = palette[take.track].name + ' · Guardado ' + format(take.ack / take.rate / 2) + ' / ' + format(take.captured / take.rate / 2);
        else saved.textContent = (clips.length ? clips.length + ' toma(s)' : 'Sin grabaciones') + ' · ' + format(projectTotal()) + ' · Armada ' + palette[selectedTrack].name;
        canvas.setAttribute('aria-valuenow', position.toFixed(2));
        canvas.setAttribute('aria-valuemax', String(extent));
        canvas.setAttribute('aria-orientation', vertical() ? 'vertical' : 'horizontal');
        canvas.setAttribute('aria-valuetext', format(position));
        if (playback && playback.gains) for (let t=1;t<=4;t++) playback.gains[t].gain.value = isMuted(t) ? 0 : 1;
        fxUI.sync();
        syncTrackButtons();
        canvas.dataset.tool=tool;
        toolButtons.forEach(b=>{b.setAttribute('aria-pressed',String(b.dataset.tool===tool));b.disabled=!['idle','playing'].includes(phase);});
        syncHistory();
        draw();
    }
    async function response(r){ let d; try{ d = await r.json(); }catch(_){ throw Error('Respuesta no válida del hosting (' + r.status + ').'); } if(!r.ok || !d.ok) throw Error(d.error || 'Error del servidor'); if(d.history)historyState=d.history; return d; }
    async function post(action, fields = {}, blob = null){ const f = new FormData(); f.append('action', action); f.append('project', root.dataset.project); f.append('csrf', root.dataset.csrf); for(const [k,v] of Object.entries(fields)) f.append(k, String(v)); if(blob) f.append('pcm', blob, 'pcm.bin'); return response(await fetch('recordings.php', {method:'POST', body:f, credentials:'same-origin', cache:'no-store'})); }
    async function load(){
        try{
            const d = await response(await fetch(endpoint, {cache:'no-store', credentials:'same-origin'}));
            maxBytes = Number(d.max_bytes) || 0;
            maxMp3Bytes=Number(d.max_mp3_bytes)||25*1024*1024;
            clips = normalizeClips(d.recordings || []);
            fxUI.load(d.track_fx,d.tempo_bpm);
            sortClips();
            decodedCache.clear();
            phase = 'idle'; position = 0; ensureExtent();
            msg(!supported ? 'Usa HTTPS y un navegador compatible con AudioWorklet para grabar.' : maxBytes < 1024 ? 'El hosting no admite fragmentos de audio.' : 'Arrastra un MP3 sobre una pista o pulsa MP3. REC arma la grabación.');
            update();
            for (const clip of clips) fetchPeaks(clip);
        } catch(e){ phase='idle'; msg(e.message,'error'); update(); }
    }
    function fetchPeaks(clip){if(!['audio/wav','audio/mpeg'].includes(clip.mime))return;fetch(endpoint+'&action=waveform&id='+encodeURIComponent(clip.id),{credentials:'same-origin',cache:'no-store'}).then(response).then(d=>{clip.peaks=d.peaks||[];draw();}).catch(()=>{});}
    async function reconcileEdits(){const d=await response(await fetch(endpoint,{cache:'no-store',credentials:'same-origin'}));clips=normalizeClips(d.recordings||[]);sortClips();selectedClip=null;for(const c of clips)fetchPeaks(c);}
    function syncHistory(){
        const available=['idle','playing'].includes(phase)&&!drag&&!editPointer&&!fxUI.isOpen();
        for(const [direction,button,verb,key] of [['undo',undoButton,'Deshacer','Ctrl+Z'],['redo',redoButton,'Rehacer','Ctrl+Y']]){
            const label=historyState[direction+'_label'];
            button.disabled=!available||!historyState[direction+'_id'];
            button.title=verb+(label?': '+label:'')+' ('+key+')';
            button.setAttribute('aria-label',button.title);
        }
    }
    async function applyHistory(direction){
        if(!['idle','playing'].includes(phase)||drag||editPointer||fxUI.isOpen())return;
        const id=historyState[direction+'_id'];if(!id)return;
        if(phase==='playing')pause();
        const undo=direction==='undo';phase='moving';cutPreview=null;selectedClip=null;canvas.classList.add('clip-saving');
        msg(undo?'Deshaciendo edición...':'Rehaciendo edición...');update();
        try{
            const d=await post(undo?'undo_clip':'redo_clip',{history_id:id});
            if(!Array.isArray(d.recordings)||!d.history)throw Error('El servidor no confirmó el historial.');
            clips=normalizeClips(d.recordings);sortClips();position=Math.min(position,projectTotal());ensureExtent();
            for(const c of clips)fetchPeaks(c);
            msg((undo?'Deshecho: ':'Rehecho: ')+(d.label||'Edición')+'. Audio original conservado.','ok');
        }catch(e){
            try{await reconcileEdits();position=Math.min(position,projectTotal());ensureExtent();msg('Historial actualizado. '+e.message,'error');}
            catch(_){historyState={undo_count:0,redo_count:0};msg('No se pudo confirmar el historial. Recarga la página: '+e.message,'error');}
        }finally{phase='idle';canvas.classList.remove('clip-saving');update();}
    }
    undoButton.addEventListener('click',()=>applyHistory('undo'));
    redoButton.addEventListener('click',()=>applyHistory('redo'));
    async function editClip(clip,action,time){
        if(phase!=='idle'||!clips.includes(clip))return;
        const cutting=action==='split_clip';
        let fields={recording_id:clip.id},rightId=null;
        if(cutting){const cut=Math.round((time-startAt(clip))*1000),len=Math.round(duration(clip)*1000);if(cut<1||cut>=len){msg('El corte debe estar dentro del clip.','error');return;}rightId=Array.from(crypto.getRandomValues(new Uint8Array(12)),x=>x.toString(16).padStart(2,'0')).join('');fields.cut_ms=cut;fields.right_id=rightId;}
        phase='moving';canvas.classList.add('clip-saving');msg(cutting?'Guardando división...':'Quitando clip...');update();
        try{
            const d=await post(action,fields);
            if(cutting){
                if(!Array.isArray(d.recordings)||d.recordings.length!==2||d.recordings[0].id!==clip.id||d.recordings[1].id!==rightId)throw Error('El servidor no confirmó la división.');
                const segments=normalizeClips(d.recordings),peaks=clip.peaks||[],i=Math.round(peaks.length*fields.cut_ms/Math.round(duration(clip)*1000));
                segments[0].peaks=peaks.slice(0,i);segments[1].peaks=peaks.slice(i);
                clips.splice(clips.indexOf(clip),1,...segments);selectedClip=segments[1];position=startAt(segments[1]);segments.forEach(fetchPeaks);
            }else{if(d.deleted!==clip.id)throw Error('El servidor no confirmó el borrado.');clips=clips.filter(c=>c!==clip);selectedClip=null;}
            sortClips();ensureExtent();position=Math.min(position,extent);msg(cutting?'Clip dividido. Audio original conservado.':'Clip quitado. Audio original conservado.','ok');
        }catch(e){try{await reconcileEdits();ensureExtent();position=Math.min(position,extent);const applied=cutting?clips.some(c=>c.id===rightId):!clips.some(c=>c.id===clip.id);msg(applied?'Edición confirmada en el hosting.':'No se aplicó la edición: '+e.message,applied?'ok':'error');}catch(_){msg('No se pudo confirmar la edición. Recarga para verificar: '+e.message,'error');}}
        finally{phase='idle';canvas.classList.remove('clip-saving');update();}
    }
    function geometry(){ const r = canvas.getBoundingClientRect(), v = vertical(); const timeline = v ? 42 : 28; const count = 4; const trackArea = v ? Math.max(0, r.width - timeline) : Math.max(0, r.height - timeline); const lane = trackArea / count; return {w:r.width, h:r.height, v, timeline, count, lane, trackArea}; }
    function along(g, t){ return g.v ? g.h - (t / extent) * g.h : (t / extent) * g.w; }
    function laneRect(g, track){ if (g.v) { const x = g.timeline + (track - 1) * g.lane; return {x:x+2, y:0, w:Math.max(0, g.lane-4), h:g.h}; } const y = g.timeline + (track - 1) * g.lane; return {x:0, y:y+2, w:g.w, h:Math.max(0, g.lane-4)}; }
    function drawWaveform(peaks, mapFn, half, center, color){ if (!peaks.length) return; ctx.strokeStyle = color; ctx.lineWidth = 1.2; ctx.beginPath(); const n = peaks.length; for (let i=0;i<n;i++){ const pos = mapFn((i + .5) / n), amp = Math.max(.8, (peaks[i] || 0) * half); if (vertical()) { ctx.moveTo(center - amp, pos); ctx.lineTo(center + amp, pos); } else { ctx.moveTo(pos, center - amp); ctx.lineTo(pos, center + amp); } } ctx.stroke(); }
    function draw(){
        const g = geometry();
        if (g.w < 1 || g.h < 1 || !ctx) return;
        const dpr = Math.min(2, window.devicePixelRatio || 1), w = Math.round(g.w * dpr), h = Math.round(g.h * dpr);
        if (canvas.width !== w || canvas.height !== h){ canvas.width = w; canvas.height = h; }
        ctx.setTransform(dpr,0,0,dpr,0,0); ctx.clearRect(0,0,g.w,g.h);
        ctx.fillStyle = '#0b1422'; ctx.fillRect(0,0,g.w,g.h);
        if (g.v) ctx.fillRect(0,0,g.timeline,g.h); else ctx.fillRect(0,0,g.w,g.timeline);
        const step = extent > 180 ? 30 : extent > 60 ? 10 : 5;
        ctx.font = '10px system-ui'; ctx.fillStyle = '#a9bbd2'; ctx.textBaseline = 'middle';
        for (let t=0;t<=extent;t+=step){ const p = along(g,t); ctx.strokeStyle = '#26364c'; ctx.lineWidth = 1; ctx.beginPath(); if (g.v){ ctx.moveTo(g.timeline,p); ctx.lineTo(g.w,p); } else { ctx.moveTo(p,g.timeline); ctx.lineTo(p,g.h); } ctx.stroke(); ctx.strokeStyle = '#728aa4'; ctx.beginPath(); if (g.v){ ctx.moveTo(g.timeline-7,p); ctx.lineTo(g.timeline,p); } else { ctx.moveTo(p,g.timeline-8); ctx.lineTo(p,g.timeline); } ctx.stroke(); ctx.textAlign = g.v ? 'right' : (t===0 ? 'left' : t===extent ? 'right' : 'center'); ctx.fillText(Math.floor(t/60)+':' + String(t%60).padStart(2,'0'), g.v ? g.timeline-9 : p, g.v ? Math.max(10,Math.min(g.h-3,p)) : 15); }
        for (let track=1; track<=4; track++){
            const lane = laneRect(g, track), p = palette[track], armed = track === selectedTrack, muted = states[track].mute, fx = states[track].fx;
            ctx.fillStyle = muted ? '#0a1018' : armed ? '#101b2a' : '#0d1726'; ctx.fillRect(lane.x, lane.y, lane.w, lane.h);
            ctx.strokeStyle = armed ? p.accent : muted ? '#3c4651' : '#243344'; ctx.lineWidth = armed ? 1.4 : 1; ctx.strokeRect(lane.x+.5, lane.y+.5, lane.w-1, lane.h-1);
            ctx.fillStyle = p.accent; ctx.font = '700 10px system-ui'; ctx.textAlign = 'left'; ctx.textBaseline = 'top';
            // Track labels and controls live in the aligned DOM strip, not on the waveform.
            const center = g.v ? lane.x + lane.w/2 : lane.y + lane.h/2;
            ctx.strokeStyle = muted ? '#1d2630' : '#294258'; ctx.lineWidth = 1; ctx.beginPath(); if (g.v){ ctx.moveTo(center, 0); ctx.lineTo(center, g.h); } else { ctx.moveTo(0, center); ctx.lineTo(g.w, center); } ctx.stroke();
            ctx.strokeStyle = '#26364c'; ctx.lineWidth = 1;
            for(let t=0;t<=extent;t+=step){ const q=along(g,t); ctx.beginPath(); if(g.v){ctx.moveTo(lane.x,q);ctx.lineTo(lane.x+lane.w,q);}else{ctx.moveTo(q,lane.y);ctx.lineTo(q,lane.y+lane.h);}ctx.stroke(); }
            const laneClips = clips.filter(c => sanitizeTrack(c.track) === track);
            for (const clip of laneClips){
                const s = startAt(clip), e = endAt(clip); if (e <= s) continue;
                const a = along(g, s), b = along(g, e), lo = Math.min(a,b), size = Math.max(1, Math.abs(b-a));
                ctx.globalAlpha = muted ? .35 : 1;
                ctx.fillStyle = fx ? '#2b2512' : p.fill; ctx.strokeStyle = clip===selectedClip ? '#ffffff' : muted ? '#5d6670' : p.accent; ctx.lineWidth=clip===selectedClip ? 2 : 1;
                if (g.v){ ctx.fillRect(lane.x+4, lo, lane.w-8, size); ctx.strokeRect(lane.x+4, lo, lane.w-8, size); } else { ctx.fillRect(lo, lane.y+4, size, lane.h-8); ctx.strokeRect(lo, lane.y+4, size, lane.h-8); }
                drawWaveform(clip.peaks || [], frac => along(g, s + frac * duration(clip)), Math.max(8, (g.v ? lane.w-14 : lane.h-14) / 2), center, muted ? '#7f8b98' : (fx ? '#ffd166' : p.wave));
                if(clip.mime==='audio/mpeg')drawMp3Label(g,lane,lo,size,clip);
                ctx.globalAlpha = 1;
            }
            if (take && take.track === track){
                const s = take.start, d = take.captured / take.rate / 2, a = along(g, s), b = along(g, s + d), lo = Math.min(a,b), size = Math.max(1, Math.abs(b-a));
                ctx.fillStyle = p.live; ctx.strokeStyle = '#ff5e7e';
                if (g.v){ ctx.fillRect(lane.x+4, lo, lane.w-8, size); ctx.strokeRect(lane.x+4, lo, lane.w-8, size); } else { ctx.fillRect(lo, lane.y+4, size, lane.h-8); ctx.strokeRect(lo, lane.y+4, size, lane.h-8); }
                drawWaveform(take.peaks || [], frac => along(g, s + frac * d), Math.max(8, (g.v ? lane.w-14 : lane.h-14) / 2), center, fx ? '#ffe4a8' : p.liveWave);
            }
        }
        const cursor = along(g, position), col = take ? '#ff5276' : '#33e7ff';
        ctx.strokeStyle = col; ctx.lineWidth = 2; ctx.beginPath(); if (g.v){ ctx.moveTo(0,cursor); ctx.lineTo(g.w,cursor); } else { ctx.moveTo(cursor,0); ctx.lineTo(cursor,g.h); } ctx.stroke();
        ctx.fillStyle = col; if (g.v) ctx.fillRect(g.timeline-5,cursor-4,8,8); else ctx.fillRect(cursor-4,g.timeline-5,8,8);
        drawCutPreview(g);
        drawImportPreview(g);
    }
    function move(p){ position = Math.max(0, Math.min(extent, p)); update(); }
    function seek(e){ if(!['idle','playing'].includes(phase)) return; const r = canvas.getBoundingClientRect(); const f = vertical() ? 1 - (e.clientY-r.top)/r.height : (e.clientX-r.left)/r.width; const target = Math.max(0, Math.min(projectTotal(), f * extent)); if(phase==='playing'){ pause(); position = target; startPlay(); } else move(target); }
    // The time axis runs rightward in landscape and upward in portrait.
    function point(e){
        const r=canvas.getBoundingClientRect(),g=geometry(),x=e.clientX-r.left,y=e.clientY-r.top;
        const cross=g.v?x:y, axis=g.v?g.h-y:x, axisSize=g.v?g.h:g.w;
        const track=g.lane>0&&cross>=g.timeline&&cross<g.timeline+g.trackArea?1+Math.floor((cross-g.timeline)/g.lane):0;
        return {x,y,g,track,time:axis/Math.max(1,axisSize)*extent};
    }
    // Import original MP3 bytes; each chunk fits the hosting's PHP upload limit.
    function drawMp3Label(g,lane,lo,size,clip){
        if(size<18||Math.min(lane.w,lane.h)<18)return;
        ctx.save();ctx.beginPath();
        if(g.v){ctx.rect(lane.x+4,lo,lane.w-8,size);ctx.clip();ctx.translate(lane.x+8,lo+size-4);ctx.rotate(-Math.PI/2);}
        else{ctx.rect(lo,lane.y+4,size,lane.h-8);ctx.clip();ctx.translate(lo+5,lane.y+7);}
        ctx.font='600 10px system-ui';ctx.textAlign='left';ctx.textBaseline='top';ctx.fillStyle='#f1f8ff';
        ctx.fillText(clip.original_name||'Audio MP3',0,0);ctx.restore();
    }
    function drawImportPreview(g){
        if(!importPreview)return;
        const lane=laneRect(g,importPreview.track),q=along(g,importPreview.time);
        ctx.save();ctx.fillStyle='#33d5ff19';ctx.fillRect(lane.x,lane.y,lane.w,lane.h);
        ctx.strokeStyle='#33d5ff';ctx.lineWidth=2;ctx.strokeRect(lane.x+1,lane.y+1,lane.w-2,lane.h-2);
        ctx.beginPath();if(g.v){ctx.moveTo(lane.x,q);ctx.lineTo(lane.x+lane.w,q);}else{ctx.moveTo(q,lane.y);ctx.lineTo(q,lane.y+lane.h);}ctx.stroke();
        const label='MP3 · P'+importPreview.track+' · '+format(importPreview.time);ctx.font='600 11px system-ui';const w=ctx.measureText(label).width+12;
        const x=Math.max(2,Math.min(g.w-w-2,g.v?lane.x:q+4)),y=Math.max(2,Math.min(g.h-22,g.v?q-22:lane.y+6));
        ctx.fillStyle='#142638';ctx.fillRect(x,y,w,20);ctx.fillStyle='#b7f5ff';ctx.textAlign='left';ctx.textBaseline='middle';ctx.fillText(label,x+6,y+10);ctx.restore();
    }
    function clearImportPreview(){if(importPreview){importPreview=null;draw();}}
    const hasFiles=e=>Array.from(e.dataTransfer?.types||[]).includes('Files');
    const canImport=()=>!!AudioCtx&&maxBytes>=1024&&['idle','playing'].includes(phase)&&!fxUI.isOpen();
    function mp3Target(e){const p=point(e);return p.track?{track:p.track,time:Math.max(0,Math.min(600,p.time))}:null;}
    // Never navigate away from the project when a desktop file is dropped.
    window.addEventListener('dragover',e=>{if(hasFiles(e)){e.preventDefault();if(e.target!==canvas)e.dataTransfer.dropEffect='none';}});
    window.addEventListener('drop',e=>{if(hasFiles(e)){e.preventDefault();clearImportPreview();}});
    canvas.addEventListener('dragover',e=>{
        if(!hasFiles(e))return;e.preventDefault();
        const dest=canImport()?mp3Target(e):null;
        e.dataTransfer.dropEffect=dest?'copy':'none';importPreview=dest;cutPreview=null;draw();
    });
    canvas.addEventListener('dragleave',clearImportPreview);
    canvas.addEventListener('drop',e=>{
        if(!hasFiles(e))return;e.preventDefault();e.stopPropagation();
        const dest=canImport()?mp3Target(e):null,files=Array.from(e.dataTransfer.files||[]);clearImportPreview();
        if(dest&&files.length)importMp3Files(files,dest.track,dest.time);
        else if(files.length)msg('Suelta los MP3 dentro de una pista cuando el editor esté disponible.','error');
    });
    importButton.addEventListener('click',()=>{if(canImport())importInput.click();});
    importInput.addEventListener('change',()=>{const files=Array.from(importInput.files||[]);importInput.value='';if(files.length&&canImport())importMp3Files(files,selectedTrack,position);});
    function mp3Peaks(buffer){
        const n=Math.min(720,buffer.length),peaks=Array(n).fill(0);
        for(let ch=0;ch<buffer.numberOfChannels;ch++){
            const data=buffer.getChannelData(ch);
            for(let i=0;i<n;i++){
                const a=Math.floor(i*data.length/n),b=Math.floor((i+1)*data.length/n);let peak=peaks[i];
                const stride=Math.max(1,Math.floor((b-a)/2048));
                for(let j=a;j<b;j+=stride)peak=Math.max(peak,Math.abs(data[j]));
                peaks[i]=Math.min(1,peak);
            }
        }
        return peaks.map(x=>Math.round(x*1000)/1000);
    }
    async function importRequest(action,fields,blob=null){
        // Exact-byte retries are safe; the server also makes finalization idempotent.
        let last;
        for(let attempt=0;attempt<2;attempt++){
            try{
                const f=new FormData();f.append('action',action);f.append('project',root.dataset.project);f.append('csrf',root.dataset.csrf);
                for(const [k,v] of Object.entries(fields))f.append(k,String(v));if(blob)f.append('pcm',blob,'mp3.part');
                const ctl=new AbortController(),timer=setTimeout(()=>ctl.abort(),60000);
                try{return await response(await fetch('recordings.php',{method:'POST',body:f,credentials:'same-origin',cache:'no-store',signal:ctl.signal}));}finally{clearTimeout(timer);}
            }catch(e){last=e;}
        }
        throw last;
    }
    async function importMp3Files(files,track,start){
        if(!canImport())return;
        if(phase==='playing')pause();
        phase='importing';selectedTrack=track;update();
        let next=Math.round(Math.max(0,start)*1000),count=0,lastError='';
        try{
            for(const file of files){
                let id=null;
                try{
                    if(!/\.mp3$/i.test(file.name)&&file.type!=='audio/mpeg')throw Error('Selecciona un archivo MP3.');
                    if(file.size<1||file.size>maxMp3Bytes)throw Error('Tamaño máximo por MP3: '+Math.floor(maxMp3Bytes/1048576)+' MB.');
                    if(next>600000)throw Error('La posición inicial supera el límite actual de 10 minutos.');
                    msg('Analizando '+file.name+'...');
                    if(!playbackContext||playbackContext.state==='closed')playbackContext=new AudioCtx();
                    const buffer=await playbackContext.decodeAudioData(await file.arrayBuffer());
                    const durationMs=Math.round(buffer.duration*1000);
                    if(durationMs<1||durationMs>600000||bufferBytes(buffer)>playbackLimit)throw Error('El MP3 supera el límite de 10 minutos o la memoria disponible.');
                    const peaks=mp3Peaks(buffer);
                    id=Array.from(crypto.getRandomValues(new Uint8Array(12)),x=>x.toString(16).padStart(2,'0')).join('');
                    const common={recording_id:id,total_bytes:file.size};
                    const step=Math.max(1024,Math.min(1024*1024,maxBytes));
                    let offset=0;
                    while(offset<file.size){
                        const end=Math.min(file.size,offset+step);
                        const d=await importRequest('mp3_chunk',{...common,offset},file.slice(offset,end));
                        if(Number(d.received)!==end)throw Error('El hosting no confirmó el fragmento MP3.');
                        offset=end;msg('Subiendo '+file.name+' · '+Math.round(offset/file.size*100)+'%');
                    }
                    const d=await importRequest('mp3_finish',{...common,track,start_ms:next,duration_ms:durationMs,original_name:file.name,peaks:JSON.stringify(peaks)});
                    if(d.recording?.id!==id||d.recording.mime!=='audio/mpeg'||Number(d.recording.track)!==track||Number(d.recording.start_ms)!==next)throw Error('El hosting no confirmó el clip MP3.');
                    const clip=normalizeClips([d.recording])[0];clip.peaks=peaks;
                    clips.push(clip);sortClips();selectedClip=clip;position=startAt(clip);next+=durationMs;
                    cacheBuffer(clip.file+':'+String(clip.size||0)+':'+String(clip.pcm_bytes||0),buffer);
                    ensureExtent();count++;update();
                }catch(e){
                    lastError=file.name+': '+e.message;
                    if(id){
                        // A lost final response must not duplicate an imported clip.
                        try{const data=await response(await fetch(endpoint,{credentials:'same-origin',cache:'no-store'}));const found=normalizeClips(data.recordings||[]).find(c=>c.id===id);if(found&&!clips.some(c=>c.id===id)){clips.push(found);sortClips();selectedClip=found;position=startAt(found);next=Math.round(endAt(found)*1000);ensureExtent();count++;fetchPeaks(found);lastError='';update();continue;}}catch(_){}
                        try{await importRequest('mp3_cancel',{recording_id:id});}catch(_){}
                    }
                }
            }
        }finally{phase='idle';clearImportPreview();msg(lastError?(count?count+' MP3 guardado(s). ':'')+lastError:count+' MP3 guardado(s) en assets de '+palette[track].name+'.',lastError?'error':'ok');update();}
    }

    function hit(p){
        if(!p.track)return null;
        const lane=laneRect(p.g,p.track),cross=p.g.v?p.x:p.y,lo=p.g.v?lane.x:lane.y,hi=lo+(p.g.v?lane.w:lane.h);
        if(cross<lo+2||cross>hi-2)return null;
        const tolerance=extent/Math.max(1,p.g.v?p.g.h:p.g.w)*3;
        return [...clips].reverse().find(c=>sanitizeTrack(c.track)===p.track&&duration(c)>0&&p.time>=startAt(c)-tolerance&&p.time<=endAt(c)+tolerance)||null;
    }
    // Preview and actual split share the same millisecond resolution.
    function cutAt(p){
        if(tool!=='cut'||phase!=='idle')return null;
        const clip=hit(p);
        if(!clip)return null;
        const lane=laneRect(p.g,p.track),cross=p.g.v?p.x:p.y,lo=p.g.v?lane.x:lane.y,hi=lo+(p.g.v?lane.w:lane.h);
        if(cross<lo+4||cross>hi-4)return null;
        const ms=Math.round((p.time-startAt(clip))*1000);
        if(ms<1||ms>=Math.round(duration(clip)*1000))return null;
        return {clip,time:startAt(clip)+ms/1000};
    }
    function clearCutPreview(){if(cutPreview){cutPreview=null;draw();}}
    function previewCut(e){
        const next=cutAt(point(e));
        if((!next&&!cutPreview)||(next&&cutPreview&&next.clip===cutPreview.clip&&next.time===cutPreview.time))return;
        cutPreview=next;draw();
    }
    function drawCutPreview(g){
        if(tool!=='cut'||phase!=='idle'||!cutPreview||!clips.includes(cutPreview.clip))return;
        const lane=laneRect(g,sanitizeTrack(cutPreview.clip.track)),p=along(g,cutPreview.time);
        const totalMs=Math.round(cutPreview.time*1000),m=Math.floor(totalMs/60000),sec=Math.floor(totalMs/1000)%60;
        const label=String(m).padStart(2,'0')+':'+String(sec).padStart(2,'0')+'.'+String(totalMs%1000).padStart(3,'0');
        ctx.save();
        // Dark outline and a bright amber guide remain visible on every waveform color.
        for(const [color,width] of [['#07111c',4],['#ffe08a',2]]){
            ctx.strokeStyle=color;ctx.lineWidth=width;ctx.beginPath();
            if(g.v){ctx.moveTo(lane.x+4,p);ctx.lineTo(lane.x+lane.w-4,p);}
            else{ctx.moveTo(p,lane.y+4);ctx.lineTo(p,lane.y+lane.h-4);}
            ctx.stroke();
        }
        ctx.font='600 11px system-ui';ctx.textAlign='left';ctx.textBaseline='middle';
        const tw=ctx.measureText(label).width+12,th=19;
        const x=Math.max(1,Math.min(g.w-tw-1,g.v?lane.x+4:p+7));
        const y=Math.max(1,Math.min(g.h-th-1,g.v?p-th-5:lane.y+6));
        ctx.fillStyle='#101927';ctx.fillRect(x,y,tw,th);ctx.strokeStyle='#ffe08a';ctx.lineWidth=1;ctx.strokeRect(x+.5,y+.5,tw-1,th-1);
        ctx.fillStyle='#ffe08a';ctx.fillText(label,x+6,y+th/2);
        ctx.restore();
    }
    function resetDrag(d){ d.clip.track=d.track;d.clip.start_ms=d.start;phase='idle';canvas.classList.remove('clip-dragging','clip-saving');draw();update(); }
    function cancelDrag(){
        if(!drag)return;const d=drag;drag=null;resetDrag(d);
        if(canvas.hasPointerCapture(d.pointer))canvas.releasePointerCapture(d.pointer);
        msg('Movimiento cancelado.');
    }
    async function saveClipMove(d){
        const clip=d.clip,target={track:clip.track,start_ms:clip.start_ms};
        if(target.track===d.track&&target.start_ms===d.start){phase='idle';update();return;}
        phase='moving';canvas.classList.remove('clip-dragging');canvas.classList.add('clip-saving');msg('Guardando nueva posición...');update();
        try{
            const result=await post('move_clip',{recording_id:clip.id,...target});
            if(result.recording?.id!==clip.id||Number(result.recording.track)!==target.track||Number(result.recording.start_ms)!==target.start_ms)throw Error('El servidor no confirmó la posición.');
            Object.assign(clip,result.recording);sortClips();ensureExtent();position=startAt(clip);msg('Clip guardado en '+palette[clip.track].name+' · '+format(position),'ok');
        }catch(e){
            // A lost HTTP response may follow a successful write. Reconcile before rollback.
            try{const data=await response(await fetch(endpoint,{cache:'no-store',credentials:'same-origin'}));const item=normalizeClips(data.recordings||[]).find(c=>c.id===clip.id);if(!item)throw Error('Clip no encontrado');const peaks=clip.peaks;Object.assign(clip,item,{peaks});sortClips();ensureExtent();position=startAt(clip);if(clip.track===target.track&&clip.start_ms===target.start_ms)msg('Posición guardada en el hosting.','ok');else msg('No se aplicó el movimiento: '+e.message,'error');}
            catch(_){clip.track=d.track;clip.start_ms=d.start;msg('No se pudo confirmar el movimiento. Recarga para verificar: '+e.message,'error');}
        }finally{phase='idle';canvas.classList.remove('clip-saving','clip-dragging');update();}
    }
    canvas.addEventListener('pointerdown',e=>{
        if(e.button!==0||!e.isPrimary||drag||!['idle','playing'].includes(phase))return;
        const p=point(e),clip=phase==='idle'?hit(p):null;
        canvas.setPointerCapture(e.pointerId);
        if(tool==='cut'){
            const target=cutAt(p);cutPreview=target;
            if(target){selectedClip=target.clip;editPointer={pointer:e.pointerId,clip:target.clip,time:target.time,x:e.clientX,y:e.clientY,tool};}
            draw();return;
        }
        if(clip&&tool==='erase'){selectedClip=clip;editPointer={pointer:e.pointerId,clip,time:p.time,x:e.clientX,y:e.clientY,tool};draw();return;}
        if(!clip||tool==='pointer'){selectedClip=clip;seekingPointer=e.pointerId;seek(e);return;}
        selectedClip=clip;drag={clip,track:clip.track,start:clip.start_ms,offset:p.time-startAt(clip),pointer:e.pointerId,x:e.clientX,y:e.clientY,moved:false};
        phase='dragging';canvas.classList.add('clip-dragging');canvas.classList.remove('clip-hover');update();
    });
    canvas.addEventListener('pointermove',e=>{
        if(drag&&drag.pointer===e.pointerId){
            if(!drag.moved&&Math.hypot(e.clientX-drag.x,e.clientY-drag.y)<4)return;
            drag.moved=true;const p=point(e);
            drag.clip.track=p.track||drag.clip.track;
            drag.clip.start_ms=Math.max(0,Math.min(600000,Math.round((p.time-drag.offset)*1000)));
            msg('Mover a '+palette[drag.clip.track].name+' · '+format(startAt(drag.clip)));draw();return;
        }
        if(seekingPointer===e.pointerId&&canvas.hasPointerCapture(e.pointerId)&&phase==='idle'){seek(e);return;}
        canvas.classList.toggle('clip-hover',tool==='hand'&&phase==='idle'&&!!hit(point(e)));
        if(tool==='cut'&&e.isPrimary)previewCut(e);else clearCutPreview();
    });
    canvas.addEventListener('pointerup',e=>{
        if(seekingPointer===e.pointerId)seekingPointer=null;
        if(editPointer?.pointer===e.pointerId){
            const d=editPointer;editPointer=null;
            if(d.tool==='cut'){
                const target=cutAt(point(e));
                if(Math.hypot(e.clientX-d.x,e.clientY-d.y)<8&&target?.clip===d.clip){clearCutPreview();editClip(d.clip,'split_clip',target.time);}
                else clearCutPreview();
            }else if(Math.hypot(e.clientX-d.x,e.clientY-d.y)<8&&hit(point(e))===d.clip)editClip(d.clip,'delete_clip',d.time);
            return;
        }
        if(!drag||drag.pointer!==e.pointerId)return;
        const d=drag;drag=null;canvas.classList.remove('clip-dragging');
        if(d.moved){saveClipMove(d);}else{phase='idle';move(Math.max(0,Math.min(projectTotal(),point(e).time)));msg('Clip seleccionado. Arrastra para moverlo.');}
    });
    canvas.addEventListener('pointerleave',clearCutPreview);
    canvas.addEventListener('pointercancel',e=>{clearCutPreview();if(drag?.pointer===e.pointerId)cancelDrag();if(seekingPointer===e.pointerId)seekingPointer=null;if(editPointer?.pointer===e.pointerId)editPointer=null;});
    canvas.addEventListener('lostpointercapture',e=>{if(editPointer?.pointer===e.pointerId)clearCutPreview();if(drag?.pointer===e.pointerId)cancelDrag();if(seekingPointer===e.pointerId)seekingPointer=null;if(editPointer?.pointer===e.pointerId)editPointer=null;});
    document.addEventListener('keydown',e=>{if(fxUI.isOpen())return;const editable=e.target instanceof Element&&e.target.closest('input,textarea,select,[contenteditable]:not([contenteditable=false])');const key=e.key.toLowerCase();if((e.ctrlKey||e.metaKey)&&!e.altKey&&!editable&&(key==='z'||key==='y')){e.preventDefault();if(!e.repeat)applyHistory(key==='y'||e.shiftKey?'redo':'undo');return;}if(e.key==='Escape'){if(drag){e.preventDefault();cancelDrag();}editPointer=null;clearCutPreview();return;}if(e.ctrlKey||e.metaKey||e.altKey||e.target.closest('input,textarea,select,[contenteditable=true]'))return;const modes={v:'pointer',h:'hand',c:'cut',e:'erase'};if(modes[e.key.toLowerCase()]&&['idle','playing'].includes(phase)){e.preventDefault();setTool(modes[e.key.toLowerCase()]);}});
    canvas.addEventListener('keydown',e=>{
        if(phase!=='idle')return;
        if(e.key==='Delete'&&selectedClip){e.preventDefault();editClip(selectedClip,'delete_clip',position);return;}
        if(e.altKey&&selectedClip&&e.key.startsWith('Arrow')){
            e.preventDefault();const clip=selectedClip,d={clip,track:clip.track,start:clip.start_ms};
            const delta=e.shiftKey?1000:100;
            if(vertical()){
                if(e.key==='ArrowUp'||e.key==='ArrowDown')clip.start_ms+=e.key==='ArrowUp'?delta:-delta;
                else clip.track+=e.key==='ArrowRight'?1:-1;
            }else{
                if(e.key==='ArrowRight'||e.key==='ArrowLeft')clip.start_ms+=e.key==='ArrowRight'?delta:-delta;
                else clip.track+=e.key==='ArrowDown'?1:-1;
            }
            clip.track=Math.max(1,Math.min(4,clip.track));clip.start_ms=Math.max(0,Math.min(600000,clip.start_ms));saveClipMove(d);return;
        }
        let p=position;if(['ArrowUp','ArrowRight'].includes(e.key))p++;else if(['ArrowDown','ArrowLeft'].includes(e.key))p--;else if(e.key==='Home')p=0;else if(e.key==='End')p=projectTotal();else return;e.preventDefault();move(Math.min(projectTotal(),p));
    });
    trackRows.forEach(row => row.addEventListener('click', e => {
        const button = e.target.closest('.track-action');
        if (!button) return;
        const track = sanitizeTrack(button.dataset.track), action = button.dataset.action;
        if (action === 'rec') { if (!['idle','playing'].includes(phase)) return; selectedTrack = track; }
        else if (action === 'mute') states[track].mute = !states[track].mute;
        else if (action === 'fx') { if(!['idle','playing'].includes(phase))return; fxUI.open(track); }
        update();
    }));
    new ResizeObserver(()=>{cutPreview=null;draw();}).observe(canvas); new MutationObserver(()=>{cutPreview=null;editPointer=null;if(drag)cancelDrag();update();}).observe(document.body, {attributes:true, attributeFilter:['data-orientation']});
    function release(t){ if(t.node){ try{ t.node.disconnect(); }catch(_){} t.node.port.onmessage = null; } if(t.source){ try{ t.source.disconnect(); }catch(_){} } if(t.media) t.media.getTracks().forEach(x => x.stop()); if(t.context && t.context!==playbackContext) t.context.close().catch(()=>{}); }
    function capture(t, buffer, peaks, frame){
        if(t!==take||!['recording','stopping'].includes(phase))return;
        const expected=t.captureFrame+t.captured/2;
        if(!Number.isSafeInteger(frame)||frame!==expected||buffer.byteLength%2){t.error='Se detectó un salto en el reloj de captura. Los fragmentos confirmados se conservan.';if(phase==='recording')endTake();return;}
        const available=Math.max(0,t.rate*2*600-t.captured),bytes=buffer.byteLength>available?buffer.slice(0,available):buffer;
        if(bytes.byteLength){const offset=t.captured;t.captured+=bytes.byteLength;t.raw.push(bytes);t.peaks.push(...peaks);const block=Math.max(2,Math.min(1048576,maxBytes)&~1);for(let i=0;i<bytes.byteLength;i+=block)t.queue.push({offset:offset+i,buffer:bytes.slice(i,i+block)});ensureExtent();update();pump(t);}
    }
    async function pump(t){ if(t.pumping || t.error || t !== take) return; t.pumping = true; try{ while(t.queue.length){ const q = t.queue[0]; const d = await post('stream_chunk', {recording_id:t.id, offset:q.offset}, new Blob([q.buffer], {type:'application/octet-stream'})); if(Number(d.pcm_bytes) < q.offset + q.buffer.byteLength) throw Error('El servidor no confirmó el fragmento.'); t.ack = Number(d.pcm_bytes); t.item = d.recording; t.queue.shift(); update(); } }catch(e){ t.error = e.message; if(phase==='recording') endTake(); } finally { t.pumping = false; if(t.ended) finalize(t); } }
    function makeDownload(t){ if(localUrl) URL.revokeObjectURL(localUrl); const h = new ArrayBuffer(44), v = new DataView(h); const str = (off,s)=>{for(let i=0;i<s.length;i++)v.setUint8(off+i,s.charCodeAt(i));}; str(0,'RIFF'); v.setUint32(4,36+t.captured,true); str(8,'WAVEfmt '); v.setUint32(16,16,true); v.setUint16(20,1,true); v.setUint16(22,1,true); v.setUint32(24,t.rate,true); v.setUint32(28,t.rate*2,true); v.setUint16(32,2,true); v.setUint16(34,16,true); str(36,'data'); v.setUint32(40,t.captured,true); localUrl = URL.createObjectURL(new Blob([h,...t.raw], {type:'audio/wav'})); download.href = localUrl; download.download = 'voz_' + t.id + '.wav'; }
    function recover(t){ phase = 'recovery'; makeDownload(t); msg((t.error || 'No se pudo confirmar el guardado.') + ' · ' + format(t.ack/t.rate/2) + ' guardados en ' + palette[t.track].name + '.', 'error'); update(); }
    async function finalize(t){
        if(t!==take||!t.ended||t.pumping||t.finalizing)return;
        if(t.error){recover(t);return;}
        if(t.queue.length){pump(t);return;}
        t.finalizing=true;phase='saving';update();
        try{
            if(t.ack!==t.captured||t.endFrame!==t.captureFrame+t.captured/2)throw Error('No coincide el número de muestras grabadas y guardadas.');
            const d=await post('stream_finish',{recording_id:t.id,offset:t.ack,transport_start_frame:t.transportFrame,capture_start_frame:t.captureFrame,capture_end_frame:t.endFrame,latency_frames:t.compFrames,sync_method:t.syncMethod,...(t.syncMethod==='acoustic'?{acoustic_latency_frames:t.acousticFrames}:{})});
            if(d.recording?.id!==t.id||Number(d.pcm_bytes)!==t.captured||Number(d.recording.start_ms)!==Math.round(t.start*1000)||Number(d.recording.track)!==t.track)throw Error('El hosting no confirmó la posición o duración exacta de la toma.');
            clips.push({...d.recording,peaks:t.peaks});sortClips();position=t.start+t.captured/t.rate/2;take=null;phase='idle';
            if(localUrl)URL.revokeObjectURL(localUrl);localUrl=null;ensureExtent();msg('Grabación WAV guardada · '+format(t.captured/t.rate/2)+(t.syncMethod==='acoustic'?' · SYNC medido.':' · captura directa.'),'ok');update();
        }catch(e){t.error=e.message;recover(t);}finally{t.finalizing=false;}
    }
    function finishCapture(t,data){
        if(t!==take||t.ended)return;
        clearTimeout(t.stopTimeout);
        t.endFrame=Number(data.endFrame);
        if(data.startFrame!==t.captureFrame||!Number.isSafeInteger(t.endFrame)||data.frames!==t.captured/2||t.endFrame!==t.captureFrame+t.captured/2){t.error=t.error||'El capturador no confirmó la secuencia completa de muestras. Puedes guardar el tramo continuo recibido.';t.endFrame=t.captureFrame+t.captured/2;}
        // For negative compensation the mic ends before the transport. Sources already
        // have a scheduled stop; keep the mix graph alive until that exact moment.
        phase='stopping';cancelAnimationFrame(playbackFrame);playbackFrame=0;
        const close=()=>{if(t!==take||t.ended)return;stopMix(false);release(t);t.ended=true;position=t.start+t.captured/t.rate/2;finalize(t);};
        const transportEnd=t.when+(t.captured/2)/t.rate;
        const remaining=Math.max(0,(Math.min(Number(t.stopMixWhen||transportEnd),transportEnd)+(playback?.graphLatency||0)-t.context.currentTime)*1000);
        if(remaining>0)setTimeout(close,remaining+15);else close();
    }
    function endTake(){
        const t=take;if(!t||phase!=='recording')return;
        phase='stopping';cancelAnimationFrame(playbackFrame);playbackFrame=0;
        // Send a frame deadline ahead of the render quantum. Apply the same latency
        // offset at both boundaries so capture length equals transport length.
        const nowFrame=Math.ceil(t.context.currentTime*t.rate);
        const lead=Math.max(512,Math.ceil(t.rate*.02));
        const transportEnd=Math.max(t.transportFrame,Math.min(t.transportFrame+Math.round(t.rate*600),nowFrame+lead));
        const captureEnd=transportEnd+t.compFrames;
        t.stopMixWhen=transportEnd/t.rate;
        for(const n of playback?.nodes||[]){try{n.stop(t.stopMixWhen);}catch(_){}}
        const out=playback?.output;if(out){out.gain.cancelScheduledValues(t.context.currentTime);out.gain.setValueAtTime(1,t.context.currentTime);out.gain.setValueAtTime(0,t.stopMixWhen+(playback?.graphLatency||0));}
        position=t.start+(transportEnd-t.transportFrame)/t.rate;msg('Guardando las últimas muestras...');update();
        t.node.port.postMessage({type:'stop',frame:captureEnd});
        t.stopTimeout=setTimeout(()=>{if(!t.ended){t.error=t.error||'No se confirmó el final del reloj de audio. Puedes guardar el tramo continuo recibido.';t.endFrame=t.captureFrame+t.captured/2;stopMix(false);release(t);t.ended=true;finalize(t);}},Math.max(2500,(captureEnd-nowFrame)/t.rate*1000+2000));
    }
    async function begin(){
        if(!['idle','playing'].includes(phase)||!supported)return;
        if(phase==='playing')pause();
        if(position>600){msg('La posición de grabación supera el límite de 10 minutos.','error');return;}
        phase='starting';msg('Preparando micrófono y acompañamiento...');update();
        const t={id:Array.from(crypto.getRandomValues(new Uint8Array(12)),x=>x.toString(16).padStart(2,'0')).join(''),track:selectedTrack,start:Math.round(position*1000)/1000,raw:[],queue:[],peaks:[],captured:0,ack:0,rate:48000,error:null,pumping:false,ended:false,finalizing:false};
        const p=newMix(t.start);playback=p;
        try{
            // Resume from the record gesture; both mic and playback use one sample clock.
            if(!playbackContext||playbackContext.state==='closed')playbackContext=new AudioCtx({latencyHint:'interactive'});
            t.context=playbackContext;await t.context.resume();
            if(t.context.state!=='running')throw Error('El navegador bloqueó el audio. Pulsa Grabar nuevamente.');
            t.media=await navigator.mediaDevices.getUserMedia(micConstraints);
            t.rate=t.context.sampleRate;
            await t.context.audioWorklet.addModule('assets/pcm-worklet.js?v=0.1.24');
            t.source=t.context.createMediaStreamSource(t.media);
            // Warm up the actual input graph before starting the accompaniment.
            // The processor emits silence and waits for an absolute start frame.
            t.node=new AudioWorkletNode(t.context,'futureo-pcm',{numberOfInputs:1,numberOfOutputs:1,outputChannelCount:[1]});
            const ready=waitWorklet(t.node,'ready');
            t.source.connect(t.node);t.node.connect(t.context.destination);
            await ready;
            const results=await prepareMix(p,t.context,true);
            if(playback!==p||p.abort.signal.aborted)throw Error('Se canceló la preparación del acompañamiento.');
            const audible=results.some(x=>!isMuted(x.clip.track)),accompaniment=results.length>0;
            let measured=null;
            if(accompaniment){
                if(!Sync)throw Error('No se cargó el módulo SYNC. Actualiza la página.');
                const route=await Sync.route(t.context,t.media);measured=Sync.lookup(route);
                if(!measured){syncDetails.open=true;syncStatus('Este dispositivo aún no tiene una calibración válida. Acerca el micrófono a tu salida de audio y pulsa Calibrar.');throw Error('Calibra SYNC antes de grabar con acompañamiento.');}
            }
            const estimate=compensation(t,p,accompaniment,measured);
            t.compFrames=estimate.frames;t.compMs=estimate.ms;t.audible=audible;t.syncMethod=estimate.method;t.acousticFrames=estimate.acousticFrames;
            if(measured)syncStatus((measured.seconds*1000).toFixed(1)+' ms medidos + '+Math.round((p.graphLatency||0)*1000)+' ms del motor = '+t.compMs+' ms aplicados automáticamente.',true);
            else syncStatus('Captura sin acompañamiento: '+t.compMs+' ms de entrada estimada.');
            const d=await post('stream_start',{recording_id:t.id,sample_rate:t.rate,track:t.track,start_ms:Math.round(t.start*1000)});
            t.item=d.recording;
            if(d.recording?.id!==t.id||Number(d.recording.start_ms)!==Math.round(t.start*1000)||Number(d.recording.track)!==t.track)throw Error('El hosting no confirmó el inicio de la toma.');
            // Schedule both capture and sources after the input worklet is running.
            // The requested start frame is acknowledged before playback is scheduled.
            const margin=Math.ceil(t.rate*.25);
            t.transportFrame=Math.ceil(t.context.currentTime*t.rate)+margin;
            t.captureFrame=t.transportFrame+t.compFrames;t.when=t.transportFrame/t.rate;
            const armed=await waitWorklet(t.node,'armed',{type:'arm',frame:t.captureFrame});
            if(armed.frame!==t.captureFrame||t.context.currentTime>t.when-.025)throw Error('El reloj de audio no quedó listo. Vuelve a pulsar Grabar.');
            t.node.port.onmessage=e=>{if(e.data.type==='pcm')capture(t,e.data.buffer,e.data.peaks,e.data.frame);else if(e.data.type==='stopped')finishCapture(t,e.data);};
            t.node.onprocessorerror=()=>{if(t===take&&!t.ended){t.error='El procesador de captura se interrumpió. Puedes guardar el tramo continuo recibido.';t.endFrame=t.captureFrame+t.captured/2;stopMix(false);release(t);t.ended=true;finalize(t);}};
            t.media.getAudioTracks().forEach(tr=>tr.addEventListener('ended',()=>{if(t===take&&phase==='recording')endTake();}));
            take=t;position=t.start;phase='recording';
            scheduleMix(p,t.context,results,t.when);
            t.stopMixWhen=t.when+600;
            for(const n of p.nodes){try{n.stop(t.stopMixWhen);}catch(_){}}
            if(p.output)p.output.gain.setValueAtTime(0,t.stopMixWhen+(p.graphLatency||0));
            msg('Grabando en '+palette[t.track].name+(audible?' · acompañamiento activo':' · sin acompañamiento audible')+(t.syncMethod==='acoustic'?' · SYNC medido':' · captura directa')+' · guardado cada 0,5 s'+(p.warning?' · '+p.warning:''),p.warning?'error':'');
            update();recordingTick(t);
        }catch(e){stopMix(false);release(t);take=null;phase='idle';msg(e.name==='NotAllowedError'?'Autoriza el micrófono en el navegador.':e.message,'error');update();}
    }
    function recordingTick(t){
        if(t!==take||phase!=='recording')return;
        position=t.start+Math.min(600,Math.max(0,(t.audible?audibleTime(t.context,playback):t.context.currentTime)-t.when));
        if(position>extent-1)extent=Math.max(extent,Math.ceil((position+5)/10)*10);
        clock.textContent=format(position);canvas.setAttribute('aria-valuenow',position.toFixed(2));canvas.setAttribute('aria-valuetext',format(position));draw();
        playbackFrame=requestAnimationFrame(()=>recordingTick(t));
    }
    function newMix(offset){return {offset,abort:new AbortController(),nodes:[],gains:null,master:null,started:false,end:offset,when:0,warning:'',graphLatency:0};}
    function stopMix(updatePosition){
        playToken++;cancelAnimationFrame(playbackFrame);playbackFrame=0;
        const p=playback;playback=null;
        if(p){
            if(updatePosition&&p.started&&playbackContext)position=Math.min(p.end,Math.max(p.offset,p.offset+audibleTime(playbackContext,p)-p.when));
            p.abort.abort();
            for(const node of p.nodes){try{node.stop();}catch(_){}try{node.disconnect();}catch(_){}}
            for(const chain of Object.values(p.fxChains||{}))chain.disconnect();
            for(const gain of Object.values(p.gains||{})){try{gain.disconnect();}catch(_){}}
            if(p.master)try{p.master.disconnect();}catch(_){}
            if(p.output)try{p.output.disconnect();}catch(_){}
        }
        audio.pause();
    }
    function pause(){stopMix(true);phase='idle';update();}
    function bufferBytes(b){return b.length*b.numberOfChannels*4;}
    function cacheBuffer(key, buffer){
        if(bufferBytes(buffer)>cacheLimit)return;
        decodedCache.delete(key);decodedCache.set(key,buffer);
        let bytes=0;for(const b of decodedCache.values())bytes+=bufferBytes(b);
        while(bytes>cacheLimit && decodedCache.size){const k=decodedCache.keys().next().value;bytes-=bufferBytes(decodedCache.get(k));decodedCache.delete(k);}
    }
    async function loadAudio(c, signal, context){
        const key=c.file+':'+String(c.size||0)+':'+String(c.pcm_bytes||0);
        if(decodedCache.has(key)){const b=decodedCache.get(key);decodedCache.delete(key);decodedCache.set(key,b);return b;}
        const url=endpoint+'&action=play&id='+encodeURIComponent(c.id)+'&v=0.1.14';
        const r=await fetch(url,{credentials:'same-origin',cache:'no-store',signal});
        if(!r.ok){let detail='HTTP '+r.status;try{const d=await r.json();if(d.error)detail=d.error;}catch(_){}throw Error(detail);}
        const type=(r.headers.get('Content-Type')||'').toLowerCase();
        if(!type.startsWith('audio/') && !type.startsWith('application/octet-stream'))throw Error('El hosting no devolvió un archivo de audio.');
        const data=await r.arrayBuffer();
        if(!data.byteLength || (c.mime==='audio/wav' && data.byteLength<=44))throw Error('El archivo guardado no contiene muestras de audio.');
        if(signal.aborted)throw new DOMException('Cancelado','AbortError');
        const buffer=await context.decodeAudioData(data);
        if(!buffer.length || !buffer.duration)throw Error('El audio no tiene duración.');
        if(signal.aborted)throw new DOMException('Cancelado','AbortError');
        cacheBuffer(key,buffer);return buffer;
    }
    function playbackTick(p){
        if(playback!==p||phase!=='playing')return;
        position=Math.min(p.end,Math.max(p.offset,p.offset+audibleTime(playbackContext,p)-p.when));
        if(position>=p.end-.005){pause();position=p.end;msg(p.warning||'Reproducción finalizada.',p.warning?'error':'ok');update();return;}
        clock.textContent=format(position);
        canvas.setAttribute('aria-valuenow',position.toFixed(2));canvas.setAttribute('aria-valuetext',format(position));draw();
        playbackFrame=requestAnimationFrame(()=>playbackTick(p));
    }
    async function prepareMix(p,context,overdub=false){
        const candidates=clips.filter(c=>hasAudio(c)&&(endAt(c)>p.offset||!duration(c)));
        const results=[],failures=[];let bytes=0;const counted=new Set();
        const timeout=setTimeout(()=>p.abort.abort(),90000);
        try{
            for(const c of candidates){
                if(p.abort.signal.aborted)throw Error('Se interrumpió la carga del audio.');
                try{
                    const b=await loadAudio(c,p.abort.signal,context);
                    if(!counted.has(b)){if(bytes+bufferBytes(b)>playbackLimit)throw Error('La mezcla supera la memoria de reproducción disponible.');bytes+=bufferBytes(b);counted.add(b);}
                    const len=playableDuration(c,b);if(!trimmed(c))c.duration_ms=Math.round(len*1000);
                    if(len>0&&startAt(c)+len>p.offset)results.push({clip:c,buffer:b,len});
                }catch(e){if(p.abort.signal.aborted)throw e;const detail=palette[sanitizeTrack(c.track)].name+': '+e.message;if(overdub&&!isMuted(c.track))throw Error('No se pudo cargar el acompañamiento. '+detail);failures.push(detail);}
                msg((overdub?'Preparando acompañamiento ':'Cargando audio ')+(results.length+failures.length)+' / '+candidates.length+'...');
            }
            if(p.abort.signal.aborted||playback!==p)throw Error('Se interrumpió la carga del audio.');
            if(!overdub&&!results.length)throw Error(failures[0]||'No hay audio reproducible desde esta posición.');
            if(!overdub&&!results.some(x=>!isMuted(x.clip.track)))throw Error('Las pistas con audio reproducible están silenciadas.');
            ensureExtent();p.end=Math.max(p.offset,...results.map(({clip,len})=>startAt(clip)+len));
            p.warning=failures.length?'No se pudieron cargar '+failures.length+' toma(s): '+failures[0]:'';
            if(results.length){
                const workletReady=await window.FutureoFX.prepare(context);
                if(p.abort.signal.aborted||playback!==p)throw Error('Se interrumpió la carga del audio.');
                p.master=context.createDynamicsCompressor();p.output=context.createGain();p.master.connect(p.output);p.output.connect(context.destination);
                p.gains={};p.fxChains={};p.graphLatency=.006;
                for(let t=1;t<=4;t++){const gain=context.createGain();gain.gain.value=isMuted(t)?0:1;gain.connect(p.master);p.gains[t]=gain;const chain=window.FutureoFX.chain(context,gain,workletReady);chain.apply(fxUI.get(t),true);p.fxChains[t]=chain;}
                p.graphLatency+=Math.max(0,...Object.values(p.fxChains).map(chain=>chain.latencySeconds||0));
                if(Object.values(p.fxChains).some((chain,i)=>{const s=fxUI.get(i+1);return s.enabled&&((!chain.worklet&&(s.tune||s.gate||s.deess))||(!chain.leveler&&s.leveler)||(!chain.rhythm&&s.rhythm));}))p.warning=(p.warning?p.warning+' · ':'')+'AudioWorklet no disponible: algunos FX se omitieron.';
            }
            return results;
        }finally{clearTimeout(timeout);}
    }
    function scheduleMix(p,context,results,when){
        p.when=when;p.origin=when-p.offset;
        for(const chain of Object.values(p.fxChains||{}))chain.setTransport(fxUI.getTempo(),p.origin,true);
        for(const {clip,buffer,len} of results){
            const source=context.createBufferSource();source.buffer=buffer;source.connect(p.fxChains[sanitizeTrack(clip.track)].input);p.nodes.push(source);
            const skip=Math.max(0,p.offset-startAt(clip));
            if(skip<len)source.start(when+Math.max(0,startAt(clip)-p.offset),sourceOffset(clip)+skip,len-skip);
        }
        p.started=true;
    }
    async function startPlay(){
        if(phase!=='idle'||activePlayableClips().length<=0)return;
        if(!AudioCtx){msg('El navegador no admite Web Audio.','error');return;}
        if(position>=projectTotal()-.001)position=0;
        const p=newMix(position);const token=++playToken;
        playback=p;phase='playing';msg('Cargando audios guardados en el hosting...');update();
        try{
            if(!playbackContext||playbackContext.state==='closed')playbackContext=new AudioCtx({latencyHint:'interactive'});
            const context=playbackContext;await context.resume();
            if(token!==playToken)return;
            if(context.state!=='running')throw Error('El navegador bloqueó el audio. Pulsa Reproducir nuevamente.');
            const results=await prepareMix(p,context);
            if(token!==playToken)return;
            scheduleMix(p,context,results,context.currentTime+.09);
            msg(p.warning||'Reproduciendo las pistas guardadas.',p.warning?'error':'ok');update();playbackTick(p);
        }catch(e){if(token===playToken){const aborted=p.abort.signal.aborted;pause();msg(aborted?'Se interrumpió la carga del audio. Vuelve a intentarlo.':e.message,'error');}}
    }
    record.addEventListener('click',()=>phase==='recording' ? endTake() : begin());
    stop.addEventListener('click',()=>{ if(phase==='recording') endTake(); else if(phase==='playing') pause(); else if(phase==='calibrating') cancelCalibration(); });
    play.addEventListener('click',()=>{if(phase==='playing'){pause();msg('Reproducción en pausa.');}else startPlay();});
    home.addEventListener('click',()=>{ if(phase==='playing') pause(); move(0); });
    $('retry').addEventListener('click',()=>{ if(phase!=='recovery'||!take) return; take.error = null; phase = 'saving'; msg('Reintentando guardado...'); update(); pump(take); });
    $('discard').addEventListener('click',()=>{ if(phase!=='recovery'||!take||!confirm('¿Cerrar esta toma? Los fragmentos ya guardados se conservarán.')) return; if(take.item&&take.ack>0) clips.push({...take.item, track:take.track, start_ms:Math.round(take.start*1000), duration_ms:take.ack/take.rate/2*1000, peaks:take.peaks.slice(0,Math.ceil(take.ack/take.rate/2*40))}); sortClips(); take = null; phase = 'idle'; position = projectTotal(); if(localUrl) URL.revokeObjectURL(localUrl); localUrl = null; ensureExtent(); msg('Se conservaron los fragmentos confirmados por el servidor.'); update(); });
    window.addEventListener('beforeunload',e=>{ if(take||fxUI.dirty()||['starting','moving','importing'].includes(phase)){ e.preventDefault(); e.returnValue=''; } });
    window.addEventListener('pagehide',()=>{ if(calibration)cancelCalibration(); if(take) release(take); if(playback)stopMix(false); if(playbackContext)playbackContext.close().catch(()=>{}); });
    const fxUI=window.FutureoFX.createUI({post,getPresets:()=>fetch(endpoint+'&action=fx_presets',{credentials:'same-origin',cache:'no-store'}).then(response),
        change(t,s,closed=false){states[t].fx=window.FutureoFX.active(s);if(playback?.fxChains?.[t]){const chain=playback.fxChains[t];chain.apply(s);if(s.enabled&&((!chain.worklet&&(s.tune||s.gate||s.deess))||(!chain.leveler&&s.leveler)||(!chain.rhythm&&s.rhythm)))msg('AudioWorklet no disponible para algunos FX.','error');}if(closed)msg('FX: cambios sin guardar. Abre el panel y pulsa Guardar pista.');update();},
        changeTempo(bpm){if(playback?.fxChains)for(const chain of Object.values(playback.fxChains))chain.setTransport(bpm,playback.origin??0);},
        togglePlay(){if(phase==='playing')pause();else startPlay();},getPlaying:()=>phase==='playing',canPlay:()=>phase==='idle'&&activePlayableClips().length>0});
    load();
})();
