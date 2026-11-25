<?php
/**
 * Auditoría central del SGA UNEDID.
 * Nunca debe interrumpir la operación principal si el registro de auditoría falla.
 */
function auditoriaGrupo(): string {
    try { return bin2hex(random_bytes(12)); }
    catch (Throwable $e) { return uniqid('aud_', true); }
}

function auditoriaIpInfo(): array {
    $remote = trim((string)($_SERVER['REMOTE_ADDR'] ?? ''));
    $forwarded = trim((string)($_SERVER['HTTP_X_FORWARDED_FOR'] ?? ''));
    $cf = trim((string)($_SERVER['HTTP_CF_CONNECTING_IP'] ?? ''));
    $real = trim((string)($_SERVER['HTTP_X_REAL_IP'] ?? ''));
    $public = null; $source = null;
    $candidates = [];
    if ($remote !== '') $candidates[] = ['ip'=>$remote,'src'=>'REMOTE_ADDR'];
    if ($cf !== '') $candidates[] = ['ip'=>$cf,'src'=>'CF_CONNECTING_IP'];
    if ($real !== '') $candidates[] = ['ip'=>$real,'src'=>'X_REAL_IP'];
    if ($forwarded !== '') {
        foreach (explode(',', $forwarded) as $part) {
            $ip = trim($part);
            if ($ip !== '') $candidates[] = ['ip'=>$ip,'src'=>'X_FORWARDED_FOR'];
        }
    }
    foreach ($candidates as $c) {
        if (filter_var($c['ip'], FILTER_VALIDATE_IP, FILTER_FLAG_NO_PRIV_RANGE | FILTER_FLAG_NO_RES_RANGE)) {
            $public = $c['ip']; $source = $c['src']; break;
        }
    }
    return [
        'remota'=>$remote !== '' ? $remote : null,
        'publica'=>$public,
        'fuente'=>$source,
        'forwarded'=>$forwarded !== '' ? substr($forwarded,0,255) : null,
    ];
}

function auditoriaJson($valor): ?string {
    if ($valor === null) return null;
    if (is_string($valor)) return $valor;
    $json = json_encode($valor, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_INVALID_UTF8_SUBSTITUTE);
    return $json === false ? null : $json;
}

function registrarAuditoria(
    string $accion,
    string $modulo,
    string $entidad,
    $entidadId,
    string $detalle,
    ?int $usuarioAfectadoId = null,
    $antes = null,
    $despues = null,
    string $resultado = 'exito',
    ?int $actorId = null,
    ?string $grupoEvento = null,
    string $criticidad = 'info'
): bool {
    global $conexion;
    try {
        if (!isset($conexion) || !($conexion instanceof mysqli)) return false;
        if ($actorId === null && !empty($_SESSION['usuario_id'])) $actorId = (int)$_SESSION['usuario_id'];
        $accion = strtoupper(substr(trim($accion),0,40));
        $modulo = substr(trim($modulo),0,80);
        $entidad = substr(trim($entidad),0,80);
        $entidadId = $entidadId === null ? null : substr((string)$entidadId,0,100);
        $detalle = substr(trim($detalle),0,4000);
        $resultado = in_array($resultado,['exito','fallo'],true) ? $resultado : 'exito';
        $criticidad = in_array($criticidad,['info','advertencia','critica'],true) ? $criticidad : 'info';
        $ip = auditoriaIpInfo();
        $ua = substr((string)($_SERVER['HTTP_USER_AGENT'] ?? ''),0,500);
        $metodo = substr((string)($_SERVER['REQUEST_METHOD'] ?? ''),0,10);
        $ruta = substr((string)($_SERVER['REQUEST_URI'] ?? ''),0,500);
        $sid = session_id();
        $sessionHash = $sid !== '' ? hash('sha256',$sid) : null;
        $antesJson = auditoriaJson($antes);
        $despuesJson = auditoriaJson($despues);
        if ($grupoEvento === null || $grupoEvento === '') $grupoEvento = auditoriaGrupo();

        $sql = "INSERT INTO auditoria_actividades
          (usuario_actor_id,usuario_afectado_id,accion,modulo,entidad,entidad_id,detalle,datos_antes,datos_despues,resultado,criticidad,ip_remota,ip_publica,ip_fuente,ip_forwarded,user_agent,metodo_http,ruta,session_hash,grupo_evento)
          VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)";
        $stmt = $conexion->prepare($sql);
        if (!$stmt) return false;
        $stmt->bind_param(
            'iissssssssssssssssss',
            $actorId,$usuarioAfectadoId,$accion,$modulo,$entidad,$entidadId,$detalle,$antesJson,$despuesJson,$resultado,$criticidad,
            $ip['remota'],$ip['publica'],$ip['fuente'],$ip['forwarded'],$ua,$metodo,$ruta,$sessionHash,$grupoEvento
        );
        $ok = $stmt->execute();
        $stmt->close();
        return $ok;
    } catch (Throwable $e) {
        return false;
    }
}

function usuarioAfectadoPorMatricula(int $matriculaId): ?int {
    global $conexion;
    try {
        $stmt=$conexion->prepare('SELECT estudiante_id FROM matriculas WHERE id=? LIMIT 1');
        $stmt->bind_param('i',$matriculaId);$stmt->execute();$r=$stmt->get_result()->fetch_assoc();$stmt->close();
        return $r ? (int)$r['estudiante_id'] : null;
    } catch (Throwable $e) { return null; }
}
