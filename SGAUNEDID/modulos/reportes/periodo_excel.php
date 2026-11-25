<?php
/** Cuadros anual, trimestral y supletorio XLSX por periodo, una hoja por aula autorizada. */
require_once __DIR__.'/../../lib/funciones.php';
require_once __DIR__.'/../../lib/cuadro_anual_excel.php';
require_once __DIR__.'/../../lib/comportamiento_trimestres.php';
exigirAdminAcademico();

// Supletorio reutiliza el mismo diseño que Trimestre 3, pero muestra
// unicamente el promedio ANUAL de asignaturas que necesitan supletorio.
// Es una consulta de solo lectura, sin modificar calificaciones.
$soloSupletorios=isset($_GET['supletorio']) && (string)$_GET['supletorio']==='1';
if(isset($_GET['supletorio']) && !$soloSupletorios){
    http_response_code(400);die('Parametro de supletorio no valido.');
}
if($soloSupletorios && isset($_GET['trimestre'])){
    http_response_code(400);die('Selecciona el trimestre o el supletorio, no ambos.');
}
// Sin parametro se conserva el cuadro ANUAL; con 1, 2 o 3 se descarga
// exclusivamente el trimestre elegido. No se admiten otros valores.
$trimestre=null;
if(isset($_GET['trimestre'])) {
    $valor=filter_var($_GET['trimestre'],FILTER_VALIDATE_INT,
        ['options'=>['min_range'=>1,'max_range'=>3]]);
    if($valor===false){http_response_code(400);die('El trimestre debe ser 1, 2 o 3.');}
    $trimestre=(int)$valor;
}
// Compatibilidad: una descarga anual sin parametro sigue incluyendo los
// supletorios existentes. El boton de Reportes envía una eleccion expresa.
$incluirSupletorios=true;
if(array_key_exists('incluir_supletorios',$_GET)){
    $opcion=$_GET['incluir_supletorios'];
    if(!is_string($opcion) || !in_array($opcion,['0','1'],true)
        || $trimestre!==null || $soloSupletorios){
        http_response_code(400);die('Opcion de supletorios no valida para este reporte.');
    }
    $incluirSupletorios=$opcion==='1';
}

$activo=periodoActivo();
$pid=(int)($_GET['periodo_id']??($activo['id']??0));
$pid=periodoInicialSubadmin($pid,isset($_GET['periodo_id'])?1:0);
if($pid<=0){http_response_code(400);die('Selecciona un periodo academico valido.');}
exigirAccesoPeriodo($pid);

$stmt=$conexion->prepare('SELECT id,nombre FROM periodos_academicos WHERE id=? LIMIT 1');
$stmt->bind_param('i',$pid);$stmt->execute();
$periodo=$stmt->get_result()->fetch_assoc();$stmt->close();
if(!$periodo){http_response_code(404);die('Periodo academico no encontrado.');}

// Importante: se filtra la jornada en CADA consulta, ademas de la autorizacion
// inicial; no debe ser posible consultar otra jornada alterando la URL.
$filtro=filtroJornadasSQL($pid,'a');
$stmt=$conexion->prepare('SELECT ap.id aula_periodo_id,a.id aula_id,a.codigo,a.nivel,a.nombre,a.paralelo, '
    .'a.resultados_cualitativos,j.nombre jornada FROM aulas_periodo ap JOIN aulas a ON a.id=ap.aula_id '
    .'LEFT JOIN jornadas j ON j.id=a.jornada_id '
    .'WHERE ap.periodo_id=? AND ap.activo=1 AND a.activo=1'.$filtro.' ORDER BY COALESCE(j.orden,9999),COALESCE(a.orden,9999),a.nombre,a.paralelo,ap.id');
$stmt->bind_param('i',$pid);$stmt->execute();
$aulas=$stmt->get_result()->fetch_all(MYSQLI_ASSOC);$stmt->close();
if(!$aulas){http_response_code(404);die('No hay aulas habilitadas en este período o con el filtro de jornada actual.');}

$datosAulas=[];
foreach($aulas as $a){
    $ap=(int)$a['aula_periodo_id'];
    $a['ofertas']=[];$a['estudiantes']=[];
    $datosAulas[$ap]=$a;
}

