<?php
/**
 * Descarga masiva de certificados PDF del aula y periodo seleccionados.
 * Solo acepta POST con token CSRF. Reutiliza el mismo generador individual.
 */
require_once __DIR__.'/../../lib/sga_certificados.php';
exigirAdminAcademico();

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    header('Allow: POST');
    http_response_code(405);
    die('Este recurso solo acepta el formulario de descarga.');
}
$token=(string)($_POST['csrf_certificados_zip'] ?? '');
if (!isset($_SESSION['csrf_certificados_zip']) ||
    !hash_equals((string)$_SESSION['csrf_certificados_zip'], $token)) {
    http_response_code(403);
    die('Solicitud no autorizada. Recarga Reportes e intenta nuevamente.');
}

$periodoId=(int)($_POST['periodo_id'] ?? 0);
$aulaPeriodoId=(int)($_POST['aula_periodo_id'] ?? 0);
$tipo=(string)($_POST['tipo_certificado'] ?? '');
// Compatibilidad con formularios antiguos: Final y Anual son el mismo certificado.
if ($tipo==='final') $tipo='anual';
$tipos=['t1'=>1, 't2'=>2, 't3'=>3, 'anual'=>0];
if ($periodoId<=0 || $aulaPeriodoId<=0 || !array_key_exists($tipo,$tipos)) {
    http_response_code(422);
    die('Selecciona un periodo, aula y tipo de certificado validos.');
}
exigirAccesoPeriodo($periodoId);
exigirAccesoAulaPeriodo($aulaPeriodoId);

