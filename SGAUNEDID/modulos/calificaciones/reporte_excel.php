<?php
/**
 * Reporte de calificaciones dinamico: todos los estudiantes, 3 trimestres y resumen.
 * No depende de la plantilla fija de 40 estudiantes ni de ZipArchive de PHP.
 */
require_once __DIR__.'/../../lib/funciones.php';
require_once __DIR__.'/../../lib/exportaciones_xlsx.php';
exigirLogin();
$oid=(int)($_GET['oferta_id']??0);
if(!$oid||!puedeGestionarOferta($oid)){http_response_code(403);die('No tienes acceso a esta asignatura.');}
$detalle=ofertaDetalle($oid);
if($detalle && !empty($detalle['evaluacion_cualitativa_parametros'])) {
  $alumnos=sgaParametrosAlumnosDeOferta($conexion,(int)$detalle['aula_periodo_id']);
  $parametros=sgaParametrosDeOferta($conexion,$oid);
  $notas=sgaParametrosNotasDeOferta($conexion,$oid);$hojas=[];
  foreach([1,2,3] as $t){
      $cab=['No.','Cédula','Estudiante'];foreach($parametros as $pa)$cab[]=$pa['eje'].' · '.$pa['ambito'];
      $filas=[];foreach($alumnos as $i=>$al){$mid=(int)$al['matricula_id'];$f=[(int)($al['numero_lista']?:$i+1),(string)$al['cedula'],$al['apellidos'].' '.$al['nombres']];foreach($parametros as $pa)$f[]=$notas[$mid][(int)$pa['id']][$t]??'';$filas[]=$f;}
      $hojas[]=['nombre'=>'Trimestre '.$t,'titulo'=>'EVALUACIÓN CUALITATIVA DEL AULA · TRIMESTRE '.$t,'subtitulo'=>$detalle['nivel'].' '.$detalle['aula'].' '.$detalle['paralelo'].' · '.$detalle['periodo'],'nota'=>'Docente: '.$detalle['docente_apellidos'].' '.$detalle['docente_nombres'].' | A+ a E- · Sin promedio numérico','cabeceras'=>$cab,'filas'=>$filas,'anchos'=>array_merge([10,19,38],array_fill(0,count($parametros),38))];
  }
  $filas=[];foreach($alumnos as $al)foreach($parametros as $pa){$mid=(int)$al['matricula_id'];$id=(int)$pa['id'];$filas[]=[(string)$al['cedula'],$al['apellidos'].' '.$al['nombres'],$pa['eje'],$pa['ambito'],$notas[$mid][$id][1]??'',$notas[$mid][$id][2]??'',$notas[$mid][$id][3]??''];}
  $hojas[]=['nombre'=>'Resumen T1-T3','titulo'=>'INFORME CUALITATIVO · RESUMEN','subtitulo'=>$detalle['aula'].' '.$detalle['paralelo'].' · '.$detalle['periodo'],'nota'=>'Valoraciones independientes, no se calcula promedio.','cabeceras'=>['Cédula','Estudiante','Eje','Ámbito / indicador','T1','T2','T3'],'filas'=>$filas,'anchos'=>[19,38,38,48,10,10,10]];
  $xlsx=sgaXlsxGenerar($hojas);while(ob_get_level()>0)ob_end_clean();
  header('Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
  header('Content-Disposition: attachment; filename="EVALUACION_AULA_'.$detalle['aula_periodo_id'].'_'.date('Ymd').'.xlsx"');
  header('Content-Length: '.strlen($xlsx));header('Cache-Control: private, no-store');echo $xlsx;exit;
}
impedirNotasEnVisorComportamiento($oid);
$o=ofertaDetalle($oid);
if(!$o){http_response_code(404);die('Asignatura no encontrada.');}
try {
    $apid=(int)$o['aula_periodo_id'];
    $s=$conexion->prepare("SELECT m.id matricula_id,m.numero_lista,u.cedula,u.apellidos,u.nombres
        FROM matriculas m JOIN usuarios u ON u.id=m.estudiante_id
        WHERE m.aula_periodo_id=? AND m.estado='activo' AND u.activo=1
        ORDER BY COALESCE(m.numero_lista,9999),u.apellidos,u.nombres");
    $s->bind_param('i',$apid);sgaEjecutar($s,'consultar los estudiantes');$estudiantes=$s->get_result()->fetch_all(MYSQLI_ASSOC);$s->close();
    $s=$conexion->prepare('SELECT * FROM calificaciones_trimestre WHERE oferta_id=? AND trimestre BETWEEN 1 AND 3');
    $s->bind_param('i',$oid);sgaEjecutar($s,'consultar las calificaciones');
    $calificaciones=[];
    foreach($s->get_result()->fetch_all(MYSQLI_ASSOC) as $r)$calificaciones[(int)$r['matricula_id']][(int)$r['trimestre']]=$r;
    $s->close();
    $s=$conexion->prepare('SELECT matricula_id,examen_supletorio FROM notas_finales WHERE oferta_id=?');
    $s->bind_param('i',$oid);sgaEjecutar($s,'consultar los supletorios');
    $sups=[];foreach($s->get_result()->fetch_all(MYSQLI_ASSOC) as $r)$sups[(int)$r['matricula_id']]=$r['examen_supletorio']===null?null:(float)$r['examen_supletorio'];$s->close();
    $config=obtenerConfiguracion((int)$o['periodo_id']);
    $materia=(string)$o['asignatura'];$curso=$o['nivel'].' '.$o['aula'].' '.$o['paralelo'];
    $docente=trim($o['docente_apellidos'].' '.$o['docente_nombres']);
    $columnas=[
        ['No.',null],['Cédula',null],['Estudiante',null],
        ['Deber 1','deber_ap1'],['Deber 2','deber_ap2'],['Deber 3','deber_ap3'],['Ref. deber','deber_refuerzo'],['Prom. deber','deber_promedio'],
        ['Tarea 1','tarea_ap1'],['Tarea 2','tarea_ap2'],['Tarea 3','tarea_ap3'],['Ref. tarea','tarea_refuerzo'],['Prom. tarea','tarea_promedio'],
        ['Lección 1','leccion_ap1'],['Lección 2','leccion_ap2'],['Lección 3','leccion_ap3'],['Ref. lección','leccion_refuerzo'],['Prom. lección','leccion_promedio'],
        ['Grupo 1','grupo_ap1'],['Grupo 2','grupo_ap2'],['Grupo 3','grupo_ap3'],['Ref. grupo','grupo_refuerzo'],['Prom. grupo','grupo_promedio'],
        ['Prom. aportes','promedio_aportes'],['Ponderado aportes','ponderado_aportes'],
        ['Disciplina','nota_disciplinar'],['Ref. disciplinar','trabajo_refuerzo_disciplinar'],['Prom. disciplinar','promedio_disciplinar'],
        ['Producto final','nota_producto_final'],['Prom. sumativa','promedio_evaluacion_sumativa'],['Pond. sumativa','ponderado_sumativa'],
        ['Nota trimestre','nota_final'],['Equivalencia',null],
    ];
    $cabeceras=array_column($columnas,0);
    $especial=!empty($o['usa_literal_especial']);
    $resultadosCualitativos=!empty($o['aula_resultados_cualitativos']);
    $hojas=[];
    for($t=1;$t<=3;$t++){
        $estados=obtenerEstadoAportes($oid,$t);
        $filas=[];
        foreach($estudiantes as $i=>$est){
            $mid=(int)$est['matricula_id'];$db=$calificaciones[$mid][$t]??null;
            $fila=[($est['numero_lista']===null||$est['numero_lista']==='')?$i+1:(int)$est['numero_lista'],
                (string)$est['cedula'],trim($est['apellidos'].' '.$est['nombres'])];
            foreach(array_slice($columnas,3,-1) as $col){
                $campo=$col[1];
                if($db===null){$fila[]='';continue;}
                if(preg_match('/^(deber|tarea|leccion|grupo)_ap[123]$/',$campo)&&!aporteActivo($estados,$campo)){
                    $fila[]='';continue;
                }
                $v=$db[$campo]??null;$fila[]=$v===null?'':(($resultadosCualitativos && $campo==='nota_final')?sgaLetraResultadoCualitativo((float)$v):round((float)$v,2));
            }
            $fila[]=isset($db['nota_final'])?($resultadosCualitativos?sgaRangoResultadoCualitativo((float)$db['nota_final']):($especial?literalEspecial((float)$db['nota_final']):cualitativo((float)$db['nota_final'],$materia))):'Pendiente';
            $filas[]=$fila;
        }
        $hojas[]=[
          'nombre'=>'Trimestre '.$t,'titulo'=>'REGISTRO DE CALIFICACIONES · TRIMESTRE '.$t,
          'subtitulo'=>"$curso · $materia · Período ".$o['periodo'],
          'nota'=>'Docente: '.$docente.' | '.$t.'.° trimestre | '.count($estudiantes).' estudiantes (todos los registros)',
          'cabeceras'=>$cabeceras,'filas'=>$filas,
          'anchos'=>array_merge([10,19,39],array_fill(0,count($cabeceras)-4,17),[19]),
        ];
    }
    $resumen=[];
    foreach($estudiantes as $i=>$est){
        $mid=(int)$est['matricula_id'];$notas=[];
        for($t=1;$t<=3;$t++)$notas[$t]=isset($calificaciones[$mid][$t]['nota_final'])?(float)$calificaciones[$mid][$t]['nota_final']:null;
        $sup=$sups[$mid]??null;
        $f=calcularFinalAnual($notas[1],$notas[2],$notas[3],$sup,$config);
        $cv=static fn(?float $v)=>$v===null?'Pendiente':($resultadosCualitativos?sgaLetraResultadoCualitativo($v):round($v,2));
        $resumen[]=[($est['numero_lista']===null||$est['numero_lista']==='')?$i+1:(int)$est['numero_lista'],
           (string)$est['cedula'],trim($est['apellidos'].' '.$est['nombres']),
           $cv($notas[1]),$cv($notas[2]),$cv($notas[3]),$cv($f['promedio_tres']),
           $sup===null?'':$cv($sup),$cv($f['promedio_final']),
           $f['promedio_final']===null?'':($resultadosCualitativos?sgaRangoResultadoCualitativo((float)$f['promedio_final']):($especial?literalEspecial((float)$f['promedio_final']):cualitativo((float)$f['promedio_final'],$materia))),
           $f['observacion']];
    }
    $hojas[]=[
        'nombre'=>'Resumen anual','titulo'=>'CONSOLIDADO ANUAL DE CALIFICACIONES',
        'subtitulo'=>"$curso · $materia · Período ".$o['periodo'],
        'nota'=>'Los trimestres no registrados aparecen pendientes. Los supletorios solo se aplican a alumnos elegibles.',
        'cabeceras'=>['No.','Cédula','Estudiante','T1','T2','T3','Promedio 3T','Supletorio','Promedio final','Equivalencia','Estado'],
        'filas'=>$resumen,'anchos'=>[10,19,39,15,15,15,19,17,19,20,21],
    ];
    $xlsx=sgaXlsxGenerar($hojas);
    if(!$xlsx)throw new RuntimeException('No se pudo generar el libro de Excel.');
    $nombre='CALIFICACIONES_'.preg_replace('/[^A-Za-z0-9_-]+/','_',cuadroAnualMayusculas($curso.'_'.$materia)).'_'.date('Ymd').'.xlsx';
    while(ob_get_level()>0)ob_end_clean();
    header('Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
    header('Content-Disposition: attachment; filename="'.$nombre.'"');
    header('Content-Length: '.strlen($xlsx));
    header('Cache-Control: private, no-store, max-age=0');
    echo $xlsx;exit;
}catch(Throwable $e){
    error_log('[SGA] Fallo reporte XLSX de asignatura '.$oid.': '.$e->getMessage());
    flash('error','No se pudo generar el Excel: '.$e->getMessage());
    redir('modulos/calificaciones/index.php?oferta_id='.$oid);
}
