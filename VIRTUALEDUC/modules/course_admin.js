'use strict';
(() => {
    const menu = document.querySelector('[data-ve-course-admin]');
    if (!menu) return;
    document.addEventListener('click', event => {
        if (!menu.contains(event.target) || event.target.closest('[data-ve-open]')) menu.open = false;
    });
    menu.addEventListener('keydown', event => {
        if (event.key === 'Escape' && menu.open) { menu.open = false; menu.querySelector('summary').focus(); }
    });
    const dialog = document.getElementById('course-enroll-dialog');
    if (!dialog) return;
    const get = key => dialog.querySelector('[data-ve-enroll-' + key + ']');
    const search = get('search'), available = get('available'), selected = get('selected');
    const status = get('status'), prev = get('prev'), next = get('next'), submit = get('submit');
    const limit = Number(dialog.dataset.veLimit);
    const chosen = new Map();
    let rows = [], page = 1, more = false, controller, revision = 0, timer;
    const message = value => { const p = document.createElement('p'); p.className = 'muted'; p.textContent = value; return p; };
    const item = (student, removing) => {
        const row = document.createElement('div'); row.className = 've-enroll-item';
        const info = document.createElement('span');
        const name = document.createElement('strong'); name.textContent = student.name;
        const user = document.createElement('small'); user.textContent = student.username;
        info.append(name,user);
        const button = document.createElement('button'); button.type = 'button';
        button.className = removing ? 've-quiet' : 've-enroll-add';
        button.textContent = removing ? 'Quitar' : 'Añadir';
        button.setAttribute('aria-label',(removing?'Quitar ':'Añadir ')+student.name);
        button.disabled = !removing && chosen.size >= limit;
        button.addEventListener('click', () => {
            if (removing) chosen.delete(student.id);
            else if (chosen.size < limit) chosen.set(student.id,student);
            render();
        });
        row.append(vePreviewAvatar(student),info,button); return row;
    };
    function render() {
        const candidates = rows.filter(student => !chosen.has(student.id));
        available.replaceChildren(...candidates.map(student => item(student,false)));
        if (!candidates.length) available.append(message('No hay estudiantes disponibles en esta página.'));
        selected.replaceChildren(...Array.from(chosen.values(), student => item(student,true)));
        if (!chosen.size) selected.append(message('No has seleccionado estudiantes.'));
        get('inputs').replaceChildren(...Array.from(chosen.keys(), id => {
            const input = document.createElement('input'); input.type='hidden'; input.name='student_ids[]'; input.value=id; return input;
        }));
        get('count').textContent = String(chosen.size);
        submit.disabled = !chosen.size;
        submit.textContent = 'Matricular ('+chosen.size+')';
        get('page').textContent = 'Página '+page;
    }
    async function load(target = 1) {
        clearTimeout(timer);
        if (controller) controller.abort();
        controller = new AbortController();
        const id = ++revision;
        prev.disabled = next.disabled = true;
        status.textContent = 'Buscando estudiantes...';
        rows = []; render();
        try {
            const params = new URLSearchParams({course_candidates:dialog.dataset.veCourseId,q:search.value.trim(),candidate_page:String(target)});
            const response = await fetch('index.php?'+params,{credentials:'same-origin',signal:controller.signal,cache:'no-store'});
            if (!response.ok) throw new Error('Solicitud no válida');
            const data = await response.json();
            if (id !== revision) return;
            rows = data.students; page = data.page; more = data.more;
            status.textContent = rows.length ? 'Estudiantes disponibles para matricular.' : 'No se encontraron estudiantes disponibles.';
            prev.disabled = page <= 1; next.disabled = !more;
            render();
        } catch (error) {
            if (id !== revision || error.name === 'AbortError') return;
            status.textContent = 'No se pudo cargar la lista. Vuelve a buscar.';
        }
    }
    menu.querySelector('[data-ve-open="course-enroll-dialog"]').addEventListener('click', () => {
        dialog.querySelector('[data-ve-tab="individual"]').click();
        chosen.clear(); search.value=''; rows=[]; page=1; load();
    });
    search.addEventListener('input', () => {
        clearTimeout(timer); if (controller) controller.abort(); ++revision;
        prev.disabled=next.disabled=true; rows=[]; render();
        timer=setTimeout(() => load(1),200);
    });
    prev.addEventListener('click', () => load(page-1));
    next.addEventListener('click', () => load(page+1));
    dialog.addEventListener('close', () => {
        const bulk = dialog.querySelector('[data-ve-enroll-csv]');
        bulk.reset();
        clearTimeout(timer); if (controller) controller.abort(); ++revision; chosen.clear(); rows=[]; render();
    });
    dialog.querySelector('[data-ve-enroll-manual]').addEventListener('submit', event => {
        if (!chosen.size) event.preventDefault();
        else { submit.disabled=true; submit.textContent='Matriculando...'; }
    });
})();
