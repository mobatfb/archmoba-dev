'use strict';
document.addEventListener('click',e=>{const close=e.target.closest('[data-dismiss]');if(close)close.closest('.pub-notice')?.remove();});
// Keep the visible slide until the requested image has loaded and decoded.
document.querySelectorAll('[data-carousel]').forEach(root=>{
    const slides=[...root.querySelectorAll('[data-slide]')],dots=[...root.querySelectorAll('[data-dot]')];if(slides.length<2)return;
    let index=Math.max(0,slides.findIndex(s=>!s.hidden)),timer=null,paused=matchMedia('(prefers-reduced-motion: reduce)').matches,hover=false,focused=false,visible=false,request=0,desired=index;
    const pause=root.querySelector('[data-pause]'),pending=new Map();
    const normalize=n=>(n+slides.length)%slides.length;
    function load(n){
        const img=slides[n].querySelector('img');if(!img)return Promise.resolve(true);
        if(pending.has(n))return pending.get(n);
        const task=new Promise(resolve=>{
            const finish=ok=>{img.removeEventListener('load',loaded);img.removeEventListener('error',failed);resolve(ok);};
            const loaded=()=>{if(typeof img.decode==='function')img.decode().then(()=>finish(true),()=>finish(img.naturalWidth>0));else finish(true);};
            const failed=()=>finish(false);
            img.addEventListener('load',loaded,{once:true});img.addEventListener('error',failed,{once:true});
            if(!img.getAttribute('src')&&img.dataset.src){img.loading='eager';img.src=img.dataset.src;}
            else if(img.complete){if(img.naturalWidth>0)loaded();else failed();}
        });pending.set(n,task);task.then(ok=>{if(!ok)pending.delete(n);});return task;
    }
    function prefetch(){if(visible&&!document.hidden)void load(normalize(index+1));}
    async function show(n){const target=normalize(n),seq=++request;desired=target;if(target===index)return;
        if(!await load(target)||seq!==request||root.hasAttribute('data-gallery-viewing')){if(seq===request)desired=index;return;}
        index=target;slides.forEach((slide,i)=>slide.hidden=i!==index);dots.forEach((d,i)=>d.setAttribute('aria-pressed',String(i===index)));prefetch();
    }
    function stop(){clearInterval(timer);timer=null;}
    function start(){stop();if(visible&&!paused&&!hover&&!focused&&!document.hidden)timer=setInterval(()=>{if(desired===index&&!root.hasAttribute('data-gallery-viewing'))void show(index+1);},6500);}
    function update(){if(pause){pause.textContent=paused?'▶':'Ⅱ';pause.setAttribute('aria-label',paused?'Reproducir carrusel':'Pausar carrusel');}start();}
    root.querySelector('[data-prev]')?.addEventListener('click',()=>{void show(desired-1);start();});root.querySelector('[data-next]')?.addEventListener('click',()=>{void show(desired+1);start();});
    dots.forEach(d=>d.addEventListener('click',()=>{void show(Number(d.dataset.dot));start();}));pause?.addEventListener('click',()=>{paused=!paused;update();});
    root.addEventListener('mouseenter',()=>{hover=true;stop();});root.addEventListener('mouseleave',()=>{hover=false;start();});root.addEventListener('focusin',()=>{focused=true;stop();});root.addEventListener('focusout',e=>{focused=root.contains(e.relatedTarget);start();});
    document.addEventListener('visibilitychange',()=>{start();prefetch();});
    if('IntersectionObserver' in window){new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;start();prefetch();},{rootMargin:'100px'}).observe(root);}else{visible=true;prefetch();}
    update();
});

// Return to the previous public page when available. The normal link is a safe fallback.
document.addEventListener('click',event=>{
    const link=event.target.closest('[data-draw-back]');
    if(!link||event.defaultPrevented||event.button!==0||event.ctrlKey||event.metaKey||event.shiftKey||event.altKey)return;
    if(history.length<2||!document.referrer)return;
    try{
        const current=new URL(location.href),previous=new URL(document.referrer);
        const directory=new URL('.',current).pathname;
        if(previous.origin!==current.origin||![directory,directory+'index.php'].includes(previous.pathname))return;
        if(previous.searchParams.has('admin')||previous.searchParams.has('page')||previous.searchParams.has('photo'))return;
        const view=previous.searchParams.get('view')||'home';
        if(!['home','account','results','evidence','login','profile','verify'].includes(view))return;
        if(previous.pathname===current.pathname&&previous.search===current.search)return;
        event.preventDefault();history.back();
    }catch(_error){/* Follow the normal internal link. */}
});
