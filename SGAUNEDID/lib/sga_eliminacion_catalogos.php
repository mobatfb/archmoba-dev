<?php
/**
 * SGA UNEDID - Borrado logico de areas y asignaturas.
 * La opcion "Borrar" oculta el catalogo de uso operativo y conserva
 * todas las filas y relaciones academicas historicas.
 * Requiere la migracion de archivado_en (parche previo) y la de sufijos DELETE.
 */

/**
 * Una asignatura puede estar asociada a cursos de varias jornadas.
 * El administrador principal puede archivarla globalmente; el subadministrador
 * solamente puede hacerlo si NINGUNA oferta relacionada queda fuera de sus
 * jornadas asignadas. Archivar nunca borra historiales de periodos cerrados.
 */
function sgaCatalogoVerificarAlcance(mysqli $db, string $tipo, int $id): void {
    if (esSuperadmin()) return;
    if (!esSubadmin()) {
        throw new RuntimeException('No tienes permisos para borrar este catalogo.');
    }
    $condicion = $tipo === 'areas' ? 's.area_id=?' : 's.id=?';
    $sql = 'SELECT DISTINCT ap.periodo_id,a.jornada_id
              FROM asignaturas s
              JOIN ofertas_academicas o ON o.asignatura_id=s.id
              JOIN aulas_periodo ap ON ap.id=o.aula_periodo_id
              JOIN aulas a ON a.id=ap.aula_id
             WHERE '.$condicion;
    $stmt = $db->prepare($sql);
    if (!$stmt) throw new RuntimeException('No fue posible comprobar los permisos por jornada.');
    $stmt->bind_param('i', $id);
    if (!$stmt->execute()) {
        $stmt->close();
        throw new RuntimeException('No fue posible validar las jornadas vinculadas.');
    }
    $result = $stmt->get_result();
    while ($fila = $result->fetch_assoc()) {
        if (!puedeAccederJornada((int)$fila['jornada_id'], (int)$fila['periodo_id'])) {
            $stmt->close();
            throw new RuntimeException('El registro tiene vinculos con otra jornada o periodo. Solicita al Administrador principal que lo borre del catalogo global.');
        }
    }
    $stmt->close();
}

/**
 * Conserva el codigo y nombre originales en columnas de respaldo y
 * anade [DELETE] para liberar el codigo/nombre para futuras altas.
 * Si ya hay otro registro con el mismo sufijo, usa [DELETE-2], [DELETE-3], etc.
 * Todas las comprobaciones y escrituras ocurren dentro de una transaccion.
 */
function sgaCatalogoGenerarEtiquetaBorrado(mysqli $db, string $tipo, int $id, ?string $codigo, string $nombre): array {
    if (!in_array($tipo, ['areas', 'asignaturas'], true)) {
        throw new RuntimeException('Catalogo no permitido.');
    }
    $check = $db->prepare('SELECT id FROM `'.$tipo.'` WHERE id<>? AND (nombre=? OR codigo=?) LIMIT 1');
    if (!$check) throw new RuntimeException('No se pudo verificar la unicidad del archivado.');
    try {
        // 1000 intentos impiden bucles indefinidos ante datos irregulares.
        // Normalmente la primera variante (sin numero) es suficiente.
        for ($n = 1; $n <= 1000; $n++) {
            $marca = $n === 1 ? '[DELETE]' : '[DELETE-'.$n.']';
            $nuevoCodigo = ($codigo === null || $codigo === '') ? $codigo : $codigo.$marca;
            $nuevoNombre = rtrim($nombre).' '.$marca;
            if (($nuevoCodigo !== null && mb_strlen_seguro_sga($nuevoCodigo) > 64)
                || mb_strlen_seguro_sga($nuevoNombre) > 200) {
                throw new RuntimeException('El codigo o nombre archivado supera el espacio disponible. Ejecuta la migracion SQL de este parche.');
            }
            $check->bind_param('iss', $id, $nuevoNombre, $nuevoCodigo);
            if (!$check->execute()) throw new RuntimeException('Error al comprobar un nombre disponible para el archivado.');
            $resultado = $check->get_result();
            if (!$resultado) throw new RuntimeException('No se pudo leer el resultado de unicidad.');
            $existe = (bool)$resultado->fetch_row();
            $resultado->free();
            if (!$existe) {
                return ['codigo'=>$nuevoCodigo, 'nombre'=>$nuevoNombre, 'marca'=>$marca];
            }
        }
        throw new RuntimeException('No se encontro una etiqueta de borrado unica.');
    } finally {
        $check->close();
    }
}

