/* FUTUREO STUDIO v0.1.23 - absolute sample-frame capture on the transport clock. */
class FutureoPCM extends AudioWorkletProcessor {
    constructor(options) {
        super();
        const opts=options?.processorOptions||{};
        this.startFrame=Math.max(0,Math.round(Number(opts.startFrame)||0));
        this.nextFrame=this.startFrame;
        this.endFrame=this.startFrame+Math.round(sampleRate*600);
        this.block=new Int16Array(Math.round(sampleRate*.5));
        this.used=0;this.active=true;
        this.port.onmessage=e=>{
            // Stop at an absolute audio frame, never at the arrival time of the UI message.
            if(e.data?.type==='stop'&&Number.isSafeInteger(e.data.frame)){
                const requested=Math.max(this.startFrame,e.data.frame);
                this.endFrame=Math.min(this.endFrame,requested);
                if(this.nextFrame>=this.endFrame)this.finish();
            }else if(e.data==='stop'){this.endFrame=this.nextFrame;this.finish();}
        };
    }
    flush(){
        if(!this.used)return;
        const buffer=new ArrayBuffer(this.used*2),view=new DataView(buffer),peaks=[];
        const step=Math.max(1,Math.round(sampleRate/40));let max=0;
        for(let i=0;i<this.used;i++){
            const n=this.block[i];view.setInt16(i*2,n,true);max=Math.max(max,Math.abs(n));
            if((i+1)%step===0||i===this.used-1){peaks.push(max/32768);max=0;}
        }
        const frame=this.nextFrame-this.used;
        this.port.postMessage({type:'pcm',frame,buffer,peaks},[buffer]);this.used=0;
    }
    append(s){
        s=Math.max(-1,Math.min(1,Number.isFinite(s)?s:0));
        this.block[this.used++]=Math.round(s*(s<0?32768:32767));this.nextFrame++;
        if(this.used===this.block.length)this.flush();
    }
    finish(){
        if(!this.active)return;
        this.active=false;
        // A delayed stop message may arrive after a rendered quantum. Keep already
        // captured frames and report their real endpoint, rather than corrupting WAV data.
        this.flush();this.port.postMessage({type:'stopped',startFrame:this.startFrame,endFrame:this.nextFrame,frames:this.nextFrame-this.startFrame});
    }
    process(inputs,outputs){
        const out=outputs[0]||[];
        for(const channel of out)channel.fill(0); // no live mic feedback
        if(!this.active)return false;
        const channels=inputs[0]||[],n=out[0]?.length||channels[0]?.length||128;
        const quantumStart=currentFrame,quantumEnd=quantumStart+n;
        if(quantumEnd<=this.startFrame)return true;
        // Never collapse time when input is temporarily absent or the graph starts late.
        const from=Math.max(this.nextFrame,quantumStart,this.startFrame);
        while(this.nextFrame<Math.min(from,this.endFrame))this.append(0);
        for(let frame=from;frame<Math.min(quantumEnd,this.endFrame);frame++){
            let s=0;for(const c of channels)s+=c[frame-quantumStart]||0;
            this.append(channels.length?s/channels.length:0);
        }
        if(this.nextFrame>=this.endFrame){this.finish();return false;}
        return true;
    }
}
registerProcessor('futureo-pcm',FutureoPCM);
