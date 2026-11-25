<?php
/** Consolidado institucional de asistencia, calculado exclusivamente con registros guardados. */

function raFechaValida(string $fecha): bool {
    $fecha = trim($fecha);
    $d = DateTimeImmutable::createFromFormat('!Y-m-d', $fecha);
    return $d !== false && $d->format('Y-m-d') === $fecha;
}

function raRangoPeriodo(array $periodo, array $get): array {
    $baseDesde = raFechaValida((string)($periodo['fecha_inicio'] ?? '')) ? (string)$periodo['fecha_inicio'] : '2000-01-01';
    $baseHasta = raFechaValida((string)($periodo['fecha_fin'] ?? '')) ? (string)$periodo['fecha_fin'] : '2099-12-31';
    $desde = isset($get['desde']) && is_string($get['desde']) && trim($get['desde']) !== '' ? trim($get['desde']) : $baseDesde;
    $hasta = isset($get['hasta']) && is_string($get['hasta']) && trim($get['hasta']) !== '' ? trim($get['hasta']) : $baseHasta;
    if (!raFechaValida($desde) || !raFechaValida($hasta) || $desde > $hasta) {
        http_response_code(400);
        die('Rango de fechas inválido. Verifica las fechas Desde y Hasta.');
    }
    return [$desde, $hasta];
}

/**
 * Reporte de asistencia: administradores ven sus jornadas; docentes ven solo
 * aulas con una oferta académica activa asignada y solo del período activo.
 * Esta autorización es independiente de la apariencia de los botones.
 */
function raPuedeConsultarPeriodo(mysqli $conexion, int $periodoId): bool {
    if ($periodoId <= 0) return false;
    if (esAdminAcademico()) return puedeAccederPeriodo($periodoId);
    $activo=periodoActivo();
    if (!$activo || (int)$activo['id'] !== $periodoId || !esDocenteOperativo($periodoId)) return false;
    $uid=(int)($_SESSION['usuario_id']??0);
    $s=$conexion->prepare('SELECT 1 FROM ofertas_academicas o '
        .'JOIN aulas_periodo ap ON ap.id=o.aula_periodo_id '
        .'WHERE ap.periodo_id=? AND ap.activo=1 AND o.docente_id=? AND o.activo=1 LIMIT 1');
    $s->bind_param('ii',$periodoId,$uid);$s->execute();
    $permitido=(bool)$s->get_result()->fetch_row();$s->close();
    return $permitido;
}
function raExigirPeriodo(mysqli $conexion, int $periodoId): void {
    exigirLogin();
    if (!raPuedeConsultarPeriodo($conexion,$periodoId)) {
        http_response_code(403);die('No tienes acceso a este reporte de asistencia en el período solicitado.');
    }
}
function raExigirAulaPeriodo(mysqli $conexion, int $aulaPeriodoId, int $periodoId): void {
    raExigirPeriodo($conexion,$periodoId);
    if ($aulaPeriodoId <= 0) {http_response_code(403);die('Paralelo no autorizado.');}
    // Confirmar siempre que el aula corresponde al período solicitado.
    $s=$conexion->prepare('SELECT 1 FROM aulas_periodo ap WHERE ap.id=? AND ap.periodo_id=? AND ap.activo=1 LIMIT 1');
    $s->bind_param('ii',$aulaPeriodoId,$periodoId);$s->execute();
    $existe=(bool)$s->get_result()->fetch_row();$s->close();
    if (!$existe){http_response_code(403);die('El aula no pertenece al período consultado.');}
    if (esAdminAcademico()) { exigirAccesoAulaPeriodo($aulaPeriodoId); return; }
    $uid=(int)($_SESSION['usuario_id']??0);
    $s=$conexion->prepare('SELECT 1 FROM ofertas_academicas o '
        .'WHERE o.aula_periodo_id=? AND o.docente_id=? AND o.activo=1 LIMIT 1');
    $s->bind_param('ii',$aulaPeriodoId,$uid);$s->execute();
    $permitido=(bool)$s->get_result()->fetch_row();$s->close();
    if (!$permitido){http_response_code(403);die('El paralelo no está asignado a tu usuario.');}
}

