'use strict';
// SGA-style off-canvas navigation, independent from the right-hand course panel.
(() => {
    const root = document.documentElement;
    const sidebar = document.getElementById('ve-sidebar');
    const menu = sidebar?.querySelector('.ve-menu');
    const openButton = document.getElementById('ve-menu-open');
    const closeButton = document.getElementById('ve-menu-close');
    const scrim = document.getElementById('ve-menu-scrim');
    const topbar = openButton?.closest('.ve-mobile-topbar');
    const workspace = document.querySelector('.ve-workspace');
    if (!sidebar || !menu || !openButton || !closeButton || !scrim || !topbar || !workspace) return;
    const mobile = window.matchMedia('(max-width: 900px)');
    const isOpen = () => root.classList.contains('ve-nav-open');
    const setMenu = opened => {
        opened = Boolean(opened && mobile.matches);
        root.classList.toggle('ve-nav-open', opened);
        openButton.setAttribute('aria-expanded', String(opened));
        sidebar.inert = mobile.matches && !opened;
        if (sidebar.inert) sidebar.setAttribute('aria-hidden', 'true');
        else sidebar.removeAttribute('aria-hidden');
        if (opened) {
            sidebar.setAttribute('role', 'dialog');
            sidebar.setAttribute('aria-modal', 'true');
        } else {
            sidebar.removeAttribute('role');
            sidebar.removeAttribute('aria-modal');
        }
        topbar.inert = opened;
        workspace.inert = opened;
        menu.open = true;
    };
    const close = (restoreFocus = true) => {
        const wasOpen = isOpen();
        setMenu(false);
        if (wasOpen && restoreFocus && mobile.matches) openButton.focus({preventScroll:true});
    };
    openButton.addEventListener('click', () => {
        if (!mobile.matches || isOpen()) return;
        setMenu(true);
        requestAnimationFrame(() => { if (isOpen()) closeButton.focus({preventScroll:true}); });
    });
    closeButton.addEventListener('click', () => close());
    scrim.addEventListener('click', () => close());
    sidebar.addEventListener('click', event => {
        if (!isOpen() || event.ctrlKey || event.metaKey || event.altKey || event.shiftKey) return;
        if (event.target.closest('a[href]')) close();
    }, true);
    document.addEventListener('keydown', event => {
        if (!isOpen()) return;
        if (event.key === 'Escape') { event.preventDefault(); close(); return; }
        if (event.key !== 'Tab') return;
        const items = [...sidebar.querySelectorAll('a[href], button:not([disabled]), summary, [tabindex="0"]')].filter(node => node.getClientRects().length && !node.closest('[inert]') && getComputedStyle(node).visibility === 'visible');
        if (!items.length) { event.preventDefault(); return; }
        const first = items[0], last = items[items.length-1];
        if (event.shiftKey && (document.activeElement === first || !sidebar.contains(document.activeElement))) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && (document.activeElement === last || !sidebar.contains(document.activeElement))) { event.preventDefault(); first.focus(); }
    });
    const sync = () => close(false);
    if (mobile.addEventListener) mobile.addEventListener('change', sync);
    else if (mobile.addListener) mobile.addListener(sync);
    root.classList.add('ve-nav-ready');
    sync();
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
