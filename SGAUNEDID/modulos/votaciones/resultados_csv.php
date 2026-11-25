<?php
require_once __DIR__.'/_lib.php';
exigirSuperadmin();

$p=periodoActivo();
if(!$p) die('No existe periodo académico activo.');
$e=eleccionPeriodo((int)$p['id']);
if(!$e) die('No existe proceso electoral para el periodo activo.');

$eid=(int)$e['id'];
$seccion=(string)($_GET['seccion']??'todas');
if(!in_array($seccion,['todas','matutina','vespertina'],true)) $seccion='todas';

$sql="SELECT DISTINCT
        u.id estudiante_id,u.cedula,u.apellidos,u.nombres,
        m.numero_lista,ea.seccion,a.nivel,a.nombre aula,a.paralelo,
        v.id voto_id,v.fecha_voto,c.nombre candidato
      FROM eleccion_aulas ea
      JOIN aulas_periodo ap ON ap.id=ea.aula_periodo_id
      JOIN aulas a ON a.id=ap.aula_id
      JOIN matriculas m ON m.aula_periodo_id=ea.aula_periodo_id AND m.estado='activo'
      JOIN usuarios u ON u.id=m.estudiante_id AND u.activo=1
      LEFT JOIN eleccion_votos v ON v.eleccion_id=ea.eleccion_id AND v.estudiante_id=m.estudiante_id
      LEFT JOIN eleccion_candidatos c ON c.id=v.candidato_id
      WHERE ea.eleccion_id=?";

if($seccion!=='todas'){
    $sql.=' AND ea.seccion=? ORDER BY a.nivel,a.nombre,a.paralelo,COALESCE(m.numero_lista,9999),u.apellidos,u.nombres';
    $stmt=$conexion->prepare($sql);
    $stmt->bind_param('is',$eid,$seccion);
}else{
    $sql.=' ORDER BY ea.seccion,a.nivel,a.nombre,a.paralelo,COALESCE(m.numero_lista,9999),u.apellidos,u.nombres';
    $stmt=$conexion->prepare($sql);
    $stmt->bind_param('i',$eid);
}
$stmt->execute();
$rows=$stmt->get_result()->fetch_all(MYSQLI_ASSOC);
$stmt->close();

$votaron=0;
foreach($rows as $r){
    if(!empty($r['voto_id'])) $votaron++;
}

registrarAuditoria(
    'EXPORT','Votaciones','eleccion',$eid,
    'Detalle nominal electoral exportado en CSV delimitado por punto y coma. Filtro: '.$seccion.'.',
    null,null,
    ['seccion'=>$seccion,'poblacion'=>count($rows),'votaron'=>$votaron,'no_votaron'=>max(0,count($rows)-$votaron),'formato'=>'csv:semicolon'],
    'exito',null,null,'critica'
);

function csvSeguro($valor): string {
    $valor=(string)($valor??'');
    // Evita que Excel interprete contenido controlado por usuarios como fórmula.
    if($valor!=='' && in_array($valor[0], ['=','+','-','@'], true)) {
        $valor="'".$valor;
    }
    return $valor;
}

$safe=preg_replace('/[^A-Za-z0-9_-]+/','_',iconv('UTF-8','ASCII//TRANSLIT//IGNORE',$p['nombre'])?:$p['nombre']);
$nombre='detalle_votacion_UNEDID_'.$safe.'_'.$seccion.'.csv';

header('Content-Type: text/csv; charset=UTF-8');
header('Content-Disposition: attachment; filename="'.$nombre.'"');
header('Cache-Control: private, max-age=0, must-revalidate');
header('Pragma: public');

$out=fopen('php://output','w');
if($out===false) die('No se pudo generar el archivo CSV.');

// BOM UTF-8 para que Excel muestre correctamente tildes y ñ.
fwrite($out, "\xEF\xBB\xBF");

fputcsv($out, [
    'Nro.','Sección','Nivel','Aula','Paralelo','Nro. lista','Cédula',
    'Apellidos','Nombres','Estado de votación','Candidato elegido','Fecha y hora del voto'
], ';', '"', '\\', "\r\n");

$n=1;
foreach($rows as $r){
    $voto=!empty($r['voto_id']);
    $fecha='';
    if($voto && !empty($r['fecha_voto'])){
        $ts=strtotime((string)$r['fecha_voto']);
        $fecha=$ts!==false?date('d/m/Y H:i:s',$ts):(string)$r['fecha_voto'];
    }
    $cedula=(string)($r['cedula']??'');
    // Conserva ceros iniciales de la cédula al abrir el CSV en Excel.
    if($cedula!=='' && $cedula[0]==='0') $cedula="'".$cedula;

    fputcsv($out, [
        $n++,
        csvSeguro(ucfirst((string)$r['seccion'])),
        csvSeguro($r['nivel']),
        csvSeguro($r['aula']),
        csvSeguro($r['paralelo']),
        $r['numero_lista']??'',
        csvSeguro($cedula),
        csvSeguro($r['apellidos']),
        csvSeguro($r['nombres']),
        $voto?'VOTÓ':'NO VOTÓ',
        $voto?csvSeguro($r['candidato']):'',
        $fecha
    ], ';', '"', '\\', "\r\n");
}

fclose($out);
exit;
