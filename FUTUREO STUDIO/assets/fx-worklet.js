/* FUTUREO STUDIO - gate, dynamic de-esser and experimental monophonic pitch correction. */
class FutureoVoiceFX extends AudioWorkletProcessor {
    static get parameterDescriptors(){return [
        {name:'gate',defaultValue:0,minValue:0,maxValue:1,automationRate:'k-rate'},
        {name:'threshold',defaultValue:-45,minValue:-70,maxValue:-25,automationRate:'k-rate'},
        {name:'deess',defaultValue:0,minValue:0,maxValue:1,automationRate:'k-rate'},
        {name:'tune',defaultValue:0,minValue:0,maxValue:1,automationRate:'k-rate'},
        {name:'key',defaultValue:0,minValue:0,maxValue:11,automationRate:'k-rate'},
        {name:'scale',defaultValue:0,minValue:0,maxValue:2,automationRate:'k-rate'}
    ];}
    constructor(){super();this.channels=[];this.ringSize=Math.ceil(sampleRate*.16)+4;this.write=0;
        this.decimate=Math.max(1,Math.round(sampleRate/8000));this.analysisRate=sampleRate/this.decimate;
        this.history=new Float32Array(Math.ceil(this.analysisRate*.055));this.historyPos=0;this.historyCount=0;this.decCount=0;this.decSum=0;this.analysisCountdown=Math.round(this.analysisRate*.022);
        this.frame=new Float32Array(this.history.length);this.diff=new Float32Array(Math.ceil(this.analysisRate/60)+2);
        this.pitch=0;this.targetRatio=1;this.ratio=1;this.phase=.25;this.window=sampleRate*.025;this.wet=0;this.gateEnvelope=0;this.gateGain=1;this.highEnvelope=0;this.fullEnvelope=0;this.deessGain=1;
    }
    analyze(key,scale,strength){
        if(this.historyCount<this.history.length){this.targetRatio=1;return;}
        const n=this.history.length,frame=this.frame;let mean=0,energy=0;
        for(let i=0;i<n;i++){const x=this.history[(this.historyPos+i)%n];frame[i]=x;mean+=x;energy+=x*x;}
        mean/=n;if(energy/n-mean*mean<.000008){this.pitch=0;this.targetRatio=1;return;}
        const max=Math.min(this.diff.length-2,Math.floor(this.analysisRate/60)),min=Math.max(2,Math.floor(this.analysisRate/650)),width=n-max;
        let sum=0;this.diff[0]=1;
        for(let lag=1;lag<=max+1;lag++){let d=0;const len=Math.min(width,n-lag);for(let i=0;i<len;i++){const delta=frame[i]-frame[i+lag];d+=delta*delta;}sum+=d;this.diff[lag]=sum>1e-12?d*lag/sum:1;}
        let best=0,minimum=.19;
        for(let lag=min;lag<=max;lag++){if(this.diff[lag]<minimum){while(lag<max&&this.diff[lag+1]<this.diff[lag])lag++;best=lag;break;}}
        if(!best){this.pitch=0;this.targetRatio=1;return;}
        const a=this.diff[best-1],b=this.diff[best],c=this.diff[best+1],den=a-2*b+c;
        const refined=best+(Math.abs(den)>1e-8?Math.max(-.5,Math.min(.5,.5*(a-c)/den)):0);
        const hz=this.analysisRate/refined;this.pitch=hz;
        const note=69+12*Math.log2(hz/440),allowed=scale===1?[0,2,4,5,7,9,11]:scale===2?[0,2,3,5,7,8,10]:[0,1,2,3,4,5,6,7,8,9,10,11];
        let nearest=Math.round(note),distance=Infinity;for(let m=Math.floor(note)-3;m<=Math.ceil(note)+3;m++){if(allowed.includes((m-key+120)%12)&&Math.abs(m-note)<distance){nearest=m;distance=Math.abs(m-note);}}
        this.targetRatio=Math.max(.84,Math.min(1.19,Math.pow(2,(nearest-note)*strength/12)));
    }
    channel(i){while(this.channels.length<=i)this.channels.push({ring:new Float32Array(this.ringSize),low:0});return this.channels[i];}
    read(ring,delay){let at=this.write-delay;while(at<0)at+=this.ringSize;const i=Math.floor(at),f=at-i;return ring[i]*(1-f)+ring[(i+1)%this.ringSize]*f;}
    process(inputs,outputs,p){const input=inputs[0],out=outputs[0];if(!out.length)return true;
        const gate=p.gate[0]>.5,deess=p.deess[0],tune=p.tune[0],threshold=Math.pow(10,p.threshold[0]/20),key=Math.round(p.key[0]),scale=Math.round(p.scale[0]);
        const hpAlpha=1-Math.exp(-2*Math.PI*4800/sampleRate),envA=1-Math.exp(-1/(sampleRate*.003)),envR=1-Math.exp(-1/(sampleRate*.065));
        const fade=1-Math.exp(-1/(sampleRate*.012)),ratioSmooth=1-Math.exp(-1/(sampleRate*.03));
        for(let i=0;i<out[0].length;i++){
            let mono=0,high=0,level=0;
            for(let ch=0;ch<out.length;ch++){const state=this.channel(ch),x=input[ch]?.[i]??input[0]?.[i]??0;state.low+=hpAlpha*(x-state.low);mono+=x;level=Math.max(level,Math.abs(x));high=Math.max(high,Math.abs(x-state.low));}
            mono/=out.length;this.gateEnvelope+=(level-this.gateEnvelope)*(level>this.gateEnvelope?envA:envR);
            const wantedGate=gate?Math.max(.02,Math.min(1,Math.pow(this.gateEnvelope/Math.max(threshold,1e-6),2))):1;
            this.gateGain+=(wantedGate-this.gateGain)*(wantedGate>this.gateGain?envA:envR);
            this.highEnvelope+=(high-this.highEnvelope)*(high>this.highEnvelope?envA:envR);this.fullEnvelope+=(level-this.fullEnvelope)*(level>this.fullEnvelope?envA:envR);
            const sib=Math.max(0,Math.min(1,(this.highEnvelope/Math.max(.009,this.fullEnvelope)-.18)*3));
            const wantDeess=1-deess*.82*sib;this.deessGain+=(wantDeess-this.deessGain)*(wantDeess<this.deessGain?envA:envR);
            if(tune>0){this.decSum+=mono;if(++this.decCount>=this.decimate){this.history[this.historyPos]=this.decSum/this.decCount;this.historyPos=(this.historyPos+1)%this.history.length;this.historyCount=Math.min(this.history.length,this.historyCount+1);this.decCount=0;this.decSum=0;if(--this.analysisCountdown<=0){this.analysisCountdown=Math.round(this.analysisRate*.022);this.analyze(key,scale,tune);}}}else{this.pitch=0;this.targetRatio=1;this.historyCount=0;this.decCount=0;this.decSum=0;}
            this.ratio+=(this.targetRatio-this.ratio)*ratioSmooth;
            const wantedWet=tune>0&&this.pitch>0&&Math.abs(this.targetRatio-1)>.0015?1:0;
            this.wet+=(wantedWet-this.wet)*fade;
            const wantedWindow=this.pitch>0?Math.max(sampleRate*.008,Math.min(sampleRate*.07,4*sampleRate/this.pitch)):this.window;
            this.window+=(wantedWindow-this.window)*ratioSmooth;
            this.phase=(this.phase+(1-this.ratio)/this.window+1)%1;
            const q=(this.phase+.5)%1,w=Math.sin(Math.PI*this.phase)**2,w2=1-w;
            for(let ch=0;ch<out.length;ch++){const state=this.channel(ch),x=input[ch]?.[i]??input[0]?.[i]??0;const dry=(state.low+(x-state.low)*this.deessGain)*this.gateGain;state.ring[this.write]=dry;
                // Two overlapping read heads shift the pitch without changing clip duration.
                const shifted=this.read(state.ring,2+this.phase*this.window)*w+this.read(state.ring,2+q*this.window)*w2;
                out[ch][i]=dry+(shifted-dry)*this.wet;
            }
            this.write=(this.write+1)%this.ringSize;
        }return true;
    }
}
registerProcessor('futureo-voice-fx',FutureoVoiceFX);