function raListaPeriodos(mysqli $conexion): array {
    if (!esAdminAcademico()) {
        $activo=periodoActivo();
        return $activo && raPuedeConsultarPeriodo($conexion,(int)$activo['id']) ? [$activo] : [];
    }
    return $conexion->query('SELECT p.* FROM periodos_academicos p ORDER BY p.anio_inicio DESC,p.id DESC')->fetch_all(MYSQLI_ASSOC);
}

function raListaAulas(mysqli $conexion, int $periodoId): array {
    raExigirPeriodo($conexion,$periodoId);
    $docente=!esAdminAcademico();
    $sql = 'SELECT ap.id aula_periodo_id, ap.periodo_id, a.id aula_id, a.codigo, a.nivel, a.nombre, a.paralelo, j.nombre jornada '
        .'FROM aulas_periodo ap JOIN aulas a ON a.id=ap.aula_id '
        .'LEFT JOIN jornadas j ON j.id=a.jornada_id '
        .'WHERE ap.periodo_id=? AND ap.activo=1'.filtroJornadasSQL($periodoId, 'a');
    if ($docente) $sql.=' AND EXISTS(SELECT 1 FROM ofertas_academicas o WHERE o.aula_periodo_id=ap.id AND o.docente_id=? AND o.activo=1)';
    $sql.=' ORDER BY a.id ASC';
    $s=$conexion->prepare($sql);
    if ($docente) {$uid=(int)$_SESSION['usuario_id'];$s->bind_param('ii',$periodoId,$uid);}
    else $s->bind_param('i',$periodoId);
    $s->execute(); $rows=$s->get_result()->fetch_all(MYSQLI_ASSOC); $s->close();
    return $rows;
}

function raPeriodo(mysqli $conexion, int $periodoId): ?array {
    $s=$conexion->prepare('SELECT * FROM periodos_academicos WHERE id=? LIMIT 1');
    $s->bind_param('i',$periodoId);$s->execute();$r=$s->get_result()->fetch_assoc()?:null;$s->close();
    return $r;
}

/** Las ausencias sin registro NO se inventan; solo se cuentan estados realmente almacenados. */
function raResumen(array $estados): array {
    $p=(int)($estados['presente']??0);$a=(int)($estados['ausente']??0);
    $t=(int)($estados['atraso']??0);$j=(int)($estados['justificado']??0);
    $registros=$p+$a+$t+$j;
    return ['presente'=>$p,'ausente'=>$a,'atraso'=>$t,'justificado'=>$j,
        'registros'=>$registros,'porcentaje'=>$registros ? round(100*($p+$t)/$registros,2):null];
}

/**
 * Carga todas las ofertas, sesiones reales y registros guardados de un aula
 * dentro del rango indicado. Nunca mezcla matrículas de otro paralelo.
 */
