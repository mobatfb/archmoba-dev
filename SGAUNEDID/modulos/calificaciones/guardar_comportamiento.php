<?php
require_once __DIR__.'/../../lib/funciones.php';
require_once __DIR__.'/../../lib/comportamiento_trimestres.php';
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, max-age=0');
function sgaComportamientoResponder(int $codigo, bool $ok, string $mensaje, array $mas=[]): never {
    http_response_code($codigo);
    echo json_encode(array_merge(['ok'=>$ok,'mensaje'=>$mensaje],$mas),JSON_UNESCAPED_UNICODE);
    exit;
}
if (($_SERVER['REQUEST_METHOD']??'')!=='POST') sgaComportamientoResponder(405,false,'Método no permitido.');
if (empty($_SESSION['usuario_id'])) sgaComportamientoResponder(401,false,'La sesión ha terminado. Inicia sesión nuevamente.');
$oid=filter_var($_POST['oferta_id']??null,FILTER_VALIDATE_INT,['options'=>['min_range'=>1]]);
$mid=filter_var($_POST['matricula_id']??null,FILTER_VALIDATE_INT,['options'=>['min_range'=>1]]);
$trimestre=filter_var($_POST['trimestre']??null,FILTER_VALIDATE_INT,['options'=>['min_range'=>1,'max_range'=>3]]);
$literal=array_key_exists('literal',$_POST) && is_string($_POST['literal']) ? $_POST['literal'] : null;
$csrf=is_string($_POST['csrf']??null) ? $_POST['csrf'] : '';
if (!$oid || !$mid || !$trimestre || $literal===null || ($literal!=='' && !sgaComportamientoValorValido($literal)))
    sgaComportamientoResponder(422,false,'Selecciona una valoración válida entre A+ y F-, o Sin nota.');
if (empty($_SESSION['csrf_comportamiento_trimestre']) || !hash_equals($_SESSION['csrf_comportamiento_trimestre'],$csrf))
    sgaComportamientoResponder(403,false,'La sesión de seguridad ha vencido. Recarga la página.');
if (!puedeGestionarOferta((int)$oid)) sgaComportamientoResponder(403,false,'No tienes permiso sobre esta asignatura.');
$o=ofertaDetalle((int)$oid);
if (!$o || empty($o['solo_visor_comportamiento']) || !(int)$o['activo'])
    sgaComportamientoResponder(403,false,'Esta asignatura no está habilitada para comportamiento.');
if(($o['periodo_estado']??'')==='cerrado')sgaComportamientoResponder(409,false,'El período está cerrado.');
$conexion->begin_transaction();
try {
    sgaAsegurarPeriodoEditable((int)$o['periodo_id']);
    $apid=(int)$o['aula_periodo_id'];
    $stmt=$conexion->prepare("SELECT m.estudiante_id,u.apellidos,u.nombres
        FROM matriculas m JOIN usuarios u ON u.id=m.estudiante_id
        WHERE m.id=? AND m.aula_periodo_id=? AND m.estado='activo' LIMIT 1");
    $stmt->bind_param('ii',$mid,$apid);$stmt->execute();$mat=$stmt->get_result()->fetch_assoc();$stmt->close();
    if (!$mat)throw new DomainException('El estudiante no pertenece a esta aula.');
    $stmt=$conexion->prepare('SELECT literal FROM calificaciones_comportamiento_trimestre WHERE oferta_id=? AND matricula_id=? AND trimestre=? LIMIT 1 FOR UPDATE');
    $stmt->bind_param('iii',$oid,$mid,$trimestre);$stmt->execute();$anterior=$stmt->get_result()->fetch_assoc();$stmt->close();
    $antes=$anterior['literal']??null;
    $valorFinal=$literal==='' ? null : $literal;
    if($valorFinal===null){
        // La tabla exige una letra valida; dejar sin nota implica eliminar la fila
        // del trimestre. Las valoraciones de otros trimestres no se modifican.
        if($anterior!==null){
            $stmt=$conexion->prepare('DELETE FROM calificaciones_comportamiento_trimestre WHERE oferta_id=? AND matricula_id=? AND trimestre=?');
            $stmt->bind_param('iii',$oid,$mid,$trimestre);
            if(!$stmt->execute())throw new RuntimeException('No se pudo quitar la valoración.');
            $stmt->close();
        }
    }else{
        $actor=(int)$_SESSION['usuario_id'];
        $stmt=$conexion->prepare('INSERT INTO calificaciones_comportamiento_trimestre (oferta_id,matricula_id,trimestre,literal,registrado_por) VALUES (?,?,?,?,?) ON DUPLICATE KEY UPDATE literal=VALUES(literal),registrado_por=VALUES(registrado_por),actualizado_en=CURRENT_TIMESTAMP');
        $stmt->bind_param('iiisi',$oid,$mid,$trimestre,$valorFinal,$actor);
        if(!$stmt->execute())throw new RuntimeException('No se pudo registrar la valoración.');
        $stmt->close();
    }
    if($antes!==$valorFinal){
        $accion=$valorFinal===null?'DELETE':($antes===null?'CREATE':'UPDATE');
        sgaAuditoriaObligatoria($accion,'Calificaciones','comportamiento_trimestre',$oid.'-'.$mid.'-'.$trimestre,
            ($valorFinal===null?'Valoración de comportamiento retirada de ':'Comportamiento de ')
                .$mat['apellidos'].' '.$mat['nombres'].' en '.$o['asignatura'].' · trimestre '.$trimestre.'.',
            (int)$mat['estudiante_id'],['literal'=>$antes],['literal'=>$valorFinal],'exito',null,null,'advertencia');
    }
    if(!$conexion->commit())throw new RuntimeException('No se confirmó el registro.');
    sgaComportamientoResponder(200,true,$valorFinal===null?'Sin nota':'Guardado',
        ['literal'=>$literal,'trimestre'=>$trimestre,'matricula_id'=>(int)$mid]);
} catch (DomainException $e){
    $conexion->rollback();sgaComportamientoResponder(422,false,$e->getMessage());
} catch (Throwable $e){
    $conexion->rollback();error_log('[SGA] comportamiento trimestre: '.$e->getMessage());
    sgaComportamientoResponder(500,false,'No se pudo guardar. Comprueba que se ejecutó la migración SQL.');
}
