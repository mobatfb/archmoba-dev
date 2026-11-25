<?php
/** Generador OOXML XLSX valido, sin depender de la extension PHP ZipArchive.
 *  Cada hoja corresponde a un aula habilitada en el periodo solicitado.
 */
require_once __DIR__.'/comportamiento_promedio.php';

function cuadroAnualXml(?string $texto): string {
    $texto = (string)($texto ?? '');
    $texto = preg_replace('/[\x00-\x08\x0B\x0C\x0E-\x1F]/u', '', $texto) ?? '';
    return htmlspecialchars($texto, ENT_XML1 | ENT_QUOTES, 'UTF-8');
}
/** Compatibilidad con hosting PHP que no trae extension mbstring. */
function cuadroAnualMayusculas(string $s): string {
    return strtoupper(strtr($s, [
        'á'=>'Á','é'=>'É','í'=>'Í','ó'=>'Ó','ú'=>'Ú','ñ'=>'Ñ','ü'=>'Ü',
    ]));
}
function cuadroAnualCortar(string $s, int $limite): string {
    $chars = preg_split('//u', $s, -1, PREG_SPLIT_NO_EMPTY);
    return is_array($chars) ? implode('',array_slice($chars,0,$limite)) : substr($s,0,$limite);
}
function cuadroAnualLargo(string $s): int {
    $chars = preg_split('//u', $s, -1, PREG_SPLIT_NO_EMPTY);
    return is_array($chars) ? count($chars) : strlen($s);
}
function cuadroAnualColumna(int $numero): string {
    $s = '';
    while ($numero > 0) {
        $numero--;
        $s = chr(65 + ($numero % 26)).$s;
        $numero = intdiv($numero,26);
    }
    return $s;
}
function cuadroAnualCeldaTexto(string $ref, string $valor, int $estilo=0): string {
    return '<c r="'.$ref.'" s="'.$estilo.'" t="inlineStr"><is><t xml:space="preserve">'
        .cuadroAnualXml($valor).'</t></is></c>';
}
function cuadroAnualCeldaNumero(string $ref, float $valor, int $estilo=7): string {
    return '<c r="'.$ref.'" s="'.$estilo.'"><v>'
        .number_format($valor,2,'.','').'</v></c>';
}
/** Las pestanas conservan el nombre literal registrado, sin abreviar grados.
 *  Excel admite como maximo 31 caracteres y no permite algunos simbolos.
 *  Si dos aulas comparten nombre y paralelo, se agrega nivel o un numero.
 */
