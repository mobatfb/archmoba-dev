/* FUTUREO STUDIO v0.1.26 - align the intact recording against the actual rendered mix. */
(() => {
    'use strict';
    const MAX_LAG=.75, finiteLatency=x=>typeof x==='number'&&Number.isFinite(x)&&x>=0&&x<=MAX_LAG;
    const median=a=>{const b=[...a].sort((x,y)=>x-y),m=b.length>>1;return b.length%2?b[m]:(b[m-1]+b[m])/2;};
    const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
    function estimate(context,media,graphLatency,accompaniment){
        const input=media.getAudioTracks()[0]?.getSettings?.().latency;
        let output=0,outputKnown=false;
        if(accompaniment){
            const base=context.baseLatency,hardware=context.outputLatency;
            output=(finiteLatency(base)?base:0)+(finiteLatency(hardware)?hardware:0);
            outputKnown=finiteLatency(hardware)&&hardware>0;
            // Output timestamps map the render clock to the samples heard at the device.
            try{const stamp=context.getOutputTimestamp?.(),now=performance.now();if(stamp&&stamp.contextTime>0&&stamp.performanceTime>0&&Math.abs(now-stamp.performanceTime)<250){const lag=context.currentTime-(stamp.contextTime+(now-stamp.performanceTime)/1000);if(finiteLatency(lag)){output=lag;outputKnown=true;}}}catch(_){}
        }
        const graph=accompaniment?Math.max(0,Math.min(.05,Number(graphLatency)||0)):0;
        return {seconds:clamp((finiteLatency(input)?input:0)+output,0,MAX_LAG)+graph,graph,inputKnown:finiteLatency(input),outputKnown,accompaniment};
    }
    function prefix(a){const p=new Float64Array(a.length+1);for(let i=0;i<a.length;i++)p[i+1]=p[i]+a[i]*a[i];return p;}
    function whiten(a){const b=new Float32Array(a.length);for(let i=1;i<a.length;i++)b[i]=a[i]-.9*a[i-1];return b;}
    // Multiple short, non-overlapping windows must agree. Reject repetitive beats,
    // unrelated singing, silence, weak leakage, and inconsistent echoes.
    function measure(mic,reference,rate){
        if(!(mic instanceof Float32Array)||!(reference instanceof Float32Array)||mic.length!==reference.length||!Number.isFinite(rate)||rate<1800||rate>8000)return null;
        const max=Math.floor(MAX_LAG*rate),n=Math.round(.32*rate),end=mic.length-max-n;
        if(end<Math.round(.65*rate))return null;
        const a=whiten(mic),b=whiten(reference),ae=prefix(a),be=prefix(b),sets=[];
        const count=Math.min(12,Math.floor(end/n)+1),near=Math.max(2,Math.round(.0025*rate)),apart=Math.round(.014*rate);
        for(let j=0;j<count;j++){
            const at=Math.round(j*end/Math.max(1,count-1)),energy=be[at+n]-be[at];
            if(energy<n*1e-7)continue;
            const scores=new Float32Array(max+1);let best=0,lag=0;
            for(let d=0;d<=max;d++){
                const p=at+d,e=ae[p+n]-ae[p];if(e<n*1e-9)continue;
                let cross=0;for(let i=0;i<n;i++)cross+=a[p+i]*b[at+i];
                const v=Math.min(1,Math.abs(cross)/Math.sqrt(e*energy));scores[d]=v;if(v>best){best=v;lag=d;}
            }
            if(best<.40)continue;
            let rival=0;for(let d=0;d<=max;d++)if(Math.abs(d-lag)>apart)rival=Math.max(rival,scores[d]);
            if(rival>best*.88||best-rival<.05)continue;
            sets.push({lag,score:best});
        }
        if(sets.length<3)return null;
        let winner=[];
        for(const x of sets){const cluster=sets.filter(y=>Math.abs(x.lag-y.lag)<=near);if(cluster.length>winner.length)winner=cluster;}
        if(winner.length<3||winner.length<Math.ceil(sets.length*.70))return null;
        const lags=winner.map(x=>x.lag),spread=Math.max(...lags)-Math.min(...lags);
        if(spread>2*near)return null;
        return {seconds:median(lags)/rate,matches:winner.length,windows:sets.length,score:median(winner.map(x=>x.score)),spreadMs:spread/rate*1000};
    }
    function align(t,data){
        const count=t.captured/2,requested=Math.max(0,Math.round(t.transportFrames||0));
        const m=t.initialEstimate.accompaniment&&data?.reference instanceof ArrayBuffer&&data?.mic instanceof ArrayBuffer?measure(new Float32Array(data.mic),new Float32Array(data.reference),t.rate/data.stride):null;
        const seconds=m?m.seconds+t.initialEstimate.graph:t.initialEstimate.seconds;
        const nominal=Math.max(0,Math.round(seconds*t.rate));
        // Preserve the complete source. The visible clip points into that WAV instead
        // of deleting samples or moving the transport start on an unproven estimate.
        const offset=Math.min(nominal,Math.max(0,count-requested)),frames=Math.min(requested,Math.max(0,count-offset));
        return {offset,frames,method:m?'reference':'estimate',measurement:m,ms:offset/t.rate*1000,limited:offset!==nominal||frames!==requested};
    }
    window.FutureoAdaptiveSync={estimate,measure,align};
})();
