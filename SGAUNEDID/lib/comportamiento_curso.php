<?php
/**
 * Comportamiento por CURSO (aulas_periodo), trimestre y docente.
 * Las evaluaciones existentes ya usan matricula_id, que vincula al estudiante
 * a un curso y periodo, por eso no hace falta cambiar su estructura en MySQL.
 */

/** Soporta temporalmente enlaces antiguos ?oferta_id= sin asignar el
 * comportamiento a esa materia. La identidad del registro sera el curso. */
function resolverCursoComportamiento(array $parametros): int {
    $apid = (int)($parametros['aula_periodo_id'] ?? 0);
    if ($apid > 0) return $apid;
    $oid = (int)($parametros['oferta_id'] ?? 0);
    if ($oid <= 0 || !puedeGestionarOferta($oid)) return 0;
    $oferta = ofertaDetalle($oid);
    return $oferta && (int)$oferta['activo'] === 1 ? (int)$oferta['aula_periodo_id'] : 0;
}

function detalleCursoComportamiento(int $aulaPeriodoId): ?array {
    global $conexion;
    if ($aulaPeriodoId <= 0) return null;
    $stmt = $conexion->prepare("SELECT ap.id aula_periodo_id,ap.periodo_id,p.nombre periodo,
        a.id aula_id,a.codigo,a.nivel,a.nombre aula,a.paralelo,a.jornada_id
        FROM aulas_periodo ap
        JOIN aulas a ON a.id=ap.aula_id
        JOIN periodos_academicos p ON p.id=ap.periodo_id
        WHERE ap.id=? AND ap.activo=1 LIMIT 1");
    $stmt->bind_param('i', $aulaPeriodoId);
    $stmt->execute();
    $curso = $stmt->get_result()->fetch_assoc() ?: null;
    $stmt->close();
    return $curso;
}

/** La restriccion se comprueba en el servidor aunque se altere la URL. */
function puedeGestionarCursoComportamiento(array $curso): bool {
    global $conexion;
    if (empty($_SESSION['usuario_id'])) return false;
    if (esSuperadmin()) return true;
    $apid = (int)$curso['aula_periodo_id'];
    if (esSubadmin()) return puedeAccederAulaPeriodo($apid);
    $pid = (int)$curso['periodo_id'];
    if (!esDocenteOperativo($pid)) return false;
    $uid = (int)$_SESSION['usuario_id'];
    $stmt = $conexion->prepare('SELECT 1 FROM ofertas_academicas o WHERE o.aula_periodo_id=? AND o.docente_id=? AND o.activo=1 LIMIT 1');
    $stmt->bind_param('ii', $apid, $uid);
    $stmt->execute();
    $permitido = (bool)$stmt->get_result()->fetch_row();
    $stmt->close();
    return $permitido;
}

/** Distintos docentes, no asignaturas: un profesor que imparte dos materias
 * en el mismo curso aparece solo una vez para la evaluacion de comportamiento. */
function docentesCursoComportamiento(int $aulaPeriodoId): array {
    global $conexion;
    $stmt=$conexion->prepare("SELECT DISTINCT u.id,u.apellidos,u.nombres
        FROM ofertas_academicas o
        JOIN usuarios u ON u.id=o.docente_id AND u.activo=1
        WHERE o.aula_periodo_id=? AND o.activo=1
        ORDER BY u.apellidos,u.nombres,u.id");
    $stmt->bind_param('i',$aulaPeriodoId);
    $stmt->execute();
    $docentes=$stmt->get_result()->fetch_all(MYSQLI_ASSOC);
    $stmt->close();
    return $docentes;
}
