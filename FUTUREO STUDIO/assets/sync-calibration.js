/* FUTUREO STUDIO v0.1.25 - acoustic round-trip measurement, local to this browser. */
(() => {
    'use strict';
    const MAX_LAG=.75, KEY='futureo.sync.acoustic.v1', MAX_AGE=30*86400000;
    const memory=new Map();
    const median=a=>{const b=[...a].sort((x,y)=>x-y),m=b.length>>1;return b.length%2?b[m]:(b[m-1]+b[m])/2;};
    const rateOK=r=>Number.isFinite(r)&&r>=8000&&r<=192000;
    function plan(rate){
        if(!rateOK(rate))throw Error('Frecuencia de muestreo no compatible con la calibración.');
        const n=Math.round(rate*.028),pulse=new Float32Array(n);
        // A short windowed sweep has a sharply localized correlation peak.
        for(let i=0;i<n;i++){const t=i/rate,window=Math.sin(Math.PI*i/(n-1))**2;pulse[i]=.18*window*Math.sin(2*Math.PI*(650*t+(.5*(2900-650)/(.028))*t*t));}
        const offsets=[.12,1.12,2.12,3.12].map(s=>Math.round(s*rate));
        const maxLag=Math.round(MAX_LAG*rate);
        return {pulse,offsets,maxLag,length:offsets[3]+maxLag+n+Math.round(.06*rate)};
    }
    function down(a,f){const out=new Float32Array(Math.floor(a.length/f));for(let i=0;i<out.length;i++){let s=0;for(let j=0;j<f;j++)s+=a[i*f+j];out[i]=s/f;}return out;}
    function energyPrefix(a){const p=new Float64Array(a.length+1);for(let i=0;i<a.length;i++)p[i+1]=p[i]+a[i]*a[i];return p;}
    function rms(a,start,n){let e=0;for(let i=start;i<start+n;i++)e+=a[i]*a[i];return Math.sqrt(e/n);}
    function corr(a,b,start,be,ae,minRms){if(start<0||start+b.length>a.length)return 0;const e=ae[start+b.length]-ae[start];if(e<minRms*minRms*b.length||e<=0)return 0;let cross=0;for(let i=0;i<b.length;i++)cross+=a[start+i]*b[i];return Math.min(1,Math.abs(cross)/Math.sqrt(e*be));}
    function analyze(samples,rate,p=plan(rate)){
        if(!(samples instanceof Float32Array)||samples.length!==p.length)throw Error('La captura de calibración no está completa.');
        let clipped=0;for(const v of samples){if(!Number.isFinite(v))throw Error('La captura de calibración no es válida.');if(Math.abs(v)>=.995)clipped++;}
        if(clipped>samples.length*.001)throw Error('La señal está saturada. Baja el volumen y repite la calibración.');
        const noise=rms(samples,0,Math.round(.08*rate));
        const minRms=Math.max(.0002,noise*2.2);
        const f=Math.max(1,Math.floor(rate/8000)),a=down(samples,f),b=down(p.pulse,f),ae=energyPrefix(a),be=energyPrefix(b)[b.length];
        const fullAE=energyPrefix(samples),fullBE=energyPrefix(p.pulse)[p.pulse.length];
        const limit=Math.ceil(p.maxLag/f),tol=Math.max(2,Math.round(rate*.0025));
        const sets=p.offsets.map(offset=>{
            const base=Math.round(offset/f),scores=new Float32Array(limit+1);let best=0;
            for(let j=0;j<=limit;j++){scores[j]=corr(a,b,base+j,be,ae,minRms*.7);best=Math.max(best,scores[j]);}
            if(best<.34)return [];
            const candidates=[];
            for(let j=0;j<=limit;j++)if(scores[j]>=Math.max(.34,best*.68)&&scores[j]>=(scores[j-1]||0)&&scores[j]>=(scores[j+1]||0))candidates.push({j,s:scores[j]});
            candidates.sort((x,y)=>y.s-x.s);
            const refined=[];
            for(const {j} of candidates.slice(0,20)){
                const approximate=(base+j)*f-offset;let score=0,lag=-1;
                for(let k=Math.max(0,approximate-2*f);k<=Math.min(p.maxLag,approximate+2*f);k++){
                    const v=corr(samples,p.pulse,offset+k,fullBE,fullAE,minRms);if(v>score){score=v;lag=k;}
                }
                if(score>=.32&&lag>=0&&!refined.some(x=>Math.abs(x.lag-lag)<=2))refined.push({lag,score});
            }
            return refined;
        });
        // Require repeated evidence. Reflections far from the direct arrival must not win
        // solely because a single reflected pulse happens to be louder.
        const groups=[];
        for(const anchor of sets.flat()){
            const matched=sets.map(set=>set.filter(x=>Math.abs(x.lag-anchor.lag)<=tol).sort((a,b)=>b.score-a.score)[0]).filter(Boolean);
            if(matched.length<3)continue;
            const lags=matched.map(x=>x.lag),spread=Math.max(...lags)-Math.min(...lags);
            if(spread>tol)continue;
            const score=median(matched.map(x=>x.score));if(score<.36)continue;
            groups.push({frames:Math.round(median(lags)),score,count:matched.length,spread});
        }
        if(!groups.length)throw Error('No se detectaron al menos tres pulsos coherentes. Acerca el micrófono a la salida de audio, revisa el volumen y repite.');
        groups.sort((a,b)=>b.count-a.count||b.score-a.score);
        const top=groups[0];
        // Prefer a comparably strong earlier arrival over a later echo. Do not select
        // an earlier correlation sidelobe inside the same arrival cluster.
        const viable=groups.filter(g=>g.count===top.count&&g.score>=top.score*.85&&g.frames<top.frames-tol).sort((a,b)=>a.frames-b.frames);
        const result=viable[0]||top;
        return {seconds:result.frames/rate,frames:result.frames,matches:result.count,spreadMs:result.spread/rate*1000,score:result.score};
    }
    async function route(context,media){
        const track=media.getAudioTracks()[0];if(!track||track.readyState==='ended')throw Error('El micrófono no está disponible.');
        const s=track.getSettings?.()||{};let outputs=[];
        try{outputs=(await navigator.mediaDevices.enumerateDevices()).filter(d=>d.kind==='audiooutput').map(d=>[d.deviceId,d.groupId,d.label]).sort((a,b)=>JSON.stringify(a).localeCompare(JSON.stringify(b)));}catch(_){}
        const sink=typeof context.sinkId==='string'?context.sinkId:'';
        const key=JSON.stringify([s.deviceId||'',s.groupId||'',track.label||'',s.sampleRate||0,s.channelCount||0,s.echoCancellation??null,s.noiseSuppression??null,s.autoGainControl??null,context.sampleRate,sink,outputs]);
        // Do not reuse a persistent result across reloads when the device cannot be identified.
        return {key,persistent:!!s.deviceId&&outputs.some(d=>d[0]||d[2])};
    }
    function readStored(){try{const a=JSON.parse(localStorage.getItem(KEY)||'[]');return Array.isArray(a)?a:[];}catch(_){return [];}}
    function valid(x){return x&&Number.isFinite(x.seconds)&&x.seconds>=0&&x.seconds<=MAX_LAG&&Number.isInteger(x.matches)&&x.matches>=3&&x.matches<=4&&Number.isFinite(x.score)&&x.score>=.36&&x.score<=1&&Number.isFinite(x.spreadMs)&&x.spreadMs>=0&&x.spreadMs<=2.5&&Number.isFinite(x.at)&&Date.now()>=x.at&&Date.now()-x.at<MAX_AGE;}
    function lookup(r){const m=memory.get(r.key);if(valid(m))return m;if(r.persistent){const x=readStored().find(x=>x.key===r.key&&valid(x));if(x){memory.set(r.key,x);return x;}}return null;}
    function forget(r){memory.delete(r.key);if(r.persistent)try{localStorage.setItem(KEY,JSON.stringify(readStored().filter(x=>x.key!==r.key)));}catch(_){} }
    function save(r,result){const item={key:r.key,seconds:result.seconds,matches:result.matches,spreadMs:result.spreadMs,score:result.score,at:Date.now()};if(!valid(item))throw Error('La medición de latencia no es confiable.');memory.set(r.key,item);if(r.persistent)try{localStorage.setItem(KEY,JSON.stringify([item,...readStored().filter(x=>x.key!==r.key&&valid(x))].slice(0,12)));}catch(_){}return item;}
    async function measure(context,media,signal,onStage=()=>{}){
        if(signal.aborted)throw Error('Calibración cancelada.');
        await context.audioWorklet.addModule('assets/sync-worklet.js?v=0.1.25');
        if(signal.aborted||context.state!=='running')throw Error('Calibración cancelada o audio suspendido.');
        const rate=context.sampleRate,p=plan(rate);let node,input;const sources=[];
        try{
            input=context.createMediaStreamSource(media);
            const first=Math.ceil(context.currentTime*rate)+Math.ceil(.40*rate),end=first+p.length;
            node=new AudioWorkletNode(context,'futureo-sync-capture',{numberOfInputs:1,numberOfOutputs:1,outputChannelCount:[1],processorOptions:{startFrame:first,endFrame:end}});
            const samples=await new Promise((resolve,reject)=>{
                let done=false,timer;
                const finish=(err,data)=>{if(done)return;done=true;clearTimeout(timer);signal.removeEventListener('abort',abort);node.port.onmessage=null;node.onprocessorerror=null;err?reject(err):resolve(data);};
                const abort=()=>finish(Error('Calibración cancelada.'));
                signal.addEventListener('abort',abort,{once:true});
                node.onprocessorerror=()=>finish(Error('Se interrumpió el procesador de calibración.'));
                node.port.onmessage=e=>{
                    const d=e.data;
                    if(d.type==='error'){finish(Error(d.reason));return;}
                    if(d.type==='ready'){
                        if(context.currentTime>(first/rate)-.04){finish(Error('El motor no estuvo listo a tiempo. Repite la prueba.'));return;}
                        try{const buffer=context.createBuffer(1,p.pulse.length,rate);buffer.copyToChannel(p.pulse,0);for(const offset of p.offsets){const source=context.createBufferSource();source.buffer=buffer;source.connect(context.destination);sources.push(source);source.start((first+offset)/rate);}onStage('Escuchando cuatro pulsos… Mantén silencio.');}catch(err){finish(err);}
                    }else if(d.type==='samples'){
                        if(d.startFrame!==first||d.endFrame!==end||!(d.buffer instanceof ArrayBuffer)||d.buffer.byteLength!==p.length*4){finish(Error('El reloj de calibración no coincide.'));return;}
                        finish(null,new Float32Array(d.buffer));
                    }
                };
                timer=setTimeout(()=>finish(Error('No se pudo completar la calibración. Revisa el micrófono y vuelve a intentarlo.')),9000);
                if(signal.aborted){abort();return;}
                input.connect(node);node.connect(context.destination);
            });
            if(signal.aborted)throw Error('Calibración cancelada.');
            onStage('Analizando los pulsos…');return analyze(samples,rate,p);
        }finally{for(const source of sources){try{source.stop();}catch(_){}try{source.disconnect();}catch(_){}}try{node?.disconnect();node?.port.close();}catch(_){}try{input?.disconnect();}catch(_){} }
    }
    window.FutureoSync={plan,analyze,route,lookup,save,forget,measure,MAX_LAG};
})();
