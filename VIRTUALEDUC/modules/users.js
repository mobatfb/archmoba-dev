'use strict';
(() => {
    const root = document.querySelector('[data-ve-users]');
    if (!root) return;
    const form = root.querySelector('.ve-users-filters');
    const search = form.elements.q;
    const role = form.elements.role;
    const count = root.querySelector('[data-ve-user-count]');
    const empty = root.querySelector('[data-ve-users-empty]');
    const normalize = value => value.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase().trim();
    const records = Array.from(root.querySelectorAll('tr[data-ve-user-role]'), row => ({
        row,
        role: row.dataset.veUserRole,
        text: normalize(Array.from(row.cells).slice(0, 4).map(cell => cell.textContent).join(' '))
    }));
    const apply = () => {
        const q = normalize(search.value);
        let visible = 0;
        for (const item of records) {
            const match = (!role.value || item.role === role.value) && item.text.includes(q);
            item.row.hidden = !match;
            if (match) visible++;
        }
        count.textContent = String(visible);
        empty.hidden = visible !== 0;
    };
    search.addEventListener('input', apply);
    role.addEventListener('change', apply);
    form.addEventListener('submit', event => { event.preventDefault(); apply(); });
    root.querySelector('.ve-users-clear').addEventListener('click', event => {
        if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        search.value = '';
        role.value = '';
        apply();
        search.focus();
    });
    apply();
})();
