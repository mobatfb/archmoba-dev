<?php
require_once __DIR__ . '/../config/conexion.php';

function exigirLogin(): void {
    if (empty($_SESSION['usuario_id'])) {
        header('Location: ' . url('index.php'));
        exit;
    }
    $u=usuarioActual();
    if(!$u || (int)$u['activo']!==1){
        $_SESSION=[];
        if(session_status()===PHP_SESSION_ACTIVE) session_destroy();
        header('Location: ' . url('index.php'));
        exit;
    }
}

function usuarioActual(): ?array {
    global $conexion;
    if (empty($_SESSION['usuario_id'])) return null;
    static $cache = null;
    if ($cache !== null) return $cache;
    $id=(int)$_SESSION['usuario_id'];
    $stmt=$conexion->prepare('SELECT id,cedula,apellidos,nombres,correo,activo FROM usuarios WHERE id=? LIMIT 1');
    $stmt->bind_param('i',$id);$stmt->execute();$cache=$stmt->get_result()->fetch_assoc() ?: null;$stmt->close();
    return $cache;
}

function periodoActivo(): ?array {
    global $conexion;
    static $cache = false;
    if ($cache !== false) return $cache;
    $res=$conexion->query("SELECT * FROM periodos_academicos WHERE estado='activo' ORDER BY anio_inicio DESC,id DESC LIMIT 1");
    $cache=$res?($res->fetch_assoc() ?: null):null;
    return $cache;
}

function tieneRol(string $codigo, ?int $periodoId = null): bool {
    global $conexion;
    if (empty($_SESSION['usuario_id'])) return false;
    $uid=(int)$_SESSION['usuario_id'];
    if ($codigo === 'superadmin' || $codigo === 'subadmin' || $codigo === 'representante') {
        $stmt=$conexion->prepare('SELECT 1 FROM usuario_roles ur JOIN roles r ON r.id=ur.rol_id WHERE ur.usuario_id=? AND r.codigo=? AND ur.periodo_id IS NULL LIMIT 1');
        $stmt->bind_param('is',$uid,$codigo);$stmt->execute();$ok=(bool)$stmt->get_result()->fetch_row();$stmt->close();return $ok;
    }
    if ($periodoId === null) {
        $p=periodoActivo();$periodoId=$p?(int)$p['id']:0;
    }
    if (!$periodoId) return false;
    $stmt=$conexion->prepare('SELECT 1 FROM usuario_roles ur JOIN roles r ON r.id=ur.rol_id WHERE ur.usuario_id=? AND r.codigo=? AND ur.periodo_id=? LIMIT 1');
    $stmt->bind_param('isi',$uid,$codigo,$periodoId);$stmt->execute();$ok=(bool)$stmt->get_result()->fetch_row();$stmt->close();return $ok;
}

function esSuperadmin(): bool {
    if (!tieneRol('superadmin')) return false;
    // Una cuenta administradora que tambien representa estudiantes solo obtiene
    // permisos de administracion mientras opera expresamente como Administrador.
    // No se confia en el valor de sesion si el rol Representante no esta asignado.
    $pid = (int)(periodoActivo()['id'] ?? 0);
    return !((string)($_SESSION['rol_operativo'] ?? '') === 'representante'
        && (int)($_SESSION['rol_operativo_periodo'] ?? -1) === $pid
        && tieneRol('representante'));
}

/**
 * La alternancia se habilita UNICAMENTE cuando coexisten el rol subadmin global,
 * el rol docente del periodo activo y al menos una asignatura activa del usuario.
 * No se otorgan roles ni se modifica la base de datos al alternar.
 */
function puedeAlternarRolDocente(?int $periodoId = null): bool {
    global $conexion;
    if (empty($_SESSION['usuario_id']) || esSuperadmin() || !tieneRol('subadmin')) return false;
    $activo = periodoActivo();
    $idActivo = (int)($activo['id'] ?? 0);
    if (!$idActivo || ($periodoId !== null && $periodoId !== $idActivo)) return false;
    $uid = (int)$_SESSION['usuario_id'];
    static $cache = [];
    $clave = $uid . ':' . $idActivo;
    if (array_key_exists($clave, $cache)) return $cache[$clave];
    if (!tieneRol('docente', $idActivo)) return $cache[$clave] = false;
    $stmt = $conexion->prepare('SELECT 1 FROM ofertas_academicas o '
        . 'JOIN aulas_periodo ap ON ap.id=o.aula_periodo_id '
        . 'JOIN asignaturas s ON s.id=o.asignatura_id '
        . 'JOIN areas ar ON ar.id=s.area_id '
        . 'WHERE s.archivado_en IS NULL AND ar.archivado_en IS NULL AND o.docente_id=? AND ap.periodo_id=? '
        . 'AND o.activo=1 AND ap.activo=1 LIMIT 1');
    if (!$stmt) return $cache[$clave] = false;
    $stmt->bind_param('ii', $uid, $idActivo);
    $ok = $stmt->execute() && (bool)$stmt->get_result()->fetch_row();
    $stmt->close();
    return $cache[$clave] = $ok;
}

/** Roles operativos disponibles para esta cuenta. No otorga permisos nuevos. */
function rolesOperativosDisponibles(): array {
    if (tieneRol('superadmin')) {
        // El rol Representante es compatible con Administrador, pero operar
        // como representante no debe conservar privilegios administrativos.
        $roles = ['superadmin'];
        if (tieneRol('representante')) $roles[] = 'representante';
        return $roles;
    }
    $roles = [];
    if (tieneRol('subadmin')) {
        $roles[] = 'subadmin';
        // Docencia de subadministrador solo si tiene asignaturas activas.
        if (puedeAlternarRolDocente()) $roles[] = 'docente';
    } elseif (tieneRol('docente')) {
        $roles[] = 'docente';
    } elseif (tieneRol('estudiante')) {
        $roles[] = 'estudiante';
    }
    // El representante es permanente y puede coexistir con el rol laboral.
    if (tieneRol('representante')) $roles[] = 'representante';
    return $roles;
}

