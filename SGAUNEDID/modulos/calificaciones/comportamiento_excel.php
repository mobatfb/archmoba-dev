<?php
require_once __DIR__.'/../../lib/funciones.php';
require_once __DIR__.'/../../lib/exportaciones_xlsx.php';
require_once __DIR__.'/../../lib/comportamiento_trimestres.php';
exigirLogin();
$oid=(int)($_GET['oferta_id']??0);
if(!$oid || !puedeGestionarOferta($oid)){http_response_code(403);die('Acceso no permitido.');}
$o=ofertaDetalle($oid);
if(!$o || empty($o['solo_visor_comportamiento']) || !(int)$o['activo']) {
    http_response_code(404);die('Asignatura de comportamiento no encontrada.');
}
$apid=(int)$o['aula_periodo_id'];
$stmt=$conexion->prepare("SELECT m.numero_lista,u.cedula,u.apellidos,u.nombres,
    cs1.literal t1,cs2.literal t2,cs3.literal t3
    FROM matriculas m JOIN usuarios u ON u.id=m.estudiante_id
    LEFT JOIN calificaciones_comportamiento_trimestre cs1
      ON cs1.matricula_id=m.id AND cs1.oferta_id=? AND cs1.trimestre=1
    LEFT JOIN calificaciones_comportamiento_trimestre cs2
      ON cs2.matricula_id=m.id AND cs2.oferta_id=? AND cs2.trimestre=2
    LEFT JOIN calificaciones_comportamiento_trimestre cs3
      ON cs3.matricula_id=m.id AND cs3.oferta_id=? AND cs3.trimestre=3
    WHERE m.aula_periodo_id=? AND m.estado='activo'
    ORDER BY COALESCE(m.numero_lista,999999),u.apellidos,u.nombres");
$stmt->bind_param('iiii',$oid,$oid,$oid,$apid);$stmt->execute();
$estudiantes=$stmt->get_result()->fetch_all(MYSQLI_ASSOC);$stmt->close();
$filas=[];
foreach($estudiantes as $i=>$r) {
    $filas[]=[(int)($r['numero_lista']?:($i+1)),(string)$r['cedula'],
        trim($r['apellidos'].' '.$r['nombres']),$r['t1']??'',$r['t2']??'',$r['t3']??'',
        sgaComportamientoFinal($r['t1'],$r['t2'],$r['t3'])??''];
}
$hojas=[[
    'nombre'=>'Comportamiento',
    'titulo'=>'REGISTRO CUALITATIVO DE COMPORTAMIENTO',
    'subtitulo'=>trim($o['nivel'].' '.$o['aula'].' '.$o['paralelo']).' · '.$o['asignatura'].' · '.$o['periodo'],
    'nota'=>'Promedio final cualitativo de los tres trimestres, de A+ a F-. Pendiente si falta algun trimestre.',
    'cabeceras'=>['No.','Cédula','Estudiante','Trimestre 1','Trimestre 2','Trimestre 3','Final'],
    'filas'=>$filas,'anchos'=>[10,19,45,20,20,20,20]
]];
$xlsx=sgaXlsxGenerar($hojas);
if(!$xlsx){http_response_code(500);die('No se pudo generar el Excel.');}
$nombre='COMPORTAMIENTO_'.preg_replace('/[^A-Za-z0-9_-]+/','_',strtoupper((string)$o['aula'].'_'.(string)$o['paralelo'])).'.xlsx';
while(ob_get_level()>0) ob_end_clean();
header('Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
header('Content-Disposition: attachment; filename="'.$nombre.'"');
header('Content-Length: '.strlen($xlsx));
header('Cache-Control: private, no-store, max-age=0');
echo $xlsx;
