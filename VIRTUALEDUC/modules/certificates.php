<?php
declare(strict_types=1);
if (!defined('VE_VERSION')) { http_response_code(404); exit; }
require_role($u,'student','teacher');
?>
<section>
  <h1>Mis certificados</h1>
  <p class="muted">Consulta los certificados emitidos a tu nombre.</p>
  <div style="border:1px solid #dce5ef;border-radius:12px;padding:32px 16px;text-align:center;background:#f8fafc">
    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#1655a8" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="14" rx="2"/><path d="M7 7h10M7 10h4"/><circle cx="16" cy="13" r="2.5"/><path d="m14 15-1 6 3-2 3 2-1-6"/></svg>
    <h2 style="font-size:18px;margin:12px 0 6px">Aún no tienes certificados</h2>
    <p class="muted" style="margin:0">La emisión de certificados se habilitará en una próxima actualización.</p>
  </div>
</section>
