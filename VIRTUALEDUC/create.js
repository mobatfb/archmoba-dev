'use strict';
document.addEventListener('click', event => {
    const button = event.target.closest('button');
    if (!button) return;
    if (button.dataset.veOpen) {
        const dialog = document.getElementById(button.dataset.veOpen);
        if (dialog && !dialog.open) dialog.showModal();
        return;
    }
    const dialog = button.closest('dialog');
    if (!dialog) return;
    if (button.hasAttribute('data-ve-close')) dialog.close();
    if (button.dataset.veTab) {
        for (const tab of dialog.querySelectorAll('[data-ve-tab]')) tab.setAttribute('aria-selected', String(tab === button));
        for (const panel of dialog.querySelectorAll('[data-ve-panel]')) panel.hidden = panel.dataset.vePanel !== button.dataset.veTab;
    }
});

// Shared create/edit pricing fields.
function veSyncCourseAccess(block) {
    const model=block.querySelector('[data-ve-access-model]');
    const wrap=block.querySelector('[data-ve-access-price]');
    const input=wrap.querySelector('input');
    const paid=model.value!=='free';
    wrap.hidden=!paid;
    input.disabled=!paid;
    input.required=paid;
    input.min=paid?'0.01':'0';
    block.querySelector('[data-ve-price-label]').textContent=model.value==='free_paid_certificate'?'Valor del certificado (USD)':'Valor del curso con certificado (USD)';
    block.querySelector('[data-ve-access-description]').textContent={
        free:'Acceso al contenido y certificado sin costo.',
        free_paid_certificate:'Acceso gratuito al contenido. Se paga únicamente por el certificado.',
        paid_included:'Un único pago cubre el contenido e incluye el certificado.'
    }[model.value]||'';
}
for(const block of document.querySelectorAll('[data-ve-course-access]')) {
    veSyncCourseAccess(block);
    block.querySelector('[data-ve-access-model]').addEventListener('change',()=>veSyncCourseAccess(block));
    block.closest('form')?.addEventListener('reset',()=>setTimeout(()=>veSyncCourseAccess(block),0));
}