$stmt=$conexion->prepare('SELECT o.id,o.aula_periodo_id,s.codigo,CASE WHEN o.evaluacion_aula=1 THEN \'Evaluación cualitativa del aula\' ELSE s.nombre END nombre,s.usa_literal_especial,CASE WHEN o.evaluacion_aula=1 OR o.evaluacion_parametros_historica=1 THEN 0 ELSE s.solo_visor_comportamiento END solo_visor_comportamiento,(o.evaluacion_aula=1 OR o.evaluacion_parametros_historica=1) evaluacion_cualitativa_parametros '
    .'FROM ofertas_academicas o JOIN asignaturas s ON s.id=o.asignatura_id '
    .'JOIN areas ar ON ar.id=s.area_id JOIN aulas_periodo ap ON ap.id=o.aula_periodo_id '
    .'JOIN aulas a ON a.id=ap.aula_id '
    .'WHERE ap.periodo_id=? AND ap.activo=1 AND a.activo=1 AND o.activo=1'.$filtro
    .' ORDER BY a.id ASC,ar.orden ASC,s.nombre ASC,o.id ASC');
$stmt->bind_param('i',$pid);$stmt->execute();$ofertas=$stmt->get_result()->fetch_all(MYSQLI_ASSOC);$stmt->close();
$ofertasPorId=[];
foreach($ofertas as $o){
    $ap=(int)$o['aula_periodo_id'];
    if(!isset($datosAulas[$ap]))continue;
    $datosAulas[$ap]['ofertas'][]=$o;
    $ofertasPorId[(int)$o['id']]=$o;
}

$stmt=$conexion->prepare("SELECT m.id matricula_id,m.aula_periodo_id,m.numero_lista,"
    ."u.apellidos,u.nombres FROM matriculas m JOIN usuarios u ON u.id=m.estudiante_id "
    ."JOIN aulas_periodo ap ON ap.id=m.aula_periodo_id JOIN aulas a ON a.id=ap.aula_id "
    ."WHERE ap.periodo_id=? AND ap.activo=1 AND a.activo=1 AND m.estado IN ('activo','finalizado')".$filtro
    ." ORDER BY a.id ASC,COALESCE(m.numero_lista,999999),u.apellidos,u.nombres");
$stmt->bind_param('i',$pid);$stmt->execute();$estudiantes=$stmt->get_result()->fetch_all(MYSQLI_ASSOC);$stmt->close();
$matriculasPorId=[];
foreach($estudiantes as $est){
    $ap=(int)$est['aula_periodo_id'];$mid=(int)$est['matricula_id'];
    if(!isset($datosAulas[$ap]))continue;
    $matriculasPorId[$mid]=$ap;
    $datosAulas[$ap]['estudiantes'][$mid]=$est;
}

// En el anual se aplica la formula institucional; en trimestre se usa la nota registrada.
$stmt=$conexion->prepare("SELECT c.oferta_id,c.matricula_id,c.trimestre,c.nota_final "
    ."FROM calificaciones_trimestre c "
    ."JOIN ofertas_academicas o ON o.id=c.oferta_id AND o.activo=1 "
    ."JOIN matriculas m ON m.id=c.matricula_id AND m.aula_periodo_id=o.aula_periodo_id "
    ."JOIN aulas_periodo ap ON ap.id=o.aula_periodo_id JOIN aulas a ON a.id=ap.aula_id "
    ."WHERE ap.periodo_id=? AND ap.activo=1 AND a.activo=1 AND m.estado IN ('activo','finalizado') "
    ."AND c.trimestre BETWEEN 1 AND 3".($trimestre!==null?' AND c.trimestre=?':'').$filtro);
if($trimestre!==null)$stmt->bind_param('ii',$pid,$trimestre);
else $stmt->bind_param('i',$pid);
$stmt->execute();$rows=$stmt->get_result();
$calificaciones=[];
while($r=$rows->fetch_assoc()){
    $mid=(int)$r['matricula_id'];$oid=(int)$r['oferta_id'];$t=(int)$r['trimestre'];
    if(isset($matriculasPorId[$mid],$ofertasPorId[$oid])){
        $calificaciones[$mid][$oid][$t]=$r['nota_final']===null?null:(float)$r['nota_final'];
    }
}
$stmt->close();

$supletorios=[];
if($trimestre===null && !$soloSupletorios && $incluirSupletorios) {
    $stmt=$conexion->prepare("SELECT nf.matricula_id,nf.oferta_id,nf.examen_supletorio "
        ."FROM notas_finales nf JOIN ofertas_academicas o ON o.id=nf.oferta_id AND o.activo=1 "
        ."JOIN matriculas m ON m.id=nf.matricula_id AND m.aula_periodo_id=o.aula_periodo_id "
        ."JOIN aulas_periodo ap ON ap.id=o.aula_periodo_id JOIN aulas a ON a.id=ap.aula_id "
        ."WHERE ap.periodo_id=? AND ap.activo=1 AND a.activo=1 AND m.estado IN ('activo','finalizado')".$filtro);
    $stmt->bind_param('i',$pid);$stmt->execute();$rows=$stmt->get_result();
    while($r=$rows->fetch_assoc()) {
        $supletorios[(int)$r['matricula_id']][(int)$r['oferta_id']]
            =$r['examen_supletorio']!==null?(float)$r['examen_supletorio']:null;
    }
    $stmt->close();
}

