<?php
require_once __DIR__.'/../../lib/sga_representantes.php';
exigirLogin();
$pid=(int)(periodoActivo()['id']??0);
$puedeGestionar=esAdminAcademico();
$puedeDocencia=$pid>0 && esDocenteOperativo($pid);
if (!$puedeGestionar && !$puedeDocencia) {
    if (esRepresentanteOperativo()) redir('modulos/representantes/mis_hijos.php');
    http_response_code(403);die('Acceso restringido al personal autorizado.');
}
if (!$pid) { http_response_code(409); die('Necesitas un período académico activo para gestionar los representantes.'); }
if(empty($_SESSION['csrf_representantes']))$_SESSION['csrf_representantes']=bin2hex(random_bytes(24));
$csrf=(string)$_SESSION['csrf_representantes'];
// V1.6.19: temporary selection of students is kept in this user's server session.
$listaKey = 'sga_rep_seleccion_v1619';
if (!isset($_SESSION[$listaKey]) || !is_array($_SESSION[$listaKey]) ||
    (int)($_SESSION[$listaKey]['periodo_id'] ?? 0) !== $pid) {
    $_SESSION[$listaKey] = ['periodo_id' => $pid, 'ids' => []];
}
if (!isset($_SESSION[$listaKey]['ids']) || !is_array($_SESSION[$listaKey]['ids'])) {
    $_SESSION[$listaKey]['ids'] = [];
}
$_SESSION[$listaKey]['ids'] = array_slice(array_values(array_unique(array_filter(
    array_map('intval', $_SESSION[$listaKey]['ids']), static fn($id) => $id > 0
))), 0, 50);
$estudianteId=(int)($_SERVER['REQUEST_METHOD']==='POST' ? ($_POST['estudiante_id']??0) : ($_GET['estudiante_id']??0));
$representanteId=(int)($_SERVER['REQUEST_METHOD']==='POST' ? ($_POST['representante_id']??0) : ($_GET['representante_id']??0));
$dir='modulos/representantes/index.php';
if($_SERVER['REQUEST_METHOD']==='POST'){
    $accion = (string)($_POST['accion'] ?? '');
    $vinculoGuardado = false;
    $mostrarSeleccion = in_array($accion, ['seleccion_agregar','seleccion_quitar','seleccion_vaciar','vincular_lote'], true);
    try {
        if (!$puedeGestionar) throw new RuntimeException('No tienes autorizacion para modificar vinculos.');
        if (!hash_equals($csrf, (string)($_POST['csrf'] ?? ''))) throw new RuntimeException('El formulario ha caducado.');
        // Temporary list operations never require a parent to be selected first.
        if (in_array($accion, ['seleccion_agregar','seleccion_quitar','seleccion_vaciar'], true)) {
            $ids = $_SESSION[$listaKey]['ids'];
            if ($accion === 'seleccion_agregar') {
                if ($estudianteId <= 0 || !sgaRepDatosEstudiante($estudianteId, $pid, true))
                    throw new DomainException('El estudiante no tiene una matricula activa en tu ambito de acceso.');
                if (!in_array($estudianteId, $ids, true)) {
                    if (count($ids) >= 50) throw new DomainException('Puedes seleccionar como maximo 50 estudiantes por lote.');
                    $ids[] = $estudianteId;
                }
            } elseif ($accion === 'seleccion_quitar') {
                $ids = array_values(array_filter($ids, static fn($id) => (int)$id !== $estudianteId));
            } else {
                $ids = [];
            }
            $_SESSION[$listaKey]['ids'] = $ids;
        } elseif (in_array($accion, ['vincular','vincular_lote','desvincular'], true)) {
            // Keep the original subadmin protection: exact 10-digit parent ID.
            if (esSubadmin()) {
                $cedula = trim((string)($_POST['cedula_rep'] ?? ''));
                $dato = sgaRepDatosRepresentante($representanteId);
                if (!$dato || !preg_match('/^[0-9]{10}$/D', $cedula) ||
                    !hash_equals((string)$dato['cedula'], $cedula))
                    throw new RuntimeException('Busca primero al representante por su cedula completa.');
            }
            if ($accion === 'vincular_lote') {
                if (($_POST['vinculo_verificado'] ?? '') !== '1')
                    throw new RuntimeException('Confirma primero la relacion familiar y la autorizacion.');
                $ids = $_SESSION[$listaKey]['ids'];
                if (!$ids || count($ids) > 50) throw new DomainException('Selecciona de 1 a 50 estudiantes antes de guardar.');
                $rep = sgaRepDatosRepresentante($representanteId);
                if (!$rep || !filter_var((string)($rep['correo'] ?? ''), FILTER_VALIDATE_EMAIL))
                    throw new DomainException('Selecciona un representante activo que tenga un correo valido.');
                // Validate EVERY student before writing ANY link.
                foreach ($ids as $id) {
                    if ((int)$id === $representanteId || !sgaRepPuedeVincular((int)$id, $pid))
                        throw new DomainException('Hay un estudiante fuera de tu jornada o sin matricula activa. La lista no se modifico.');
                }
                $conexion->begin_transaction();
                try {
                    $nuevos = 0;
                    foreach ($ids as $id) {
                        $id = (int)$id;
                        $cambio = sgaRepVincular($representanteId, $id, $pid);
                        if ($cambio) {
                            $nuevos++;
                            registrarAuditoria('ASSIGN_ROLE','Representantes','representante_estudiante',
                                $representanteId.'-'.$id,'Vinculacion familiar registrada en lote.',
                                $id,null,['representante_id'=>$representanteId], 'exito',null,null,'advertencia');
                        }
                    }
                    $conexion->commit();
                } catch (Throwable $e) {
                    $conexion->rollback();
                    throw $e;
                }
                $_SESSION[$listaKey]['ids'] = [];
                flash('success', 'Vinculos procesados: '.count($ids).' estudiantes. Registros actualizados: '.$nuevos.'.');
                $vinculoGuardado = true;
            } elseif ($accion === 'vincular') {
                // Backward compatibility with the previous single-student form.
                if (($_POST['vinculo_verificado'] ?? '') !== '1')
                    throw new RuntimeException('Verifica primero la relacion familiar y marca la confirmacion.');
                $cambio = sgaRepVincular($representanteId, $estudianteId, $pid);
                registrarAuditoria('ASSIGN_ROLE','Representantes','representante_estudiante',
                    $representanteId.'-'.$estudianteId,'Vinculacion familiar registrada.',
                    $estudianteId,null,['representante_id'=>$representanteId], 'exito',null,null,'advertencia');
                flash('success',$cambio?'Representante vinculado correctamente.':'Este representante ya estaba vinculado.');
                $vinculoGuardado = true;
            } else {
                sgaRepDesvincular($representanteId,$estudianteId,$pid);
                registrarAuditoria('UPDATE','Representantes','representante_estudiante',
                    $representanteId.'-'.$estudianteId,'Vinculacion familiar desactivada.',
                    $estudianteId,['representante_id'=>$representanteId],['activo'=>0],'exito',null,null,'advertencia');
                flash('success','Vinculo eliminado. Este representante no recibira nuevas novedades de este estudiante.');
            }
        } else {
            throw new RuntimeException('Accion no reconocida.');
        }
    } catch(Throwable $e) {
        flash('error',$e->getMessage());
        // Failed bulk operations stay open so the user can retry the selection.
        if ($accion === 'vincular_lote') $mostrarSeleccion = true;
    }
    $params = [
        'representante_id'=>$representanteId ?: null,
        'cedula_rep'=>trim((string)($_POST['cedula_rep']??'')),
        'q'=>substr(trim((string)($_POST['q']??'')),0,80),
    ];
    if ($mostrarSeleccion && !$vinculoGuardado) {
        $params['vincular'] = 1;
        $params['buscar_est'] = substr(trim((string)($_POST['buscar_est']??'')),0,80);
        $params['buscar_rep'] = substr(trim((string)($_POST['buscar_rep']??'')),0,80);
    }
    $params = array_filter($params, static fn($v) => $v !== null && $v !== '');
    redir($dir . ($params ? '?' . http_build_query($params, '', '&', PHP_QUERY_RFC3986) : '') .
        ($vinculoGuardado || $accion === 'desvincular' ? '#sga-fam-ficha' : ''));
}

