'use strict';
(() => {
    const dialog = document.querySelector('#edit-course-dialog[data-ve-edit-auto]');
    if (dialog && !dialog.open && typeof dialog.showModal === 'function') dialog.showModal();
})();