// El aula debe pertenecer expresamente al periodo solicitado y estar habilitada.
$stmt=$conexion->prepare("SELECT ap.id, p.nombre periodo, a.nivel, a.nombre aula, a.paralelo
    FROM aulas_periodo ap
    JOIN periodos_academicos p ON p.id=ap.periodo_id
    JOIN aulas a ON a.id=ap.aula_id
    WHERE ap.id=? AND ap.periodo_id=? AND ap.activo=1 LIMIT 1");
if (!$stmt) {http_response_code(500);die('No se pudo consultar el aula.');}
$stmt->bind_param('ii',$aulaPeriodoId,$periodoId);
$stmt->execute();
$aula=$stmt->get_result()->fetch_assoc();
$stmt->close();
if (!$aula) {http_response_code(404);die('El aula no esta habilitada en ese periodo.');}

$stmt=$conexion->prepare("SELECT m.id matricula_id,u.cedula,u.apellidos,u.nombres
    FROM matriculas m JOIN usuarios u ON u.id=m.estudiante_id
    WHERE m.aula_periodo_id=? AND m.estado='activo'
    ORDER BY COALESCE(m.numero_lista,999999),u.apellidos,u.nombres,m.id");
if (!$stmt) {http_response_code(500);die('No se pudo consultar las matriculas.');}
$stmt->bind_param('i',$aulaPeriodoId);
$stmt->execute();
$matriculas=$stmt->get_result()->fetch_all(MYSQLI_ASSOC);
$stmt->close();
if (!$matriculas) {http_response_code(404);die('El aula no tiene estudiantes matriculados activos.');}
if (!class_exists('ZipArchive')) {
    http_response_code(503);
    die('La extension PHP ZIP no esta habilitada en este servidor. Solicita activarla al hosting.');
}

// Evita rutas arbitrarias, colisiones y caracteres incompatibles en archivos ZIP.
$nombreSeguro=static function(string $texto,int $max=66): string {
    $ascii=@iconv('UTF-8','ASCII//TRANSLIT//IGNORE',$texto);
    if ($ascii===false) $ascii=$texto;
    $limpio=trim((string)preg_replace('/[^A-Za-z0-9]+/','_',strtoupper($ascii)),'_');
    return substr($limpio!==''?$limpio:'SIN_NOMBRE',0,$max);
};
$trimestre=$tipos[$tipo];
$esFinal=false; // El certificado anual no crea una modalidad final duplicada.
$archivoZip='certificados_'.strtoupper($tipo).'_'.$nombreSeguro((string)$aula['periodo'],22).
    '_aula_'.$aulaPeriodoId.'.zip';

$temporal=null;
$zip=null;
$abierto=false;
try {
    $temporal=tempnam(sys_get_temp_dir(),'sga_cert_');
    if ($temporal===false) throw new RuntimeException('No se pudo crear el archivo temporal.');
    $zip=new ZipArchive();
    if ($zip->open($temporal,ZipArchive::CREATE | ZipArchive::OVERWRITE)!==true) {
        throw new RuntimeException('No se pudo iniciar el archivo ZIP.');
    }
    $abierto=true;
    $total=0;
    $nombresUsados=[];
    foreach ($matriculas as $estudiante) {
        $mid=(int)$estudiante['matricula_id'];
        $paquete=sgaPrepararCertificadoAcademico($mid,$trimestre,$esFinal);
        // Revalidacion defensiva: no incluir una matricula de otra aula/periodo.
        if ((int)$paquete['estudiante']['aula_periodo_id']!==$aulaPeriodoId ||
            (int)$paquete['estudiante']['periodo_id']!==$periodoId) {
            throw new RuntimeException('Matricula fuera del aula seleccionada.');
        }
        $pdf=$paquete['informe']['pdf']->build();
        // Mismo nombre que la descarga individual, sin prefijos de matricula ni trimestre.
        $archivoDentro=$paquete['informe']['filename'];
        // Seguridad adicional si existen datos duplicados: no omitir ningun PDF del ZIP.
        $base=substr($archivoDentro, 0, -4);
        $candidato=$archivoDentro;
        $indice=2;
        while (isset($nombresUsados[strtolower($candidato)])) {
            $candidato=$base.'_'.$indice.'.pdf';
            $indice++;
        }
        $archivoDentro=$candidato;
        $nombresUsados[strtolower($archivoDentro)]=true;
        if (!$zip->addFromString($archivoDentro,$pdf)) {
            throw new RuntimeException('No se pudo agregar uno de los certificados.');
        }
        $total++;
        unset($paquete,$pdf);
    }
    if (!$zip->close()) throw new RuntimeException('No se pudo cerrar el archivo ZIP.');
    $abierto=false;
    if (!is_file($temporal) || filesize($temporal)===0) {
        throw new RuntimeException('No se creo correctamente el ZIP.');
    }

    registrarAuditoria('EXPORT','Reportes','certificados_academicos_zip',$aulaPeriodoId,
        'Descarga masiva de '.$total.' certificados '.$tipo.' del aula '.$aulaPeriodoId.'.',
        null,null,
        ['periodo_id'=>$periodoId,'aula_periodo_id'=>$aulaPeriodoId,
         'tipo'=>$tipo,'cantidad'=>$total,'archivo'=>$archivoZip],
        'exito',null,null,'info');

    // Un ZIP descargado no debe dejar en el navegador la pagina de Reportes.
    while (ob_get_level()>0) ob_end_clean();
    header('Content-Type: application/zip');
    header('Content-Disposition: attachment; filename="'.$archivoZip.'"');
    header('Content-Length: '.filesize($temporal));
    header('Cache-Control: private, no-store, max-age=0');
    header('X-Content-Type-Options: nosniff');
    readfile($temporal);
} catch (Throwable $error) {
    if ($abierto && $zip instanceof ZipArchive) $zip->close();
    error_log('SGA certificados ZIP: '.$error->getMessage());
    if (!headers_sent()) http_response_code(500);
    echo 'No fue posible generar todos los certificados. Ningun archivo ha sido modificado. Revisa el registro del servidor.';
} finally {
    if ($temporal!==null && is_file($temporal)) @unlink($temporal);
}
exit;
