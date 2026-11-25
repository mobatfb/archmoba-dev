<?php
/**
 * Reglas de integridad academica compartidas entre docentes, reportes y administracion.
 * Este archivo no cambia permisos, sesiones ni credenciales (fase de seguridad excluida).
 */
function sgaResultadoAnual(?float $t1, ?float $t2, ?float $t3, ?float $sup, array $config): array {
    if ($t1 === null || $t2 === null || $t3 === null) {
        return ['promedio_tres'=>null, 'promedio_final'=>null,
            'observacion'=>'EN CURSO', 'trimestres_completos'=>false];
    }
    $promedio = truncar2(($t1+$t2+$t3)/3);
    $aprueba = (float)($config['nota_aprobacion'] ?? 7.0);
    $minimo = (float)($config['nota_min_supletorio'] ?? 4.0);
    if ($promedio >= $aprueba) {
        $final = $promedio;
        $estado = 'APROBADO';
    } elseif ($promedio < $minimo) {
        $final = $promedio;
        $estado = 'REPROBADO';
    } elseif ($sup === null || $sup <= 0.0) {
        // Sin examen guardado se conserva el promedio real, nunca un 0 artificial.
        $final = $promedio;
        $estado = 'SUPLETORIO';
    } elseif ($sup >= $aprueba) {
        $final = $aprueba;
        $estado = 'APROBADO';
    } else {
        $final = $promedio;
        $estado = 'REPROBADO';
    }
    return ['promedio_tres'=>$promedio, 'promedio_final'=>round($final,2),
        'observacion'=>$estado, 'trimestres_completos'=>true];
}

/** Valida que haya tres trimestres y que la nota anual requiera supletorio. */
function sgaValidarSupletorio(?float $t1, ?float $t2, ?float $t3, ?float $nota, array $config): void {
    if ($nota === null) return; // Se permite dejar el campo en blanco.
    if ($t1 === null || $t2 === null || $t3 === null)
        throw new DomainException('No se puede registrar supletorio: faltan trimestres por calificar.');
    $promedio=truncar2(($t1+$t2+$t3)/3);
    $apr=(float)($config['nota_aprobacion'] ?? 7.0);
    $min=(float)($config['nota_min_supletorio'] ?? 4.0);
    if ($promedio < $min || $promedio >= $apr)
        throw new DomainException('El estudiante no requiere supletorio con su promedio anual actual.');
    if ($nota <= 0 || $nota > 10)
        throw new DomainException('La nota de supletorio debe ser mayor a 0 y menor o igual a 10.');
}

/** Un periodo cerrado es historico: no se permiten escrituras academicas. */
function sgaAsegurarPeriodoEditable(int $periodoId): void {
    global $conexion;
    if ($periodoId <= 0) throw new DomainException('Periodo academico no valido.');
    $s=$conexion->prepare('SELECT estado FROM periodos_academicos WHERE id=? LIMIT 1');
    if (!$s) throw new RuntimeException('No se pudo verificar el periodo academico.');
    $s->bind_param('i',$periodoId);
    if (!$s->execute()) { $detalle=$s->error; $s->close(); throw new RuntimeException('No se pudo consultar el periodo: '.$detalle); }
    $row=$s->get_result()->fetch_assoc();$s->close();
    if (!$row) throw new DomainException('El periodo academico no existe.');
    if ($row['estado']==='cerrado') throw new DomainException('El periodo esta CERRADO. El historial academico es de solo lectura.');
}
function sgaAsegurarOfertaEditable(int $ofertaId): void {
    $of=ofertaDetalle($ofertaId);
    if (!$of) throw new DomainException('La asignatura no existe.');
    sgaAsegurarPeriodoEditable((int)$of['periodo_id']);
}
function sgaAsegurarAulaEditable(int $aulaPeriodoId): void {
    global $conexion;
    $s=$conexion->prepare('SELECT periodo_id FROM aulas_periodo WHERE id=? LIMIT 1');
    if (!$s) throw new RuntimeException('No se pudo verificar el aula.');
    $s->bind_param('i',$aulaPeriodoId);
    if (!$s->execute()) { $detalle=$s->error;$s->close();throw new RuntimeException('Error al consultar el aula: '.$detalle); }
    $row=$s->get_result()->fetch_assoc();$s->close();
    if (!$row) throw new DomainException('El aula no existe.');
    sgaAsegurarPeriodoEditable((int)$row['periodo_id']);
}

/** Asegura que una escritura se haya persistido: mysqli puede devolver false silenciosamente. */
function sgaEjecutar(mysqli_stmt $stmt, string $contexto='guardar la informacion'): void {
    if (!$stmt->execute()) throw new RuntimeException('Error al '.$contexto.': '.$stmt->error);
}

/** Las trazas criticas participan en la misma transaccion que las notas/asistencias. */
function sgaAuditoriaObligatoria(...$argumentos): void {
    if (!registrarAuditoria(...$argumentos))
        throw new RuntimeException('No se pudo registrar la auditoria; se cancelaron los cambios.');
}
