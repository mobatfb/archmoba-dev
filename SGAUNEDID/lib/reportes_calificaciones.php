<?php
/**
 * Calcula las notas anuales de un aula en una sola consulta agrupada.
 * Evita el patron de 3 consultas por cada combinacion estudiante/asignatura.
 */
require_once __DIR__.'/funciones.php';
function sgaFinalesPorAula(int $aulaPeriodoId, int $periodoId): array {
    global $conexion;
    $config=obtenerConfiguracion($periodoId);
    $sql="SELECT m.id matricula_id,o.id oferta_id,c1.nota_final t1,c2.nota_final t2,c3.nota_final t3,nf.examen_supletorio
      FROM matriculas m
      JOIN ofertas_academicas o ON o.aula_periodo_id=m.aula_periodo_id AND o.activo=1
      JOIN asignaturas a ON a.id=o.asignatura_id
      LEFT JOIN calificaciones_trimestre c1 ON c1.matricula_id=m.id AND c1.oferta_id=o.id AND c1.trimestre=1
      LEFT JOIN calificaciones_trimestre c2 ON c2.matricula_id=m.id AND c2.oferta_id=o.id AND c2.trimestre=2
      LEFT JOIN calificaciones_trimestre c3 ON c3.matricula_id=m.id AND c3.oferta_id=o.id AND c3.trimestre=3
      LEFT JOIN notas_finales nf ON nf.matricula_id=m.id AND nf.oferta_id=o.id
      WHERE m.aula_periodo_id=? AND m.estado='activo'";
    $s=$conexion->prepare($sql);
    if (!$s) throw new RuntimeException('No se pudo preparar el consolidado academico.');
    $s->bind_param('i',$aulaPeriodoId);sgaEjecutar($s,'consultar notas consolidadas');
    $data=[];$res=$s->get_result();
    while($r=$res->fetch_assoc()) {
        $calcular=static function($v):?float {return $v===null?null:(float)$v;};
        $f=sgaResultadoAnual($calcular($r['t1']),$calcular($r['t2']),$calcular($r['t3']),$calcular($r['examen_supletorio']),$config);
        $f['examen_supletorio']=$calcular($r['examen_supletorio']);
        $data[(int)$r['matricula_id']][(int)$r['oferta_id']]=$f;
    }
    $s->close();return $data;
}
