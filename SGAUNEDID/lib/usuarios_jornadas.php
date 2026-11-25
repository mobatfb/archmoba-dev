<?php
/**
 * Jornadas de personas (usuarios_jornadas_gestion) por periodo.
 * No cambia los permisos del rol Subadministrador, que siguen viviendo en
 * subadministrador_jornadas y solo se administran desde Roles de usuarios.
 */

/** Catalogo visible para asignar a personas; el subadmin solo ve sus jornadas autorizadas. */
function sgaUJCatalogo(int $periodoId): array {
    global $conexion;
    if ($periodoId<=0) return [];
    $sql='SELECT id,codigo,nombre FROM jornadas WHERE activo=1';
    if (esSubadmin()) {
        $ids=jornadasPermitidasPeriodo($periodoId);
        if (!$ids) return [];
        $sql.=' AND id IN ('.implode(',',array_map('intval',$ids)).')';
    }
    $rs=$conexion->query($sql.' ORDER BY orden,nombre,id');
    if (!$rs) throw new RuntimeException('No se pudo consultar las jornadas.');
    return $rs->fetch_all(MYSQLI_ASSOC);
}

/** Valida todos los IDs en servidor; nunca acepta una jornada que no este en el catalogo autorizado. */
function sgaUJValidarIds(array $valores,array $catalogo,bool $requerido): array {
    $permitidas=[];
    foreach ($catalogo as $j) $permitidas[(int)$j['id']]=true;
    $ids=[];
    foreach ($valores as $valor) {
        if (!is_scalar($valor) || !ctype_digit((string)$valor) || (int)$valor<=0)
            throw new RuntimeException('La selección contiene una jornada no válida.');
        $id=(int)$valor;
        if (!isset($permitidas[$id]))
            throw new RuntimeException('Seleccionaste una jornada inexistente, inactiva o sin autorización.');
        $ids[$id]=true;
    }
    if ($requerido && !$ids) throw new RuntimeException('Selecciona al menos una jornada.');
    return array_keys($ids);
}

/** Convierte codigos/nombres del CSV, separados con |, a IDs de jornadas autorizadas. */
function sgaUJClaveCsv(string $texto): string {
    $v=trim($texto);
    $v=function_exists('mb_strtolower')?mb_strtolower($v,'UTF-8'):strtolower($v);
    $v=strtr($v,['á'=>'a','é'=>'e','í'=>'i','ó'=>'o','ú'=>'u','ü'=>'u','ñ'=>'n']);
    return preg_replace('/\s+/u',' ',trim($v)) ?: '';
}
function sgaUJDesdeCsv(string $celda,array $catalogo,int $fila,bool $requerido): array {
    $celda=trim($celda);
    if ($celda==='') {
        if ($requerido) throw new RuntimeException("Fila $fila: indica una o varias jornadas.");
        return [];
    }
    $ind=[];
    foreach ($catalogo as $j) {
        foreach ([(string)$j['id'],(string)$j['codigo'],(string)$j['nombre']] as $token) {
            $clave=sgaUJClaveCsv($token);
            if ($clave!=='') $ind[$clave]=(int)$j['id'];
        }
    }
    $ids=[];
    foreach (explode('|',$celda) as $token) {
        $clave=sgaUJClaveCsv($token);
        if ($clave==='' || !isset($ind[$clave]))
            throw new RuntimeException("Fila $fila: la jornada '".trim($token)."' no existe, está inactiva o no tienes autorización.");
        $ids[$ind[$clave]]=true;
    }
    return array_keys($ids);
}

/** Jornadas de gestion registradas para la persona, sin modificar periodos ajenos. */
function sgaUJAsignadas(int $usuarioId,int $periodoId): array {
    global $conexion;
    if ($usuarioId<=0 || $periodoId<=0) return [];
    $s=$conexion->prepare('SELECT jornada_id FROM usuarios_jornadas_gestion WHERE usuario_id=? AND periodo_id=? ORDER BY jornada_id');
    if (!$s) throw new RuntimeException('No se pudieron consultar las jornadas del usuario.');
    $s->bind_param('ii',$usuarioId,$periodoId);
    if (!$s->execute()) throw new RuntimeException('No se pudieron recuperar las jornadas del usuario.');
    $ids=array_map('intval',array_column($s->get_result()->fetch_all(MYSQLI_ASSOC),'jornada_id'));
    $s->close();return $ids;
}