// V1.6.18: directorio principal y vinculación dentro de una única ventana flotante.
$esSubadminLimitado = esSubadmin(); // Directorio restringido a estudiantes de jornadas asignadas.
$buscarEst = trim((string)($_GET['buscar_est'] ?? ''));
$buscarRep = trim((string)($_GET['buscar_rep'] ?? ''));
$buscarDir = trim((string)($_GET['q'] ?? ''));
if (strlen($buscarDir) > 80) $buscarDir = '';
$pagina = max(1, min(100000, (int)($_GET['pagina'] ?? 1)));
$porPagina = 30;
$cedulaRep = trim((string)($_REQUEST['cedula_rep'] ?? ''));
$estudiantes = $buscarEst !== '' ? sgaRepBuscarEstudiantes($buscarEst, $pid) : [];
$representantes = $puedeGestionar && $buscarRep !== '' ? sgaRepBuscarRepresentantes($buscarRep) : [];
$seleccionado = $estudianteId ? sgaRepDatosEstudiante($estudianteId, $pid, true) : null;
$listaEstudiantes = [];
if ($puedeGestionar) {
    foreach ($_SESSION[$listaKey]['ids'] as $id) {
        $dato = sgaRepDatosEstudiante((int)$id, $pid, true);
        if ($dato) $listaEstudiantes[] = $dato;
    }
    $_SESSION[$listaKey]['ids'] = array_map(static fn($u) => (int)$u['id'], $listaEstudiantes);
}
$idsEnLista = array_map(static fn($u) => (int)$u['id'], $listaEstudiantes);

/** Enlaces del módulo: los identificadores se conservan, sin alterar el esquema. */
function sgaRepDirUrlV1618(array $params = []): string {
    return url('modulos/representantes/index.php' . ($params ? '?' . http_build_query($params, '', '&', PHP_QUERY_RFC3986) : ''));
}

// Los recuentos son únicamente de estudiantes con matrícula y aula activas en este período.
// Para subadministradores y docentes, el recuento incluye únicamente estudiantes accesibles.
$alcance = "SELECT re.representante_id, COUNT(DISTINCT est.id) AS cantidad
    FROM sga_representantes_estudiantes re
    JOIN usuarios est ON est.id = re.estudiante_id AND est.activo = 1
    JOIN matriculas m ON m.estudiante_id = est.id AND m.estado = 'activo'
    JOIN aulas_periodo ap ON ap.id = m.aula_periodo_id AND ap.periodo_id = " . $pid . " AND ap.activo = 1
    JOIN aulas a ON a.id = ap.aula_id";
if ($esSubadminLimitado) {
    $jornadas = array_map('intval', jornadasPermitidasPeriodo($pid));
    $ids = $jornadas ? implode(',', $jornadas) : '0';
    $alcance .= " WHERE re.activo = 1 AND a.jornada_id IN ($ids)
        AND NOT EXISTS (
            SELECT 1 FROM matriculas m2
            JOIN aulas_periodo ap2 ON ap2.id = m2.aula_periodo_id AND ap2.periodo_id = $pid AND ap2.activo = 1
            JOIN aulas a2 ON a2.id = ap2.aula_id
            WHERE m2.estudiante_id = est.id AND m2.estado = 'activo'
            AND (a2.jornada_id IS NULL OR a2.jornada_id NOT IN ($ids))
        )";
} elseif (!$puedeGestionar) {
    $docenteId = (int)($_SESSION['usuario_id'] ?? 0);
    $alcance .= " JOIN ofertas_academicas oa ON oa.aula_periodo_id = ap.id
        AND oa.docente_id = $docenteId AND oa.activo = 1
        WHERE re.activo = 1";
} else {
    $alcance .= " WHERE re.activo = 1";
}
$alcance .= ' GROUP BY re.representante_id';
$joinConteos = esSuperadmin() ? 'LEFT JOIN' : 'INNER JOIN';
$fromDirectorio = " FROM usuarios u
    JOIN usuario_roles ur ON ur.usuario_id = u.id AND ur.periodo_id IS NULL
    JOIN roles rol ON rol.id = ur.rol_id AND rol.codigo = 'representante'
    $joinConteos ($alcance) cnt ON cnt.representante_id = u.id
    WHERE u.activo = 1";
