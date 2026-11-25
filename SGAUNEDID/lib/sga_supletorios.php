<?php
/** Utilidades del módulo Supletorios. Reutiliza las reglas académicas de Calificaciones. */
require_once __DIR__ . '/funciones.php';

function sgaSupPuedeVerPeriodo(int $periodoId): bool {
    if ($periodoId <= 0) return false;
    if (esSuperadmin()) return true;
    if (esSubadmin()) return puedeAccederPeriodo($periodoId);
    return esDocenteOperativo($periodoId);
}

function sgaSupExigirOferta(int $ofertaId): array {
    exigirLogin();
    $oferta = $ofertaId > 0 ? ofertaDetalle($ofertaId) : null;
    if (!$oferta || !sgaSupPuedeVerPeriodo((int)$oferta['periodo_id']) ||
        !puedeGestionarOferta($ofertaId) || !empty($oferta['solo_visor_comportamiento']) || !empty($oferta['evaluacion_cualitativa_parametros']) || !empty($oferta['aula_evaluacion_parametros'])) {
        http_response_code(403);
        exit('No tienes acceso al supletorio de esta asignatura.');
    }
    return $oferta;
}

function sgaSupCsrf(): string {
    if (empty($_SESSION['csrf_sga_supletorios'])) {
        $_SESSION['csrf_sga_supletorios'] = bin2hex(random_bytes(32));
    }
    return (string)$_SESSION['csrf_sga_supletorios'];
}

function sgaSupValidarCsrf(): void {
    if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
        http_response_code(405);
        exit('Método no permitido.');
    }
    if (!hash_equals(sgaSupCsrf(), (string)($_POST['csrf'] ?? ''))) {
        throw new DomainException('La sesión del formulario caducó. Actualiza la página e inténtalo nuevamente.');
    }
}

function sgaSupRetorno(int $periodoId, int $ofertaId): string {
    return 'modulos/supletorios/index.php?periodo_id=' . $periodoId . '&oferta_id=' . $ofertaId . '&estado=casos#sga-sup-estudiantes';
}

/**
 * Determina la elegibilidad desde el mismo resultado y los mismos límites que
 * modulos/calificaciones/finales.php (sin alterar los datos originales).
 */
function sgaSupCalcularEstado(array $fila, array $config): array {
    $t1 = ($fila['t1'] ?? null) === null ? null : (float)$fila['t1'];
    $t2 = ($fila['t2'] ?? null) === null ? null : (float)$fila['t2'];
    $t3 = ($fila['t3'] ?? null) === null ? null : (float)$fila['t3'];
    $sup = ($fila['examen_supletorio'] ?? null) === null ? null : (float)$fila['examen_supletorio'];
    $resultado = calcularFinalAnual($t1, $t2, $t3, $sup, $config);
    $completo = $resultado['trimestres_completos'];
    $promedio = $resultado['promedio_tres'];
    $aplica = $completo && $promedio >= (float)$config['nota_min_supletorio']
        && $promedio < (float)$config['nota_aprobacion'];
    $registrado = $sup !== null && $sup > 0.0;
    $estado = !$completo ? 'incompleto'
        : (!$aplica ? ($sup !== null ? 'revisar' : 'no_aplica')
        : (!$registrado ? 'pendiente'
        : ($sup >= (float)$config['nota_aprobacion'] ? 'aprobado' : 'no_aprobado')));
    return [
        't1' => $t1, 't2' => $t2, 't3' => $t3, 'supletorio' => $sup,
        'resultado' => $resultado, 'aplica' => $aplica,
        'completo' => $completo, 'registrado' => $registrado, 'estado' => $estado,
    ];
}
