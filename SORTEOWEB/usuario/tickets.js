'use strict';
(()=>{
    const board=document.querySelector('[data-ticket-board]'),dialog=document.getElementById('ticket-buy');
    if(!board||!dialog)return;
    const numbers=[...board.querySelectorAll('[data-number]')],live=board.querySelector('[data-ticket-live]'),note=dialog.querySelector('[data-ticket-buy-note]');
    const info=new Intl.NumberFormat('es-EC');
    let selected=null,busy=false,available=true,room=true,stopped=false,timer=null;
    const canPick=state=>room&&(state==='free'||state==='shared');
    const message='Las compras aún no están disponibles. Puedes consultar los números, pero no se reservarán ni se descontará saldo.';
    function status(button,state){
        button.dataset.state=state;
        button.disabled=!canPick(state)||!available;
        const label={sold:'vendido',pending:'pendiente de pago',free:'disponible',shared:'comprado por otros, disponible',mine:'ya lo tienes'}[state]||'no disponible';
        button.setAttribute('aria-label',button.querySelector('[data-ticket-label]').textContent+': '+label);
    }
    function updateDialog(){if(selected)note.textContent=!available?'No se puede verificar la disponibilidad.':!canPick(selected.dataset.state)?'Este número ya no está disponible. Selecciona otro.':message;}
    function suspend(text,terminal=false){available=false;live.textContent=text;numbers.forEach(b=>b.disabled=true);updateDialog();if(terminal){stopped=true;clearInterval(timer);}}
    async function refresh(){
        if(busy||stopped||document.hidden)return;
        busy=true;
        const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),4500);
        try{
            const response=await fetch(board.dataset.url,{credentials:'same-origin',cache:'no-store',headers:{Accept:'application/json'},signal:controller.signal});
            if([401,404,409].includes(response.status)){suspend(response.status===401?'Sesión finalizada. Vuelve a ingresar.':'Sorteo no disponible.',true);return;}
            if(!response.ok)throw Error('HTTP');
            const data=await response.json();
            if(data.active!==true||!data.blocked||typeof data.blocked!=='object'||!Number.isInteger(data.start)||!Number.isInteger(data.end)||typeof data.price_label!=='string')throw Error('Datos inválidos');
            if(data.start!==Number(board.dataset.start)||data.end!==Number(board.dataset.end)){suspend('Cambió la capacidad. Recarga la página.',true);return;}
            available=true;room=data.available!==0;
            numbers.forEach(button=>{status(button,data.blocked[button.dataset.number]||'free');const el=button.querySelector('[data-buyers]');if(el)el.textContent=info.format(data.buyers?.[button.dataset.number]||0);});
            ['paid','pending','available','total'].forEach(key=>{const el=board.querySelector('[data-ticket-'+key+']');if(el){if(Number.isInteger(data[key]))el.textContent=info.format(data[key]);else if(key==='available'&&data[key]===null)el.textContent='Sin límite';}});
            document.querySelectorAll('[data-ticket-price]').forEach(el=>el.textContent=data.price_label);
            live.textContent='Actualizado '+new Date().toLocaleTimeString('es-EC')+' · cada 5 s';updateDialog();
        }catch(error){suspend('Sin conexión. Reintentando…');}finally{clearTimeout(timeout);busy=false;}
    }
    board.addEventListener('click',e=>{const button=e.target.closest('[data-number]');if(!button||button.disabled||!available||dialog.open)return;selected=button;dialog.querySelector('[data-ticket-selected]').textContent=button.querySelector('[data-ticket-label]').textContent;updateDialog();dialog.showModal();refresh();});
    dialog.addEventListener('close',()=>{if(selected&&!selected.disabled)selected.focus();selected=null;});
    dialog.addEventListener('click',e=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)dialog.close();}});
    const highlighted=board.querySelector('.ticket-highlight');if(highlighted)highlighted.scrollIntoView({block:'nearest',inline:'nearest'});
    timer=setInterval(refresh,5000);document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});
})();