function cuadroAnualNombreHoja(array $aula, array &$usados): string {
    $nombre=trim((string)($aula['nombre']??''));
    $paralelo=trim((string)($aula['paralelo']??''));
    $nivel=trim((string)($aula['nivel']??''));
    // Conservar el nombre creado y anadir el paralelo, salvo que ya lo incluya.
    if($paralelo!=='' && ($nombre==='' || !preg_match('/(?:^|\s)'.preg_quote($paralelo,'/').'$/iu',$nombre))){
        $nombre.=($nombre!==''?' ':'').$paralelo;
    }
    $limpiar=static function(string $s):string {
        $s=str_replace(['[',']',':','*','?',chr(92),'/'],' ',$s);
        $s=preg_replace('/\s+/u',' ', $s)??$s;
        return trim($s," \t\n\r\0\x0B'");
    };
    $nombre=$limpiar($nombre);
    if($nombre==='')$nombre='Aula';
    // En aulas de nombre muy extenso, conservar visible el paralelo al final.
    if($paralelo!=='' && cuadroAnualLargo($nombre)>31){
        $paraleloLimpio=$limpiar($paralelo);
        if($paraleloLimpio!=='' && cuadroAnualLargo($paraleloLimpio)<16){
            $separador=' '.$paraleloLimpio;
            $original=$limpiar((string)($aula['nombre']??''));
            $nombre=cuadroAnualCortar($original,31-cuadroAnualLargo($separador)).$separador;
        }
    }
    // No se hace conversion OCTAVO => 8 ni se convierte a mayusculas.
    $base=cuadroAnualCortar($nombre,31);
    $clave=static function(string $s):string {
        return strtolower(strtr($s,['Á'=>'á','É'=>'é','Í'=>'í','Ó'=>'ó','Ú'=>'ú','Ñ'=>'ñ','Ü'=>'ü']));
    };
    $titulo=$base;
    if(isset($usados[$clave($titulo)])){
        $nivel=$limpiar($nivel);
        if($nivel!==''){
            $sufijo=' - '.$nivel;
            $candidato=cuadroAnualCortar($nombre,max(1,31-cuadroAnualLargo($sufijo))).$sufijo;
            if(!isset($usados[$clave($candidato)]))$titulo=$candidato;
        }
    }
    $i=2;
    while(isset($usados[$clave($titulo)])){
        $sufijo=' ('.$i++.')';
        $titulo=cuadroAnualCortar($nombre,max(1,31-cuadroAnualLargo($sufijo))).$sufijo;
    }
    $usados[$clave($titulo)]=true;
    return $titulo;
}
/** El encabezado interior tambien respeta el nombre real del aula. */
function cuadroAnualTituloAula(array $aula): string {
    $nombre=trim((string)($aula['nombre']??''));
    $paralelo=trim((string)($aula['paralelo']??''));
    if($paralelo!=='' && ($nombre==='' || !preg_match('/(?:^|\s)'.preg_quote($paralelo,'/').'$/iu',$nombre))){
        $nombre.=($nombre!==''?' ':'').$paralelo;
    }
    return cuadroAnualMayusculas(trim($nombre));
}
function cuadroAnualEncabezadoAsignatura(array $oferta): string {
    // Los encabezados del cuadro anual usan el nombre completo de la asignatura.
    // El codigo (ej. FUND-TIC, OVP, MAT) solo es un respaldo si no hay nombre.
    $nombre = trim((string)($oferta['nombre']??''));
    if($nombre!=='')return cuadroAnualMayusculas($nombre);
    $codigo = trim((string)($oferta['codigo']??''));
    return $codigo!==''?cuadroAnualMayusculas($codigo):'ASIGNATURA';
}
/** Anchura legible sin columnas desmesuradas para materias de nombre extenso. */
function cuadroAnualAnchoAsignatura(string $nombre): int {
    $largo = cuadroAnualLargo($nombre);
    if($largo>=55)return 31;
    if($largo>=34)return 28;
    return 23;
}
/** Estima el numero de renglones al ajustar texto en la cabecera de Excel. */
function cuadroAnualLineasCabecera(string $nombre,int $ancho): int {
    $palabras=preg_split('/\s+/u',trim($nombre),-1,PREG_SPLIT_NO_EMPTY);
    if(!$palabras)return 1;
    $limite=max(10,$ancho-6);
    $lineas=1;$ocupado=0;
    foreach($palabras as $palabra){
        $largo=cuadroAnualLargo($palabra);
        if($ocupado>0 && ($ocupado+1+$largo)>$limite){
            $lineas++;$ocupado=0;
        }
        if($largo>$limite){
            $lineas+=intdiv($largo-1,$limite);
            $ocupado=$largo%$limite;
            if($ocupado===0)$ocupado=$limite;
        }else{
            $ocupado+=($ocupado?1:0)+$largo;
        }
    }
    return $lineas;
}