/** Cuenta caracteres UTF-8 sin depender de la extension mbstring. */
function mb_strlen_seguro_sga(string $valor): int {
    return function_exists('mb_strlen') ? mb_strlen($valor, 'UTF-8') : (preg_match_all('/./us', $valor) ?: 0);
}

/**
 * Renombra un registro para liberar ambos valores con indices UNIQUE,
 * guarda los textos originales y marca el borrado logico si aun esta visible.
 * $legacy=true solo se permite para registros previamente archivados.
 */
function sgaCatalogoRenombrarBorrado(mysqli $db, string $tipo, array $fila, bool $legacy = false): array {
    if (!in_array($tipo, ['areas','asignaturas'], true)) throw new RuntimeException('Catalogo invalido.');
    foreach (['id','codigo','nombre','archivado_en','codigo_original_borrado','nombre_original_borrado'] as $campo) {
        if (!array_key_exists($campo, $fila)) {
            throw new RuntimeException('Falta la migracion SQL de este parche. Ejecutala antes de usar Borrar.');
        }
    }
    $id = (int)$fila['id'];
    if ($id <= 0) throw new RuntimeException('Identificador no valido.');
    if ($legacy) {
        if ($fila['archivado_en'] === null || $fila['nombre_original_borrado'] !== null) {
            throw new RuntimeException('El registro no requiere la normalizacion anterior.');
        }
    } elseif ($fila['archivado_en'] !== null) {
        throw new RuntimeException('El registro ya estaba borrado.');
    }
    $originalCodigo = $fila['codigo'] === null ? null : (string)$fila['codigo'];
    $originalNombre = (string)$fila['nombre'];
    $nuevos = sgaCatalogoGenerarEtiquetaBorrado($db, $tipo, $id, $originalCodigo, $originalNombre);
    $nuevoCodigo = $nuevos['codigo'];
    $nuevoNombre = $nuevos['nombre'];
    $sql = 'UPDATE `'.$tipo.'` SET codigo=?, nombre=?, codigo_original_borrado=?, nombre_original_borrado=?, activo=0'
        .($legacy ? ' WHERE id=? AND archivado_en IS NOT NULL AND nombre_original_borrado IS NULL'
                  : ', archivado_en=NOW() WHERE id=? AND archivado_en IS NULL');
    $stmt = $db->prepare($sql);
    if (!$stmt) throw new RuntimeException('No se pudo preparar el borrado. Ejecuta primero la migracion SQL.');
    $stmt->bind_param('ssssi', $nuevoCodigo, $nuevoNombre, $originalCodigo, $originalNombre, $id);
    $exito = $stmt->execute();
    $afectadas = $stmt->affected_rows;
    $numeroError = $stmt->errno;
    $stmt->close();
    if (!$exito || $afectadas !== 1) {
        if ($numeroError === 1062) throw new RuntimeException('Conflicto de unicidad al archivar. Vuelve a intentarlo.');
        if ($numeroError === 1406) throw new RuntimeException('El campo de codigo o nombre es demasiado corto. Ejecuta la migracion SQL.');
        throw new RuntimeException('No fue posible guardar el registro archivado.');
    }
    return $nuevos;
}

/**
 * Funcion exclusiva para la pantalla del Administrador que convierte los
 * catalogos YA borrados con el parche anterior, sin modificar su fecha de
 * archivado, ID ni las relaciones academicas.
 */
