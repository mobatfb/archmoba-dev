/* FUTUREO STUDIO v0.1.19 - server-backed, synchronized audio playback */
(() => {
    const root = document.querySelector('.voice-recorder');
    if (!root) return;
    const $ = id => document.getElementById('voice-' + id);
    const canvas = $('canvas'), ctx = canvas.getContext('2d'), audio = $('audio');
    const record = $('record'), play = $('play'), stop = $('stop'), home = $('home'), clock = $('clock'), status = $('status'), saved = $('saved'), recovery = $('recovery'), download = $('download'), trackName = $('track-name');
    const trackRows = Array.from(document.querySelectorAll('[data-track-row]'));
    const endpoint = 'recordings.php?' + new URLSearchParams({project: root.dataset.project}).toString();
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    const supported = window.isSecureContext && navigator.mediaDevices?.getUserMedia && AudioCtx && window.AudioWorkletNode && window.crypto?.getRandomValues;
    const palette = {1:{accent:'#33d5ff',fill:'#10323e',live:'#123c47',wave:'#32d7e8',liveWave:'#ff6785',name:'Pista 1'},2:{accent:'#c39cff',fill:'#241936',live:'#302140',wave:'#c8a7ff',liveWave:'#ff93d2',name:'Pista 2'},3:{accent:'#ffd166',fill:'#3a2d14',live:'#46361a',wave:'#ffd166',liveWave:'#ffe4a8',name:'Pista 3'},4:{accent:'#76e39a',fill:'#143021',live:'#193b29',wave:'#76e39a',liveWave:'#b6f4c8',name:'Pista 4'}};
    let selectedTrack = 1, clips = [], take = null, phase = 'loading', maxBytes = 0, position = 0, extent = 30, playback = null, playToken = 0, localUrl = null;
    let drag = null, selectedClip = null, seekingPointer = null, tool = 'pointer', editPointer = null, cutPreview = null;
    const toolButtons = Array.from(root.querySelectorAll('.daw-tool[data-tool]'));
    const toolHints = {pointer:'Puntero: selecciona clips o cambia el cursor.',hand:'Mano: arrastra un clip a otra posición o pista.',cut:'Cúter: pulsa dentro de un clip para dividirlo.',erase:'Borrar: pulsa un clip para quitarlo de la línea de tiempo.'};
    function setTool(next){if(!toolHints[next]||!['idle','playing'].includes(phase))return;if(drag)cancelDrag();tool=next;editPointer=null;cutPreview=null;msg(toolHints[tool]);update();}
    toolButtons.forEach(b=>b.addEventListener('click',()=>setTool(b.dataset.tool)));
    let playbackContext = null, playbackFrame = 0;
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
    function ensureExtent(){ extent = Math.max(30, Math.ceil((projectTotal() + 5) / 10) * 10); }
    function update(){
        const live = phase === 'recording', idle = phase === 'idle';
        if (!idle || tool !== 'cut') cutPreview=null;
        record.disabled = !supported || maxBytes < 1024 || !(idle || live);
        record.classList.toggle('is-recording', live);
        record.setAttribute('aria-label', live ? 'Detener grabación' : 'Grabar voz');
        record.title = live ? 'Detener grabación' : 'Grabar voz';
        play.disabled = phase !== 'playing' && (!idle || activePlayableClips().length <= 0);
        play.textContent = phase === 'playing' ? 'Ⅱ' : '▶';
        play.setAttribute('aria-label', phase === 'playing' ? 'Pausar' : 'Reproducir');
        stop.disabled = !['recording','playing'].includes(phase);
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
        draw();
    }
    async function response(r){ let d; try{ d = await r.json(); }catch(_){ throw Error('Respuesta no válida del hosting (' + r.status + ').'); } if(!r.ok || !d.ok) throw Error(d.error || 'Error del servidor'); return d; }
    async function post(action, fields = {}, blob = null){ const f = new FormData(); f.append('action', action); f.append('project', root.dataset.project); f.append('csrf', root.dataset.csrf); for(const [k,v] of Object.entries(fields)) f.append(k, String(v)); if(blob) f.append('pcm', blob, 'pcm.bin'); return response(await fetch('recordings.php', {method:'POST', body:f, credentials:'same-origin', cache:'no-store'})); }
    async function load(){
        try{
            const d = await response(await fetch(endpoint, {cache:'no-store', credentials:'same-origin'}));
            maxBytes = Number(d.max_bytes) || 0;
            clips = normalizeClips(d.recordings || []);
            fxUI.load(d.track_fx,d.tempo_bpm);
            sortClips();
            decodedCache.clear();
            phase = 'idle'; position = 0; ensureExtent();
            msg(!supported ? 'Usa HTTPS y un navegador compatible con AudioWorklet para grabar.' : maxBytes < 1024 ? 'El hosting no admite fragmentos de audio.' : 'Selecciona una herramienta de edición en la barra inferior. REC arma la grabación.');
            update();
            for (const clip of clips) fetchPeaks(clip);
        } catch(e){ phase='idle'; msg(e.message,'error'); update(); }
    }
    function fetchPeaks(clip){if(clip.mime!=='audio/wav')return;fetch(endpoint+'&action=waveform&id='+encodeURIComponent(clip.id),{credentials:'same-origin',cache:'no-store'}).then(response).then(d=>{clip.peaks=d.peaks||[];draw();}).catch(()=>{});}
    async function reconcileEdits(){const d=await response(await fetch(endpoint,{cache:'no-store',credentials:'same-origin'}));clips=normalizeClips(d.recordings||[]);sortClips();selectedClip=null;for(const c of clips)fetchPeaks(c);}
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
    document.addEventListener('keydown',e=>{if(fxUI.isOpen())return;if(e.key==='Escape'){if(drag){e.preventDefault();cancelDrag();}editPointer=null;clearCutPreview();return;}if(e.ctrlKey||e.metaKey||e.altKey||e.target.closest('input,textarea,select,[contenteditable=true]'))return;const modes={v:'pointer',h:'hand',c:'cut',e:'erase'};if(modes[e.key.toLowerCase()]&&['idle','playing'].includes(phase)){e.preventDefault();setTool(modes[e.key.toLowerCase()]);}});
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
    function release(t){ if(t.node){ try{ t.node.disconnect(); }catch(_){} t.node.port.onmessage = null; } if(t.source){ try{ t.source.disconnect(); }catch(_){} } if(t.media) t.media.getTracks().forEach(x => x.stop()); if(t.context) t.context.close().catch(()=>{}); }
    function capture(t, buffer, peaks){ if(t !== take || !['recording','stopping'].includes(phase)) return; const available = Math.max(0, t.rate * 2 * 600 - t.captured); const bytes = buffer.byteLength > available ? buffer.slice(0, available) : buffer; if(bytes.byteLength){ const offset = t.captured; t.captured += bytes.byteLength; t.raw.push(bytes); t.peaks.push(...peaks); const block = Math.max(2, Math.min(1048576, maxBytes) & ~1); for(let i=0;i<bytes.byteLength;i+=block) t.queue.push({offset:offset+i, buffer:bytes.slice(i, i+block)}); position = t.start + t.captured / t.rate / 2; ensureExtent(); update(); pump(t); } if(t.captured >= t.rate * 2 * 600 && phase==='recording') endTake(); }
    async function pump(t){ if(t.pumping || t.error || t !== take) return; t.pumping = true; try{ while(t.queue.length){ const q = t.queue[0]; const d = await post('stream_chunk', {recording_id:t.id, offset:q.offset}, new Blob([q.buffer], {type:'application/octet-stream'})); if(Number(d.pcm_bytes) < q.offset + q.buffer.byteLength) throw Error('El servidor no confirmó el fragmento.'); t.ack = Number(d.pcm_bytes); t.item = d.recording; t.queue.shift(); update(); } }catch(e){ t.error = e.message; if(phase==='recording') endTake(); } finally { t.pumping = false; if(t.ended) finalize(t); } }
    function makeDownload(t){ if(localUrl) URL.revokeObjectURL(localUrl); const h = new ArrayBuffer(44), v = new DataView(h); const str = (off,s)=>{for(let i=0;i<s.length;i++)v.setUint8(off+i,s.charCodeAt(i));}; str(0,'RIFF'); v.setUint32(4,36+t.captured,true); str(8,'WAVEfmt '); v.setUint32(16,16,true); v.setUint16(20,1,true); v.setUint16(22,1,true); v.setUint32(24,t.rate,true); v.setUint32(28,t.rate*2,true); v.setUint16(32,2,true); v.setUint16(34,16,true); str(36,'data'); v.setUint32(40,t.captured,true); localUrl = URL.createObjectURL(new Blob([h,...t.raw], {type:'audio/wav'})); download.href = localUrl; download.download = 'voz_' + t.id + '.wav'; }
    function recover(t){ phase = 'recovery'; makeDownload(t); msg((t.error || 'No se pudo confirmar el guardado.') + ' · ' + format(t.ack/t.rate/2) + ' guardados en ' + palette[t.track].name + '.', 'error'); update(); }
    async function finalize(t){ if(t!==take||!t.ended||t.pumping||t.finalizing) return; if(t.error){ recover(t); return; } if(t.queue.length){ pump(t); return; } t.finalizing = true; phase = 'saving'; update(); try{ const d = await post('stream_finish', {recording_id:t.id, offset:t.ack}); clips.push({...d.recording, peaks:t.peaks, track:sanitizeTrack(d.recording.track || t.track), start_ms:Number(d.recording.start_ms ?? Math.round(t.start*1000))}); sortClips(); position = endAt(clips[clips.length-1]); take = null; phase = 'idle'; if(localUrl) URL.revokeObjectURL(localUrl); localUrl = null; ensureExtent(); msg('Grabación WAV guardada en assets del proyecto, en ' + palette[selectedTrack].name + '.', 'ok'); update(); }catch(e){ t.error = e.message; recover(t); } finally { t.finalizing = false; } }
    function endTake(){ const t = take; if(!t || phase!=='recording') return; phase = 'stopping'; msg('Guardando los últimos fragmentos...'); update(); t.node.port.postMessage('stop'); t.stopTimeout = setTimeout(()=>{ if(!t.ended){ t.error = t.error || 'No se confirmó el último bloque del micrófono.'; t.ended = true; release(t); finalize(t); } },2000); }
    async function begin(){ if(phase!=='idle'||!supported) return; phase = 'starting'; msg('Solicitando acceso al micrófono...'); update(); const t = {id:Array.from(crypto.getRandomValues(new Uint8Array(12)),x=>x.toString(16).padStart(2,'0')).join(''), track:selectedTrack, start:position, raw:[], queue:[], peaks:[], captured:0, ack:0, rate:48000, error:null, pumping:false, ended:false, finalizing:false}; try{ t.media = await navigator.mediaDevices.getUserMedia({audio:{channelCount:1},video:false}); t.context = new AudioCtx(); await t.context.resume(); t.rate = t.context.sampleRate; await t.context.audioWorklet.addModule('assets/pcm-worklet.js?v=0.1.8'); t.source = t.context.createMediaStreamSource(t.media); t.node = new AudioWorkletNode(t.context,'futureo-pcm',{numberOfInputs:1,numberOfOutputs:1,outputChannelCount:[1]}); const d = await post('stream_start',{recording_id:t.id,sample_rate:t.rate,track:t.track,start_ms:Math.round(t.start*1000)}); t.item = d.recording; take = t; phase='recording'; msg('Grabando en ' + palette[t.track].name + ' · guardado automático cada 0,5 s'); t.node.port.onmessage = e => { if(e.data.type==='pcm') capture(t,e.data.buffer,e.data.peaks); else if(e.data.type==='stopped'){ clearTimeout(t.stopTimeout); t.ended=true; release(t); finalize(t); } }; t.media.getAudioTracks().forEach(tr=>tr.addEventListener('ended',()=>{ if(t===take&&phase==='recording') endTake(); })); t.source.connect(t.node); t.node.connect(t.context.destination); update(); } catch(e){ release(t); take=null; phase='idle'; msg(e.name==='NotAllowedError' ? 'Autoriza el micrófono en el navegador.' : e.message, 'error'); update(); } }
    function pause(){
        playToken++; cancelAnimationFrame(playbackFrame); playbackFrame=0;
        const p=playback; playback=null;
        if(p){
            if(p.started && playbackContext) position=Math.min(p.end,Math.max(p.offset,p.offset+playbackContext.currentTime-p.when));
            p.abort.abort();
            for(const node of p.nodes){try{node.stop();}catch(_){} try{node.disconnect();}catch(_){}}
            for(const chain of Object.values(p.fxChains || {}))chain.disconnect();
            for(const gain of Object.values(p.gains || {})){try{gain.disconnect();}catch(_){}}
            if(p.master)try{p.master.disconnect();}catch(_){}
        }
        audio.pause(); phase='idle'; update();
    }
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
        position=Math.min(p.end,Math.max(p.offset,p.offset+playbackContext.currentTime-p.when));
        if(position>=p.end-.005){pause();position=p.end;msg(p.warning||'Reproducción finalizada.',p.warning?'error':'ok');update();return;}
        clock.textContent=format(position);
        canvas.setAttribute('aria-valuenow',position.toFixed(2));canvas.setAttribute('aria-valuetext',format(position));draw();
        playbackFrame=requestAnimationFrame(()=>playbackTick(p));
    }
    async function startPlay(){
        if(phase!=='idle'||activePlayableClips().length<=0)return;
        if(!AudioCtx){msg('El navegador no admite Web Audio.','error');return;}
        if(position>=projectTotal()-.001)position=0;
        const offset=position, token=++playToken;
        const p={offset,abort:new AbortController(),nodes:[],gains:null,master:null,started:false,end:0,when:0,warning:''};
        playback=p;phase='playing';msg('Cargando audios guardados en el hosting...');update();
        let timeout=0;
        try{
            // Unlock the audio context immediately from the user's Play gesture.
            if(!playbackContext||playbackContext.state==='closed')playbackContext=new AudioCtx();
            const context=playbackContext;
            await context.resume();
            if(token!==playToken||p.abort.signal.aborted)return;
            if(context.state!=='running')throw Error('El navegador bloqueó el audio. Pulsa Reproducir nuevamente.');
            const candidates=clips.filter(c=>hasAudio(c)&&(endAt(c)>offset||!duration(c)));
            const results=[];const failures=[];let bytes=0;const counted=new Set();
            timeout=setTimeout(()=>p.abort.abort(),90000);
            // Load real files, including muted tracks so unmuting works during playback.
            for(const c of candidates){
                if(token!==playToken)return;
                try{
                    const b=await loadAudio(c,p.abort.signal,context);
                    if(token!==playToken)return;
                    if(!counted.has(b)){if(bytes+bufferBytes(b)>playbackLimit)throw Error('La mezcla supera la memoria de reproducción disponible; abre un proyecto más corto.');bytes+=bufferBytes(b);counted.add(b);}
                    const len=playableDuration(c,b);if(!trimmed(c))c.duration_ms=Math.round(len*1000);
                    if(len>0&&startAt(c)+len>offset)results.push({clip:c,buffer:b,len});
                }catch(e){if(p.abort.signal.aborted)throw e;failures.push(palette[sanitizeTrack(c.track)].name+': '+e.message);}
                msg('Cargando audio '+(results.length+failures.length)+' / '+candidates.length+'...');
            }
            clearTimeout(timeout);timeout=0;
            if(token!==playToken)return;
            if(!results.length)throw Error(failures[0]||'No hay audio reproducible desde esta posición.');
            if(!results.some(x=>!isMuted(x.clip.track)))throw Error('Las pistas con audio reproducible están silenciadas.');
            ensureExtent();
            p.end=Math.max(...results.map(({clip,len})=>startAt(clip)+len));
            p.master=context.createDynamicsCompressor();p.master.connect(context.destination);
            const workletReady=await window.FutureoFX.prepare(context);
            if(token!==playToken||p.abort.signal.aborted)return;
            p.gains={};p.fxChains={};for(let t=1;t<=4;t++){const gain=context.createGain();gain.gain.value=isMuted(t)?0:1;gain.connect(p.master);p.gains[t]=gain;const chain=window.FutureoFX.chain(context,gain,workletReady);chain.apply(fxUI.get(t),true);p.fxChains[t]=chain;}
            p.when=context.currentTime+.09;
            p.origin=p.when-offset;for(const chain of Object.values(p.fxChains))chain.setTransport(fxUI.getTempo(),p.origin,true);
            for(const {clip,buffer,len} of results){
                const source=context.createBufferSource();source.buffer=buffer;source.connect(p.fxChains[sanitizeTrack(clip.track)].input);p.nodes.push(source);
                const skip=Math.max(0,offset-startAt(clip));
                if(skip<len)source.start(p.when+Math.max(0,startAt(clip)-offset),sourceOffset(clip)+skip,len-skip);
            }
            p.started=true;p.warning=failures.length?'No se pudieron cargar '+failures.length+' toma(s): '+failures[0]:'';
            if(Object.values(p.fxChains).some((chain,i)=>{const s=fxUI.get(i+1);return s.enabled&&((!chain.worklet&&(s.tune||s.gate||s.deess))||(!chain.leveler&&s.leveler)||(!chain.rhythm&&s.rhythm));}))p.warning=(p.warning?p.warning+' · ':'')+'AudioWorklet no disponible: algunos FX (afinación, Gate, De-Esser, Nivelador o Rhythm) se omitieron.';
            msg(p.warning||'Reproduciendo las pistas guardadas.',p.warning?'error':'ok');update();playbackTick(p);
        }catch(e){if(token===playToken){const aborted=p.abort.signal.aborted;pause();msg(aborted?'Se interrumpió la carga del audio. Vuelve a intentarlo.':e.message,'error');}}
        finally{if(timeout)clearTimeout(timeout);}
    }
    record.addEventListener('click',()=>phase==='recording' ? endTake() : begin());
    stop.addEventListener('click',()=>{ if(phase==='recording') endTake(); else if(phase==='playing') pause(); });
    play.addEventListener('click',()=>{if(phase==='playing'){pause();msg('Reproducción en pausa.');}else startPlay();});
    home.addEventListener('click',()=>{ if(phase==='playing') pause(); move(0); });
    $('retry').addEventListener('click',()=>{ if(phase!=='recovery'||!take) return; take.error = null; phase = 'saving'; msg('Reintentando guardado...'); update(); pump(take); });
    $('discard').addEventListener('click',()=>{ if(phase!=='recovery'||!take||!confirm('¿Cerrar esta toma? Los fragmentos ya guardados se conservarán.')) return; if(take.item&&take.ack>0) clips.push({...take.item, track:take.track, start_ms:Math.round(take.start*1000), duration_ms:take.ack/take.rate/2*1000, peaks:take.peaks.slice(0,Math.ceil(take.ack/take.rate/2*40))}); sortClips(); take = null; phase = 'idle'; position = projectTotal(); if(localUrl) URL.revokeObjectURL(localUrl); localUrl = null; ensureExtent(); msg('Se conservaron los fragmentos confirmados por el servidor.'); update(); });
    window.addEventListener('beforeunload',e=>{ if(take||fxUI.dirty()||['starting','moving'].includes(phase)){ e.preventDefault(); e.returnValue=''; } });
    window.addEventListener('pagehide',()=>{ if(take) release(take); if(playback)pause(); if(playbackContext)playbackContext.close().catch(()=>{}); });
    const fxUI=window.FutureoFX.createUI({post,getPresets:()=>fetch(endpoint+'&action=fx_presets',{credentials:'same-origin',cache:'no-store'}).then(response),
        change(t,s,closed=false){states[t].fx=window.FutureoFX.active(s);if(playback?.fxChains?.[t]){const chain=playback.fxChains[t];chain.apply(s);if(s.enabled&&((!chain.worklet&&(s.tune||s.gate||s.deess))||(!chain.leveler&&s.leveler)||(!chain.rhythm&&s.rhythm)))msg('AudioWorklet no disponible para algunos FX.','error');}if(closed)msg('FX: cambios sin guardar. Abre el panel y pulsa Guardar pista.');update();},
        changeTempo(bpm){if(playback?.fxChains)for(const chain of Object.values(playback.fxChains))chain.setTransport(bpm,playback.origin??0);},
        togglePlay(){if(phase==='playing')pause();else startPlay();},getPlaying:()=>phase==='playing',canPlay:()=>phase==='idle'&&activePlayableClips().length>0});
    load();
})();
