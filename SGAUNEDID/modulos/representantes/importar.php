<?php
/** CSV de vinculos: cedula;estudiantes (varias cedulas separadas por coma). */
require_once __DIR__.'/../../lib/sga_representantes.php';
exigirAdminAcademico();
$redir='modulos/representantes/index.php';
try {
    if($_SERVER['REQUEST_METHOD']!=='POST')throw new RuntimeException('La importación solo se permite desde el formulario.');
    if(empty($_SESSION['csrf_representantes'])||!hash_equals($_SESSION['csrf_representantes'],(string)($_POST['csrf']??'')))throw new RuntimeException('El formulario caducó.');
    if(($_POST['vinculos_verificados']??'')!=='1')throw new RuntimeException('Debes confirmar que UNEDID verificó los vínculos familiares.');
    $pid=(int)(periodoActivo()['id']??0);
    if(!$pid)throw new RuntimeException('No existe un período académico activo.');
    $archivo=$_FILES['archivo']??[];
    if(($archivo['error']??UPLOAD_ERR_NO_FILE)!==UPLOAD_ERR_OK || (int)($archivo['size']??0)<5 || (int)($archivo['size']??0)>1024*1024)throw new RuntimeException('Selecciona un CSV de hasta 1 MB.');
    if(strtolower(pathinfo((string)($archivo['name']??''),PATHINFO_EXTENSION))!=='csv')throw new RuntimeException('Solo se permiten archivos .csv.');
    $f=fopen((string)$archivo['tmp_name'],'rb');if(!$f)throw new RuntimeException('No se pudo leer el archivo.');
    try{
        $cab=fgetcsv($f,0,';');
        if(!is_array($cab)||count($cab)!==2)throw new RuntimeException('El CSV debe tener dos columnas: cedula;estudiantes.');
        $cab=array_map(static fn($x)=>strtolower(trim(preg_replace('/^\xEF\xBB\xBF/','',(string)$x))),$cab);
        if($cab!==['cedula','estudiantes'])throw new RuntimeException('Las columnas deben llamarse cedula;estudiantes y estar en ese orden.');
        $linea=1;$pares=[];$vistos=[];
        while(($datos=fgetcsv($f,0,';'))!==false){
            $linea++;if($linea>1001)throw new RuntimeException('Máximo 1.000 filas por importación.');
            if(count($datos)===1 && trim((string)$datos[0])==='')continue;
            if(count($datos)!==2)throw new RuntimeException('Fila '.$linea.': deben existir dos columnas separadas por punto y coma.');
            $rep=trim((string)$datos[0]);$hijos=explode(',',(string)$datos[1]);
            if(!preg_match('/^[0-9]{10}$/D',$rep))throw new RuntimeException('Fila '.$linea.': cédula del representante inválida.');
            if(count($hijos)>30||!array_filter($hijos,static fn($h)=>trim((string)$h)!==''))throw new RuntimeException('Fila '.$linea.': escribe entre 1 y 30 cédulas de estudiantes.');
            foreach($hijos as $ced){
                $ced=trim((string)$ced);
                if(!preg_match('/^[0-9]{10}$/D',$ced))throw new RuntimeException('Fila '.$linea.': cédula de estudiante inválida. Usa comas para separar hijos.');
                $key=$rep.':'.$ced;if(isset($vistos[$key]))continue;$vistos[$key]=true;
                $pares[]=['representante'=>$rep,'estudiante'=>$ced,'linea'=>$linea];
                if(count($pares)>5000)throw new RuntimeException('Límite de 5.000 vínculos por archivo.');
            }
        }
        if(!$pares)throw new RuntimeException('El archivo no contiene vínculos.');
    }finally{fclose($f);}
    $conexion->begin_transaction();
    try{
        $nuevos=0;$omitidos=0;
        $buscar=$conexion->prepare('SELECT id,activo FROM usuarios WHERE cedula=? LIMIT 1');
        foreach($pares as $p){
            $cedRep=$p['representante'];$cedEst=$p['estudiante'];
            $buscar->bind_param('s',$cedRep);$buscar->execute();$r=$buscar->get_result()->fetch_assoc();
            if(!$r||(int)$r['activo']!==1||!sgaRepEsRepresentante((int)$r['id']))throw new RuntimeException('Fila '.$p['linea'].': el representante '.$cedRep.' no está creado, activo o no tiene el rol Representante.');
            $buscar->bind_param('s',$cedEst);$buscar->execute();$h=$buscar->get_result()->fetch_assoc();
            if(!$h||(int)$h['activo']!==1)throw new RuntimeException('Fila '.$p['linea'].': estudiante '.$cedEst.' no encontrado o inactivo.');
            if(!sgaRepPuedeVincular((int)$h['id'],$pid))throw new RuntimeException('Fila '.$p['linea'].': el estudiante '.$cedEst.' no está matriculado en una jornada que puedas administrar.');
            if(sgaRepVincular((int)$r['id'],(int)$h['id'],$pid))$nuevos++;else $omitidos++;
        }
        $buscar->close();
        if(!$conexion->commit())throw new RuntimeException('No se pudo confirmar la importación.');
        registrarAuditoria('IMPORT','Representantes','vinculacion_csv',null,'Vinculación masiva por CSV.',null,null,['nuevos'=>$nuevos,'ya_existentes'=>$omitidos], 'exito',null,null,'advertencia');
        flash('success','CSV importado: '.$nuevos.' vínculos nuevos o reactivados y '.$omitidos.' ya existentes.');
    }catch(Throwable $e){$conexion->rollback();throw $e;}
}catch(Throwable $e){flash('error','No se pudo importar: '.$e->getMessage());}
redir($redir);
