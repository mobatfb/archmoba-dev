<?php
/** SGA UNEDID: las asignaturas comparten el catalogo y se habilitan por jornadas. */
require_once __DIR__.'/areas_jornadas.php';

function sgaAsignaturasJornadasInstaladas(mysqli $db): bool {
    $q=$db->query("SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='asignaturas' AND COLUMN_NAME='jornadas_ids' LIMIT 1");
    if (!$q) return false;
    $ok=(bool)$q->fetch_row(); $q->free(); return $ok;
}
function sgaAsignaturasAreaVisible(array $area): bool {
    if (esSuperadmin()) return true;
    $pid=(int)(periodoActivo()['id']??0);
    if (!$pid) return false;
    return (bool)array_intersect(sgaAreasJornadasDecodificar((string)($area['jornadas_ids']??'')),jornadasEnVista($pid));
}
function sgaAsignaturasExigirArea(mysqli $db,int $areaId,bool $activa=true): array {
    if (!sgaAreasJornadasInstaladas($db)) throw new RuntimeException('Instala primero la migracion de jornadas en Areas.');
    $s=$db->prepare('SELECT id,nombre,activo,jornadas_ids FROM areas WHERE id=? AND archivado_en IS NULL LIMIT 1');
    $s->bind_param('i',$areaId); $s->execute(); $a=$s->get_result()->fetch_assoc(); $s->close();
    if (!$a || ($activa && (int)$a['activo']!==1)) throw new RuntimeException('Area inactiva o inexistente.');
    if (!sgaAsignaturasAreaVisible($a)) throw new RuntimeException('El area no esta habilitada para tu jornada.');
    return $a;
}
/** Jornadas asignables al area por el perfil actual. */
function sgaAsignaturasJornadasOpciones(array $area,array $opciones): array {
    $ids=sgaAreasJornadasDecodificar((string)($area['jornadas_ids']??''));
    return array_values(array_filter($opciones,static fn($j)=>in_array((int)$j['id'],$ids,true)));
}
function sgaAsignaturasValidarJornadas($valores,array $area,array $opciones): array {
    return sgaAreasJornadasValidarSeleccion($valores,sgaAsignaturasJornadasOpciones($area,$opciones));
}
function sgaAsignaturasJornadasGuardar(mysqli $db,int $asigId,array $ids): void {
    if (!sgaAsignaturasJornadasInstaladas($db)) throw new RuntimeException('Instala la migracion de jornadas en Asignaturas.');
    $ids=array_values(array_unique(array_map('intval',$ids)));
    if (!$asigId || !$ids || min($ids)<=0) throw new RuntimeException('Selecciona al menos una jornada de la asignatura.');
    $valor=implode(',',$ids);
    if (strlen($valor)>512) throw new RuntimeException('Se excedio el limite de jornadas de la asignatura.');
    $s=$db->prepare('UPDATE asignaturas SET jornadas_ids=? WHERE id=? AND archivado_en IS NULL');
    $s->bind_param('si',$valor,$asigId);$s->execute();$s->close();
}
/** Cualquier uso academico de una materia en la jornada evita deshabilitarla sin afectar historiales. */
function sgaAsignaturasEnUsoJornada(mysqli $db,int $asigId,int $jornadaId): bool {
    $q=$db->prepare('SELECT 1 FROM aulas_periodo ap JOIN aulas au ON au.id=ap.aula_id WHERE au.jornada_id=? AND (EXISTS(SELECT 1 FROM aula_asignaturas_seleccionadas t WHERE t.aula_periodo_id=ap.id AND t.asignatura_id=? AND t.seleccionada=1) OR EXISTS(SELECT 1 FROM ofertas_academicas o WHERE o.aula_periodo_id=ap.id AND o.asignatura_id=? AND o.activo=1)) LIMIT 1');
    $q->bind_param('iii',$jornadaId,$asigId,$asigId);$q->execute();$ok=(bool)$q->get_result()->fetch_row();$q->close();return $ok;
}
function sgaAsignaturasExigirSinUsoJornadasRetiradas(mysqli $db,int $id,array $anteriores,array $nuevas): void {
    foreach(array_diff($anteriores,$nuevas) as $jid) {
        if (sgaAsignaturasEnUsoJornada($db,$id,(int)$jid))
            throw new RuntimeException('No puedes quitar esta jornada: la asignatura ya esta seleccionada o asignada a un docente en alguna de sus aulas.');
    }
}
/** Solo el administrador principal puede editar un registro compartido con otras jornadas. */
function sgaAsignaturasExigirRegistro(mysqli $db,int $asigId): void {
    if (!sgaAsignaturasJornadasInstaladas($db)) throw new RuntimeException('Falta la migracion de jornadas en Asignaturas.');
    $s=$db->prepare('SELECT s.jornadas_ids,a.jornadas_ids area_jornadas FROM asignaturas s JOIN areas a ON a.id=s.area_id WHERE s.id=? AND s.archivado_en IS NULL AND a.archivado_en IS NULL LIMIT 1');
    $s->bind_param('i',$asigId);$s->execute();$r=$s->get_result()->fetch_assoc();$s->close();
    if (!$r) throw new RuntimeException('Asignatura no encontrada.');
    if (esSuperadmin()) return;
    $permitidas=jornadasPermitidasPeriodo((int)(periodoActivo()['id']??0));
    $ids=sgaAreasJornadasDecodificar($r['jornadas_ids']);
    if (!$ids || array_diff($ids,$permitidas)) throw new RuntimeException('La asignatura es compartida o pertenece a otra jornada. Puedes habilitarla para la tuya, pero solo el Administrador puede cambiar su configuracion global.');
    if (array_diff($ids,sgaAreasJornadasDecodificar($r['area_jornadas']))) throw new RuntimeException('El area no esta habilitada para esta asignatura.');
}
/** Permite al Subadministrador anexar SU jornada sin tocar las ajenas. */
function sgaAsignaturasHabilitarPropia(mysqli $db,int $asigId,int $jornadaId): array {
    if (!esSubadmin() || esSuperadmin() || $jornadaId<=0 || !in_array($jornadaId,jornadasEnVista((int)(periodoActivo()['id']??0)),true))
        throw new RuntimeException('La jornada no esta autorizada para tu perfil.');
    $s=$db->prepare('SELECT s.id,s.activo,s.jornadas_ids,a.activo area_activa,a.jornadas_ids area_jornadas FROM asignaturas s JOIN areas a ON a.id=s.area_id WHERE s.id=? AND s.archivado_en IS NULL AND a.archivado_en IS NULL FOR UPDATE');
    $s->bind_param('i',$asigId);$s->execute();$r=$s->get_result()->fetch_assoc();$s->close();
    if (!$r || !(int)$r['activo'] || !(int)$r['area_activa']) throw new RuntimeException('La asignatura o su area no estan activas.');
    if (!in_array($jornadaId,sgaAreasJornadasDecodificar($r['area_jornadas']),true)) throw new RuntimeException('Primero habilita el area para tu jornada.');
    $antes=sgaAreasJornadasDecodificar($r['jornadas_ids']);
    if (!in_array($jornadaId,$antes,true)) sgaAsignaturasJornadasGuardar($db,$asigId,array_merge($antes,[$jornadaId]));
    return ['antes'=>$antes,'despues'=>array_values(array_unique(array_merge($antes,[$jornadaId])))];
}
function sgaAsignaturasHabilitadaEnJornada(mysqli $db,int $id,int $jornadaId): bool {
    if ($id<1 || $jornadaId<1 || !sgaAsignaturasJornadasInstaladas($db)) return false;
    $q=$db->prepare('SELECT 1 FROM asignaturas s JOIN areas a ON a.id=s.area_id WHERE s.id=? AND s.activo=1 AND a.activo=1 AND s.archivado_en IS NULL AND a.archivado_en IS NULL AND FIND_IN_SET(?,s.jornadas_ids)>0 AND FIND_IN_SET(?,a.jornadas_ids)>0 LIMIT 1');
    $q->bind_param('iii',$id,$jornadaId,$jornadaId);$q->execute();$ok=(bool)$q->get_result()->fetch_row();$q->close();return $ok;
}
