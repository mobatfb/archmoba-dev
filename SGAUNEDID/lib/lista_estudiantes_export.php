<?php
/** Lista de estudiantes: Excel XLSX validado y PDF institucional.
 * Usa el MISMO motor OOXML del Cuadro Anual, sin extension PHP ZipArchive.
 */
require_once __DIR__.'/simple_pdf.php';
require_once __DIR__.'/cuadro_anual_excel.php';

function listaEstudiantesCurso(array $oferta): string {
    return trim((string)($oferta['nivel']??'').' · '.(string)($oferta['aula']??'').' '.(string)($oferta['paralelo']??''));
}

/** Coloca el contenido en las celdas reales A1:E..., con estilos y encabezados visibles. */
function listaEstudiantesEstilosXlsx(): string {
    $base=cuadroAnualEstilos();
    return preg_replace_callback('/<cellXfs count="(\d+)">(.*?)<\/cellXfs>/s',
        static function(array $m): string {
            $estiloTexto = static function(int $fill): string {
                return '<xf numFmtId="49" fontId="0" fillId="'.$fill.'" borderId="1"'
                    .' xfId="0" applyFont="1" applyFill="1" applyBorder="1"'
                    .' applyNumberFormat="1" applyAlignment="1"'
                    .'><alignment horizontal="left" vertical="center" wrapText="1"/></xf>';
            };
            return '<cellXfs count="'.((int)$m[1]+2).'">'
                .$m[2].$estiloTexto(0).$estiloTexto(3).'</cellXfs>';
        },$base,1) ?? $base;
}

function listaEstudiantesCrearHojaXlsx(array $oferta, array $alumnos): string {
    $ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main';
    $ultimaFila=max(9,8+count($alumnos));
    // El Cuadro Anual puede incorporar estilos nuevos; no fijar indices de celda.
    preg_match('/<cellXfs count="(\d+)">/',cuadroAnualEstilos(),$estilosEncontrados);
    $indiceFormatoTexto=(int)($estilosEncontrados[1]??0);
    $titulos=[
        'LISTA DE ESTUDIANTES',
        'UNIDAD EDUCATIVA DE INICIACIÓN Y DESARROLLO DEPORTIVO DEL AZUAY',
        'PERÍODO ACADÉMICO: '.(string)($oferta['periodo']??''),
        'CURSO / PARALELO: '.listaEstudiantesCurso($oferta),
        'ASIGNATURA: '.(string)($oferta['asignatura']??''),
        'DOCENTE: '.trim((string)($oferta['docente_apellidos']??'').' '.(string)($oferta['docente_nombres']??'')),
        'ESTUDIANTES MATRICULADOS: '.count($alumnos),
    ];
    $xml='<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        .'<worksheet xmlns="'.$ns.'">'
        .'<sheetPr><pageSetUpPr fitToPage="1"/></sheetPr>'
        .'<dimension ref="A1:E'.$ultimaFila.'"/>'
        .'<sheetViews><sheetView workbookViewId="0" showGridLines="0">'
        .'<selection activeCell="A1" sqref="A1"/>'
        .'</sheetView></sheetViews>'
        .'<sheetFormatPr defaultRowHeight="21"/>'
        .'<cols>'
        .'<col min="1" max="1" width="9" customWidth="1"/>'
        .'<col min="2" max="2" width="19" customWidth="1"/>'
        .'<col min="3" max="3" width="33" customWidth="1"/>'
        .'<col min="4" max="4" width="32" customWidth="1"/>'
        .'<col min="5" max="5" width="43" customWidth="1"/>'
        .'</cols><sheetData>';
    foreach($titulos as $i=>$texto) {
        $r=$i+1;
        $estilo=$r===1?1:($r===2?6:($r%2===0?6:5));
        $altura=($r===1?32:($r===2?27:24));
        $xml.='<row r="'.$r.'" ht="'.$altura.'" customHeight="1">'
            .cuadroAnualCeldaTexto('A'.$r,$texto,$estilo).'</row>';
    }
    $xml.='<row r="8" ht="31" customHeight="1">';
    foreach(['No.','CÉDULA','APELLIDOS','NOMBRES','CORREO'] as $i=>$col) {
        $xml.=cuadroAnualCeldaTexto(chr(65+$i).'8',$col,3);
    }
    $xml.='</row>';
    foreach($alumnos as $i=>$alumno) {
        $r=9+$i;
        $par=($i%2)===1;
        $estiloTexto=$par?6:5;
        $estiloNumero=$par?18:17;
        $numero=$alumno['numero_lista']??null;
        $xml.='<row r="'.$r.'" ht="26" customHeight="1">';
        if($numero===null || $numero==='') {
            $xml.=cuadroAnualCeldaTexto('A'.$r,'',$estiloTexto);
        } else {
            // La columna No. es numerica sin decimales.
            $xml.='<c r="A'.$r.'" s="'.$estiloNumero.'"><v>'.(int)$numero.'</v></c>';
        }
        // La cedula se escribe como TEXTO, para no perder los ceros iniciales.
        // Texto explícito de Excel (formato @), además del tipo inlineStr.
        $xml.=cuadroAnualCeldaTexto('B'.$r,(string)($alumno['cedula']??''),($indiceFormatoTexto+($par?1:0)));
        $xml.=cuadroAnualCeldaTexto('C'.$r,(string)($alumno['apellidos']??''),$estiloTexto);
        $xml.=cuadroAnualCeldaTexto('D'.$r,(string)($alumno['nombres']??''),$estiloTexto);
        $xml.=cuadroAnualCeldaTexto('E'.$r,(string)($alumno['correo']??''),$estiloTexto);
        $xml.='</row>';
    }
    if(!$alumnos) {
        $xml.='<row r="9" ht="29" customHeight="1">'
            .cuadroAnualCeldaTexto('A9','No hay estudiantes matriculados en este curso.',5).'</row>';
    }
    $xml.='</sheetData>';
    if($alumnos) $xml.='<autoFilter ref="A8:E'.$ultimaFila.'"/>';
    $xml.='<mergeCells count="'.(7+($alumnos?0:1)).'">';
    for($r=1;$r<=7;$r++) $xml.='<mergeCell ref="A'.$r.':E'.$r.'"/>';
    if(!$alumnos) $xml.='<mergeCell ref="A9:E9"/>';
    $xml.='</mergeCells>'
        .'<printOptions horizontalCentered="1"/>'
        .'<pageMargins left="0.32" right="0.32" top="0.4" bottom="0.4" header="0.2" footer="0.2"/>'
        .'<pageSetup paperSize="9" orientation="landscape" fitToWidth="1" fitToHeight="0"/>'
        .'</worksheet>';
    return $xml;
}

