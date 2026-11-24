'use strict';
(() => {
    for (const notice of document.querySelectorAll('.notice')) {
        if (notice.classList.contains('ve-dismissible')) continue;
        const content = document.createElement('div');
        content.className = 've-notice-content';
        content.setAttribute('role', notice.classList.contains('error') ? 'alert' : 'status');
        while (notice.firstChild) content.appendChild(notice.firstChild);
        const close = document.createElement('button');
        close.type = 'button';
        close.className = 've-notice-close';
        close.textContent = '\u00d7';
        close.setAttribute('aria-label', 'Cerrar aviso');
        close.title = 'Cerrar aviso';
        close.addEventListener('click', () => notice.remove());
        notice.classList.add('ve-dismissible');
        notice.append(content, close);
    }
})();
