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
