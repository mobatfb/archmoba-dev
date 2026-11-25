<?php

const XLSX_MAIN_NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main';

function xlsxCargarXml($zip, string $ruta): DOMDocument
{
    $contenido = $zip->getFromName($ruta);
    if ($contenido === false) {
        throw new RuntimeException("No se encontró la parte XLSX: {$ruta}");
    }
    $dom = new DOMDocument('1.0', 'UTF-8');
    $dom->preserveWhiteSpace = false;
    $dom->formatOutput = false;
    if (!$dom->loadXML($contenido, LIBXML_NONET)) {
        throw new RuntimeException("No se pudo leer XML: {$ruta}");
    }
    return $dom;
}

function xlsxGuardarXml($zip, string $ruta, DOMDocument $dom): void
{
    if (!$zip->addFromString($ruta, $dom->saveXML())) {
        throw new RuntimeException("No se pudo actualizar {$ruta} dentro del XLSX.");
    }
}

function xlsxColumnaIndice(string $letras): int
{
    $n = 0;
    foreach (str_split(strtoupper($letras)) as $c) {
        $n = ($n * 26) + (ord($c) - 64);
    }
    return $n;
}

function xlsxReferenciaPartes(string $ref): array
{
    if (!preg_match('/^([A-Z]+)(\d+)$/i', $ref, $m)) {
        throw new InvalidArgumentException("Referencia de celda inválida: {$ref}");
    }
    return [strtoupper($m[1]), (int)$m[2]];
}

function xlsxObtenerOCrearCelda(DOMDocument $dom, string $ref): DOMElement
{
    [$col, $filaNum] = xlsxReferenciaPartes($ref);
    $xp = new DOMXPath($dom);
    $xp->registerNamespace('m', XLSX_MAIN_NS);

    $celda = $xp->query("//m:sheetData/m:row[@r='{$filaNum}']/m:c[@r='{$ref}']")->item(0);
    if ($celda instanceof DOMElement) {
        return $celda;
    }

    $fila = $xp->query("//m:sheetData/m:row[@r='{$filaNum}']")->item(0);
    if (!($fila instanceof DOMElement)) {
        $sheetData = $xp->query('//m:sheetData')->item(0);
        if (!($sheetData instanceof DOMElement)) {
            throw new RuntimeException('El XLSX no contiene sheetData.');
        }
        $fila = $dom->createElementNS(XLSX_MAIN_NS, 'row');
        $fila->setAttribute('r', (string)$filaNum);
        $insertado = false;
        foreach ($sheetData->childNodes as $nodo) {
            if ($nodo instanceof DOMElement && $nodo->localName === 'row' && (int)$nodo->getAttribute('r') > $filaNum) {
                $sheetData->insertBefore($fila, $nodo);
                $insertado = true;
                break;
            }
        }
        if (!$insertado) $sheetData->appendChild($fila);
    }

    $celda = $dom->createElementNS(XLSX_MAIN_NS, 'c');
    $celda->setAttribute('r', $ref);
    $indice = xlsxColumnaIndice($col);
    $insertado = false;
    foreach ($fila->childNodes as $nodo) {
        if (!($nodo instanceof DOMElement) || $nodo->localName !== 'c') continue;
        [$colExistente] = xlsxReferenciaPartes($nodo->getAttribute('r'));
        if (xlsxColumnaIndice($colExistente) > $indice) {
            $fila->insertBefore($celda, $nodo);
            $insertado = true;
            break;
        }
    }
    if (!$insertado) $fila->appendChild($celda);
    return $celda;
}

function xlsxLimpiarContenidoCelda(DOMElement $celda): void
{
    $eliminar = [];
    foreach ($celda->childNodes as $nodo) {
        if ($nodo instanceof DOMElement && in_array($nodo->localName, ['f', 'v', 'is'], true)) {
            $eliminar[] = $nodo;
        }
    }
    foreach ($eliminar as $nodo) $celda->removeChild($nodo);
    $celda->removeAttribute('t');
}

function xlsxCeldaVacia(DOMDocument $dom, string $ref): void
{
    $celda = xlsxObtenerOCrearCelda($dom, $ref);
    xlsxLimpiarContenidoCelda($celda);
}

function xlsxCeldaTexto(DOMDocument $dom, string $ref, ?string $valor): void
{
    if ($valor === null || $valor === '') {
        xlsxCeldaVacia($dom, $ref);
        return;
    }
    $celda = xlsxObtenerOCrearCelda($dom, $ref);
    xlsxLimpiarContenidoCelda($celda);
    $celda->setAttribute('t', 'inlineStr');
    $is = $dom->createElementNS(XLSX_MAIN_NS, 'is');
    $t = $dom->createElementNS(XLSX_MAIN_NS, 't');
    if (preg_match('/^\s|\s$/u', $valor)) {
        $t->setAttributeNS('http://www.w3.org/XML/1998/namespace', 'xml:space', 'preserve');
    }
    $t->appendChild($dom->createTextNode($valor));
    $is->appendChild($t);
    $celda->appendChild($is);
}

