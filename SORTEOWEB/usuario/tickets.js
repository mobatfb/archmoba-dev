'use strict';
(()=>{
    const board=document.querySelector('[data-ticket-board]'),dialog=document.getElementById('ticket-buy');
    if(!board||!dialog)return;
    const numbers=[...board.querySelectorAll('[data-number]')],live=board.querySelector('[data-ticket-live]'),note=dialog.querySelector('[data-ticket-buy-note]');
    const info=new Intl.NumberFormat('es-EC');
    let selected=null,busy=false,available=true,stopped=false,timer=null;
    const message='La compra todavía no está habilitada. No se reservará el número ni se descontará saldo.';
    function status(button,state){
        button.dataset.state=state;
        button.disabled=state!=='free'||!available;
        const label={sold:'vendido',pending:'pendiente de pago',free:'disponible'}[state]||'no disponible';
        button.setAttribute('aria-label',button.textContent.trim()+': '+label);
    }
    function updateDialog(){if(selected)note.textContent=!available?'No se puede verificar la disponibilidad.':selected.dataset.state!=='free'?'Este número ya no está disponible. Selecciona otro.':message;}
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
            available=true;
            numbers.forEach(button=>status(button,data.blocked[button.dataset.number]||'free'));
            ['paid','pending','available','total'].forEach(key=>{const el=board.querySelector('[data-ticket-'+key+']');if(el&&Number.isInteger(data[key]))el.textContent=info.format(data[key]);});
            document.querySelectorAll('[data-ticket-price]').forEach(el=>el.textContent=data.price_label);
            live.textContent='Actualizado '+new Date().toLocaleTimeString('es-EC')+' · cada 5 s';updateDialog();
        }catch(error){suspend('Sin conexión. Reintentando…');}finally{clearTimeout(timeout);busy=false;}
    }
    board.addEventListener('click',e=>{const button=e.target.closest('[data-number]');if(!button||button.disabled||!available||dialog.open)return;selected=button;dialog.querySelector('[data-ticket-selected]').textContent=button.textContent.trim();updateDialog();dialog.showModal();refresh();});
    dialog.addEventListener('close',()=>{if(selected&&!selected.disabled)selected.focus();selected=null;});
    dialog.addEventListener('click',e=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)dialog.close();}});
    const highlighted=board.querySelector('.ticket-highlight');if(highlighted)highlighted.scrollIntoView({block:'nearest',inline:'nearest'});
    timer=setInterval(refresh,5000);document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});
})();
