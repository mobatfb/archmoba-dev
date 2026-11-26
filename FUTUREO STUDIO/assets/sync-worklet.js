/* FUTUREO STUDIO v0.1.25 - bounded calibration capture on the render clock. */
class FutureoSyncCapture extends AudioWorkletProcessor {
    constructor(options) {
        super();
        const o=options.processorOptions||{};
        this.first=o.startFrame;this.end=o.endFrame;this.next=this.first;
        this.active=Number.isSafeInteger(this.first)&&Number.isSafeInteger(this.end)&&this.first>=0&&this.end>this.first&&this.end-this.first<=sampleRate*6;
        this.data=this.active?new Float32Array(this.end-this.first):null;this.ready=false;
    }
    fail(reason){this.active=false;this.port.postMessage({type:'error',reason});return false;}
    process(inputs,outputs){
        for(const c of outputs[0]||[])c.fill(0); // never monitor the microphone
        if(!this.active)return false;
        const channels=inputs[0]||[],n=outputs[0]?.[0]?.length||channels[0]?.length||128;
        if(!this.ready){this.ready=true;this.port.postMessage({type:'ready',frame:currentFrame});}
        const from=Math.max(this.first,currentFrame),to=Math.min(this.end,currentFrame+n);
        if(to<=from)return true;
        if(from!==this.next||!channels.length||channels.some(c=>c.length<n))return this.fail('La entrada de audio se interrumpió durante la prueba.');
        for(let f=from;f<to;f++){let v=0;for(const c of channels)v+=c[f-currentFrame];this.data[f-this.first]=v/channels.length;}
        this.next=to;
        if(to===this.end){this.active=false;this.port.postMessage({type:'samples',startFrame:this.first,endFrame:this.end,buffer:this.data.buffer},[this.data.buffer]);return false;}
        return true;
    }
}
registerProcessor('futureo-sync-capture',FutureoSyncCapture);
