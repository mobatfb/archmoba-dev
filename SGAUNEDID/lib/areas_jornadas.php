<?php
/**
 * SGA UNEDID - Jornadas de areas en UN CAMPO de la tabla areas.
 * areas.jornadas_ids contiene IDs separados por coma, ej.: 1,2.
 * No crea ni requiere tablas de relacion nuevas.
 */

function sgaAreasJornadasInstaladas(mysqli $db): bool {
    $r = $db->query("SELECT 1 FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='areas' AND column_name='jornadas_ids' LIMIT 1");
    if (!$r) return false;
    $ok = (bool)$r->fetch_row();
    $r->free();
    return $ok;
}

/** Opciones activas; el subadministrador solo visualiza sus jornadas autorizadas. */
function sgaAreasJornadasOpciones(mysqli $db): array {
    $r = $db->query('SELECT id,codigo,nombre,orden FROM jornadas WHERE activo=1 ORDER BY orden,nombre');
    if (!$r) throw new RuntimeException('No se pudieron consultar las jornadas.');
    $opciones = $r->fetch_all(MYSQLI_ASSOC);
    $r->free();
    if (esSuperadmin()) return $opciones;
    $periodoId = (int)(periodoActivo()['id'] ?? 0);
    $permitidas = jornadasPermitidasPeriodo($periodoId);
    return array_values(array_filter($opciones, static fn($j) => in_array((int)$j['id'], $permitidas, true)));
}

function sgaAreasJornadasValidarSeleccion($valores, array $opciones): array {
    if (!is_array($valores) || !$valores) throw new RuntimeException('Selecciona al menos una jornada para el area.');
    $permitidas = array_map('intval', array_column($opciones, 'id'));
    $ids = [];
    foreach ($valores as $v) {
        if (!is_scalar($v) || !preg_match('/^[1-9][0-9]*$/D', (string)$v)) {
            throw new RuntimeException('La jornada seleccionada no es valida.');
        }
        $id = (int)$v;
        if (!in_array($id, $permitidas, true)) {
            throw new RuntimeException('Hay jornadas inactivas o no autorizadas en la seleccion.');
        }
        $ids[$id] = $id;
    }
    return array_values($ids);
}

/** CSV: codigo MAT, nombre MATUTINA, o combinaciones MAT|VES. */
function sgaAreasJornadasLeerCsv(string $valor, array $opciones): array {
    $map = [];
    foreach ($opciones as $j) {
        $map[strtoupper(trim((string)$j['codigo']))] = (int)$j['id'];
        $map[strtoupper(trim((string)$j['nombre']))] = (int)$j['id'];
    }
    $encontradas = [];
    foreach (explode('|', $valor) as $parte) {
        $clave = strtoupper(trim($parte));
        if ($clave === '' || !isset($map[$clave])) {
            throw new RuntimeException('Jornada inexistente o no autorizada en CSV: '.($clave === '' ? '(vacia)' : $clave).'.');
        }
        $encontradas[] = (string)$map[$clave];
    }
    return sgaAreasJornadasValidarSeleccion($encontradas, $opciones);
}

/** Analiza el campo de IDs, descartando entradas invalidas sin conceder permisos. */
function sgaAreasJornadasDecodificar(?string $valor): array {
    if ($valor === null || trim($valor) === '') return [];
    $ids = [];
    foreach (explode(',', $valor) as $parte) {
        $parte = trim($parte);
        if ($parte === '' || !preg_match('/^[1-9][0-9]*$/D', $parte)) continue;
        $id = (int)$parte;
        $ids[$id] = $id;
    }
    return array_values($ids);
}

/** Devuelve los vinculos por area sin requerir una tabla intermedia. */
function sgaAreasJornadasTodas(mysqli $db): array {
    if (!sgaAreasJornadasInstaladas($db)) return [];
    $j = $db->query('SELECT id,nombre FROM jornadas ORDER BY orden,nombre');
    if (!$j) throw new RuntimeException('No se pudieron consultar las jornadas.');
    $nombres = [];
    foreach ($j->fetch_all(MYSQLI_ASSOC) as $fila) $nombres[(int)$fila['id']] = (string)$fila['nombre'];
    $j->free();
    $q = $db->query('SELECT id,jornadas_ids FROM areas');
    if (!$q) throw new RuntimeException('No se pudieron consultar las jornadas de las areas.');
    $vinculos = [];
    foreach ($q->fetch_all(MYSQLI_ASSOC) as $a) {
        $areaId = (int)$a['id'];
        $ids = sgaAreasJornadasDecodificar($a['jornadas_ids']);
        $etiquetas = [];
        foreach ($ids as $id) $etiquetas[] = $nombres[$id] ?? 'Jornada '.$id;
        $vinculos[$areaId] = ['ids'=>$ids, 'nombres'=>$etiquetas];
    }
    $q->free();
    return $vinculos;
}

