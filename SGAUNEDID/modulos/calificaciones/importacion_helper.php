<?php
/**
 * UNEDID grade import. Input columns are from the original school workbook.
 * Only direct teacher-entered cells are read: calculated cells are ignored.
 */
function impCamposAportes(): array {
    return [
        'D'=>'deber_ap1','E'=>'deber_ap2','F'=>'deber_ap3',
        'J'=>'tarea_ap1','K'=>'tarea_ap2','L'=>'tarea_ap3',
        'P'=>'leccion_ap1','Q'=>'leccion_ap2','R'=>'leccion_ap3',
        'V'=>'grupo_ap1','W'=>'grupo_ap2','X'=>'grupo_ap3',
    ];
}
function impCamposOtros(): array {
    return [
        'H'=>'deber_refuerzo','N'=>'tarea_refuerzo',
        'T'=>'leccion_refuerzo','Z'=>'grupo_refuerzo',
        'AD'=>'nota_disciplinar',
        'AE'=>'trabajo_refuerzo_disciplinar',
        'AG'=>'nota_producto_final',
    ];
}
function impEtiquetas(): array {
    return [
        'deber_ap1'=>'Deber AP1','deber_ap2'=>'Deber AP2','deber_ap3'=>'Deber AP3','deber_refuerzo'=>'Refuerzo deber',
        'tarea_ap1'=>'Tarea AP1','tarea_ap2'=>'Tarea AP2','tarea_ap3'=>'Tarea AP3','tarea_refuerzo'=>'Refuerzo tarea',
        'leccion_ap1'=>'Leccion AP1','leccion_ap2'=>'Leccion AP2','leccion_ap3'=>'Leccion AP3','leccion_refuerzo'=>'Refuerzo leccion',
        'grupo_ap1'=>'Grupo AP1','grupo_ap2'=>'Grupo AP2','grupo_ap3'=>'Grupo AP3','grupo_refuerzo'=>'Refuerzo grupo',
        'nota_disciplinar'=>'Nota disciplinar','trabajo_refuerzo_disciplinar'=>'Refuerzo disciplinar',
        'nota_producto_final'=>'Producto final',
    ];
}
function impXmlSeguro(string $xml): DOMDocument {
    $dom=new DOMDocument('1.0','UTF-8');
    $antes=libxml_use_internal_errors(true);
    try {
        if (!$dom->loadXML($xml, LIBXML_NONET | LIBXML_COMPACT)) {
            throw new RuntimeException('XML interno del libro de Excel no valido.');
        }
    } finally { libxml_clear_errors();libxml_use_internal_errors($antes); }
    return $dom;
}
function impZipLeer(ZipArchive $z,string $nombre,int $limite=10000000): ?string {
    $stat=$z->statName($nombre);
    if ($stat===false) return null;
    if (($stat['size']??0)>$limite)throw new RuntimeException('Una parte del Excel supera el limite permitido.');
    $data=$z->getFromName($nombre);
    if ($data===false)throw new RuntimeException('No se pudo extraer '.$nombre);
    return $data;
}
function impXlsxLeer(string $ruta,int $trimestre): array {
    if (!class_exists('ZipArchive') || !class_exists('DOMDocument'))
        throw new RuntimeException('Este servidor requiere las extensiones PHP ZIP y DOM/XML para leer XLSX.');
    if ($trimestre<1 || $trimestre>3)throw new InvalidArgumentException('Trimestre incorrecto.');
    if (!is_file($ruta) || filesize($ruta)>5*1024*1024)
        throw new RuntimeException('El archivo Excel debe tener como maximo 5 MB.');
    $zip=new ZipArchive();
    if ($zip->open($ruta)!==true)throw new RuntimeException('El archivo no es un XLSX valido.');
    try {
        $wxml=impZipLeer($zip,'xl/workbook.xml',1000000);
        $rxml=impZipLeer($zip,'xl/_rels/workbook.xml.rels',1000000);
        if (!$wxml || !$rxml)throw new RuntimeException('Estructura XLSX incompleta.');
        $wd=impXmlSeguro($wxml);$rd=impXmlSeguro($rxml);
        $ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main';
        $nsRelDoc='http://schemas.openxmlformats.org/officeDocument/2006/relationships';
        $nsRelPkg='http://schemas.openxmlformats.org/package/2006/relationships';
        $map=[];
        foreach ($rd->getElementsByTagNameNS($nsRelPkg,'Relationship') as $rel) {
            $id=$rel->getAttribute('Id');$target=$rel->getAttribute('Target');
            if ($rel->getAttribute('TargetMode')==='External')continue;
            $target=ltrim($target,'/');
            if (str_starts_with($target,'xl/'))$resolved=$target;
            else $resolved='xl/'.$target;
            // Only worksheet paths are allowed, no ZIP traversal.
            if (preg_match('#^xl/worksheets/[^/]+\.xml$#i',$resolved))$map[$id]=$resolved;
        }
        $sheetPath=null;$wanted='TRIM'.$trimestre;
        foreach ($wd->getElementsByTagNameNS($ns,'sheet') as $sheet) {
            $name=strtoupper(preg_replace('/[^A-Z0-9]/','',strtoupper($sheet->getAttribute('name'))));
            if ($name===$wanted || $name==='TRIMESTRE'.$trimestre) {
                $sheetPath=$map[$sheet->getAttributeNS($nsRelDoc,'id')]??null;
                break;
            }
        }
        if (!$sheetPath)throw new RuntimeException('No existe la hoja TRIM '.$trimestre.' en el Excel.');
        $sxml=impZipLeer($zip,$sheetPath,10000000);
        if (!$sxml)throw new RuntimeException('No se pudo leer la hoja TRIM '.$trimestre.'.');
        $shared=[];$sharedXml=impZipLeer($zip,'xl/sharedStrings.xml',7000000);
        if ($sharedXml!==null) {
            $sDom=impXmlSeguro($sharedXml);
            foreach ($sDom->getElementsByTagNameNS($ns,'si') as $si) {
                $text='';foreach ($si->getElementsByTagNameNS($ns,'t') as $t)$text.=$t->textContent;
                $shared[]=$text;
            }
        }
        $dom=impXmlSeguro($sxml);
        $cols=impCamposAportes()+impCamposOtros();
        $reversed=$cols;
        $rows=[];$vacios=[];$sinNotas=0;$conFormulas=0;
        foreach ($dom->getElementsByTagNameNS($ns,'row') as $row) {
            $fila=(int)$row->getAttribute('r');
            if ($fila<9 || $fila>150)continue;
            $cells=[];
            foreach ($row->getElementsByTagNameNS($ns,'c') as $cell) {
                $ref=$cell->getAttribute('r');
                if (!preg_match('/^([A-Z]+)(\d+)$/i',$ref,$m))continue;
                $col=strtoupper($m[1]);
                if (!isset($reversed[$col]) && $col!=='B' && $col!=='C')continue;
                $type=$cell->getAttribute('t');
                $isFormula=$cell->getElementsByTagNameNS($ns,'f')->length>0;
                $valor=null;
                if ($type==='inlineStr') {
                    $parts=[];foreach($cell->getElementsByTagNameNS($ns,'t') as $tn)$parts[]=$tn->textContent;
                    $valor=implode('',$parts);
                } else {
                    $v=$cell->getElementsByTagNameNS($ns,'v')->item(0);
                    if ($v)$valor=$v->textContent;
                    if ($type==='s' && $valor!==null)$valor=$shared[(int)$valor]??null;
                }
                $cells[$col]=['valor'=>$valor,'formula'=>$isFormula,'error'=>$type==='e'];
            }
            $nb=trim((string)($cells['B']['valor']??''));
            $nc=trim((string)($cells['C']['valor']??''));
            $nombre=trim($nb.' '.$nc);
            if (preg_match('/^(PROMEDIO|TOTAL\b|DOMINAN\b|ALCANZAN\b|PROXIMOS\b|PROXIMOS A|NO ALCANZAN\b|ALUMNOS\b)/iu',$nombre))continue;
            $notas=[];
            foreach($cols as $col=>$campo) {
                $celda=$cells[$col]??null;
                if (!$celda)continue;
                if ($celda['formula']) { $conFormulas++; continue; }
                $raw=trim((string)($celda['valor']??''));
                if ($raw==='')continue;
                $num=str_replace(',','.',$raw);
                if ($celda['error'] || !is_numeric($num) || !is_finite((float)$num) || (float)$num<0 || (float)$num>10) {
                    throw new RuntimeException('Nota invalida en TRIM '.$trimestre.'!'.$col.$fila.' ('.$raw.'). Debe ser de 0 a 10.');
                }
                $notas[$campo]=round((float)$num,2);
            }
            if (!$notas) {if ($nombre!=='')$sinNotas++;continue;}
            if ($nombre==='')$vacios[]=$fila;
            $rows[]=['fila'=>$fila,'nombre'=>$nombre,'notas'=>$notas];
            if (count($rows)>140)throw new RuntimeException('Demasiadas filas de estudiantes para esta plantilla.');
        }
        $camposUsados=[];foreach($rows as $row)foreach($row['notas'] as $c=>$n)$camposUsados[$c]=true;
        return ['trimestre'=>$trimestre,'filas'=>$rows,'columnas_usadas'=>array_keys($camposUsados),
            'filas_sin_nombre'=>$vacios,'filas_sin_notas'=>$sinNotas,'formulas_ignoradas'=>$conFormulas];
    } finally { $zip->close(); }
}
/** Uppercase, accent-free, collapsed whitespace, unordered name token multiset. */
function impTokensNombre(string $name): array {
    $name=strtr($name,[
        'Á'=>'A','À'=>'A','Â'=>'A','Ä'=>'A','Ã'=>'A','Å'=>'A','É'=>'E','È'=>'E','Ê'=>'E','Ë'=>'E',
        'Í'=>'I','Ì'=>'I','Ï'=>'I','Î'=>'I','Ó'=>'O','Ò'=>'O','Ô'=>'O','Ö'=>'O','Õ'=>'O',
        'Ú'=>'U','Ù'=>'U','Û'=>'U','Ü'=>'U','Ñ'=>'N','Ç'=>'C',
        'á'=>'a','à'=>'a','â'=>'a','ä'=>'a','ã'=>'a','å'=>'a','é'=>'e','è'=>'e','ê'=>'e','ë'=>'e',
        'í'=>'i','ì'=>'i','ï'=>'i','î'=>'i','ó'=>'o','ò'=>'o','ô'=>'o','ö'=>'o','õ'=>'o',
        'ú'=>'u','ù'=>'u','û'=>'u','ü'=>'u','ñ'=>'n','ç'=>'c',
    ]);
    if (function_exists('iconv')) {
        $conv=@iconv('UTF-8','ASCII//TRANSLIT//IGNORE',$name);
        if ($conv!==false)$name=$conv;
    }
    $name=strtoupper($name);
    $name=preg_replace('/[^A-Z0-9]+/',' ',$name);
    $tokens=array_values(array_filter(explode(' ',trim($name)),static fn($x)=>$x!=='' && !in_array($x,['DE','DEL','LA','LAS','LOS','EL','Y'],true)));
    sort($tokens,SORT_STRING);
    return $tokens;
}
function impNombreScore(string $origen,string $nombreBd): float {
    $a=impTokensNombre($origen);$b=impTokensNombre($nombreBd);
    if (!$a || !$b)return 0.0;
    if ($a===$b)return 100.0;
    $todos=0;$lena=0;$lenb=0;
    foreach($a as $v)$lena+=strlen($v);
    foreach($b as $v)$lenb+=strlen($v);
    $usados=[];
    // Match the most informative tokens first, without reusing surname/name tokens.
    usort($a,static fn($x,$y)=>strlen($y)<=>strlen($x));
    foreach($a as $ta) {
        $mejor=0.0;$best=null;
        foreach($b as $j=>$tb) {
            if(isset($usados[$j]))continue;
            $max=max(strlen($ta),strlen($tb));
            $sim=$max ? 1-(levenshtein($ta,$tb)/$max) : 0;
            if ($sim>$mejor) {$mejor=$sim;$best=$j;}
        }
        if($best!==null && $mejor>=0.72) {
            $usados[$best]=true;$todos+=$mejor*max(strlen($ta),strlen($b[$best]));
        }
    }
    $score=($lena+$lenb)?200*$todos/($lena+$lenb):0;
    return round(min(99.0,$score),1);
}
function impSugerirNombre(string $origen,array $estudiantes): array {
    if (trim($origen)==='')return ['estado'=>'sin_nombre','id'=>0,'score'=>0,'candidatos'=>[]];
    $scores=[];
    foreach($estudiantes as $e) {
        $nombre=trim($e['apellidos'].' '.$e['nombres']);
        $scores[]=['id'=>(int)$e['id'],'nombre'=>$nombre,'score'=>impNombreScore($origen,$nombre)];
    }
    usort($scores,static fn($a,$b)=>$b['score']<=>$a['score']);
    $mejor=$scores[0]??['score'=>0,'id'=>0];$segundo=$scores[1]['score']??0;
    $nt=count(impTokensNombre($origen));
    $auto=($mejor['score']===100.0 || ($nt>=3 && $mejor['score']>=94.0) || ($nt===2 && $mejor['score']>=97.0))
        && ($mejor['score']-$segundo>=8);
    $estado=$auto?($mejor['score']===100.0?'exacta':'alta'):($mejor['score']>=70?'revisar':'no_encontrado');
    return ['estado'=>$estado,'id'=>$auto?$mejor['id']:0,'score'=>$mejor['score'],
        'candidatos'=>array_slice($scores,0,3)];
}
