<?php
/**
 * Autorizacion multi-jornada por usuario y periodo academico.
 * Las verificaciones se hacen en el servidor, con acceso denegado por defecto.
 * Un subadministrador global NO recibe permisos sobre un periodo sin asignaciones explicitas.
 */
function jornadasPermitidasPeriodo(int $periodoId): array {
    global $conexion;
    if ($periodoId <= 0 || !esSubadmin()) return [];
    $uid=(int)($_SESSION['usuario_id']??0);
    $s=$conexion->prepare('SELECT sj.jornada_id FROM subadministrador_jornadas sj JOIN jornadas j ON j.id=sj.jornada_id AND j.activo=1 WHERE sj.usuario_id=? AND sj.periodo_id=? ORDER BY j.orden,j.id');
    $s->bind_param('ii',$uid,$periodoId);$s->execute();
    $ids=array_map('intval',array_column($s->get_result()->fetch_all(MYSQLI_ASSOC),'jornada_id'));
    $s->close();return $ids;
}
/** El selector solo filtra pantallas: nunca concede acceso a una jornada nueva. */
function jornadasEnVista(int $periodoId): array {
    $ids=jornadasPermitidasPeriodo($periodoId);
    $elegida=(int)($_SESSION['jornada_vista_periodos'][$periodoId]??0);
    if($elegida>0 && in_array($elegida,$ids,true))return [$elegida];
    return $ids;
}
/** Periodo inicial del subadministrador: si el activo no esta autorizado,
 * abre el ultimo periodo al que si tiene permisos, sin aceptar un parametro falso. */
function periodoInicialSubadmin(int $preferido,int $solicitadoExpresamente): int {
    global $conexion;
    if(!esSubadmin() || esSuperadmin())return $preferido;
    if($solicitadoExpresamente) return $preferido; // El acceso solicitado se validara aparte.
    if(puedeAccederPeriodo($preferido))return $preferido;
    $uid=(int)($_SESSION['usuario_id']??0);
    $s=$conexion->prepare('SELECT p.id FROM periodos_academicos p JOIN subadministrador_jornadas sj ON sj.periodo_id=p.id JOIN jornadas j ON j.id=sj.jornada_id AND j.activo=1 WHERE sj.usuario_id=? GROUP BY p.id ORDER BY p.anio_inicio DESC,p.id DESC LIMIT 1');
    $s->bind_param('i',$uid);$s->execute();$r=$s->get_result()->fetch_assoc();$s->close();
    return (int)($r['id']??0);
}
function puedeAccederPeriodo(int $periodoId): bool {
    if ($periodoId<=0 || !esAdminAcademico()) return false;
    return esSuperadmin() || count(jornadasPermitidasPeriodo($periodoId))>0;
}
function exigirAccesoPeriodo(int $periodoId): void {
    exigirAdminAcademico();
    if (!puedeAccederPeriodo($periodoId)) {http_response_code(403);die('No tienes jornadas autorizadas para el periodo académico solicitado.');}
}
function puedeAccederJornada(int $jornadaId,int $periodoId): bool {
    if($jornadaId<=0 || $periodoId<=0 || !esAdminAcademico()) return false;
    return esSuperadmin() || in_array($jornadaId,jornadasPermitidasPeriodo($periodoId),true);
}
function exigirAccesoJornada(int $jornadaId,int $periodoId): void {
    exigirAdminAcademico();
    if(!puedeAccederJornada($jornadaId,$periodoId)){http_response_code(403);die('Jornada no autorizada para este periodo.');}
}
/** Para filtros de consultas SELECT internas: alias SQL solo puede ser uno conocido. */
function filtroJornadasSQL(int $periodoId,string $alias='a'): string {
    if(!in_array($alias,['a','au'],true)) throw new InvalidArgumentException('Alias de tabla no válido.');
    if(!esSubadmin() || esSuperadmin()) return '';
    $ids=jornadasEnVista($periodoId);
    return $ids?' AND '.$alias.'.jornada_id IN ('.implode(',',$ids).')':' AND 1=0';
}
function puedeAccederAula(int $aulaId,int $periodoId): bool {
    global $conexion;
    if($aulaId<=0 || !puedeAccederPeriodo($periodoId)) return false;
    if(esSuperadmin()) return true;
    $s=$conexion->prepare('SELECT jornada_id FROM aulas WHERE id=?');
    $s->bind_param('i',$aulaId);$s->execute();$row=$s->get_result()->fetch_assoc();$s->close();
    return $row && puedeAccederJornada((int)$row['jornada_id'],$periodoId);
}
function exigirAccesoAula(int $aulaId,int $periodoId): void {
    if(!puedeAccederAula($aulaId,$periodoId)){http_response_code(403);die('Acceso denegado al aula o periodo.');}
}
function puedeAccederAulaPeriodo(int $aulaPeriodoId): bool {
    global $conexion;
    if($aulaPeriodoId<=0 || !esAdminAcademico()) return false;
    $s=$conexion->prepare('SELECT ap.periodo_id,a.jornada_id FROM aulas_periodo ap JOIN aulas a ON a.id=ap.aula_id WHERE ap.id=? LIMIT 1');
    $s->bind_param('i',$aulaPeriodoId);$s->execute();$row=$s->get_result()->fetch_assoc();$s->close();
    return $row && (esSuperadmin() || puedeAccederJornada((int)$row['jornada_id'],(int)$row['periodo_id']));
}
function exigirAccesoAulaPeriodo(int $aulaPeriodoId): void {
    exigirAdminAcademico();
    if(!puedeAccederAulaPeriodo($aulaPeriodoId)){http_response_code(403);die('No tienes acceso a esta aula en el periodo solicitado.');}
}
function puedeAccederMatricula(int $matriculaId): bool {
    global $conexion;
    if($matriculaId<=0 || !esAdminAcademico()) return false;
    $s=$conexion->prepare('SELECT aula_periodo_id FROM matriculas WHERE id=? LIMIT 1');
    $s->bind_param('i',$matriculaId);$s->execute();$row=$s->get_result()->fetch_assoc();$s->close();
    return $row && puedeAccederAulaPeriodo((int)$row['aula_periodo_id']);
}
function exigirAccesoMatricula(int $matriculaId): void {
    exigirAdminAcademico();
    if(!puedeAccederMatricula($matriculaId)){http_response_code(403);die('No tienes acceso a la matrícula solicitada.');}
}
function puedeAccederOfertaSubadmin(int $ofertaId): bool {
    global $conexion;
    if($ofertaId<=0 || !esSubadmin())return false;
    $s=$conexion->prepare('SELECT ap.periodo_id,a.jornada_id FROM ofertas_academicas o JOIN aulas_periodo ap ON ap.id=o.aula_periodo_id JOIN aulas a ON a.id=ap.aula_id WHERE o.id=? LIMIT 1');
    $s->bind_param('i',$ofertaId);$s->execute();$row=$s->get_result()->fetch_assoc();$s->close();
    return $row && puedeAccederJornada((int)$row['jornada_id'],(int)$row['periodo_id']);
}
/**
 * Condicion de VISIBILIDAD por relacion con las jornadas indicadas en el periodo.
 * Una persona puede tener roles administrativos Y academicos o familiares.
 * La presencia de superadmin/subadmin NO la oculta del directorio por su
 * actividad como docente, representante o subadministrador de la jornada.
 *
 * IMPORTANTE: esta funcion sirve SOLO para SELECT. Nunca concede permiso
 * para modificar el usuario: las escrituras deben seguir utilizando
 * puedeGestionarUsuarioJornada(), que protege cuentas administrativas.
 */
