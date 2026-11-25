<?php
declare(strict_types=1);
if (!defined('SW_APP') || !SW_PUBLIC) { http_response_code(404); exit; }
function otp_template(string $code): array {
    $html='<!doctype html><html lang="es"><body style="margin:0;background:#eff4fa;font-family:Arial,sans-serif;color:#10294d;padding:24px"><div style="max-width:520px;margin:auto;background:#fff;border:1px solid #dce4ee;border-radius:14px;padding:28px"><div style="font-size:22px;font-weight:bold;color:#245b9d">SORTEOWEB</div><h2>Tu código de acceso</h2><p>Utiliza el siguiente código para verificar tu correo e iniciar sesión:</p><div style="background:#edf4ff;text-align:center;padding:22px;border-radius:10px;font-size:34px;font-weight:bold;letter-spacing:8px">'.h($code).'</div><p>Caduca en <b>5 minutos</b> y solo se puede usar una vez.</p><p>Si no solicitaste este acceso, ignora el mensaje. No compartas el código con nadie.</p></div></body></html>';
    return ['SORTEOWEB - Codigo de acceso',"Tu código de acceso a SORTEOWEB: $code\nCaduca en 5 minutos. No lo compartas.\nSi no lo solicitaste, ignora este mensaje.",$html];
}
