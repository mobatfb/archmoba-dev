/* SGA UNEDID: navegacion movil y tablas adaptativas sin dependencias externas. */
(function () {
  'use strict';
  var root = document.documentElement;
  var menu = document.getElementById('sga-sidebar');
  var openButton = document.getElementById('sga-menu-open');
  var closeButton = document.getElementById('sga-menu-close');
  var scrim = document.getElementById('sga-menu-scrim');
  var mobile = window.matchMedia('(max-width: 760px)');
  var cards = window.matchMedia('(max-width: 620px)');
  var previousFocus = null;

  function markMenu(opened) {
    root.classList.toggle('sga-menu-open', opened && mobile.matches);
    if (openButton) openButton.setAttribute('aria-expanded', opened && mobile.matches ? 'true' : 'false');
    if (menu) {
      menu.inert = !opened && mobile.matches;
      menu.setAttribute('aria-hidden', !opened && mobile.matches ? 'true' : 'false');
    }
    if (scrim) scrim.setAttribute('aria-hidden', opened && mobile.matches ? 'false' : 'true');
  }
  function openMenu() {
    if (!menu || !mobile.matches) return;
    previousFocus = document.activeElement;
    markMenu(true);
    if (closeButton) closeButton.focus();
  }
  function closeMenu(restoreFocus) {
    var wasOpen = root.classList.contains('sga-menu-open');
    if (wasOpen && restoreFocus && openButton) openButton.focus();
    markMenu(false);
    if (wasOpen && restoreFocus && previousFocus && previousFocus !== openButton && typeof previousFocus.focus === 'function') {
      // El foco del usuario vuelve al boton de menu para que la pagina sea previsible.
      openButton.focus();
    }
  }
  if (menu && openButton) {
    openButton.addEventListener('click', openMenu);
    if (closeButton) closeButton.addEventListener('click', function () { closeMenu(true); });
    if (scrim) scrim.addEventListener('click', function () { closeMenu(true); });
    menu.querySelectorAll('nav a').forEach(function (link) {
      link.addEventListener('click', function () { closeMenu(false); });
      try {
        var linkUrl = new URL(link.href, location.href);
        var currentUrl = new URL(location.href);
        if (linkUrl.pathname === currentUrl.pathname && linkUrl.search === currentUrl.search) {
          link.setAttribute('aria-current', 'page');
        }
      } catch (ignore) { /* La navegacion sigue funcionando. */ }
    });
    document.addEventListener('keydown', function (event) {
      if (!root.classList.contains('sga-menu-open')) return;
      if (event.key === 'Escape') { event.preventDefault(); closeMenu(true); return; }
      if (event.key !== 'Tab') return;
      var items = Array.prototype.filter.call(menu.querySelectorAll('a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex="0"]'), function (node) {
        return node.getClientRects().length > 0;
      });
      if (!items.length) return;
      var first = items[0], last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    });
    if (mobile.addEventListener) mobile.addEventListener('change', function () { closeMenu(false); });
    else if (mobile.addListener) mobile.addListener(function () { closeMenu(false); });
    markMenu(false);
  }

  // Se respetan los nombres y las celdas: no se reordena ni clona informacion.
  document.querySelectorAll('table.table-responsive-cards').forEach(function (table) {
    var cells = table.querySelectorAll('thead tr:last-child th');
    var titles = Array.prototype.map.call(cells, function (th) { return th.textContent.replace(/\s+/g, ' ').trim(); });
    table.querySelectorAll('tbody tr').forEach(function (tr) {
      var tds = tr.querySelectorAll(':scope > td');
      tds.forEach(function (td, index) {
        if (td.colSpan > 1 || td.hasAttribute('data-label')) return;
        var title = titles[index] || 'Dato';
        td.setAttribute('data-label', title);
      });
    });
    var parent = table.parentElement;
    if (parent && parent.classList.contains('table-wrap')) parent.classList.add('is-card-view');
  });

  // Las tablas grandes siguen desplazandose en su propio contenedor.
  var scrollRegions = Array.prototype.slice.call(document.querySelectorAll('.table-wrap, .imp-results, .matrix-wrap'));
  scrollRegions.forEach(function (region) {
    if (!region.hasAttribute('role')) region.setAttribute('role', 'region');
    if (!region.hasAttribute('aria-label')) region.setAttribute('aria-label', 'Tabla de datos con desplazamiento horizontal cuando sea necesario');
    if (!region.hasAttribute('tabindex')) region.setAttribute('tabindex', '0');
    if (region.classList.contains('matrix-wrap') || region.classList.contains('grade-matrix-wrap')) return;
    var hint = document.createElement('div');
    hint.className = 'table-scroll-hint';
    hint.textContent = 'Desliza horizontalmente para ver el resto de columnas \u2192';
    hint.setAttribute('aria-hidden', 'true');
    region.insertBefore(hint, region.firstChild);
  });
  function updateWideTableHints() {
    scrollRegions.forEach(function (region) {
      if (region.classList.contains('is-card-view') && cards.matches) {
        region.classList.remove('has-wide-table');
        return;
      }
      region.classList.toggle('has-wide-table', region.scrollWidth > region.clientWidth + 12);
    });
  }
  window.addEventListener('resize', updateWideTableHints, { passive: true });
  if (cards.addEventListener) cards.addEventListener('change', updateWideTableHints);
  window.addEventListener('load', updateWideTableHints);
  updateWideTableHints();
})();
