<?php
require_once __DIR__.'/../../lib/lista_estudiantes.php';
require_once __DIR__.'/../../lib/lista_estudiantes_export.php';
$oid=(int)($_GET['oferta_id']??0);
$datos=listaEstudiantesCargar($oid); // Validación de rol, asignatura y jornada.
try {
    $xlsx=listaEstudiantesExcel($datos['oferta'],$datos['estudiantes']);
    registrarAuditoria('EXPORT','Lista','lista_estudiantes',$oid,'Descarga de lista de estudiantes en Excel.',null,null,['oferta_id'=>$oid,'alumnos'=>count($datos['estudiantes'])],'exito');
    $nombre='LISTA_ESTUDIANTES_'.preg_replace('/[^A-Za-z0-9_-]/','_',(string)($datos['oferta']['aula']??'CURSO')).'_'.preg_replace('/[^A-Za-z0-9_-]/','_',(string)($datos['oferta']['paralelo']??'')).'_OFERTA'.$oid.'.xlsx';
    if(session_status()===PHP_SESSION_ACTIVE) session_write_close();
    while(ob_get_level()>0) ob_end_clean();
    header('Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
    header('Content-Disposition: attachment; filename="'.$nombre.'"');
    header('Content-Length: '.strlen($xlsx));
    header('Cache-Control: private, no-store, max-age=0');
    header('X-Content-Type-Options: nosniff');
    echo $xlsx;
    exit;
} catch(Throwable $e) {
    error_log('SGA Lista XLSX: '.$e->getMessage());
    http_response_code(500);
    die('No se pudo generar la lista Excel.');
}
