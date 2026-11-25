'use strict';
const $=(s,r=document)=>r.querySelector(s);
const $$=(s,r=document)=>[...r.querySelectorAll(s)];
const money=n=>new Intl.NumberFormat('es-EC',{style:'currency',currency:'USD'}).format(n);
const safeJson=s=>{try{return JSON.parse(s)}catch{return null}};
const rf=$('#raffle-form'),pf=$('#participant-form');
const photoUrl=(id,slot)=>`index.php?photo=${encodeURIComponent(id)}&slot=${slot}`;
const previewUrls=new Map();
function updatePotential(){if(!rf)return;const n=Number(rf.elements.ticket_count.value),p=Number(rf.elements.price.value);$('#potential').textContent=money(Math.max(0,n||0)*Math.max(0,p||0));}
function clearPreviews(){if(!rf)return;for(const u of previewUrls.values())URL.revokeObjectURL(u);previewUrls.clear();$$('.photo-box',rf).forEach(box=>{const img=$('.preview',box);img.removeAttribute('src');img.hidden=true;$('.remove',box).hidden=true;});}
function resetRaffle(r){if(!rf)return;$$('[data-client-notice]',rf).forEach(n=>n.remove());rf.reset();clearPreviews();rf.elements.raffle_id.value=r?.id||0;$('#raffle-title').textContent=r?'Editar sorteo':'Crear sorteo';if(r){for(const k of ['title','description','type','ticket_count'])rf.elements[k].value=r[k];rf.elements.price.value=(Number(r.ticket_price_cents)/100).toFixed(2);$$('.photo-box',rf).forEach((box,i)=>{const img=$('.preview',box);img.onload=()=>{img.hidden=false;$('.remove',box).hidden=false;};img.onerror=()=>{img.hidden=true;$('.remove',box).hidden=true;};img.src=photoUrl(r.id,i+1);});}updatePotential();}
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
if(rf){rf.addEventListener('input',updatePotential);$$('input[type=file]',rf).forEach(input=>input.addEventListener('change',()=>{const img=$('.preview',input.closest('.photo-box'));const old=previewUrls.get(input);if(old)URL.revokeObjectURL(old);const f=input.files[0];if(!f){img.removeAttribute('src');img.hidden=true;return;}if(f.size>2097152){input.value='';previewUrls.delete(input);img.removeAttribute('src');img.hidden=true;showClientNotice($('.dialog-body',rf),'Cada foto debe pesar máximo 2 MB.');return;}const u=URL.createObjectURL(f);previewUrls.set(input,u);img.onload=()=>img.hidden=false;img.onerror=()=>img.hidden=true;img.src=u;}));$('#raffle-dialog').addEventListener('close',clearPreviews);}

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
