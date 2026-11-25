'use strict';
// Dialogs for the participant's active-raffle module only.
let raffleDialogTrigger=null;
document.addEventListener('click',event=>{
    const trigger=event.target.closest('[data-user-dialog]');
    if(!trigger)return;
    const dialog=document.getElementById(trigger.dataset.userDialog);
    if(!(dialog instanceof HTMLDialogElement)||dialog.open)return;
    const previous=trigger.closest('dialog');
    if(!previous)raffleDialogTrigger=trigger;
    if(previous?.open)previous.close();
    dialog.showModal();
});
document.querySelectorAll('.user-raffle-dialog').forEach(dialog=>{
    dialog.addEventListener('click',event=>{if(event.target===dialog){const r=dialog.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)dialog.close();}});
    dialog.addEventListener('close',()=>{if(!document.querySelector('.user-raffle-dialog[open]')&&raffleDialogTrigger){raffleDialogTrigger.focus();raffleDialogTrigger=null;}});
});
