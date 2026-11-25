/* FUTUREO STUDIO v0.1.7: real microphone recording, per-project server storage. */
(() => {
    const root = document.querySelector('.voice-recorder');
    if (!root) return;
    const $ = id => document.getElementById('voice-' + id);
    const button = $('record'), clock = $('clock'), caption = $('caption'), status = $('status');
    const recovery = $('recovery'), download = $('download'), list = $('list');
    const query = new URLSearchParams({project:root.dataset.project});
    const endpoint = 'recordings.php?' + query.toString();
    const supported = window.isSecureContext && navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder;
    let stream, recorder, chunks = [], bytes = 0, maxBytes = 0, start = 0, timer, pending = null, objectUrl, busy = false, recording = false;
    let items = [];
    const format = ms => { const s = Math.floor(ms/1000); return String(Math.floor(s/60)).padStart(2,'0') + ':' + String(s%60).padStart(2,'0'); };
    function message(text, state='') { status.textContent=text; status.dataset.state=state; }
    function update() {
        button.disabled = !supported || !maxBytes || busy || !!pending;
        button.classList.toggle('is-recording',recording);
        button.setAttribute('aria-label',recording?'Detener grabación':'Grabar voz');
        caption.textContent=recording?'Detener y guardar':busy?'Procesando...':'Grabar voz';
    }
    function render() {
        list.replaceChildren(); $('count').textContent=String(items.length);
        if (!items.length) { const p=document.createElement('p');p.className='voice-empty';p.textContent='Todavía no hay grabaciones.';list.append(p);return; }
        items.slice().reverse().forEach(item=>{
            const card=document.createElement('article');card.className='voice-item';
            const title=document.createElement('strong');title.textContent=item.file;
            const meta=document.createElement('small');meta.textContent=format(item.duration_ms||0)+' · '+new Date(item.created_at).toLocaleString('es-EC');
            const audio=document.createElement('audio');audio.controls=true;audio.preload='none';audio.src=endpoint+'&action=play&id='+encodeURIComponent(item.id);
            audio.addEventListener('play',()=>list.querySelectorAll('audio').forEach(a=>{if(a!==audio)a.pause();}));
            card.append(title,meta,audio);list.append(card);
        });
    }
    async function jsonResponse(response) {
        let data;try{data=await response.json();}catch(_){throw new Error('El hosting devolvió una respuesta no válida ('+response.status+').');}
        if(!response.ok||!data.ok)throw new Error(data.error||'Error del servidor.');return data;
    }
    async function load() {
        try { const data=await jsonResponse(await fetch(endpoint,{cache:'no-store',credentials:'same-origin'}));items=data.recordings;maxBytes=Number(data.max_bytes)||0;render();
            if(!supported) message('Para grabar necesitas HTTPS y un navegador compatible con el micrófono.','error');
            else if(!maxBytes)message('El hosting no permite cargar archivos de audio.','error');
            else message('Pulsa el micrófono para comenzar.');
        } catch(e){message(e.message,'error');} finally{update();}
    }
    function release() { clearInterval(timer);if(stream)stream.getTracks().forEach(t=>t.stop());stream=null; }
    function stop() { if(recorder && recorder.state==='recording'){recorder.stop();recording=false;busy=true;update();} }
    function clearPending(){if(objectUrl)URL.revokeObjectURL(objectUrl);objectUrl=null;pending=null;recovery.hidden=true;download.removeAttribute('href');}
    async function save(){
        if(!pending||busy)return;busy=true;update();message('Guardando audio en el hosting...');
        const data=new FormData();data.append('action','save');data.append('project',root.dataset.project);data.append('csrf',root.dataset.csrf);data.append('duration_ms',String(pending.duration));data.append('recording_id',pending.id);data.append('audio',pending.blob,pending.filename);
        try{const result=await jsonResponse(await fetch('recordings.php',{method:'POST',body:data,credentials:'same-origin'}));if(!items.some(x=>x.id===result.recording.id))items.push(result.recording);clearPending();render();message('Grabación guardada correctamente.','ok');}
        catch(e){message(e.message+' Puedes reintentar o descargar una copia.','error');recovery.hidden=false;}
        finally{busy=false;update();}
    }
    async function begin(){
        if(busy||pending||recording)return;busy=true;update();message('Solicitando acceso al micrófono...');
        try{
            stream=await navigator.mediaDevices.getUserMedia({audio:true,video:false});
            const types=['audio/webm;codecs=opus','audio/ogg;codecs=opus','audio/mp4','audio/webm'];
            const mime=types.find(t=>MediaRecorder.isTypeSupported(t));
            recorder=new MediaRecorder(stream,mime?{mimeType:mime,audioBitsPerSecond:64000}:{audioBitsPerSecond:64000});
            chunks=[];bytes=0;let failed=false;
            recorder.ondataavailable=e=>{if(e.data.size){chunks.push(e.data);bytes+=e.data.size;if(bytes>=maxBytes*.85)stop();}};
            recorder.onerror=()=>{failed=true;recording=false;busy=false;release();message('No se pudo completar la grabación. Intenta nuevamente.','error');update();};
            recorder.onstop=()=>{
                const duration=Math.min(600000,Math.round(performance.now()-start));release();recording=false;busy=false;clock.textContent=format(duration);
                if(failed){update();return;}
                const type=recorder.mimeType||chunks[0]?.type||mime||'audio/webm';const blob=new Blob(chunks,{type});chunks=[];
                if(!blob.size){message('No se capturó audio.','error');update();return;}
                const extension=type.includes('mp4')?'m4a':type.includes('ogg')?'ogg':'webm';
                const id=Array.from(crypto.getRandomValues(new Uint8Array(12)),n=>n.toString(16).padStart(2,'0')).join('');
                pending={blob,duration,id,filename:'voz.'+extension};objectUrl=URL.createObjectURL(blob);download.href=objectUrl;download.download=pending.filename;
                if(blob.size>maxBytes){message('El audio supera el límite del hosting. Descarga una copia.','error');recovery.hidden=false;update();return;}
                save();
            };
            recorder.start(1000);start=performance.now();recording=true;busy=false;clock.textContent='00:00';message('Grabando voz...');update();
            timer=setInterval(()=>{const elapsed=performance.now()-start;clock.textContent=format(elapsed);if(elapsed>=600000)stop();},200);
        }catch(e){release();recording=false;busy=false;message(e.name==='NotAllowedError'?'Permite el acceso al micrófono en tu navegador.':('No se pudo iniciar el micrófono: '+e.message),'error');update();}
    }
    button.addEventListener('click',()=>recording?stop():begin());
    $('retry').addEventListener('click',save);
    $('discard').addEventListener('click',()=>{if(!busy&&confirm('¿Descartar esta grabación sin guardar?')){clearPending();message('Grabación descartada.');update();}});
    window.addEventListener('beforeunload',e=>{if(recording||pending||busy){e.preventDefault();e.returnValue='';}});
    window.addEventListener('pagehide',release);
    load();
})();
