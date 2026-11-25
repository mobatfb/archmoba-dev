'use strict';
const $=(s,r=document)=>r.querySelector(s);
const $$=(s,r=document)=>[...r.querySelectorAll(s)];
const money=n=>new Intl.NumberFormat('es-EC',{style:'currency',currency:'USD'}).format(n);
const safeJson=s=>{try{return JSON.parse(s)}catch{return null}};
const rf=$('#raffle-form'),pf=$('#participant-form');
const photoUrl=(id,slot)=>`index.php?photo=${encodeURIComponent(id)}&slot=${slot}`;
const previewUrls=new Map();
let wizardStep=1,lastPrizeType='',productPrice='1.00';
const moneyCents=value=>{const m=String(value).match(/^(0|[1-9][0-9]{0,6})(?:[.,]([0-9]{1,2}))?$/);if(!m)return 0;const n=Number(m[1])*100+Number((m[2]||'').padEnd(2,'0'));return n>0&&n<=100000000?n:0;};
const cashLabel=cents=>'$'+(cents/100).toFixed(2).replace('.',',').replace(/\B(?=(\d{3})+,)/g,'.');
const cashTitle=cents=>`Gana ${cashLabel(cents)} en efectivo`;
const integerValue=value=>{const n=Number(value);return Number.isInteger(n)&&n>=1&&n<=1000000?n:0;};
function updatePotential(){
    if(!rf)return;const e=rf.elements,shared=e.participation_mode.value==='compartido',cap=e.close_mode.value==='capacidad',cash=e.type.value==='dinero';
    const rounding=$('[data-rounding-note]',rf),potentialLabel=$('[data-potential-label]',rf);
    let n=integerValue(shared&&cap?e.participation_limit.value:e.ticket_count.value),p=moneyCents(e.price.value);
    if(cash){
        const amount=moneyCents(e.money_amount.value),quantity=integerValue(e.pricing_participations.value);
        p=amount&&quantity?Math.ceil(amount/quantity):0;n=quantity;
        e.price.value=p?(p/100).toFixed(2):'';e.price.setCustomValidity('');
        if(!shared)e.ticket_count.value=quantity||'';
        if(cap)e.participation_limit.value=quantity||'';
        $('[data-money-title]',rf).textContent=amount?cashTitle(amount):'Ingresa el monto';
        $('[data-money-note]',rf).textContent=shared?(cap?'La cantidad indicada será la capacidad total de participaciones pagadas. Cada cuenta puede elegir varios números distintos.':'La cantidad indicada sirve para calcular el precio; no limita las ventas. Cada cuenta puede elegir varios números distintos.'):'Cada participación corresponde a un número exclusivo. Una persona puede adquirir varios números.';
        potentialLabel.textContent=shared&&!cap?'Ingreso estimado':'Ingreso a capacidad completa';
        rounding.hidden=!(amount&&quantity&&p*quantity>amount);
        rounding.textContent=rounding.hidden?'':`El boleto se redondea hacia arriba al centavo. Diferencia al alcanzar la cantidad prevista: ${cashLabel(p*quantity-amount)}.`;
        $('#potential').textContent=amount&&quantity?cashLabel(n*p):'—';
    }else{
        potentialLabel.textContent='Ingreso potencial';rounding.hidden=true;
        $('#potential').textContent=shared&&!cap?'Sin límite fijo':cashLabel(n*p);
    }
}
function refreshRaffleSettings(){
    if(!rf)return;const e=rf.elements,type=e.type.value,cash=type==='dinero',shared=e.participation_mode.value==='compartido',cap=e.close_mode.value==='capacidad';
    const toggle=(selector,visible,input)=>{$(selector,rf).hidden=!visible;if(input){input.disabled=!visible;input.required=visible;}};
    $('[data-selected-type]',rf).textContent=cash?'Premio seleccionado: Dinero':'Premio seleccionado: Producto físico';
    toggle('[data-money-inputs]',cash);for(const name of ['money_amount','pricing_participations']){e[name].disabled=!cash;e[name].required=cash;}
    toggle('[data-money-calculation]',cash);toggle('[data-prize-field]',!cash&&shared,e.prize_value);
    $('[data-mode-note]',rf).textContent=shared?'Cada cuenta puede adquirir cada número una sola vez. Los titulares pagados del número ganador comparten el premio.':'Cada número tiene un solo titular.';
    toggle('[data-close-date]',!cap,e.closes_at);toggle('[data-close-limit]',!cash&&cap&&shared,e.participation_limit);
    $('[data-close-note]',rf).textContent=cap?(shared?'Finaliza al alcanzar el total de participaciones pagadas indicado.':'Finaliza al pagar todos los números.'):'Finaliza a la fecha y hora anunciadas (Ecuador).';
    const product=$('[data-product-fields]',rf);product.hidden=cash;$$('input,textarea',product).forEach(el=>el.disabled=cash);e.title.required=!cash;
    toggle('[data-money-fields]',cash);toggle('[data-ticket-count]',!cash||shared,e.ticket_count);
    $('[data-number-price]',rf).classList.toggle('single',cash&&!shared);
    $('[data-price-label]',rf).textContent=cash?'Precio por participación (automático)':'Valor del boleto ($)';e.price.readOnly=cash;
    updatePotential();
}
function wizardShow(step,focus=true){
    wizardStep=step;$$('[data-raffle-step]',rf).forEach(el=>el.hidden=Number(el.dataset.raffleStep)!==step);
    $$('[data-step-indicator]',rf).forEach(el=>{const n=Number(el.dataset.stepIndicator);el.classList.toggle('complete',n<step);if(n===step)el.setAttribute('aria-current','step');else el.removeAttribute('aria-current');});
    $('[data-wizard-back]',rf).hidden=step===1;$('[data-wizard-next]',rf).hidden=step!==2;
    const submit=$('button[type=submit]',rf);submit.hidden=step!==3;submit.disabled=step!==3;
    if(focus){const h=$(`[data-raffle-step="${step}"] h3`,rf);h.focus({preventScroll:true});$('#raffle-dialog').scrollTop=0;}
}
function validateRaffle(){
    const e=rf.elements;updatePotential();e.closes_at.setCustomValidity('');
    if(!e.closes_at.disabled&&e.closes_at.value&&Date.parse(e.closes_at.value+'-05:00')<=Date.now())e.closes_at.setCustomValidity('Selecciona una fecha y hora futuras (Ecuador).');
    const fields=$$('input,select,textarea',$('[data-raffle-step="2"]',rf));
    for(const field of fields){if(field.disabled||!field.willValidate)continue;if(!field.checkValidity()){wizardShow(2);field.reportValidity();return false;}}
    if(e.type.value==='dinero'&&(!moneyCents(e.money_amount.value)||!integerValue(e.pricing_participations.value)||!moneyCents(e.price.value))){wizardShow(2);showClientNotice($('.dialog-body',rf),'Ingresa un monto válido y la cantidad de participaciones.');return false;}
    return true;
}
function buildSummary(){
    const e=rf.elements,cash=e.type.value==='dinero',shared=e.participation_mode.value==='compartido',cap=e.close_mode.value==='capacidad',amount=moneyCents(e.money_amount.value),quantity=integerValue(e.pricing_participations.value),details=$('[data-summary-details]',rf);
    $('[data-summary-title]',rf).textContent=cash?cashTitle(amount):e.title.value.trim();
    $('[data-summary-description]',rf).textContent=cash?`Premio en efectivo de ${cashLabel(amount)}. ${shared?'El importe se divide entre las cuentas titulares pagadas del número ganador.':'El titular pagado recibe el importe total.'}`:e.description.value.trim();
    const photos=$('[data-summary-photos]',rf);photos.replaceChildren();
    const addPhoto=(src,alt)=>{const img=document.createElement('img');img.src=src;img.alt=alt;photos.append(img);};
    if(cash)addPhoto('assets/premio-dinero.svg','Monedas de oro');else $$('.photo-box',rf).forEach(box=>{const img=$('.preview',box),file=$('input[type=file]',box),remove=$('input[type=checkbox]',box);if(img.getAttribute('src')&&!img.hidden&&(!remove.checked||file.files.length))addPhoto(img.src,`Fotografía ${photos.children.length+1}`);});
    photos.hidden=!photos.children.length;
    const rows=[['Tipo de premio',cash?'Dinero':'Producto físico'],['Modalidad',shared?'Números compartidos':'Números exclusivos']];
    if(cash||shared)rows.push([cash?'Monto del premio':'Equivalente económico',cashLabel(cash?amount:moneyCents(e.prize_value.value))]);
    if(cash)rows.push(['Participaciones previstas',quantity.toLocaleString('es-EC')]);
    rows.push(['Cantidad de números',Number(e.ticket_count.value).toLocaleString('es-EC')],['Precio por participación',cashLabel(moneyCents(e.price.value))],['Condición de finalización',cap?`Capacidad: ${Number(shared?e.participation_limit.value:e.ticket_count.value).toLocaleString('es-EC')} pagadas`:`Fecha: ${e.closes_at.value.replace('T',' ')} (Ecuador)`],[$('[data-potential-label]',rf).textContent,$('#potential').textContent]);
    details.replaceChildren();for(const [key,value] of rows){const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=key;dd.textContent=value;details.append(dt,dd);}
    const note=$('[data-summary-warning]',rf);note.textContent=[cash&&!cap&&shared?'El ingreso es estimado, no garantizado: la cantidad de participaciones solo se usa para calcular el precio.':(!cap?'La fecha puede llegar antes de completar la venta.':''),$('[data-rounding-note]',rf).hidden?'':$('[data-rounding-note]',rf).textContent].filter(Boolean).join(' ');
}
function wizardChoose(type){
    if(wizardStep!==1||!type)return;
    if(type!==lastPrizeType){if(lastPrizeType==='producto')productPrice=rf.elements.price.value;rf.elements.participation_mode.value=type==='dinero'?'compartido':'exclusivo';if(type==='producto')rf.elements.price.value=productPrice;lastPrizeType=type;}
    refreshRaffleSettings();wizardShow(2);
}
function wizardReview(){if(validateRaffle()){buildSummary();wizardShow(3);}}
function photoOrder(){const boxes=$$('.photo-box',rf);rf.elements.photo_order.value=boxes.map(b=>b.dataset.photoSlot).join(',');boxes.forEach((b,i)=>{$('[data-photo-position]',b).textContent=i+1;$('[data-photo-move="-1"]',b).disabled=i===0;$('[data-photo-move="1"]',b).disabled=i===boxes.length-1;});}
function resetPhotoOrder(){const grid=$('.photo-grid',rf);$$('.photo-box',grid).sort((a,b)=>Number(a.dataset.photoSlot)-Number(b.dataset.photoSlot)).forEach(b=>grid.append(b));photoOrder();}
function movePhoto(box,delta){const boxes=$$('.photo-box',rf),i=boxes.indexOf(box),target=boxes[i+delta];if(!target)return;const grid=box.parentElement;grid.insertBefore(box,delta<0?target:target.nextSibling);photoOrder();}
function clearPreviews(){if(!rf)return;for(const u of previewUrls.values())URL.revokeObjectURL(u);previewUrls.clear();$$('.photo-box',rf).forEach(box=>{const img=$('.preview',box);img.onload=null;img.onerror=null;img.removeAttribute('src');img.hidden=true;$('.remove',box).hidden=true;});}
function resetRaffle(r){
    if(!rf)return;$$('[data-client-notice]',rf).forEach(n=>n.remove());rf.reset();resetPhotoOrder();clearPreviews();const e=rf.elements;
    e.raffle_id.value=r?.id||0;$('#raffle-title').textContent=r?'Editar sorteo':'Crear sorteo';$('button[type=submit]',rf).textContent=r?'Guardar cambios':'Crear sorteo';lastPrizeType=r?.type||'';productPrice='1.00';
    if(r){for(const k of ['title','description','type','ticket_count'])e[k].value=r[k];e.price.value=(Number(r.ticket_price_cents)/100).toFixed(2);if(r.type==='producto')productPrice=e.price.value;e.participation_mode.value=r.participation_mode||'exclusivo';const amount=r.prize_cents==null?'':(Number(r.prize_cents)/100).toFixed(2);e.prize_value.value=r.type==='producto'?amount:'';e.money_amount.value=r.type==='dinero'?amount:'';e.pricing_participations.value=r.pricing_participations||(r.close_mode==='capacidad'?r.participation_limit:r.ticket_count)||100;e.close_mode.value=r.close_mode||'fecha';e.participation_limit.value=r.participation_limit||r.ticket_count;e.closes_at.value=r.closes_at?new Date(Number(r.closes_at)*1000-5*3600000).toISOString().slice(0,16):'';if(r.type==='producto')$$('.photo-box',rf).forEach(box=>{const img=$('.preview',box);img.onload=()=>{img.hidden=false;$('.remove',box).hidden=false;};img.onerror=()=>{img.hidden=true;$('.remove',box).hidden=true;};img.src=photoUrl(r.id,Number(box.dataset.photoSlot));});}
    refreshRaffleSettings();wizardShow(r?2:1,false);
}
function resetParticipant(p){if(!pf)return;pf.reset();pf.elements.participant_id.value=p?.id||0;$('#participant-title').textContent=p?'Editar participante':'Registrar participante';for(const k of ['name','email','phone','ticket_number','payment_status'])if(p)pf.elements[k].value=p[k];if(pf.elements.link_user){pf.elements.link_user.checked=Boolean(p?.user_id);pf.elements.link_user.disabled=Boolean(p?.user_id);}}
function show(id){const d=document.getElementById(id);if(d&&!d.open)d.showModal();}
function viewRaffle(r){if(!r)return;$('#view-title').textContent=r.title;$('#view-description').textContent=r.description||'Sin descripción.';$('#view-info').textContent=`${r.type} · ${r.status} · ${r.ticket_count} boletos · ${money(Number(r.ticket_price_cents)/100)} por boleto`;const root=$('#view-photos');root.replaceChildren();for(let i=1;i<=3;i++){const img=document.createElement('img');img.alt=`Foto ${i}`;img.hidden=true;img.onload=()=>img.hidden=false;img.onerror=()=>img.remove();img.src=photoUrl(r.id,i);root.append(img);}show('view-dialog');}
document.addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;if(b.hasAttribute('data-dismiss-notice')){b.closest('[data-notice]')?.remove();return;}if(b.dataset.open){if(b.dataset.open==='raffle-dialog')resetRaffle(null);if(b.dataset.open==='participant-dialog')resetParticipant(null);show(b.dataset.open);}if(b.hasAttribute('data-close'))b.closest('dialog')?.close();if(b.dataset.editRaffle){const r=safeJson(b.dataset.editRaffle);if(r){resetRaffle(r);show('raffle-dialog');}}if(b.dataset.viewRaffle)viewRaffle(safeJson(b.dataset.viewRaffle));if(b.dataset.editParticipant){const p=safeJson(b.dataset.editParticipant);if(p){resetParticipant(p);show('participant-dialog');}}});
// Shared dismissible notifications and confirmations.
function showClientNotice(root,message,kind='error'){
    if(!root)return;
    const old=$('[data-client-notice]',root);if(old)old.remove();
    const n=document.createElement('div');n.className='notice '+kind;n.dataset.notice='';n.dataset.clientNotice='';n.setAttribute('role',kind==='error'||kind==='warning'?'alert':'status');
    const label=document.createElement('span');label.className='notice-text';label.textContent=message;
    const close=document.createElement('button');close.type='button';close.className='notice-close';close.dataset.dismissNotice='';close.setAttribute('aria-label','Cerrar mensaje');close.title='Cerrar mensaje';close.textContent='×';
    n.append(label,close);root.prepend(n);n.scrollIntoView({block:'nearest'});
}
const confirmDialog=document.createElement('dialog');confirmDialog.id='action-confirm-dialog';confirmDialog.setAttribute('aria-labelledby','action-confirm-title');
confirmDialog.innerHTML='<div class="dialog-head"><h2 id="action-confirm-title">Confirmar operación</h2><button type="button" class="close" data-close aria-label="Cerrar y cancelar" title="Cerrar y cancelar">×</button></div><div class="dialog-body"><p data-confirm-message></p></div><div class="dialog-foot"><button type="button" class="btn secondary" data-close>Cancelar</button><button type="button" class="btn primary" data-confirm-accept>Confirmar</button></div>';
document.body.append(confirmDialog);
let pendingConfirmation=null;const confirmedForms=new WeakSet();
confirmDialog.addEventListener('close',()=>{if(!confirmDialog.open)pendingConfirmation=null;});
$('[data-confirm-accept]',confirmDialog).addEventListener('click',()=>{
    const pending=pendingConfirmation;pendingConfirmation=null;confirmDialog.close();if(!pending||!pending.form.isConnected)return;
    confirmedForms.add(pending.form);try{if(pending.submitter)pending.form.requestSubmit(pending.submitter);else pending.form.requestSubmit();}finally{confirmedForms.delete(pending.form);}
});
document.addEventListener('submit',e=>{
    const form=e.target,text=form.dataset.confirm;if(!text||confirmedForms.has(form))return;
    if(typeof confirmDialog.showModal!=='function'){if(!window.confirm(text))e.preventDefault();return;}
    e.preventDefault();pendingConfirmation={form,submitter:e.submitter};$('[data-confirm-message]',confirmDialog).textContent=text;
    if(!confirmDialog.open)confirmDialog.showModal();
});
$$('[data-search]').forEach(input=>input.addEventListener('input',()=>{const t=document.getElementById(input.dataset.search),needle=input.value.trim().toLocaleLowerCase();if(t)$$('tbody tr',t).forEach(row=>row.hidden=!row.textContent.toLocaleLowerCase().includes(needle));}));
if(rf){
    rf.noValidate=true;
    rf.addEventListener('input',updatePotential);
    rf.addEventListener('change',e=>{if(e.target.name==='type')wizardChoose(e.target.value);if(['participation_mode','close_mode'].includes(e.target.name))refreshRaffleSettings();});
    rf.addEventListener('click',e=>{if(e.target.matches('input[name=type]'))wizardChoose(e.target.value);});
    $('[data-wizard-back]',rf).addEventListener('click',()=>wizardShow(wizardStep-1));
    $('[data-wizard-next]',rf).addEventListener('click',wizardReview);
    rf.addEventListener('submit',e=>{if(wizardStep!==3){e.preventDefault();if(wizardStep===2)wizardReview();return;}if(!validateRaffle())e.preventDefault();else $('button[type=submit]',rf).disabled=true;});
    const grid=$('.photo-grid',rf);let dragging=null;grid.addEventListener('click',e=>{const b=e.target.closest('[data-photo-move]');if(b)movePhoto(b.closest('.photo-box'),Number(b.dataset.photoMove));});grid.addEventListener('dragstart',e=>{dragging=e.target.closest('.photo-box');if(dragging&&e.dataTransfer)e.dataTransfer.setData('text/plain',dragging.dataset.photoSlot);});grid.addEventListener('dragover',e=>{if(dragging&&e.target.closest('.photo-box'))e.preventDefault();});grid.addEventListener('drop',e=>{const target=e.target.closest('.photo-box');if(!dragging||!target||dragging===target)return;e.preventDefault();const boxes=$$('.photo-box',grid);grid.insertBefore(dragging,boxes.indexOf(dragging)<boxes.indexOf(target)?target.nextSibling:target);photoOrder();dragging=null;});grid.addEventListener('dragend',()=>{dragging=null;});photoOrder();refreshRaffleSettings();wizardShow(1,false);$$('input[type=file]',rf).forEach(input=>input.addEventListener('change',()=>{const img=$('.preview',input.closest('.photo-box'));const old=previewUrls.get(input);if(old)URL.revokeObjectURL(old);const f=input.files[0];if(!f){img.removeAttribute('src');img.hidden=true;return;}if(f.size>2097152){input.value='';previewUrls.delete(input);img.removeAttribute('src');img.hidden=true;showClientNotice($('.dialog-body',rf),'Cada foto debe pesar máximo 2 MB.');return;}const u=URL.createObjectURL(f);previewUrls.set(input,u);img.onload=()=>img.hidden=false;img.onerror=()=>img.hidden=true;img.src=u;}));$('#raffle-dialog').addEventListener('close',clearPreviews);}

