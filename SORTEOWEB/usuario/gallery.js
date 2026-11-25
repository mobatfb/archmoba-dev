'use strict';
// One viewer for every raffle. The underlying details dialog stays open.
(()=>{
    const viewer=document.getElementById('user-photo-viewer');
    if(!(viewer instanceof HTMLDialogElement))return;
    const image=viewer.querySelector('.photo-viewer-image'),title=viewer.querySelector('#user-photo-viewer-title'),count=viewer.querySelector('[data-viewer-count]'),prev=viewer.querySelector('[data-viewer-prev]'),next=viewer.querySelector('[data-viewer-next]'),close=viewer.querySelector('[data-viewer-close]');
    let photos=[],index=0,origin=null;
    function show(i){
        if(!photos.length)return;
        index=(i+photos.length)%photos.length;
        const photo=photos[index];
        image.src=photo.src;image.alt=photo.alt;
        count.textContent=(index+1)+' / '+photos.length;
        prev.hidden=next.hidden=photos.length<2;
    }
    document.addEventListener('click',event=>{
        const trigger=event.target.closest('[data-gallery-photo]');
        if(!trigger||viewer.open)return;
        const gallery=trigger.closest('.user-details-gallery'),details=trigger.closest('.user-details-dialog');
        if(!gallery||!details?.open)return;
        const buttons=[...gallery.querySelectorAll('[data-gallery-photo]')];
        photos=buttons.map(button=>{const img=button.querySelector('.user-details-photo-main');return {src:img.src,alt:img.alt};});
        origin=trigger;title.textContent=details.querySelector('h2').textContent;
        show(buttons.indexOf(trigger));viewer.showModal();close.focus();
    });
    prev.addEventListener('click',()=>show(index-1));next.addEventListener('click',()=>show(index+1));
    close.addEventListener('click',()=>viewer.close());
    viewer.addEventListener('keydown',event=>{
        if(event.key==='ArrowLeft'||event.key==='ArrowRight'){event.preventDefault();show(index+(event.key==='ArrowLeft'?-1:1));}
    });
    viewer.addEventListener('click',event=>{
        if(event.target!==viewer)return;
        const r=viewer.getBoundingClientRect();
        if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)viewer.close();
    });
    viewer.addEventListener('close',()=>{
        image.removeAttribute('src');image.alt='';photos=[];
        if(origin?.isConnected&&origin.closest('dialog')?.open)origin.focus();
        origin=null;
    });
})();
