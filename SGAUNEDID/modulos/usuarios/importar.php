<?php
require_once __DIR__.'/../../lib/funciones.php';
require_once __DIR__.'/../../lib/roles_usuarios.php';
require_once __DIR__.'/../../lib/usuarios_unicode.php';
require_once __DIR__.'/../../lib/usuarios_jornadas.php';
exigirAdminAcademico();
$destino='modulos/usuarios/index.php';
try {
    if ($_SERVER['REQUEST_METHOD']!=='POST') throw new RuntimeException('La importación debe realizarse desde el formulario.');
    if (empty($_SESSION['csrf_usuarios']) || !hash_equals($_SESSION['csrf_usuarios'],(string)($_POST['csrf']??''))) throw new RuntimeException('El formulario ha caducado.');
    if (!isset($_FILES['archivo']) || ($_FILES['archivo']['error']??UPLOAD_ERR_NO_FILE)!==UPLOAD_ERR_OK) throw new RuntimeException('No se recibió el archivo CSV.');
    $tam=(int)($_FILES['archivo']['size']??0);
    if ($tam<=0 || $tam>12*1024*1024) throw new RuntimeException('El archivo debe contener datos y no superar 12 MB.');
    $pid=(int)(periodoActivo()['id']??0);
    if (!$pid) throw new RuntimeException('Activa primero un período académico.');
    // Los CSV nuevos especifican jornadas por fila. El selector es solo respaldo
    // para archivos anteriores que no tenian la columna jornadas.
    $catalogoJornadas=sgaUJCatalogo($pid);
    $jornadaImport=(int)($_POST['jornada_id']??0);
    if($jornadaImport) sgaUJValidarIds([$jornadaImport],$catalogoJornadas,true);
    $bytes=file_get_contents($_FILES['archivo']['tmp_name']);
    if ($bytes===false) throw new RuntimeException('No se pudo leer el archivo CSV.');
    $contenido=sgaUsuariosCsvUtf8($bytes);
    unset($bytes);
    $f=fopen('php://temp/maxmemory:2097152','w+');
    if (!$f || fwrite($f,$contenido)!==strlen($contenido)) throw new RuntimeException('No se pudo preparar el archivo CSV.');
    unset($contenido);
    rewind($f);
    $actualizarDatos=esAdminAcademico() && !empty($_POST['actualizar_datos']);
    $primera=(string)fgets($f);rewind($f);
    $separadores=[';'=>substr_count($primera,';'),','=>substr_count($primera,','),"\t"=>substr_count($primera,"\t")];
    arsort($separadores);$delim=(string)array_key_first($separadores);
    $header=fgetcsv($f,0,$delim);
    if (!is_array($header)) throw new RuntimeException('El archivo CSV está vacío o tiene cabeceras incorrectas.');
    $normalizarHeader=static function ($v): string {
        $v=trim(preg_replace('/^\xEF\xBB\xBF/','',(string)$v));
        $v=strtolower(strtr($v,['Á'=>'a','É'=>'e','Í'=>'i','Ó'=>'o','Ú'=>'u','Ñ'=>'n','á'=>'a','é'=>'e','í'=>'i','ó'=>'o','ú'=>'u','ñ'=>'n']));
        return preg_replace('/\s+/u','_',$v)?:$v;
    };
    $map=array_flip(array_map($normalizarHeader,$header));
    foreach (['cedula','apellidos','nombres','rol'] as $requerido) {
        if (!array_key_exists($requerido,$map)) throw new RuntimeException('Falta la columna obligatoria: '.$requerido.'. Descarga la nueva plantilla.');
    }
    $columnaJornadas=$map['jornadas']??$map['jornada']??null;
    $csvConJornadas=$columnaJornadas!==null;
    if(!$csvConJornadas && esSubadmin() && !$jornadaImport)
        throw new RuntimeException('El CSV anterior no tiene la columna jornadas. Descarga la nueva plantilla o elige una jornada predeterminada.');
    $filas=[];$vistos=[];$numero=1;
    while (($row=fgetcsv($f,0,$delim))!==false) {
        $numero++;
        if ($numero>25001) throw new RuntimeException('Límite de 25.000 filas por archivo. Divide el CSV en lotes.');
        if (count($row)===1 && trim((string)$row[0])==='') continue;
        $ced=trim((string)($row[$map['cedula']]??''));
        $ape=trim((string)($row[$map['apellidos']]??''));
        $nom=trim((string)($row[$map['nombres']]??''));
        $correo=isset($map['correo'])?trim((string)($row[$map['correo']]??'')):'';
        $clave=isset($map['clave'])?(string)($row[$map['clave']]??''):'';
        $rol=normalizarRolUsuario((string)($row[$map['rol']]??''));
        if ($ced===''||$ape===''||$nom==='') throw new RuntimeException("Fila $numero: se requieren cédula, apellidos y nombres.");
        sgaValidarNombreUtf8($ape, 'Apellidos', $numero);
        sgaValidarNombreUtf8($nom, 'Nombres', $numero);
        if (!in_array($rol,['estudiante','docente','representante'],true)) throw new RuntimeException("Fila $numero: el rol debe ser estudiante, docente o representante, nunca administrador.");
        if ($correo!=='' && !filter_var($correo,FILTER_VALIDATE_EMAIL)) throw new RuntimeException("Fila $numero: correo electrónico inválido.");
        if($rol==='representante' && $correo==='') throw new RuntimeException("Fila $numero: el representante necesita correo electrónico.");
        if (isset($vistos[$ced])) throw new RuntimeException("Fila $numero: la cédula $ced aparece más de una vez en el CSV.");
        // Se admiten códigos (MAT|VES), nombres (MATUTINA|VESPERTINA) e IDs del catálogo.
        $jornadasFila=$csvConJornadas
            ? sgaUJDesdeCsv((string)($row[$columnaJornadas]??''),$catalogoJornadas,$numero,esSubadmin()||$rol!=='representante')
            : ($jornadaImport?[$jornadaImport]:[]);
        $vistos[$ced]=true;
        $filas[]=['cedula'=>$ced,'apellidos'=>$ape,'nombres'=>$nom,'correo'=>$correo,'clave'=>$clave,'rol'=>$rol,'jornadas'=>$jornadasFila];
    }
    fclose($f);unset($f);
    if (!$filas) throw new RuntimeException('El CSV no contiene usuarios para importar.');
    $creados=0;$actualizados=0;$sinCambios=0;$protegidos=0;$datosCorregidos=0;$jornadasActualizadas=0;
    $conexion->begin_transaction();
    foreach ($filas as $fila) {
        $ced=$fila['cedula'];$s=$conexion->prepare('SELECT id,apellidos,nombres,correo FROM usuarios WHERE cedula=? LIMIT 1');$s->bind_param('s',$ced);$s->execute();$ex=$s->get_result()->fetch_assoc();$s->close();
        if ($ex) {
            $uid=(int)$ex['id'];
            if (tieneRolGlobalUsuario($uid)) {$protegidos++;continue;}
            if(esSubadmin()&&!puedeGestionarUsuarioJornada($uid,$pid))
                throw new RuntimeException('El CSV contiene una cuenta que no puedes gestionar. La importación se canceló.');
            $anterior=obtenerRolPrincipalUsuario($uid,$pid);
            $corrigio=false;
            if ($actualizarDatos) {
                // El CSV es la fuente autorizada solo cuando el administrador académico marca
                // expresamente esta opción. Contraseña y cédula nunca se tocan.
                $correoNuevo=$fila['correo']!==''?$fila['correo']:$ex['correo'];
                if ($ex['apellidos']!==$fila['apellidos'] || $ex['nombres']!==$fila['nombres'] || $ex['correo']!==$correoNuevo) {
                    $up=$conexion->prepare('UPDATE usuarios SET apellidos=?,nombres=?,correo=? WHERE id=?');
                    if (!$up) throw new RuntimeException('No se pudo preparar la actualización de nombres.');
                    $up->bind_param('sssi',$fila['apellidos'],$fila['nombres'],$correoNuevo,$uid);
                    if (!$up->execute()) throw new RuntimeException('No se pudieron corregir los nombres de la cédula '.$ced.'.');
                    $up->close();
                    $datosCorregidos++;$corrigio=true;
                }
            }
            $cambioRol=$anterior!==$fila['rol'];
            if ($cambioRol) {
                establecerRolUsuario($uid,$fila['rol'],$pid,false);
                $actualizados++;
            }
            $cambioJornadas=false;
            if ($csvConJornadas || $jornadaImport) {
                // Plantillas nuevas: sustituyen las jornadas del periodo por las de la fila.
                // Plantillas antiguas: incorporan la jornada predeterminada sin retirar otras.
                $nuevas=$csvConJornadas?$fila['jornadas']:
                    array_values(array_unique(array_merge(sgaUJAsignadas($uid,$pid),$fila['jornadas'])));
                $cambioJornadas=sgaUJGuardar($uid,$pid,$nuevas);
                if($cambioJornadas)$jornadasActualizadas++;
            }
            if (!$cambioRol && !$corrigio && !$cambioJornadas) $sinCambios++;
        } else {
            $clave=$fila['clave']!==''?$fila['clave']:($fila['rol']==='representante'?bin2hex(random_bytes(16)):$ced);
            if($fila['rol']==='representante' && strlen($clave)<8)throw new RuntimeException('La contraseña de un representante debe tener al menos 8 caracteres.');
            $hash=password_hash($clave,PASSWORD_DEFAULT);
            $correoDb=$fila['correo']!==''?$fila['correo']:null;
            $s=$conexion->prepare('INSERT INTO usuarios (cedula,apellidos,nombres,correo,clave,debe_cambiar_clave) VALUES (?,?,?,?,?,1)');
            $s->bind_param('sssss',$ced,$fila['apellidos'],$fila['nombres'],$correoDb,$hash);
            if (!$s->execute()) throw new RuntimeException('No se pudo crear al usuario con cédula '.$ced.'; revisa duplicados en la base.');
            $uid=(int)$conexion->insert_id;$s->close();
            establecerRolUsuario($uid,$fila['rol'],$pid,false);
            if($fila['jornadas'])sgaUJGuardar($uid,$pid,$fila['jornadas']);
            $creados++;
        }
    }
    $conexion->commit();
    $grupo=auditoriaGrupo();
    registrarAuditoria('IMPORT','Usuarios','usuarios_csv',null,'Importación CSV de usuarios y roles realizada.',null,null,
        ['creados'=>$creados,'roles_actualizados'=>$actualizados,'jornadas_actualizadas'=>$jornadasActualizadas,
         'datos_corregidos'=>$datosCorregidos,'sin_cambios'=>$sinCambios,'cuentas_protegidas'=>$protegidos,
         'periodo_id'=>$pid,'jornadas_por_fila'=>$csvConJornadas], 'exito',null,$grupo,'info');
    flash('success',"Importación: $creados creados, $actualizados roles actualizados, $jornadasActualizadas cambios de jornadas, $datosCorregidos datos corregidos, $sinCambios sin cambios y $protegidos administradores protegidos.");
} catch (Throwable $e) {
    if (isset($f) && is_resource($f)) fclose($f);
    if (isset($conexion) && $conexion instanceof mysqli) $conexion->rollback();
    flash('error','Importación cancelada: '.$e->getMessage());
}
redir($destino);
