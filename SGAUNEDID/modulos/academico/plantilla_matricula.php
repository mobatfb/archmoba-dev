<?php
require_once __DIR__.'/../../lib/funciones.php';
exigirAdminAcademico();
$apId=(int)($_GET['aula_periodo_id']??0);
exigirAccesoAulaPeriodo($apId);
$stmt=$conexion->prepare('SELECT ap.id,p.nombre periodo,a.nivel,a.nombre aula,a.paralelo FROM aulas_periodo ap JOIN periodos_academicos p ON p.id=ap.periodo_id JOIN aulas a ON a.id=ap.aula_id WHERE ap.id=? LIMIT 1');
$stmt->bind_param('i',$apId);$stmt->execute();$ap=$stmt->get_result()->fetch_assoc();$stmt->close();
if(!$ap){http_response_code(404);die('Aula no encontrada.');}
$nombre='matricula_'.$ap['nivel'].'_'.$ap['aula'].'_'.$ap['paralelo'].'_'.$ap['periodo'].'.csv';
$nombre=preg_replace('/[^A-Za-z0-9._-]/','_',$nombre);
registrarAuditoria('EXPORT','Matrículas','plantilla_matricula',$apId,'Plantilla CSV de matrícula descargada para '.$ap['nivel'].' · '.$ap['aula'].' '.$ap['paralelo'].' · '.$ap['periodo'].'.',null,null,['archivo'=>$nombre,'aula_periodo_id'=>$apId],'exito',null,null,'info');
header('Content-Type: text/csv; charset=UTF-8');
header('Content-Disposition: attachment; filename="'.$nombre.'"');
echo "\xEF\xBB\xBF";
$out=fopen('php://output','w');
fputcsv($out,['aula_periodo_id',$apId]);
fputcsv($out,['cedula']);
for($i=0;$i<25;$i++)fputcsv($out,['']);
fclose($out);
exit;