function cuadroAnualEstilos(): string {
    $ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main';
    $fonts=''
      .'<font><sz val="10"/><color rgb="FF223247"/><name val="Calibri"/></font>'
      .'<font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font>'
      .'<font><b/><sz val="10"/><color rgb="FFBC2929"/><name val="Calibri"/></font>'
      .'<font><b/><sz val="10"/><color rgb="FF154E7B"/><name val="Calibri"/></font>'
      .'<font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font>';
    $fills='<fill><patternFill patternType="none"/></fill>'
      .'<fill><patternFill patternType="gray125"/></fill>'
      .'<fill><patternFill patternType="solid"><fgColor rgb="FF143F70"/><bgColor indexed="64"/></patternFill></fill>'
      .'<fill><patternFill patternType="solid"><fgColor rgb="FFEFF5FB"/><bgColor indexed="64"/></patternFill></fill>'
      .'<fill><patternFill patternType="solid"><fgColor rgb="FF6743A2"/><bgColor indexed="64"/></patternFill></fill>'
      .'<fill><patternFill patternType="solid"><fgColor rgb="FFF0EAFB"/><bgColor indexed="64"/></patternFill></fill>';
    $borders='<border><left/><right/><top/><bottom/><diagonal/></border>'
      .'<border><left style="thin"><color rgb="FFCEDBE8"/></left>'
      .'<right style="thin"><color rgb="FFCEDBE8"/></right>'
      .'<top style="thin"><color rgb="FFCEDBE8"/></top>'
      .'<bottom style="thin"><color rgb="FFCEDBE8"/></bottom><diagonal/></border>';
    $defs=[
      [0,0,0,0,'left'], [1,2,1,0,'center'], [3,3,1,0,'center'],
      [1,2,1,0,'center'], [4,4,1,0,'center'], [0,0,1,0,'left'],
      [0,3,1,0,'left'], [0,0,1,2,'center'], [0,3,1,2,'center'],
      [2,0,1,2,'center'], [2,3,1,2,'center'], [3,0,1,0,'center'],
      [3,3,1,0,'center'], [3,5,1,0,'center'], [3,5,1,0,'center'],
      [0,0,1,0,'center'], [0,3,1,0,'center'], [0,0,1,1,'center'],
      [0,3,1,1,'center'],
      // Literales por debajo de 7 (B-): texto rojo, sin formato numerico.
      [2,0,1,0,'center'], [2,3,1,0,'center'],
    ];
    $xfs='';
    foreach ($defs as $d) {
       [$font,$fill,$border,$num,$align]=$d;
       $xfs.='<xf numFmtId="'.$num.'" fontId="'.$font.'" fillId="'.$fill.'" borderId="'.$border.'"'
           .' xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"'
           .($num?' applyNumberFormat="1"':'')
           .'><alignment horizontal="'.$align.'" vertical="center" wrapText="1"/></xf>';
    }
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
      .'<styleSheet xmlns="'.$ns.'"><fonts count="5">'.$fonts.'</fonts>'
      .'<fills count="6">'.$fills.'</fills><borders count="2">'.$borders.'</borders>'
      .'<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
      .'<cellXfs count="'.count($defs).'">'.$xfs.'</cellXfs>'
      .'<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
      .'</styleSheet>';
}
/**
 * Una hoja mantiene la distribución de la plantilla: título fila 1,
 * encabezados fila 3, estudiantes desde fila 4, materias y comportamiento.
 * Las notas incompletas se dejan vacías, tanto en el cuadro anual como
 * en el de un trimestre; nunca se inventan ceros.
 */
