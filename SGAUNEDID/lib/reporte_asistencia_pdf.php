<?php
/** PDF institucional de asistencia, disponible por paralelo y por estudiante. */
require_once __DIR__.'/simple_pdf.php';

function raPdfTituloAula(array $aula): string {
    return trim(($aula['nivel']??'').' · '.($aula['nombre']??'').' '.($aula['paralelo']??''));
}
function raPdfCabecera(SimplePdf $pdf,array $datos,string $periodo,bool $individual,string $alumno=''): void {
    $inst=require __DIR__.'/../config/reportes_institucional.php';
    $azul='#194B73';$gris='#64758A';$texto='#28323E';
    $pdf->addPage();
    $escudo=(string)($inst['escudo_ecuador']??'');
    if($escudo!=='')$pdf->imageJpeg($escudo,37,747,124,63);
    $pdf->rightText(558,786,'Ministerio de Educación',13.5,true,$azul);
    $pdf->rightText(558,770,'UNEDID - Cuenca',8,false,$gris);
    $pdf->textColor(38,721,'CÓDIGO AMIE:',8.5,true,$texto);
    $pdf->textColor(127,721,(string)($inst['codigo_amie']??'01H00363'),8.5,false,$texto);
    $pdf->textColor(265,721,'AÑO LECTIVO:',8.5,true,$texto);
    $pdf->textColor(351,721,$periodo,8.5,false,$texto);
    $pdf->textColor(447,721,'RÉGIMEN:',8.5,true,$texto);
    $pdf->textColor(508,721,(string)($inst['regimen']??'SIERRA'),8.5,false,$texto);
    $pdf->centerText(297,693,$individual?'REPORTE INDIVIDUAL DE ASISTENCIA':'REPORTE CONSOLIDADO DE ASISTENCIA',12.0,true,$azul);
    $titulo=(string)($inst['institucion']??'UNIDAD EDUCATIVA DE INICIACIÓN Y DESARROLLO DEPORTIVO DEL AZUAY');
    $lineas=$pdf->wrapText(strtoupper($titulo),430,10.5,true);
    $y=669;
    foreach(array_slice($lineas,0,3) as $linea){$pdf->centerText(297,$y,$linea,10.5,true,$texto);$y-=15;}
    $pdf->textColor(37,609,'CURSO / PARALELO:',8.5,true,$texto);
    $pdf->textColor(151,609,$pdf->fitText(raPdfTituloAula($datos['aula']),220,8.5),8.5,false,$texto);
    $pdf->textColor(380,609,'PERÍODO:',8.5,true,$texto);
    $pdf->textColor(449,609,$periodo,8.5,false,$texto);
    $pdf->textColor(37,589,'FECHAS:',8.5,true,$texto);
    $pdf->textColor(92,589,$datos['desde'].'  a  '.$datos['hasta'],8.5,false,$texto);
    if($individual && $alumno!==''){
        $pdf->textColor(37,569,'ESTUDIANTE:',8.5,true,$texto);
        $pdf->textColor(116,569,$pdf->fitText($alumno,436,9.0,true),9,true,$texto);
    }
}
function raPdfEncabezadoTabla(SimplePdf $pdf,array $columnas,array $anchos,float $y): float {
    $x=37.0;
    foreach($columnas as $idx=>$c){
        $w=$anchos[$idx];
        $pdf->fillRect($x,$y-23,$w,23,'#DCEAF4','#BDD0E0',.5);
        $pdf->centerText($x+$w/2,$y-14,$pdf->fitText($c,$w-6,7.5,true),7.5,true,'#153F61');
        $x+=$w;
    }
    return $y-23;
}
function raPdfPie(SimplePdf $pdf,float $y): void {
    $pdf->textColor(37,max(30,$y-23),'P: Presente  ·  A: Ausente  ·  T: Atraso  ·  J: Justificado',7.3,false,'#617487');
    $pdf->textColor(37,max(19,$y-37),'Porcentaje = (P + T) / registros guardados. Sin registro no equivale a ausencia.',7.0,false,'#617487');
}
/**
 * Una tabla consolidada por paralelo (número, estudiante, totales y porcentaje)
 * o una tabla individual con detalle por asignatura.
 */
