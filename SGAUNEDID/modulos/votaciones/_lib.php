<?php
require_once __DIR__ . '/../../lib/funciones.php';

function eleccionPeriodo(int $periodoId): ?array {
    global $conexion;
    $stmt=$conexion->prepare('SELECT e.*,p.nombre periodo FROM elecciones e JOIN periodos_academicos p ON p.id=e.periodo_id WHERE e.periodo_id=? LIMIT 1');
    $stmt->bind_param('i',$periodoId);$stmt->execute();$r=$stmt->get_result()->fetch_assoc()?:null;$stmt->close();return $r;
}

function eleccionPorId(int $id): ?array {
    global $conexion;
    $stmt=$conexion->prepare('SELECT e.*,p.nombre periodo FROM elecciones e JOIN periodos_academicos p ON p.id=e.periodo_id WHERE e.id=? LIMIT 1');
    $stmt->bind_param('i',$id);$stmt->execute();$r=$stmt->get_result()->fetch_assoc()?:null;$stmt->close();return $r;
}

function votacionCsrf(): string {
    if(empty($_SESSION['votacion_csrf'])){
        try{$_SESSION['votacion_csrf']=bin2hex(random_bytes(24));}
        catch(Throwable $e){$_SESSION['votacion_csrf']=hash('sha256',session_id().'|votacion');}
    }
    return (string)$_SESSION['votacion_csrf'];
}

function validarVotacionCsrf(): void {
    $token=(string)($_POST['csrf']??'');
    if($token==='' || !hash_equals(votacionCsrf(),$token)){
        http_response_code(419);die('La sesión del formulario expiró. Regresa al módulo e inténtalo nuevamente.');
    }
}

function poblacionEleccion(int $eleccionId, ?string $seccion=null): int {
    global $conexion;
    $sql="SELECT COUNT(DISTINCT m.estudiante_id) c
          FROM eleccion_aulas ea
          JOIN matriculas m ON m.aula_periodo_id=ea.aula_periodo_id AND m.estado='activo'
          WHERE ea.eleccion_id=?";
    if($seccion!==null){$sql.=' AND ea.seccion=?';$stmt=$conexion->prepare($sql);$stmt->bind_param('is',$eleccionId,$seccion);}
    else{$stmt=$conexion->prepare($sql);$stmt->bind_param('i',$eleccionId);}
    $stmt->execute();$c=(int)($stmt->get_result()->fetch_assoc()['c']??0);$stmt->close();return $c;
}

function votosEleccion(int $eleccionId, ?string $seccion=null): int {
    global $conexion;
    if($seccion!==null){$stmt=$conexion->prepare('SELECT COUNT(*) c FROM eleccion_votos WHERE eleccion_id=? AND seccion=?');$stmt->bind_param('is',$eleccionId,$seccion);}
    else{$stmt=$conexion->prepare('SELECT COUNT(*) c FROM eleccion_votos WHERE eleccion_id=?');$stmt->bind_param('i',$eleccionId);}
    $stmt->execute();$c=(int)($stmt->get_result()->fetch_assoc()['c']??0);$stmt->close();return $c;
}

function electorEleccion(int $eleccionId,int $usuarioId): ?array {
    global $conexion;
    $sql="SELECT m.id matricula_id,m.aula_periodo_id,ea.seccion,a.nivel,a.nombre aula,a.paralelo,u.cedula,u.apellidos,u.nombres
          FROM eleccion_aulas ea
          JOIN matriculas m ON m.aula_periodo_id=ea.aula_periodo_id AND m.estado='activo'
          JOIN aulas_periodo ap ON ap.id=ea.aula_periodo_id
          JOIN aulas a ON a.id=ap.aula_id
          JOIN usuarios u ON u.id=m.estudiante_id
          WHERE ea.eleccion_id=? AND m.estudiante_id=? LIMIT 1";
    $stmt=$conexion->prepare($sql);$stmt->bind_param('ii',$eleccionId,$usuarioId);$stmt->execute();$r=$stmt->get_result()->fetch_assoc()?:null;$stmt->close();return $r;
}

function eleccionEstaAbierta(array $e): bool {
    if(($e['estado']??'')!=='activa') return false;
    $ahora=time();
    if(!empty($e['fecha_inicio']) && $ahora<strtotime($e['fecha_inicio'])) return false;
    if(!empty($e['fecha_fin']) && $ahora>strtotime($e['fecha_fin'])) return false;
    return true;
}

function fotoCandidatoUrl(?string $foto): ?string {
    $foto=trim((string)$foto); if($foto==='')return null;
    return url('assets/uploads/votaciones/'.rawurlencode(basename($foto)));
}

function guardarFotoCandidato(array $archivo): ?string {
    if(empty($archivo['name']) || ($archivo['error']??UPLOAD_ERR_NO_FILE)===UPLOAD_ERR_NO_FILE)return null;
    if(($archivo['error']??UPLOAD_ERR_OK)!==UPLOAD_ERR_OK)throw new RuntimeException('No se pudo cargar la fotografía.');
    if(($archivo['size']??0)>5*1024*1024)throw new RuntimeException('La fotografía no puede superar 5 MB.');
    $ext=strtolower(pathinfo((string)$archivo['name'],PATHINFO_EXTENSION));
    $permitidas=['jpg','jpeg','png','webp'];
    if(!in_array($ext,$permitidas,true))throw new RuntimeException('Formato de fotografía no permitido.');
    if(function_exists('finfo_open')){
        $f=finfo_open(FILEINFO_MIME_TYPE);$mime=$f?finfo_file($f,$archivo['tmp_name']):null;if($f)finfo_close($f);
        if($mime && !in_array($mime,['image/jpeg','image/png','image/webp'],true))throw new RuntimeException('El archivo cargado no es una imagen válida.');
    }
    $dir=APP_ROOT.'/assets/uploads/votaciones';if(!is_dir($dir)&&!mkdir($dir,0775,true))throw new RuntimeException('No se pudo preparar la carpeta de fotografías.');
    try{$base=bin2hex(random_bytes(12));}catch(Throwable $e){$base=uniqid('cand_',true);}
    $nombre=$base.'.'.$ext;$dest=$dir.'/'.$nombre;
    if(!move_uploaded_file($archivo['tmp_name'],$dest))throw new RuntimeException('No se pudo guardar la fotografía.');
    return $nombre;
}