// Mobile navigation: close button, backdrop, links and Escape.
(()=>{
    const sidebar=$('#sidebar'),toggle=$('#menu-toggle'),close=$('#sidebar-close'),overlay=$('#sidebar-overlay'),main=$('.shell>main');
    if(!sidebar||!toggle||!close||!overlay||!main)return;
    const mobile=window.matchMedia('(max-width: 760px)');
    const isOpen=()=>sidebar.classList.contains('open');
    function setOpen(value,restoreFocus=false){
        const open=mobile.matches&&value;
        if(!open&&restoreFocus&&mobile.matches){main.inert=false;toggle.focus();}
        sidebar.classList.toggle('open',open);
        toggle.setAttribute('aria-expanded',String(open));
        overlay.hidden=!open;
        main.inert=open;
        sidebar.inert=mobile.matches&&!open;
        document.body.classList.toggle('mobile-menu-open',open);
        if(open)close.focus();
    }
    toggle.addEventListener('click',()=>setOpen(!isOpen(),isOpen()));
    close.addEventListener('click',()=>setOpen(false,true));
    overlay.addEventListener('click',()=>setOpen(false,true));
    sidebar.addEventListener('click',e=>{if(mobile.matches&&e.target.closest('a'))setOpen(false,true);});
    document.addEventListener('keydown',e=>{if(e.key==='Escape'&&isOpen()){e.preventDefault();setOpen(false,true);}});
    mobile.addEventListener('change',()=>setOpen(false,mobile.matches&&sidebar.contains(document.activeElement)));
    setOpen(false);
})();