/** Paquete XLSX con la misma configuracion y empaquetador del Cuadro Anual. */
function listaEstudiantesExcel(array $oferta,array $alumnos): string {
    $ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main';
    $rel='http://schemas.openxmlformats.org/officeDocument/2006/relationships';
    $sheet=listaEstudiantesCrearHojaXlsx($oferta,$alumnos);
    $types='<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        .'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        .'<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        .'<Default Extension="xml" ContentType="application/xml"/>'
        .'<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        .'<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        .'<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        .'<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        .'<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
        .'</Types>';
    $book='<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        .'<workbook xmlns="'.$ns.'" xmlns:r="'.$rel.'">'
        .'<bookViews><workbookView activeTab="0"/></bookViews>'
        .'<sheets><sheet name="Lista de estudiantes" sheetId="1" r:id="rId1"/></sheets>'
        .'<calcPr calcId="191029"/></workbook>';
    $bookRels='<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        .'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        .'<Relationship Id="rId1" Type="'.$rel.'/worksheet" Target="worksheets/sheet1.xml"/>'
        .'<Relationship Id="rId2" Type="'.$rel.'/styles" Target="styles.xml"/>'
        .'</Relationships>';
    $rootRels='<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        .'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        .'<Relationship Id="rId1" Type="'.$rel.'/officeDocument" Target="xl/workbook.xml"/>'
        .'<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
        .'<Relationship Id="rId3" Type="'.$rel.'/extended-properties" Target="docProps/app.xml"/>'
        .'</Relationships>';
    $app='<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        .'<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"'
        .' xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
        .'<Application>SGA UNEDID</Application><HeadingPairs><vt:vector size="2" baseType="variant">'
        .'<vt:variant><vt:lpstr>Worksheets</vt:lpstr></vt:variant><vt:variant><vt:i4>1</vt:i4></vt:variant>'
        .'</vt:vector></HeadingPairs><TitlesOfParts><vt:vector size="1" baseType="lpstr">'
        .'<vt:lpstr>Lista de estudiantes</vt:lpstr></vt:vector></TitlesOfParts></Properties>';
    $now=gmdate('Y-m-d\TH:i:s\Z');
    $core='<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        .'<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"'
        .' xmlns:dc="http://purl.org/dc/elements/1.1/"'
        .' xmlns:dcterms="http://purl.org/dc/terms/"'
        .' xmlns:dcmitype="http://purl.org/dc/dcmitype/"'
        .' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        .'<dc:creator>SGA UNEDID</dc:creator>'
        .'<dcterms:created xsi:type="dcterms:W3CDTF">'.$now.'</dcterms:created>'
        .'</cp:coreProperties>';
    return cuadroAnualZip([
        '[Content_Types].xml'=>$types,
        '_rels/.rels'=>$rootRels,
        'docProps/app.xml'=>$app,
        'docProps/core.xml'=>$core,
        'xl/workbook.xml'=>$book,
        'xl/_rels/workbook.xml.rels'=>$bookRels,
        'xl/styles.xml'=>listaEstudiantesEstilosXlsx(),
        'xl/worksheets/sheet1.xml'=>$sheet,
    ]);
}

