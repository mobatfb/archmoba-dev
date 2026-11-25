<?php
// Diagnostico temporal: habilitar solo durante el mantenimiento controlado.
if (getenv('SGA_ENABLE_DIAGNOSTICS') !== '1') { http_response_code(404); exit; }
header('Content-Type: text/html; charset=UTF-8');
function ok($v){return $v?'<strong style="color:#147a4d">OK</strong>':'<strong style="color:#b73333">FALTA</strong>';}
$dbFile=__DIR__.'/config/database.php';
$db=is_file($dbFile)?require $dbFile:null;
$dbOk=false;$dbMsg='No se encontro config/database.php';
if(is_array($db)){
    if(extension_loaded('mysqli')){
        mysqli_report(MYSQLI_REPORT_OFF);
        $c=@new mysqli((string)$db['host'],(string)$db['user'],(string)$db['pass'],(string)$db['name'],(int)$db['port']);
        if(!$c->connect_errno){$dbOk=true;$dbMsg='Conexion correcta a MySQL.';$c->close();}
        else{$dbMsg='Error MySQL '.$c->connect_errno.': '.$c->connect_error;}
    }else{$dbMsg='La extension mysqli no esta habilitada.';}
}
$phpOk=version_compare(PHP_VERSION,'7.4.0','>=');
?><!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Diagnostico cPanel - SGA UNEDID</title><style>body{font-family:Arial,sans-serif;background:#f3f6fa;color:#152033;margin:0;padding:28px}.box{max-width:900px;margin:auto;background:#fff;border:1px solid #dce4ee;border-radius:14px;padding:24px}table{border-collapse:collapse;width:100%}td,th{padding:10px;border-bottom:1px solid #e5eaf0;text-align:left}code{background:#eef4fb;padding:2px 5px;border-radius:4px}.warn{background:#fff8df;border:1px solid #ead48a;padding:12px;border-radius:8px;margin-top:18px}</style></head><body><div class="box"><h1>Diagnostico cPanel · SGA UNEDID</h1><table><tr><th>Comprobacion</th><th>Estado</th><th>Detalle</th></tr><tr><td>PHP >= 7.4</td><td><?=ok($phpOk)?></td><td><?=htmlspecialchars(PHP_VERSION)?></td></tr><tr><td>mysqli</td><td><?=ok(extension_loaded('mysqli'))?></td><td>Conexion MySQL</td></tr><tr><td>mbstring</td><td><?=ok(extension_loaded('mbstring'))?></td><td>Texto UTF-8</td></tr><tr><td>zip</td><td><?=ok(extension_loaded('zip'))?></td><td>Reporte Excel de calificaciones</td></tr><tr><td>dom</td><td><?=ok(extension_loaded('dom'))?></td><td>Manipulacion XLSX</td></tr><tr><td>fileinfo</td><td><?=ok(extension_loaded('fileinfo'))?></td><td>Fotos de candidatos</td></tr><tr><td>Conexion BD</td><td><?=ok($dbOk)?></td><td><?=htmlspecialchars($dbMsg)?></td></tr></table><div class="warn"><strong>Importante:</strong> si la base falla, edite <code>config/database.php</code>. En cPanel el nombre de la base y el usuario suelen llevar el prefijo de la cuenta. Cuando termine las pruebas, elimine este archivo <code>diagnostico_cpanel.php</code> del hosting.</div></div></body></html>
