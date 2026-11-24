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
