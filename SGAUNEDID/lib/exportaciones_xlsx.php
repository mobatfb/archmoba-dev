<?php
/**
 * Exportador XLSX compartido para tablas dinamicas.
 * PHP 8.1 sin ZipArchive, sin DOM y sin dependencias externas.
 * Genera OOXML estricto (autofiltro ANTES de celdas combinadas), sin paneles bloqueados.
 */
require_once __DIR__.'/cuadro_anual_excel.php';

function sgaXlsxCelda(string $ref, $valor, int $estilo=4): string {
    if($valor===null||$valor==='')return '<c r="'.$ref.'" s="'.$estilo.'" t="inlineStr"><is><t></t></is></c>';
    if(is_int($valor)||is_float($valor)){
        $numero=is_finite((float)$valor)?number_format((float)$valor,6,'.',''): '0';
        $numero=rtrim(rtrim($numero,'0'),'.');
        if($numero==='')$numero='0';
        return '<c r="'.$ref.'" s="'.($estilo===5?7:6).'"><v>'.$numero.'</v></c>';
    }
    // Las cedulas y demas identificadores siempre quedan como texto.
    return '<c r="'.$ref.'" s="'.$estilo.'" t="inlineStr"><is><t xml:space="preserve">'
      .cuadroAnualXml((string)$valor).'</t></is></c>';
}
function sgaXlsxEstilos():string {
    return <<<'XML'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<numFmts count="1"><numFmt numFmtId="164" formatCode="0.00"/></numFmts>
<fonts count="3"><font><sz val="10"/><name val="Calibri"/><color rgb="FF23374D"/></font>
<font><b/><sz val="12"/><name val="Calibri"/><color rgb="FFFFFFFF"/></font>
<font><b/><sz val="10"/><name val="Calibri"/><color rgb="FF123A5F"/></font></fonts>
<fills count="4"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FF002F6C"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFEFF5FC"/></patternFill></fill></fills>
<borders count="2"><border><left/><right/><top/><bottom/><diagonal/></border>
<border><left style="thin"><color rgb="FFD4E1EE"/></left><right style="thin"><color rgb="FFD4E1EE"/></right><top style="thin"><color rgb="FFD4E1EE"/></top><bottom style="thin"><color rgb="FFD4E1EE"/></bottom><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="8">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"><alignment vertical="center"/></xf>
<xf numFmtId="0" fontId="2" fillId="3" borderId="0" xfId="0" applyFont="1" applyFill="1"><alignment vertical="center"/></xf>
<xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"><alignment vertical="center" wrapText="1"/></xf>
<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1"><alignment vertical="center" wrapText="1"/></xf>
<xf numFmtId="0" fontId="0" fillId="3" borderId="1" xfId="0" applyFill="1" applyBorder="1"><alignment vertical="center" wrapText="1"/></xf>
<xf numFmtId="164" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyNumberFormat="1"><alignment vertical="center" horizontal="center"/></xf>
<xf numFmtId="164" fontId="0" fillId="3" borderId="1" xfId="0" applyFill="1" applyBorder="1" applyNumberFormat="1"><alignment vertical="center" horizontal="center"/></xf>
</cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>
XML;
}
/** @param array{nombre:string,titulo:string,subtitulo?:string,nota?:string,cabeceras:array,filas:array,anchos?:array} $hoja */
function sgaXlsxHoja(array $hoja):string {
    $headers=$hoja['cabeceras'];$datos=$hoja['filas'];$columnas=count($headers);
    if($columnas<1||$columnas>300)throw new DomainException('La tabla contiene demasiadas columnas.');
    if(count($datos)>50000)throw new DomainException('La tabla contiene demasiadas filas.');
    $ultimaCol=cuadroAnualColumna($columnas);$ultimaFila=max(4,4+count($datos));
    $xml='<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
      .'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
      .'<dimension ref="A1:'.$ultimaCol.$ultimaFila.'"/>'
      .'<sheetViews><sheetView showGridLines="0" workbookViewId="0"/></sheetViews>'
      .'<sheetFormatPr defaultRowHeight="17"/>'
      .'<cols>';
    foreach($headers as $i=>$h){
        $num=$i+1;$ancho=(float)($hoja['anchos'][$i]??(($i===2)?32:($i<3?17:16)));
        $ancho=max(10,min(47,$ancho));
        $xml.='<col min="'.$num.'" max="'.$num.'" width="'.number_format($ancho,1,'.','').'" customWidth="1"/>';
    }
    $xml.='</cols><sheetData>';
    $xml.='<row r="1" ht="30" customHeight="1">'.sgaXlsxCelda('A1',$hoja['titulo'],1).'</row>';
    $xml.='<row r="2" ht="23" customHeight="1">'.sgaXlsxCelda('A2',$hoja['subtitulo']??'',2).'</row>';
    $xml.='<row r="3" ht="23" customHeight="1">'.sgaXlsxCelda('A3',$hoja['nota']??'',2).'</row>';
    $xml.='<row r="4" ht="34" customHeight="1">';
    foreach($headers as $i=>$cabecera)$xml.=sgaXlsxCelda(cuadroAnualColumna($i+1).'4',(string)$cabecera,3);
    $xml.='</row>';
    foreach($datos as $i=>$datosFila){
        $numeroFila=5+$i;$estilo=($i%2===0)?4:5;
        $xml.='<row r="'.$numeroFila.'" ht="21" customHeight="1">';
        for($c=0;$c<$columnas;$c++){
            $dato=$datosFila[$c]??null;
            $xml.=sgaXlsxCelda(cuadroAnualColumna($c+1).$numeroFila,$dato,$estilo);
        }
        $xml.='</row>';
    }
    $xml.='</sheetData>';
    // El orden de estos elementos es parte de la especificacion XLSX (Excel Windows).
    $xml.='<autoFilter ref="A4:'.$ultimaCol.$ultimaFila.'"/>';
    if($columnas>1)$xml.='<mergeCells count="3"><mergeCell ref="A1:'.$ultimaCol.'1"/>'
      .'<mergeCell ref="A2:'.$ultimaCol.'2"/><mergeCell ref="A3:'.$ultimaCol.'3"/></mergeCells>';
    $xml.='<printOptions horizontalCentered="1"/>'
      .'<pageMargins left="0.25" right="0.25" top="0.45" bottom="0.45" header="0.2" footer="0.2"/>'
      .'<pageSetup paperSize="9" orientation="landscape" fitToWidth="1" fitToHeight="0"/>'
      .'</worksheet>';
    return $xml;
}
/** Un solo libro dinamico, sin limitacion de 40 estudiantes. */
function sgaXlsxGenerar(array $hojas):string {
    if(!$hojas||count($hojas)>100)throw new DomainException('No hay hojas validas para exportar.');
    $n=count($hojas);$mainNs='http://schemas.openxmlformats.org/spreadsheetml/2006/main';
    $relsNs='http://schemas.openxmlformats.org/officeDocument/2006/relationships';
    $content='<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
      .'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
      .'<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
      .'<Default Extension="xml" ContentType="application/xml"/>'
      .'<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
      .'<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
      .'<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
      .'<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>';
    $workbook='<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
      .'<workbook xmlns="'.$mainNs.'" xmlns:r="'.$relsNs.'"><bookViews><workbookView activeTab="0"/></bookViews><sheets>';
    $workRels='<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
      .'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">';
    $partes=[];$nombres=[];$vistos=[];
    foreach(array_values($hojas) as $i=>$hoja){
        $j=$i+1;$nombre=trim(preg_replace('/[\[\]:*?\\\\\/]/u','',(string)($hoja['nombre']??''))??'');
        $nombre=cuadroAnualCortar($nombre?:'Hoja'.$j,28);
        $original=$nombre;$intentos=2;
        while(isset($vistos[strtolower($nombre)])){$sufijo='-'.$intentos++;$nombre=cuadroAnualCortar($original,31-strlen($sufijo)).$sufijo;}
        $vistos[strtolower($nombre)]=true;$nombres[]=$nombre;
        $workbook.='<sheet name="'.cuadroAnualXml($nombre).'" sheetId="'.$j.'" r:id="rId'.$j.'"/>';
        $workRels.='<Relationship Id="rId'.$j.'" Type="'.$relsNs.'/worksheet" Target="worksheets/sheet'.$j.'.xml"/>';
        $content.='<Override PartName="/xl/worksheets/sheet'.$j.'.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>';
        $partes['xl/worksheets/sheet'.$j.'.xml']=sgaXlsxHoja($hoja);
    }
    $workbook.='</sheets><calcPr calcId="191029"/></workbook>';
    $workRels.='<Relationship Id="rId'.($n+1).'" Type="'.$relsNs.'/styles" Target="styles.xml"/></Relationships>';
    $content.='</Types>';
    $app='<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
      .'<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"'
      .' xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
      .'<Application>SGA UNEDID</Application><HeadingPairs><vt:vector size="2" baseType="variant">'
      .'<vt:variant><vt:lpstr>Worksheets</vt:lpstr></vt:variant><vt:variant><vt:i4>'.$n.'</vt:i4></vt:variant>'
      .'</vt:vector></HeadingPairs><TitlesOfParts><vt:vector size="'.$n.'" baseType="lpstr">';
    foreach($nombres as $nombre)$app.='<vt:lpstr>'.cuadroAnualXml($nombre).'</vt:lpstr>';
    $app.='</vt:vector></TitlesOfParts></Properties>';
    $now=gmdate('Y-m-d\TH:i:s\Z');
    $core='<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
      .'<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"'
      .' xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/"'
      .' xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
      .'<dc:creator>SGA UNEDID</dc:creator><cp:lastModifiedBy>SGA UNEDID</cp:lastModifiedBy>'
      .'<dcterms:created xsi:type="dcterms:W3CDTF">'.$now.'</dcterms:created></cp:coreProperties>';
    $root='<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
      .'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
      .'<Relationship Id="rId1" Type="'.$relsNs.'/officeDocument" Target="xl/workbook.xml"/>'
      .'<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
      .'<Relationship Id="rId3" Type="'.$relsNs.'/extended-properties" Target="docProps/app.xml"/>'
      .'</Relationships>';
    return cuadroAnualZip(array_merge([
        '[Content_Types].xml'=>$content,'_rels/.rels'=>$root,
        'docProps/app.xml'=>$app,'docProps/core.xml'=>$core,'xl/workbook.xml'=>$workbook,
        'xl/_rels/workbook.xml.rels'=>$workRels,'xl/styles.xml'=>sgaXlsxEstilos()
    ],$partes));
}
