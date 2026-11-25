<?php
require_once __DIR__.'/../../lib/funciones.php';
exigirAdminAcademico();
if($_SERVER['REQUEST_METHOD']!=='POST') redir('modulos/academico/index.php');
$apId=(int)($_POST['aula_periodo_id']??0);
exigirAccesoAulaPeriodo($apId);
if(empty($_SESSION['csrf_aula_gestion']) || !hash_equals((string)$_SESSION['csrf_aula_gestion'],(string)($_POST['csrf_aula_gestion']??''))){
    flash('error','La sesion del formulario ha caducado. Recarga el aula e intenta de nuevo.');
    redir('modulos/academico/aula.php?id='.$apId);
}

$stmt=$conexion->prepare('SELECT ap.id,ap.periodo_id,p.nombre periodo,a.nivel,a.nombre aula,a.paralelo FROM aulas_periodo ap JOIN periodos_academicos p ON p.id=ap.periodo_id JOIN aulas a ON a.id=ap.aula_id WHERE ap.id=? LIMIT 1');
$stmt->bind_param('i',$apId);$stmt->execute();$ap=$stmt->get_result()->fetch_assoc();$stmt->close();
if(!$ap){flash('error','El aula seleccionada no existe.');redir('modulos/academico/index.php');}
if(empty($_FILES['archivo'])||($_FILES['archivo']['error']??UPLOAD_ERR_NO_FILE)!==UPLOAD_ERR_OK){flash('error','Selecciona un archivo CSV válido.');redir('modulos/academico/aula.php?id='.$apId);}
if(($_FILES['archivo']['size']??0)>2*1024*1024){flash('error','El CSV supera el tamaño permitido de 2 MB.');redir('modulos/academico/aula.php?id='.$apId);}
$path=$_FILES['archivo']['tmp_name'];
$fh=fopen($path,'r');
if(!$fh){flash('error','No se pudo leer el archivo CSV.');redir('modulos/academico/aula.php?id='.$apId);}
$first=fgets($fh);
if($first===false){fclose($fh);flash('error','El archivo CSV está vacío.');redir('modulos/academico/aula.php?id='.$apId);}
$first=preg_replace('/^\xEF\xBB\xBF/','',$first);
$delimiter=substr_count($first,';')>substr_count($first,',')?';':',';
$meta=str_getcsv(trim($first),$delimiter);
$meta[0]=trim((string)($meta[0]??''));
$idPlantilla=(int)($meta[1]??0);
if(strtolower($meta[0])!=='aula_periodo_id'||$idPlantilla!==$apId){fclose($fh);flash('error','La plantilla CSV no corresponde a este curso. Descarga una nueva desde esta misma pantalla.');redir('modulos/academico/aula.php?id='.$apId);}
$header=fgetcsv($fh,0,$delimiter);
if(!$header||strtolower(trim((string)($header[0]??'')))!=='cedula'){fclose($fh);flash('error','Formato inválido. La segunda fila debe contener la columna cedula.');redir('modulos/academico/aula.php?id='.$apId);}
$cedulas=[];
while(($row=fgetcsv($fh,0,$delimiter))!==false){
    $ced=trim((string)($row[0]??''));
    $ced=preg_replace('/\s+/','',$ced);
    if($ced!=='')$cedulas[$ced]=true;
}
fclose($fh);
$cedulas=array_keys($cedulas);
if(!$cedulas){flash('error','No se encontraron cédulas para matricular.');redir('modulos/academico/aula.php?id='.$apId);}

$pid=(int)$ap['periodo_id'];
$creados=$reactivados=$existentes=$noEncontrados=$conflictos=0;$detalle=[];$audMat=[];$grupoAud=auditoriaGrupo();
try{
    sgaAsegurarAulaEditable($apId);
    $conexion->begin_transaction();
    foreach($cedulas as $ced){
        $u=usuarioPorCedula($ced);
        if(!$u||!(int)$u['activo']){$noEncontrados++;$detalle[]=$ced.' no existe o está inactivo';continue;}
        $r=matricularUsuarioEnAula((int)$u['id'],$apId,$pid);
        if($r['estado']==='creado'){$creados++;$audMat[]=['accion'=>'CREATE','uid'=>(int)$u['id'],'mid'=>$r['matricula_id']??null,'detalle'=>'Estudiante matriculado mediante CSV.'];}
        elseif($r['estado']==='reactivado'){$reactivados++;$audMat[]=['accion'=>'UPDATE','uid'=>(int)$u['id'],'mid'=>$r['matricula_id']??null,'detalle'=>'Matrícula reactivada mediante CSV.'];}
        elseif($r['estado']==='existente')$existentes++;
        elseif($r['estado']==='conflicto'){$conflictos++;$detalle[]=$ced.': '.$r['mensaje'];}
        else {$detalle[]=$ced.': '.$r['mensaje'];}
    }
    foreach($audMat as $a){sgaAuditoriaObligatoria($a['accion'],'Matrículas','matricula',$a['mid'],$a['detalle'],$a['uid'],null,['aula_periodo_id'=>$apId,'periodo_id'=>$pid,'estado'=>'activo'],'exito',null,$grupoAud,'info');}
    sgaAuditoriaObligatoria('IMPORT','Matrículas','matriculas_csv',$apId,"Matrícula masiva CSV: $creados nuevas, $reactivados reactivadas, $existentes existentes, $noEncontrados no encontradas, $conflictos conflictos.",null,null,['aula_periodo_id'=>$apId,'creadas'=>$creados,'reactivadas'=>$reactivados,'existentes'=>$existentes,'no_encontradas'=>$noEncontrados,'conflictos'=>$conflictos],'exito',null,$grupoAud,'info');
    if(!$conexion->commit())throw new RuntimeException('No se pudo confirmar la importacion de matriculas.');
    $msg="Importación completada: $creados nuevas, $reactivados reactivadas, $existentes ya matriculadas, $noEncontrados no encontradas".($conflictos?", $conflictos conflictos":'').'.';
    if($detalle)$msg.=' '.implode(' | ',array_slice($detalle,0,5));
    flash(($noEncontrados||$conflictos)?'info':'success',$msg);
}catch(Throwable $e){
    try{$conexion->rollback();}catch(Throwable $x){}
    flash('error','No se pudo completar la importación: '.$e->getMessage());
}
redir('modulos/academico/aula.php?id='.$apId);
