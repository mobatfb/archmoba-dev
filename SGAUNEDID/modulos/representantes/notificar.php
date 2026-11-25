<?php
require_once __DIR__.'/../../lib/sga_representantes.php';
exigirLogin();
$pid=(int)(periodoActivo()['id']??0);
if($_SERVER['REQUEST_METHOD']!=='POST'){http_response_code(405);die('Método no permitido.');}
if(empty($_SESSION['csrf_representantes'])||!hash_equals($_SESSION['csrf_representantes'],(string)($_POST['csrf']??''))){http_response_code(403);die('Formulario caducado.');}
$eid=(int)($_POST['estudiante_id']??0);
$volver='modulos/representantes/index.php?estudiante_id='.$eid;
try{
    if(!$pid||!(esAdminAcademico()||esDocenteOperativo($pid))||!sgaRepPuedeConsultarEstudiante($eid,$pid,true))throw new DomainException('No tienes acceso a este estudiante.');
    if(!sgaRepRepresentantesDe($eid))throw new DomainException('No hay representantes vinculados para enviar esta novedad.');
    $actor=(int)$_SESSION['usuario_id'];
    $s=$conexion->prepare("SELECT COUNT(*) total FROM sga_representantes_novedades WHERE creada_por=? AND creada_en > DATE_SUB(NOW(),INTERVAL 1 HOUR)");
    $s->bind_param('i',$actor);$s->execute();$contador=(int)($s->get_result()->fetch_assoc()['total']??0);$s->close();
    if($contador>=30)throw new DomainException('Se alcanzó el límite de 30 avisos por hora. Inténtalo después.');
    $tipo=trim((string)($_POST['tipo']??''));$asunto=trim((string)($_POST['asunto']??''));$detalle=trim((string)($_POST['detalle']??''));
    $id=sgaRepCrearNovedad($eid,$pid,$actor,$tipo,$asunto,$detalle);
    // Correo inmediato a los primeros representantes. El cron procesa los restantes o reintentos.
    try {
        $resultado=sgaRepEnviarPendientes(12,$id);
        $mensaje='Novedad registrada. Correos enviados: '.(int)$resultado['enviados'].'.';
        if((int)$resultado['errores']>0)$mensaje.=' Hay entregas pendientes para reintentar desde la cola.';
        flash((int)$resultado['errores']>0?'error':'success',$mensaje);
    }catch(Throwable $errorEnvio){
        error_log('[SGA UNEDID] No fue posible completar el envio de la novedad '.(int)$id);
        flash('error','La novedad quedó registrada, pero el envío de correos sigue pendiente. Revisa el cron y la configuración SMTP.');
    }
}catch(Throwable $e){
    // El SMTP podría fallar DESPUÉS de haber guardado la novedad; no revelar datos técnicos.
    error_log('[SGA UNEDID] Notificacion representantes: '.get_class($e));
    flash('error',$e instanceof DomainException?$e->getMessage():'No se pudo completar la operación. Revisa el registro de errores del sistema.');
}
redir($volver);
