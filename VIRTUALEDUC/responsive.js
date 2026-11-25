'use strict';
(() => {
    const menu = document.querySelector('.ve-menu');
    if (!menu) return;
    const mobile = window.matchMedia('(max-width: 900px)');
    const sync = () => { menu.open = !mobile.matches; };
    sync();
    if (mobile.addEventListener) mobile.addEventListener('change', sync);
    else if (mobile.addListener) mobile.addListener(sync);
    menu.addEventListener('click', event => {
        if (mobile.matches && event.target.closest('nav a')) menu.open = false;
    });
})();

// Reuse the desktop aside in a native modal on compact screens; no duplicated content.
(() => {
    const toggle = document.getElementById('ve-course-drawer-toggle');
    const drawer = document.getElementById('ve-course-drawer');
    const aside = document.getElementById('ve-course-aside');
    const body = document.getElementById('ve-course-drawer-body');
    const closeButton = document.getElementById('ve-course-drawer-close');
    if (!toggle || !drawer || !aside || !body || !closeButton || typeof drawer.showModal !== 'function') return;
    const layout = aside.parentElement;
    const mobile = window.matchMedia('(max-width: 900px)');
    layout.classList.add('ve-course-drawer-ready');
    const restore = () => {
        if (drawer.open) return;
        if (aside.parentElement !== layout) layout.append(aside);
        toggle.setAttribute('aria-expanded', 'false');
        document.documentElement.classList.remove('ve-course-drawer-open');
    };
    const close = () => {
        if (drawer.open) drawer.close();
        restore();
    };
    const sync = () => {
        if (!mobile.matches) close();
        toggle.hidden = !mobile.matches;
    };
    toggle.addEventListener('click', () => {
        if (!mobile.matches || drawer.open) return;
        body.append(aside);
        try { drawer.showModal(); } catch (error) { restore(); return; }
        toggle.setAttribute('aria-expanded', 'true');
        document.documentElement.classList.add('ve-course-drawer-open');
        closeButton.focus();
    });
    closeButton.addEventListener('click', close);
    drawer.addEventListener('close', restore);
    drawer.addEventListener('click', event => {
        if (event.target !== drawer) return;
        const rect = drawer.getBoundingClientRect();
        if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) close();
    });
    if (mobile.addEventListener) mobile.addEventListener('change', sync);
    else if (mobile.addListener) mobile.addListener(sync);
    sync();
})();
