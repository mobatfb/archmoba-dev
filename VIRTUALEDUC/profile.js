'use strict';
(() => {
    const dialog = document.getElementById('ve-profile-dialog');
    const link = document.querySelector('[data-ve-profile-open]');
    if (dialog && link && typeof dialog.showModal === 'function') {
        const profile = dialog.querySelector('[data-ve-profile-pane="profile"]');
        const password = dialog.querySelector('[data-ve-profile-pane="password"]');
        const form = password.querySelector('form');
        const title = document.getElementById('ve-profile-title');
        const change = dialog.querySelector('[data-ve-profile-password]');
        const show = (editing, focus = false) => {
            if (!editing) form.reset();
            profile.hidden = editing;
            password.hidden = !editing;
            title.textContent = editing ? 'Cambiar contraseña' : 'Mi perfil';
            if (focus) (editing ? form.elements.old_password : change).focus();
        };
        link.addEventListener('click', event => {
            if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
            event.preventDefault();
            if (!dialog.open) { show(false); dialog.showModal(); }
        });
        change.addEventListener('click', () => show(true, true));
        password.querySelector('[data-ve-profile-back]').addEventListener('click', () => show(false, true));
        dialog.addEventListener('close', () => show(false));
    }
    for (const form of document.querySelectorAll('.ve-profile-remove')) {
        form.addEventListener('submit', event => {
            if (!window.confirm('¿Eliminar la foto y volver a mostrar tus iniciales?')) event.preventDefault();
        });
    }
})();
