<?php
/** Fuente compartida para la vista y las descargas de la lista de estudiantes. */
require_once __DIR__.'/funciones.php';

function listaEstudiantesCargar(int $ofertaId): array {
    global $conexion;
    exigirLogin();
    if ($ofertaId <= 0 || !puedeGestionarOferta($ofertaId)) {
        http_response_code(403);
        die('No tienes acceso a esta lista de estudiantes.');
    }
    $oferta = ofertaDetalle($ofertaId);
    if (!$oferta) { http_response_code(404); die('Asignación académica inexistente.'); }
    // La autorización se comprueba antes de utilizar el ID del aula del periodo.
    $aulaPeriodoId = (int)$oferta['aula_periodo_id'];
    $stmt = $conexion->prepare("SELECT m.numero_lista, u.cedula, u.apellidos, u.nombres, u.correo
        FROM matriculas m
        JOIN usuarios u ON u.id=m.estudiante_id
        WHERE m.aula_periodo_id=? AND m.estado='activo'
        ORDER BY COALESCE(m.numero_lista,2147483647), u.apellidos, u.nombres, u.id");
    $stmt->bind_param('i', $aulaPeriodoId);
    $stmt->execute();
    $estudiantes = $stmt->get_result()->fetch_all(MYSQLI_ASSOC);
    $stmt->close();
    return ['oferta'=>$oferta,'estudiantes'=>$estudiantes];
}