function cuadroAnualCrearHoja(array $aula, string $periodo, ?int $trimestre=null, bool $soloSupletorios=false): string {
    $ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main';
    $ofertas = $aula['ofertas']??[];
    $estudiantes = $aula['estudiantes']??[];
    $cantidadCols = count($ofertas)+3;
    $colFin = cuadroAnualColumna($cantidadCols);
    $ultimoRow = max(4,3+count($estudiantes));
    $titulo = cuadroAnualTituloAula($aula);
    $subtitulo = 'PERÍODO '.$periodo.'  |  '.(string)($aula['nivel']??'');
    if ($soloSupletorios) $subtitulo.='  |  SUPLETORIO';
    elseif ($trimestre!==null) $subtitulo.='  |  TRIMESTRE '.$trimestre;
    if (!empty($aula['jornada'])) $subtitulo.='  |  JORNADA '.cuadroAnualMayusculas((string)$aula['jornada']);
    $cabeceras=[];$anchos=[];$altoCabecera=56;
    foreach($ofertas as $oferta){
        $encabezado=cuadroAnualEncabezadoAsignatura($oferta);
        $ancho=cuadroAnualAnchoAsignatura($encabezado);
        $cabeceras[]=$encabezado;
        $anchos[]=$ancho;
        $altoCabecera=max($altoCabecera,min(155,cuadroAnualLineasCabecera($encabezado,$ancho)*16+12));
    }
    $xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
      .'<worksheet xmlns="'.$ns.'">'
      .'<sheetPr><pageSetUpPr fitToPage="1"/></sheetPr>'
      .'<dimension ref="A1:'.$colFin.$ultimoRow.'"/>'
      .'<sheetViews><sheetView workbookViewId="0" showGridLines="0">'
      .'<pane xSplit="2" ySplit="3" topLeftCell="C4" activePane="bottomRight" state="frozen"/>'
      .'<selection pane="bottomRight" activeCell="C4" sqref="C4"/>'
      .'</sheetView></sheetViews><sheetFormatPr defaultRowHeight="19"/>'
      .'<cols><col min="1" max="1" width="7" customWidth="1"/>'
      .'<col min="2" max="2" width="42" customWidth="1"/>';
    foreach($anchos as $pos=>$ancho){
        $c=$pos+3;
        $xml.='<col min="'.$c.'" max="'.$c.'" width="'.$ancho.'" customWidth="1"/>';
    }
    $xml.='<col min="'.$cantidadCols.'" max="'.$cantidadCols.'" width="29" customWidth="1"/></cols>';
    $xml.='<sheetData>';
    $xml.='<row r="1" ht="29" customHeight="1">'
      .cuadroAnualCeldaTexto('B1',$titulo,1).'</row>';
    $xml.='<row r="2" ht="22" customHeight="1">'
      .cuadroAnualCeldaTexto('B2',$subtitulo,2).'</row>';
    $xml.='<row r="3" ht="'.$altoCabecera.'" customHeight="1">'
      .cuadroAnualCeldaTexto('A3','No.',3)
      .cuadroAnualCeldaTexto('B3','NOMBRES COMPLETOS',3);
    foreach($cabeceras as $pos=>$encabezado) {
        $ref=cuadroAnualColumna($pos+3).'3';
        // El texto visible dentro de la hoja siempre es el NOMBRE COMPLETO
        // de la asignatura. Las pestanas siguen identificando cada aula.
        // La asignatura de comportamiento conserva el diseño azul de cualquier otra
        // asignatura; solo la columna final COMPORTAMIENTO usa morado.
        $estiloEncabezado=3;
        $xml.=cuadroAnualCeldaTexto($ref,$encabezado,$estiloEncabezado);
    }
    $xml.=cuadroAnualCeldaTexto($colFin.'3','COMPORTAMIENTO',4).'</row>';
    foreach($estudiantes as $i=>$est) {
        $r=4+$i;
        $par=($i%2)===1;
        $xml.='<row r="'.$r.'" ht="25" customHeight="1">';
        $num=(int)($est['numero_lista']??0);
        $xml.=cuadroAnualCeldaNumero('A'.$r,(float)($num>0?$num:$i+1),$par?18:17);
        $nombre=trim((string)($est['apellidos']??'').' '.(string)($est['nombres']??''));
        $xml.=cuadroAnualCeldaTexto('B'.$r,cuadroAnualMayusculas($nombre),$par?6:5);
        $notas=$est['notas']??[];
        foreach($ofertas as $pos=>$oferta) {
            $c=cuadroAnualColumna($pos+3).$r;
            $oid=(int)($oferta['id']??0);
            $valor=$notas[$oid]??null;
            if($valor===null || $valor==='') {
                $xml.=cuadroAnualCeldaTexto($c,'',$par?16:15);
            } elseif(!empty($oferta['solo_visor_comportamiento'])) {
                // Usa el literal de la asignatura de comportamiento; no
                // agrega las valoraciones de otros docentes.
                $bajo=(bool)preg_match('/^[DEF][+-]$/',strtoupper((string)$valor));
                $xml.=cuadroAnualCeldaTexto($c,(string)$valor,$bajo?($par?20:19):($par?12:11));
            } elseif(is_numeric($valor)) {
                $n=(float)$valor;
                $xml.=cuadroAnualCeldaNumero($c,$n,$n<7?($par?10:9):($par?8:7));
            } else {
                // La letra B- abarca 6,50 a 7,49. No deducir aprobación desde la letra.
                $literalNota=trim((string)$valor);
                $esLiteralBajo=(bool)preg_match('/^[CDE][+-]$/',strtoupper($literalNota))
                    || (preg_match('/^([0-9]+(?:\.[0-9]+)?)\s*\([A-E][+-]\)$/',$literalNota,$coincidencia)
                        && (float)$coincidencia[1]<7.0);
                $real=$est['notas_numericas'][$oid]??null;
                if($real!==null && !empty($aula['resultados_cualitativos']))$esLiteralBajo=(float)$real<7.0;
                $estilo=$esLiteralBajo?($par?20:19):($par?12:11);
                $xml.=cuadroAnualCeldaTexto($c,(string)$valor,$estilo);
            }
        }
        $literal=(string)($est['comportamiento']??'');
        $xml.=cuadroAnualCeldaTexto($colFin.$r,$literal,$par?14:13);
        $xml.='</row>';
    }
    $xml.='</sheetData>';
    // Orden oficial de elementos CT_Worksheet: autoFilter ANTES de mergeCells.
    // Respeta el orden del exportador anual previamente funcional (Excel Windows).
    if($estudiantes)$xml.='<autoFilter ref="A3:'.$colFin.$ultimoRow.'"/>';
    $xml.='<mergeCells count="2"><mergeCell ref="B1:'.$colFin.'1"/><mergeCell ref="B2:'.$colFin.'2"/></mergeCells>';
    $xml.='<printOptions horizontalCentered="1"/><pageMargins left="0.25" right="0.25" top="0.45" bottom="0.45" header="0.2" footer="0.2"/>'
      .'<pageSetup paperSize="9" orientation="landscape" fitToWidth="1" fitToHeight="0"/>'
      .'</worksheet>';
    return $xml;
}
/**
 * Valor informativo para el reporte independiente "Supletorio - Excel".
 * Muestra los promedios ANUALES entre 0,00 y 6,99 inclusive, independientemente
 * de la condicion de promocion o del minimo oficial para rendir supletorios.
 * Solo muestra notas reales con los tres trimestres calificados; no transforma
 * las reglas ni los permisos del modulo academico de supletorios.
 */