// Calificaciones cualitativas por trimestre; la letra final se calcula aparte.
$comportamientoTrimestres=[];
$stmt=$conexion->prepare("SELECT cc.oferta_id,cc.matricula_id,cc.trimestre,cc.literal
    FROM calificaciones_comportamiento_trimestre cc
    JOIN ofertas_academicas o ON o.id=cc.oferta_id AND o.activo=1
    JOIN asignaturas s ON s.id=o.asignatura_id AND s.solo_visor_comportamiento=1
    JOIN matriculas m ON m.id=cc.matricula_id AND m.aula_periodo_id=o.aula_periodo_id
    JOIN aulas_periodo ap ON ap.id=o.aula_periodo_id JOIN aulas a ON a.id=ap.aula_id
    WHERE ap.periodo_id=? AND ap.activo=1 AND a.activo=1
        AND m.estado IN ('activo','finalizado')".$filtro);
$stmt->bind_param('i',$pid);$stmt->execute();
foreach($stmt->get_result()->fetch_all(MYSQLI_ASSOC) as $r){
    $mid=(int)$r['matricula_id'];$oid=(int)$r['oferta_id'];
    if(isset($matriculasPorId[$mid],$ofertasPorId[$oid])) {
        $comportamientoTrimestres[$mid][$oid][(int)$r['trimestre']]=$r['literal'];
    }
}
$stmt->close();

$config=$trimestre===null?obtenerConfiguracion($pid):[];
foreach($datosAulas as $ap=>&$aula){
    $resultadosCualitativosAula=!empty($aula['resultados_cualitativos']);
    foreach($aula['estudiantes'] as $mid=>&$est){
        $est['comportamiento']='';
        $notasFinales=[];$detalleNotas=[];$notasNumericas=[];$detalleNumerico=[];
        foreach($aula['ofertas'] as $of){
            $oid=(int)$of['id'];$tr=$calificaciones[$mid][$oid]??[];
            $nota=null;
            if(!empty($of['evaluacion_cualitativa_parametros'])) {
                // No inventar una nota global a partir de ámbitos individuales.
                // El informe cualitativo por estudiante muestra cada ámbito.
                $notasFinales[$oid]=$soloSupletorios?null:'POR PARÁMETROS';
                if($trimestre===null && !$soloSupletorios) {
                    $detalleNotas[$oid]=['t1'=>null,'t2'=>null,'t3'=>null,'supletorio'=>null,'final'=>'POR PARÁMETROS'];
                }
                continue;
            }
            if($soloSupletorios) {
                // Mostrar la nota anual que necesita supletorio (4,00-6,99 con
                // la configuracion predeterminada), nunca solo un T3 insuficiente.
                // Las asignaturas de comportamiento no generan supletorio.
                if(empty($of['solo_visor_comportamiento'])) {
                    $nota=cuadroAnualNotaPendienteSupletorio($tr,$config);
                    if($resultadosCualitativosAula)$notasNumericas[$oid]=$nota;
                    if($nota!==null && $resultadosCualitativosAula)
                        $nota=sgaNotaResultadoParaConsulta((float)$nota,true);
                }
                $notasFinales[$oid]=$nota;
                continue;
            }
            if(!empty($of['solo_visor_comportamiento'])) {
                $valores=$comportamientoTrimestres[$mid][$oid]??[];
                $final=sgaComportamientoFinal($valores[1]??null,$valores[2]??null,$valores[3]??null);
                if($trimestre!==null) {
                    $notasFinales[$oid]=$valores[$trimestre]??null;
                } else {
                    $notasFinales[$oid]=$final;
                    if(!$soloSupletorios) {
                        $detalleNotas[$oid]=[
                            't1'=>$valores[1]??null,
                            't2'=>$valores[2]??null,
                            't3'=>$valores[3]??null,
                            'final'=>$final, // Promedio cualitativo en letra.
                        ];
                    }
                }
                if(!array_key_exists('comportamiento_fuente',$est)) {
                    $est['comportamiento_fuente']=$oid;
                    $est['comportamiento']=$trimestre!==null
                        ? (string)($valores[$trimestre]??'') : ($final??'');
                }
                continue;
            }
            $especial=!empty($of['usa_literal_especial']);
            if($trimestre!==null) {
                // Un trimestre nunca mezcla calificaciones de supletorios.
                if(isset($tr[$trimestre])) {
                    $valor=(float)$tr[$trimestre];
                    if($resultadosCualitativosAula)$notasNumericas[$oid]=$valor;
                    $nota=$resultadosCualitativosAula?sgaNotaResultadoParaConsulta($valor,true):($especial?literalEspecial($valor):round($valor,2));
                }
            } else {
                // Conservar las tres notas originales y mostrar el supletorio
                // exactamente entre trimestre 3 y la nota final calculada.
                // Con la opcion No no se consulta ni aplica el examen.
                $registrado=$incluirSupletorios?($supletorios[$mid][$oid]??null):null;
                $completo=isset($tr[1],$tr[2],$tr[3]);
                $valorFinalNumerico=null;
                if($completo){
                    $fin=calcularFinalAnual((float)$tr[1],(float)$tr[2],(float)$tr[3],$registrado,$config);
                    $valor=$fin['observacion']==='SUPLETORIO'
                        ?(float)$fin['promedio_tres']:(float)$fin['promedio_final'];
                    $valorFinalNumerico=$valor;
                    $nota=$resultadosCualitativosAula?sgaNotaResultadoParaConsulta($valor,true):($especial?literalEspecial($valor):round($valor,2));
                }
                $convertir=static function($v)use($especial,$resultadosCualitativosAula){
                    if($v===null)return null;
                    $v=(float)$v;
                    return $resultadosCualitativosAula?sgaNotaResultadoParaConsulta($v,true):($especial?literalEspecial($v):round($v,2));
                };
                $detalleNumerico[$oid]=['t1'=>$tr[1]??null,'t2'=>$tr[2]??null,'t3'=>$tr[3]??null,'supletorio'=>$completo?$registrado:null,'final'=>$valorFinalNumerico];
                $detalleNotas[$oid]=[
                    't1'=>$convertir($tr[1]??null),
                    't2'=>$convertir($tr[2]??null),
                    't3'=>$convertir($tr[3]??null),
                    // La calificacion del examen es numerica, sin transformar
                    // el dato historico original que se guarda en la BD.
                    'supletorio'=>$completo && $registrado!==null?($resultadosCualitativosAula?sgaNotaResultadoParaConsulta((float)$registrado,true):round((float)$registrado,2)):null,
                    'final'=>$nota,
                ];
            }
            $notasFinales[$oid]=$nota;
        }
        $est['notas']=$notasFinales;
        if($resultadosCualitativosAula){$est['notas_numericas']=$notasNumericas;$est['detalle_numerico']=$detalleNumerico;}
        if($trimestre===null)$est['detalle_notas']=$detalleNotas;
    }
    unset($est);
    $aula['estudiantes']=array_values($aula['estudiantes']);
}
unset($aula);

try {
    $archivo=cuadroAnualGenerarXlsx(array_values($datosAulas),(string)$periodo['nombre'],$trimestre,$soloSupletorios,$incluirSupletorios);
} catch(Throwable $e) {
    error_log('SGA Cuadro de calificaciones XLSX: '.$e->getMessage());
    http_response_code(500);die('No se pudo generar el cuadro de calificaciones de este periodo.');
}

registrarAuditoria('EXPORT','Reportes',
    $soloSupletorios?'cuadro_supletorio_periodo':($trimestre===null?'cuadro_anual_periodo':'cuadro_trimestral_periodo'),$pid,
    $soloSupletorios?'Cuadro Excel de asignaturas con supletorio descargado con una hoja por aula autorizada.'
        :($trimestre===null?'Cuadro anual Excel por periodo descargado con una hoja por aula autorizada.'
            :'Cuadro Excel del trimestre '.$trimestre.' descargado con una hoja por aula autorizada.'),
    null,null,['periodo'=>$periodo['nombre'],'trimestre'=>$trimestre,
        'supletorio'=>$soloSupletorios,
        'incluir_supletorios'=>($trimestre===null && !$soloSupletorios)?$incluirSupletorios:null,
        'aulas'=>count($datosAulas),
        'estudiantes'=>count($matriculasPorId)],'exito');

$slug=preg_replace('/[^A-Za-z0-9_-]/','_',(string)$periodo['nombre'])??'periodo';
$nombre=$soloSupletorios?'CUADRO_SUPLETORIOS_'.$slug.'.xlsx'
    :($trimestre===null?($incluirSupletorios?'CUADRO_ANUAL_CALIFICACIONES_'.$slug.'.xlsx'
            :'CUADRO_ANUAL_SIN_SUPLETORIOS_'.$slug.'.xlsx')
        :'CUADRO_CALIFICACIONES_TRIMESTRE_'.$trimestre.'_'.$slug.'.xlsx');
if(session_status()===PHP_SESSION_ACTIVE)session_write_close();
while(ob_get_level()>0)ob_end_clean();
header('Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
header('Content-Disposition: attachment; filename="'.$nombre.'"');
header('Content-Length: '.strlen($archivo));
header('X-Content-Type-Options: nosniff');
header('Cache-Control: private, no-store, max-age=0');
echo $archivo;
exit;