function sgaCatalogoActualizarArchivadosPrevios(mysqli $db): array {
    if (!esSuperadmin()) throw new RuntimeException('Esta migracion solo la ejecuta el Administrador principal.');
    $totales = ['areas'=>0, 'asignaturas'=>0];
    if (!$db->begin_transaction()) throw new RuntimeException('No se pudo iniciar la migracion de archivados.');
    try {
        foreach (['areas','asignaturas'] as $tipo) {
            $res = $db->query('SELECT * FROM `'.$tipo.'` WHERE archivado_en IS NOT NULL '
                .'AND nombre_original_borrado IS NULL ORDER BY id FOR UPDATE');
            if (!$res) throw new RuntimeException('Ejecuta primero la migracion SQL: faltan las columnas de respaldo.');
            $filas = $res->fetch_all(MYSQLI_ASSOC);
            $res->free();
            foreach ($filas as $fila) {
                $nuevo = sgaCatalogoRenombrarBorrado($db, $tipo, $fila, true);
                $totales[$tipo]++;
                $despues = $fila;
                $despues['codigo_original_borrado'] = $fila['codigo'];
                $despues['nombre_original_borrado'] = $fila['nombre'];
                $despues['codigo'] = $nuevo['codigo'];
                $despues['nombre'] = $nuevo['nombre'];
                $despues['activo'] = 0;
                sgaAuditoriaObligatoria('UPDATE', $tipo === 'areas' ? 'Áreas' : 'Asignaturas',
                    $tipo === 'areas' ? 'area' : 'asignatura', (int)$fila['id'],
                    'Normalizacion de registro borrado anteriormente: se liberaron codigo y nombre con '. $nuevo['marca'] .'.',
                    null, $fila, $despues, 'exito', null, null, 'advertencia');
            }
        }
        if (!$db->commit()) throw new RuntimeException('No se pudo confirmar la migracion.');
        return $totales;
    } catch (Throwable $e) {
        try { $db->rollback(); } catch (Throwable $ignore) {}
        throw $e;
    }
}

/**
 * ARCHIVAR = no DELETE, no CASCADE y no se eliminan ofertas, notas ni asistencias.
 * El area archivada tambien archiva sus asignaturas que sigan visibles.
 * Todos los cambios, incluso los nombres/codigos, son transaccionales.
 */