/** Un subadministrador no modifica areas que contengan jornadas ajenas. */
function sgaAreasJornadasPuedeEditar(array $ids): bool {
    if (esSuperadmin()) return true;
    $periodoId = (int)(periodoActivo()['id'] ?? 0);
    $permitidas = jornadasPermitidasPeriodo($periodoId);
    return count($ids) > 0 && count(array_diff($ids, $permitidas)) === 0;
}

function sgaAreasJornadasExigirEdicion(mysqli $db, int $areaId): void {
    if (esSuperadmin()) return;
    if (!sgaAreasJornadasInstaladas($db)) {
        throw new RuntimeException('Instala SQL_SGA_AREAS_JORNADAS.sql para habilitar las jornadas.');
    }
    $s = $db->prepare('SELECT jornadas_ids FROM areas WHERE id=? AND archivado_en IS NULL LIMIT 1');
    if (!$s) throw new RuntimeException('No se pudieron consultar los permisos del area.');
    $s->bind_param('i', $areaId);
    $s->execute();
    $fila = $s->get_result()->fetch_assoc();
    $s->close();
    if (!$fila || !sgaAreasJornadasPuedeEditar(sgaAreasJornadasDecodificar($fila['jornadas_ids']))) {
        throw new RuntimeException('Esta area tiene jornadas no autorizadas o es compartida; solo el Administrador puede modificarla.');
    }
}

/** Guardar dentro de la transaccion del formulario/CSV. */
function sgaAreasJornadasGuardar(mysqli $db, int $areaId, array $ids): void {
    if (!sgaAreasJornadasInstaladas($db)) throw new RuntimeException('Falta la migracion SQL_SGA_AREAS_JORNADAS.sql.');
    if ($areaId <= 0 || !$ids) throw new RuntimeException('Area o jornadas invalidas.');
    $normalizados = [];
    foreach ($ids as $id) {
        $n = (int)$id;
        if ($n <= 0) throw new RuntimeException('Jornada invalida.');
        $normalizados[$n] = $n;
    }
    $valor = implode(',', array_values($normalizados));
    if (strlen($valor) > 512) throw new RuntimeException('Demasiadas jornadas para el area.');
    $stmt = $db->prepare('UPDATE areas SET jornadas_ids=? WHERE id=? AND archivado_en IS NULL');
    if (!$stmt) throw new RuntimeException('No se pudo preparar la actualizacion del area.');
    $stmt->bind_param('si', $valor, $areaId);
    if (!$stmt->execute()) { $stmt->close(); throw new RuntimeException('No se pudieron guardar las jornadas del area.'); }
    $stmt->close();
}

/** Habilita una jornada del subadministrador sin cambiar otras jornadas del area. */
function sgaAreasJornadasHabilitarPropia(mysqli $db,int $areaId,int $jornadaId): array {
    if (!esSubadmin() || esSuperadmin() || $jornadaId<=0 || !in_array($jornadaId,jornadasEnVista((int)(periodoActivo()['id']??0)),true))
        throw new RuntimeException('No tienes autorizacion sobre esta jornada.');
    $s=$db->prepare('SELECT activo,jornadas_ids FROM areas WHERE id=? AND archivado_en IS NULL FOR UPDATE');
    $s->bind_param('i',$areaId);$s->execute();$r=$s->get_result()->fetch_assoc();$s->close();
    if (!$r || (int)$r['activo']!==1) throw new RuntimeException('El area no existe o esta inactiva.');
    $anteriores=sgaAreasJornadasDecodificar($r['jornadas_ids']);
    $actuales=array_values(array_unique(array_merge($anteriores,[$jornadaId])));
    if (!in_array($jornadaId,$anteriores,true)) sgaAreasJornadasGuardar($db,$areaId,$actuales);
    return ['antes'=>$anteriores,'despues'=>$actuales];
}

/** No quitar una jornada del area si alguna asignatura del area la tiene habilitada. */
function sgaAreasJornadasValidarRetirada(mysqli $db,int $areaId,array $originales,array $nuevas): void {
    foreach(array_diff($originales,$nuevas) as $jid){
        $jid=(int)$jid;
        $s=$db->prepare('SELECT 1 FROM asignaturas WHERE area_id=? AND archivado_en IS NULL AND FIND_IN_SET(?,jornadas_ids)>0 LIMIT 1');
        $s->bind_param('ii',$areaId,$jid);$s->execute();$usada=(bool)$s->get_result()->fetch_row();$s->close();
        if($usada)throw new RuntimeException('Primero quita esta jornada de las asignaturas del area; no se puede desconectar un area que contiene materias habilitadas para esa jornada.');
    }
}
