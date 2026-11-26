/* FUTUREO STUDIO - mono PCM16 capture, real sample clock. */
class FutureoPCM extends AudioWorkletProcessor {
    constructor(options) {
        super();
        this.block = new Int16Array(Math.round(sampleRate * .5));
        this.used = 0;
        this.active = true;
        this.startFrame = Math.max(0, Number(options?.processorOptions?.startFrame) || 0);
        this.port.onmessage = e => {
            if (e.data === 'stop') {
                this.active = false;
                this.flush();
                this.port.postMessage({type:'stopped'});
            }
        };
    }
    flush() {
        if (!this.used) return;
        const buffer = new ArrayBuffer(this.used * 2);
        const view = new DataView(buffer);
        const peaks = [];
        const step = Math.max(1, Math.round(sampleRate / 40));
        let max = 0;
        for (let i=0; i<this.used; i++) {
            const n = this.block[i];
            view.setInt16(i*2,n,true);
            max = Math.max(max,Math.abs(n));
            if ((i+1)%step===0 || i===this.used-1) {peaks.push(max/32768);max=0;}
        }
        this.port.postMessage({type:'pcm',buffer,peaks},[buffer]);
        this.used=0;
    }
    process(inputs, outputs) {
        // Silent output keeps the graph running without feeding the mic to speakers.
        for(const channel of outputs[0] || []) channel.fill(0);
        if (!this.active) return false;
        const channels=inputs[0];
        if (!channels || !channels.length) return true;
        const n=channels[0].length;
        for(let i=0;i<n;i++) {
            let s=0;
            for(const c of channels) s+=c[i]||0;
            s=Math.max(-1,Math.min(1,s/channels.length));
            this.block[this.used++]=Math.round(s*(s<0?32768:32767));
            if(this.used===this.block.length) this.flush();
        }
        return true;
    }
}
registerProcessor('futureo-pcm',FutureoPCM);
