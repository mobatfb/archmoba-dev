<?php
/** Excel XLSX institucional: una hoja por aula con consolidado de asistencia. */
require_once __DIR__.'/cuadro_anual_excel.php';

function raXlsxTexto(string $ref, string $valor, int $estilo=4): string {
    return '<c r="'.$ref.'" s="'.$estilo.'" t="inlineStr"><is><t xml:space="preserve">'.cuadroAnualXml($valor).'</t></is></c>';
}
function raXlsxNumero(string $ref, int $valor, int $estilo=10): string {
    return '<c r="'.$ref.'" s="'.$estilo.'"><v>'.$valor.'</v></c>';
}
function raXlsxPorcentaje(string $ref, ?float $porcentaje, int $estilo=6): string {
    if($porcentaje===null)return raXlsxTexto($ref,'',4);
    // Las celdas son porcentajes numericos reales, no textos como '75%'.
    return '<c r="'.$ref.'" s="'.$estilo.'"><v>'.number_format($porcentaje/100,8,'.','').'</v></c>';
}
function raXlsxEstilos(): string {
    return <<<'XML'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="4">
<font><sz val="10"/><name val="Calibri"/><color rgb="FF23344C"/></font>
<font><b/><sz val="11"/><name val="Calibri"/><color rgb="FFFFFFFF"/></font>
<font><b/><sz val="11"/><name val="Calibri"/><color rgb="FF194B73"/></font>
<font><b/><sz val="10"/><name val="Calibri"/><color rgb="FF23344C"/></font>
</fonts>
<fills count="4"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FF194B73"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFEFF5FB"/></patternFill></fill></fills>
<borders count="2"><border><left/><right/><top/><bottom/><diagonal/></border>
<border><left style="thin"><color rgb="FFD0DCE9"/></left><right style="thin"><color rgb="FFD0DCE9"/></right><top style="thin"><color rgb="FFD0DCE9"/></top><bottom style="thin"><color rgb="FFD0DCE9"/></bottom><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="12">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
<xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"><alignment vertical="center" wrapText="1"/></xf>
<xf numFmtId="0" fontId="2" fillId="3" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"><alignment vertical="center" wrapText="1"/></xf>
<xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1"><alignment vertical="center" wrapText="1"/></xf>
<xf numFmtId="0" fontId="0" fillId="3" borderId="1" xfId="0" applyFill="1" applyBorder="1"><alignment vertical="center" wrapText="1"/></xf>
<xf numFmtId="10" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyNumberFormat="1"><alignment horizontal="center" vertical="center"/></xf>
<xf numFmtId="10" fontId="0" fillId="3" borderId="1" xfId="0" applyFill="1" applyBorder="1" applyNumberFormat="1"><alignment horizontal="center" vertical="center"/></xf>
<xf numFmtId="10" fontId="2" fillId="0" borderId="1" xfId="0" applyFont="1" applyBorder="1" applyNumberFormat="1"><alignment horizontal="center" vertical="center"/></xf>
<xf numFmtId="10" fontId="2" fillId="3" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyNumberFormat="1"><alignment horizontal="center" vertical="center"/></xf>
<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1"><alignment horizontal="center" vertical="center"/></xf>
<xf numFmtId="0" fontId="0" fillId="3" borderId="1" xfId="0" applyFill="1" applyBorder="1"><alignment horizontal="center" vertical="center"/></xf>
</cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>
XML;
}
function raXlsxHoja(array $datos,string $periodo): string {
    $ofertas=$datos['ofertas'];$estudiantes=$datos['estudiantes'];$aula=$datos['aula'];
    $colCount=count($ofertas)+9; // 3 identificaciones + materias + total + P/A/T/J + registros
    $ultima=cuadroAnualColumna($colCount);
    $ultimaFila=max(4,3+count($estudiantes));
    $titulo=cuadroAnualTituloAula($aula);
    $subtitulo='PERÍODO '.$periodo.' | ASISTENCIA '.$datos['desde'].' a '.$datos['hasta'];
    $cabeceras=['No.','NOMBRES COMPLETOS','CÉDULA'];
    foreach($ofertas as $o)$cabeceras[]=cuadroAnualMayusculas((string)$o['asignatura']);
    $cabeceras=array_merge($cabeceras,['ASISTENCIA TOTAL','PRESENTES','AUSENTES','ATRASOS','JUSTIFICADOS','REGISTROS']);
    $xml='<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        .'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        .'<sheetPr><pageSetUpPr fitToPage="1"/></sheetPr>'
        .'<dimension ref="A1:'.$ultima.$ultimaFila.'"/>'
        .'<sheetViews><sheetView workbookViewId="0" showGridLines="0"><pane xSplit="3" ySplit="3" topLeftCell="D4" activePane="bottomRight" state="frozen"/><selection pane="bottomRight" activeCell="D4" sqref="D4"/></sheetView></sheetViews>'
        .'<sheetFormatPr defaultRowHeight="20"/>'
        .'<cols><col min="1" max="1" width="7" customWidth="1"/>'
        .'<col min="2" max="2" width="43" customWidth="1"/>'
        .'<col min="3" max="3" width="17" customWidth="1"/>';
    foreach($ofertas as $i=>$o){$col=$i+4;$xml.='<col min="'.$col.'" max="'.$col.'" width="29" customWidth="1"/>';}
    for($col=count($ofertas)+4;$col<=$colCount;$col++)$xml.='<col min="'.$col.'" max="'.$col.'" width="16" customWidth="1"/>';
    $xml.='</cols><sheetData>';
    // Bandas de cabecera sin fusiones cruzadas con el panel congelado.
    $xml.='<row r="1" ht="31" customHeight="1">';
    for($col=1;$col<=$colCount;$col++){
        $ref=cuadroAnualColumna($col).'1';
        $xml.=raXlsxTexto($ref,$col===2?$titulo:'',1);
    }
    $xml.='</row>';
    $xml.='<row r="2" ht="22" customHeight="1">';
    for($col=1;$col<=$colCount;$col++){
        $ref=cuadroAnualColumna($col).'2';
        $valor=$col===2?'PERÍODO '.$periodo:($col===4?'ASISTENCIA '.$datos['desde'].' a '.$datos['hasta']:'');
        $xml.=raXlsxTexto($ref,$valor,2);
    }
    $xml.='</row>';
    $xml.='<row r="3" ht="87" customHeight="1">';
    foreach($cabeceras as $i=>$nombre){$xml.=raXlsxTexto(cuadroAnualColumna($i+1).'3',$nombre,3);}
    $xml.='</row>';
    foreach($estudiantes as $i=>$est){
        $r=$i+4;$alterno=(($i%2)===1);$sty=$alterno?5:4;$styNum=$alterno?11:10;$styPct=$alterno?7:6;
        $xml.='<row r="'.$r.'" ht="26" customHeight="1">'
            .raXlsxNumero('A'.$r,(int)($est['numero_lista']?:($i+1)),$styNum)
            .raXlsxTexto('B'.$r,trim($est['apellidos'].' '.$est['nombres']),$sty)
            .raXlsxTexto('C'.$r,(string)$est['cedula'],$sty);
        foreach($ofertas as $j=>$o) {
            $ref=cuadroAnualColumna($j+4).$r;
            $valor=$est['por_oferta'][(int)$o['id']]['porcentaje']??null;
            $xml.=raXlsxPorcentaje($ref,$valor,$styPct);
        }
        $k=count($ofertas)+4;
        $resumen=$est['total'];
        $xml.=raXlsxPorcentaje(cuadroAnualColumna($k++).$r,$resumen['porcentaje'],$alterno?9:8);
        foreach(['presente','ausente','atraso','justificado','registros'] as $campo)
            $xml.=raXlsxNumero(cuadroAnualColumna($k++).$r,(int)$resumen[$campo],$styNum);
        $xml.='</row>';
    }
    $xml.='</sheetData>'
        .'<autoFilter ref="A3:'.$ultima.$ultimaFila.'"/>'
        .'<pageMargins left="0.3" right="0.3" top="0.4" bottom="0.4" header="0.2" footer="0.2"/>'
        .'<pageSetup paperSize="9" orientation="landscape" fitToWidth="1" fitToHeight="0"/></worksheet>';
    return $xml;
}

