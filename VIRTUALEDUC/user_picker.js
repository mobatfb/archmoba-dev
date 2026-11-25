'use strict';
// Shared avatars for asynchronous people searches; the server supplies only authorized URLs.
function vePreviewAvatar(person) {
    const avatar = document.createElement('span'); avatar.className = 've-person-avatar ve-avatar-preview'; avatar.setAttribute('aria-hidden','true');
    const initials = document.createElement('span'); initials.textContent = person.initials || 'U'; avatar.append(initials);
    if (typeof person.avatar === 'string' && person.avatar.startsWith('?profile_photo=1&')) {
        const photo = document.createElement('img'); photo.alt = ''; photo.loading = 'lazy'; photo.decoding = 'async'; photo.width = photo.height = 42;
        photo.addEventListener('error', () => photo.remove(), {once:true}); photo.src = person.avatar; avatar.append(photo);
    }
    return avatar;
}
(() => {
    for (const picker of document.querySelectorAll('[data-ve-user-picker]')) {
        const input = picker.querySelector('input:not([type=hidden])'), results = picker.querySelector('[data-ve-picker-results]');
        if (!results) continue;
        const list = picker.querySelector('[data-ve-picker-list]'), status = picker.querySelector('[data-ve-picker-status]'), selected = picker.querySelector('[data-ve-picker-selected]');
        const courseSelect = picker.closest('form').querySelector('select[name="id_curso"]');
        const multiple = picker.hasAttribute('data-ve-picker-multiple');
        const selectedValues = () => [...selected.querySelectorAll('input[type=hidden]')].map(node => node.value);
        const validate = () => { if(multiple) input.setCustomValidity(selectedValues().length ? '' : 'Selecciona al menos un responsable.'); };
        const limit = Number(picker.dataset.vePickerLimit || 50);
        let controller, timer, revision = 0;
        const cancel = () => { clearTimeout(timer); if (controller) controller.abort(); ++revision; };
        const close = () => { cancel(); results.hidden = true; };
        const clearSelection = () => { selected.hidden = true; selected.replaceChildren(); };
        const choose = person => {
            if (multiple) {
                const values = selectedValues();
                if (values.includes(person.username)) return;
                if (values.length >= limit) { status.textContent = 'Máximo '+limit+' responsables.'; return; }
                const row = document.createElement('div'); row.className='ve-picker-selected'; row.dataset.veResponsibleRow='';
                const hidden=document.createElement('input'); hidden.type='hidden'; hidden.name='usuarios_responsables[]'; hidden.value=person.username;
                const name=document.createElement('strong'); name.textContent=person.name;
                const remove=document.createElement('button'); remove.type='button'; remove.className='ve-quiet ve-responsible-remove'; remove.dataset.veResponsibleRemove=''; remove.setAttribute('aria-label','Quitar responsable'); remove.textContent='×';
                row.append(hidden,vePreviewAvatar(person),name,remove); selected.append(row);
                input.value=''; validate(); input.focus(); close(); return;
            }
            input.value = person.username;
            const name = document.createElement('strong'); name.textContent = person.name;
            selected.replaceChildren(vePreviewAvatar(person),name); selected.hidden = false;
            input.focus(); close();
        };
        async function search() {
            cancel(); const request = revision;
            results.hidden = false; list.replaceChildren();
            const kind = picker.dataset.veUserPicker, course = courseSelect ? courseSelect.value : picker.dataset.vePickerCourse;
            if (kind === 'student' && (!course || course === '0')) { status.textContent = 'Selecciona primero un curso.'; return; }
            status.textContent = 'Buscando usuarios...'; controller = new AbortController();
            try {
                const params = new URLSearchParams({user_picker:kind,q:input.value.trim(),course_id:course});
                const response = await fetch('index.php?'+params,{credentials:'same-origin',cache:'no-store',signal:controller.signal});
                if (!response.ok) throw Error('Búsqueda no disponible');
                const data = await response.json(); if (request !== revision) return;
                status.textContent = data.people.length ? (data.more ? 'Primeros 30 resultados. Escribe para acotar la búsqueda.' : 'Selecciona un usuario.') : 'No se encontraron usuarios disponibles.';
                const people=multiple?data.people.filter(person=>!selectedValues().includes(person.username)):data.people;
                if(multiple && !people.length) status.textContent=data.more?'Escribe para buscar otros responsables.':'No hay más usuarios disponibles.';
                for (const person of people) {
                    const button = document.createElement('button'); button.type='button'; button.className='ve-picker-person';
                    const info=document.createElement('span'), name=document.createElement('strong'), user=document.createElement('small');
                    name.textContent=person.name; user.textContent=person.username; info.append(name,user);
                    button.append(vePreviewAvatar(person),info); button.addEventListener('click',()=>choose(person)); list.append(button);
                }
            } catch(error) { if (request === revision && error.name !== 'AbortError') status.textContent = 'No se pudo buscar. Intenta nuevamente.'; }
        }
        if (multiple) {
            validate();
            selected.addEventListener('click',event=>{
                const remove=event.target.closest('[data-ve-responsible-remove]');
                if(!remove) return;
                remove.closest('[data-ve-responsible-row]').remove(); validate();
                input.focus(); search();
            });
            picker.closest('form').addEventListener('reset',()=>setTimeout(validate,0));
        }
        input.addEventListener('focus',search);
        input.addEventListener('input',()=>{ if(!multiple) clearSelection(); cancel(); list.replaceChildren(); results.hidden=false; status.textContent='Buscando usuarios...'; timer=setTimeout(search,200); });
        if(courseSelect) courseSelect.addEventListener('change',()=>{input.value=''; clearSelection(); close();});
        picker.addEventListener('keydown',event=>{if(event.key==='Escape' && !results.hidden){event.preventDefault(); event.stopPropagation(); input.focus(); close();}});
        document.addEventListener('click',event=>{if(!picker.contains(event.target)) close();});
        const dialog=picker.closest('dialog'); if(dialog) dialog.addEventListener('close',close);
    }
    // Restore initials if a photo is removed or an authorized thumbnail cannot be served.
    const fallback = event => { if (event.target instanceof HTMLImageElement && event.target.parentElement?.classList.contains('ve-avatar-preview')) event.target.remove(); };
    document.addEventListener('error',fallback,true);
    for (const image of document.querySelectorAll('.ve-avatar-preview img')) if(image.complete && !image.naturalWidth) image.remove();
})();