function xlsxCeldaNumero(DOMDocument $dom, string $ref, $valor): void
{
    if ($valor === null || $valor === '') {
        xlsxCeldaVacia($dom, $ref);
        return;
    }
    $numero = (float)$valor;
    $celda = xlsxObtenerOCrearCelda($dom, $ref);
    xlsxLimpiarContenidoCelda($celda);
    $v = $dom->createElementNS(XLSX_MAIN_NS, 'v');
    $texto = number_format($numero, 10, '.', '');
    $texto = rtrim(rtrim($texto, '0'), '.');
    if ($texto === '-0') $texto = '0';
    $v->appendChild($dom->createTextNode($texto === '' ? '0' : $texto));
    $celda->appendChild($v);
}

/** Modifica una columna concreta sin cambiar la anchura de sus columnas vecinas. */
function xlsxFijarAnchuraColumna(DOMDocument $dom, int $indice, float $anchura): void
{
    $xp=new DOMXPath($dom);$xp->registerNamespace('m', XLSX_MAIN_NS);
    foreach($xp->query('//m:cols/m:col') as $original){
        $min=(int)$original->getAttribute('min');$max=(int)$original->getAttribute('max');
        if($indice<$min || $indice>$max)continue;
        $parent=$original->parentNode;
        if($min<$indice){$antes=$original->cloneNode(true);$antes->setAttribute('max',(string)($indice-1));$parent->insertBefore($antes,$original);}
        $centro=$original->cloneNode(true);
        $centro->setAttribute('min',(string)$indice);$centro->setAttribute('max',(string)$indice);
        $centro->setAttribute('width',(string)$anchura);$centro->setAttribute('customWidth','1');
        $parent->insertBefore($centro,$original);
        if($max>$indice){$despues=$original->cloneNode(true);$despues->setAttribute('min',(string)($indice+1));$parent->insertBefore($despues,$original);}
        $parent->removeChild($original);return;
    }
}

/** Fórmula XLSX directa: no reutiliza cachés de la plantilla vieja. */
function xlsxCeldaFormula(DOMDocument $dom, string $ref, string $formula): void
{
    $celda=xlsxObtenerOCrearCelda($dom,$ref);
    xlsxLimpiarContenidoCelda($celda);
    $f=$dom->createElementNS(XLSX_MAIN_NS,'f');
    $f->appendChild($dom->createTextNode(ltrim($formula,'=')));
    $celda->appendChild($f);
}

/** Adapta solo la fila de cabecera de un libro XLSX basado en la plantilla anterior. */
function xlsxCambiarRangoCombinado(DOMDocument $dom,string $anterior,string $nuevo): void
{
    $xp=new DOMXPath($dom);$xp->registerNamespace('m', XLSX_MAIN_NS);
    foreach($xp->query('//m:mergeCells/m:mergeCell[@ref="'.$anterior.'"]') as $celda)
        $celda->setAttribute('ref',$nuevo);
}

function xlsxQuitarCalcChainYForzarRecalculo($zip): void
{
    if ($zip->locateName('xl/calcChain.xml') !== false) {
        $zip->deleteName('xl/calcChain.xml');
    }

    try {
        $dom = xlsxCargarXml($zip, '[Content_Types].xml');
        $xp = new DOMXPath($dom);
        $xp->registerNamespace('ct', 'http://schemas.openxmlformats.org/package/2006/content-types');
        foreach ($xp->query("//ct:Override[@PartName='/xl/calcChain.xml']") as $nodo) {
            $nodo->parentNode->removeChild($nodo);
        }
        xlsxGuardarXml($zip, '[Content_Types].xml', $dom);
    } catch (Throwable $e) {
        // No bloquea la generación si la plantilla no declara calcChain aquí.
    }

    try {
        $dom = xlsxCargarXml($zip, 'xl/_rels/workbook.xml.rels');
        $xp = new DOMXPath($dom);
        $xp->registerNamespace('r', 'http://schemas.openxmlformats.org/package/2006/relationships');
        foreach ($xp->query("//r:Relationship[contains(@Target,'calcChain')]") as $nodo) {
            $nodo->parentNode->removeChild($nodo);
        }
        xlsxGuardarXml($zip, 'xl/_rels/workbook.xml.rels', $dom);
    } catch (Throwable $e) {
    }

    $dom = xlsxCargarXml($zip, 'xl/workbook.xml');
    $xp = new DOMXPath($dom);
    $xp->registerNamespace('m', XLSX_MAIN_NS);
    $calcPr = $xp->query('//m:calcPr')->item(0);
    if ($calcPr instanceof DOMElement) {
        $calcPr->setAttribute('calcMode', 'auto');
        $calcPr->setAttribute('fullCalcOnLoad', '1');
        $calcPr->setAttribute('forceFullCalc', '1');
    }
    xlsxGuardarXml($zip, 'xl/workbook.xml', $dom);
}

function xlsxNombreArchivoSeguro(string $texto): string
{
    $texto = iconv('UTF-8', 'ASCII//TRANSLIT//IGNORE', $texto) ?: $texto;
    $texto = preg_replace('/[^A-Za-z0-9._-]+/', '_', $texto);
    $texto = trim((string)$texto, '._-');
    return $texto !== '' ? $texto : 'reporte';
}