function listaEstudiantesPdf(array $oferta,array $alumnos): SimplePdf {
    $config=require __DIR__.'/../config/reportes_institucional.php';
    $pdf=new SimplePdf();
    $numeroPagina=0;
    $ancho=[36,87,271,133]; // 527 puntos, dentro de hoja A4.
    $cabecera=function() use($pdf,$oferta,$config,&$numeroPagina,$ancho,$alumnos):float {
        ++$numeroPagina;
        $pdf->addPage();
        $logo=(string)($config['escudo_ecuador']??'');
        if($logo!=='') $pdf->imageJpeg($logo,39,744,112,61);
        $pdf->rightText(558,785,'Ministerio de Educación',13.0,true,'#194B73');
        $pdf->rightText(558,769,'UNEDID - Cuenca',8.1,false,'#64758A');
        $pdf->centerText(297,711,'LISTA DE ESTUDIANTES',13.2,true,'#143E70');
        $inst=(string)($config['institucion']??'UNEDID');
        $y=687;
        foreach(array_slice($pdf->wrapText(strtr(strtoupper($inst), ['á'=>'Á','é'=>'É','í'=>'Í','ó'=>'Ó','ú'=>'Ú','ñ'=>'Ñ','ü'=>'Ü']),470,9.1,true),0,3) as $linea){
            $pdf->centerText(297,$y,$linea,9.1,true,'#28323E');$y-=14;
        }
        $pdf->textColor(38,632,'CÓDIGO AMIE:',8.4,true,'#253950');
        $pdf->textColor(137,632,(string)($config['codigo_amie']??''),8.4,false,'#253950');
        $pdf->textColor(333,632,'PERÍODO:',8.4,true,'#253950');
        $pdf->textColor(405,632,(string)($oferta['periodo']??''),8.4,false,'#253950');
        $pdf->textColor(38,608,'CURSO / PARALELO:',8.4,true,'#253950');
        $pdf->textColor(171,608,$pdf->fitText(listaEstudiantesCurso($oferta),380,8.5),8.5,false,'#253950');
        $pdf->textColor(38,586,'ASIGNATURA:',8.4,true,'#253950');
        $pdf->textColor(132,586,$pdf->fitText((string)($oferta['asignatura']??''),420,8.2),8.2,false,'#253950');
        $docente=trim((string)($oferta['docente_apellidos']??'').' '.(string)($oferta['docente_nombres']??''));
        $pdf->textColor(38,565,'DOCENTE:',8.4,true,'#253950');
        $pdf->textColor(113,565,$pdf->fitText($docente,435,8.2),8.2,false,'#253950');
        $pdf->textColor(38,543,'TOTAL DE ESTUDIANTES:',8.4,true,'#253950');
        $pdf->textColor(206,543,(string)count($alumnos),8.4,true,'#253950');
        $columnas=['No.','CÉDULA','APELLIDOS Y NOMBRES','CORREO'];
        $x=38.0;$y=519.0;
        foreach($columnas as $i=>$texto){
            $pdf->fillRect($x,$y-27,$ancho[$i],27,'#DCEAF4','#B8CADB',.6);
            $pdf->centerText($x+$ancho[$i]/2,$y-17,$texto,7.6,true,'#153F61');
            $x+=$ancho[$i];
        }
        $pdf->rightText(558,38,'Página '.$numeroPagina,8,false,'#617487');
        return $y-27;
    };
    $y=$cabecera();
    foreach($alumnos as $idx=>$r){
        $nombre=trim((string)($r['apellidos']??'').' '.(string)($r['nombres']??''));
        $lineas=array_slice($pdf->wrapText($nombre,259,8.1,true),0,3);
        $correo=(string)($r['correo']??'');
        $h=max(27,count($lineas)*12+9);
        if($y-$h<66) $y=$cabecera();
        $fill=$idx%2===0?'#FFFFFF':'#F3F7FB';
        $x=38.0;
        foreach($ancho as $w){$pdf->fillRect($x,$y-$h,$w,$h,$fill,'#CDD9E5',.45);$x+=$w;}
        $num=$r['numero_lista']===null?'—':(string)$r['numero_lista'];
        $pdf->centerText(38+$ancho[0]/2,$y-$h/2-3,$num,8.2,false,'#253950');
        $pdf->centerText(38+$ancho[0]+$ancho[1]/2,$y-$h/2-3,(string)($r['cedula']??''),7.7,false,'#253950');
        $x=38+$ancho[0]+$ancho[1]+6;
        foreach($lineas as $j=>$linea) $pdf->textColor($x,$y-14-$j*12,$linea,8.1,$j===0,'#253950');
        $correo=$pdf->fitText($correo,$ancho[3]-8,7.2);
        $pdf->textColor(38+$ancho[0]+$ancho[1]+$ancho[2]+4,$y-$h/2-3,$correo,7.2,false,'#314860');
        $y-=$h;
    }
    if(!$alumnos) $pdf->textColor(42,$y-20,'No existen estudiantes matriculados en este curso.',9,false,'#52677F');
    return $pdf;
}
