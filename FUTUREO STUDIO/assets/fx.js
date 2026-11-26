/* FUTUREO STUDIO v0.1.19: per-track real-time playback FX and reusable hosting presets. */
(() => {
    'use strict';
    const defaults=()=>({enabled:true,tune:false,tuneAmount:70,key:0,scale:'chromatic',gate:false,threshold:-45,deess:false,deessAmount:45,eq:false,low:0,mid:0,high:0,comp:false,compAmount:45,leveler:false,levelTarget:-18,levelStrength:85,levelBoost:12,reverb:false,reverbMix:20,delay:false,delayMix:15,delayTime:280,tempoDelay:false,delayDivision:2,rhythm:false,rhythmStyle:"futureo",rhythmPattern:46557,rhythmIntensity:65,rhythmGate:35,rhythmTremolo:15,rhythmRepeat:20,rhythmPan:35});
    const effects=['tune','gate','deess','eq','comp','leveler','reverb','delay','rhythm'];
    const active=s=>s.enabled&&effects.some(k=>s[k]);
    const rhythmStyles={futureo:{bpm:124,pattern:46557},reggaeton:{bpm:95,pattern:54197},trap:{bpm:140,pattern:59849},hiphop:{bpm:90,pattern:22865},electronic:{bpm:128,pattern:21845}};
    const tempoValue=v=>Math.round(Math.max(60,Math.min(180,Number(v)||124)));
    const futureo={...defaults(),tune:true,tuneAmount:72,key:0,scale:'chromatic',gate:true,threshold:-52,deess:true,deessAmount:42,eq:true,low:-3,mid:1,high:3,comp:true,compAmount:48,leveler:true,levelTarget:-19,levelStrength:87,levelBoost:10,reverb:true,reverbMix:22,delay:true,delayMix:17,tempoDelay:true,delayDivision:2,rhythm:true,rhythmStyle:'futureo',rhythmPattern:rhythmStyles.futureo.pattern,rhythmIntensity:62,rhythmGate:30,rhythmTremolo:18,rhythmRepeat:24,rhythmPan:32};
    const factory=[
        {name:'Futureo',settings:futureo,tempo_bpm:124},
        {name:'Voz natural',settings:defaults()},
        {name:'Voz nivelada',settings:{...defaults(),leveler:true,levelStrength:100}},
        {name:'Voz profesional',settings:{...defaults(),gate:true,deess:true,eq:true,low:-2,mid:1,high:3,comp:true,compAmount:45,reverb:true,reverbMix:10}},
        {name:'Trap / Reggaetón',settings:{...defaults(),tune:true,tuneAmount:100,gate:true,deess:true,comp:true,compAmount:58,eq:true,low:-2,high:3,reverb:true,reverbMix:18,delay:true,delayMix:12}},
        {name:'Voz de radio',settings:{...defaults(),eq:true,low:-12,mid:7,high:-9,comp:true,compAmount:75,deess:true}},
        {name:'Voz ambiental',settings:{...defaults(),comp:true,reverb:true,reverbMix:50,delay:true,delayMix:30,delayTime:440}}
    ];
    const modules=new WeakMap(), impulses=new WeakMap();
    async function prepare(context){
        if(!context.audioWorklet||!window.AudioWorkletNode)return false;
        if(!modules.has(context))modules.set(context,context.audioWorklet.addModule('assets/fx-worklet.js?v=0.1.19').then(()=>true).catch(()=>false));
        return modules.get(context);
    }
    function impulse(context){
        if(impulses.has(context))return impulses.get(context);
        const n=Math.round(context.sampleRate*1.7), b=context.createBuffer(2,n,context.sampleRate);let seed=17041;
        for(let ch=0;ch<2;ch++){const d=b.getChannelData(ch);for(let i=0;i<n;i++){seed=(Math.imul(seed,1664525)+1013904223)>>>0;d[i]=(seed/2147483648-1)*Math.pow(1-i/n,3);}}
        impulses.set(context,b);return b;
    }
    function chain(context,destination,workletReady){
        const nodes=[];const own=n=>(nodes.push(n),n),gain=()=>own(context.createGain());
        const input=gain(), output=gain();let prev=input, voice=null;
        if(workletReady){try{voice=own(new AudioWorkletNode(context,'futureo-voice-fx'));prev.connect(voice);prev=voice;}catch(_){voice=null;}}
        const low=own(context.createBiquadFilter()),mid=own(context.createBiquadFilter()),high=own(context.createBiquadFilter());
        low.type='lowshelf';low.frequency.value=180;mid.type='peaking';mid.frequency.value=1300;mid.Q.value=.8;high.type='highshelf';high.frequency.value=4800;
        prev.connect(low);low.connect(mid);mid.connect(high);
        const comp=own(context.createDynamicsCompressor()),compWet=gain(),compDry=gain(),mixed=gain();
        comp.knee.value=18;comp.attack.value=.006;comp.release.value=.13;high.connect(comp);comp.connect(compWet);compWet.connect(mixed);high.connect(compDry);compDry.connect(mixed);
        // One shared leveler per track, after dynamics and before spatial effects.
        let leveler=null, signal=mixed;
        if(workletReady){try{leveler=own(new AudioWorkletNode(context,'futureo-leveler'));mixed.connect(leveler);signal=leveler;}catch(_){leveler=null;}}
        // Shared transport origin keeps the rhythmic DSP locked to the project timeline.
        let rhythm=null;
        if(workletReady){try{rhythm=own(new AudioWorkletNode(context,'futureo-rhythm',{outputChannelCount:[2]}));signal.connect(rhythm);signal=rhythm;}catch(_){rhythm=null;}}
        let tempo=124,origin=0;
        signal.connect(output);
        const verb=own(context.createConvolver()),verbWet=gain();verb.buffer=impulse(context);signal.connect(verb);verb.connect(verbWet);verbWet.connect(output);
        const delay=own(context.createDelay(2)),feedback=gain(),delayWet=gain();signal.connect(delay);delay.connect(feedback);feedback.connect(delay);delay.connect(delayWet);delayWet.connect(output);output.connect(destination);
        function param(p,v){if(p)p.setTargetAtTime(v,context.currentTime,.012);}
        let current=defaults();
        function apply(s,instant=false){
            current={...defaults(),...s};s=current;
            const put=(p,v)=>{if(!p)return;if(instant)p.value=v;else param(p,v);};const on=k=>s.enabled&&s[k];
            if(voice){const q=(k,v)=>put(voice.parameters.get(k),v);q('gate',on('gate')?1:0);q('threshold',s.threshold);q('deess',on('deess')?s.deessAmount/100:0);q('tune',on('tune')?s.tuneAmount/100:0);q('key',s.key);q('scale',['chromatic','major','minor'].indexOf(s.scale));}
            put(low.gain,on('eq')?s.low:0);put(mid.gain,on('eq')?s.mid:0);put(high.gain,on('eq')?s.high:0);
            put(comp.threshold,-8-s.compAmount*.32);put(comp.ratio,1+s.compAmount*.075);put(compWet.gain,on('comp')?1:0);put(compDry.gain,on('comp')?0:1);
            if(leveler){const q=(k,v)=>put(leveler.parameters.get(k),v);q('enabled',on('leveler')?1:0);q('target',s.levelTarget);q('strength',s.levelStrength/100);q('boost',s.levelBoost);}
            if(rhythm){const q=(k,v)=>put(rhythm.parameters.get(k),v);q('enabled',on('rhythm')?1:0);for(const [k,v] of [['bpm',tempo],['origin',origin],['pattern',s.rhythmPattern]]){const p=rhythm.parameters.get(k);p.cancelScheduledValues(context.currentTime);p.setValueAtTime(v,context.currentTime);}q('intensity',s.rhythmIntensity/100);q('gate',s.rhythmGate/100);q('tremolo',s.rhythmTremolo/100);q('repeat',s.rhythmRepeat/100);q('pan',s.rhythmPan/100);}
            const delaySeconds=s.tempoDelay?(60/tempo)*([.25,.5,.75,1][s.delayDivision]||.75):s.delayTime/1000;
            put(verbWet.gain,on('reverb')?s.reverbMix/100:0);put(delay.delayTime,delaySeconds);put(delayWet.gain,on('delay')?s.delayMix/100:0);put(feedback.gain,on('delay')?.32:0);
            // Leave headroom for the dry voice plus spatial returns.
            put(output.gain,s.enabled&&(s.reverb||s.delay)?1/(1+(s.reverb?s.reverbMix:0)/180+(s.delay?s.delayMix:0)/150):1);
        }
        apply(defaults(),true);
        return {input,apply,worklet:!!voice,leveler:!!leveler,rhythm:!!rhythm,setTransport(bpm,start,instant=false){tempo=tempoValue(bpm);origin=Number(start)||0;apply(current,instant);},disconnect(){for(const n of nodes){try{n.disconnect();}catch(_){}}}};
    }
    const schema=[
        ['tune','Afinación automática (AutoTune básico)',[['tuneAmount','Intensidad',0,100,'%'],['key','Tonalidad',['Do','Do♯','Re','Re♯','Mi','Fa','Fa♯','Sol','Sol♯','La','La♯','Si']],['scale','Escala',[['chromatic','Cromática'],['major','Mayor'],['minor','Menor']]]]],
        ['gate','Noise Gate',[['threshold','Umbral',-70,-25,' dB']]],
        ['deess','De-Esser',[['deessAmount','Intensidad',0,100,'%']]],
        ['eq','Equalizer (EQ)',[['low','Graves',-12,12,' dB'],['mid','Medios',-12,12,' dB'],['high','Agudos',-12,12,' dB']]],
        ['comp','Compressor',[['compAmount','Compresión',0,100,'%']]],
        ['leveler','Nivelador automático de volumen',[['levelTarget','Objetivo RMS',-30,-9,' dBFS'],['levelStrength','Intensidad',0,100,'%'],['levelBoost','Refuerzo máximo',0,18,' dB']]],
        ['reverb','Reverb',[['reverbMix','Mezcla',0,60,'%']]],
        ['delay','Delay',[['delayMix','Mezcla',0,50,'%'],['delayTime','Tiempo libre',80,800,' ms'],['delayDivision','División BPM',['1/16','1/8','1/8 con puntillo','1/4']]]],
        ['rhythm','FUTUREO Rhythm',[['rhythmIntensity','Intensidad',0,100,'%'],['rhythmGate','Rhythmic Gate',0,100,'%'],['rhythmTremolo','Tremolo',0,100,'%'],['rhythmRepeat','Beat Repeat / Stutter',0,100,'%'],['rhythmPan','Auto Panner',0,100,'%']]]
    ];
    function createUI({post,getPresets,change,changeTempo,togglePlay,getPlaying,canPlay}){
        const settings={1:defaults(),2:defaults(),3:defaults(),4:defaults()},dirty=new Set();let track=1,presets=[],busy=false,loading=false,tempo=124,tempoDirty=false;
        const dialog=document.createElement('dialog');dialog.className='futureo-fx';dialog.setAttribute('aria-labelledby','fx-title');
        dialog.innerHTML='<header class="fx-head"><h2 id="fx-title">FUTUREO FX</h2><label class="fx-bypass"><input type="checkbox" data-fx="enabled"> FX activos</label><button type="button" data-act="close" aria-label="Cerrar efectos">✕</button></header><div class="fx-body"><div class="fx-presets"><label for="fx-preset">Biblioteca de presets</label><div class="fx-line"><select id="fx-preset"></select><button type="button" data-act="load">Cargar</button></div><div class="fx-line"><input id="fx-name" maxlength="60" placeholder="Nombre de mi preset" aria-label="Nombre del nuevo preset"><button type="button" class="fx-primary" data-act="preset">Guardar preset</button></div><p class="fx-hint">Los presets se comparten entre todos los proyectos del hosting.</p></div><div class="fx-tempo"><label for="fx-bpm">Tempo global del proyecto</label><div class="fx-line"><input type="number" id="fx-bpm" min="60" max="180" step="1" value="124" aria-label="BPM global"><strong>BPM</strong></div><p class="fx-hint">Compartido por las cuatro pistas. Guardar pista conserva también los cambios de tempo.</p></div><div class="fx-units"></div><p class="fx-hint">Afinación experimental para voz monofónica; Gate, De-Esser, Nivelador y Rhythm requieren AudioWorklet. Los efectos se escuchan al reproducir y no modifican los WAV originales.</p></div><footer class="fx-bottom"><button type="button" class="fx-play" data-act="play">▶ Escuchar mezcla</button><button type="button" data-act="reset">Restablecer</button><button type="button" class="fx-primary" data-act="save">Guardar pista</button><p class="fx-status" role="status" aria-live="polite"></p></footer>';
        const q=s=>dialog.querySelector(s), units=q('.fx-units'),info=q('.fx-status'), name=q('#fx-name'), selection=q('#fx-preset');
        for(const [key,title,fields] of schema){
            const box=document.createElement('section');box.className='fx-unit';box.innerHTML=`<label class="fx-unit-title">${title}<input type="checkbox" class="fx-toggle" data-fx="${key}" aria-label="Activar ${title}"></label><div class="fx-fields"></div>`;const group=box.querySelector('.fx-fields');
            for(const [field,label,min,max,suffix] of fields){const row=document.createElement('label');const span=document.createElement('span');span.textContent=label;row.append(span);let control;
                if(Array.isArray(min)){row.className='fx-select';control=document.createElement('select');min.forEach((option,i)=>{const item=document.createElement('option');item.value=Array.isArray(option)?option[0]:String(i);item.textContent=Array.isArray(option)?option[1]:option;control.append(item);});row.append(control);}
                else{control=document.createElement('input');control.type='range';control.min=min;control.max=max;control.step=1;const out=document.createElement('output');out.dataset.output=field;out.dataset.suffix=suffix||'';row.append(control,out);}
                control.dataset.fx=field;group.append(row);
            }if(key==='leveler'){const hint=document.createElement('p');hint.className='fx-hint';hint.textContent='Equilibra todos los clips de la pista, compensa los pasajes fuertes y suaves y limita picos de la señal directa a -1 dBFS. El refuerzo se reduce durante los silencios.';box.append(hint);}
            if(key==='delay'){const sync=document.createElement('label');sync.className='fx-extra';sync.innerHTML='<input type="checkbox" data-fx="tempoDelay"> Sincronizar Delay con BPM';box.append(sync);}
            if(key==='rhythm'){
                const rhythm=document.createElement('div');rhythm.className='fx-rhythm';rhythm.innerHTML='<label for="fx-style">Patrón rítmico</label><select id="fx-style"><option value="futureo">Futureo</option><option value="reggaeton">Reggaetón</option><option value="trap">Trap</option><option value="hiphop">Hip Hop</option><option value="electronic">Electrónica</option><option value="custom">Personalizado</option></select><div class="fx-steps" role="group" aria-label="Secuenciador de 16 pasos"></div><p class="fx-hint">Activa los pasos para crear acentos. Repeat repite fragmentos al final de cada pulso activo. Los estilos ajustan el BPM global.</p>';
                const steps=rhythm.querySelector('.fx-steps');for(let i=0;i<16;i++){const b=document.createElement('button');b.type='button';b.dataset.step=i;b.textContent=i+1;b.setAttribute('aria-label','Paso '+(i+1));b.setAttribute('aria-pressed','false');steps.append(b);}box.append(rhythm);
            }units.append(box);
        }
        document.body.append(dialog);
        function note(s,error=false){info.textContent=s;info.dataset.error=String(error);}
        function updatePresets(){const current=selection.value;selection.replaceChildren();for(const [label,items,prefix] of [['Predeterminados',factory,'f'],['Mis presets',presets,'u']]){if(!items.length)continue;const group=document.createElement('optgroup');group.label=label;items.forEach((p,i)=>{const o=document.createElement('option');o.value=prefix+i;o.textContent=p.name;group.append(o);});selection.append(group);}if([...selection.options].some(o=>o.value===current))selection.value=current;}
        function render(){q('#fx-title').textContent='FUTUREO FX · Pista '+track;const s=settings[track];for(const el of dialog.querySelectorAll('[data-fx]')){const k=el.dataset.fx;if(el.type==='checkbox')el.checked=!!s[k];else el.value=s[k];}for(const o of dialog.querySelectorAll('[data-output]'))o.textContent=s[o.dataset.output]+o.dataset.suffix;q('#fx-bpm').value=tempo;q('#fx-style').value=s.rhythmStyle;for(const b of dialog.querySelectorAll('[data-step]'))b.setAttribute('aria-pressed',String(!!(s.rhythmPattern&(1<<Number(b.dataset.step)))));sync();}
        function sync(){q('[data-act="play"]').textContent=getPlaying()?'Ⅱ Pausar mezcla':'▶ Escuchar mezcla';q('[data-act="play"]').disabled=!canPlay()&&!getPlaying();for(const el of dialog.querySelectorAll('[data-act="save"],[data-act="preset"],[data-act="load"],[data-act="reset"]'))el.disabled=busy;}
        function setTempo(v){const next=tempoValue(v);if(next!==tempo){tempo=next;tempoDirty=true;changeTempo(tempo);}}
        function apply(){dirty.add(track);change(track,settings[track]);render();note('Cambios aplicados a la reproducción. Guarda la pista para conservarlos.');}
        q('#fx-bpm').addEventListener('change',e=>{setTempo(e.target.value);render();note('Tempo global modificado. Guarda la pista para conservarlo.');});
        q('#fx-style').addEventListener('change',e=>{const style=e.target.value;settings[track].rhythmStyle=style;if(rhythmStyles[style]){settings[track].rhythmPattern=rhythmStyles[style].pattern;setTempo(rhythmStyles[style].bpm);}apply();});
        dialog.addEventListener('input',e=>{const k=e.target.dataset.fx;if(!k)return;const el=e.target;settings[track][k]=el.type==='checkbox'?el.checked:k==='scale'?el.value:Number(el.value);dirty.add(track);change(track,settings[track]);for(const o of dialog.querySelectorAll('[data-output]'))o.textContent=settings[track][o.dataset.output]+o.dataset.suffix;note('Cambios sin guardar en el proyecto.');});
        async function refresh(){if(loading)return;loading=true;try{const d=await getPresets();presets=Array.isArray(d.presets)?d.presets:[];updatePresets();}catch(e){note(e.message,true);}finally{loading=false;}}
        async function saveTrack(){const t=track,snapshot=JSON.stringify(settings[t]),bpm=tempo;const fields={track:t,settings:snapshot};if(tempoDirty)fields.tempo_bpm=bpm;const d=await post('save_track_fx',fields);if(tempo===bpm){tempo=tempoValue(d.tempo_bpm??tempo);tempoDirty=false;changeTempo(tempo);}if(JSON.stringify(settings[t])===snapshot){settings[t]={...defaults(),...d.settings};dirty.delete(t);change(t,settings[t]);render();}return d;}
        dialog.addEventListener('click',async e=>{const step=e.target.closest('[data-step]');if(step&&!busy){settings[track].rhythmPattern^=1<<Number(step.dataset.step);settings[track].rhythmStyle='custom';apply();return;}
            const action=e.target.closest('[data-act]')?.dataset.act;if(!action)return;
            if(action==='close'){if(!busy)dialog.close();return;}if(action==='play'){togglePlay();return;}if(busy)return;
            if(action==='reset'){settings[track]=defaults();apply();return;}
            if(action==='load'){const value=selection.value,p=(value[0]==='f'?factory:presets)[Number(value.slice(1))];if(!p)return;settings[track]={...defaults(),...p.settings};if(p.tempo_bpm!=null)setTempo(p.tempo_bpm);name.value=value[0]==='u'?p.name:'';apply();note('Preset cargado: '+p.name+'. Guarda la pista para conservarlo.');return;}
            busy=true;sync();try{
                if(action==='save'){await saveTrack();note('Ajustes guardados en el proyecto.');}
                if(action==='preset'){const n=name.value.trim();if(!n)throw Error('Escribe un nombre para el preset.');if(presets.some(p=>p.name===n)&&!confirm('¿Reemplazar el preset «'+n+'»?'))return;const d=await post('save_fx_preset',{name:n,settings:JSON.stringify(settings[track]),tempo_bpm:tempo});presets=d.presets||[];updatePresets();selection.value='u'+presets.findIndex(p=>p.name===n);note('Preset «'+n+'» guardado en el hosting.');}
            }catch(e){note(e.message,true);}finally{busy=false;sync();}
        });
        dialog.addEventListener('cancel',e=>{if(busy)e.preventDefault();});
        dialog.addEventListener('close',()=>{if(dirty.has(track)||tempoDirty)change(track,settings[track],true);});
        updatePresets();
        return {open(t){if(dialog.open)return;track=t;name.value='';render();note((dirty.has(t)||tempoDirty)?'Hay cambios sin guardar.':'Ajusta los efectos y escucha la mezcla.');dialog.showModal();refresh();},get(t){return settings[t];},getTempo:()=>tempo,load(raw,bpm){tempo=tempoValue(bpm);tempoDirty=false;changeTempo(tempo);for(let t=1;t<=4;t++){settings[t]={...defaults(),...(raw?.[t]||{})};dirty.delete(t);change(t,settings[t]);}},sync,isOpen:()=>dialog.open,dirty:()=>dirty.size>0||tempoDirty,active};
    }
    window.FutureoFX={defaults,active,prepare,chain,createUI};
})();
