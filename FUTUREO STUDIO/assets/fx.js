/* FUTUREO STUDIO v0.1.17: per-track real-time playback FX and reusable hosting presets. */
(() => {
    'use strict';
    const defaults=()=>({enabled:true,tune:false,tuneAmount:70,key:0,scale:'chromatic',gate:false,threshold:-45,deess:false,deessAmount:45,eq:false,low:0,mid:0,high:0,comp:false,compAmount:45,reverb:false,reverbMix:20,delay:false,delayMix:15,delayTime:280});
    const effects=['tune','gate','deess','eq','comp','reverb','delay'];
    const active=s=>s.enabled&&effects.some(k=>s[k]);
    const factory=[
        {name:'Voz natural',settings:defaults()},
        {name:'Voz profesional',settings:{...defaults(),gate:true,deess:true,eq:true,low:-2,mid:1,high:3,comp:true,compAmount:45,reverb:true,reverbMix:10}},
        {name:'Trap / Reggaetón',settings:{...defaults(),tune:true,tuneAmount:100,gate:true,deess:true,comp:true,compAmount:58,eq:true,low:-2,high:3,reverb:true,reverbMix:18,delay:true,delayMix:12}},
        {name:'Voz de radio',settings:{...defaults(),eq:true,low:-12,mid:7,high:-9,comp:true,compAmount:75,deess:true}},
        {name:'Voz ambiental',settings:{...defaults(),comp:true,reverb:true,reverbMix:50,delay:true,delayMix:30,delayTime:440}}
    ];
    const modules=new WeakMap(), impulses=new WeakMap();
    async function prepare(context){
        if(!context.audioWorklet||!window.AudioWorkletNode)return false;
        if(!modules.has(context))modules.set(context,context.audioWorklet.addModule('assets/fx-worklet.js?v=0.1.17').then(()=>true).catch(()=>false));
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
        mixed.connect(output);
        const verb=own(context.createConvolver()),verbWet=gain();verb.buffer=impulse(context);mixed.connect(verb);verb.connect(verbWet);verbWet.connect(output);
        const delay=own(context.createDelay(1)),feedback=gain(),delayWet=gain();mixed.connect(delay);delay.connect(feedback);feedback.connect(delay);delay.connect(delayWet);delayWet.connect(output);output.connect(destination);
        function param(p,v){if(p)p.setTargetAtTime(v,context.currentTime,.012);}
        function apply(s,instant=false){
            const put=(p,v)=>{if(!p)return;if(instant)p.value=v;else param(p,v);};const on=k=>s.enabled&&s[k];
            if(voice){const q=(k,v)=>put(voice.parameters.get(k),v);q('gate',on('gate')?1:0);q('threshold',s.threshold);q('deess',on('deess')?s.deessAmount/100:0);q('tune',on('tune')?s.tuneAmount/100:0);q('key',s.key);q('scale',['chromatic','major','minor'].indexOf(s.scale));}
            put(low.gain,on('eq')?s.low:0);put(mid.gain,on('eq')?s.mid:0);put(high.gain,on('eq')?s.high:0);
            put(comp.threshold,-8-s.compAmount*.32);put(comp.ratio,1+s.compAmount*.075);put(compWet.gain,on('comp')?1:0);put(compDry.gain,on('comp')?0:1);
            put(verbWet.gain,on('reverb')?s.reverbMix/100:0);put(delay.delayTime,s.delayTime/1000);put(delayWet.gain,on('delay')?s.delayMix/100:0);put(feedback.gain,on('delay')?.32:0);
        }
        apply(defaults(),true);
        return {input,apply,worklet:!!voice,disconnect(){for(const n of nodes){try{n.disconnect();}catch(_){}}}};
    }
    const schema=[
        ['tune','Afinación automática (AutoTune básico)',[['tuneAmount','Intensidad',0,100,'%'],['key','Tonalidad',['Do','Do♯','Re','Re♯','Mi','Fa','Fa♯','Sol','Sol♯','La','La♯','Si']],['scale','Escala',[['chromatic','Cromática'],['major','Mayor'],['minor','Menor']]]]],
        ['gate','Noise Gate',[['threshold','Umbral',-70,-25,' dB']]],
        ['deess','De-Esser',[['deessAmount','Intensidad',0,100,'%']]],
        ['eq','Equalizer (EQ)',[['low','Graves',-12,12,' dB'],['mid','Medios',-12,12,' dB'],['high','Agudos',-12,12,' dB']]],
        ['comp','Compressor',[['compAmount','Compresión',0,100,'%']]],
        ['reverb','Reverb',[['reverbMix','Mezcla',0,60,'%']]],
        ['delay','Delay',[['delayMix','Mezcla',0,50,'%'],['delayTime','Tiempo',80,800,' ms']]]
    ];
    function createUI({post,getPresets,change,togglePlay,getPlaying,canPlay}){
        const settings={1:defaults(),2:defaults(),3:defaults(),4:defaults()},dirty=new Set();let track=1,presets=[],busy=false,loading=false;
        const dialog=document.createElement('dialog');dialog.className='futureo-fx';dialog.setAttribute('aria-labelledby','fx-title');
        dialog.innerHTML='<header class="fx-head"><h2 id="fx-title">FUTUREO FX</h2><label class="fx-bypass"><input type="checkbox" data-fx="enabled"> FX activos</label><button type="button" data-act="close" aria-label="Cerrar efectos">✕</button></header><div class="fx-body"><div class="fx-presets"><label for="fx-preset">Biblioteca de presets</label><div class="fx-line"><select id="fx-preset"></select><button type="button" data-act="load">Cargar</button></div><div class="fx-line"><input id="fx-name" maxlength="60" placeholder="Nombre de mi preset" aria-label="Nombre del nuevo preset"><button type="button" class="fx-primary" data-act="preset">Guardar preset</button></div><p class="fx-hint">Los presets se comparten entre todos los proyectos del hosting.</p></div><div class="fx-units"></div><p class="fx-hint">Afinación experimental para voz monofónica; Gate y De-Esser requieren AudioWorklet. Los efectos se escuchan al reproducir y no modifican los WAV originales.</p></div><footer class="fx-bottom"><button type="button" class="fx-play" data-act="play">▶ Escuchar mezcla</button><button type="button" data-act="reset">Restablecer</button><button type="button" class="fx-primary" data-act="save">Guardar pista</button><p class="fx-status" role="status" aria-live="polite"></p></footer>';
        const q=s=>dialog.querySelector(s), units=q('.fx-units'),info=q('.fx-status'), name=q('#fx-name'), selection=q('#fx-preset');
        for(const [key,title,fields] of schema){
            const box=document.createElement('section');box.className='fx-unit';box.innerHTML=`<label class="fx-unit-title">${title}<input type="checkbox" class="fx-toggle" data-fx="${key}" aria-label="Activar ${title}"></label><div class="fx-fields"></div>`;const group=box.querySelector('.fx-fields');
            for(const [field,label,min,max,suffix] of fields){const row=document.createElement('label');const span=document.createElement('span');span.textContent=label;row.append(span);let control;
                if(Array.isArray(min)){row.className='fx-select';control=document.createElement('select');min.forEach((option,i)=>{const item=document.createElement('option');item.value=Array.isArray(option)?option[0]:String(i);item.textContent=Array.isArray(option)?option[1]:option;control.append(item);});row.append(control);}
                else{control=document.createElement('input');control.type='range';control.min=min;control.max=max;control.step=1;const out=document.createElement('output');out.dataset.output=field;out.dataset.suffix=suffix||'';row.append(control,out);}
                control.dataset.fx=field;group.append(row);
            }units.append(box);
        }
        document.body.append(dialog);
        function note(s,error=false){info.textContent=s;info.dataset.error=String(error);}
        function updatePresets(){const current=selection.value;selection.replaceChildren();for(const [label,items,prefix] of [['Predeterminados',factory,'f'],['Mis presets',presets,'u']]){if(!items.length)continue;const group=document.createElement('optgroup');group.label=label;items.forEach((p,i)=>{const o=document.createElement('option');o.value=prefix+i;o.textContent=p.name;group.append(o);});selection.append(group);}if([...selection.options].some(o=>o.value===current))selection.value=current;}
        function render(){q('#fx-title').textContent='FUTUREO FX · Pista '+track;const s=settings[track];for(const el of dialog.querySelectorAll('[data-fx]')){const k=el.dataset.fx;if(el.type==='checkbox')el.checked=!!s[k];else el.value=s[k];}for(const o of dialog.querySelectorAll('[data-output]'))o.textContent=s[o.dataset.output]+o.dataset.suffix;sync();}
        function sync(){q('[data-act="play"]').textContent=getPlaying()?'Ⅱ Pausar mezcla':'▶ Escuchar mezcla';q('[data-act="play"]').disabled=!canPlay()&&!getPlaying();for(const el of dialog.querySelectorAll('[data-act="save"],[data-act="preset"],[data-act="load"],[data-act="reset"]'))el.disabled=busy;}
        function apply(){dirty.add(track);change(track,settings[track]);render();note('Cambios aplicados a la reproducción. Guarda la pista para conservarlos.');}
        dialog.addEventListener('input',e=>{const k=e.target.dataset.fx;if(!k)return;const el=e.target;settings[track][k]=el.type==='checkbox'?el.checked:k==='scale'?el.value:Number(el.value);dirty.add(track);change(track,settings[track]);for(const o of dialog.querySelectorAll('[data-output]'))o.textContent=settings[track][o.dataset.output]+o.dataset.suffix;note('Cambios sin guardar en el proyecto.');});
        async function refresh(){if(loading)return;loading=true;try{const d=await getPresets();presets=Array.isArray(d.presets)?d.presets:[];updatePresets();}catch(e){note(e.message,true);}finally{loading=false;}}
        async function saveTrack(){const t=track,snapshot=JSON.stringify(settings[t]);const d=await post('save_track_fx',{track:t,settings:snapshot});if(JSON.stringify(settings[t])===snapshot){settings[t]={...defaults(),...d.settings};dirty.delete(t);change(t,settings[t]);render();}return d;}
        dialog.addEventListener('click',async e=>{const action=e.target.closest('[data-act]')?.dataset.act;if(!action)return;
            if(action==='close'){if(!busy)dialog.close();return;}if(action==='play'){togglePlay();return;}if(busy)return;
            if(action==='reset'){settings[track]=defaults();apply();return;}
            if(action==='load'){const value=selection.value,p=(value[0]==='f'?factory:presets)[Number(value.slice(1))];if(!p)return;settings[track]={...defaults(),...p.settings};name.value=value[0]==='u'?p.name:'';apply();note('Preset cargado: '+p.name+'. Guarda la pista para conservarlo.');return;}
            busy=true;sync();try{
                if(action==='save'){await saveTrack();note('Ajustes guardados en el proyecto.');}
                if(action==='preset'){const n=name.value.trim();if(!n)throw Error('Escribe un nombre para el preset.');if(presets.some(p=>p.name===n)&&!confirm('¿Reemplazar el preset «'+n+'»?'))return;const d=await post('save_fx_preset',{name:n,settings:JSON.stringify(settings[track])});presets=d.presets||[];updatePresets();selection.value='u'+presets.findIndex(p=>p.name===n);note('Preset «'+n+'» guardado en el hosting.');}
            }catch(e){note(e.message,true);}finally{busy=false;sync();}
        });
        dialog.addEventListener('cancel',e=>{if(busy)e.preventDefault();});
        dialog.addEventListener('close',()=>{if(dirty.has(track))change(track,settings[track],true);});
        updatePresets();
        return {open(t){if(dialog.open)return;track=t;name.value='';render();note(dirty.has(t)?'Hay cambios sin guardar.':'Ajusta los efectos y escucha la mezcla.');dialog.showModal();refresh();},get(t){return settings[t];},load(raw){for(let t=1;t<=4;t++){settings[t]={...defaults(),...(raw?.[t]||{})};dirty.delete(t);change(t,settings[t]);}},sync,isOpen:()=>dialog.open,dirty:()=>dirty.size>0,active};
    }
    window.FutureoFX={defaults,active,prepare,chain,createUI};
})();
