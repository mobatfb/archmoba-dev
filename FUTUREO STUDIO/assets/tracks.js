/* FUTUREO STUDIO v0.1.6: design preview, no audio engine yet */
(() => {
    const root = document.querySelector('.audio-editor');
    if (!root) return;
    const colors = ['#00dbea', '#d64aff', '#ffc914', '#12e85c'];
    const duration = 30;
    let seconds = 10;
    const svgNS = 'http://www.w3.org/2000/svg';
    root.innerHTML = '<span class="audio-preview-label">Muestra de diseño · 30 s</span><div class="audio-ruler" aria-hidden="true"></div><div class="audio-lanes" role="slider" tabindex="0" aria-label="Posición del cursor" aria-valuemin="0" aria-valuemax="30"><div class="audio-playhead"></div></div><div class="audio-controls" aria-label="Controles de pistas de muestra"></div>';
    const ruler = root.querySelector('.audio-ruler');
    const lanes = root.querySelector('.audio-lanes');
    const controls = root.querySelector('.audio-controls');
    const playhead = root.querySelector('.audio-playhead');
    const state = colors.map(() => ({mute:false, solo:false}));
    const waves = [];
    const ticks = [];
    const vertical = () => document.body.dataset.orientation === 'vertical';
    const format = n => Math.floor(n / 60) + ':' + String(Math.floor(n % 60)).padStart(2, '0');
    function sampleWave(index) {
        let seed = 128 + index * 997;
        const rand = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; };
        const upper = [], lower = [];
        for (let i = 0; i <= 360; i++) {
            const t = i / 360;
            const envelope = Math.min(1,t*15,(1-t)*15) * (.12 + .68*Math.pow(Math.abs(Math.sin(t*(11+index*3)*Math.PI+index)),3));
            const a = Math.max(.5,44*envelope*(.22+.78*rand()));
            const b = Math.max(.5,44*envelope*(.22+.78*rand()));
            upper.push([t*1000,50-a]); lower.push([t*1000,50+b]);
        }
        return upper.concat(lower.reverse());
    }
    colors.forEach((color,index) => {
        const lane = document.createElement('div'); lane.className = 'audio-lane'; lane.style.setProperty('--track-color',color);
        const svg = document.createElementNS(svgNS,'svg'); svg.setAttribute('class','audio-wave'); svg.setAttribute('preserveAspectRatio','none'); svg.setAttribute('aria-hidden','true');
        const path = document.createElementNS(svgNS,'path'); svg.append(path); lane.append(svg); lanes.insertBefore(lane,playhead);
        waves.push({lane,svg,path,points:sampleWave(index)});
        const control = document.createElement('div'); control.className='audio-track-control'; control.style.setProperty('--track-color',color);
        control.innerHTML='<span class="audio-track-name">Pista '+(index+1)+'</span><div class="audio-track-buttons"><button type="button" aria-pressed="false" aria-label="Silenciar pista '+(index+1)+'" title="Silenciar (muestra)">M</button><button type="button" aria-pressed="false" aria-label="Solo pista '+(index+1)+'" title="Solo (muestra)">S</button></div>';
        const buttons=control.querySelectorAll('button');
        ['mute','solo'].forEach((key,j)=>buttons[j].addEventListener('click',()=>{
            state[index][key]=!state[index][key]; buttons[j].setAttribute('aria-pressed',String(state[index][key]));
            const anySolo=state.some(s=>s.solo); waves.forEach((w,i)=>w.lane.classList.toggle('dimmed',state[i].mute||(anySolo&&!state[i].solo)));
        }));
        controls.append(control);
    });
    for(let t=0;t<=duration;t++){
        const tick=document.createElement('div'); tick.className='audio-tick'+(t%5===0?' major':'')+(t===0?' first':t===duration?' last':'');
        if(t%5===0){const label=document.createElement('span');label.textContent=format(t);tick.append(label);}
        ruler.append(tick);ticks.push(tick);
    }
    function drawCursor(){
        const percent=seconds/duration*100;
        playhead.style.left=vertical()?'0':percent+'%';
        playhead.style.top=vertical()?(100-percent)+'%':'0';
        lanes.setAttribute('aria-valuenow',String(Math.round(seconds*10)/10));
        lanes.setAttribute('aria-valuetext',format(seconds));
    }
    function layout(){
        const v=vertical();
        lanes.setAttribute('aria-orientation',v?'vertical':'horizontal');
        ticks.forEach((tick,i)=>{tick.style.left=v?'auto':i/duration*100+'%';tick.style.top=v?(100-i/duration*100)+'%':'auto';});
        waves.forEach(w=>{
            w.svg.setAttribute('viewBox',v?'0 0 100 1000':'0 0 1000 100');
            w.path.setAttribute('d','M'+w.points.map(([x,y])=>v?y.toFixed(2)+','+(1000-x).toFixed(2):x.toFixed(2)+','+y.toFixed(2)).join(' L')+' Z');
        });
        drawCursor();
    }
    function seek(event){
        const rect=lanes.getBoundingClientRect();
        const fraction=vertical()?1-(event.clientY-rect.top)/rect.height:(event.clientX-rect.left)/rect.width;
        seconds=Math.max(0,Math.min(duration,fraction*duration));drawCursor();
    }
    [ruler,lanes].forEach(el=>{
        el.addEventListener('pointerdown',e=>{if(e.button!==0)return;el.setPointerCapture(e.pointerId);seek(e);});
        el.addEventListener('pointermove',e=>{if(el.hasPointerCapture(e.pointerId))seek(e);});
    });
    lanes.addEventListener('keydown',e=>{
        let value=seconds;
        if(e.key==='ArrowUp'||e.key==='ArrowRight')value++;
        else if(e.key==='ArrowDown'||e.key==='ArrowLeft')value--;
        else if(e.key==='Home')value=0;
        else if(e.key==='End')value=duration;
        else return;
        e.preventDefault();seconds=Math.max(0,Math.min(duration,value));drawCursor();
    });
    new MutationObserver(layout).observe(document.body,{attributes:true,attributeFilter:['data-orientation']});
    layout();
})();
