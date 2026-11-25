<?php
/** Matriz de asistencia por fechas registradas para una oferta academica.
 * XLSX nativo empaquetado sin la extension PHP ZipArchive.
 * Los registros inexistentes se dejan vacios, nunca se consideran ausencias.
 */
require_once __DIR__ . '/asistencia_excel.php';

/** @param array<int,array<string,mixed>> $sesiones
 *  @param array<int,array<string,mixed>> $estudiantes
 *  @param array<int,array<int,string>> $estados
 */
function generarExcelAsistenciaPorFechas(array $oferta, array $sesiones, array $estudiantes, array $estados): string {
    $nFechas = count($sesiones);
    // Excel limita cada hoja a 16.384 columnas. Tres identificadores y cinco columnas de resumen.
    if ($nFechas > 16376) throw new RuntimeException('Demasiadas fechas para una hoja de Excel.');
    $colsTotal = 3 + $nFechas + 5;
    $colFin = asistenciaExcelColumna($colsTotal);
    $filaCabecera = 8;
    $ultimaFila = max(9, $filaCabecera + count($estudiantes));
    $titulo = 'ASISTENCIA POR FECHAS · ' . (string)($oferta['asignatura'] ?? '');
    $curso = trim((string)($oferta['nivel'] ?? '') . ' · ' . (string)($oferta['aula'] ?? '') . ' ' . (string)($oferta['paralelo'] ?? ''));
    $docente = trim((string)($oferta['docente_apellidos'] ?? '') . ' ' . (string)($oferta['docente_nombres'] ?? ''));

    $filas = [];
    $filas[] = asistenciaExcelFila(1, [asistenciaExcelCelda('A', 1, 'UNIDAD EDUCATIVA DE INICIACIÓN Y DESARROLLO DEPORTIVO DEL AZUAY', 1)], 31);
    $filas[] = asistenciaExcelFila(2, [asistenciaExcelCelda('A', 2, $titulo, 2)], 35);
    $filas[] = asistenciaExcelFila(3, [asistenciaExcelCelda('A', 3, 'CURSO: '.$curso.'  |  PERÍODO: '.(string)($oferta['periodo'] ?? ''), 2)], 25);
    $filas[] = asistenciaExcelFila(4, [asistenciaExcelCelda('A', 4, 'DOCENTE: '.$docente, 2)], 24);
    $filas[] = asistenciaExcelFila(5, [asistenciaExcelCelda('A', 5, 'LEYENDA: P = Presente   ·   A = Ausente   ·   T = Atraso   ·   J = Justificado   ·   celda vacía = Sin registro', 3)], 23);
    $filas[] = asistenciaExcelFila(6, [asistenciaExcelCelda('A', 6, 'Fechas con registro: '.$nFechas.'   ·   Estudiantes: '.count($estudiantes).'   ·   Los días no registrados no se consideran ausencias.', 3)], 22);

    $cabeceras = [
        asistenciaExcelCelda('A', $filaCabecera, 'No.', 4),
        asistenciaExcelCelda('B', $filaCabecera, 'CÉDULA', 4),
        asistenciaExcelCelda('C', $filaCabecera, 'ESTUDIANTE', 4),
    ];
    foreach ($sesiones as $i => $sesion) {
        $col = asistenciaExcelColumna(4+$i);
        $fecha = (string)($sesion['fecha'] ?? '');
        $cabeceras[] = asistenciaExcelCelda($col, $filaCabecera, date('d/m/Y', strtotime($fecha)), 4);
    }
    $resumenCabeceras = ['P','A','T','J','% ASIST.'];
    foreach ($resumenCabeceras as $i=>$nombre) {
        $cabeceras[] = asistenciaExcelCelda(asistenciaExcelColumna(4+$nFechas+$i), $filaCabecera, $nombre, 4);
    }
    $filas[] = asistenciaExcelFila($filaCabecera, $cabeceras, 32);

    $estiloEstado = ['presente'=>5,'ausente'=>6,'atraso'=>7,'justificado'=>8];
    $letraEstado = ['presente'=>'P','ausente'=>'A','atraso'=>'T','justificado'=>'J'];
    foreach ($estudiantes as $i=>$estudiante) {
        $fila = $filaCabecera+$i+1;
        $matriculaId = (int)($estudiante['matricula_id']??0);
        $numeroLista = ($estudiante['numero_lista'] === null || $estudiante['numero_lista'] === '') ? $i+1 : (int)$estudiante['numero_lista'];
        $celdas = [
            asistenciaExcelCelda('A',$fila,$numeroLista,12,'n'),
            asistenciaExcelCelda('B',$fila,(string)($estudiante['cedula']??''),14),
            asistenciaExcelCelda('C',$fila,trim((string)($estudiante['apellidos']??'').' '.(string)($estudiante['nombres']??'')),($i%2)?9:0),
        ];
        $conteo = ['presente'=>0,'ausente'=>0,'atraso'=>0,'justificado'=>0];
        foreach ($sesiones as $j=>$sesion) {
            $col = asistenciaExcelColumna(4+$j);
            $sesionId = (int)($sesion['id']??0);
            $estado = $estados[$matriculaId][$sesionId]??null;
            if ($estado!==null && isset($letraEstado[$estado])) {
                $celdas[] = asistenciaExcelCelda($col,$fila,$letraEstado[$estado],$estiloEstado[$estado]);
                $conteo[$estado]++;
            } else {
                $celdas[] = asistenciaExcelCelda($col,$fila,'',($i%2)?9:0);
            }
        }
        foreach (['presente','ausente','atraso','justificado'] as $j=>$estado) {
            $celdas[] = asistenciaExcelCelda(asistenciaExcelColumna(4+$nFechas+$j),$fila,$conteo[$estado],12,'n');
        }
        $registrados=array_sum($conteo);
        $porcentaje=$registrados > 0 ? ($conteo['presente']+$conteo['atraso'])/$registrados : null;
        $colPorcentaje=asistenciaExcelColumna(4+$nFechas+4);
        $celdas[]= $porcentaje===null
            ? asistenciaExcelCelda($colPorcentaje,$fila,'—',12)
            : asistenciaExcelCelda($colPorcentaje,$fila,$porcentaje,11,'n');
        $filas[] = asistenciaExcelFila($fila,$celdas,25);
    }
    if (!$estudiantes) $filas[] = asistenciaExcelFila(9,[asistenciaExcelCelda('C',9,'No existen estudiantes matriculados en este curso.',3)]);

    $colF1 = asistenciaExcelColumna(4+$nFechas);
    $colF5 = asistenciaExcelColumna(4+$nFechas+4);
    $columnas = '<col min="1" max="1" width="8" customWidth="1"/>'
        .'<col min="2" max="2" width="18" customWidth="1"/>'
        .'<col min="3" max="3" width="47" customWidth="1"/>';
    if($nFechas>0) $columnas.='<col min="4" max="'.(3+$nFechas).'" width="14" customWidth="1"/>';
    $columnas.='<col min="'.(4+$nFechas).'" max="'.(7+$nFechas).'" width="10" customWidth="1"/>'
        .'<col min="'.(8+$nFechas).'" max="'.(8+$nFechas).'" width="15" customWidth="1"/>';

    $merges=['A1:'.$colFin.'1','A2:'.$colFin.'2','A3:'.$colFin.'3','A4:'.$colFin.'4',
        'A5:'.$colFin.'5','A6:'.$colFin.'6'];
    $mergeXml='<mergeCells count="'.count($merges).'">';
    foreach($merges as $r) $mergeXml.='<mergeCell ref="'.$r.'"/>';
    $mergeXml.='</mergeCells>';
    // OpenXML CT_Worksheet: autoFilter va ANTES de mergeCells; el orden inverso dispara reparacion en Excel.
    $sheet='<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
      .'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
      .'<sheetPr><pageSetUpPr fitToPage="1"/></sheetPr>'
      .'<dimension ref="A1:'.$colFin.$ultimaFila.'"/>'
      .'<sheetViews><sheetView workbookViewId="0" showGridLines="0"><selection activeCell="A1" sqref="A1"/></sheetView></sheetViews>'
      .'<sheetFormatPr defaultRowHeight="20"/><cols>'.$columnas.'</cols>'
      .'<sheetData>'.implode('',$filas).'</sheetData>'
      .($estudiantes?'<autoFilter ref="A8:'.$colFin.$ultimaFila.'"/>':'')
      .$mergeXml
      .'<printOptions horizontalCentered="1"/>'
      .'<pageMargins left="0.25" right="0.25" top="0.45" bottom="0.45" header="0.2" footer="0.2"/>'
      .'<pageSetup orientation="landscape" paperSize="9" fitToWidth="1" fitToHeight="0"/>'
      .'</worksheet>';

    // Un unico libro con la matriz completa de fechas guardadas.
    $contentTypes='<?xml version="1.0" encoding="UTF-8"?>'
       .'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
       .'<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
       .'<Default Extension="xml" ContentType="application/xml"/>'
       .'<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
       .'<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
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
       .'<sheets><sheet name="Asistencia por fechas" sheetId="1" r:id="rId1"/></sheets>'
       .'</workbook>';
    $bookRels='<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
       .'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
       .'<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
       .'<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
       .'</Relationships>';
    $created=gmdate('Y-m-d\TH:i:s\Z');
    $core='<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
       .'<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
       .'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
       .'<dc:creator>SGA UNEDID</dc:creator><dcterms:created xsi:type="dcterms:W3CDTF">'.$created.'</dcterms:created>'
       .'</cp:coreProperties>';
    $app='<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
       .'<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
       .'<Application>SGA UNEDID</Application></Properties>';
    return cuadroAnualZip([
        '[Content_Types].xml'=>$contentTypes, '_rels/.rels'=>$rels,
        'docProps/core.xml'=>$core, 'docProps/app.xml'=>$app,
        'xl/workbook.xml'=>$book, 'xl/_rels/workbook.xml.rels'=>$bookRels,
        'xl/styles.xml'=>asistenciaExcelEstilos(),
        'xl/worksheets/sheet1.xml'=>$sheet,
    ]);
}