function raCargarAula(mysqli $conexion, array $aula, string $desde, string $hasta): array {
    $apid=(int)$aula['aula_periodo_id'];
    $pid=(int)$aula['periodo_id'];
    raExigirAulaPeriodo($conexion,$apid,$pid);
    $soloDocente=!esAdminAcademico();
    $uid=(int)($_SESSION['usuario_id']??0);
    $s=$conexion->prepare('SELECT o.id,s.nombre asignatura,ar.nombre area '
        .'FROM ofertas_academicas o JOIN asignaturas s ON s.id=o.asignatura_id '
        .'JOIN areas ar ON ar.id=s.area_id '
        .'WHERE o.aula_periodo_id=? AND o.activo=1'
        .($soloDocente?' AND o.docente_id=?':'')
        .' ORDER BY ar.orden,s.nombre,o.id');
    if ($soloDocente) $s->bind_param('ii',$apid,$uid);else $s->bind_param('i',$apid);
    $s->execute();$ofertas=$s->get_result()->fetch_all(MYSQLI_ASSOC);$s->close();
    $s=$conexion->prepare("SELECT m.id matricula_id,m.numero_lista,u.cedula,u.apellidos,u.nombres "
        ."FROM matriculas m JOIN usuarios u ON u.id=m.estudiante_id "
        ."WHERE m.aula_periodo_id=? AND m.estado IN ('activo','finalizado') "
        ."ORDER BY COALESCE(m.numero_lista,999999),u.apellidos,u.nombres");
    $s->bind_param('i',$apid);$s->execute();$estudiantes=$s->get_result()->fetch_all(MYSQLI_ASSOC);$s->close();

    $sesiones=[];
    $s=$conexion->prepare('SELECT ss.oferta_id,COUNT(*) total '
        .'FROM asistencia_sesiones ss JOIN ofertas_academicas o ON o.id=ss.oferta_id '
        .'WHERE o.aula_periodo_id=? AND o.activo=1 AND ss.fecha>=? AND ss.fecha<=? '
        .($soloDocente?' AND o.docente_id=?':'')
        .' GROUP BY ss.oferta_id');
    if ($soloDocente) $s->bind_param('issi',$apid,$desde,$hasta,$uid);
    else $s->bind_param('iss',$apid,$desde,$hasta);
    $s->execute();
    foreach($s->get_result()->fetch_all(MYSQLI_ASSOC) as $r) $sesiones[(int)$r['oferta_id']]=(int)$r['total'];
    $s->close();

    $estados=[];
    $s=$conexion->prepare('SELECT ad.matricula_id,ss.oferta_id, '
        ."SUM(ad.estado='presente') presente,SUM(ad.estado='ausente') ausente, "
        ."SUM(ad.estado='atraso') atraso,SUM(ad.estado='justificado') justificado "
        .'FROM asistencia_detalle ad JOIN asistencia_sesiones ss ON ss.id=ad.sesion_id '
        .'JOIN ofertas_academicas o ON o.id=ss.oferta_id '
        .'JOIN matriculas m ON m.id=ad.matricula_id AND m.aula_periodo_id=o.aula_periodo_id '
        .'WHERE o.aula_periodo_id=? AND o.activo=1 AND ss.fecha>=? AND ss.fecha<=? '
        .($soloDocente?' AND o.docente_id=?':'')
        .' GROUP BY ad.matricula_id,ss.oferta_id');
    if ($soloDocente) $s->bind_param('issi',$apid,$desde,$hasta,$uid);
    else $s->bind_param('iss',$apid,$desde,$hasta);
    $s->execute();
    foreach($s->get_result()->fetch_all(MYSQLI_ASSOC) as $r) {
        $estados[(int)$r['matricula_id']][(int)$r['oferta_id']]=raResumen($r);
    }
    $s->close();

    $totalesAula=['presente'=>0,'ausente'=>0,'atraso'=>0,'justificado'=>0];
    foreach($estudiantes as &$est) {
        $mid=(int)$est['matricula_id'];
        $est['por_oferta']=[];
        $acum=['presente'=>0,'ausente'=>0,'atraso'=>0,'justificado'=>0];
        foreach($ofertas as $o) {
            $oid=(int)$o['id'];
            $r=$estados[$mid][$oid]??raResumen([]);
            $r['sesiones']=(int)($sesiones[$oid]??0);
            $est['por_oferta'][$oid]=$r;
            foreach($acum as $clave=>&$valor) $valor+=(int)$r[$clave];
            unset($valor);
        }
        $est['total']=raResumen($acum);
        foreach($totalesAula as $clave=>&$total) $total+=(int)$acum[$clave];
        unset($total);
    }
    unset($est);
    return ['aula'=>$aula,'desde'=>$desde,'hasta'=>$hasta,'ofertas'=>$ofertas,
        'estudiantes'=>$estudiantes,'sesiones'=>$sesiones,'total'=>raResumen($totalesAula)];
}
