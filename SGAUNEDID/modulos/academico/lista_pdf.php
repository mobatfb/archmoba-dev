<?php
require_once __DIR__.'/../../lib/lista_estudiantes.php';
require_once __DIR__.'/../../lib/lista_estudiantes_export.php';
$oid=(int)($_GET['oferta_id']??0);
$datos=listaEstudiantesCargar($oid); // Validación de rol, asignatura y jornada.
try {
    $pdf=listaEstudiantesPdf($datos['oferta'],$datos['estudiantes']);
    registrarAuditoria('EXPORT','Lista','lista_estudiantes',$oid,'Descarga de lista de estudiantes en PDF.',null,null,['oferta_id'=>$oid,'alumnos'=>count($datos['estudiantes'])],'exito');
    if(session_status()===PHP_SESSION_ACTIVE) session_write_close();
    while(ob_get_level()>0) ob_end_clean();
    $pdf->output('LISTA_ESTUDIANTES_OFERTA'.$oid.'.pdf');
} catch(Throwable $e) {
    error_log('SGA Lista PDF: '.$e->getMessage());
    http_response_code(500);
    die('No se pudo generar la lista PDF.');
}