/** @param array<int,array> $aulas */
function raXlsxLibro(array $aulas,string $periodo): string {
    if(!$aulas)throw new InvalidArgumentException('No hay aulas para exportar.');
    $n=count($aulas);$ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main';
    $rel='http://schemas.openxmlformats.org/officeDocument/2006/relationships';
    $tipos='<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        .'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        .'<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        .'<Default Extension="xml" ContentType="application/xml"/>'
        .'<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        .'<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>';
    $wb='<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        .'<workbook xmlns="'.$ns.'" xmlns:r="'.$rel.'"><bookViews><workbookView activeTab="0"/></bookViews><sheets>';
    $rels='<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        .'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">';
    $files=[];$usados=[];
    foreach($aulas as $i=>$d) {
        $idx=$i+1;$nombre=cuadroAnualNombreHoja($d['aula'],$usados);
        $wb.='<sheet name="'.cuadroAnualXml($nombre).'" sheetId="'.$idx.'" r:id="rId'.$idx.'"/>';
        $rels.='<Relationship Id="rId'.$idx.'" Type="'.$rel.'/worksheet" Target="worksheets/sheet'.$idx.'.xml"/>';
        $tipos.='<Override PartName="/xl/worksheets/sheet'.$idx.'.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>';
        $files['xl/worksheets/sheet'.$idx.'.xml']=raXlsxHoja($d,$periodo);
    }
    $wb.='</sheets><calcPr calcId="191029"/></workbook>';
    $rels.='<Relationship Id="rId'.($n+1).'" Type="'.$rel.'/styles" Target="styles.xml"/></Relationships>';
    $tipos.='</Types>';
    $mainRel='<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        .'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        .'<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        .'</Relationships>';
    $files=array_merge(['[Content_Types].xml'=>$tipos,'_rels/.rels'=>$mainRel,
        'xl/workbook.xml'=>$wb,'xl/_rels/workbook.xml.rels'=>$rels,
        'xl/styles.xml'=>raXlsxEstilos()],$files);
    return cuadroAnualZip($files);
}