/** Rol operativo autorizado para esta solicitud. El cambio nunca altera la BD. */
function rolOperativoActual(): string {
    $disponibles = rolesOperativosDisponibles();
    if (!$disponibles) return '';
    $pid = (int)(periodoActivo()['id'] ?? 0);
    $pedido = (string)($_SESSION['rol_operativo'] ?? '');
    if ((int)($_SESSION['rol_operativo_periodo'] ?? -1) === $pid
        && in_array($pedido, $disponibles, true)) return $pedido;
    // Prioridad por defecto: Subadministrador > Docente > Estudiante > Representante.
    return $disponibles[0];
}

function esSubadmin(): bool {
    return tieneRol('subadmin') && rolOperativoActual() === 'subadmin';
}

function esDocenteOperativo(?int $periodoId = null): bool {
    if (!tieneRol('docente', $periodoId)) return false;
    return esSuperadmin() || rolOperativoActual() === 'docente';
}

function esEstudianteOperativo(?int $periodoId = null): bool {
    return tieneRol('estudiante', $periodoId) && rolOperativoActual() === 'estudiante';
}

function esRepresentanteOperativo(): bool {
    return tieneRol('representante') && rolOperativoActual() === 'representante';
}

function esAdminAcademico(): bool { return esSuperadmin() || esSubadmin(); }
function exigirSuperadmin(): void { exigirLogin(); if(!esSuperadmin()){http_response_code(403);die('Acceso restringido al administrador.');} }
function exigirAdminAcademico(): void { exigirLogin(); if(!esAdminAcademico()){http_response_code(403);die('Acceso restringido a la administración académica.');} }

function asignarRolPeriodo(int $usuarioId,string $codigo,int $periodoId): void {
    global $conexion;
    $stmt=$conexion->prepare('SELECT id FROM roles WHERE codigo=? LIMIT 1');$stmt->bind_param('s',$codigo);$stmt->execute();$r=$stmt->get_result()->fetch_assoc();$stmt->close();
    if(!$r) return;
    $rolId=(int)$r['id'];
    $stmt=$conexion->prepare('SELECT id FROM usuario_roles WHERE usuario_id=? AND rol_id=? AND periodo_id=? LIMIT 1');$stmt->bind_param('iii',$usuarioId,$rolId,$periodoId);$stmt->execute();$ex=$stmt->get_result()->fetch_assoc();$stmt->close();
    if(!$ex){$stmt=$conexion->prepare('INSERT INTO usuario_roles(usuario_id,rol_id,periodo_id) VALUES(?,?,?)');$stmt->bind_param('iii',$usuarioId,$rolId,$periodoId);$stmt->execute();$urId=(int)$conexion->insert_id;$stmt->close();if(function_exists('registrarAuditoria'))registrarAuditoria('ASSIGN_ROLE','Usuarios','usuario_rol',$urId,'Rol '.$codigo.' asignado al usuario para el periodo '.$periodoId.'.',$usuarioId,null,['rol'=>$codigo,'periodo_id'=>$periodoId],'exito',null,null,'advertencia');}
}

function puedeGestionarOferta(int $ofertaId): bool {
    global $conexion;
    exigirLogin();
    if ($ofertaId <= 0) return false;
    $check = $conexion->prepare('SELECT 1 FROM ofertas_academicas o JOIN asignaturas s ON s.id=o.asignatura_id JOIN areas ar ON ar.id=s.area_id WHERE o.id=? AND s.archivado_en IS NULL AND ar.archivado_en IS NULL LIMIT 1');
    if (!$check) return false;
    $check->bind_param('i', $ofertaId);
    $valida = $check->execute() && (bool)$check->get_result()->fetch_row();
    $check->close();
    if (!$valida) return false;
    if(esSuperadmin()) return true;
    if(esSubadmin()) return puedeAccederOfertaSubadmin($ofertaId);
    if (!esDocenteOperativo()) return false;
    $uid=(int)$_SESSION['usuario_id'];
    $stmt=$conexion->prepare('SELECT 1 FROM ofertas_academicas o JOIN aulas_periodo ap ON ap.id=o.aula_periodo_id WHERE o.id=? AND o.docente_id=? AND o.activo=1 AND (ap.evaluacion_cualitativa_parametros=0 OR o.evaluacion_aula=1) LIMIT 1');
    $stmt->bind_param('ii',$ofertaId,$uid);$stmt->execute();$ok=(bool)$stmt->get_result()->fetch_row();$stmt->close();return $ok;
}

function rolesVisiblesUsuario(int $usuarioId): array {
    global $conexion;
    $stmt=$conexion->prepare('SELECT r.codigo,r.nombre,p.nombre periodo FROM usuario_roles ur JOIN roles r ON r.id=ur.rol_id LEFT JOIN periodos_academicos p ON p.id=ur.periodo_id WHERE ur.usuario_id=? ORDER BY r.nombre,p.nombre');
    $stmt->bind_param('i',$usuarioId);$stmt->execute();$rows=$stmt->get_result()->fetch_all(MYSQLI_ASSOC);$stmt->close();return $rows;
}

require_once __DIR__ . '/permisos_jornadas.php';
