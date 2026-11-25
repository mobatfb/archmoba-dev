'use strict';
document.addEventListener('click',e=>{const close=e.target.closest('[data-dismiss]');if(close)close.closest('.pub-notice')?.remove();});
document.querySelectorAll('[data-carousel]').forEach(root=>{const slides=[...root.querySelectorAll('[data-slide]')],dots=[...root.querySelectorAll('[data-dot]')];if(slides.length<2)return;let index=slides.findIndex(s=>!s.hidden);if(index<0)index=0;let timer=null,paused=matchMedia('(prefers-reduced-motion: reduce)').matches,hover=false,focused=false;const pause=root.querySelector('[data-pause]');function show(n){index=(n+slides.length)%slides.length;slides.forEach((s,i)=>s.hidden=i!==index);dots.forEach((d,i)=>d.setAttribute('aria-pressed',String(i===index)));}function stop(){clearInterval(timer);timer=null;}function start(){stop();if(!paused&&!hover&&!focused&&!document.hidden)timer=setInterval(()=>show(index+1),6500);}function update(){if(pause){pause.textContent=paused?'▶':'Ⅱ';pause.setAttribute('aria-label',paused?'Reproducir carrusel':'Pausar carrusel');}start();}const prev=root.querySelector('[data-prev]'),next=root.querySelector('[data-next]');if(prev)prev.addEventListener('click',()=>{show(index-1);start()});if(next)next.addEventListener('click',()=>{show(index+1);start()});dots.forEach(d=>d.addEventListener('click',()=>{show(Number(d.dataset.dot));start()}));if(pause)pause.addEventListener('click',()=>{paused=!paused;update()});root.addEventListener('mouseenter',()=>{hover=true;stop()});root.addEventListener('mouseleave',()=>{hover=false;start()});root.addEventListener('focusin',()=>{focused=true;stop()});root.addEventListener('focusout',e=>{focused=root.contains(e.relatedTarget);start()});document.addEventListener('visibilitychange',start);update();});

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