/** Dentro de la transaccion del llamador: sustituye las jornadas, nunca el historial academico. */
function sgaUJGuardar(int $usuarioId,int $periodoId,array $nuevas): bool {
    global $conexion;
    if ($usuarioId<=0 || $periodoId<=0) {
        if ($nuevas) throw new RuntimeException('Selecciona un período académico para asignar jornadas.');
        return false;
    }
    $anteriores=sgaUJAsignadas($usuarioId,$periodoId);
    $nuevas=array_values(array_unique(array_map('intval',$nuevas)));
    sort($nuevas);sort($anteriores);
    if ($anteriores===$nuevas) return false;
    if (esSubadmin()) {
        $autorizadas=jornadasPermitidasPeriodo($periodoId);
        if (array_diff($anteriores,$autorizadas) || array_diff($nuevas,$autorizadas))
            throw new RuntimeException('No puedes modificar jornadas que no administras.');
    }
    $s=$conexion->prepare('DELETE FROM usuarios_jornadas_gestion WHERE usuario_id=? AND periodo_id=?');
    if (!$s) throw new RuntimeException('No se pudo actualizar las jornadas.');
    $s->bind_param('ii',$usuarioId,$periodoId);
    if (!$s->execute()) throw new RuntimeException('No se pudieron desvincular las jornadas anteriores.');
    $s->close();
    if ($nuevas) {
        $s=$conexion->prepare('INSERT INTO usuarios_jornadas_gestion (usuario_id,periodo_id,jornada_id) VALUES (?,?,?)');
        if (!$s) throw new RuntimeException('No se pudo guardar las jornadas del usuario.');
        foreach ($nuevas as $id) {
            $s->bind_param('iii',$usuarioId,$periodoId,$id);
            if (!$s->execute()) throw new RuntimeException('No se pudo registrar una de las jornadas.');
        }
        $s->close();
    }
    return true;
}

/** El subadministrador puede editar roles academicos de SUS personas, no roles globales de gestión. */
function sgaUJGuardarRolesSubadmin(int $usuarioId,int $periodoId,array $solicitados): array {
    global $conexion;
    if (!esSubadmin() || !puedeGestionarUsuarioJornada($usuarioId,$periodoId))
        throw new RuntimeException('No tienes permiso para modificar los roles de esta cuenta.');
    if (tieneRolGlobalUsuario($usuarioId))
        throw new RuntimeException('No puedes modificar una cuenta administrativa.');
    $roles=sgaValidarListaRoles($solicitados);
    foreach ($roles as $rol) {
        if (!in_array($rol,['docente','estudiante','representante'],true))
            throw new RuntimeException('Los roles administrativos se gestionan desde Roles de usuarios.');
    }
    $rs=$conexion->query("SELECT id,codigo FROM roles WHERE codigo IN ('docente','estudiante','representante')");
    if (!$rs) throw new RuntimeException('No se pudo validar el catálogo de roles.');
    $rolIds=[];
    foreach($rs->fetch_all(MYSQLI_ASSOC) as $fila) $rolIds[$fila['codigo']]=(int)$fila['id'];
    foreach($roles as $rol) if (empty($rolIds[$rol])) throw new RuntimeException('El rol '.$rol.' no existe en el catálogo.');
    $s=$conexion->prepare("SELECT r.codigo FROM usuario_roles ur JOIN roles r ON r.id=ur.rol_id WHERE ur.usuario_id=? AND ((ur.periodo_id=? AND r.codigo IN ('docente','estudiante')) OR (ur.periodo_id IS NULL AND r.codigo='representante'))");
    if (!$s) throw new RuntimeException('No se pudieron leer los roles actuales.');
    $s->bind_param('ii',$usuarioId,$periodoId);
    if (!$s->execute()) throw new RuntimeException('No se pudieron validar los roles actuales.');
    $anteriores=array_column($s->get_result()->fetch_all(MYSQLI_ASSOC),'codigo');$s->close();
    foreach (array_diff($anteriores,$roles) as $rol) sgaValidarRetiradaRol($usuarioId,$rol,$periodoId);
    foreach (array_diff($anteriores,$roles) as $rol) {
        if ($rol==='representante') {
            $s=$conexion->prepare('SELECT 1 FROM sga_representantes_estudiantes WHERE representante_id=? AND activo=1 LIMIT 1');
            $s->bind_param('i',$usuarioId);$s->execute();$vinculos=(bool)$s->get_result()->fetch_row();$s->close();
            if ($vinculos) throw new RuntimeException('El representante tiene hijos vinculados. Desvincúlalos antes de retirar el rol.');
            $idRol=$rolIds['representante'];
            $s=$conexion->prepare('DELETE FROM usuario_roles WHERE usuario_id=? AND rol_id=? AND periodo_id IS NULL');
            $s->bind_param('ii',$usuarioId,$idRol);
            if (!$s->execute()) throw new RuntimeException('No se pudo retirar el rol Representante.');
            $s->close();continue;
        }
        $idRol=$rolIds[$rol];
        $s=$conexion->prepare('DELETE FROM usuario_roles WHERE usuario_id=? AND rol_id=? AND periodo_id=?');
        $s->bind_param('iii',$usuarioId,$idRol,$periodoId);
        if (!$s->execute()) throw new RuntimeException('No se pudo retirar el rol '.$rol.'.');
        $s->close();
    }
    foreach (array_diff($roles,$anteriores) as $rol) {
        if ($rol==='representante') {establecerRolUsuario($usuarioId,'representante',$periodoId,false);continue;}
        $idRol=$rolIds[$rol];
        $s=$conexion->prepare('INSERT INTO usuario_roles (usuario_id,rol_id,periodo_id) VALUES (?,?,?)');
        $s->bind_param('iii',$usuarioId,$idRol,$periodoId);
        if (!$s->execute()) throw new RuntimeException('No se pudo asignar el rol '.$rol.'.');
        $s->close();
    }
    return $roles;
}