function cuadroAnualNotaPendienteSupletorio(array $trimestres,array $config): ?float {
    if(!isset($trimestres[1],$trimestres[2],$trimestres[3]))return null;
    $resultado=calcularFinalAnual((float)$trimestres[1],(float)$trimestres[2],
        (float)$trimestres[3],null,$config);
    if(($resultado['promedio_tres']??null)===null)return null;
    $promedio=round((float)$resultado['promedio_tres'],2);
    return $promedio>=0.0 && $promedio<7.0 ? $promedio : null;
}

/** Escribe una nota real o un literal conservando los colores del cuadro anual. */
function cuadroAnualCeldaCalificacion(string $ref, $valor, bool $filaPar, bool $esComportamiento=false, ?float $notaNumerica=null):string {
    if($valor===null || $valor==='')return cuadroAnualCeldaTexto($ref,'',$filaPar?16:15);
    if($esComportamiento){
        $bajo=(bool)preg_match('/^[DEF][+-]$/',strtoupper((string)$valor));
        return cuadroAnualCeldaTexto($ref,(string)$valor,$bajo?($filaPar?20:19):($filaPar?12:11));
    }
    if(is_numeric($valor)){
        $nota=(float)$valor;
        return cuadroAnualCeldaNumero($ref,$nota,$nota<7?($filaPar?10:9):($filaPar?8:7));
    }
    $literal=trim((string)$valor);
    $bajo=(bool)preg_match('/^[CDE][+-]$/',strtoupper($literal))
        || (preg_match('/^([0-9]+(?:\.[0-9]+)?)\s*\([A-E][+-]\)$/',$literal,$coincidencia)
            && (float)$coincidencia[1]<7.0);
    if($notaNumerica!==null)$bajo=$notaNumerica<7.0;
    return cuadroAnualCeldaTexto($ref,$literal,$bajo?($filaPar?20:19):($filaPar?12:11));
}
/**
 * Cuadro ANUAL con cuatro o cinco columnas por asignatura numerica:
 * Trimestre 1, Trimestre 2, Trimestre 3, [Supletorio] y Final.
 * Las asignaturas de comportamiento muestran T1, T2, T3 y final cualitativo.
 * El cuadro trimestral mantiene su diseno historico de una nota por asignatura.
 */
