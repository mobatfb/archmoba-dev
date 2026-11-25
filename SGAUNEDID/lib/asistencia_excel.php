<?php
/** Excel XLSX de asistencia con el empaquetador OOXML del Cuadro Anual.
 * No requiere extension PHP ZipArchive ni dependencias de Composer.
 */
require_once __DIR__.'/cuadro_anual_excel.php';

function asistenciaExcelTexto($valor): string {
    $texto = (string)($valor ?? '');
    $texto = preg_replace('/[\x00-\x08\x0B\x0C\x0E-\x1F]/u', '', $texto) ?? '';
    return htmlspecialchars($texto, ENT_XML1 | ENT_QUOTES, 'UTF-8');
}

function asistenciaExcelColumna(int $i): string {
    $salida = '';
    do { $salida = chr(65 + (($i - 1) % 26)) . $salida; $i = intdiv($i - 1, 26); } while ($i > 0);
    return $salida;
}

/** Tipo t: texto seguro; n: número; f: fórmula con resultado numérico cacheado. */
function asistenciaExcelCelda(string $col, int $fila, $valor, int $estilo = 0, string $tipo = 't'): string {
    $ref = $col . $fila;
    if ($tipo === 'f') {
        [$formula, $cache] = $valor;
        return '<c r="'.$ref.'" s="'.$estilo.'"><f>'.asistenciaExcelTexto($formula).'</f><v>'.(float)$cache.'</v></c>';
    }
    if ($tipo === 'n') return '<c r="'.$ref.'" s="'.$estilo.'"><v>'.(float)$valor.'</v></c>';
    return '<c r="'.$ref.'" s="'.$estilo.'" t="inlineStr"><is><t xml:space="preserve">'.asistenciaExcelTexto($valor).'</t></is></c>';
}

function asistenciaExcelFila(int $numero, array $celdas, ?int $alto = null): string {
    $atributos = ' r="'.$numero.'"';
    if ($alto !== null) $atributos .= ' ht="'.$alto.'" customHeight="1"';
    return '<row'.$atributos.'>'.implode('', $celdas).'</row>';
}

function asistenciaExcelEstilos(): string {
    return <<<'XML'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
 <numFmts count="1"><numFmt numFmtId="165" formatCode="0.00%"/></numFmts>
 <fonts count="7">
  <font><sz val="11"/><name val="Calibri"/><color rgb="FF23344C"/></font>
  <font><b/><sz val="15"/><name val="Calibri"/><color rgb="FFFFFFFF"/></font>
  <font><b/><sz val="11"/><name val="Calibri"/><color rgb="FF173D6A"/></font>
  <font><b/><sz val="11"/><name val="Calibri"/><color rgb="FFFFFFFF"/></font>
  <font><b/><sz val="11"/><name val="Calibri"/><color rgb="FF0F7044"/></font>
  <font><b/><sz val="11"/><name val="Calibri"/><color rgb="FF9E2730"/></font>
  <font><b/><sz val="11"/><name val="Calibri"/><color rgb="FF805C10"/></font>
 </fonts>
 <fills count="9">
  <fill><patternFill patternType="none"/></fill>
  <fill><patternFill patternType="gray125"/></fill>
  <fill><patternFill patternType="solid"><fgColor rgb="FF0A2E61"/><bgColor indexed="64"/></patternFill></fill>
  <fill><patternFill patternType="solid"><fgColor rgb="FF1C5797"/><bgColor indexed="64"/></patternFill></fill>
  <fill><patternFill patternType="solid"><fgColor rgb="FFE6F6ED"/><bgColor indexed="64"/></patternFill></fill>
  <fill><patternFill patternType="solid"><fgColor rgb="FFFFE9E8"/><bgColor indexed="64"/></patternFill></fill>
  <fill><patternFill patternType="solid"><fgColor rgb="FFFFF2D9"/><bgColor indexed="64"/></patternFill></fill>
  <fill><patternFill patternType="solid"><fgColor rgb="FFEDF2F9"/><bgColor indexed="64"/></patternFill></fill>
  <fill><patternFill patternType="solid"><fgColor rgb="FFDCEAF7"/><bgColor indexed="64"/></patternFill></fill>
 </fills>
 <borders count="2"><border><left/><right/><top/><bottom/><diagonal/></border><border><left style="thin"><color rgb="FFD5E2EF"/></left><right style="thin"><color rgb="FFD5E2EF"/></right><top style="thin"><color rgb="FFD5E2EF"/></top><bottom style="thin"><color rgb="FFD5E2EF"/></bottom><diagonal/></border></borders>
 <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
 <cellXfs count="15">
  <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1"/>
  <xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"><alignment vertical="center"/></xf>
  <xf numFmtId="0" fontId="2" fillId="8" borderId="0" xfId="0" applyFont="1" applyFill="1"/>
  <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
  <xf numFmtId="0" fontId="3" fillId="3" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"><alignment vertical="center" horizontal="center" wrapText="1"/></xf>
  <xf numFmtId="0" fontId="4" fillId="4" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"/>
  <xf numFmtId="0" fontId="5" fillId="5" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"/>
  <xf numFmtId="0" fontId="6" fillId="6" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"/>
  <xf numFmtId="0" fontId="2" fillId="7" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"/>
  <xf numFmtId="0" fontId="0" fillId="7" borderId="1" xfId="0" applyFill="1" applyBorder="1"/>
  <xf numFmtId="0" fontId="2" fillId="8" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"/>
  <xf numFmtId="165" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1"/>
  <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1"><alignment horizontal="center"/></xf>
  <xf numFmtId="165" fontId="2" fillId="8" borderId="1" xfId="0" applyNumberFormat="1" applyFont="1" applyFill="1" applyBorder="1"/>
  <xf numFmtId="49" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1"/>
 </cellXfs>
 <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>
XML;
}

