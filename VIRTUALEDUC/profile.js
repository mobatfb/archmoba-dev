'use strict';
(() => {
    const dialog = document.getElementById('ve-profile-dialog');
    const link = document.querySelector('[data-ve-profile-open]');
    if (dialog && link && typeof dialog.showModal === 'function') {
        link.addEventListener('click', event => {
            if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
            event.preventDefault();
            if (!dialog.open) dialog.showModal();
        });
    }
    for (const form of document.querySelectorAll('.ve-profile-remove')) {
        form.addEventListener('submit', event => {
            if (!window.confirm('¿Eliminar la foto y volver a mostrar tus iniciales?')) event.preventDefault();
        });
    }
})();