$filtrado = strlen($buscarDir) >= 2;
if ($filtrado) {
    $fromDirectorio .= ' AND (u.cedula LIKE ? OR u.apellidos LIKE ? OR u.nombres LIKE ?)';
}
$sentencia = $conexion->prepare('SELECT COUNT(DISTINCT u.id) AS total ' . $fromDirectorio);
if (!$sentencia) throw new RuntimeException('No se pudo preparar el directorio de representantes.');
if ($filtrado) {
    $buscaLike = '%' . $buscarDir . '%';
    $sentencia->bind_param('sss', $buscaLike, $buscaLike, $buscaLike);
}
$sentencia->execute();
$totalDirectorio = (int)($sentencia->get_result()->fetch_assoc()['total'] ?? 0);
$sentencia->close();
$totalPaginas = max(1, (int)ceil($totalDirectorio / $porPagina));
$pagina = min($pagina, $totalPaginas);
$offset = ($pagina - 1) * $porPagina;
$sentencia = $conexion->prepare("SELECT DISTINCT u.id, u.cedula, u.apellidos, u.nombres, u.correo,
    COALESCE(cnt.cantidad, 0) AS cantidad
    $fromDirectorio ORDER BY u.apellidos, u.nombres, u.id LIMIT $porPagina OFFSET $offset");
if (!$sentencia) throw new RuntimeException('No se pudo cargar el directorio de representantes.');
if ($filtrado) $sentencia->bind_param('sss', $buscaLike, $buscaLike, $buscaLike);
$sentencia->execute();
$directorio = $sentencia->get_result()->fetch_all(MYSQLI_ASSOC);
$sentencia->close();

// El detalle individual se muestra únicamente tras seleccionar un representante.
$padreSeleccionado = null;
$hijos = [];
if ($representanteId > 0) {
    if ($puedeGestionar) {
        $padreSeleccionado = sgaRepDatosRepresentante($representanteId);
    } else {
        $sentencia = $conexion->prepare("SELECT u.id,u.cedula,u.apellidos,u.nombres,u.correo FROM usuarios u
            JOIN usuario_roles ur ON ur.usuario_id=u.id AND ur.periodo_id IS NULL
            JOIN roles rol ON rol.id=ur.rol_id AND rol.codigo='representante'
            WHERE u.id=? AND u.activo=1 LIMIT 1");
        $sentencia->bind_param('i', $representanteId);
        $sentencia->execute();
        $padreSeleccionado = $sentencia->get_result()->fetch_assoc() ?: null;
        $sentencia->close();
    }
    if ($esSubadminLimitado && $padreSeleccionado
        && (!preg_match('/^[0-9]{10}$/D', $cedulaRep) || !hash_equals((string)$padreSeleccionado['cedula'], $cedulaRep))) {
        $padreSeleccionado = null;
    }
    if ($padreSeleccionado) {
        $sentencia = $conexion->prepare("SELECT DISTINCT est.id FROM sga_representantes_estudiantes re
            JOIN usuarios est ON est.id=re.estudiante_id AND est.activo=1
            WHERE re.representante_id=? AND re.activo=1 ORDER BY est.id");
        $sentencia->bind_param('i', $representanteId);
        $sentencia->execute();
        $idsHijos = $sentencia->get_result()->fetch_all(MYSQLI_ASSOC);
        $sentencia->close();
        foreach ($idsHijos as $dato) {
            $hijo = sgaRepDatosEstudiante((int)$dato['id'], $pid, true);
            if ($hijo) $hijos[] = $hijo;
        }
    }
    // Los docentes no pueden abrir un representante si no hay ningún alumno autorizado.
    if (!$puedeGestionar && !$hijos) $padreSeleccionado = null;
    if (!$padreSeleccionado) $representanteId = 0;
}

$familia = $seleccionado ? sgaRepRepresentantesDe((int)$seleccionado['id']) : [];
$historial = [];
if ($seleccionado) {
    $sentencia = $conexion->prepare("SELECT n.id,n.tipo,n.asunto,n.creada_en,
        SUM(CASE WHEN e.estado='enviado' THEN 1 ELSE 0 END) AS entregados,
        SUM(CASE WHEN e.estado IN ('pendiente','enviando','error') THEN 1 ELSE 0 END) AS pendientes,
        SUM(CASE WHEN e.estado='sin_correo' THEN 1 ELSE 0 END) AS sin_correo
        FROM sga_representantes_novedades n
        LEFT JOIN sga_representantes_envios e ON e.novedad_id=n.id
        WHERE n.estudiante_id=? AND n.periodo_id=?
        GROUP BY n.id,n.tipo,n.asunto,n.creada_en ORDER BY n.id DESC LIMIT 15");
    $sentencia->bind_param('ii', $estudianteId, $pid);
    $sentencia->execute();
    $historial = $sentencia->get_result()->fetch_all(MYSQLI_ASSOC);
    $sentencia->close();
}
$tituloPagina = 'Representantes';
$subtituloPagina = $puedeGestionar
    ? 'Consulta los representantes y sus estudiantes vinculados. Vincula desde un único formulario flotante.'
    : 'Consulta las familias de tus estudiantes y registra novedades con acceso autorizado.';
require __DIR__ . '/../../partials/header.php';
?>
<style>
/* V1.6.19: directorio con seleccion provisional y ficha flotante; estilos encapsulados en este módulo. */
.sga-fam-toolbar{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.sga-fam-toolbar h2,.sga-fam-panel-head h2{margin:0 0 4px}
.sga-fam-muted{font-size:12px;color:#61738d;line-height:1.5}
.sga-fam-search{display:flex;align-items:end;gap:9px;max-width:620px;margin:15px 0 5px;flex-wrap:wrap}
.sga-fam-search label{flex:1 1 250px;min-width:0}
.sga-fam-search input{min-width:0}
.sga-fam-search .btn{flex:0 0 auto}
.sga-fam-count{display:inline-flex;align-items:center;padding:4px 9px;border-radius:20px;background:#edf3fa;color:#29476e;font-weight:700;font-size:12px;white-space:nowrap}
.sga-fam-count.zero{background:#f1f3f6;color:#68788b}
.sga-fam-table{margin-top:14px}
.sga-fam-table .table{width:100%}
.sga-fam-table .table td,.sga-fam-table .table th{padding:10px 11px;vertical-align:middle}
.sga-fam-name{font-weight:700;color:#122b4b;line-height:1.35}
.sga-fam-actions{display:flex;gap:6px;align-items:center;justify-content:flex-end;flex-wrap:wrap}
.sga-fam-actions .btn{white-space:nowrap}
.sga-fam-active{background:#f2f7ff}
.sga-fam-pages{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;margin-top:12px}
.sga-fam-pages .actions{display:flex;gap:7px}
.sga-fam-panel{margin-top:15px}
.sga-fam-panel-head{display:flex;align-items:start;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-bottom:11px}
.sga-fam-panel-head .actions{display:flex;gap:7px;flex-wrap:wrap}
.sga-fam-table form{margin:0}
.sga-fam-dialog{position:fixed;inset:0;margin:auto;width:min(840px,calc(100vw - 24px));max-width:100%;max-height:min(91dvh,840px);padding:0;overflow-y:auto;overscroll-behavior:contain;border:1px solid #cbd8e8;border-radius:15px;background:#fff;color:#203650;box-shadow:0 28px 70px rgba(4,22,49,.35)}
.sga-fam-dialog:not([open]){display:none}
.sga-fam-dialog::backdrop{background:rgba(5,20,41,.60);backdrop-filter:blur(2px)}
.sga-fam-dialog-head{display:flex;align-items:start;justify-content:space-between;gap:12px;padding:17px 19px 12px;border-bottom:1px solid #dfe8f4}
.sga-fam-dialog-head h2{font-size:20px;margin:0 0 5px;color:#14345b}
.sga-fam-dialog-close{flex:0 0 34px;width:34px;height:34px;border:0;border-radius:8px;background:#edf2f9;color:#315070;font:700 23px/1 Arial,sans-serif;cursor:pointer}
.sga-fam-tabs{display:flex;gap:8px;padding:12px 19px 0;border-bottom:1px solid #e4eaf2}
.sga-fam-tabs button{padding:10px 13px;border:1px solid #d3dfef;border-bottom:0;background:#f5f8fc;color:#284967;border-radius:9px 9px 0 0;font-weight:700;font-size:13px;cursor:pointer}
.sga-fam-tabs button[aria-selected=true]{background:#fff;color:#12539e;border-color:#89acd7;box-shadow:inset 0 3px 0 #12539e}
.sga-fam-tab-panel{padding:18px 19px 20px}
.sga-fam-tab-panel[hidden]{display:none!important}
.sga-fam-form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.sga-fam-form-grid .sga-fam-search-box{padding:13px;border:1px solid #e0e8f2;border-radius:10px;background:#fbfcff;min-width:0}
.sga-fam-form-grid h3{margin:0 0 5px;font-size:15px;color:#1b3a60}
.sga-fam-form-grid label{display:block;min-width:0}
.sga-fam-find{display:flex;gap:7px;align-items:end;flex-wrap:wrap;margin:10px 0 0}
.sga-fam-find label{flex:1 1 185px}
.sga-fam-find .btn{margin-bottom:0;flex:0 0 auto}
.sga-fam-results{margin-top:11px;max-height:215px;overflow-y:auto;overscroll-behavior:contain;border:1px solid #e2e9f3;border-radius:9px;background:white}
.sga-fam-result{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:8px 10px;border-bottom:1px solid #edf1f6}
.sga-fam-result:last-child{border-bottom:0}
.sga-fam-result .btn{flex:0 0 auto}
.sga-fam-picked{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin-top:10px}
.sga-fam-picked strong{display:inline-block;max-width:100%;padding:5px 8px;border-radius:8px;background:#e7f1ff;color:#174b87;font-size:12px;overflow-wrap:anywhere}
.sga-fam-confirm{display:grid;gap:10px;margin-top:13px;padding:13px;border:1px solid #cddff3;border-radius:10px;background:#f5f9ff}
.sga-fam-check{display:flex;flex-direction:row!important;align-items:flex-start;gap:9px;line-height:1.45;font-size:13px;cursor:pointer}
.sga-fam-check input{width:17px!important;height:17px;flex:0 0 17px;margin:1px 0 0}
.sga-fam-dialog-actions{display:flex;justify-content:flex-end;gap:8px;flex-wrap:wrap}
.sga-fam-inline-form{margin:0;flex:0 0 auto}
.sga-fam-queue{margin-top:14px;border:1px solid #b9d2ef;background:#f5f9ff;border-radius:10px;padding:10px}
.sga-fam-confirm .sga-fam-queue{margin:0;padding:0;border:0;background:transparent}
.sga-fam-confirm .sga-fam-queue-items{max-height:245px}
.sga-fam-confirm .sga-fam-empty-list{margin-top:7px}
.sga-fam-vincular-form{display:grid;gap:11px}
.sga-fam-queue-head{display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;margin-bottom:9px;font-size:13px}
.sga-fam-queue-items{display:grid;gap:5px;max-height:210px;overflow-y:auto}
.sga-fam-queue-item{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:8px 9px;border:1px solid #dbe7f7;border-radius:8px;background:white}
.sga-fam-queue-item strong{display:block;font-size:12px;color:#153b68;line-height:1.35}
.sga-fam-queue-item span{display:block;font-size:11px;color:#61738d;margin-top:3px}
.sga-fam-empty-list{margin:9px 0 0;text-align:right}
.sga-fam-ficha-dialog{width:min(800px,calc(100vw - 24px))}
.sga-fam-ficha-body{padding:12px 19px 20px}
.sga-fam-ficha-bottom{margin-top:18px}
.sga-fam-csv-example{display:grid;gap:4px;background:#f5f8fc;border:1px solid #dce5f0;border-radius:10px;padding:11px 13px;font-size:12px;overflow-wrap:anywhere}
.sga-fam-csv-example code{white-space:normal;overflow-wrap:anywhere;color:#173d70}
.sga-fam-csv-form{display:grid;gap:13px;margin:12px 0}
.sga-fam-csv-form input[type=file]{max-width:100%;font-size:13px}
.sga-fam-dialog a:focus-visible,.sga-fam-dialog button:focus-visible{outline:3px solid #4a93d6;outline-offset:2px}
@media(max-width:690px){
 .sga-fam-form-grid{grid-template-columns:1fr}
 .sga-fam-dialog-head,.sga-fam-tab-panel{padding-left:13px;padding-right:13px}
 .sga-fam-tabs{padding-left:13px;padding-right:13px}
 .sga-fam-ficha-body{padding-left:13px;padding-right:13px}
 .sga-fam-queue-item{align-items:flex-start}
 .sga-fam-table .table thead{display:none}
 .sga-fam-table .table,.sga-fam-table .table tbody,.sga-fam-table .table tr,.sga-fam-table .table td{display:block;width:100%}
 .sga-fam-table .table tr{padding:9px 10px;border-bottom:1px solid #e1e8f1}
 .sga-fam-table .table td{padding:3px 0;border:0}
 .sga-fam-table .table td[data-label]::before{content:attr(data-label) ': ';font-size:11px;font-weight:700;color:#61738d}
 .sga-fam-actions{justify-content:flex-start;margin-top:5px}
 .sga-fam-dialog-actions .btn{flex:1 1 120px}
}
</style>

<section class="card" id="sga-fam-directorio">
  <div class="sga-fam-toolbar">
    <div>
      <h2>Directorio de representantes</h2>
      <div class="sga-fam-muted"><?=e($puedeGestionar ? 'Consulta los responsables registrados y añade estudiantes desde una ventana flotante.' : 'Representantes vinculados a estudiantes que puedes consultar.')?></div>
    </div>
    <div class="actions" style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
      <span class="sga-fam-count"><?=$totalDirectorio?> representante<?=$totalDirectorio===1?'':'s'?></span>
      <button class="btn btn-primary" type="button" data-sga-fam-open>
        <?=$puedeGestionar ? '+ Vincular estudiante' : 'Buscar estudiante'?>
      </button>
    </div>
  </div>
  <form class="sga-fam-search" method="get" action="<?=e(url($dir))?>">
    <label>Buscar en el directorio
      <input name="q" type="search" value="<?=e($buscarDir)?>" maxlength="80" placeholder="Apellidos, nombres o cédula" autocomplete="off">
    </label>
    <button class="btn btn-secondary" type="submit">Buscar</button>
    <?php if($buscarDir!==''):?><a class="btn btn-secondary" href="<?=e(url($dir))?>">Limpiar</a><?php endif;?>
  </form>
  <div class="sga-fam-muted">Cantidad de estudiantes vinculados con matrícula activa en el período <?=e((string)(periodoActivo()['nombre']??'activo'))?>. Solo se muestran los permitidos para tu perfil.</div>
  <div class="table-wrap sga-fam-table">
    <table class="table">
      <thead><tr><th>Representante</th><th>Correo</th><th>Representados</th><th style="text-align:right">Acciones</th></tr></thead>
      <tbody>
      <?php foreach($directorio as $rep):
        $rid=(int)$rep['id'];
        $params=['representante_id'=>$rid,'cedula_rep'=>(string)$rep['cedula'],'q'=>$buscarDir,'pagina'=>$pagina];
      ?>
        <tr class="<?=$rid===$representanteId?'sga-fam-active':''?>">
          <td><div class="sga-fam-name"><?=e($rep['apellidos'].' '.$rep['nombres'])?></div><div class="mini-note"><?=e($rep['cedula'])?></div></td>
          <td data-label="Correo"><span class="sga-fam-muted"><?=!empty($rep['correo'])?e($rep['correo']):'Sin correo registrado'?></span></td>
          <td data-label="Representados"><span class="sga-fam-count <?=((int)$rep['cantidad']===0)?'zero':''?>"><?=(int)$rep['cantidad']?> estudiante<?=(int)$rep['cantidad']===1?'':'s'?></span></td>
          <td><div class="sga-fam-actions">
            <a class="btn btn-sm btn-secondary" href="<?=e(sgaRepDirUrlV1618($params))?>#sga-fam-ficha">Ver estudiantes</a>
            <?php if($puedeGestionar):?><a class="btn btn-sm btn-primary" href="<?=e(sgaRepDirUrlV1618($params+['vincular'=>1]))?>">+ Añadir</a><?php endif;?>
          </div></td>
        </tr>
      <?php endforeach;?>
      <?php if(!$directorio):?><tr><td colspan="4">No se encontraron representantes<?= $buscarDir!==''?' con esa búsqueda':'' ?>.<?php if($puedeGestionar):?> Utiliza «Vincular estudiante» para localizar una cuenta de representante o importar un CSV.<?php endif;?></td></tr><?php endif;?>
      </tbody>
    </table>
  </div>
  <?php if($totalPaginas>1):?>
  <div class="sga-fam-pages">
    <span class="sga-fam-muted">Página <?=$pagina?> de <?=$totalPaginas?> · <?=$totalDirectorio?> representantes</span>
    <div class="actions">
      <?php if($pagina>1):?><a class="btn btn-sm btn-secondary" href="<?=e(sgaRepDirUrlV1618(['q'=>$buscarDir,'pagina'=>$pagina-1]))?>">Anterior</a><?php endif;?>
      <?php if($pagina<$totalPaginas):?><a class="btn btn-sm btn-secondary" href="<?=e(sgaRepDirUrlV1618(['q'=>$buscarDir,'pagina'=>$pagina+1]))?>">Siguiente</a><?php endif;?>
    </div>
  </div>
  <?php endif;?>
</section>

<?php if($padreSeleccionado):?>
<section class="card sga-fam-panel" id="sga-fam-ficha">
  <div class="sga-fam-panel-head">
    <div>
      <h2>Estudiantes de <?=e($padreSeleccionado['apellidos'].' '.$padreSeleccionado['nombres'])?></h2>
      <div class="sga-fam-muted">Representante: <?=e($padreSeleccionado['cedula'])?> · <?=count($hijos)?> estudiante<?=count($hijos)===1?'':'s'?> bajo tus permisos</div>
    </div>
    <?php if($puedeGestionar):?>
    <div class="actions"><a class="btn btn-primary btn-sm" href="<?=e(sgaRepDirUrlV1618(['representante_id'=>$representanteId,'cedula_rep'=>$cedulaRep ?: (string)$padreSeleccionado['cedula'],'vincular'=>1,'q'=>$buscarDir]))?>">+ Añadir estudiante</a></div>
    <?php endif;?>
  </div>
  <div class="table-wrap sga-fam-table">
    <table class="table">
      <thead><tr><th>Estudiante representado</th><th>Aula</th><th style="text-align:right">Acciones</th></tr></thead>
      <tbody>
        <?php foreach($hijos as $h):?>
        <tr>
          <td><div class="sga-fam-name"><?=e($h['apellidos'].' '.$h['nombres'])?></div><div class="mini-note"><?=e($h['cedula'])?></div></td>
          <td data-label="Aula"><?=e($h['aula'])?></td>
          <td><div class="sga-fam-actions">
            <a class="btn btn-sm btn-secondary" href="<?=e(sgaRepDirUrlV1618(['estudiante_id'=>(int)$h['id'],'representante_id'=>$representanteId,'cedula_rep'=>$cedulaRep ?: (string)$padreSeleccionado['cedula'],'q'=>$buscarDir,'ficha'=>1]))?>">Ver ficha y notificar</a>
            <?php if($puedeGestionar):?>
            <form method="post">
              <input type="hidden" name="csrf" value="<?=e($csrf)?>">
              <input type="hidden" name="accion" value="desvincular">
              <input type="hidden" name="representante_id" value="<?=$representanteId?>">
              <input type="hidden" name="estudiante_id" value="<?=(int)$h['id']?>">
              <input type="hidden" name="cedula_rep" value="<?=e($padreSeleccionado['cedula'])?>">
              <button class="btn btn-sm btn-secondary" type="submit" data-confirm="¿Desvincular a este estudiante?">Desvincular</button>
            </form>
            <?php endif;?>
          </div></td>
        </tr>
        <?php endforeach;?>
        <?php if(!$hijos):?><tr><td colspan="3">Todavía no hay estudiantes vinculados con matrícula activa en tu ámbito de acceso.</td></tr><?php endif;?>
      </tbody>
    </table>
  </div>
</section>
<?php endif;?>

<?php if($seleccionado):?>
<dialog class="sga-fam-dialog sga-fam-ficha-dialog" id="sga-fam-estudiante" aria-labelledby="sga-fam-ficha-title">
  <div class="sga-fam-dialog-head">
    <div>
      <h2 id="sga-fam-ficha-title">Ver ficha y notificar</h2>
      <div class="sga-fam-name"><?=e($seleccionado['apellidos'].' '.$seleccionado['nombres'])?></div>
      <div class="sga-fam-muted"><?=e($seleccionado['cedula'])?> · <?=e($seleccionado['aula'])?></div>
    </div>
    <button class="sga-fam-dialog-close" type="button" data-sga-fam-ficha-close aria-label="Cerrar ficha">&times;</button>
  </div>
  <div class="sga-fam-ficha-body">
  <h3 style="font-size:16px;margin:13px 0 8px">Representantes asociados</h3>
  <div class="table-wrap sga-fam-table"><table class="table"><thead><tr><th>Representante</th><th>Correo de notificaciones</th></tr></thead><tbody>
    <?php foreach($familia as $f):?><tr><td><div class="sga-fam-name"><?=e($f['apellidos'].' '.$f['nombres'])?></div><div class="mini-note"><?=e($f['cedula'])?></div></td><td data-label="Correo"><?=!empty($f['correo'])?e($f['correo']):'Sin correo'?></td></tr><?php endforeach;?>
    <?php if(!$familia):?><tr><td colspan="2">Este estudiante aún no tiene representantes vinculados.</td></tr><?php endif;?>
  </tbody></table></div>
  <h3 style="font-size:16px;margin:18px 0 8px">Registrar novedad y notificar a la familia</h3>
  <?php if(!$familia):?><div class="notice">Primero debe vincularse al menos un representante para enviar avisos.</div><?php else:?>
  <form method="post" action="<?=e(url('modulos/representantes/notificar.php'))?>" style="display:grid;gap:11px">
    <input type="hidden" name="csrf" value="<?=e($csrf)?>"><input type="hidden" name="estudiante_id" value="<?=$estudianteId?>">
    <div class="form-grid cols-2">
      <label>Tipo de novedad<select name="tipo" required>
        <option value="general">Información general</option><option value="academica">Situación académica</option><option value="asistencia">Asistencia</option><option value="comportamiento">Comportamiento</option><option value="urgente">Aviso importante</option>
      </select></label>
      <label>Asunto<input name="asunto" required maxlength="180" placeholder="Ej.: Reunión de seguimiento"></label>
    </div>
    <label>Descripción de la novedad<textarea name="detalle" rows="3" maxlength="2000" required placeholder="Describe lo sucedido de forma respetuosa y concreta."></textarea></label>
    <div><button class="btn btn-primary" type="submit" data-confirm="¿Enviar esta novedad a los representantes con correo válido?">Registrar y enviar aviso</button></div>
  </form>
  <p class="mini-note">Cada representante recibe un correo individual; no se comparte la dirección de otros representantes.</p>
  <?php endif;?>
  <?php if($historial):?>
  <h3 style="font-size:16px;margin:20px 0 8px">Últimas novedades</h3>
  <div class="table-wrap sga-fam-table"><table class="table"><thead><tr><th>Fecha</th><th>Asunto</th><th>Entregas</th></tr></thead><tbody>
    <?php foreach($historial as $n):?><tr><td data-label="Fecha"><?=e($n['creada_en'])?></td><td><?=e($n['asunto'])?><div class="mini-note"><?=e($n['tipo'])?></div></td><td data-label="Correos"><?=(int)$n['entregados']?> enviados · <?=(int)$n['pendientes']?> pendientes<?php if((int)$n['sin_correo']):?> · <?=(int)$n['sin_correo']?> sin correo<?php endif;?></td></tr><?php endforeach;?>
  </tbody></table></div>
  <?php endif;?>
  <div class="sga-fam-dialog-actions sga-fam-ficha-bottom"><button class="btn btn-secondary" type="button" data-sga-fam-ficha-close>Cerrar</button></div>
  </div>
</dialog>
<?php endif;?>

<!-- La búsqueda individual y la importación masiva viven en el mismo diálogo. -->
<dialog class="sga-fam-dialog" id="sga-fam-dialog" aria-labelledby="sga-fam-dialog-title">
  <div class="sga-fam-dialog-head">
    <div>
      <h2 id="sga-fam-dialog-title"><?=$puedeGestionar?'Vincular representantes y estudiantes':'Buscar estudiante'?></h2>
      <div class="sga-fam-muted"><?=$puedeGestionar?'Busca ambas cuentas o importa un CSV, sin salir del directorio.':'Localiza estudiantes de tus asignaturas autorizadas.'?></div>
    </div>
    <button class="sga-fam-dialog-close" type="button" data-sga-fam-close aria-label="Cerrar ventana">&times;</button>
  </div>
  <?php if($puedeGestionar):?>
  <div class="sga-fam-tabs" role="tablist" aria-label="Modo de vinculación">
    <button type="button" role="tab" id="sga-fam-tab-individual" data-sga-fam-tab="individual" aria-selected="true" aria-controls="sga-fam-panel-individual">Vincular individual</button>
    <button type="button" role="tab" id="sga-fam-tab-csv" data-sga-fam-tab="csv" aria-selected="false" aria-controls="sga-fam-panel-csv">Importar CSV</button>
  </div>
  <?php endif;?>
  <div class="sga-fam-tab-panel" id="sga-fam-panel-individual" role="tabpanel" aria-labelledby="sga-fam-tab-individual">
    <div class="sga-fam-form-grid">
      <div class="sga-fam-search-box">
        <h3>1. Buscar estudiante</h3>
        <div class="sga-fam-muted">Introduce al menos tres caracteres de su nombre o cédula.</div>
        <form method="get" class="sga-fam-find" action="<?=e(url($dir))?>">
          <input type="hidden" name="vincular" value="1">
          <input type="hidden" name="representante_id" value="<?=$representanteId?>">
          <input type="hidden" name="cedula_rep" value="<?=e($padreSeleccionado['cedula']??$cedulaRep)?>">
          <input type="hidden" name="q" value="<?=e($buscarDir)?>">
          <label>Estudiante<input type="search" name="buscar_est" minlength="3" maxlength="80" value="<?=e($buscarEst)?>" placeholder="Nombre o cédula" required></label>
          <button class="btn btn-sm btn-primary" type="submit">Buscar</button>
        </form>
        <?php if($buscarEst!==''):?>
        <div class="sga-fam-results">
          <?php foreach($estudiantes as $f):?>
          <div class="sga-fam-result">
            <div><strong class="sga-fam-muted"><?=e($f['apellidos'].' '.$f['nombres'])?></strong><div class="mini-note"><?=e($f['aula'])?> · <?=e($f['cedula'])?></div></div>
            <?php if($puedeGestionar):?>
            <?php if(in_array((int)$f['id'], $idsEnLista, true)):?>
              <span class="sga-fam-count">En lista</span>
            <?php else:?>
              <form method="post" class="sga-fam-inline-form">
                <input type="hidden" name="csrf" value="<?=e($csrf)?>">
                <input type="hidden" name="accion" value="seleccion_agregar">
                <input type="hidden" name="estudiante_id" value="<?=(int)$f['id']?>">
                <input type="hidden" name="representante_id" value="<?=$representanteId?>">
                <input type="hidden" name="cedula_rep" value="<?=e($padreSeleccionado['cedula']??$cedulaRep)?>">
                <input type="hidden" name="buscar_est" value="<?=e($buscarEst)?>">
                <input type="hidden" name="buscar_rep" value="<?=e($buscarRep)?>">
                <input type="hidden" name="q" value="<?=e($buscarDir)?>">
                <button class="btn btn-sm btn-primary" type="submit">+ A&ntilde;adir</button>
              </form>
            <?php endif;?>
            <?php else:?>
              <a class="btn btn-sm btn-secondary" href="<?=e(sgaRepDirUrlV1618(['estudiante_id'=>(int)$f['id']]))?>">Ver ficha</a>
            <?php endif;?>
          </div>
          <?php endforeach;?>
          <?php if(!$estudiantes):?><div class="sga-fam-result"><span class="sga-fam-muted">No se encontraron estudiantes autorizados.</span></div><?php endif;?>
        </div>
        <?php endif;?>

      </div>
      <?php if($puedeGestionar):?>
      <div class="sga-fam-search-box">
        <h3>2. Buscar representante</h3>
        <div class="sga-fam-muted"><?= $esSubadminLimitado?'Para subadministradores, se exige la cédula completa de 10 dígitos.':'Busca una cuenta que ya tenga el rol Representante.' ?></div>
        <form method="get" class="sga-fam-find" action="<?=e(url($dir))?>">
          <input type="hidden" name="vincular" value="1">
          <input type="hidden" name="estudiante_id" value="<?=$seleccionado?(int)$seleccionado['id']:0?>">
          <input type="hidden" name="q" value="<?=e($buscarDir)?>">
          <label>Representante<input type="search" name="buscar_rep" minlength="3" maxlength="80" value="<?=e($buscarRep)?>" placeholder="<?=$esSubadminLimitado?'Cédula de 10 dígitos':'Nombre o cédula'?>" required></label>
          <button class="btn btn-sm btn-primary" type="submit">Buscar</button>
        </form>
        <?php if($padreSeleccionado):?>
        <div class="sga-fam-picked"><span class="sga-fam-muted">Seleccionado:</span><strong><?=e($padreSeleccionado['apellidos'].' '.$padreSeleccionado['nombres'])?></strong></div>
        <?php endif;?>
        <?php if($buscarRep!==''):?>
        <div class="sga-fam-results">
          <?php foreach($representantes as $f):?>
          <div class="sga-fam-result">
            <div><strong class="sga-fam-muted"><?=e($f['apellidos'].' '.$f['nombres'])?></strong><div class="mini-note"><?=e($f['cedula'])?></div></div>
            <a class="btn btn-sm btn-secondary" href="<?=e(sgaRepDirUrlV1618(['vincular'=>1,'representante_id'=>(int)$f['id'],'cedula_rep'=>(string)$f['cedula'],'buscar_est'=>$buscarEst,'buscar_rep'=>$buscarRep,'q'=>$buscarDir]))?>">Elegir</a>
          </div>
          <?php endforeach;?>
          <?php if(!$representantes):?><div class="sga-fam-result"><span class="sga-fam-muted">No se encontró una cuenta con rol Representante.</span></div><?php endif;?>
        </div>
        <?php endif;?>
      </div>
      <?php endif;?>
    </div>
    <?php if($puedeGestionar):?>
      <div class="sga-fam-confirm">
        <strong>3. Confirmar los v&iacute;nculos</strong>
        <?php if($padreSeleccionado):?>
        <div class="sga-fam-muted"><strong>Representante:</strong> <?=e($padreSeleccionado['apellidos'].' '.$padreSeleccionado['nombres'])?></div>
        <?php endif;?>
        <div class="sga-fam-muted"><strong>Estudiantes:</strong> <?=count($listaEstudiantes)?> en la lista provisional</div>
        <!-- V1.6.20: review, remove or clear selected students exactly where the link is confirmed. -->
        <div class="sga-fam-queue" aria-live="polite">
          <?php if($listaEstudiantes):?>
          <div class="sga-fam-queue-items">
            <?php foreach($listaEstudiantes as $f):?>
            <div class="sga-fam-queue-item">
              <div><strong><?=e($f['apellidos'].' '.$f['nombres'])?></strong><span><?=e($f['aula'])?></span></div>
              <form method="post" class="sga-fam-inline-form">
                <input type="hidden" name="csrf" value="<?=e($csrf)?>">
                <input type="hidden" name="accion" value="seleccion_quitar">
                <input type="hidden" name="estudiante_id" value="<?=(int)$f['id']?>">
                <input type="hidden" name="representante_id" value="<?=$representanteId?>">
                <input type="hidden" name="cedula_rep" value="<?=e($padreSeleccionado['cedula']??$cedulaRep)?>">
                <input type="hidden" name="buscar_est" value="<?=e($buscarEst)?>">
                <input type="hidden" name="buscar_rep" value="<?=e($buscarRep)?>">
                <input type="hidden" name="q" value="<?=e($buscarDir)?>">
                <button class="btn btn-sm btn-secondary" type="submit" aria-label="Quitar <?=e($f['apellidos'].' '.$f['nombres'])?>">Quitar</button>
              </form>
            </div>
            <?php endforeach;?>
          </div>
          <form method="post" class="sga-fam-empty-list">
            <input type="hidden" name="csrf" value="<?=e($csrf)?>">
            <input type="hidden" name="accion" value="seleccion_vaciar">
            <input type="hidden" name="representante_id" value="<?=$representanteId?>">
            <input type="hidden" name="cedula_rep" value="<?=e($padreSeleccionado['cedula']??$cedulaRep)?>">
            <input type="hidden" name="buscar_est" value="<?=e($buscarEst)?>">
            <input type="hidden" name="buscar_rep" value="<?=e($buscarRep)?>">
            <input type="hidden" name="q" value="<?=e($buscarDir)?>">
            <button class="btn btn-sm btn-secondary" type="submit">Vaciar lista</button>
          </form>
          <?php else:?>
          <div class="sga-fam-muted">Busca estudiantes en el paso 1 y pulsa &laquo;A&ntilde;adir&raquo;. Aparecer&aacute;n aqu&iacute; para revisar antes de vincular.</div>
          <?php endif;?>
        </div>
        <?php if($padreSeleccionado && $listaEstudiantes):?>
        <form method="post" class="sga-fam-vincular-form">
          <input type="hidden" name="csrf" value="<?=e($csrf)?>">
          <input type="hidden" name="accion" value="vincular_lote">
          <input type="hidden" name="representante_id" value="<?=(int)$padreSeleccionado['id']?>">
          <input type="hidden" name="cedula_rep" value="<?=e($padreSeleccionado['cedula'])?>">
          <input type="hidden" name="q" value="<?=e($buscarDir)?>">
          <label class="sga-fam-check"><input type="checkbox" name="vinculo_verificado" value="1" required>Confirmo que UNEDID verific&oacute; la relaci&oacute;n familiar y la autorizaci&oacute;n correspondiente para cada estudiante seleccionado.</label>
          <div class="sga-fam-dialog-actions"><button type="button" class="btn btn-secondary" data-sga-fam-close>Cancelar</button><button class="btn btn-primary" type="submit">Vincular <?=count($listaEstudiantes)?> estudiante<?=count($listaEstudiantes)===1?'':'s'?></button></div>
        </form>
        <?php else:?>
          <p class="sga-fam-muted"><?= $listaEstudiantes?'Elige un representante en el paso 2 para habilitar la vinculaci&oacute;n.':'A&ntilde;ade uno o varios estudiantes y elige un representante para habilitar el guardado.' ?></p>
          <div class="sga-fam-dialog-actions"><button class="btn btn-secondary" type="button" data-sga-fam-close>Cerrar</button></div>
        <?php endif;?>
      </div>
    <?php else:?>
      <div class="sga-fam-dialog-actions" style="margin-top:14px"><button class="btn btn-secondary" type="button" data-sga-fam-close>Cerrar</button>
      <?php if($seleccionado):?><a class="btn btn-primary" href="<?=e(sgaRepDirUrlV1618(['estudiante_id'=>(int)$seleccionado['id']]))?>">Ver ficha</a><?php endif;?></div>
    <?php endif;?>
  </div>
  <?php if($puedeGestionar):?>
  <div class="sga-fam-tab-panel" id="sga-fam-panel-csv" role="tabpanel" aria-labelledby="sga-fam-tab-csv" hidden>
    <h3 style="margin:0 0 8px">Asignación masiva mediante CSV</h3>
    <p class="sga-fam-muted">Vincula cuentas ya registradas. El archivo debe estar en UTF-8 y contener dos columnas separadas por punto y coma.</p>
    <div class="sga-fam-csv-example"><strong>Formato</strong><code>cedula;estudiantes</code><code>0101234567;0109876543,0108765432</code></div>
    <div style="margin-top:12px"><a class="btn btn-sm btn-secondary" href="<?=e(url('plantillas/representantes_estudiantes.csv'))?>">Descargar plantilla CSV</a></div>
    <form action="<?=e(url('modulos/representantes/importar.php'))?>" method="post" enctype="multipart/form-data" class="sga-fam-csv-form">
      <input type="hidden" name="csrf" value="<?=e($csrf)?>">
      <label>Archivo CSV (máximo 1 MB)<input type="file" name="archivo" accept=".csv,text/csv" required></label>
      <label class="sga-fam-check"><input type="checkbox" name="vinculos_verificados" value="1" required>Confirmo que UNEDID verificó las relaciones familiares y las autorizaciones.</label>
      <div class="sga-fam-dialog-actions"><button type="button" class="btn btn-secondary" data-sga-fam-close>Cancelar</button><button type="submit" class="btn btn-primary">Importar vínculos</button></div>
    </form>
    <p class="sga-fam-muted">Si existe algún error, se cancela toda la importación. El sistema no crea cuentas nuevas.</p>
  </div>
  <?php endif;?>
</dialog>
<script>
(() => {
  const ficha = document.getElementById('sga-fam-estudiante');
  if (ficha) {
    const abrirFicha = () => {
      if (typeof ficha.showModal === 'function') {
        if (!ficha.open) ficha.showModal();
      } else ficha.setAttribute('open', '');
    };
    const cerrarFicha = () => {
      if (typeof ficha.close === 'function' && ficha.open) ficha.close();
      else ficha.removeAttribute('open');
    };
    ficha.querySelectorAll('[data-sga-fam-ficha-close]').forEach(b => b.addEventListener('click', cerrarFicha));
    ficha.addEventListener('click', e => {
      if (e.target !== ficha) return;
      const r = ficha.getBoundingClientRect();
      if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) cerrarFicha();
    });
    <?php if($seleccionado && (($_GET['vincular']??'')!=='1') && !($buscarEst!=='' || $buscarRep!=='')):?>abrirFicha();<?php endif;?>
  }
  const dialogo = document.getElementById('sga-fam-dialog');
  if (!dialogo) return;
  let origen = null;
  const mostrar = (origenNuevo) => {
    origen = origenNuevo || origen;
    if (typeof dialogo.showModal === 'function') {
      if (!dialogo.open) dialogo.showModal();
    } else dialogo.setAttribute('open', '');
  };
  const cerrar = () => {
    if (typeof dialogo.close === 'function' && dialogo.open) dialogo.close();
    else dialogo.removeAttribute('open');
  };
  document.querySelectorAll('[data-sga-fam-open]').forEach(b => b.addEventListener('click', () => mostrar(b)));
  dialogo.querySelectorAll('[data-sga-fam-close]').forEach(b => b.addEventListener('click', cerrar));
  dialogo.addEventListener('click', e => {
    if (e.target !== dialogo) return;
    const r = dialogo.getBoundingClientRect();
    if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) cerrar();
  });
  dialogo.addEventListener('close', () => { if (origen && origen.isConnected) origen.focus(); });
  const pestañas = [...dialogo.querySelectorAll('[data-sga-fam-tab]')];
  function seleccionarPestaña(nombre) {
    pestañas.forEach(p => p.setAttribute('aria-selected', String(p.dataset.sgaFamTab === nombre)));
    ['individual','csv'].forEach(n => {
      const panel = document.getElementById('sga-fam-panel-' + n);
      if (panel) panel.hidden = n !== nombre;
    });
  }
  pestañas.forEach(p => p.addEventListener('click', () => seleccionarPestaña(p.dataset.sgaFamTab)));
  seleccionarPestaña('<?=e(($_GET['pestana']??'')==='csv'?'csv':'individual')?>');
  <?php if(($_GET['vincular']??'')==='1' || $buscarEst!=='' || $buscarRep!==''):?>mostrar(null);<?php endif;?>
})();
</script>
<?php require __DIR__ . '/../../partials/footer.php'; ?>