function cuadroAnualCrearHojaFinal(array $aula,string $periodo,bool $incluirSupletorios=true):string {
    $ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main';
    $ofertas=$aula['ofertas']??[];
    $estudiantes=$aula['estudiantes']??[];
    $grupos=[];$colActual=3;
    foreach($ofertas as $oferta){
        $visor=!empty($oferta['solo_visor_comportamiento']);
        $ancho=$visor?4:($incluirSupletorios?5:4);
        $grupos[]=['oferta'=>$oferta,'primera'=>$colActual,'ultima'=>$colActual+$ancho-1,'visor'=>$visor];
        $colActual+=$ancho;
    }
    $colComportamiento=$colActual;
    $cantidadCols=$colComportamiento;
    // Cada hoja existe aunque el aula no tenga ofertas ni estudiantes.
    $ultimaCol=cuadroAnualColumna($cantidadCols);
    $ultimaFila=max(5,4+count($estudiantes));
    $titulo=cuadroAnualTituloAula($aula);
    $subtitulo='PERÍODO '.$periodo.'  |  '.(string)($aula['nivel']??'');
    if(!empty($aula['jornada']))$subtitulo.='  |  JORNADA '.cuadroAnualMayusculas((string)$aula['jornada']);
    $xml='<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        .'<worksheet xmlns="'.$ns.'">'
        .'<sheetPr><pageSetUpPr fitToPage="1"/></sheetPr>'
        .'<dimension ref="A1:'.$ultimaCol.$ultimaFila.'"/>'
        .'<sheetViews><sheetView workbookViewId="0" showGridLines="0">'
        .'<pane xSplit="2" ySplit="4" topLeftCell="C5" activePane="bottomRight" state="frozen"/>'
        .'<selection pane="bottomRight" activeCell="C5" sqref="C5"/>'
        .'</sheetView></sheetViews><sheetFormatPr defaultRowHeight="19"/>'
        .'<cols><col min="1" max="1" width="7" customWidth="1"/>'
        .'<col min="2" max="2" width="42" customWidth="1"/>';
    foreach($grupos as $grupo){
        $primera=$grupo['primera'];
        if($grupo['visor']){
            $xml.='<col min="'.$primera.'" max="'.($primera+3).'" width="15" customWidth="1"/>';
        }else{
            for($c=$primera;$c<=$grupo['ultima'];$c++){
                $ancho=($incluirSupletorios && $c===$primera+3)?16:13;
                $xml.='<col min="'.$c.'" max="'.$c.'" width="'.$ancho.'" customWidth="1"/>';
            }
        }
    }
    $xml.='<col min="'.$colComportamiento.'" max="'.$colComportamiento.'" width="29" customWidth="1"/></cols>';
    $xml.='<sheetData>';
    $xml.='<row r="1" ht="29" customHeight="1">'.cuadroAnualCeldaTexto('B1',$titulo,1).'</row>';
    $xml.='<row r="2" ht="22" customHeight="1">'.cuadroAnualCeldaTexto('B2',$subtitulo,2).'</row>';
    $xml.='<row r="3" ht="56" customHeight="1">'
        .cuadroAnualCeldaTexto('A3','LISTA',3)
        .cuadroAnualCeldaTexto('B3','ESTUDIANTES',3);
    foreach($grupos as $grupo){
        $referencia=cuadroAnualColumna($grupo['primera']).'3';
        $xml.=cuadroAnualCeldaTexto($referencia,cuadroAnualEncabezadoAsignatura($grupo['oferta']),3);
    }
    $xml.=cuadroAnualCeldaTexto($ultimaCol.'3','COMPORTAMIENTO',4).'</row>';
    $xml.='<row r="4" ht="30" customHeight="1">'
        .cuadroAnualCeldaTexto('A4','No.',2)
        .cuadroAnualCeldaTexto('B4','NOMBRES COMPLETOS',2);
    foreach($grupos as $grupo){
        $cabeceras=$grupo['visor']?['TRIMESTRE 1','TRIMESTRE 2','TRIMESTRE 3','FINAL']:($incluirSupletorios
            ?['TRIMESTRE 1','TRIMESTRE 2','TRIMESTRE 3','SUPLETORIO','FINAL']
            :['TRIMESTRE 1','TRIMESTRE 2','TRIMESTRE 3','FINAL']);
        foreach($cabeceras as $pos=>$nombre){
            $xml.=cuadroAnualCeldaTexto(cuadroAnualColumna($grupo['primera']+$pos).'4',$nombre,2);
        }
    }
    // El resumen de comportamiento del cuadro anual es la LETRA FINAL
    // de los tres trimestres, no un promedio de notas numericas.
    $xml.=cuadroAnualCeldaTexto($ultimaCol.'4','FINAL',4).'</row>';
    foreach($estudiantes as $i=>$est){
        $r=5+$i;
        $par=($i%2)===1;
        $xml.='<row r="'.$r.'" ht="25" customHeight="1">';
        $n=(int)($est['numero_lista']??0);
        $xml.=cuadroAnualCeldaNumero('A'.$r,(float)($n>0?$n:$i+1),$par?18:17);
        $nombre=trim((string)($est['apellidos']??'').' '.(string)($est['nombres']??''));
        $xml.=cuadroAnualCeldaTexto('B'.$r,cuadroAnualMayusculas($nombre),$par?6:5);
        $notas=$est['notas']??[];
        $detalle=$est['detalle_notas']??[];
        foreach($grupos as $grupo){
            $oid=(int)($grupo['oferta']['id']??0);
            $primera=$grupo['primera'];
            if($grupo['visor']){
                $registro=$detalle[$oid]??[];
                foreach(['t1','t2','t3','final'] as $j=>$campo) {
                    $celda=cuadroAnualColumna($primera+$j).$r;
                    $xml.=cuadroAnualCeldaCalificacion($celda,$registro[$campo]??null,$par,true);
                }
                continue;
            }
            $fila=$detalle[$oid]??[];
            $valores=[ $fila['t1']??null, $fila['t2']??null, $fila['t3']??null ];
            $real=$est['detalle_numerico'][$oid]??[];
            $campos=$incluirSupletorios?['t1','t2','t3','supletorio','final']:['t1','t2','t3','final'];
            if($incluirSupletorios)$valores[]=$fila['supletorio']??null;
            $valores[]=$fila['final']??($notas[$oid]??null);
            foreach($valores as $j=>$valor){
                $celda=cuadroAnualColumna($primera+$j).$r;
                $numero=$real[$campos[$j]]??null;
                $xml.=cuadroAnualCeldaCalificacion($celda,$valor,$par,false,$numero===null?null:(float)$numero);
            }
        }
        // La celda contiene la letra final; si falta un trimestre permanece vacia.
        $xml.=cuadroAnualCeldaTexto($ultimaCol.$r,(string)($est['comportamiento']??''),$par?14:13);
        $xml.='</row>';
    }
    $xml.='</sheetData>';
    if($estudiantes)$xml.='<autoFilter ref="A4:'.$ultimaCol.$ultimaFila.'"/>';
    $merges=['B1:'.$ultimaCol.'1','B2:'.$ultimaCol.'2'];
    foreach($grupos as $grupo){
        if($grupo['primera']!==$grupo['ultima']){
            $merges[]=cuadroAnualColumna($grupo['primera']).'3:'.cuadroAnualColumna($grupo['ultima']).'3';
        }
    }
    $xml.='<mergeCells count="'.count($merges).'">';
    foreach($merges as $rango)$xml.='<mergeCell ref="'.$rango.'"/>';
    $xml.='</mergeCells>';
    $xml.='<printOptions horizontalCentered="1"/>'
        .'<pageMargins left="0.25" right="0.25" top="0.45" bottom="0.45" header="0.2" footer="0.2"/>'
        .'<pageSetup paperSize="9" orientation="landscape" fitToWidth="1" fitToHeight="0"/>'
        .'</worksheet>';
    return $xml;
}

