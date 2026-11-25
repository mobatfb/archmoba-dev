<?php
require_once __DIR__.'/../../lib/funciones.php';
require_once __DIR__.'/../../lib/roles_usuarios.php';
require_once __DIR__.'/../../lib/usuarios_unicode.php';
require_once __DIR__.'/../../lib/usuarios_jornadas.php';
exigirAdminAcademico();
if (empty($_SESSION['csrf_usuarios'])) $_SESSION['csrf_usuarios']=bin2hex(random_bytes(24));
$csrf=$_SESSION['csrf_usuarios'];
$pid=(int)(periodoActivo()['id']??0);
if(esSubadmin()) exigirAccesoPeriodo($pid);
// Mismas jornadas activas del periodo, filtradas por permiso para el Subadministrador.
$jornadasGestion=sgaUJCatalogo($pid);
$editarId=(int)($_GET['editar']??0);$editar=null;
if ($editarId && esSubadmin() && !puedeGestionarUsuarioJornada($editarId,$pid)) {
    http_response_code(403);die('No puedes modificar cuentas administrativas ni cuentas de otra jornada.');
}
if ($editarId) {$s=$conexion->prepare('SELECT id,cedula,apellidos,nombres,correo,activo FROM usuarios WHERE id=?');$s->bind_param('i',$editarId);$s->execute();$editar=$s->get_result()->fetch_assoc()?:null;$s->close();}
$editarRolesMarcados=[];
$editarJornadasMarcadas=$editar?array_fill_keys(sgaUJAsignadas((int)$editar['id'],$pid),true):[];
if($editar){
    $s=$conexion->prepare("SELECT r.codigo FROM usuario_roles ur JOIN roles r ON r.id=ur.rol_id
        WHERE ur.usuario_id=? AND ((ur.periodo_id=? AND r.codigo IN ('docente','estudiante'))
        OR (ur.periodo_id IS NULL AND r.codigo='representante'))");
    $s->bind_param('ii',$editarId,$pid);$s->execute();
    foreach($s->get_result()->fetch_all(MYSQLI_ASSOC) as $fila)$editarRolesMarcados[$fila['codigo']]=true;
    $s->close();
}
if ($_SERVER['REQUEST_METHOD']==='POST') {
    try {
        if (!hash_equals($csrf,(string)($_POST['csrf']??''))) throw new RuntimeException('Sesión de formulario caducada.');
        $accion=(string)($_POST['accion']??'');
        if ($accion==='crear') {
            $ced=trim((string)($_POST['cedula']??''));$ape=trim((string)($_POST['apellidos']??''));$nom=trim((string)($_POST['nombres']??''));$correo=trim((string)($_POST['correo']??''));
            $clave=(string)($_POST['clave']??'');$rol=normalizarRolUsuario((string)($_POST['rol']??''));
            if ($ced===''||$ape===''||$nom==='') throw new RuntimeException('Cédula, apellidos y nombres son obligatorios.');
            sgaValidarNombreUtf8($ape,'Apellidos');
            sgaValidarNombreUtf8($nom,'Nombres');
            if (!in_array($rol,['estudiante','docente','representante'],true)) throw new RuntimeException('Selecciona Estudiante, Docente o Representante.');
            if (!$pid && $rol!=='representante') throw new RuntimeException('Activa un período académico antes de registrar usuarios con rol académico.');
            $jornadasNuevo=sgaUJValidarIds((array)($_POST['jornadas']??[]),$jornadasGestion,
                esSubadmin() || $rol!=='representante');
            if ($correo!==''&&!filter_var($correo,FILTER_VALIDATE_EMAIL)) throw new RuntimeException('Correo electrónico inválido.');
            if ($rol==='representante' && $correo==='') throw new RuntimeException('El representante necesita un correo registrado para recibir avisos.');
            if ($clave==='') $clave=$rol==='representante'?bin2hex(random_bytes(16)):$ced;
            if($rol==='representante' && strlen($clave)<8) throw new RuntimeException('La contraseña inicial del representante debe tener al menos 8 caracteres.');
            $hash=password_hash($clave,PASSWORD_DEFAULT);$correoDb=$correo!==''?$correo:null;
            $conexion->begin_transaction();
            $s=$conexion->prepare('INSERT INTO usuarios (cedula,apellidos,nombres,correo,clave,debe_cambiar_clave) VALUES (?,?,?,?,?,1)');$s->bind_param('sssss',$ced,$ape,$nom,$correoDb,$hash);
            if (!$s->execute()) throw new RuntimeException($s->errno===1062?'La cédula o correo ya existe.':'No se pudo crear el usuario.');
            $nuevoId=(int)$conexion->insert_id;$s->close();
            establecerRolUsuario($nuevoId,$rol,$pid,false);
            sgaUJGuardar($nuevoId,$pid,$jornadasNuevo);
            $conexion->commit();
            registrarAuditoria('CREATE','Usuarios','usuario',$nuevoId,'Usuario creado con rol '.$rol.'.',$nuevoId,null,
                ['cedula'=>$ced,'rol'=>$rol,'periodo_id'=>$pid,'jornadas'=>$jornadasNuevo]);
            flash('success','Usuario creado con el rol '.ucfirst($rol).' y sus jornadas.');
        } elseif ($accion==='editar'||$accion==='toggle'||$accion==='eliminar') {
            if(!esAdminAcademico()) throw new RuntimeException('Solo la administración académica puede gestionar usuarios.');
            $id=(int)($_POST['id']??0);if (!$id) throw new RuntimeException('Usuario inválido.');
            if (tieneRolGlobalUsuario($id)) throw new RuntimeException('Las cuentas administrativas están protegidas.');
            if (esSubadmin() && !puedeGestionarUsuarioJornada($id,$pid))
                throw new RuntimeException('No tienes autorización para gestionar esta cuenta.');
            $s=$conexion->prepare('SELECT id,cedula,apellidos,nombres,correo,activo FROM usuarios WHERE id=?');$s->bind_param('i',$id);$s->execute();$antes=$s->get_result()->fetch_assoc();$s->close();
            if (!$antes) throw new RuntimeException('Usuario no encontrado.');
            if ($accion==='editar') {
                $ced=trim((string)($_POST['cedula']??''));$ape=trim((string)($_POST['apellidos']??''));$nom=trim((string)($_POST['nombres']??''));$correo=trim((string)($_POST['correo']??''));
                if ($ced===''||$ape===''||$nom==='') throw new RuntimeException('Datos incompletos.');
                sgaValidarNombreUtf8($ape,'Apellidos');
                sgaValidarNombreUtf8($nom,'Nombres');
                if ($correo!==''&&!filter_var($correo,FILTER_VALIDATE_EMAIL)) throw new RuntimeException('Correo inválido.');
                $correoDb=$correo!==''?$correo:null;
                // Roles en casillas, sin tocar permisos administrativos o historiales de otros periodos.
                $rolesFormulario=sgaValidarListaRoles((array)($_POST['roles_usuario']??[]));
                if(array_intersect($rolesFormulario,['superadmin','subadmin']))
                    throw new RuntimeException('Los roles administrativos se gestionan desde Roles de usuarios.');
                if(in_array('representante',$rolesFormulario,true) && !filter_var($correoDb,FILTER_VALIDATE_EMAIL))
                    throw new RuntimeException('Para ser Representante debes registrar un correo válido.');
                $rolesAnteriores=rolesVisiblesUsuario($id);
                $jornadasAnteriores=sgaUJAsignadas($id,$pid);
                $jornadasNuevo=sgaUJValidarIds((array)($_POST['jornadas']??[]),$jornadasGestion,esSubadmin());
                // La nueva clave es opcional. Nunca guardar ni auditar la clave en texto plano.
                $nuevaClave=(string)($_POST['nueva_clave']??'');
                $confirmarClave=(string)($_POST['confirmar_clave']??'');
                $cambiaClave=($nuevaClave!=='');
                if ($cambiaClave) {
                    if (trim($nuevaClave)==='') throw new RuntimeException('La nueva contraseña no puede estar compuesta solo por espacios.');
                    if (preg_match_all('/./us', $nuevaClave) < 8) throw new RuntimeException('La nueva contraseña debe tener al menos 8 caracteres.');
                    if (strlen($nuevaClave)>72) throw new RuntimeException('La contraseña es demasiado larga. Prueba una más corta.');
                    if (!hash_equals($nuevaClave,$confirmarClave)) throw new RuntimeException('La confirmación de la contraseña no coincide.');
                    $hash=password_hash($nuevaClave,PASSWORD_DEFAULT);
                    // Una sola sentencia mantiene los datos y la nueva contraseña consistentes.
                    $s=$conexion->prepare('UPDATE usuarios SET cedula=?,apellidos=?,nombres=?,correo=?,clave=?,debe_cambiar_clave=1 WHERE id=?');
                    $s->bind_param('sssssi',$ced,$ape,$nom,$correoDb,$hash,$id);
                } else {
                    if ($confirmarClave!=='') throw new RuntimeException('Escribe también la nueva contraseña o deja ambos campos vacíos.');
                    $s=$conexion->prepare('UPDATE usuarios SET cedula=?,apellidos=?,nombres=?,correo=? WHERE id=?');
                    $s->bind_param('ssssi',$ced,$ape,$nom,$correoDb,$id);
                }
                $conexion->begin_transaction();
                if (!$s->execute()) throw new RuntimeException($s->errno===1062?'La cédula o correo ya está registrado.':'No se pudo actualizar el usuario.');$s->close();
                $rolesResultado=esSuperadmin()
                    ? sgaGuardarRolesMultiples($id,$pid,$rolesFormulario,[])
                    : ['roles'=>sgaUJGuardarRolesSubadmin($id,$pid,$rolesFormulario)];
                $cambioJornadas=sgaUJGuardar($id,$pid,$jornadasNuevo);
                // Si el administrador cambia una contraseña, caducan enlaces de recuperación previos.
                if ($cambiaClave) {
                    $anular = $conexion->prepare('UPDATE sga_recuperacion_claves SET usado_en=NOW() WHERE usuario_id=? AND usado_en IS NULL');
                    if ($anular) { $anular->bind_param('i', $id); $anular->execute(); $anular->close(); }
                }
                $conexion->commit();
                registrarAuditoria('UPDATE','Usuarios','usuario',$id,
                    'Datos de usuario y roles actualizados con casillas.', $id,
                    ['usuario'=>$antes,'roles'=>$rolesAnteriores,'jornadas'=>$jornadasAnteriores],
                    ['cedula'=>$ced,'apellidos'=>$ape,'nombres'=>$nom,'correo'=>$correoDb,
                     'clave_actualizada'=>$cambiaClave,'roles'=>$rolesResultado['roles'],
                     'jornadas'=>$jornadasNuevo,'jornadas_modificadas'=>$cambioJornadas,'periodo_id'=>$pid]);
                flash('success',$cambiaClave?'Usuario, jornadas y contraseña actualizados.':'Usuario, roles y jornadas actualizados correctamente.');
            } elseif ($accion==='toggle') {
                if ($id===(int)$_SESSION['usuario_id']) throw new RuntimeException('No puedes desactivar tu propia cuenta.');
                $nuevo=(int)$antes['activo']?0:1;
                $s=$conexion->prepare('UPDATE usuarios SET activo=? WHERE id=?');$s->bind_param('ii',$nuevo,$id);$s->execute();$s->close();
                registrarAuditoria('UPDATE','Usuarios','usuario',$id,$nuevo?'Usuario activado.':'Usuario desactivado.',$id,$antes,['activo'=>$nuevo]);
                flash('success',$nuevo?'Usuario activado.':'Usuario desactivado.');
            } else {
                if ($id===(int)$_SESSION['usuario_id']) throw new RuntimeException('No puedes eliminar tu propia cuenta.');
                $s=$conexion->prepare("SELECT (SELECT COUNT(*) FROM usuario_roles WHERE usuario_id=?)+
                  (SELECT COUNT(*) FROM matriculas WHERE estudiante_id=?)+
                  (SELECT COUNT(*) FROM ofertas_academicas WHERE docente_id=?)+
                  (SELECT COUNT(*) FROM elecciones WHERE creada_por=?)+
                  (SELECT COUNT(*) FROM eleccion_votos WHERE estudiante_id=?)+
                  (SELECT COUNT(*) FROM asistencia_sesiones WHERE registrado_por=?) AS dependencias");
                $s->bind_param('iiiiii',$id,$id,$id,$id,$id,$id);$s->execute();$dep=(int)$s->get_result()->fetch_assoc()['dependencias'];$s->close();
                if ($dep) throw new RuntimeException('El usuario tiene roles o historial. Desactívalo en lugar de eliminarlo.');
                $s=$conexion->prepare('DELETE FROM usuarios WHERE id=?');$s->bind_param('i',$id);$s->execute();$s->close();
                registrarAuditoria('DELETE','Usuarios','usuario',$id,'Usuario sin historial eliminado.',null,$antes,null,'exito',null,null,'critica');flash('success','Usuario eliminado.');
            }
        } else throw new RuntimeException('Acción no reconocida.');
    } catch (Throwable $e) { $conexion->rollback(); flash('error','No se pudo completar la acción: '.$e->getMessage()); }
    $rolVolver=(string)($_POST['retorno_rol']??'estudiante');
    if(!in_array($rolVolver,['estudiante','docente','representante','subadmin','superadmin','sin_rol','todos'],true))$rolVolver='estudiante';
    $qVolver=trim((string)($_POST['retorno_q']??''));
    if(strlen($qVolver)>200)$qVolver=substr($qVolver,0,200);
    // Conserva el filtro de jornada tras crear, editar, activar o eliminar.
    $jornadaRetornoEntrada=$_POST['retorno_jornada']??'todas';
    $jornadaVolver=is_scalar($jornadaRetornoEntrada)?trim((string)$jornadaRetornoEntrada):'todas';
    if ($jornadaVolver!=='todas' && $jornadaVolver!=='sin_asignar' &&
        (!ctype_digit($jornadaVolver) || (int)$jornadaVolver<=0)) $jornadaVolver='todas';
    $pagVolver=max(1,(int)($_POST['retorno_pag']??1));
    redir('modulos/usuarios/index.php?'.http_build_query(['rol'=>$rolVolver,'jornada'=>$jornadaVolver,'q'=>$qVolver,'pag'=>$pagVolver]));
}
// Búsqueda completa en BD solo al enviar el formulario; paginación sin límite fijo.
$q=trim((string)($_GET['q']??''));
$opcionesRolUsuarios=[
    'estudiante'=>'Estudiantes',
    'docente'=>'Docentes',
    'representante'=>'Representantes',
    // El Subadministrador puede BUSCAR estos perfiles; no puede modificarlos.
    'subadmin'=>'Subadministradores (solo consulta)',
    'superadmin'=>'Superadministradores (solo consulta)',
    'sin_rol'=>'Sin rol',
    'todos'=>'Todos los roles',
];
$rolFiltro=trim((string)($_GET['rol']??'estudiante'));
if(!isset($opcionesRolUsuarios[$rolFiltro]))$rolFiltro='estudiante';
// El filtro de jornada es independiente del rol. Solo se muestran las jornadas
// autorizadas y, en Subadministrador, las del contexto de visualización actual.
$jornadasFiltroDisponibles=$jornadasGestion;
if (esSubadmin()) {
    $jornadasVista=jornadasEnVista($pid);
    $jornadasFiltroDisponibles=array_values(array_filter($jornadasGestion,
        static fn(array $j):bool=>in_array((int)$j['id'],$jornadasVista,true)));
}
$jornadasFiltroIds=[];
foreach($jornadasFiltroDisponibles as $j)$jornadasFiltroIds[(int)$j['id']]=true;
$jornadaEntrada=$_GET['jornada']??'todas';
$jornadaSolicitada=is_scalar($jornadaEntrada)?trim((string)$jornadaEntrada):'todas';
$jornadaFiltro='todas';
if ($jornadaSolicitada==='sin_asignar' && !esSubadmin()) {
    $jornadaFiltro='sin_asignar';
} elseif (ctype_digit($jornadaSolicitada) && (int)$jornadaSolicitada>0 &&
          isset($jornadasFiltroIds[(int)$jornadaSolicitada])) {
    $jornadaFiltro=(string)(int)$jornadaSolicitada;
}
$pagina=max(1,(int)($_GET['pag']??1));
$porPagina=300;
$base=' FROM usuarios u WHERE 1=1';
$parametrosBusqueda=[];
$tiposBusqueda='';
if ($q!=='') {
    $terminosBusqueda=array_slice(preg_split('/\s+/', $q, -1, PREG_SPLIT_NO_EMPTY), 0, 12);
    foreach ($terminosBusqueda as $termino) {
        $base.=' AND (u.cedula LIKE ? OR u.apellidos LIKE ? OR u.nombres LIKE ? OR u.correo LIKE ?)';
        $like='%'.$termino.'%';
        array_push($parametrosBusqueda, $like, $like, $like, $like);
        $tiposBusqueda.='ssss';
    }
}
// Filtrar en el servidor por rol: respeta los roles academicos del periodo activo.
// Los roles globales no dependen de un periodo academico.
if($rolFiltro==='sin_rol'){
    $base.=' AND NOT EXISTS (SELECT 1 FROM usuario_roles ur0 WHERE ur0.usuario_id=u.id)';
}elseif($rolFiltro!=='todos'){
    $base.=' AND EXISTS (SELECT 1 FROM usuario_roles urf JOIN roles rf ON rf.id=urf.rol_id'
        .' WHERE urf.usuario_id=u.id AND rf.codigo=?';
    $parametrosBusqueda[]=$rolFiltro;
    $tiposBusqueda.='s';
    if($rolFiltro==='estudiante'||$rolFiltro==='docente'){
        $base.=' AND urf.periodo_id=?';
        $parametrosBusqueda[]=$pid;
        $tiposBusqueda.='i';
    }else{
        $base.=' AND urf.periodo_id IS NULL';
    }
    $base.=')';
}
// Filtrado en base de datos, antes del COUNT y de la paginación. Un usuario
// con varias jornadas puede aparecer en cualquiera de ellas, sin duplicarse.
if ($jornadaFiltro==='sin_asignar') {
    $base.=' AND NOT EXISTS (SELECT 1 FROM usuarios_jornadas_gestion ujf WHERE ujf.usuario_id=u.id AND ujf.periodo_id=?)';
    $parametrosBusqueda[]=$pid;
    $tiposBusqueda.='i';
} elseif ($jornadaFiltro!=='todas') {
    // La jornada puede provenir de docencia, matricula, vinculo familiar o
    // subadministracion, no exclusivamente de usuarios_jornadas_gestion.
    $base.=' AND '.sgaUsuarioVisibleEnJornadasSQL($pid,[(int)$jornadaFiltro],'u');
}
$base.=filtroUsuariosJornadasSQL($pid,'u');
$bindBusqueda=static function(mysqli_stmt $stmt)use($parametrosBusqueda,$tiposBusqueda):void {
    if($parametrosBusqueda)$stmt->bind_param($tiposBusqueda,...$parametrosBusqueda);
};
$s=$conexion->prepare('SELECT COUNT(*) total'.$base);
if(!$s)throw new RuntimeException('No se pudo preparar la consulta de usuarios.');
$bindBusqueda($s);sgaEjecutar($s,'contar usuarios');
$totalUsuarios=(int)($s->get_result()->fetch_assoc()['total']??0);$s->close();
$totalPaginas=max(1,(int)ceil($totalUsuarios/$porPagina));
$pagina=min($pagina,$totalPaginas);
$offset=($pagina-1)*$porPagina;
$sql='SELECT u.id,u.cedula,u.apellidos,u.nombres,u.correo,u.activo'.$base
    .' ORDER BY u.apellidos,u.nombres,u.id LIMIT '.$porPagina.' OFFSET '.$offset;
$s=$conexion->prepare($sql);
if(!$s)throw new RuntimeException('No se pudo preparar la lista de usuarios.');
$bindBusqueda($s);sgaEjecutar($s,'listar usuarios');
$usuarios=$s->get_result()->fetch_all(MYSQLI_ASSOC);$s->close();
// Roles y jornadas se obtienen por lote, no una consulta por cada usuario.
$rolesPorUsuario=[];$rolesGlobales=[];$rolesPrincipales=[];$jornadasPorUsuario=[];
if($usuarios){
    $ids=implode(',',array_map('intval',array_column($usuarios,'id')));
    $rolesSql='SELECT ur.usuario_id,r.codigo,r.nombre,p.nombre periodo,ur.periodo_id
      FROM usuario_roles ur JOIN roles r ON r.id=ur.rol_id
      LEFT JOIN periodos_academicos p ON p.id=ur.periodo_id
      WHERE ur.usuario_id IN ('.$ids.') ORDER BY r.nombre,p.nombre';
    $result=$conexion->query($rolesSql);
    if(!$result)throw new RuntimeException('No se pudieron recuperar los roles de los usuarios.');
    while($dato=$result->fetch_assoc()){
        $uid=(int)$dato['usuario_id'];
        $rolesPorUsuario[$uid][]=['codigo'=>$dato['codigo'],'nombre'=>$dato['nombre'],'periodo'=>$dato['periodo']];
        if($dato['periodo_id']===null && in_array($dato['codigo'],['superadmin','subadmin'],true))$rolesGlobales[$uid]=true;
        if((int)$dato['periodo_id']===$pid && in_array($dato['codigo'],['docente','estudiante'],true)){
            if(!isset($rolesPrincipales[$uid])||$dato['codigo']==='docente')$rolesPrincipales[$uid]=$dato['codigo'];
        }
    }
    $result->free();
    if($pid>0){
        // Jornadas efectivas por persona: docentes, alumnos, representantes y
        // subadministradores pueden estar vinculados sin fila en la tabla UJ.
        // Los IDs del IN proceden exclusivamente del SELECT de esta pagina.
        $p=(int)$pid;
        $sqlJornadas="SELECT DISTINCT rel.usuario_id,j.nombre FROM (".
            "SELECT uj.usuario_id,uj.jornada_id FROM usuarios_jornadas_gestion uj WHERE uj.periodo_id=$p AND uj.usuario_id IN ($ids)".
            " UNION SELECT m.estudiante_id usuario_id,a.jornada_id FROM matriculas m JOIN aulas_periodo ap ON ap.id=m.aula_periodo_id AND ap.activo=1 JOIN aulas a ON a.id=ap.aula_id WHERE m.estado='activo' AND ap.periodo_id=$p AND m.estudiante_id IN ($ids)".
            " UNION SELECT o.docente_id usuario_id,a.jornada_id FROM ofertas_academicas o JOIN aulas_periodo ap ON ap.id=o.aula_periodo_id AND ap.activo=1 JOIN aulas a ON a.id=ap.aula_id WHERE o.activo=1 AND ap.periodo_id=$p AND o.docente_id IN ($ids)".
            " UNION SELECT re.representante_id usuario_id,a.jornada_id FROM sga_representantes_estudiantes re JOIN matriculas m ON m.estudiante_id=re.estudiante_id AND m.estado='activo' JOIN aulas_periodo ap ON ap.id=m.aula_periodo_id AND ap.activo=1 JOIN aulas a ON a.id=ap.aula_id WHERE re.activo=1 AND ap.periodo_id=$p AND re.representante_id IN ($ids)".
            " UNION SELECT sj.usuario_id,sj.jornada_id FROM subadministrador_jornadas sj JOIN usuario_roles ur ON ur.usuario_id=sj.usuario_id AND ur.periodo_id IS NULL JOIN roles r ON r.id=ur.rol_id AND r.codigo='subadmin' WHERE sj.periodo_id=$p AND sj.usuario_id IN ($ids)".
            ") rel JOIN jornadas j ON j.id=rel.jornada_id ORDER BY rel.usuario_id,j.orden,j.nombre";
        $consultaJornadas=$conexion->query($sqlJornadas);
        if(!$consultaJornadas)throw new RuntimeException('No se pudieron consultar las jornadas vinculadas.');
        foreach($consultaJornadas->fetch_all(MYSQLI_ASSOC) as $fila)$jornadasPorUsuario[(int)$fila['usuario_id']][]=$fila['nombre'];
        $consultaJornadas->free();
    }
}
$urlPaginaUsuarios=static fn(int $n)=>url('modulos/usuarios/index.php?'.http_build_query(['q'=>$q,'rol'=>$rolFiltro,'jornada'=>$jornadaFiltro,'pag'=>$n]));
$urlBaseUsuarios=static fn(array $campos=[])=>url('modulos/usuarios/index.php?'.http_build_query(array_merge(['q'=>$q,'rol'=>$rolFiltro,'jornada'=>$jornadaFiltro,'pag'=>$pagina],$campos)));
$tituloPagina='Usuarios';$subtituloPagina='Filtra por rol, administra cuentas y abre formularios sin ocupar espacio en la pagina.';require __DIR__.'/../../partials/header.php';
?>
<style>
/* V1.6.23: modales uniformes con Representantes, filtro por rol, lista compacta. */
.sga-users-heading{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;margin:2px 0 14px}
.sga-users-heading .section-title{margin:0}
.sga-users-heading-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.sga-users-dialog{position:fixed;inset:0;margin:auto;width:min(840px,calc(100vw - 24px));max-width:100%;max-height:min(91dvh,840px);padding:0;overflow-y:auto;overscroll-behavior:contain;border:1px solid #cbd8e8;border-radius:15px;background:#fff;color:#203650;box-shadow:0 28px 70px rgba(4,22,49,.35)}
.sga-users-dialog:not([open]){display:none}
.sga-users-dialog::backdrop{background:rgba(5,20,41,.60);backdrop-filter:blur(2px)}
.sga-users-dialog-head{display:flex;align-items:start;justify-content:space-between;gap:12px;padding:17px 19px 12px;border-bottom:1px solid #dfe8f4}
.sga-users-dialog-head h2{font-size:20px;margin:0 0 5px;color:#14345b}
.sga-users-dialog-head p{font-size:12px;line-height:1.45;color:#61738d;margin:0}
.sga-users-dialog-close{flex:0 0 34px;width:34px;height:34px;border:0;border-radius:8px;background:#edf2f9;color:#315070;font:700 23px/1 Arial,sans-serif;cursor:pointer}
.sga-users-tabs{display:flex;gap:8px;padding:12px 19px 0;border-bottom:1px solid #e4eaf2}
.sga-users-tab{padding:10px 13px;border:1px solid #d3dfef;border-bottom:0;background:#f5f8fc;color:#284967;border-radius:9px 9px 0 0;font-weight:700;font-size:13px;cursor:pointer}
.sga-users-tab[aria-selected="true"]{background:#fff;color:#12539e;border-color:#89acd7;box-shadow:inset 0 3px 0 #12539e}
.sga-users-dialog-content{padding:18px 19px 20px}
.sga-users-pane[hidden]{display:none!important}
.sga-users-pane .form-grid{gap:12px}
.sga-users-pane .form-grid>p{margin:2px 0 4px}
.sga-users-dialog .form-actions{grid-column:1/-1;justify-content:flex-end;align-items:center;flex-wrap:wrap}
.sga-users-import-hint{margin:0 0 16px;color:#5a6f8b;font-size:13px;line-height:1.5}
.sga-users-import-actions{display:flex;justify-content:flex-end;gap:9px;flex-wrap:wrap;margin-top:16px}
.sga-users-inline-check{display:flex;flex-direction:row;align-items:flex-start;gap:9px;margin-top:14px;font-weight:500;line-height:1.45}
.sga-users-inline-check input{width:18px;min-width:18px;height:18px;margin:1px 0 0}
.sga-users-dialog input,.sga-users-dialog select,.sga-users-dialog textarea{min-width:0}
.sga-users-dialog button:focus-visible,.sga-users-dialog a:focus-visible{outline:3px solid #4a93d6;outline-offset:2px}
.sga-users-role-filter,.sga-users-jornada-filter{display:flex;flex-direction:column;gap:4px;min-width:155px;max-width:220px}
.sga-users-role-filter span,.sga-users-jornada-filter span{font-size:11px;color:#556c87;font-weight:750}
.sga-users-role-filter select,.sga-users-jornada-filter select{height:37px;font-size:13px}
/* La barra necesita todo el ancho: el aviso informativo va en su propia fila. */
.toolbar.sga-users-filter-toolbar{display:flex;flex-direction:column;align-items:stretch;gap:7px}
.sga-users-filter-toolbar>.mini-note{align-self:flex-end;text-align:right}
/* Escritorio: ambos filtros, busqueda y boton en una unica fila. */
.sga-users-filter-form{display:grid;grid-template-columns:minmax(135px,175px) minmax(135px,175px) minmax(170px,1fr) max-content max-content;gap:9px;align-items:end;width:100%;min-width:0}
.sga-users-filter-form>.sga-users-role-filter,.sga-users-filter-form>.sga-users-jornada-filter{min-width:0;max-width:none;width:100%}
.sga-users-filter-form>input{min-width:0;max-width:none;width:100%;height:37px}
.sga-users-filter-form>.btn{white-space:nowrap;min-height:37px}
@media(max-width:900px){
 .sga-users-filter-form{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}
 .sga-users-filter-form>input{grid-column:1}
 .sga-users-filter-form>button[type="submit"]{grid-column:2;justify-self:start}
}
@media(max-width:480px){
 .sga-users-filter-form{grid-template-columns:1fr}
 .sga-users-filter-form>input,.sga-users-filter-form>button[type="submit"]{grid-column:1}
 .sga-users-filter-form>button[type="submit"]{justify-self:stretch}
 .sga-users-filter-toolbar>.mini-note{align-self:stretch;text-align:left}
}
.sga-users-edit-dialog{width:min(800px,calc(100vw - 24px))}
.sga-users-edit-roles{grid-column:1/-1;border:1px solid #d4dfeb;border-radius:10px;padding:12px;margin:0}
.sga-users-edit-roles legend{font-weight:750;font-size:13px;padding:0 5px}
.sga-users-edit-role-items{display:flex;flex-wrap:wrap;gap:9px}
.sga-users-edit-role-items label{display:flex;flex-direction:row;align-items:center;gap:8px;padding:8px 11px;border:1px solid #dae3ed;border-radius:8px;background:#fbfcff}
.sga-users-edit-role-items input{width:17px;height:17px}
.sga-users-jornadas{grid-column:1/-1;border:1px solid #d4dfeb;border-radius:10px;padding:12px;margin:0}
.sga-users-jornadas legend{font-weight:750;font-size:13px;padding:0 5px}
.sga-users-jornada-items{display:flex;flex-wrap:wrap;gap:9px}
.sga-users-jornada-items label{display:flex;align-items:center;gap:8px;padding:8px 12px;border:1px solid #dae3ed;border-radius:8px;background:#fbfcff;font-size:13px;cursor:pointer}
.sga-users-jornada-items input{width:17px;height:17px;margin:0;flex-shrink:0}
.sga-users-jornadas p{margin:9px 0 0}
@media(max-width:640px){
 .sga-users-dialog{width:calc(100vw - 16px);max-height:calc(100dvh - 16px);border-radius:12px}
 .sga-users-dialog-head,.sga-users-dialog-content{padding-left:13px;padding-right:13px}
 .sga-users-tabs{padding-left:13px;padding-right:13px}
 .sga-users-tab{flex:1;padding:9px 7px;font-size:12px}
 .sga-users-dialog .form-grid.cols-2{grid-template-columns:minmax(0,1fr)}
 .sga-users-import-actions .btn{flex:1 1 auto}
 .sga-users-heading-actions .btn{font-size:12px}
 .sga-users-role-filter,.sga-users-jornada-filter{flex:1 1 140px;max-width:none}
 .sga-users-filter-form>input{max-width:none}
}
</style>
<div class="sga-users-heading">
  <h2 class="section-title">Listado de usuarios</h2>
  <div class="sga-users-heading-actions">
    <a class="btn btn-sm btn-secondary" href="<?=e(url('modulos/roles/index.php'))?>">Administrar roles</a>
    <button type="button" class="btn btn-primary" id="sga-users-open" data-sga-users-open="crear" aria-haspopup="dialog" aria-controls="sga-users-overlay">+ Crear / importar usuarios</button>
  </div>
</div>
<?php if($editar && esAdminAcademico()):?>
<dialog class="sga-users-dialog sga-users-edit-dialog" id="sga-users-edit-dialog" aria-labelledby="sga-users-edit-title">
  <header class="sga-users-dialog-head">
    <div><h2 id="sga-users-edit-title">Editar usuario</h2><p><?=e($editar['apellidos'].' '.$editar['nombres'])?> · <?=e($editar['cedula'])?></p></div>
    <button type="button" class="sga-users-dialog-close" data-sga-users-edit-close aria-label="Cerrar edicion">&times;</button>
  </header>
  <div class="sga-users-dialog-content">
<form method="post" accept-charset="UTF-8"><input type="hidden" name="csrf" value="<?=e($csrf)?>"><input type="hidden" name="accion" value="editar"><input type="hidden" name="id" value="<?=(int)$editar['id']?>">
<input type="hidden" name="retorno_rol" value="<?=e($rolFiltro)?>"><input type="hidden" name="retorno_jornada" value="<?=e($jornadaFiltro)?>"><input type="hidden" name="retorno_q" value="<?=e($q)?>"><input type="hidden" name="retorno_pag" value="<?=$pagina?>">
<div class="form-grid cols-2"><label>Cédula<input name="cedula" required value="<?=e($editar['cedula']??'')?>"></label><label>Correo<input type="email" name="correo" value="<?=e($editar['correo']??'')?>"></label><label>Apellidos<input required name="apellidos" value="<?=e($editar['apellidos']??'')?>"></label><label>Nombres<input required name="nombres" value="<?=e($editar['nombres']??'')?>"></label>
<fieldset class="sga-users-jornadas"><legend>Jornadas del usuario</legend>
<div class="sga-users-jornada-items"><?php foreach($jornadasGestion as $j):?><label><input type="checkbox" name="jornadas[]" value="<?=(int)$j['id']?>" <?=isset($editarJornadasMarcadas[(int)$j['id']])?'checked':''?>><?=e($j['nombre'])?></label><?php endforeach;?></div>
<p class="mini-note">Selecciona una o varias jornadas para este período académico. <?php if(esSubadmin()):?>Solo puedes asignar las que administras.<?php endif;?></p></fieldset>
<?php if (!$editar):?><label>Clave inicial<input type="password" name="clave" autocomplete="new-password" placeholder="Vacío = contraseña temporal automática para representantes"></label><label>Rol de usuario<select name="rol" required><option value="estudiante">Estudiante</option><option value="docente">Docente</option><option value="representante">Representante</option></select></label><p class="mini-note" style="grid-column:1/-1">Representantes: registra siempre su correo real. Si dejas la clave vacía, se genera una clave temporal aleatoria; el representante la establece desde «¿Olvidaste tu contraseña?» usando su cédula.</p><?php else:?>
<fieldset class="sga-users-edit-roles">
<legend>Roles del usuario</legend>
<div class="sga-users-edit-role-items">
<?php foreach(['docente'=>'Docente','estudiante'=>'Estudiante','representante'=>'Representante'] as $codigo=>$titulo):?>
<label>
<input type="checkbox" name="roles_usuario[]" value="<?=e($codigo)?>" <?=isset($editarRolesMarcados[$codigo])?'checked':''?>><?=e($titulo)?></label>
<?php endforeach;?>
</div>
<p class="mini-note">Puedes marcar uno o varios roles compatibles. Los permisos del Subadministrador se gestionan exclusivamente en «Roles de usuarios». No se pueden retirar perfiles con matrículas, asignaturas o hijos vinculados.</p>
</fieldset>
<label>Nueva contraseña (opcional)<input type="password" name="nueva_clave" autocomplete="new-password" minlength="8" maxlength="72" placeholder="Escribir nueva contraseña"></label>
<label>Confirmar contraseña<input type="password" name="confirmar_clave" autocomplete="new-password" minlength="8" maxlength="72" placeholder="Repetir nueva contraseña"></label>
<div class="mini-note" style="grid-column:1/-1">Deja los dos campos vacíos para conservar la contraseña actual. Si asignas una nueva, utiliza al menos 8 caracteres y confirma que coincidan.</div>
<?php endif;?>
<div class="form-actions"><button type="button" class="btn btn-secondary" data-sga-users-edit-close>Cancelar</button><button type="submit" class="btn btn-primary">Guardar cambios</button></div></div></form>
  </div>
</dialog>
<?php endif;?>
<dialog id="sga-users-overlay" class="sga-users-dialog" aria-labelledby="sga-users-dialog-title">
    <header class="sga-users-dialog-head">
      <div><h2 id="sga-users-dialog-title">Crear o importar usuarios</h2><p>Selecciona cómo deseas registrar las cuentas en el SGA.</p></div>
      <button type="button" id="sga-users-close" class="sga-users-dialog-close" aria-label="Cerrar ventana">&times;</button>
    </header>
    <div class="sga-users-tabs" role="tablist" aria-label="Método de registro">
      <button type="button" class="sga-users-tab" role="tab" id="sga-users-tab-crear" aria-selected="true" aria-controls="sga-users-panel-crear" data-sga-users-tab="crear">Crear usuario</button>
      <button type="button" class="sga-users-tab" role="tab" id="sga-users-tab-csv" aria-selected="false" aria-controls="sga-users-panel-csv" data-sga-users-tab="csv" tabindex="-1">Importar CSV</button>
    </div>
    <div class="sga-users-dialog-content">
      <section class="sga-users-pane" id="sga-users-panel-crear" role="tabpanel" aria-labelledby="sga-users-tab-crear">
        <form method="post" id="sga-users-create-form" accept-charset="UTF-8">
          <input type="hidden" name="csrf" value="<?=e($csrf)?>">
          <input type="hidden" name="accion" value="crear"><input type="hidden" name="retorno_rol" value="<?=e($rolFiltro)?>"><input type="hidden" name="retorno_jornada" value="<?=e($jornadaFiltro)?>"><input type="hidden" name="retorno_q" value="<?=e($q)?>"><input type="hidden" name="retorno_pag" value="<?=$pagina?>">
          <div class="form-grid cols-2">
            <label>Cédula<input name="cedula" required autocomplete="off" placeholder="Cédula de identidad"></label>
            <label>Correo<input type="email" name="correo" autocomplete="email" placeholder="correo@ejemplo.com"></label>
            <label>Apellidos<input required name="apellidos" autocomplete="family-name"></label>
            <label>Nombres<input required name="nombres" autocomplete="given-name"></label>
            <fieldset class="sga-users-jornadas" id="sga-usuario-jornada-label">
              <legend>Jornadas del usuario</legend>
              <div class="sga-users-jornada-items">
                <?php foreach($jornadasGestion as $j):?><label><input type="checkbox" name="jornadas[]" value="<?=(int)$j['id']?>"><?=e($j['nombre'])?></label><?php endforeach;?>
              </div>
              <p class="mini-note">Marca una o varias jornadas del período activo. Para representantes, la asignación es opcional para Administrador.</p>
            </fieldset>
            <label>Clave inicial<input type="password" name="clave" autocomplete="new-password" placeholder="Vacío: según el rol, cédula o clave temporal"></label>
            <label>Rol de usuario
              <select name="rol" required>
                <option value="estudiante">Estudiante</option>
                <option value="docente">Docente</option>
                <option value="representante">Representante</option>
              </select>
            </label>
            <p class="mini-note" style="grid-column:1/-1">Para representantes es obligatorio un correo real. Si no escribes una clave, se genera una temporal aleatoria; podrán recuperarla mediante su cédula desde «¿Olvidaste tu contraseña?».</p>
            <div class="form-actions">
              <button type="button" class="btn btn-secondary" data-sga-users-cancel>Cancelar</button>
              <button type="submit" class="btn btn-primary">Crear usuario con rol</button>
            </div>
          </div>
        </form>
      </section>
      <section class="sga-users-pane" id="sga-users-panel-csv" role="tabpanel" aria-labelledby="sga-users-tab-csv" hidden>
        <p class="sga-users-import-hint"><strong>Importación masiva de usuarios.</strong> Archivo CSV UTF-8. En la columna <strong>jornadas</strong> escribe una o varias, separadas por <code>|</code>: <code>MATUTINA|VESPERTINA</code>. Cada fila puede tener jornadas distintas. Las contraseñas existentes no se modifican.</p>
        <form method="post" action="<?=e(url('modulos/usuarios/importar.php'))?>" enctype="multipart/form-data">
          <input type="hidden" name="csrf" value="<?=e($csrf)?>">
          <?php if(esSubadmin()):?>
          <label>Jornada predeterminada (solo CSV antiguos sin columna <code>jornadas</code>)
            <select name="jornada_id"><option value="">Usar las jornadas de cada fila del CSV</option><?php foreach($jornadasGestion as $j):?><option value="<?=(int)$j['id']?>"><?=e($j['nombre'])?></option><?php endforeach;?></select>
          </label>
          <?php endif;?>
          <label style="margin-top:13px">Archivo CSV
            <input type="file" name="archivo" accept=".csv,text/csv" required>
          </label>
          <?php if(esAdminAcademico()):?>
          <label class="sga-users-inline-check"><input type="checkbox" name="actualizar_datos" value="1"><span>Corregir también apellidos, nombres y correo de cuentas existentes con los valores del CSV, sin cambiar sus cédulas ni contraseñas.</span></label>
          <?php endif;?>
          <?php if(!$pid):?><p class="notice">Activa un período académico antes de importar usuarios con rol.</p><?php endif;?>
          <div class="sga-users-import-actions">
            <a class="btn btn-secondary" href="<?=e(url('plantilla_usuarios.csv'))?>">Descargar plantilla</a>
            <button type="button" class="btn btn-secondary" data-sga-users-cancel>Cancelar</button>
            <button type="submit" class="btn btn-primary" <?=$pid?'':'disabled'?>>Importar usuarios</button>
          </div>
        </form>
      </section>
    </div>
</dialog>
<script>
(function(){
  'use strict';
  const dialog=document.getElementById('sga-users-overlay');
  const editDialog=document.getElementById('sga-users-edit-dialog');
  const trigger=document.getElementById('sga-users-open');
  const tabs=Array.from(dialog?.querySelectorAll('[data-sga-users-tab]')||[]);
  const createForm=document.getElementById('sga-users-create-form');
  const tipoUsuario=createForm?.querySelector('select[name="rol"]');
  const jornadaBox=document.getElementById('sga-usuario-jornada-label');
  const panels={crear:document.getElementById('sga-users-panel-crear'),csv:document.getElementById('sga-users-panel-csv')};
  function seleccionarPestana(tipo,ponerFoco){
    if(!panels[tipo])return;
    for(const tab of tabs){
      const activo=tab.dataset.sgaUsersTab===tipo;
      tab.setAttribute('aria-selected',String(activo));
      tab.tabIndex=activo?0:-1;
      if(activo&&ponerFoco)tab.focus();
    }
    for(const [nombre,panel] of Object.entries(panels))if(panel)panel.hidden=nombre!==tipo;
  }
  function ajustarJornada(){
    if(!tipoUsuario||!jornadaBox)return;
    // La jornada nunca desaparece: puede pertenecer a más de una.
    const aviso=jornadaBox.querySelector('p');
    if(aviso) aviso.dataset.rolSeleccionado=tipoUsuario.value;
  }
  createForm?.addEventListener('submit',function(e){
    const rol=tipoUsuario?.value||'';
    const requeridas=rol!=='representante'||<?=esSubadmin()?'true':'false'?>;
    if(requeridas && !createForm.querySelector('input[name="jornadas[]"]:checked')){
      e.preventDefault();
      alert('Selecciona al menos una jornada para el usuario.');
      jornadaBox?.querySelector('input[name="jornadas[]"]')?.focus();
    }
  });
  if(dialog&&trigger){
    trigger.addEventListener('click',()=>{
      seleccionarPestana('crear',false);
      ajustarJornada();
      dialog.showModal();
      (panels.crear?.querySelector('input:not([type="hidden"])')||dialog.querySelector('[data-sga-users-tab]'))?.focus();
    });
    dialog.querySelector('#sga-users-close')?.addEventListener('click',()=>dialog.close());
    dialog.querySelectorAll('[data-sga-users-cancel]').forEach(btn=>btn.addEventListener('click',()=>dialog.close()));
    // Al pulsar fuera del recuadro se cierra el dialogo, como en Representantes.
    dialog.addEventListener('click',event=>{
      if(event.target!==dialog)return;
      const r=dialog.getBoundingClientRect();
      if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)dialog.close();
    });
    for(const tab of tabs){
      tab.addEventListener('click',()=>seleccionarPestana(tab.dataset.sgaUsersTab,true));
      tab.addEventListener('keydown',event=>{
        if(!['ArrowLeft','ArrowRight'].includes(event.key))return;
        event.preventDefault();
        const ix=tabs.indexOf(tab),next=tabs[(ix+(event.key==='ArrowRight'?1:tabs.length-1))%tabs.length];
        seleccionarPestana(next.dataset.sgaUsersTab,true);
      });
    }
    tipoUsuario?.addEventListener('change',ajustarJornada);
    ajustarJornada();
  }
  // Edicion: cargar el usuario solicitado y abrir su ficha flotante automaticamente.
  if(editDialog){
    editDialog.showModal();
    const cerrarEdicion=()=>editDialog.close();
    editDialog.querySelectorAll('[data-sga-users-edit-close]').forEach(btn=>btn.addEventListener('click',cerrarEdicion));
    editDialog.addEventListener('click',event=>{
      if(event.target!==editDialog)return;
      const r=editDialog.getBoundingClientRect();
      if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)editDialog.close();
    });
    editDialog.addEventListener('close',()=>{
      // Quitar ?editar=... sin recargar para que no se reabra al actualizar.
      const clean=new URL(window.location.href);
      clean.searchParams.delete('editar');
      try{window.history.replaceState(null,'',clean.pathname+clean.search+clean.hash);}catch(_e){}
    });
  }
})();
</script>


<div class="toolbar sga-users-filter-toolbar">
  <form method="get" action="<?=e(url('modulos/usuarios/index.php'))?>" class="sga-users-filter-form" id="formBusquedaUsuarios" role="search">
    <label class="sga-users-role-filter" for="sga-users-filtro-rol"><span>Filtrar por rol</span>
      <select name="rol" id="sga-users-filtro-rol" aria-label="Filtrar usuarios por rol">
      <?php foreach($opcionesRolUsuarios as $codigoRol=>$nombreRol):?>
        <option value="<?=e($codigoRol)?>" <?=$rolFiltro===$codigoRol?'selected':''?>><?=e($nombreRol)?></option>
      <?php endforeach;?>
      </select>
    </label>
    <label class="sga-users-jornada-filter" for="sga-users-filtro-jornada"><span>Filtrar por jornada</span>
      <select name="jornada" id="sga-users-filtro-jornada" aria-label="Filtrar usuarios por jornada">
        <option value="todas" <?=$jornadaFiltro==='todas'?'selected':''?>>Todas las jornadas</option>
        <?php foreach($jornadasFiltroDisponibles as $j):?>
          <option value="<?=(int)$j['id']?>" <?=$jornadaFiltro===(string)(int)$j['id']?'selected':''?>><?=e($j['nombre'])?></option>
        <?php endforeach;?>
        <?php if(!esSubadmin()):?><option value="sin_asignar" <?=$jornadaFiltro==='sin_asignar'?'selected':''?>>Sin jornada asignada</option><?php endif;?>
      </select>
    </label>
    <input type="search" id="busquedaUsuarios" name="q" value="<?=e($q)?>" placeholder="Cédula, apellidos, nombres o correo" aria-label="Buscar usuarios" aria-describedby="ayudaBusquedaUsuarios" autocomplete="off">
    <button type="submit" class="btn btn-secondary" title="Consulta usuarios con el rol y búsqueda elegidos">Buscar más</button>
    <?php if($q!==''):?><a class="btn btn-secondary" href="<?=e(url('modulos/usuarios/index.php?'.http_build_query(['rol'=>$rolFiltro,'jornada'=>$jornadaFiltro])))?>">Limpiar búsqueda</a><?php endif;?>
  </form>
  <span class="mini-note">El historial académico y las cuentas administrativas están protegidos.</span>
</div>
<div class="mini-note" id="ayudaBusquedaUsuarios" aria-live="polite" style="margin:0 0 12px">Filtra los usuarios del rol seleccionado. Escribe para buscar en esta pagina o pulsa Enter para buscar en toda la base de datos.</div>
<nav class="paginacion-sga" aria-label="Paginación de usuarios">
  <span class="mini-note"><?=number_format($totalUsuarios,0,',','.')?> usuario(s) encontrados · Página <?=$pagina?> de <?=$totalPaginas?></span>
  <div class="actions">
    <?php if($pagina>1):?><a class="btn btn-sm btn-secondary" href="<?=e($urlPaginaUsuarios($pagina-1))?>">Anterior</a><?php endif;?>
    <?php if($pagina<$totalPaginas):?><a class="btn btn-sm btn-secondary" href="<?=e($urlPaginaUsuarios($pagina+1))?>">Siguiente</a><?php endif;?>
  </div>
</nav>
<div class="table-wrap"><table class="table table-responsive-cards" id="tablaUsuarios"><thead><tr><th>Cédula</th><th>Persona</th><th>Correo</th><th>Rol(es)</th><th>Jornadas</th><th>Estado</th><th>Acciones</th></tr></thead><tbody>
<?php foreach($usuarios as $u):$uid=(int)$u['id'];$roles=$rolesPorUsuario[$uid]??[];$protegido=!empty($rolesGlobales[$uid]);?><tr data-usuario-fila="1"><td><?=e($u['cedula'])?></td><td><strong><?=e($u['apellidos'].' '.$u['nombres'])?></strong></td><td><?=e($u['correo']??'')?></td><td><?php if(!$roles):?><span class="badge">Sin rol</span><?php else:foreach($roles as $r):?><span class="badge"><?=e($r['nombre'].($r['periodo']?' · '.$r['periodo']:''))?></span> <?php endforeach;endif;?></td><td><?php if(empty($jornadasPorUsuario[$uid])):?><span class="mini-note">Sin asignar</span><?php else:foreach($jornadasPorUsuario[$uid] as $jn):?><span class="badge"><?=e($jn)?></span> <?php endforeach;endif;?></td><td><span class="badge <?=$u['activo']?'good':'bad'?>"><?=$u['activo']?'Activo':'Inactivo'?></span></td><td><div class="actions">
<?php if(!$protegido && esAdminAcademico()):?><a class="btn btn-sm btn-secondary" href="<?=e($urlBaseUsuarios(['editar'=>$uid]))?>" aria-haspopup="dialog">Editar</a><?php if((int)$u['id']!==(int)$_SESSION['usuario_id']):?>
<form method="post"><input type="hidden" name="csrf" value="<?=e($csrf)?>"><input type="hidden" name="accion" value="toggle"><input type="hidden" name="retorno_rol" value="<?=e($rolFiltro)?>"><input type="hidden" name="retorno_jornada" value="<?=e($jornadaFiltro)?>"><input type="hidden" name="retorno_q" value="<?=e($q)?>"><input type="hidden" name="retorno_pag" value="<?=$pagina?>"><input type="hidden" name="id" value="<?=(int)$u['id']?>"><button class="btn btn-sm <?=$u['activo']?'btn-secondary':'btn-success'?>" data-confirm="¿Cambiar el estado del usuario?"><?=$u['activo']?'Desactivar':'Activar'?></button></form>
<form method="post"><input type="hidden" name="csrf" value="<?=e($csrf)?>"><input type="hidden" name="accion" value="eliminar"><input type="hidden" name="retorno_rol" value="<?=e($rolFiltro)?>"><input type="hidden" name="retorno_jornada" value="<?=e($jornadaFiltro)?>"><input type="hidden" name="retorno_q" value="<?=e($q)?>"><input type="hidden" name="retorno_pag" value="<?=$pagina?>"><input type="hidden" name="id" value="<?=(int)$u['id']?>"><button class="btn btn-sm btn-danger" data-confirm="Solo se eliminará si no tiene historial. ¿Continuar?">Eliminar</button></form>
<?php endif;endif;?><?php if($protegido):?><span class="badge">Cuenta administrativa · solo consulta</span><?php endif;?></div></td></tr><?php endforeach;?>
<tr id="usuariosSinCoincidencias" <?=$usuarios?'hidden':''?>><td colspan="7" id="usuariosSinCoincidenciasTexto" class="empty">No hay usuarios para mostrar. Puedes escribir otra búsqueda y presionar Enter.</td></tr>
</tbody></table></div>
<script>
(function () {
    'use strict';
    var entrada=document.getElementById('busquedaUsuarios');
    var tabla=document.getElementById('tablaUsuarios');
    var ayuda=document.getElementById('ayudaBusquedaUsuarios');
    var filaVacia=document.getElementById('usuariosSinCoincidencias');
    var mensajeVacio=document.getElementById('usuariosSinCoincidenciasTexto');
    if (!entrada || !tabla || !ayuda || !filaVacia || !mensajeVacio) return;

    // El filtrado local no dispara peticiones al servidor: solo se consulta MySQL
    // al enviar el formulario con Enter o "Buscar más".
    function normalizar(texto) {
        var valor=String(texto == null ? '' : texto).toLowerCase();
        if (typeof valor.normalize === 'function') valor=valor.normalize('NFD');
        return valor.replace(/[\u0300-\u036f]/g,'').replace(/\s+/g,' ').trim();
    }
    var filas=Array.prototype.slice.call(tabla.querySelectorAll('tbody tr[data-usuario-fila]'));
    var usuarios=filas.map(function (fila) {
        // Excluir la columna "Acciones" para que "Editar" o "Eliminar" no sean coincidencias.
        var texto=Array.prototype.slice.call(fila.cells,0,6).map(function(celda){return celda.textContent;}).join(' ');
        return {fila:fila, texto:normalizar(texto)};
    });
    function filtrar() {
        var consulta=normalizar(entrada.value);
        var palabras=consulta ? consulta.split(' ') : [];
        var visibles=0;
        usuarios.forEach(function (usuario) {
            var coincide=palabras.every(function (palabra) {return usuario.texto.indexOf(palabra)!==-1;});
            usuario.fila.hidden=!coincide;
            if (coincide) visibles++;
        });
        filaVacia.hidden=visibles>0;
        if (!visibles) {
            mensajeVacio.textContent='No hay coincidencias entre los usuarios cargados. Pulsa Enter para consultar toda la base de datos.';
        }
        ayuda.textContent=consulta
            ? visibles+' de '+usuarios.length+' usuarios cargados coinciden. Pulsa Enter para buscar en la base de datos.'
            : 'Mostrando '+visibles+' usuarios de esta página. Escribe para filtrar aquí o pulsa Enter para buscar en toda la base de datos.';
    }
    entrada.addEventListener('input',filtrar);
    var filtros=[document.getElementById('sga-users-filtro-rol'),document.getElementById('sga-users-filtro-jornada')];
    filtros.forEach(function(select){
        if(select)select.addEventListener('change',function(){
            document.getElementById('formBusquedaUsuarios').requestSubmit();
        });
    });
    filtrar();
})();
</script>
<?php require __DIR__.'/../../partials/footer.php'; ?>
