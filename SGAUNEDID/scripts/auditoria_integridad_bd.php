<?php
/** Diagnostico de solo lectura para ejecutar en PHP CLI del hosting.
 * php scripts/auditoria_integridad_bd.php
 * No repara ni elimina informacion. Nunca muestra credenciales ni nombres.
 */
if(PHP_SAPI!=='cli'){http_response_code(403);exit;}
require_once __DIR__.'/../lib/funciones.php';
$comprobaciones=[
 'Estudiantes con mas de una matricula activa en el mismo periodo'=>
    "SELECT COUNT(*) cantidad FROM (SELECT m.estudiante_id,ap.periodo_id
      FROM matriculas m JOIN aulas_periodo ap ON ap.id=m.aula_periodo_id
      WHERE m.estado='activo' GROUP BY m.estudiante_id,ap.periodo_id HAVING COUNT(*)>1) x",
 'Numeros de lista repetidos en el mismo paralelo'=>
    "SELECT COUNT(*) cantidad FROM (SELECT aula_periodo_id,numero_lista FROM matriculas
      WHERE estado='activo' AND numero_lista IS NOT NULL
      GROUP BY aula_periodo_id,numero_lista HAVING COUNT(*)>1) x",
 'Calificaciones asociadas a matriculas de otra aula'=>
    'SELECT COUNT(*) cantidad FROM calificaciones_trimestre ct JOIN matriculas m ON m.id=ct.matricula_id JOIN ofertas_academicas o ON o.id=ct.oferta_id WHERE m.aula_periodo_id<>o.aula_periodo_id',
 'Asistencias asociadas a matriculas de otra aula'=>
    'SELECT COUNT(*) cantidad FROM asistencia_detalle ad JOIN matriculas m ON m.id=ad.matricula_id JOIN asistencia_sesiones s ON s.id=ad.sesion_id JOIN ofertas_academicas o ON o.id=s.oferta_id WHERE m.aula_periodo_id<>o.aula_periodo_id',
 'Supletorios cargados sin las tres notas trimestrales'=>
    "SELECT COUNT(*) cantidad FROM notas_finales nf
      LEFT JOIN calificaciones_trimestre c1 ON c1.oferta_id=nf.oferta_id AND c1.matricula_id=nf.matricula_id AND c1.trimestre=1
      LEFT JOIN calificaciones_trimestre c2 ON c2.oferta_id=nf.oferta_id AND c2.matricula_id=nf.matricula_id AND c2.trimestre=2
      LEFT JOIN calificaciones_trimestre c3 ON c3.oferta_id=nf.oferta_id AND c3.matricula_id=nf.matricula_id AND c3.trimestre=3
      WHERE nf.examen_supletorio IS NOT NULL AND (c1.nota_final IS NULL OR c2.nota_final IS NULL OR c3.nota_final IS NULL)",
];
$errores=0;
echo "DIAGNOSTICO ACADEMICO SGA UNEDID (SOLO LECTURA)\n";
foreach($comprobaciones as $nombre=>$sql){
    $resultado=$conexion->query($sql);
    if(!$resultado){fwrite(STDERR,"ERROR consulta [$nombre]\n");$errores++;continue;}
    $cantidad=(int)($resultado->fetch_assoc()['cantidad']??0);$resultado->free();
    echo ($cantidad===0?'OK':'REVISAR')." | $nombre | $cantidad\n";
    if($cantidad!==0)$errores++;
}
echo "Este diagnostico NO modifica registros. Revise los casos detectados antes de corregir datos.\n";
exit($errores?1:0);
