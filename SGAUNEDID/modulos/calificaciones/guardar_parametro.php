<?php
/** API de autoguardado de una valoracion cualitativa por parametro. */
require_once __DIR__.'/../../lib/funciones.php';
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, max-age=0');
function sgaParamResp(int $status,bool $ok,string $message): never {
    http_response_code($status);
    echo json_encode(['ok'=>$ok,'mensaje'=>$message],JSON_UNESCAPED_UNICODE);
    exit;
}
if(($_SERVER['REQUEST_METHOD']??'')!=='POST')sgaParamResp(405,false,'Método no permitido.');
if(empty($_SESSION['usuario_id']))sgaParamResp(401,false,'Tu sesión terminó. Vuelve a ingresar.');
$oid=filter_var($_POST['oferta_id']??null,FILTER_VALIDATE_INT,['options'=>['min_range'=>1]]);
$mid=filter_var($_POST['matricula_id']??null,FILTER_VALIDATE_INT,['options'=>['min_range'=>1]]);
$pid=filter_var($_POST['parametro_id']??null,FILTER_VALIDATE_INT,['options'=>['min_range'=>1]]);
$trim=filter_var($_POST['trimestre']??null,FILTER_VALIDATE_INT,['options'=>['min_range'=>1,'max_range'=>3]]);
$literal=is_string($_POST['literal']??null)?(string)$_POST['literal']:null;
$csrf=is_string($_POST['csrf']??null)?(string)$_POST['csrf']:'';
if(!$oid||!$mid||!$pid||!$trim||$literal===null||($literal!==''&&!in_array($literal,sgaParametrosOpciones(),true)))
    sgaParamResp(422,false,'Parámetro, trimestre o valoración inválidos.');
if(empty($_SESSION['csrf_parametros_cualitativos'])||!hash_equals((string)$_SESSION['csrf_parametros_cualitativos'],$csrf))
    sgaParamResp(403,false,'La sesión de seguridad caducó. Actualiza la página.');
if(!puedeGestionarOferta((int)$oid))sgaParamResp(403,false,'No tienes permiso para esta evaluación del aula.');
$o=ofertaDetalle((int)$oid);
if(!$o||empty($o['evaluacion_cualitativa_parametros'])||!empty($o['solo_visor_comportamiento'])||!(int)$o['activo'])
    sgaParamResp(403,false,'La asignatura no utiliza esta modalidad.');
if(($o['periodo_estado']??'')==='cerrado')sgaParamResp(409,false,'El período está cerrado.');
if(!sgaParametrosPuedeCalificar($o))sgaParamResp(403,false,'Solo el docente responsable y la administración autorizada pueden registrar valoraciones.');
try{
    sgaAsegurarPeriodoEditable((int)$o['periodo_id']);
    if(!$conexion->begin_transaction())throw new RuntimeException('No se pudo iniciar el guardado.');
    sgaParametrosBloquearAula($conexion,(int)$o['aula_periodo_id']);
    $o=ofertaDetalle((int)$oid);
    if(!$o || !sgaParametrosPuedeCalificar($o))throw new DomainException('Los permisos, el responsable o el estado del aula cambiaron. Recarga la página.');
    $s=$conexion->prepare('SELECT id FROM sga_parametros_cualitativos WHERE id=? AND oferta_id=? AND activo=1 LIMIT 1');
    $s->bind_param('ii',$pid,$oid);sgaEjecutar($s,'validar ámbito');$param=$s->get_result()->fetch_assoc();$s->close();
    if(!$param)throw new DomainException('El ámbito no pertenece a la asignatura.');
    $apid=(int)$o['aula_periodo_id'];
    $s=$conexion->prepare("SELECT m.estudiante_id FROM matriculas m WHERE m.id=? AND m.aula_periodo_id=? AND m.estado='activo' LIMIT 1");
    $s->bind_param('ii',$mid,$apid);sgaEjecutar($s,'validar matrícula');$mat=$s->get_result()->fetch_assoc();$s->close();
    if(!$mat)throw new DomainException('Este estudiante no pertenece al aula.');
    $s=$conexion->prepare('SELECT literal FROM sga_calificaciones_parametros WHERE parametro_id=? AND matricula_id=? AND trimestre=? LIMIT 1 FOR UPDATE');
    $s->bind_param('iii',$pid,$mid,$trim);sgaEjecutar($s,'consultar nota anterior');$ant=$s->get_result()->fetch_assoc();$s->close();
    $previa=$ant['literal']??null;$nueva=$literal===''?null:$literal;
    if($nueva===null){
        if($ant!==null){
            $s=$conexion->prepare('DELETE FROM sga_calificaciones_parametros WHERE parametro_id=? AND matricula_id=? AND trimestre=?');
            $s->bind_param('iii',$pid,$mid,$trim);sgaEjecutar($s,'eliminar valoración');$s->close();
        }
    }elseif($previa!==$nueva){
        $actor=(int)$_SESSION['usuario_id'];
        $s=$conexion->prepare('INSERT INTO sga_calificaciones_parametros(oferta_id,matricula_id,parametro_id,trimestre,literal,registrado_por) VALUES (?,?,?,?,?,?) ON DUPLICATE KEY UPDATE literal=VALUES(literal),registrado_por=VALUES(registrado_por),actualizado_en=CURRENT_TIMESTAMP');
        $s->bind_param('iiiisi',$oid,$mid,$pid,$trim,$nueva,$actor);sgaEjecutar($s,'guardar valoración');$s->close();
    }
    if($previa!==$nueva){
        $accion=$nueva===null?'DELETE':($previa===null?'CREATE':'UPDATE');
        sgaAuditoriaObligatoria($accion,'Calificaciones','evaluacion_parametro',$oid.'-'.$mid.'-'.$pid.'-'.$trim,
            'Valoración cualitativa por ámbito actualizada.',(int)$mat['estudiante_id'],
            ['literal'=>$previa],['literal'=>$nueva,'trimestre'=>$trim,'parametro_id'=>$pid,'rol_operativo'=>rolOperativoActual()],'exito',(int)$_SESSION['usuario_id']);
    }
    if(!$conexion->commit())throw new RuntimeException('No se confirmó la calificación.');
    sgaParamResp(200,true,$nueva===null?'Sin nota':'Guardado');
}catch(DomainException $e){try{$conexion->rollback();}catch(Throwable $ignored){}sgaParamResp(422,false,$e->getMessage());}
catch(Throwable $e){try{$conexion->rollback();}catch(Throwable $ignored){}sgaParamResp(500,false,'No se pudo guardar la valoración. Verifica la conexión e inténtalo otra vez.');}
