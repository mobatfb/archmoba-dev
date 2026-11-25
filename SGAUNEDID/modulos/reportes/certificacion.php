<?php
require_once __DIR__ . '/../../lib/funciones.php';
require_once __DIR__ . '/../../lib/reporte_academico_pdf.php';
exigirAdminAcademico();

$mid = (int)($_GET['matricula_id'] ?? 0);
$trimestre = (int)($_GET['trimestre'] ?? 0);
$vista = isset($_GET['vista']) && (string)$_GET['vista'] === '1';
if (!in_array($trimestre, [0, 1, 2, 3], true)) $trimestre = 0;
if ($mid <= 0) { http_response_code(400); die('Matrícula inválida.'); }
exigirAccesoMatricula($mid);

$stmt = $conexion->prepare("SELECT m.id, m.aula_periodo_id, u.cedula, u.apellidos, u.nombres,
    p.id periodo_id, p.nombre periodo, a.nivel, a.nombre aula, a.paralelo, a.resultados_cualitativos
    FROM matriculas m
    JOIN usuarios u ON u.id = m.estudiante_id
    JOIN aulas_periodo ap ON ap.id = m.aula_periodo_id
    JOIN periodos_academicos p ON p.id = ap.periodo_id
    JOIN aulas a ON a.id = ap.aula_id
    WHERE m.id = ? LIMIT 1");
$stmt->bind_param('i', $mid);
$stmt->execute();
$est = $stmt->get_result()->fetch_assoc();
$stmt->close();
if (!$est) { http_response_code(404); die('Matrícula no encontrada.'); }

$apid = (int)$est['aula_periodo_id'];
$stmt = $conexion->prepare("SELECT o.id, CASE WHEN o.evaluacion_aula=1 THEN 'Evaluación cualitativa del aula' ELSE s.nombre END asignatura, CASE WHEN o.evaluacion_aula=1 THEN 'Ejes y ámbitos' ELSE ar.nombre END area, ar.orden area_orden, s.usa_literal_especial, CASE WHEN o.evaluacion_aula=1 OR o.evaluacion_parametros_historica=1 THEN 0 ELSE s.solo_visor_comportamiento END solo_visor_comportamiento,(o.evaluacion_aula=1 OR o.evaluacion_parametros_historica=1) evaluacion_cualitativa_parametros,
    c1.nota_final t1, c1.cualitativo c1_cual,
    c2.nota_final t2, c2.cualitativo c2_cual,
    c3.nota_final t3, c3.cualitativo c3_cual,
    nf.examen_supletorio,cb1.literal comp_t1,cb2.literal comp_t2,cb3.literal comp_t3
    FROM ofertas_academicas o
    JOIN asignaturas s ON s.id = o.asignatura_id
    JOIN areas ar ON ar.id = s.area_id
    LEFT JOIN calificaciones_trimestre c1 ON c1.oferta_id = o.id AND c1.matricula_id = ? AND c1.trimestre = 1
    LEFT JOIN calificaciones_trimestre c2 ON c2.oferta_id = o.id AND c2.matricula_id = ? AND c2.trimestre = 2
    LEFT JOIN calificaciones_trimestre c3 ON c3.oferta_id = o.id AND c3.matricula_id = ? AND c3.trimestre = 3
    LEFT JOIN notas_finales nf ON nf.oferta_id = o.id AND nf.matricula_id = ?
    LEFT JOIN calificaciones_comportamiento_trimestre cb1 ON cb1.oferta_id=o.id AND cb1.matricula_id=? AND cb1.trimestre=1
    LEFT JOIN calificaciones_comportamiento_trimestre cb2 ON cb2.oferta_id=o.id AND cb2.matricula_id=? AND cb2.trimestre=2
    LEFT JOIN calificaciones_comportamiento_trimestre cb3 ON cb3.oferta_id=o.id AND cb3.matricula_id=? AND cb3.trimestre=3
    WHERE o.aula_periodo_id = ? AND o.activo = 1
    ORDER BY ar.orden, ar.nombre, s.nombre");
$stmt->bind_param('iiiiiiii', $mid, $mid, $mid, $mid, $mid, $mid, $mid, $apid);
$stmt->execute();
$rows = $stmt->get_result()->fetch_all(MYSQLI_ASSOC);
$stmt->close();

// La marca de comportamiento se interpreta en el formateador PDF usando
// exclusivamente las calificaciones de la asignatura asignada al aula.
// Los registros colectivos históricos quedan intactos, pero no se promedian.

$config = obtenerConfiguracion((int)$est['periodo_id']);
$informe = crearReporteAcademicoInstitucional($est, $rows, $trimestre, $config);
$archivo = $informe['filename'];

$uidAfectado = usuarioAfectadoPorMatricula($mid);
registrarAuditoria(
    'EXPORT', 'Reportes', 'certificacion_academica', $mid,
    ($trimestre ? 'Reporte institucional del trimestre ' . $trimestre : 'Reporte institucional anual')
        . ($vista ? ' visualizado' : ' descargado')
        . ' para ' . $est['apellidos'] . ' ' . $est['nombres'] . '.',
    $uidAfectado, null,
    [
        'trimestre' => $trimestre,
        'archivo' => $archivo,
        'periodo' => $est['periodo'],
        'registradas' => $informe['registradas'],
        'pendientes' => $informe['pendientes'],
        'vista_previa' => $vista,
    ],
    'exito', null, null, 'info'
);
$informe['pdf']->output($archivo, $vista);