/** Construye un contenedor ZIP conforme a OPC sin usar PHP ZipArchive. */
function cuadroAnualZip(array $archivos): string {
    if(count($archivos)>500)throw new RuntimeException('Se ha superado el límite de hojas.');
    $local='';$central='';$cuenta=0;
    foreach($archivos as $nombre=>$data) {
        $nombre=(string)$nombre;$data=(string)$data;
        $tam=strlen($data);$len=strlen($nombre);
        if($tam>0x7FFFFFFF)throw new RuntimeException('El archivo Excel es demasiado grande.');
        $crc=crc32($data);
        $offset=strlen($local);
        $local.=pack('VvvvvvVVVvv',0x04034b50,20,2048,0,0,33,$crc,$tam,$tam,$len,0).$nombre.$data;
        $central.=pack('VvvvvvvVVVvvvvvVV',0x02014b50,20,20,2048,0,0,33,$crc,$tam,$tam,$len,0,0,0,0,0,$offset).$nombre;
        $cuenta++;
    }
    $centralLen=strlen($central);$centralOff=strlen($local);
    return $local.$central.pack('VvvvvVVv',0x06054b50,0,0,$cuenta,$cuenta,$centralLen,$centralOff,0);
}
/** @param array<int,array> $aulas */
function cuadroAnualGenerarXlsx(array $aulas,string $periodo,?int $trimestre=null,bool $soloSupletorios=false,bool $incluirSupletorios=true): string {
    if(!$aulas)throw new InvalidArgumentException('No hay aulas habilitadas para exportar.');
    if($soloSupletorios && $trimestre!==null){
        throw new InvalidArgumentException('No es posible mezclar trimestre y supletorio.');
    }
    if($trimestre!==null && ($trimestre<1 || $trimestre>3)){
        throw new InvalidArgumentException('Trimestre no valido.');
    }
    $ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main';
    $rel='http://schemas.openxmlformats.org/officeDocument/2006/relationships';
    $n=count($aulas);
    $tipos='<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
      .'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
      .'<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
      .'<Default Extension="xml" ContentType="application/xml"/>'
      .'<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
      .'<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
      .'<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
      .'<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>';
    $workbook='<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
      .'<workbook xmlns="'.$ns.'" xmlns:r="'.$rel.'"><bookViews><workbookView activeTab="0"/></bookViews><sheets>';
    $workbookRel='<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
      .'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">';
    $files=[];$nombres=[];$usados=[];
    foreach($aulas as $i=>$aula) {
        $idx=$i+1;
        $nombre=cuadroAnualNombreHoja($aula,$usados);
        $nombres[]=$nombre;
        $workbook.='<sheet name="'.cuadroAnualXml($nombre).'" sheetId="'.$idx.'" r:id="rId'.$idx.'"/>';
        $workbookRel.='<Relationship Id="rId'.$idx.'" Type="'.$rel.'/worksheet" Target="worksheets/sheet'.$idx.'.xml"/>';
        $tipos.='<Override PartName="/xl/worksheets/sheet'.$idx.'.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>';
        $files['xl/worksheets/sheet'.$idx.'.xml']=($trimestre===null && !$soloSupletorios)
            ?cuadroAnualCrearHojaFinal($aula,$periodo,$incluirSupletorios)
            :cuadroAnualCrearHoja($aula,$periodo,$trimestre,$soloSupletorios);
    }
    $workbook.='</sheets><calcPr calcId="191029"/></workbook>';
    $workbookRel.='<Relationship Id="rId'.($n+1).'" Type="'.$rel.'/styles" Target="styles.xml"/></Relationships>';
    $tipos.='</Types>';
    $appXml='<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
      .'<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"'
      .' xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
      .'<Application>SGA UNEDID</Application><HeadingPairs><vt:vector size="2" baseType="variant">'
      .'<vt:variant><vt:lpstr>Worksheets</vt:lpstr></vt:variant><vt:variant><vt:i4>'.$n.'</vt:i4></vt:variant>'
      .'</vt:vector></HeadingPairs><TitlesOfParts><vt:vector size="'.$n.'" baseType="lpstr">';
    foreach($nombres as $nombre)$appXml.='<vt:lpstr>'.cuadroAnualXml($nombre).'</vt:lpstr>';
    $appXml.='</vt:vector></TitlesOfParts></Properties>';
    $now=gmdate('Y-m-d\TH:i:s\Z');
    $core='<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
       .'<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"'
       .' xmlns:dc="http://purl.org/dc/elements/1.1/"'
       .' xmlns:dcterms="http://purl.org/dc/terms/"'
       .' xmlns:dcmitype="http://purl.org/dc/dcmitype/"'
       .' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
       .'<dc:creator>SGA UNEDID</dc:creator><cp:lastModifiedBy>SGA UNEDID</cp:lastModifiedBy>'
       .'<dcterms:created xsi:type="dcterms:W3CDTF">'.$now.'</dcterms:created>'
       .'</cp:coreProperties>';
    $rootRel='<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
      .'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
      .'<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
      .'<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
      .'<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
      .'</Relationships>';
    // El orden de los archivos no afecta su validez OOXML.
    $archive=['[Content_Types].xml'=>$tipos,'_rels/.rels'=>$rootRel,
       'docProps/app.xml'=>$appXml,'docProps/core.xml'=>$core,
       'xl/workbook.xml'=>$workbook,'xl/_rels/workbook.xml.rels'=>$workbookRel,
       'xl/styles.xml'=>cuadroAnualEstilos()];
    foreach($files as $name=>$bytes)$archive[$name]=$bytes;
    return cuadroAnualZip($archive);
}
