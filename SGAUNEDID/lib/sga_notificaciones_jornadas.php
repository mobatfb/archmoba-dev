<?php
/** Notificaciones institucionales por correo, limitadas a la jornada y periodo autorizados. */
require_once __DIR__ . '/funciones.php';

/** Permisos sin depender de sesion: tambien se usa al reintentar desde Cron. */
function sgaNotiContextoActor(int $periodoId, int $actorId, ?string $modo = null): ?array {
    global $conexion;
    if ($periodoId <= 0 || $actorId <= 0) return null;
    $stmt=$conexion->prepare('SELECT 1 FROM usuarios WHERE id=? AND activo=1 LIMIT 1');
    if (!$stmt) throw new RuntimeException('No se pudo comprobar el remitente.');
    $stmt->bind_param('i',$actorId);$stmt->execute();$activo=(bool)$stmt->get_result()->fetch_row();$stmt->close();
    if (!$activo) return null;
    $stmt=$conexion->prepare("SELECT r.codigo FROM usuario_roles ur JOIN roles r ON r.id=ur.rol_id
        WHERE ur.usuario_id=? AND ((ur.periodo_id IS NULL AND r.codigo IN ('superadmin','subadmin'))
          OR (ur.periodo_id=? AND r.codigo='docente')
          OR (ur.periodo_id IS NULL AND r.codigo='representante'))");
    if (!$stmt) throw new RuntimeException('No se pudo comprobar el rol del remitente.');
    $stmt->bind_param('ii',$actorId,$periodoId);$stmt->execute();
    $roles=array_column($stmt->get_result()->fetch_all(MYSQLI_ASSOC),'codigo');$stmt->close();
    $super=in_array('superadmin',$roles,true);
    $admin=$super||in_array('subadmin',$roles,true);
    $docente=in_array('docente',$roles,true);
    $representante=in_array('representante',$roles,true);
    if ($modo===null) $modo=$admin?'administracion':($docente?'docente':'representante');
    if (!in_array($modo,['administracion','docente','representante'],true)) return null;
    if (($modo==='administracion'&&!$admin)||($modo==='docente'&&!$docente)||($modo==='representante'&&!$representante)) return null;
    if ($modo==='docente') {
        $stmt=$conexion->prepare("SELECT DISTINCT a.jornada_id id FROM ofertas_academicas o
            JOIN aulas_periodo ap ON ap.id=o.aula_periodo_id AND ap.activo=1
            JOIN aulas a ON a.id=ap.aula_id AND a.activo=1
            JOIN asignaturas s ON s.id=o.asignatura_id AND s.activo=1 AND s.archivado_en IS NULL
            JOIN jornadas j ON j.id=a.jornada_id AND j.activo=1
            WHERE o.docente_id=? AND o.activo=1 AND ap.periodo_id=? ORDER BY a.jornada_id");
        if (!$stmt) throw new RuntimeException('No se pudieron consultar las asignaturas del docente.');
        $stmt->bind_param('ii',$actorId,$periodoId);$stmt->execute();
        $ids=array_map('intval',array_column($stmt->get_result()->fetch_all(MYSQLI_ASSOC),'id'));
        $stmt->close();
    } elseif ($modo==='representante') {
        // El representante solo obtiene jornadas donde tiene hijos matriculados actualmente.
        $stmt=$conexion->prepare("SELECT DISTINCT a.jornada_id id FROM sga_representantes_estudiantes re
            JOIN matriculas m ON m.estudiante_id=re.estudiante_id AND m.estado='activo'
            JOIN aulas_periodo ap ON ap.id=m.aula_periodo_id AND ap.activo=1
            JOIN aulas a ON a.id=ap.aula_id AND a.activo=1
            JOIN jornadas j ON j.id=a.jornada_id AND j.activo=1
            JOIN usuarios hijo ON hijo.id=re.estudiante_id AND hijo.activo=1
            WHERE re.representante_id=? AND re.activo=1 AND ap.periodo_id=? ORDER BY a.jornada_id");
        if (!$stmt) throw new RuntimeException('No se pudieron consultar las jornadas de tus hijos.');
        $stmt->bind_param('ii',$actorId,$periodoId);$stmt->execute();
        $ids=array_map('intval',array_column($stmt->get_result()->fetch_all(MYSQLI_ASSOC),'id'));
        $stmt->close();
    } elseif ($super) {
        $rs=$conexion->query('SELECT id FROM jornadas WHERE activo=1 ORDER BY orden,id');
        $ids=$rs?array_map('intval',array_column($rs->fetch_all(MYSQLI_ASSOC),'id')):[];
    } else {
        $stmt=$conexion->prepare('SELECT sj.jornada_id id FROM subadministrador_jornadas sj
            JOIN jornadas j ON j.id=sj.jornada_id AND j.activo=1
            WHERE sj.usuario_id=? AND sj.periodo_id=? ORDER BY j.orden,j.id');
        if (!$stmt) throw new RuntimeException('No se pudieron consultar las jornadas autorizadas.');
        $stmt->bind_param('ii',$actorId,$periodoId);$stmt->execute();
        $ids=array_map('intval',array_column($stmt->get_result()->fetch_all(MYSQLI_ASSOC),'id'));
        $stmt->close();
    }
    return $ids?['super'=>($modo==='administracion'&&$super),'jornadas'=>array_values(array_unique($ids)),
        'modo'=>$modo,'actor_id'=>$actorId]:null;
}

function sgaNotiJornadas(int $periodoId, array $contexto): array {
    global $conexion;
    if (!$contexto['jornadas']) return [];
    $in = implode(',', array_map('intval', $contexto['jornadas']));
    $rs = $conexion->query("SELECT id, nombre FROM jornadas WHERE activo=1 AND id IN ($in) ORDER BY orden,nombre,id");
    return $rs ? $rs->fetch_all(MYSQLI_ASSOC) : [];
}

/** Solo jornadas actuales del remitente; el valor 0 significa TODAS las autorizadas. */
function sgaNotiComprobarJornada(array $contexto, int $jornadaId): array {
    if ($jornadaId < 0 || ($jornadaId !== 0 && !in_array($jornadaId, $contexto['jornadas'], true))) {
        throw new DomainException('La jornada seleccionada no esta autorizada.');
    }
    return $jornadaId ? [$jornadaId] : $contexto['jornadas'];
}

/**
 * Consulta correlacionada de alcance: gestion, matricula, docencia y representantes.
 * Se autoriza por relacion vigente en la jornada seleccionada, incluso si la persona participa en otras jornadas.
 * Los identificadores se convierten a enteros ANTES de formar la consulta SQL.
 */
function sgaNotiFiltroSQL(int $periodoId, array $contexto, int $jornadaId): string {
    $seleccionadas = sgaNotiComprobarJornada($contexto, $jornadaId);
    if (!$seleccionadas) return ' AND 1=0';
    $p = (int)$periodoId;
    $visibles = implode(',', array_map('intval', $seleccionadas));
    $relaciones = [
        "EXISTS (SELECT 1 FROM usuarios_jornadas_gestion uj WHERE uj.usuario_id=u.id AND uj.periodo_id=$p AND uj.jornada_id IN ($visibles))",
        "EXISTS (SELECT 1 FROM matriculas m JOIN aulas_periodo ap ON ap.id=m.aula_periodo_id AND ap.activo=1 JOIN aulas a ON a.id=ap.aula_id WHERE m.estudiante_id=u.id AND m.estado='activo' AND ap.periodo_id=$p AND a.jornada_id IN ($visibles))",
        "EXISTS (SELECT 1 FROM ofertas_academicas o JOIN aulas_periodo ap ON ap.id=o.aula_periodo_id AND ap.activo=1 JOIN aulas a ON a.id=ap.aula_id WHERE o.docente_id=u.id AND o.activo=1 AND ap.periodo_id=$p AND a.jornada_id IN ($visibles))",
        "EXISTS (SELECT 1 FROM sga_representantes_estudiantes re JOIN matriculas m ON m.estudiante_id=re.estudiante_id AND m.estado='activo' JOIN aulas_periodo ap ON ap.id=m.aula_periodo_id AND ap.activo=1 JOIN aulas a ON a.id=ap.aula_id WHERE re.representante_id=u.id AND re.activo=1 AND ap.periodo_id=$p AND a.jornada_id IN ($visibles))",
    ];
    // Los otros Subadministradores de la misma jornada tambien son contactos
    // validos. Nunca excluirlos por su rol global: pueden ser docentes o padres.
    $relaciones[] = "EXISTS (SELECT 1 FROM subadministrador_jornadas sj JOIN usuario_roles ur ON ur.usuario_id=sj.usuario_id AND ur.periodo_id IS NULL JOIN roles r ON r.id=ur.rol_id AND r.codigo='subadmin' WHERE sj.usuario_id=u.id AND sj.periodo_id=$p AND sj.jornada_id IN ($visibles))";
    // Esto es SOLO el ambito de lectura/envio. Los roles de los destinatarios
    // se protegen de forma independiente en el modulo Roles y sus validadores.
    return ' AND (' . implode(' OR ', $relaciones) . ')';
}

function sgaNotiTipoSQL(int $periodoId, string $tipo): string {
    $p = (int)$periodoId;
    if ($tipo === 'estudiante' || $tipo === 'docente') {
        return " AND EXISTS (SELECT 1 FROM usuario_roles ur JOIN roles r ON r.id=ur.rol_id WHERE ur.usuario_id=u.id AND ur.periodo_id=$p AND r.codigo='".$tipo."')";
    }
    if ($tipo === 'representante') {
        return " AND EXISTS (SELECT 1 FROM usuario_roles ur JOIN roles r ON r.id=ur.rol_id WHERE ur.usuario_id=u.id AND ur.periodo_id IS NULL AND r.codigo='representante')";
    }
    return '';
}

/** Lista inicial sin filtro, busqueda opcional y validacion segura por ids. */
function sgaNotiBuscar(int $periodoId, array $contexto, int $jornadaId, string $q = '', string $tipo = '', array $ids = [], int $pagina = 1, int $porPagina = 25): array {
    global $conexion;
    if (!$periodoId || !$contexto['jornadas']) return [];
    $q = trim($q);
    $esIds = (bool)$ids;
    if (!$esIds && strlen($q) > 80) return [];
    if ($esIds) {
        $ids = array_values(array_unique(array_filter(array_map('intval', $ids), static fn($v) => $v > 0)));
        if (!$ids || count($ids) > 20) return [];
    }
    $filtrado = sgaNotiFiltroSQL($periodoId, $contexto, $jornadaId);
    if (!$esIds) $filtrado .= sgaNotiTipoSQL($periodoId, $tipo);
    $criterio = $esIds
        ? ' AND u.id IN ('.implode(',', $ids).')'
        : ($q === '' ? '' : " AND (u.cedula LIKE ? OR u.nombres LIKE ? OR u.apellidos LIKE ? OR CONCAT(u.apellidos,' ',u.nombres) LIKE ? OR u.correo LIKE ?)");
    // La consulta sin busqueda se pagina para evitar cargar a todos los usuarios a la vez.
    // Se consulta una fila adicional para saber si hay una pagina siguiente.
    $pagina = max(1, min(10000, $pagina));
    $porPagina = max(5, min(100, $porPagina));
    $limiteSQL = $esIds ? ' LIMIT 60' : ' LIMIT '.($porPagina + 1).' OFFSET '.(($pagina - 1) * $porPagina);
    $sql = "SELECT u.id,u.cedula,u.apellidos,u.nombres,u.correo,
        CASE WHEN EXISTS(SELECT 1 FROM usuario_roles ur JOIN roles r ON r.id=ur.rol_id WHERE ur.usuario_id=u.id AND ur.periodo_id=".(int)$periodoId." AND r.codigo='docente') THEN 'Docente'
        WHEN EXISTS(SELECT 1 FROM usuario_roles ur JOIN roles r ON r.id=ur.rol_id WHERE ur.usuario_id=u.id AND ur.periodo_id=".(int)$periodoId." AND r.codigo='estudiante') THEN 'Estudiante'
        WHEN EXISTS(SELECT 1 FROM usuario_roles ur JOIN roles r ON r.id=ur.rol_id WHERE ur.usuario_id=u.id AND ur.periodo_id IS NULL AND r.codigo='representante') THEN 'Representante'
        ELSE 'Personal' END AS tipo
        FROM usuarios u WHERE u.activo=1".$filtrado.$criterio.' ORDER BY u.apellidos,u.nombres,u.id'.$limiteSQL;
    $stmt = $conexion->prepare($sql);
    if (!$stmt) throw new RuntimeException('No se pudo consultar los destinatarios de tu jornada.');
    if (!$esIds && $q !== '') {
        // Los comodines introducidos por el usuario se tratan como texto literal.
        $valor = '%'.addcslashes($q, '\\%_').'%';
        $stmt->bind_param('sssss', $valor, $valor, $valor, $valor, $valor);
    }
    if (!$stmt->execute()) { $stmt->close(); throw new RuntimeException('No se pudo completar la búsqueda.'); }
    $rows = $stmt->get_result()->fetch_all(MYSQLI_ASSOC);
    $stmt->close();
    return $rows;
}

/** Seleccion individual autorizada para administradores. */
function sgaNotiValidarDestinatarios(int $pid, array $ctx, int $jid, array $ids): array {
    $ids=array_values(array_unique(array_filter(array_map('intval',$ids),static fn($id)=>$id>0)));
    if (!$ids || count($ids)>10) throw new DomainException('Selecciona de 1 a 10 destinatarios.');
    $filas=sgaNotiBuscar($pid,$ctx,$jid,'','',$ids);
    if(count($filas)!==count($ids)) throw new DomainException('Algunos destinatarios no pertenecen a tus jornadas.');
    return $filas;
}

function sgaNotiAulas(int $pid, array $ctx): array {
    global $conexion;
    if (($ctx['modo']??'')!=='administracion'||!$ctx['jornadas'])return [];
    $jids=implode(',',array_map('intval',$ctx['jornadas']));
    $stmt=$conexion->prepare("SELECT ap.id,a.jornada_id,a.nivel,a.nombre,a.paralelo,j.nombre jornada
        FROM aulas_periodo ap JOIN aulas a ON a.id=ap.aula_id AND a.activo=1
        JOIN jornadas j ON j.id=a.jornada_id AND j.activo=1
        WHERE ap.periodo_id=? AND ap.activo=1 AND a.jornada_id IN ($jids)
        ORDER BY j.orden,a.orden,a.nivel,a.nombre,a.paralelo,ap.id");
    if (!$stmt) throw new RuntimeException('No se pudieron consultar las aulas.');
    $stmt->bind_param('i',$pid);$stmt->execute();$filas=$stmt->get_result()->fetch_all(MYSQLI_ASSOC);$stmt->close();
    foreach($filas as &$f)$f['etiqueta']=trim($f['nivel'].' '.$f['nombre'].' '.$f['paralelo']).' - '.$f['jornada'];
    unset($f);return $filas;
}

/** Hijos actualmente matriculados del representante, con el aula y la jornada real. */
function sgaNotiHijosRepresentante(int $pid,int $actor,array $ctx): array {
    global $conexion;
    if (($ctx['modo']??'')!=='representante') return [];
    $stmt=$conexion->prepare("SELECT DISTINCT re.estudiante_id,ap.id aula_periodo_id,a.jornada_id,
        hijo.apellidos hijo_apellidos,hijo.nombres hijo_nombres,
        a.nivel,a.nombre aula,a.paralelo,j.nombre jornada
        FROM sga_representantes_estudiantes re
        JOIN usuarios hijo ON hijo.id=re.estudiante_id AND hijo.activo=1
        JOIN matriculas m ON m.estudiante_id=hijo.id AND m.estado='activo'
        JOIN aulas_periodo ap ON ap.id=m.aula_periodo_id AND ap.activo=1 AND ap.periodo_id=?
        JOIN aulas a ON a.id=ap.aula_id AND a.activo=1
        JOIN jornadas j ON j.id=a.jornada_id AND j.activo=1
        WHERE re.representante_id=? AND re.activo=1
        ORDER BY hijo.apellidos,hijo.nombres,j.orden,a.orden,ap.id");
    if(!$stmt) throw new RuntimeException('No se pudieron consultar tus hijos matriculados.');
    $stmt->bind_param('ii',$pid,$actor);$stmt->execute();$filas=$stmt->get_result()->fetch_all(MYSQLI_ASSOC);$stmt->close();
    foreach($filas as &$f){
        $f['hijo_nombre']=trim($f['hijo_apellidos'].' '.$f['hijo_nombres']);
        $f['aula_nombre']=trim($f['nivel'].' '.$f['aula'].' '.$f['paralelo']);
        $f['etiqueta']=$f['hijo_nombre'].' - '.$f['aula_nombre'].' ('.$f['jornada'].')';
    }
    unset($f);return $filas;
}

/** Nunca confiar en el estudiante que llega desde un campo oculto del navegador. */
function sgaNotiHijoValido(int $pid,int $actor,array $ctx,int $estudianteId): array {
    if(($ctx['modo']??'')!=='representante'||$estudianteId<=0)
        throw new DomainException('Selecciona un hijo o hija matriculado.');
    foreach(sgaNotiHijosRepresentante($pid,$actor,$ctx) as $h){
        if((int)$h['estudiante_id']===$estudianteId)return $h;
    }
    throw new DomainException('No existe vinculacion activa con ese estudiante en el periodo.');
}

/** Contactos individuales: exclusivamente docentes del aula del hijo y su subadministracion. */
function sgaNotiBuscarRepresentante(int $pid,int $actor,array $ctx,int $hijoId,string $q='',array $ids=[],int $pagina=1,int $porPagina=25): array {
    global $conexion;
    $h=sgaNotiHijoValido($pid,$actor,$ctx,$hijoId);
    $ap=(int)$h['aula_periodo_id'];$jid=(int)$h['jornada_id'];$p=(int)$pid;
    $ids=array_values(array_unique(array_filter(array_map('intval',$ids),static fn($n)=>$n>0)));
    if(count($ids)>10)throw new DomainException('Maximo 10 destinatarios individuales.');
    $q=trim($q);if(strlen($q)>80)$q=substr($q,0,80);
    $filtro=" AND u.id<>".(int)$actor." AND (
        EXISTS (SELECT 1 FROM ofertas_academicas o
          JOIN usuario_roles ur ON ur.usuario_id=o.docente_id AND ur.periodo_id=$p
          JOIN roles r ON r.id=ur.rol_id AND r.codigo='docente'
          WHERE o.docente_id=u.id AND o.aula_periodo_id=$ap AND o.activo=1)
        OR EXISTS (SELECT 1 FROM subadministrador_jornadas sj
          JOIN usuario_roles ur ON ur.usuario_id=sj.usuario_id AND ur.periodo_id IS NULL
          JOIN roles r ON r.id=ur.rol_id AND r.codigo='subadmin'
          WHERE sj.usuario_id=u.id AND sj.periodo_id=$p AND sj.jornada_id=$jid)
        )";
    $idSql=$ids?' AND u.id IN ('.implode(',',$ids).')':'';
    $busca=(!$ids&&$q!=='')?" AND (u.cedula LIKE ? OR u.nombres LIKE ? OR u.apellidos LIKE ? OR CONCAT(u.apellidos,' ',u.nombres) LIKE ? OR u.correo LIKE ?)":'';
    $pagina=max(1,min(10000,$pagina));$porPagina=max(5,min(50,$porPagina));
    $limite=$ids?' LIMIT 20':' LIMIT '.($porPagina+1).' OFFSET '.(($pagina-1)*$porPagina);
    $sql="SELECT u.id,u.cedula,u.apellidos,u.nombres,u.correo,
        CASE WHEN EXISTS (SELECT 1 FROM subadministrador_jornadas sj
           WHERE sj.usuario_id=u.id AND sj.periodo_id=$p AND sj.jornada_id=$jid)
           THEN 'Subadministrador' ELSE 'Docente' END tipo
        FROM usuarios u WHERE u.activo=1 $filtro $idSql $busca
        ORDER BY u.apellidos,u.nombres,u.id $limite";
    $stmt=$conexion->prepare($sql);
    if(!$stmt)throw new RuntimeException('No se pudieron consultar los contactos del aula.');
    if($busca){$v='%'.addcslashes($q,'\\%_').'%';$stmt->bind_param('sssss',$v,$v,$v,$v,$v);}
    if(!$stmt->execute()){$stmt->close();throw new RuntimeException('No se pudo realizar la busqueda.');}
    $filas=$stmt->get_result()->fetch_all(MYSQLI_ASSOC);$stmt->close();return $filas;
}

function sgaNotiOfertasDocente(int $pid, int $actor, array $ctx): array {
    global $conexion;
    if (($ctx['modo']??'')!=='docente'||!$ctx['jornadas'])return [];
    $jids=implode(',',array_map('intval',$ctx['jornadas']));
    $stmt=$conexion->prepare("SELECT o.id,o.aula_periodo_id,a.jornada_id,
        s.nombre asignatura,a.nivel,a.nombre aula,a.paralelo,j.nombre jornada
        FROM ofertas_academicas o JOIN aulas_periodo ap ON ap.id=o.aula_periodo_id AND ap.activo=1
        JOIN aulas a ON a.id=ap.aula_id AND a.activo=1
        JOIN jornadas j ON j.id=a.jornada_id AND j.activo=1
        JOIN asignaturas s ON s.id=o.asignatura_id AND s.activo=1 AND s.archivado_en IS NULL
        WHERE o.docente_id=? AND ap.periodo_id=? AND o.activo=1 AND a.jornada_id IN ($jids)
        ORDER BY j.orden,a.orden,s.nombre,o.id");
    if(!$stmt)throw new RuntimeException('No se pudieron consultar las asignaturas asignadas.');
    $stmt->bind_param('ii',$actor,$pid);$stmt->execute();$filas=$stmt->get_result()->fetch_all(MYSQLI_ASSOC);$stmt->close();
    foreach($filas as &$f)$f['etiqueta']=$f['asignatura'].' - '.trim($f['nivel'].' '.$f['aula'].' '.$f['paralelo']).' ('.$f['jornada'].')';
    unset($f);return $filas;
}

function sgaNotiOfertaValida(int $pid,int $actor,array $ctx,int $ofertaId): array {
    if (($ctx['modo']??'')!=='docente'||$ofertaId<=0)
        throw new DomainException('Selecciona una asignatura de tus cursos.');
    foreach(sgaNotiOfertasDocente($pid,$actor,$ctx) as $oferta){
        if((int)$oferta['id']===$ofertaId)return $oferta;
    }
    throw new DomainException('La asignatura no pertenece a tus cursos actuales.');
}

/** Consulta de individuos accesibles a un docente desde su asignatura vigente.
 * Incluye estudiantes del curso, representantes vinculados, colegas de jornada y subadministradores de jornada.
 */
function sgaNotiBuscarDocente(int $pid,int $actor,array $ctx,int $ofertaId,string $q='',array $ids=[],int $pagina=1,int $porPagina=25): array {
    global $conexion;
    $oferta=sgaNotiOfertaValida($pid,$actor,$ctx,$ofertaId);
    $ap=(int)$oferta['aula_periodo_id'];$jid=(int)$oferta['jornada_id'];$pid=(int)$pid;
    $ids=array_values(array_unique(array_filter(array_map('intval',$ids),static fn($n)=>$n>0)));
    if(count($ids)>10)throw new DomainException('Solo se permiten 10 personas por envio individual.');
    $q=trim($q);
    if(strlen($q)>80)$q=substr($q,0,80);
    $filtro=" AND u.id<>".(int)$actor." AND (
        EXISTS (SELECT 1 FROM matriculas m WHERE m.estudiante_id=u.id AND m.aula_periodo_id=$ap AND m.estado='activo')
        OR EXISTS (SELECT 1 FROM sga_representantes_estudiantes re JOIN matriculas m ON m.estudiante_id=re.estudiante_id
            WHERE re.representante_id=u.id AND re.activo=1 AND m.aula_periodo_id=$ap AND m.estado='activo')
        OR EXISTS (SELECT 1 FROM ofertas_academicas o JOIN aulas_periodo ap2 ON ap2.id=o.aula_periodo_id AND ap2.activo=1
            JOIN aulas a ON a.id=ap2.aula_id AND a.activo=1
            WHERE o.docente_id=u.id AND o.activo=1 AND ap2.periodo_id=$pid AND a.jornada_id=$jid)
        OR EXISTS (SELECT 1 FROM subadministrador_jornadas sj JOIN usuario_roles ur ON ur.usuario_id=sj.usuario_id AND ur.periodo_id IS NULL
            JOIN roles r ON r.id=ur.rol_id AND r.codigo='subadmin'
            WHERE sj.usuario_id=u.id AND sj.periodo_id=$pid AND sj.jornada_id=$jid)
        )";
    $idSql=$ids?' AND u.id IN ('.implode(',',$ids).')':'';
    $busca=(!$ids&&$q!=='')?" AND (u.cedula LIKE ? OR u.nombres LIKE ? OR u.apellidos LIKE ? OR CONCAT(u.apellidos,' ',u.nombres) LIKE ? OR u.correo LIKE ?)":'';
    $pagina=max(1,min(10000,$pagina));$porPagina=max(5,min(50,$porPagina));
    $limite=$ids?' LIMIT 20':' LIMIT '.($porPagina+1).' OFFSET '.(($pagina-1)*$porPagina);
    $sql="SELECT u.id,u.cedula,u.apellidos,u.nombres,u.correo,
        CASE WHEN EXISTS(SELECT 1 FROM subadministrador_jornadas sj WHERE sj.usuario_id=u.id AND sj.periodo_id=$pid AND sj.jornada_id=$jid)
                 THEN 'Subadministrador'
             WHEN EXISTS(SELECT 1 FROM ofertas_academicas o JOIN aulas_periodo ap2 ON ap2.id=o.aula_periodo_id AND ap2.periodo_id=$pid
                 JOIN aulas a ON a.id=ap2.aula_id AND a.jornada_id=$jid WHERE o.docente_id=u.id AND o.activo=1)
                 THEN 'Docente'
             WHEN EXISTS(SELECT 1 FROM matriculas m WHERE m.estudiante_id=u.id AND m.aula_periodo_id=$ap AND m.estado='activo')
                 THEN 'Estudiante'
             ELSE 'Representante' END tipo
        FROM usuarios u WHERE u.activo=1 $filtro $idSql $busca
        ORDER BY u.apellidos,u.nombres,u.id $limite";
    $stmt=$conexion->prepare($sql);
    if(!$stmt)throw new RuntimeException('No se pudieron consultar personas de la jornada.');
    if($busca){$val='%'.addcslashes($q,'\\%_').'%';$stmt->bind_param('sssss',$val,$val,$val,$val,$val);}
    $stmt->execute();$filas=$stmt->get_result()->fetch_all(MYSQLI_ASSOC);$stmt->close();return $filas;
}

/** No repetir destinatarios aunque tengan varias asignaturas o cuentas que compartan correo. */
function sgaNotiUnicosPorCorreo(array $personas): array {
    $vistos=[];$salida=[];
    foreach($personas as $p){
        $email=trim((string)($p['correo']??''));
        if(!filter_var($email,FILTER_VALIDATE_EMAIL))continue;
        $clave=strtolower($email);
        if(isset($vistos[$clave]))continue;
        $vistos[$clave]=true;$p['correo']=$email;$salida[]=$p;
    }
    return $salida;
}

/** Conjunto destinatario calculado en servidor; el navegador NO puede inventar miembros. */
function sgaNotiResolverGrupo(int $pid,int $actor,array $ctx,int $jid,string $tipo,
                               int $apSolicitada=0,int $ofertaId=0,array $ids=[],?int $soloId=null,int $hijoId=0): array {
    global $conexion;
    $autorizadas=sgaNotiComprobarJornada($ctx,$jid);
    if(!$autorizadas)throw new DomainException('No hay jornadas autorizadas para esta operacion.');
    $doc=($ctx['modo']??'')==='docente';
    $admin=($ctx['modo']??'')==='administracion';
    $rep=($ctx['modo']??'')==='representante';
    if(!$doc&&!$admin&&!$rep)throw new DomainException('Perfil no autorizado.');
    $apId=null;$ofId=null;$firma='Administracion academica';
    $datosOferta=null;$datosHijo=null;
    if($rep){
        $datosHijo=sgaNotiHijoValido($pid,$actor,$ctx,$hijoId);
        if($jid!==(int)$datosHijo['jornada_id'])
            throw new DomainException('La jornada del envio no corresponde al estudiante seleccionado.');
        $apId=(int)$datosHijo['aula_periodo_id'];
        $firma='Representante de: '.$datosHijo['hijo_nombre'].' | Aula: '.$datosHijo['aula_nombre'].' | Jornada: '.$datosHijo['jornada'];
    }
    if($doc){
        $datosOferta=sgaNotiOfertaValida($pid,$actor,$ctx,$ofertaId);
        $ofId=(int)$datosOferta['id'];
        $jidOferta=(int)$datosOferta['jornada_id'];
        if($jid!==$jidOferta)throw new DomainException('La jornada debe corresponder a la asignatura seleccionada.');
        $firma='Docente de la asignatura: '.$datosOferta['asignatura'];
    }
    if($tipo==='individual'){
        if($soloId!==null)$ids=[$soloId];
        $ids=array_values(array_unique(array_filter(array_map('intval',$ids),static fn($id)=>$id>0)));
        if(!$ids||count($ids)>10)throw new DomainException('Selecciona de 1 a 10 personas.');
        $personas=$doc?sgaNotiBuscarDocente($pid,$actor,$ctx,$ofId,'',$ids):
            ($rep?sgaNotiBuscarRepresentante($pid,$actor,$ctx,$hijoId,'',$ids):sgaNotiValidarDestinatarios($pid,$ctx,$jid,$ids));
        if(count($personas)!==count($ids))throw new DomainException('Algunos destinatarios ya no estan autorizados.');
        $etiqueta=$doc?'Personas vinculadas a mi asignatura y jornada':
            ($rep?'Docentes o subadministradores de '.$datosHijo['aula_nombre'].' ('.$datosHijo['jornada'].')':'Destinatarios individuales');
        return ['personas'=>sgaNotiUnicosPorCorreo($personas),'grupo'=>$etiqueta,
            'cargo'=>$firma,'aula_periodo_id'=>null,'oferta_id'=>$ofId];
    }
    $permitidos=$doc?['estudiantes_asignatura','familias_asignatura','docentes_jornada','subadmins_jornada']:
        ($rep?['docentes_hijo','subadmins_hijo']:
        ['estudiantes_aula','familias_aula','docentes_aula','docentes_jornada','subadmins_jornada',
         'todos_estudiantes','todos_docentes','todos_representantes','todos_todos']);
    if(!in_array($tipo,$permitidos,true))throw new DomainException('El grupo no esta disponible para tu perfil.');
    $whereSolo=$soloId!==null?' AND u.id='.(int)$soloId:'';
    $p=(int)$pid;
    if($rep){
        $aulaNombre=$datosHijo['aula_nombre'];
        $nombreJornada=$datosHijo['jornada'];
    }elseif($doc){
        $apId=(int)$datosOferta['aula_periodo_id'];
        $aulaNombre=trim($datosOferta['nivel'].' '.$datosOferta['aula'].' '.$datosOferta['paralelo']);
        $nombreJornada=(string)$datosOferta['jornada'];
    } elseif(in_array($tipo,['estudiantes_aula','familias_aula','docentes_aula'],true)){
        $jids=implode(',',array_map('intval',$autorizadas));
        $stmt=$conexion->prepare("SELECT ap.id,a.jornada_id,a.nivel,a.nombre,a.paralelo,j.nombre jornada
            FROM aulas_periodo ap JOIN aulas a ON a.id=ap.aula_id AND a.activo=1
            JOIN jornadas j ON j.id=a.jornada_id AND j.activo=1
            WHERE ap.id=? AND ap.periodo_id=? AND ap.activo=1 AND a.jornada_id IN ($jids) LIMIT 1");
        if(!$stmt)throw new RuntimeException('No se pudo comprobar el aula.');
        $stmt->bind_param('ii',$apSolicitada,$pid);$stmt->execute();$fila=$stmt->get_result()->fetch_assoc();$stmt->close();
        if(!$fila)throw new DomainException('El aula no pertenece a tus jornadas autorizadas.');
        if($jid>0 && (int)$fila['jornada_id']!==$jid)throw new DomainException('El aula no corresponde a la jornada elegida.');
        $apId=(int)$fila['id'];$aulaNombre=trim($fila['nivel'].' '.$fila['nombre'].' '.$fila['paralelo']);
        $nombreJornada=(string)$fila['jornada'];
    }
    if($rep && in_array($tipo,['docentes_hijo','subadmins_hijo'],true)){
        if($tipo==='docentes_hijo'){
            $grupo='Docentes del aula de '.$datosHijo['hijo_nombre'].' - '.$aulaNombre.' ('.$nombreJornada.')';
            $sql="SELECT DISTINCT u.id,u.cedula,u.apellidos,u.nombres,u.correo
                FROM ofertas_academicas o
                JOIN usuarios u ON u.id=o.docente_id AND u.activo=1
                JOIN usuario_roles ur ON ur.usuario_id=u.id AND ur.periodo_id=$p
                JOIN roles r ON r.id=ur.rol_id AND r.codigo='docente'
                WHERE o.aula_periodo_id=$apId AND o.activo=1 AND u.id<>".(int)$actor." $whereSolo
                ORDER BY u.apellidos,u.nombres,u.id LIMIT 6000";
        }else{
            $grupo='Subadministradores de '.$nombreJornada.' - representante de '.$datosHijo['hijo_nombre'];
            $sql="SELECT DISTINCT u.id,u.cedula,u.apellidos,u.nombres,u.correo
                FROM subadministrador_jornadas sj
                JOIN usuarios u ON u.id=sj.usuario_id AND u.activo=1
                JOIN usuario_roles ur ON ur.usuario_id=u.id AND ur.periodo_id IS NULL
                JOIN roles r ON r.id=ur.rol_id AND r.codigo='subadmin'
                WHERE sj.periodo_id=$p AND sj.jornada_id=$jid AND u.id<>".(int)$actor." $whereSolo
                ORDER BY u.apellidos,u.nombres,u.id LIMIT 6000";
        }
    } elseif($admin && in_array($tipo,['todos_estudiantes','todos_docentes','todos_representantes','todos_todos'],true)){
        // El subadministrador solo recorre aulas de sus jornadas autorizadas, nunca el catalogo global.
        $jids=implode(',',array_map('intval',$autorizadas));
        $nombres=[];foreach(sgaNotiJornadas($pid,$ctx) as $j){if(in_array((int)$j['id'],$autorizadas,true))$nombres[]=$j['nombre'];}
        $nombreJornada=implode(', ',$nombres);
        $comunes='u.id,u.cedula,u.apellidos,u.nombres,u.correo';
        $sqlEst="SELECT DISTINCT $comunes FROM matriculas m
            JOIN aulas_periodo ap ON ap.id=m.aula_periodo_id AND ap.periodo_id=$p AND ap.activo=1
            JOIN aulas a ON a.id=ap.aula_id AND a.activo=1 AND a.jornada_id IN ($jids)
            JOIN usuarios u ON u.id=m.estudiante_id AND u.activo=1
            WHERE m.estado='activo' AND u.id<>".(int)$actor." $whereSolo";
        $sqlDoc="SELECT DISTINCT $comunes FROM ofertas_academicas o
            JOIN aulas_periodo ap ON ap.id=o.aula_periodo_id AND ap.periodo_id=$p AND ap.activo=1
            JOIN aulas a ON a.id=ap.aula_id AND a.activo=1 AND a.jornada_id IN ($jids)
            JOIN usuarios u ON u.id=o.docente_id AND u.activo=1
            JOIN usuario_roles ur ON ur.usuario_id=u.id AND ur.periodo_id=$p
            JOIN roles r ON r.id=ur.rol_id AND r.codigo='docente'
            WHERE o.activo=1 AND u.id<>".(int)$actor." $whereSolo";
        $sqlRep="SELECT DISTINCT $comunes FROM sga_representantes_estudiantes re
            JOIN matriculas m ON m.estudiante_id=re.estudiante_id AND m.estado='activo'
            JOIN aulas_periodo ap ON ap.id=m.aula_periodo_id AND ap.periodo_id=$p AND ap.activo=1
            JOIN aulas a ON a.id=ap.aula_id AND a.activo=1 AND a.jornada_id IN ($jids)
            JOIN usuarios u ON u.id=re.representante_id AND u.activo=1
            JOIN usuario_roles ur ON ur.usuario_id=u.id AND ur.periodo_id IS NULL
            JOIN roles r ON r.id=ur.rol_id AND r.codigo='representante'
            WHERE re.activo=1 AND u.id<>".(int)$actor." $whereSolo";
        $sqlPartes=['todos_estudiantes'=>[$sqlEst],'todos_docentes'=>[$sqlDoc],
            'todos_representantes'=>[$sqlRep],'todos_todos'=>[$sqlEst,$sqlDoc,$sqlRep]];
        $etiquetas=['todos_estudiantes'=>'Todos los estudiantes',
            'todos_docentes'=>'Todos los docentes','todos_representantes'=>'Todos los representantes',
            'todos_todos'=>'Toda la comunidad educativa (estudiantes, docentes y representantes)'];
        $grupo=$etiquetas[$tipo].' - '.$nombreJornada;
        $sql='SELECT id,cedula,apellidos,nombres,correo FROM ('.implode(' UNION ',$sqlPartes[$tipo]).
            ') lista ORDER BY apellidos,nombres,id LIMIT 6000';
    } elseif(in_array($tipo,['docentes_jornada','subadmins_jornada'],true)){

        if($jid<=0)throw new DomainException('Selecciona una jornada especifica.');
        $nombreJornada='';
        foreach(sgaNotiJornadas($pid,$ctx) as $j){if((int)$j['id']===$jid){$nombreJornada=$j['nombre'];break;}}
        if($nombreJornada==='')throw new DomainException('Jornada no habilitada.');
        if($tipo==='docentes_jornada'){
            $grupo='Docentes de la jornada '.$nombreJornada;
            $sql="SELECT DISTINCT u.id,u.cedula,u.apellidos,u.nombres,u.correo
                FROM ofertas_academicas o
                JOIN aulas_periodo ap ON ap.id=o.aula_periodo_id AND ap.activo=1 AND ap.periodo_id=$p
                JOIN aulas a ON a.id=ap.aula_id AND a.activo=1 AND a.jornada_id=$jid
                JOIN usuarios u ON u.id=o.docente_id AND u.activo=1
                JOIN usuario_roles ur ON ur.usuario_id=u.id AND ur.periodo_id=$p
                JOIN roles r ON r.id=ur.rol_id AND r.codigo='docente'
                WHERE o.activo=1 AND u.id<>".(int)$actor." $whereSolo ORDER BY u.apellidos,u.nombres,u.id LIMIT 6000";
        }else{
            $grupo='Subadministradores de la jornada '.$nombreJornada;
            $sql="SELECT DISTINCT u.id,u.cedula,u.apellidos,u.nombres,u.correo
                FROM subadministrador_jornadas sj
                JOIN usuarios u ON u.id=sj.usuario_id AND u.activo=1
                JOIN usuario_roles ur ON ur.usuario_id=u.id AND ur.periodo_id IS NULL
                JOIN roles r ON r.id=ur.rol_id AND r.codigo='subadmin'
                WHERE sj.periodo_id=$p AND sj.jornada_id=$jid AND u.id<>".(int)$actor." $whereSolo
                ORDER BY u.apellidos,u.nombres,u.id LIMIT 6000";
        }
    } elseif(in_array($tipo,['estudiantes_asignatura','estudiantes_aula'],true)){
        $grupo='Estudiantes de '.$aulaNombre.($doc?' - '.$datosOferta['asignatura']:'').' ('.$nombreJornada.')';
        $sql="SELECT DISTINCT u.id,u.cedula,u.apellidos,u.nombres,u.correo FROM matriculas m
            JOIN usuarios u ON u.id=m.estudiante_id AND u.activo=1
            WHERE m.aula_periodo_id=$apId AND m.estado='activo' $whereSolo
            ORDER BY u.apellidos,u.nombres,u.id LIMIT 6000";
    } elseif(in_array($tipo,['familias_asignatura','familias_aula'],true)){
        $grupo='Representantes de '.$aulaNombre.($doc?' - '.$datosOferta['asignatura']:'').' ('.$nombreJornada.')';
        $sql="SELECT DISTINCT u.id,u.cedula,u.apellidos,u.nombres,u.correo FROM sga_representantes_estudiantes re
            JOIN matriculas m ON m.estudiante_id=re.estudiante_id AND m.estado='activo' AND m.aula_periodo_id=$apId
            JOIN usuarios u ON u.id=re.representante_id AND u.activo=1
            WHERE re.activo=1 $whereSolo ORDER BY u.apellidos,u.nombres,u.id LIMIT 6000";
    } else { // docentes_aula, solo administracion
        $grupo='Docentes de '.$aulaNombre.' ('.$nombreJornada.')';
        $sql="SELECT DISTINCT u.id,u.cedula,u.apellidos,u.nombres,u.correo FROM ofertas_academicas o
            JOIN usuarios u ON u.id=o.docente_id AND u.activo=1
            JOIN usuario_roles ur ON ur.usuario_id=u.id AND ur.periodo_id=$p
            JOIN roles r ON r.id=ur.rol_id AND r.codigo='docente'
            WHERE o.aula_periodo_id=$apId AND o.activo=1 $whereSolo
            ORDER BY u.apellidos,u.nombres,u.id LIMIT 6000";
    }
    $res=$conexion->query($sql);
    if(!$res)throw new RuntimeException('No se pudo resolver el grupo destinatario.');
    $filasGrupo=$res->fetch_all(MYSQLI_ASSOC);
    if(count($filasGrupo)>=6000)throw new DomainException('El grupo es demasiado grande; divide el envio en aulas.');
    $personas=sgaNotiUnicosPorCorreo($filasGrupo);
    if(count($personas)>5000)throw new DomainException('El grupo supera 5.000 direcciones. Divide el envio por jornada o categoria.');
    return ['personas'=>$personas,'grupo'=>$grupo,'cargo'=>$firma,
        'aula_periodo_id'=>$apId,'oferta_id'=>$ofId];
}

function sgaNotiTablasInstaladas(): bool {
    global $conexion;
    foreach(['sga_notificaciones_jornadas','sga_notificaciones_jornadas_envios'] as $tabla){
        $r=$conexion->query("SHOW TABLES LIKE '".$tabla."'");
        if(!$r||!$r->num_rows)return false;
    }
    foreach(['modo_remitente','tipo_destino','aula_periodo_id','oferta_id','estudiante_contexto_id','grupo_etiqueta'] as $c){
        $r=$conexion->query("SHOW COLUMNS FROM sga_notificaciones_jornadas LIKE '".$c."'");
        if(!$r||!$r->num_rows)return false;
    }
    return true;
}

function sgaNotiCrear(int $pid,int $actor,array $ctx,int $jid,array $ids,string $asunto,string $mensaje,
                       string $tipo='individual',int $apId=0,int $ofertaId=0,int $hijoId=0): array {
    global $conexion;
    $asunto=trim($asunto);$mensaje=trim($mensaje);
    $lenA=function_exists('mb_strlen')?mb_strlen($asunto,'UTF-8'):strlen($asunto);
    $lenM=function_exists('mb_strlen')?mb_strlen($mensaje,'UTF-8'):strlen($mensaje);
    if($lenA<4||$lenA>150||$lenM<5||$lenM>4000||preg_match('/[\r\n]/',$asunto))
        throw new DomainException('Escribe un asunto de 4 a 150 caracteres (una linea) y un mensaje de 5 a 4.000 caracteres.');
    $destino=sgaNotiResolverGrupo($pid,$actor,$ctx,$jid,$tipo,$apId,$ofertaId,$ids,null,$hijoId);
    $personas=$destino['personas'];$cantidad=count($personas);
    if(!$cantidad)throw new DomainException('No hay destinatarios con correo valido en el grupo seleccionado.');
    $stmt=$conexion->prepare('SELECT COUNT(*) total FROM sga_notificaciones_jornadas WHERE remitente_id=? AND creado_en>DATE_SUB(NOW(),INTERVAL 1 HOUR)');
    $stmt->bind_param('i',$actor);$stmt->execute();$porHora=(int)($stmt->get_result()->fetch_assoc()['total']??0);$stmt->close();
    $maxHora=($ctx['modo']==='representante')?3:10;
    if($porHora>=$maxHora)throw new DomainException('Limite de '.$maxHora.' notificaciones por hora alcanzado.');
    $stmt=$conexion->prepare('SELECT COUNT(*) total FROM sga_notificaciones_jornadas_envios e JOIN sga_notificaciones_jornadas n ON n.id=e.notificacion_id WHERE n.remitente_id=? AND n.creado_en>DATE_SUB(NOW(),INTERVAL 1 DAY)');
    $stmt->bind_param('i',$actor);$stmt->execute();$porDia=(int)($stmt->get_result()->fetch_assoc()['total']??0);$stmt->close();
    $maxDia=($ctx['modo']==='representante')?30:5000;
    if($porDia+$cantidad>$maxDia)throw new DomainException('Limite de '.$maxDia.' correos en 24 horas.');
    $modo=(string)$ctx['modo'];$grupo=(string)$destino['grupo'];$aulaDB=$destino['aula_periodo_id'];$ofertaDB=$destino['oferta_id'];
    $hijoDB=$modo==='representante'?$hijoId:null;
    $conexion->begin_transaction();
    try{
        $stmt=$conexion->prepare('INSERT INTO sga_notificaciones_jornadas
          (periodo_id,remitente_id,jornada_id,asunto,mensaje,modo_remitente,tipo_destino,aula_periodo_id,oferta_id,estudiante_contexto_id,grupo_etiqueta)
          VALUES(?,?,?,?,?,?,?,?,?,?,?)');
        if(!$stmt)throw new RuntimeException('No se pudo registrar la notificacion.');
        $stmt->bind_param('iiissssiiis',$pid,$actor,$jid,$asunto,$mensaje,$modo,$tipo,$aulaDB,$ofertaDB,$hijoDB,$grupo);
        $stmt->execute();$id=(int)$conexion->insert_id;$stmt->close();
        $stmt=$conexion->prepare('INSERT INTO sga_notificaciones_jornadas_envios (notificacion_id,destinatario_id,correo_destino) VALUES(?,?,?)');
        if(!$stmt)throw new RuntimeException('No se pudo crear la cola.');
        foreach($personas as $p){$idU=(int)$p['id'];$email=(string)$p['correo'];$stmt->bind_param('iis',$id,$idU,$email);$stmt->execute();}
        $stmt->close();
        if(!$conexion->commit())throw new RuntimeException('No fue posible confirmar la notificacion.');
        try {
            registrarAuditoria('CREATE','Notificaciones','notificacion_jornada',$id,
              'Notificacion institucional registrada para el grupo indicado.',null,null,
              ['periodo_id'=>$pid,'grupo'=>$grupo,'tipo'=>$tipo,'cantidad'=>$cantidad],
              'exito',null,null,'advertencia');
        } catch (Throwable $auditoriaError) {
            error_log('[SGA] Registro auditoria notificacion: '.get_class($auditoriaError));
        }
        return ['id'=>$id,'total'=>$cantidad,'grupo'=>$grupo];
    }catch(Throwable $e){$conexion->rollback();throw $e;}
}

/** Cola de envios con revalidacion del rol, asignatura, jornada y destinatario. */
function sgaNotiEnviarPendientes(int $limite=10,?int $notificacionId=null,?int $soloRemitente=null): array {
    global $conexion;
    require_once __DIR__.'/sga_smtp.php';
    $limite=max(1,min(30,$limite));$estado=['enviados'=>0,'errores'=>0,'omitidos'=>0];
    $conexion->query("UPDATE sga_notificaciones_jornadas_envios SET estado='pendiente' WHERE estado='enviando' AND actualizado_en<DATE_SUB(NOW(),INTERVAL 10 MINUTE) AND intentos<3");
    $conexion->query("UPDATE sga_notificaciones_jornadas_envios SET estado='error',ultimo_error='Intentos agotados' WHERE estado='enviando' AND actualizado_en<DATE_SUB(NOW(),INTERVAL 10 MINUTE) AND intentos>=3");
    $where='';if($notificacionId!==null)$where.=' AND n.id='.(int)$notificacionId;
    if($soloRemitente!==null)$where.=' AND n.remitente_id='.(int)$soloRemitente;
    $sql="SELECT e.id,e.destinatario_id,e.correo_destino,n.periodo_id,n.remitente_id,n.jornada_id,n.asunto,n.mensaje,n.creado_en,
        n.modo_remitente,n.tipo_destino,n.aula_periodo_id,n.oferta_id,n.estudiante_contexto_id,n.grupo_etiqueta,
        destino.nombres,destino.apellidos,autor.nombres autor_nombres,autor.apellidos autor_apellidos
        FROM sga_notificaciones_jornadas_envios e
        JOIN sga_notificaciones_jornadas n ON n.id=e.notificacion_id
        JOIN usuarios destino ON destino.id=e.destinatario_id
        JOIN usuarios autor ON autor.id=n.remitente_id
        WHERE e.estado IN ('pendiente','error') AND e.intentos<3
        AND (e.estado='pendiente' OR e.actualizado_en<DATE_SUB(NOW(),INTERVAL 5 MINUTE)) $where
        ORDER BY e.id LIMIT $limite";
    $r=$conexion->query($sql);if(!$r)throw new RuntimeException('No se pudo consultar la cola de notificaciones.');
    $pendientes=$r->fetch_all(MYSQLI_ASSOC);
    $config=require __DIR__.'/../config/recuperacion.php';$smtp=$config['smtp']??[];
    foreach($pendientes as $fila){
        $id=(int)$fila['id'];
        $stmt=$conexion->prepare("UPDATE sga_notificaciones_jornadas_envios SET estado='enviando',intentos=intentos+1 WHERE id=? AND estado IN ('pendiente','error') AND intentos<3");
        $stmt->bind_param('i',$id);$stmt->execute();$tomado=$stmt->affected_rows===1;$stmt->close();
        if(!$tomado)continue;
        try{
            $pid=(int)$fila['periodo_id'];$actor=(int)$fila['remitente_id'];$jid=(int)$fila['jornada_id'];
            $stmt=$conexion->prepare("SELECT 1 FROM periodos_academicos WHERE id=? AND estado='activo' LIMIT 1");
            $stmt->bind_param('i',$pid);$stmt->execute();$activo=(bool)$stmt->get_result()->fetch_row();$stmt->close();
            $ctx=$activo?sgaNotiContextoActor($pid,$actor,(string)$fila['modo_remitente']):null;
            if(!$ctx)throw new DomainException('El remitente ya no dispone de permisos.');
            $uid=(int)$fila['destinatario_id'];
            $grupo=sgaNotiResolverGrupo($pid,$actor,$ctx,$jid,(string)$fila['tipo_destino'],
                (int)$fila['aula_periodo_id'],(int)$fila['oferta_id'],[$uid],$uid,(int)$fila['estudiante_contexto_id']);
            $personas=$grupo['personas'];
            if(count($personas)!==1||(int)$personas[0]['id']!==$uid||
               strcasecmp((string)$personas[0]['correo'],(string)$fila['correo_destino'])!==0)
                throw new DomainException('El destinatario ya no pertenece al grupo o su correo cambio.');
            $nombre=trim($fila['apellidos'].' '.$fila['nombres']);
            $remitente=trim($fila['autor_apellidos'].' '.$fila['autor_nombres']);
            $cargo=(string)$grupo['cargo'];
            $contacto='';
            if(($ctx['modo']??'')==='representante'){
                $contactoCorreo='';
                // Cron no mantiene la sesion del remitente: consultar el correo del actor real.
                $cs=$conexion->prepare('SELECT correo FROM usuarios WHERE id=? AND activo=1 LIMIT 1');
                if($cs){$cs->bind_param('i',$actor);$cs->execute();$c=$cs->get_result()->fetch_assoc();$cs->close();
                  $contactoCorreo=trim((string)($c['correo']??''));}
                if(filter_var($contactoCorreo,FILTER_VALIDATE_EMAIL))$contacto="Correo de contacto del representante: ".$contactoCorreo."\n";
            }
            $contenido="Estimado/a ".$nombre.":\n\n".$fila['mensaje']."\n\n".
                "Grupo destinatario: ".$fila['grupo_etiqueta']."\n\n".
                "Atentamente,\n".$remitente."\n".$cargo."\n".$contacto."\n".
                "Periodo academico: ".$pid."\nFecha: ".$fila['creado_en']."\n\n".
                "Sistema de Gestion Academica UNEDID\n".
                rtrim((string)($config['app_url']??'https://sgaunedid.aulaprofenathaly.com'),'/')."\n\n".
                "Mensaje institucional automatico. No responda a este correo.";
            (new SgaSmtp((int)($smtp['timeout']??10)))->send($smtp,(string)$fila['correo_destino'],
                'SGA UNEDID | '.$fila['asunto'],$contenido);
            $stmt=$conexion->prepare("UPDATE sga_notificaciones_jornadas_envios SET estado='enviado',enviado_en=NOW(),ultimo_error=NULL WHERE id=?");
            $stmt->bind_param('i',$id);$stmt->execute();$stmt->close();$estado['enviados']++;
        }catch(DomainException $e){
            $stmt=$conexion->prepare("UPDATE sga_notificaciones_jornadas_envios SET estado='omitido',ultimo_error='Permisos o datos del grupo no vigentes' WHERE id=?");
            $stmt->bind_param('i',$id);$stmt->execute();$stmt->close();$estado['omitidos']++;
        }catch(Throwable $e){
            error_log('[SGA] Envio notificacion '.$id.' fallo ('.get_class($e).')');
            $stmt=$conexion->prepare("UPDATE sga_notificaciones_jornadas_envios SET estado='error',ultimo_error='Error de entrega o proceso SMTP' WHERE id=?");
            $stmt->bind_param('i',$id);$stmt->execute();$stmt->close();$estado['errores']++;
        }
    }
    return $estado;
}