function sgaUsuarioVisibleEnJornadasSQL(int $periodoId,array $jornadas,string $alias='u'): string {
    if($alias!=='u')throw new InvalidArgumentException('Alias de usuario inválido.');
    $ids=array_values(array_unique(array_filter(array_map('intval',$jornadas),static fn($v)=>$v>0)));
    if($periodoId<=0 || !$ids)return '1=0';
    $p=(int)$periodoId;$in=implode(',',$ids);
    return "(EXISTS (SELECT 1 FROM usuarios_jornadas_gestion uj WHERE uj.usuario_id=u.id AND uj.periodo_id=$p AND uj.jornada_id IN ($in))".
        " OR EXISTS (SELECT 1 FROM matriculas m JOIN aulas_periodo ap ON ap.id=m.aula_periodo_id AND ap.activo=1 JOIN aulas a ON a.id=ap.aula_id WHERE m.estudiante_id=u.id AND m.estado='activo' AND ap.periodo_id=$p AND a.jornada_id IN ($in))".
        " OR EXISTS (SELECT 1 FROM ofertas_academicas o JOIN aulas_periodo ap ON ap.id=o.aula_periodo_id AND ap.activo=1 JOIN aulas a ON a.id=ap.aula_id WHERE o.docente_id=u.id AND o.activo=1 AND ap.periodo_id=$p AND a.jornada_id IN ($in))".
        " OR EXISTS (SELECT 1 FROM sga_representantes_estudiantes re JOIN matriculas m ON m.estudiante_id=re.estudiante_id AND m.estado='activo' JOIN aulas_periodo ap ON ap.id=m.aula_periodo_id AND ap.activo=1 JOIN aulas a ON a.id=ap.aula_id WHERE re.representante_id=u.id AND re.activo=1 AND ap.periodo_id=$p AND a.jornada_id IN ($in))".
        " OR EXISTS (SELECT 1 FROM subadministrador_jornadas sj JOIN usuario_roles ur ON ur.usuario_id=sj.usuario_id AND ur.periodo_id IS NULL JOIN roles r ON r.id=ur.rol_id AND r.codigo='subadmin' WHERE sj.usuario_id=u.id AND sj.periodo_id=$p AND sj.jornada_id IN ($in)))";
}
/** Filtra solo las consultas del Subadministrador y respeta su jornada en vista. */
function filtroUsuariosJornadasSQL(int $periodoId,string $alias='u'): string {
    if(esSuperadmin())return '';
    if(!esSubadmin())return ' AND 1=0';
    $ids=jornadasEnVista($periodoId);
    return ' AND '.sgaUsuarioVisibleEnJornadasSQL($periodoId,$ids,$alias);
}
/** Modificar un rol individual NO puede afectar a personas con otras jornadas en ese periodo. */
function puedeGestionarUsuarioJornada(int $usuarioId,int $periodoId): bool {
    global $conexion;
    if($usuarioId<=0 || !puedeAccederPeriodo($periodoId))return false;
    if(esSuperadmin())return true;
    $ids=jornadasPermitidasPeriodo($periodoId);
    if(!$ids)return false;
    $in=implode(',',$ids);
    $s=$conexion->prepare("SELECT
       (SELECT COUNT(*) FROM usuarios_jornadas_gestion uj WHERE uj.usuario_id=? AND uj.periodo_id=? AND uj.jornada_id IN ($in))+
       (SELECT COUNT(*) FROM matriculas m JOIN aulas_periodo ap ON ap.id=m.aula_periodo_id JOIN aulas a ON a.id=ap.aula_id WHERE m.estudiante_id=? AND ap.periodo_id=? AND a.jornada_id IN ($in))+
       (SELECT COUNT(*) FROM ofertas_academicas o JOIN aulas_periodo ap ON ap.id=o.aula_periodo_id JOIN aulas a ON a.id=ap.aula_id WHERE o.docente_id=? AND ap.periodo_id=? AND a.jornada_id IN ($in)) AS propias,
       (SELECT COUNT(*) FROM matriculas m JOIN aulas_periodo ap ON ap.id=m.aula_periodo_id JOIN aulas a ON a.id=ap.aula_id WHERE m.estudiante_id=? AND ap.periodo_id=? AND (a.jornada_id IS NULL OR a.jornada_id NOT IN ($in)))+
       (SELECT COUNT(*) FROM ofertas_academicas o JOIN aulas_periodo ap ON ap.id=o.aula_periodo_id JOIN aulas a ON a.id=ap.aula_id WHERE o.docente_id=? AND ap.periodo_id=? AND (a.jornada_id IS NULL OR a.jornada_id NOT IN ($in)))+
       (SELECT COUNT(*) FROM usuarios_jornadas_gestion uj WHERE uj.usuario_id=? AND uj.periodo_id=? AND uj.jornada_id NOT IN ($in)) AS ajenas");
    $s->bind_param('iiiiiiiiiiii',$usuarioId,$periodoId,$usuarioId,$periodoId,$usuarioId,$periodoId,$usuarioId,$periodoId,$usuarioId,$periodoId,$usuarioId,$periodoId);
    $s->execute();$row=$s->get_result()->fetch_assoc();$s->close();
    if(!$row || (int)$row['propias']<1 || (int)$row['ajenas']>0)return false;
    $s=$conexion->prepare("SELECT 1 FROM usuario_roles ur JOIN roles r ON r.id=ur.rol_id WHERE ur.usuario_id=? AND r.codigo IN ('superadmin','subadmin') LIMIT 1");
    $s->bind_param('i',$usuarioId);$s->execute();$global=(bool)$s->get_result()->fetch_row();$s->close();
    return !$global;
}
function vincularUsuarioJornada(int $usuarioId,int $periodoId,int $jornadaId): void {
    global $conexion;
    exigirAccesoJornada($jornadaId,$periodoId);
    $s=$conexion->prepare('INSERT IGNORE INTO usuarios_jornadas_gestion (usuario_id,periodo_id,jornada_id) VALUES (?,?,?)');
    $s->bind_param('iii',$usuarioId,$periodoId,$jornadaId);
    if(!$s->execute())throw new RuntimeException('No se pudo vincular el usuario a la jornada.');
    $s->close();
}