/* Automatic gain riding. Shared detector preserves stereo balance. */
class FutureoLeveler extends AudioWorkletProcessor {
    static get parameterDescriptors(){return [
        {name:'enabled',defaultValue:0,minValue:0,maxValue:1,automationRate:'k-rate'},
        {name:'target',defaultValue:-18,minValue:-30,maxValue:-9,automationRate:'k-rate'},
        {name:'strength',defaultValue:.85,minValue:0,maxValue:1,automationRate:'k-rate'},
        {name:'boost',defaultValue:12,minValue:0,maxValue:18,automationRate:'k-rate'}
    ];}
    constructor(){super();this.power=0;this.gainDb=0;this.limiter=1;
        this.rise=1-Math.exp(-1/(sampleRate*.055));this.fall=1-Math.exp(-1/(sampleRate*.16));
        this.down=1-Math.exp(-1/(sampleRate*.045));this.up=1-Math.exp(-1/(sampleRate*.25));
        this.limitRelease=1-Math.exp(-1/(sampleRate*.08));this.ceiling=Math.pow(10,-1/20);
    }
    process(inputs,outputs,p){
        const input=inputs[0]||[],out=outputs[0];if(!out.length)return true;
        const enabled=p.enabled[0]>.5&&p.strength[0]>0,target=p.target[0],strength=p.strength[0],boost=p.boost[0];
        for(let i=0;i<out[0].length;i++){
            let power=0,peak=0;
            for(let ch=0;ch<out.length;ch++){
                const x=input[ch]?.[i]??input[0]?.[i]??0;power+=x*x;peak=Math.max(peak,Math.abs(x));
            }
            power/=out.length;this.power+=(power-this.power)*(power>this.power?this.rise:this.fall);
            if(!enabled){this.gainDb=0;this.limiter=1;for(let ch=0;ch<out.length;ch++)out[ch][i]=input[ch]?.[i]??input[0]?.[i]??0;continue;}
            const rmsDb=10*Math.log10(Math.max(1e-12,this.power));
            let desired=Math.max(-30,Math.min(boost,(target-rmsDb)*strength));
            // Prevent automatic gain from lifting the noise floor in near-silence.
            if(desired>0)desired*=Math.max(0,Math.min(1,(rmsDb+55)/10));
            this.gainDb+=(desired-this.gainDb)*(desired<this.gainDb?this.down:this.up);
            const gain=Math.pow(10,this.gainDb/20);
            const allowed=Math.min(1,this.ceiling/Math.max(1e-12,peak*gain));
            this.limiter=allowed<this.limiter?allowed:this.limiter+(allowed-this.limiter)*this.limitRelease;
            const g=gain*this.limiter;
            for(let ch=0;ch<out.length;ch++)out[ch][i]=(input[ch]?.[i]??input[0]?.[i]??0)*g;
        }return true;
    }
}
registerProcessor('futureo-leveler',FutureoLeveler);