function raPdfGenerar(array $datos,string $periodo,?int $matriculaId=null): array {
    $pdf=new SimplePdf();$ind=$matriculaId!==null;
    $alumno=null;
    if($ind){
        foreach($datos['estudiantes'] as $r){
            if((int)$r['matricula_id']===$matriculaId){$alumno=$r;break;}
        }
        if(!$alumno)throw new InvalidArgumentException('Matrícula fuera del paralelo consultado.');
    }
    $nombre=$ind?trim($alumno['apellidos'].' '.$alumno['nombres']):'';
    $repetirCabecera=function()use($pdf,$datos,$periodo,$ind,$nombre):float{
        raPdfCabecera($pdf,$datos,$periodo,$ind,$nombre);
        return $ind?549:570;
    };
    $y=$repetirCabecera();
    $col=$ind?['ASIGNATURA','P','A','T','J','REG.','ASISTENCIA']
        :['No.','ESTUDIANTE','P','A','T','J','REG.','ASISTENCIA'];
    $anchos=$ind?[235,34,34,34,34,51,105]:[36,215,34,34,34,34,50,89];
    // Las columnas deben sumar 527 puntos (37 a 564) dentro de A4.
    $y=raPdfEncabezadoTabla($pdf,$col,$anchos,$y);
    $filas=$ind?$datos['ofertas']:$datos['estudiantes'];
    foreach($filas as $idx=>$fila){
        $resumen=$ind?$alumno['por_oferta'][(int)$fila['id']]:$fila['total'];
        $nombreFila=$ind?(string)$fila['asignatura']:(string)($fila['apellidos'].' '.$fila['nombres']);
        $largo= $ind?220:203;
        $lineas=$pdf->wrapText($nombreFila,$largo,8.0,!$ind);
        $lineas=array_slice($lineas,0,3);
        $h=max(25,count($lineas)*11+7);
        if($y-$h<75){
            raPdfPie($pdf,$y);
            $y=$repetirCabecera();
            $y=raPdfEncabezadoTabla($pdf,$col,$anchos,$y);
        }
        $x=37.0;
        $fondo=($idx%2===0)?'#FFFFFF':'#F3F7FB';
        foreach($anchos as $w){$pdf->fillRect($x,$y-$h,$w,$h,$fondo,'#CBD8E4',.45);$x+=$w;}
        if(!$ind)$pdf->centerText(37+$anchos[0]/2,$y-15,(string)($fila['numero_lista']?:($idx+1)),8.2,false,'#273B53');
        $start=$ind?37:37+$anchos[0];
        foreach($lineas as $j=>$str)$pdf->textColor($start+6,$y-14-$j*11,$str,8.0,$j===0 && !$ind,'#283B51');
        $base=$ind?1:2;
        $valores=[(int)$resumen['presente'],(int)$resumen['ausente'],(int)$resumen['atraso'],(int)$resumen['justificado'],(int)$resumen['registros']];
        foreach($valores as $pos=>$v){
            $colIndex=$base+$pos;
            $cx=37+array_sum(array_slice($anchos,0,$colIndex))+$anchos[$colIndex]/2;
            $pdf->centerText($cx,$y-$h/2-3,(string)$v,8.2,false,'#2A4059');
        }
        $cx=37+array_sum(array_slice($anchos,0,count($anchos)-1))+$anchos[count($anchos)-1]/2;
        $texto=$resumen['porcentaje']===null?'Sin registro':number_format((float)$resumen['porcentaje'],2,'.','').'%';
        $pdf->centerText($cx,$y-$h/2-3,$texto,$resumen['porcentaje']===null?7.1:8.2,true,'#194B73');
        $y-=$h;
    }
    if($ind){
        $resumen=$alumno['total'];
        if($y<125){raPdfPie($pdf,$y);$y=$repetirCabecera();}
        $pdf->fillRect(37,$y-29,527,29,'#E8EFF4','#B8C5CF',.5);
        $pdf->textColor(44,$y-18,'TOTAL DEL ESTUDIANTE',9.1,true,'#194B73');
        $x=37;
        foreach($anchos as $i=>$w){
            if($i>=1&&$i<=5){
                $keys=[1=>'presente',2=>'ausente',3=>'atraso',4=>'justificado',5=>'registros'];
                $pdf->centerText($x+$w/2,$y-18,(string)$resumen[$keys[$i]],8.4,true,'#194B73');
            }elseif($i===6){
                $pdf->centerText($x+$w/2,$y-18,$resumen['porcentaje']===null?'—':number_format($resumen['porcentaje'],2,'.','').'%',8.8,true,'#194B73');
            }
            $x+=$w;
        }
        $y-=29;
    }
    raPdfPie($pdf,$y);
    $base='ASISTENCIA_'.($ind?'ESTUDIANTE_'.$matriculaId:'PARALELO_'.(int)$datos['aula']['aula_periodo_id']);
    return ['pdf'=>$pdf,'nombre'=>$base.'.pdf'];
}
