<?php
/** Test del generador OOXML sin exigir mysqli, ZIP o base de datos. */
if(PHP_SAPI!=='cli'){http_response_code(403);exit;}
require_once __DIR__.'/../lib/exportaciones_xlsx.php';
$filas=[];
for($i=1;$i<=125;$i++)$filas[]=[$i,'E'.str_pad((string)$i,9,'0',STR_PAD_LEFT),'ESTUDIANTE DE PRUEBA '.$i,($i%11)+0.5];
$hojas=[];
foreach(['Trimestre 1','Trimestre 2','Trimestre 3','Resumen anual'] as $n){
    $hojas[]=['nombre'=>$n,'titulo'=>'PRUEBA CALIFICACIONES','subtitulo'=>'125 estudiantes',
        'nota'=>'Documento generado solamente para pruebas','cabeceras'=>['No.','Cedula','Estudiante','Nota'],
        'filas'=>$filas,'anchos'=>[10,20,38,16]];
}
$bin=sgaXlsxGenerar($hojas);
if(strlen($bin)<10000||substr($bin,0,2)!=='PK'){
    fwrite(STDERR,"ERROR: el libro generado no parece XLSX.\n");exit(1);
}
if(class_exists('ZipArchive')){
    $tmp=tempnam(sys_get_temp_dir(),'sga_excel_');file_put_contents($tmp,$bin);
    $zip=new ZipArchive();if($zip->open($tmp)!==true){unlink($tmp);exit(1);}
    if($zip->numFiles<10||$zip->getFromName('xl/worksheets/sheet4.xml')===false){$zip->close();unlink($tmp);exit(1);}
    $zip->close();unlink($tmp);
}
echo 'OK: XLSX de 125 estudiantes, cuatro hojas, '.strlen($bin)." bytes\n";