/** @return array{archivo:string,resumen:array} */
function generarExcelAsistencia(array $oferta, array $sesion, array $estudiantes): array {
    $fecha=(string)$sesion['fecha'];
    $curso=trim(($oferta['nivel']??'').' · '.($oferta['aula']??'').' '.($oferta['paralelo']??''));
    $docente=trim(($oferta['docente_apellidos']??'').' '.($oferta['docente_nombres']??''));
    $nombres=['presente'=>'Presente','ausente'=>'Ausente','atraso'=>'Atraso','justificado'=>'Justificado','sin_registrar'=>'Sin registrar'];
    $estilos=['presente'=>5,'ausente'=>6,'atraso'=>7,'justificado'=>8,'sin_registrar'=>9];
    $cuenta=array_fill_keys(array_keys($nombres),0);
    $cuerpo=[];
    $cuerpo[]=asistenciaExcelFila(1,[asistenciaExcelCelda('A',1,'SGA UNEDID · UNIDAD EDUCATIVA DE INICIACIÓN Y DESARROLLO DEPORTIVO DEL AZUAY',1)],31);
    $cuerpo[]=asistenciaExcelFila(2,[asistenciaExcelCelda('A',2,'REGISTRO DE ASISTENCIA · '.date('d/m/Y',strtotime($fecha)),2)],27);
    $metadatos=[3=>['Asignatura',$oferta['asignatura']??''],4=>['Curso / paralelo',$curso],5=>['Período',$oferta['periodo']??''],6=>['Docente',$docente],7=>['Tema / actividad',$sesion['tema']??'']];
    foreach($metadatos as $r=>$m)$cuerpo[]=asistenciaExcelFila($r,[asistenciaExcelCelda('A',$r,$m[0],2),asistenciaExcelCelda('C',$r,$m[1],3)]);
    $cols=['No.','Cédula','Estudiante','Estado','Observación'];
    $c=[];foreach($cols as $i=>$texto)$c[]=asistenciaExcelCelda(asistenciaExcelColumna($i+1),8,$texto,4);
    $cuerpo[]=asistenciaExcelFila(8,$c,27);
    foreach($estudiantes as $i=>$est){
        $r=$i+9;
        $estado=(string)($est['estado']??'');
        if(!isset($nombres[$estado]))$estado='sin_registrar';
        $cuenta[$estado]++;
        $cuerpo[]=asistenciaExcelFila($r,[
            asistenciaExcelCelda('A',$r,($est['numero_lista']??null)===null?($i+1):(int)$est['numero_lista'],12,'n'),
            asistenciaExcelCelda('B',$r,$est['cedula']??'',14),
            asistenciaExcelCelda('C',$r,trim(($est['apellidos']??'').' '.($est['nombres']??'')),0),
            asistenciaExcelCelda('D',$r,$nombres[$estado],$estilos[$estado]),
            asistenciaExcelCelda('E',$r,$est['observacion']??'',0),
        ],23);
    }
    $ultimo=max(9,8+count($estudiantes));
    if(!$estudiantes)$cuerpo[]=asistenciaExcelFila(9,[asistenciaExcelCelda('C',9,'No hay estudiantes matriculados.',3)]);
    $estR=implode('',$cuerpo);
    $merges=['A1:E1','A2:E2'];
    for($filaMeta=3;$filaMeta<=7;$filaMeta++){ $merges[]='A'.$filaMeta.':B'.$filaMeta; $merges[]='C'.$filaMeta.':E'.$filaMeta; }
    $mergeXml='<mergeCells count="'.count($merges).'">';foreach($merges as $m)$mergeXml.='<mergeCell ref="'.$m.'"/>';$mergeXml.='</mergeCells>';
    $sheet1='<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
      .'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
      .'<sheetPr><pageSetUpPr fitToPage="1"/></sheetPr>'
      .'<dimension ref="A1:E'.$ultimo.'"/>'
      .'<sheetViews><sheetView workbookViewId="0" showGridLines="0">'
      .'<selection activeCell="A1" sqref="A1"/></sheetView></sheetViews>'
      .'<sheetFormatPr defaultRowHeight="20"/><cols><col min="1" max="1" width="8" customWidth="1"/>'
      .'<col min="2" max="2" width="19" customWidth="1"/><col min="3" max="3" width="48" customWidth="1"/>'
      .'<col min="4" max="4" width="18" customWidth="1"/><col min="5" max="5" width="58" customWidth="1"/></cols>'
      // OOXML: autoFilter MUST precede mergeCells (CT_Worksheet sequence).
      // Excel for Windows repairs/rejects the file when these are reversed.
      .'<sheetData>'.$estR.'</sheetData><autoFilter ref="A8:E'.$ultimo.'"/>'.$mergeXml
      .'<printOptions horizontalCentered="1"/>'
      .'<pageMargins left="0.25" right="0.25" top="0.5" bottom="0.5" header="0.2" footer="0.2"/>'
      .'<pageSetup orientation="landscape" paperSize="9" fitToWidth="1"/></worksheet>';

    $resumen=[];
    $resumen[]=asistenciaExcelFila(1,[asistenciaExcelCelda('A',1,'RESUMEN DE ASISTENCIA',1)],31);
    $resumen[]=asistenciaExcelFila(2,[asistenciaExcelCelda('A',2,(string)($oferta['asignatura']??''),2)]);
    $resumen[]=asistenciaExcelFila(3,[asistenciaExcelCelda('A',3,'Curso: '.$curso,3)]);
    $resumen[]=asistenciaExcelFila(4,[asistenciaExcelCelda('A',4,'Período: '.($oferta['periodo']??''),3)]);
    $resumen[]=asistenciaExcelFila(5,[asistenciaExcelCelda('A',5,'Fecha: '.date('d/m/Y',strtotime($fecha)),3)]);
    $resumen[]=asistenciaExcelFila(6,[asistenciaExcelCelda('A',6,'Estado',4),asistenciaExcelCelda('B',6,'Cantidad',4),asistenciaExcelCelda('C',6,'Porcentaje',4)],26);
    $total=count($estudiantes);
    $claveEstados=array_keys($nombres);
    $rangos='$D$9:$D$'.$ultimo;
    foreach($claveEstados as $i=>$estado){
        $r=$i+7;$cantidad=$cuenta[$estado];
        $est=$estilos[$estado];
        $resumen[]=asistenciaExcelFila($r,[
            asistenciaExcelCelda('A',$r,$nombres[$estado],$est),
            // El informe refleja el estado guardado. Evitar fórmulas dinámicas en el XLSX
            // evita incompatibilidades de recálculo al abrirlo en Excel de escritorio.
            asistenciaExcelCelda('B',$r,$cantidad,12,'n'),
            asistenciaExcelCelda('C',$r,$total ? $cantidad/$total : 0.0,11,'n'),
        ],23);
    }
    $resumen[]=asistenciaExcelFila(12,[
        asistenciaExcelCelda('A',12,'TOTAL',10),
        asistenciaExcelCelda('B',12,$total,10,'n'),
        asistenciaExcelCelda('C',12,$total?1.0:0.0,13,'n'),
    ],25);
    $resumen[]=asistenciaExcelFila(14,[asistenciaExcelCelda('A',14,'Solo se incluye el registro guardado para la fecha seleccionada.',3)]);
    $resumen[]=asistenciaExcelFila(15,[asistenciaExcelCelda('A',15,'Observaciones generales: '.($sesion['observaciones']??''),3)]);
    $sheet2='<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
      .'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
      .'<dimension ref="A1:C15"/><sheetViews><sheetView workbookViewId="0"/></sheetViews>'
      .'<sheetFormatPr defaultRowHeight="20"/><cols><col min="1" max="1" width="52" customWidth="1"/>'
      .'<col min="2" max="2" width="19" customWidth="1"/><col min="3" max="3" width="21" customWidth="1"/></cols>'
      .'<sheetData>'.implode('',$resumen).'</sheetData><mergeCells count="7"><mergeCell ref="A1:C1"/>'
      .'<mergeCell ref="A2:C2"/><mergeCell ref="A3:C3"/><mergeCell ref="A4:C4"/><mergeCell ref="A5:C5"/>'
      .'<mergeCell ref="A14:C14"/><mergeCell ref="A15:C15"/></mergeCells>'
      .'</worksheet>';

    $contenidoTipos='<?xml version="1.0" encoding="UTF-8"?>'
       .'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
       .'<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
       .'<Default Extension="xml" ContentType="application/xml"/>'
       .'<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
       .'<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
       .'<Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
       .'<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
       .'<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
       .'<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
       .'</Types>';
    $rels='<?xml version="1.0" encoding="UTF-8"?>'
       .'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
       .'<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
       .'<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
       .'<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
       .'</Relationships>';
    $book='<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
       .'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
       .'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
       .'<bookViews><workbookView activeTab="0"/></bookViews>'
       .'<sheets><sheet name="Registro" sheetId="1" r:id="rId1"/>'
       .'<sheet name="Resumen" sheetId="2" r:id="rId2"/></sheets>'
       .'</workbook>';
    $bookRels='<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
       .'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
       .'<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
       .'<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>'
       .'<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
       .'</Relationships>';
    $creado=gmdate('Y-m-d\TH:i:s\Z');
    $core='<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
       .'<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
       .'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
       .'<dc:creator>SGA UNEDID</dc:creator><dcterms:created xsi:type="dcterms:W3CDTF">'.$creado.'</dcterms:created>'
       .'</cp:coreProperties>';
    $app='<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
       .'<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
       .'<Application>SGA UNEDID</Application></Properties>';

    $partes=[
        '[Content_Types].xml'=>$contenidoTipos,
        '_rels/.rels'=>$rels,
        'docProps/core.xml'=>$core,
        'docProps/app.xml'=>$app,
        'xl/workbook.xml'=>$book,
        'xl/_rels/workbook.xml.rels'=>$bookRels,
        'xl/styles.xml'=>asistenciaExcelEstilos(),
        'xl/worksheets/sheet1.xml'=>$sheet1,
        'xl/worksheets/sheet2.xml'=>$sheet2,
    ];
    $bytes=cuadroAnualZip($partes);
    $tmp=tempnam(sys_get_temp_dir(),'sga_asis_');
    if($tmp===false)throw new RuntimeException('No se pudo crear el archivo temporal XLSX.');
    try {
        if(file_put_contents($tmp,$bytes,LOCK_EX)!==strlen($bytes)) {
            throw new RuntimeException('No se pudo escribir el archivo XLSX completo.');
        }
        return ['archivo'=>$tmp,'resumen'=>$cuenta];
    } catch(Throwable $e) {
        @unlink($tmp);
        throw $e;
    }
}