/* FUTUREO Rhythm: sample-clock-synchronized amplitude pattern, repeat and stereo pan. */
class FutureoRhythm extends AudioWorkletProcessor {
    static get parameterDescriptors(){return [
        {name:'enabled',defaultValue:0,minValue:0,maxValue:1,automationRate:'k-rate'},
        {name:'bpm',defaultValue:124,minValue:60,maxValue:180,automationRate:'k-rate'},
        {name:'origin',defaultValue:0,minValue:-100000000,maxValue:100000000,automationRate:'k-rate'},
        {name:'pattern',defaultValue:46557,minValue:0,maxValue:65535,automationRate:'k-rate'},
        {name:'intensity',defaultValue:.65,minValue:0,maxValue:1,automationRate:'k-rate'},
        {name:'gate',defaultValue:.35,minValue:0,maxValue:1,automationRate:'k-rate'},
        {name:'tremolo',defaultValue:.15,minValue:0,maxValue:1,automationRate:'k-rate'},
        {name:'repeat',defaultValue:.2,minValue:0,maxValue:1,automationRate:'k-rate'},
        {name:'pan',defaultValue:.35,minValue:0,maxValue:1,automationRate:'k-rate'}
    ];}
    constructor(){super();this.size=Math.ceil(sampleRate*1.2)+4;this.rings=[];this.history=0;this.amp=1;this.alpha=1-Math.exp(-1/(sampleRate*.004));}
    ring(ch){while(this.rings.length<=ch)this.rings.push(new Float32Array(this.size));return this.rings[ch];}
    read(ring,frame){const index=Math.floor(frame),f=frame-index,n=((index%this.size)+this.size)%this.size;return ring[n]*(1-f)+ring[(n+1)%this.size]*f;}
    process(inputs,outputs,p){
        const input=inputs[0]||[],out=outputs[0];if(!out.length)return true;
        const enabled=p.enabled[0]>.5,depth=enabled?p.intensity[0]:0,pattern=Math.round(p.pattern[0])&65535;
        const stepFrames=sampleRate*60/p.bpm[0]/4,origin=Math.round(p.origin[0]*sampleRate);
        const gate=p.gate[0]*depth,tremolo=p.tremolo[0]*depth,repeat=p.repeat[0]*depth,pan=p.pan[0]*depth;
        for(let i=0;i<out[0].length;i++){
            const frame=currentFrame+i,pos=(frame-origin)/stepFrames,index=Math.floor(pos),phase=pos-index;
            const step=((index%16)+16)%16,hit=!!(pattern&(1<<step)),write=((frame%this.size)+this.size)%this.size;
            const ready=depth>0&&frame>=origin;
            const target=ready?(hit?1:1-gate)*(1-tremolo*(.5-.5*Math.cos(Math.PI*pos))):1;
            this.amp+= (target-this.amp)*this.alpha;
            // On the last subdivision of a beat, replay the first half of the previous subdivision twice.
            const repeatOn=ready&&hit&&step%4===3&&this.history>stepFrames*2&&repeat>0;
            const sub=phase*2-Math.floor(phase*2),fade=Math.min(1,sub*18,(1-sub)*18),wet=repeatOn?repeat*fade:0;
            const prevStart=origin+(index-1)*stepFrames;
            const readFrame=prevStart+sub*stepFrames*.5;
            const panValue=ready?Math.sin(pos*Math.PI/4)*pan:0;
            for(let ch=0;ch<out.length;ch++){
                const x=input[ch]?.[i]??input[0]?.[i]??0,r=this.ring(ch);r[write]=x;
                if(!ready){out[ch][i]=x;continue;}
                const y=wet>0?x+(this.read(r,readFrame)-x)*wet:x;
                // Equal center level; attenuate the opposing channel during panning.
                const stereo=out.length>1?(ch===0?1-Math.max(0,panValue):1+Math.min(0,panValue)):1;
                out[ch][i]=y*this.amp*stereo;
            }
            this.history=Math.min(this.history+1,this.size);
        }
        return true;
    }
}
registerProcessor('futureo-rhythm',FutureoRhythm);
