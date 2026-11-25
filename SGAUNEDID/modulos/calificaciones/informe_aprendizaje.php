<?php
/** Informe de aprendizaje cualitativo, formato institucional en PDF. */
require_once __DIR__.'/../../lib/funciones.php';
require_once __DIR__.'/../../lib/simple_pdf.php';
exigirLogin();
$oid=(int)($_GET['oferta_id']??0);$mid=(int)($_GET['matricula_id']??0);
if(!$oid||!$mid||!puedeGestionarOferta($oid)){http_response_code(403);exit('No tienes acceso a este informe.');}
$o=ofertaDetalle($oid);
if(!$o || empty($o['evaluacion_cualitativa_parametros'])){http_response_code(404);exit('La asignatura no tiene evaluación por parámetros.');}
$apid=(int)$o['aula_periodo_id'];
$s=$conexion->prepare("SELECT m.id,m.numero_lista,u.apellidos,u.nombres,u.cedula FROM matriculas m JOIN usuarios u ON u.id=m.estudiante_id WHERE m.id=? AND m.aula_periodo_id=? AND m.estado IN ('activo','finalizado') LIMIT 1");
$s->bind_param('ii',$mid,$apid);sgaEjecutar($s,'consultar la matrícula');$al=$s->get_result()->fetch_assoc();$s->close();
if(!$al){http_response_code(404);exit('El estudiante no pertenece al aula.');}
$par=sgaParametrosDeOferta($conexion,$oid);
$notas=sgaParametrosNotasDeOferta($conexion,$oid,$mid);
$cfg=require __DIR__.'/../../config/reportes_institucional.php';
$pdf=new SimplePdf();
$azul='#193E65';$gris='#4D657F';$borde='#C5D3E0';$cab='#EDF3F8';
$pag=0;
$encabezado=function()use($pdf,$cfg,$o,$al,$azul,$gris,$borde,$cab,&$pag):float{
  $pag++;$pdf->addPage();
  if(is_file((string)($cfg['logo']??'')))$pdf->imageJpeg($cfg['logo'],45,735,70,65);
  $pdf->centerText(315,790,'INFORME DE APRENDIZAJE',15,true,$azul);
  $pdf->centerText(315,769,$pdf->fitText((string)$cfg['institucion'],410,9.5,true),9.5,true,$azul);
  $pdf->lineColor(45,729,550,729,1.1,$azul);
  $pdf->text(45,710,'AÑO LECTIVO: '.(string)$o['periodo'],9,true);
  $pdf->text(315,710,'RÉGIMEN: '.(string)($cfg['regimen']??''),9,true);
  $pdf->text(45,691,'AULA: '.(string)$o['nivel'].' · '.(string)$o['aula'].' '.(string)$o['paralelo'],8.5);
  $pdf->text(45,676,(!empty($o['evaluacion_aula'])?'DOCENTE: '.$pdf->fitText(trim($o['docente_apellidos'].' '.$o['docente_nombres']),465,9,true):'ASIGNATURA (histórico): '.$pdf->fitText((string)$o['asignatura'],430,9,true)),9,true);
  $pdf->text(45,657,'ESTUDIANTE: '.$pdf->fitText((string)$al['apellidos'].' '.(string)$al['nombres'],466,9,true),9,true);
  $pdf->text(45,642,'CÉDULA: '.(string)$al['cedula'],8.8);
  $pdf->fillRect(45,593,505,34,$cab,$borde,0.6);
  $pdf->text(51,604,'EJE DE DESARROLLO',8.2,true);
  $pdf->text(217,604,'ÁMBITO / INDICADOR',8.2,true);
  foreach(['I','II','III'] as $i=>$t)$pdf->centerText(448+$i*39,604,$t,9,true,$azul);
  $pdf->textColor(45,33,'SGA UNEDID · Evaluación cualitativa por parámetros · Página '.$pag,7,false,$gris);
  return 593;
};
// Agrupar los ejes consecutivos sin alterar el orden de los parametros ni sus IDs.
// La celda izquierda ocupa toda la altura del grupo (equivalente a rowspan).
$grupos=[];
foreach($par as $p){
  $eje=trim((string)$p['eje']);
  $ultimo=count($grupos)-1;
  if($ultimo<0 || $grupos[$ultimo]['eje']!==$eje){
    $grupos[]=['eje'=>$eje,'filas'=>[]];
    $ultimo++;
  }
  $a=$pdf->wrapText($eje,151,8.1,false);
  $b=$pdf->wrapText((string)$p['ambito'],215,8.2,false);
  $alto=max(29,max(1,count($a),count($b))*11+12);
  $grupos[$ultimo]['filas'][]=['id'=>(int)$p['id'],'texto'=>$b,'alto'=>$alto];
}
$y=$encabezado();
$limite=85;
$altoPagina=593-$limite;
foreach($grupos as $grupo){
  $filas=$grupo['filas'];
  $lineasEje=$pdf->wrapText($grupo['eje'],151,8.1,false);
  $altoGrupo=array_sum(array_column($filas,'alto'));
  // Si el grupo cabe en una pagina completa, evitar cortarlo entre paginas.
  if($altoGrupo<=$altoPagina && $y-$altoGrupo<$limite){$y=$encabezado();}
  $n=count($filas);
  for($i=0;$i<$n;){
    if($y-$filas[$i]['alto']<$limite && $y<593){$y=$encabezado();}
    $inicio=$i;$altoBloque=0;
    // Un eje excepcionalmente largo se repite solo al continuar en otra pagina.
    while($i<$n && $y-$altoBloque-$filas[$i]['alto']>=$limite){
      $altoBloque+=$filas[$i]['alto'];$i++;
    }
    // Garantizar avance aun si un indicador excepcional excede la pagina.
    if($i===$inicio){$altoBloque=$filas[$i]['alto'];$i++;}
    $pdf->fillRect(45,$y-$altoBloque,165,$altoBloque,'#FFFFFF',$borde,0.45);
    // Alineacion vertical centrada del nombre del eje dentro de la celda unida.
    $baseEje=$y-$altoBloque/2+(count($lineasEje)-1)*5.5-2.5;
    foreach($lineasEje as $j=>$texto)$pdf->text(51,$baseEje-$j*11,$texto,8.1);
    for($j=$inicio;$j<$i;$j++){
      $fila=$filas[$j];$id=$fila['id'];$alto=$fila['alto'];
      // Las divisiones horizontales comienzan en la columna de ambito,
      // por lo que nunca atraviesan la celda combinada del eje.
      $pdf->fillRect(210,$y-$alto,340,$alto,'#FFFFFF',$borde,0.45);
      foreach($fila['texto'] as $k=>$texto)$pdf->text(217,$y-14-$k*11,$texto,8.2);
      foreach([1,2,3] as $t){
        $literal=(string)($notas[$mid][$id][$t]??'');
        if($literal==='')$literal='—';
        $pdf->centerText(409+$t*39,$y-$alto/2-3,$literal,10,true,$azul);
      }
      $pdf->lineColor(429,$y-$alto,429,$y,.4,$borde);
      $y-=$alto;
    }
    if($i<$n){$y=$encabezado();}
  }
}
$y-=25;
if($y<85)$y=$encabezado()-25;
$pdf->textColor(45,$y,'Las valoraciones se registran por ámbito y trimestre; no representan un promedio numérico.',8,false,$gris);
$filename='APRENDIZAJE_'.preg_replace('/[^A-Z0-9_]+/','_',strtoupper(iconv('UTF-8','ASCII//TRANSLIT//IGNORE',$al['apellidos'].'_'.$al['nombres'])?:'ESTUDIANTE')).'_'.preg_replace('/[^0-9A-Za-z]/','',(string)$al['cedula']).'.pdf';
$pdf->output($filename,true);
