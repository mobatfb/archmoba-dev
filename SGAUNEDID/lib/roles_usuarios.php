<?php
/** Reglas comunes de roles. El llamador controla la transaccion. */
require_once __DIR__ . '/auth.php';

function normalizarRolUsuario(string $entrada): string {
    $rol=strtolower(trim($entrada));
    $rol=strtr($rol,['á'=>'a','é'=>'e','í'=>'i','ó'=>'o','ú'=>'u','ñ'=>'n']);
    $rol=preg_replace('/\s+/u',' ',$rol)?:$rol;
    $sinonimos=[
        'admin'=>'superadmin','administrador'=>'superadmin','superadmin'=>'superadmin','super administrador'=>'superadmin',
        'subadmin'=>'subadmin','subadministrador'=>'subadmin','sub administrador'=>'subadmin',
        'docente'=>'docente','profesor'=>'docente','profesora'=>'docente',
        'estudiante'=>'estudiante','alumno'=>'estudiante','alumna'=>'estudiante',
        'representante'=>'representante','padre'=>'representante','madre'=>'representante','representante legal'=>'representante'
    ];
    return $sinonimos[$rol]??'';
}

function obtenerRolPrincipalUsuario(int $usuarioId,int $periodoId): string {
    global $conexion;
    $s=$conexion->prepare("SELECT r.codigo FROM usuario_roles ur JOIN roles r ON r.id=ur.rol_id
          WHERE ur.usuario_id=? AND ((r.codigo IN ('superadmin','subadmin','representante') AND ur.periodo_id IS NULL)
             OR (ur.periodo_id=? AND r.codigo IN ('docente','estudiante')))
          ORDER BY FIELD(r.codigo,'superadmin','subadmin','docente','estudiante','representante') LIMIT 1");
    $s->bind_param('ii',$usuarioId,$periodoId);$s->execute();$r=$s->get_result()->fetch_assoc();$s->close();
    return (string)($r['codigo']??'');
}

function tieneRolGlobalUsuario(int $usuarioId): bool {
    global $conexion;
    $s=$conexion->prepare("SELECT 1 FROM usuario_roles ur JOIN roles r ON r.id=ur.rol_id
        WHERE ur.usuario_id=? AND r.codigo IN ('superadmin','subadmin') AND ur.periodo_id IS NULL LIMIT 1");
    $s->bind_param('i',$usuarioId);$s->execute();$ok=(bool)$s->get_result()->fetch_row();$s->close();return $ok;
}

function validarRolCompatibleConAcademico(int $usuarioId,int $periodoId,string $nuevo): void {
    global $conexion;
    if ($nuevo!=='estudiante') {
        $s=$conexion->prepare("SELECT COUNT(*) total FROM matriculas m JOIN aulas_periodo ap ON ap.id=m.aula_periodo_id
             WHERE m.estudiante_id=? AND ap.periodo_id=? AND m.estado='activo'");
        $s->bind_param('ii',$usuarioId,$periodoId);$s->execute();$n=(int)$s->get_result()->fetch_assoc()['total'];$s->close();
        if ($n && $nuevo!=='superadmin' && $nuevo!=='subadmin') throw new RuntimeException('El usuario mantiene una matrícula activa. Retira la matrícula antes de retirar su rol estudiante.');
    }
    if ($nuevo!=='docente') {
        $s=$conexion->prepare("SELECT COUNT(*) total FROM ofertas_academicas o JOIN aulas_periodo ap ON ap.id=o.aula_periodo_id
              WHERE o.docente_id=? AND ap.periodo_id=? AND o.activo=1");
        $s->bind_param('ii',$usuarioId,$periodoId);$s->execute();$n=(int)$s->get_result()->fetch_assoc()['total'];$s->close();
        if ($n && $nuevo!=='superadmin' && $nuevo!=='subadmin') throw new RuntimeException('Tiene asignaturas activas como docente. Reasigna la docencia antes de retirar el rol docente.');
    }
}

/**
 * Asigna un rol principal. Los roles globales de administrador solo pueden gestionarse
 * en el modulo dedicado, nunca desde un archivo CSV. Conserva historiales de otros periodos.
 * NOTA: No inicia ni confirma transaccion; el llamador se encarga de ello.
 */
function establecerRolUsuario(int $usuarioId,string $codigo,int $periodoId,bool $permitirGlobal=false): void {
    global $conexion;
    if (!in_array($codigo,['superadmin','subadmin','docente','estudiante','representante'],true)) throw new RuntimeException('Rol no permitido.');
    if (($codigo==='superadmin'||$codigo==='subadmin') && !$permitirGlobal) throw new RuntimeException('No puedes asignar permisos administrativos desde un CSV.');
    // El representante no es un rol academico por periodo. Se agrega sin borrar
    // asignaciones docentes/estudiantiles; nunca concede permisos administrativos.
    if ($codigo==='representante') {
        if (tieneRolGlobalUsuario($usuarioId) && !$permitirGlobal) throw new RuntimeException('No puedes cambiar una cuenta administrativa desde Usuarios.');
        $s=$conexion->prepare('SELECT id,correo FROM usuarios WHERE id=? AND activo=1 LIMIT 1');
        $s->bind_param('i',$usuarioId);$s->execute();$existe=$s->get_result()->fetch_assoc();$s->close();
        if(!$existe) throw new RuntimeException('Cuenta inexistente o inactiva.');
        if(!filter_var($existe['correo']??'',FILTER_VALIDATE_EMAIL)) throw new RuntimeException('Registra un correo válido para este representante antes de asignar el rol.');
        $s=$conexion->prepare("INSERT INTO usuario_roles (usuario_id,rol_id,periodo_id)
          SELECT ?,r.id,NULL FROM roles r WHERE r.codigo='representante'
          AND NOT EXISTS (SELECT 1 FROM usuario_roles ur WHERE ur.usuario_id=? AND ur.rol_id=r.id AND ur.periodo_id IS NULL)");
        $s->bind_param('ii',$usuarioId,$usuarioId);
        if(!$s->execute()) throw new RuntimeException('No se pudo asignar el rol Representante. Importa el SQL del parche.');
        $filas=$s->affected_rows;$s->close();
        if($filas===0){
            $s=$conexion->prepare("SELECT id FROM roles WHERE codigo='representante' LIMIT 1");
            $s->execute();$rol=$s->get_result()->fetch_assoc();$s->close();
            if(!$rol)throw new RuntimeException('Falta crear el rol Representante con el SQL del parche.');
        }
        return;
    }
    if ($periodoId<=0) throw new RuntimeException('Se necesita un periodo académico seleccionado.');
    $s=$conexion->prepare('SELECT id FROM usuarios WHERE id=? LIMIT 1');$s->bind_param('i',$usuarioId);$s->execute();$existe=$s->get_result()->fetch_assoc();$s->close();
    if (!$existe) throw new RuntimeException('La cuenta seleccionada no existe.');
    if (!$permitirGlobal && tieneRolGlobalUsuario($usuarioId)) throw new RuntimeException('Los roles administrativos no pueden cambiarse mediante CSV.');

    if ($codigo==='docente'||$codigo==='estudiante') {
        validarRolCompatibleConAcademico($usuarioId,$periodoId,$codigo);
        if ($permitirGlobal && tieneRolGlobalUsuario($usuarioId)) {
            $s=$conexion->prepare("SELECT 1 FROM usuario_roles ur JOIN roles r ON r.id=ur.rol_id WHERE ur.usuario_id=? AND r.codigo='superadmin' LIMIT 1");
            $s->bind_param('i',$usuarioId);$s->execute();$eraAdmin=(bool)$s->get_result()->fetch_row();$s->close();
            if ($eraAdmin) {
                $n=(int)$conexion->query("SELECT COUNT(DISTINCT ur.usuario_id) total FROM usuario_roles ur JOIN roles r ON r.id=ur.rol_id WHERE r.codigo='superadmin'")->fetch_assoc()['total'];
                if ($n<=1) throw new RuntimeException('No puedes retirar el rol al último administrador.');
            }
            if ($usuarioId===(int)($_SESSION['usuario_id']??0)) throw new RuntimeException('No puedes retirar tu propio acceso administrativo.');
            $s=$conexion->prepare("DELETE ur FROM usuario_roles ur JOIN roles r ON r.id=ur.rol_id
                  WHERE ur.usuario_id=? AND r.codigo IN ('superadmin','subadmin') AND ur.periodo_id IS NULL");
            $s->bind_param('i',$usuarioId);if (!$s->execute()) throw new RuntimeException('No se pudo cambiar el rol administrativo.');$s->close();
        }
        $s=$conexion->prepare("DELETE ur FROM usuario_roles ur JOIN roles r ON r.id=ur.rol_id
             WHERE ur.usuario_id=? AND ur.periodo_id=? AND r.codigo IN ('docente','estudiante') AND r.codigo<>?");
        $s->bind_param('iis',$usuarioId,$periodoId,$codigo);if (!$s->execute()) throw new RuntimeException('No se pudo actualizar el rol académico.');$s->close();
    } else {
        if (!$permitirGlobal) throw new RuntimeException('Acceso restringido.');
        if ($usuarioId===(int)($_SESSION['usuario_id']??0) && $codigo!=='superadmin') throw new RuntimeException('No puedes degradar tu propio rol de administrador.');
        $s=$conexion->prepare("SELECT 1 FROM usuario_roles ur JOIN roles r ON r.id=ur.rol_id WHERE ur.usuario_id=? AND r.codigo='superadmin' LIMIT 1");
        $s->bind_param('i',$usuarioId);$s->execute();$eraAdmin=(bool)$s->get_result()->fetch_row();$s->close();
        if ($eraAdmin && $codigo!=='superadmin') {
            $n=(int)$conexion->query("SELECT COUNT(DISTINCT ur.usuario_id) total FROM usuario_roles ur JOIN roles r ON r.id=ur.rol_id WHERE r.codigo='superadmin'")->fetch_assoc()['total'];
            if ($n<=1) throw new RuntimeException('No se puede desproteger al último administrador.');
        }
        $s=$conexion->prepare("DELETE ur FROM usuario_roles ur JOIN roles r ON r.id=ur.rol_id
              WHERE ur.usuario_id=? AND r.codigo IN ('superadmin','subadmin') AND ur.periodo_id IS NULL AND r.codigo<>?");
        $s->bind_param('is',$usuarioId,$codigo);if (!$s->execute()) throw new RuntimeException('No se pudo actualizar la administración.');$s->close();
        // Si tiene matriculas u ofertas activas, conserva el rol academico correspondiente.
        // El rol global tiene prioridad en el menu y los permisos.
    }
    $s=$conexion->prepare('SELECT id FROM roles WHERE codigo=? LIMIT 1');$s->bind_param('s',$codigo);$s->execute();$r=$s->get_result()->fetch_assoc();$s->close();
    if (!$r) throw new RuntimeException('Rol no encontrado. Ejecuta primero el SQL de migración.');
    $rolId=(int)$r['id'];
    if ($codigo==='superadmin'||$codigo==='subadmin') {
        $s=$conexion->prepare('SELECT id FROM usuario_roles WHERE usuario_id=? AND rol_id=? AND periodo_id IS NULL LIMIT 1');
        $s->bind_param('ii',$usuarioId,$rolId);$s->execute();$ex=$s->get_result()->fetch_assoc();$s->close();
        if (!$ex) {$s=$conexion->prepare('INSERT INTO usuario_roles (usuario_id,rol_id,periodo_id) VALUES (?,?,NULL)');$s->bind_param('ii',$usuarioId,$rolId);if (!$s->execute()) throw new RuntimeException('Error al asignar rol administrativo.');$s->close();}
    } else {
        $s=$conexion->prepare('SELECT id FROM usuario_roles WHERE usuario_id=? AND rol_id=? AND periodo_id=? LIMIT 1');
        $s->bind_param('iii',$usuarioId,$rolId,$periodoId);$s->execute();$ex=$s->get_result()->fetch_assoc();$s->close();
        if (!$ex) {$s=$conexion->prepare('INSERT INTO usuario_roles (usuario_id,rol_id,periodo_id) VALUES (?,?,?)');$s->bind_param('iii',$usuarioId,$rolId,$periodoId);if (!$s->execute()) throw new RuntimeException('Error al asignar rol académico.');$s->close();}
    }
}



/** Determina si un usuario (no necesariamente el de sesión) tiene rol global. */
function sgaUsuarioTieneRolGlobal(int $usuarioId, string $codigo): bool {
    global $conexion;
    if (!in_array($codigo,['superadmin','subadmin','representante'],true)) return false;
    $s=$conexion->prepare('SELECT 1 FROM usuario_roles ur JOIN roles r ON r.id=ur.rol_id '
        .'WHERE ur.usuario_id=? AND ur.periodo_id IS NULL AND r.codigo=? LIMIT 1');
    $s->bind_param('is',$usuarioId,$codigo);$s->execute();
    $ok=(bool)$s->get_result()->fetch_row();$s->close();return $ok;
}

/** Acceso familiar adicional: nunca modifica Docente, Subadmin ni las jornadas. */
function sgaActualizarRolRepresentante(int $usuarioId, bool $habilitar): void {
    global $conexion;
    if (!esAdminAcademico()) throw new RuntimeException('Solo la administración académica puede gestionar roles adicionales.');
    if (esSubadmin() && tieneRolGlobalUsuario($usuarioId))
        throw new RuntimeException('Una cuenta administradora está protegida frente al Subadministrador.');
    if ($usuarioId<=0) throw new RuntimeException('Selecciona una cuenta válida.');
    $existe=sgaUsuarioTieneRolGlobal($usuarioId,'representante');
    if ($existe===$habilitar) return;
    if ($habilitar) {
        establecerRolUsuario($usuarioId,'representante',0,true);
        return;
    }
    // No romper la comunicación con menores actualmente vinculados.
    $s=$conexion->prepare('SELECT 1 FROM sga_representantes_estudiantes WHERE representante_id=? AND activo=1 LIMIT 1');
    $s->bind_param('i',$usuarioId);$s->execute();$vinculos=(bool)$s->get_result()->fetch_row();$s->close();
    if ($vinculos) throw new RuntimeException('Este representante tiene hijos vinculados. Desvincúlalos antes de retirar el acceso familiar.');
    $s=$conexion->prepare("DELETE ur FROM usuario_roles ur JOIN roles r ON r.id=ur.rol_id
         WHERE ur.usuario_id=? AND ur.periodo_id IS NULL AND r.codigo='representante'");
    $s->bind_param('i',$usuarioId);
    if(!$s->execute())throw new RuntimeException('No se pudo retirar el rol Representante.');
    $s->close();
}

/**
 * Cambia el rol principal conservando los roles académicos y familiares válidos.
 * El rol Representante es SIEMPRE adicional: no revoca Docente/Subadmin.
 */
function sgaCambiarRolPrincipalUsuario(int $usuarioId,string $codigo,int $periodoId,bool $permitirGlobal=false): void {
    if (!in_array($codigo,['superadmin','subadmin','docente','estudiante','representante'],true))
        throw new RuntimeException('Rol no permitido.');
    if ($codigo==='representante') {
        if (!$permitirGlobal && tieneRolGlobalUsuario($usuarioId))
            throw new RuntimeException('La asignación familiar de una cuenta administrativa se realiza desde Roles.');
        establecerRolUsuario($usuarioId,$codigo,$periodoId,$permitirGlobal);
        return;
    }
    establecerRolUsuario($usuarioId,$codigo,$periodoId,$permitirGlobal);
}

/** Importacion de rol Representante: no se abren cuentas academicas de jornadas ajenas. */
function sgaRepImportarPuedeTocarUsuario(int $usuarioId,int $periodoId,string $rol): bool {
    if(puedeGestionarUsuarioJornada($usuarioId,$periodoId))return true;
    if($rol!=='representante')return false;
    global $conexion;
    // Permitir solamente un representante YA existente, sin cambios de sus datos.
    $s=$conexion->prepare("SELECT 1 FROM usuario_roles ur JOIN roles r ON r.id=ur.rol_id WHERE ur.usuario_id=? AND ur.periodo_id IS NULL AND r.codigo='representante' LIMIT 1");
    $s->bind_param('i',$usuarioId);$s->execute();$yaRep=(bool)$s->get_result()->fetch_row();$s->close();
    return $yaRep;
}


/**
 * V1.6.3: guarda un CONJUNTO de roles de una cuenta sin sustituir otros perfiles.
 * Roles globales: superadmin, subadmin y representante.
 * Roles del periodo elegido: docente y estudiante.
 * El llamador inicia/confirmar la transaccion y registra la auditoria.
 */
function sgaValidarListaRoles(array $seleccion): array {
    $validos=['superadmin','subadmin','docente','estudiante','representante'];
    $roles=[];
    foreach ($seleccion as $valor) {
        if (!is_string($valor) || !in_array($valor,$validos,true)) {
            throw new RuntimeException('Se recibió un rol no permitido.');
        }
        $roles[$valor]=true;
    }
    if (!$roles) throw new RuntimeException('Marca por lo menos un rol antes de guardar.');
    if (isset($roles['superadmin'],$roles['subadmin']))
        throw new RuntimeException('Administrador y Subadministrador no pueden asignarse juntos.');
    if (isset($roles['estudiante']) && (isset($roles['docente']) || isset($roles['superadmin']) || isset($roles['subadmin'])))
        throw new RuntimeException('El rol Estudiante no puede combinarse con Docente ni con roles administrativos en el mismo periodo.');
    return array_values(array_keys($roles));
}

/** Las jornadas validadas son exclusivamente las activas. */
function sgaValidarJornadasSeleccionadas(array $solicitadas): array {
    global $conexion;
    $ids=[];
    foreach ($solicitadas as $jornada) {
        if (!is_scalar($jornada) || !ctype_digit((string)$jornada) || (int)$jornada<=0)
            throw new RuntimeException('La selección contiene una jornada no válida.');
        $ids[(int)$jornada]=true;
    }
    if (!$ids) throw new RuntimeException('Marca al menos una jornada para Subadministrador.');
    $permitidos=[];
    $res=$conexion->query('SELECT id FROM jornadas WHERE activo=1');
    if (!$res) throw new RuntimeException('No se pudo verificar las jornadas disponibles.');
    foreach($res->fetch_all(MYSQLI_ASSOC) as $fila)$permitidos[(int)$fila['id']]=true;
    foreach(array_keys($ids) as $id)if(!isset($permitidos[$id]))
        throw new RuntimeException('Una jornada seleccionada está inactiva o no existe.');
    return array_keys($ids);
}

/** Reglas previas a la retirada de roles con historial o vínculos activos. */
function sgaValidarRetiradaRol(int $usuarioId,string $codigo,int $periodoId): void {
    global $conexion;
    if ($codigo==='superadmin') {
        if ($usuarioId===(int)($_SESSION['usuario_id']??0))
            throw new RuntimeException('Por seguridad no puedes retirar tu propio rol Administrador.');
        // Bloquea las asignaciones de administradores mientras se decide la retirada.
        $res=$conexion->query("SELECT ur.id,ur.usuario_id FROM usuario_roles ur JOIN roles r ON r.id=ur.rol_id WHERE r.codigo='superadmin' AND ur.periodo_id IS NULL FOR UPDATE");
        if(!$res)throw new RuntimeException('No se pudo comprobar el número de administradores.');
        $administradores=[];
        foreach($res->fetch_all(MYSQLI_ASSOC) as $fila)$administradores[(int)$fila['usuario_id']]=true;
        if(count($administradores)<=1)throw new RuntimeException('No puedes retirar al último Administrador.');
    } elseif($codigo==='docente' || $codigo==='estudiante') {
        if($codigo==='docente') {
            $sql="SELECT 1 FROM ofertas_academicas o JOIN aulas_periodo ap ON ap.id=o.aula_periodo_id WHERE o.docente_id=? AND ap.periodo_id=? AND o.activo=1 LIMIT 1";
            $texto='El docente mantiene asignaturas activas; primero debes reasignarlas.';
        } else {
            $sql="SELECT 1 FROM matriculas m JOIN aulas_periodo ap ON ap.id=m.aula_periodo_id WHERE m.estudiante_id=? AND ap.periodo_id=? AND m.estado='activo' LIMIT 1";
            $texto='El estudiante tiene una matrícula activa; primero debes retirarla o finalizarla.';
        }
        $s=$conexion->prepare($sql);
        if(!$s)throw new RuntimeException('No se pudieron verificar las asignaciones académicas.');
        $s->bind_param('ii',$usuarioId,$periodoId);
        if(!$s->execute())throw new RuntimeException('No se pudieron verificar las asignaciones académicas.');
        $asignado=(bool)$s->get_result()->fetch_row();$s->close();
        if($asignado)throw new RuntimeException($texto);
    }
}

/**
 * Sincroniza todos los roles del periodo seleccionado y los globales.
 * Las asignaciones académicas de periodos ANTERIORES no se alteran.
 * Se debe invocar dentro de una transaccion SQL ya abierta.
 */
function sgaGuardarRolesMultiples(int $usuarioId,int $periodoId,array $seleccion,array $jornadas=[]): array {
    global $conexion;
    if(!esAdminAcademico()) throw new RuntimeException('Esta acción requiere permisos de administración académica.');
    $nuevos=sgaValidarListaRoles($seleccion);
    if (esSubadmin()) {
        // El Subadministrador gestiona Docente, Estudiante y Representante, pero
        // jamás puede conceder/revocar privilegios administrativos, ni siquiera
        // mediante una petición POST manipulada.
        if (array_intersect($nuevos,['superadmin','subadmin']))
            throw new RuntimeException('Los roles Administrador y Subadministrador solo los asigna el Administrador principal.');
        if ($periodoId<=0 || !puedeGestionarUsuarioJornada($usuarioId,$periodoId))
            throw new RuntimeException('No puedes cambiar roles de cuentas administrativas ni de usuarios inexistentes.');
    }
    if((in_array('docente',$nuevos,true) || in_array('estudiante',$nuevos,true) || in_array('subadmin',$nuevos,true)) && $periodoId<=0)
        throw new RuntimeException('Selecciona un periodo académico antes de asignar roles académicos o jornadas.');
    $jornadasFinales=in_array('subadmin',$nuevos,true)?sgaValidarJornadasSeleccionadas($jornadas):[];

    $s=$conexion->prepare('SELECT id,activo,correo FROM usuarios WHERE id=? LIMIT 1 FOR UPDATE');
    if(!$s)throw new RuntimeException('No se pudo consultar el usuario.');
    $s->bind_param('i',$usuarioId);
    if(!$s->execute())throw new RuntimeException('No se pudo consultar el usuario.');
    $usuario=$s->get_result()->fetch_assoc();$s->close();
    if(!$usuario)throw new RuntimeException('El usuario ya no existe.');

    $codigos=['superadmin','subadmin','docente','estudiante','representante'];
    $rolesId=[];
    $rs=$conexion->query("SELECT id,codigo FROM roles WHERE codigo IN ('superadmin','subadmin','docente','estudiante','representante')");
    if(!$rs)throw new RuntimeException('No se pudo consultar el catálogo de roles.');
    foreach($rs->fetch_all(MYSQLI_ASSOC) as $fila)$rolesId[$fila['codigo']]=(int)$fila['id'];
    foreach($nuevos as $codigo)if(empty($rolesId[$codigo]))
        throw new RuntimeException('Falta configurar el rol '.ucfirst($codigo).' en la base de datos.');

    $s=$conexion->prepare("SELECT r.codigo FROM usuario_roles ur JOIN roles r ON r.id=ur.rol_id
       WHERE ur.usuario_id=? AND ((ur.periodo_id IS NULL AND r.codigo IN ('superadmin','subadmin','representante'))
       OR (ur.periodo_id=? AND r.codigo IN ('docente','estudiante'))) FOR UPDATE");
    if(!$s)throw new RuntimeException('No se pudo consultar los roles actuales.');
    $s->bind_param('ii',$usuarioId,$periodoId);
    if(!$s->execute())throw new RuntimeException('No se pudo consultar los roles actuales.');
    $anteriores=[];
    foreach($s->get_result()->fetch_all(MYSQLI_ASSOC) as $fila)$anteriores[$fila['codigo']]=true;
    $s->close();

    foreach($codigos as $codigo) {
        $estaba=isset($anteriores[$codigo]);
        $quiere=in_array($codigo,$nuevos,true);
        if($estaba===$quiere)continue;
        if(!$quiere){
            sgaValidarRetiradaRol($usuarioId,$codigo,$periodoId);
            if($codigo==='representante'){
                sgaActualizarRolRepresentante($usuarioId,false); // protege hijos vinculados
                continue;
            }
            if(in_array($codigo,['superadmin','subadmin'],true)){
                $s=$conexion->prepare('DELETE FROM usuario_roles WHERE usuario_id=? AND rol_id=? AND periodo_id IS NULL');
                $idRol=$rolesId[$codigo];$s->bind_param('ii',$usuarioId,$idRol);
            } else {
                $s=$conexion->prepare('DELETE FROM usuario_roles WHERE usuario_id=? AND rol_id=? AND periodo_id=?');
                $idRol=$rolesId[$codigo];$s->bind_param('iii',$usuarioId,$idRol,$periodoId);
            }
            if(!$s || !$s->execute())throw new RuntimeException('No se pudo retirar el rol '.$codigo.'.');
            $s->close();
            if($codigo==='subadmin'){
                $s=$conexion->prepare('DELETE FROM subadministrador_jornadas WHERE usuario_id=?');
                $s->bind_param('i',$usuarioId);
                if(!$s->execute())throw new RuntimeException('No se pudieron revocar jornadas anteriores.');
                $s->close();
            }
        } else {
            if($codigo==='representante'){
                sgaActualizarRolRepresentante($usuarioId,true); // valida correo y cuenta
                continue;
            }
            $idRol=$rolesId[$codigo];
            if(in_array($codigo,['superadmin','subadmin'],true)){
                $s=$conexion->prepare('INSERT INTO usuario_roles (usuario_id,rol_id,periodo_id) VALUES (?,?,NULL)');
                $s->bind_param('ii',$usuarioId,$idRol);
            } else {
                $s=$conexion->prepare('INSERT INTO usuario_roles (usuario_id,rol_id,periodo_id) VALUES (?,?,?)');
                $s->bind_param('iii',$usuarioId,$idRol,$periodoId);
            }
            if(!$s || !$s->execute())throw new RuntimeException('No se pudo añadir el rol '.$codigo.'.');
            $s->close();
        }
    }

    if(in_array('subadmin',$nuevos,true)){
        $s=$conexion->prepare('DELETE FROM subadministrador_jornadas WHERE usuario_id=? AND periodo_id=?');
        $s->bind_param('ii',$usuarioId,$periodoId);
        if(!$s->execute())throw new RuntimeException('No se pudieron actualizar jornadas.');
        $s->close();
        $s=$conexion->prepare('INSERT INTO subadministrador_jornadas (usuario_id,periodo_id,jornada_id) VALUES (?,?,?)');
        foreach($jornadasFinales as $jornadaId){
            $s->bind_param('iii',$usuarioId,$periodoId,$jornadaId);
            if(!$s->execute())throw new RuntimeException('No se pudo guardar la jornada seleccionada.');
        }
        $s->close();
    }
    return ['roles'=>$nuevos,'jornadas'=>$jornadasFinales];
}