function sgaCatalogoArchivar(mysqli $db, string $tipo, int $id, string $confirmacion): array {
    if (!in_array($tipo, ['areas', 'asignaturas'], true) || $id <= 0) {
        throw new RuntimeException('Tipo o identificador invalido.');
    }
    if ($confirmacion !== 'ELIMINAR') {
        throw new RuntimeException('Escribe ELIMINAR para confirmar que deseas ocultar el registro.');
    }
    if (!$db->begin_transaction()) throw new RuntimeException('No fue posible iniciar la operacion.');
    try {
        // Las tablas solo vienen de la lista cerrada anterior.
        $stmt = $db->prepare('SELECT * FROM `'.$tipo.'` WHERE id=? LIMIT 1 FOR UPDATE');
        if (!$stmt) throw new RuntimeException('No se pudo consultar el catalogo.');
        $stmt->bind_param('i', $id);
        if (!$stmt->execute()) {
            $stmt->close();
            throw new RuntimeException('No se pudo leer el registro.');
        }
        $antes = $stmt->get_result()->fetch_assoc();
        $stmt->close();
        if (!$antes) throw new RuntimeException('El registro no existe.');
        if (!array_key_exists('archivado_en', $antes)) {
            throw new RuntimeException('Ejecuta primero SQL_SGA_BORRADO_LOGICO_CATALOGOS.sql.');
        }
        if ($antes['archivado_en'] !== null) throw new RuntimeException('El registro ya esta oculto del catalogo.');
        if (!array_key_exists('codigo_original_borrado', $antes)) {
            throw new RuntimeException('Ejecuta primero SQL_SGA_SUFFIX_DELETE.sql incluido en este parche.');
        }
        $hijas = [];
        if ($tipo === 'areas') {
            $stmt = $db->prepare('SELECT * FROM asignaturas WHERE area_id=? ORDER BY id FOR UPDATE');
            if (!$stmt) throw new RuntimeException('No fue posible consultar las asignaturas del area.');
            $stmt->bind_param('i', $id);
            if (!$stmt->execute()) {
                $stmt->close();
                throw new RuntimeException('No fue posible leer las asignaturas del area.');
            }
            $hijas = $stmt->get_result()->fetch_all(MYSQLI_ASSOC);
            $stmt->close();
        }
        sgaCatalogoVerificarAlcance($db, $tipo, $id);

        $resumen = ['areas'=>0, 'asignaturas'=>0, 'ofertas_conservadas'=>0];
        $sqlOfertas = $tipo === 'areas'
            ? 'SELECT COUNT(*) total FROM ofertas_academicas o JOIN asignaturas s ON s.id=o.asignatura_id WHERE s.area_id=?'
            : 'SELECT COUNT(*) total FROM ofertas_academicas WHERE asignatura_id=?';
        $stmt = $db->prepare($sqlOfertas);
        if (!$stmt) throw new RuntimeException('No se pudo comprobar el historial vinculado.');
        $stmt->bind_param('i', $id);
        if (!$stmt->execute()) {
            $stmt->close();
            throw new RuntimeException('No se pudo contar el historial vinculado.');
        }
        $resumen['ofertas_conservadas'] = (int)($stmt->get_result()->fetch_assoc()['total'] ?? 0);
        $stmt->close();

        // Renombra primero el elemento solicitado: OVP -> OVP[DELETE].
        $nuevo = sgaCatalogoRenombrarBorrado($db, $tipo, $antes);
        $resumen[$tipo] = 1;

        if ($tipo === 'areas') {
            foreach ($hijas as $hija) {
                if ($hija['archivado_en'] !== null) continue;
                sgaCatalogoRenombrarBorrado($db, 'asignaturas', $hija);
                $resumen['asignaturas']++;
            }
        }

        $stmt = $db->prepare('SELECT * FROM `'.$tipo.'` WHERE id=? LIMIT 1');
        if (!$stmt) throw new RuntimeException('No se pudo verificar el cambio de nombre.');
        $stmt->bind_param('i', $id);
        if (!$stmt->execute()) { $stmt->close(); throw new RuntimeException('No fue posible leer el registro archivado.'); }
        $despues = $stmt->get_result()->fetch_assoc();
        $stmt->close();
        $detalle = 'BORRADO LOGICO: '.($tipo === 'areas' ? 'Area' : 'Asignatura')
            .' retirada del catalogo. Codigo anterior: '.(string)($antes['codigo'] ?? 'SIN CODIGO')
            .'. Codigo archivado: '.(string)($despues['codigo'] ?? 'SIN CODIGO')
            .'. Nombre anterior: '.(string)$antes['nombre']
            .'. Nombre archivado: '.(string)$despues['nombre']
            .'. Asignaturas ocultadas: '.$resumen['asignaturas']
            .'. Ofertas academicas conservadas: '.$resumen['ofertas_conservadas'].'.';
        if ($tipo === 'areas' && $hijas) {
            $detalle .= ' IDs de asignaturas asociadas (primeras 15): '.implode(',', array_map(
                static fn($h) => (string)$h['id'], array_slice($hijas, 0, 15)
            )).'.';
        }
        sgaAuditoriaObligatoria('UPDATE', $tipo === 'areas' ? 'Áreas' : 'Asignaturas',
            $tipo === 'areas' ? 'area' : 'asignatura', $id, $detalle,
            null, $antes, $despues, 'exito', null, null, 'advertencia');
        if (!$db->commit()) throw new RuntimeException('No se pudo confirmar el borrado logico.');
        return $resumen;
    } catch (Throwable $e) {
        try { $db->rollback(); } catch (Throwable $ignore) {}
        throw $e;
    }
}
