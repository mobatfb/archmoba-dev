<?php
/** Relaciones muchos-a-muchos y notificaciones familiares del SGA UNEDID. */
require_once __DIR__.'/funciones.php';

function sgaRepEsRepresentante(?int $usuarioId = null): bool {
    global $conexion;
    $id = $usuarioId ?? (int)($_SESSION['usuario_id'] ?? 0);
    if ($id <= 0) return false;
    $s = $conexion->prepare("SELECT 1 FROM usuario_roles ur JOIN roles r ON r.id=ur.rol_id WHERE ur.usuario_id=? AND ur.periodo_id IS NULL AND r.codigo='representante' LIMIT 1");
    $s->bind_param('i', $id); $s->execute(); $ok = (bool)$s->get_result()->fetch_row(); $s->close();
    return $ok;
}

function sgaRepPuedeConsultarEstudiante(int $estudianteId, int $periodoId, bool $soloPersonal = false): bool {
    global $conexion;
    if ($estudianteId <= 0 || $periodoId <= 0 || empty($_SESSION['usuario_id'])) return false;
    $s = $conexion->prepare("SELECT ap.id aula_periodo_id, a.jornada_id FROM matriculas m
        JOIN aulas_periodo ap ON ap.id=m.aula_periodo_id AND ap.activo=1
        JOIN aulas a ON a.id=ap.aula_id
        JOIN usuarios u ON u.id=m.estudiante_id AND u.activo=1
        WHERE m.estudiante_id=? AND ap.periodo_id=? AND m.estado='activo'");
    $s->bind_param('ii', $estudianteId, $periodoId); $s->execute();
    $matriculas = $s->get_result()->fetch_all(MYSQLI_ASSOC); $s->close();
    if (!$matriculas) return false;
    if (esAdminAcademico()) {
        if(esSubadmin()){
            // Un alumno que tiene matrícula en otra jornada no se gestiona desde aquí.
            foreach($matriculas as $m){
                if(!puedeAccederJornada((int)$m['jornada_id'],$periodoId)) return false;
            }
        }
        return true;
    }
    if (esDocenteOperativo($periodoId)) {
        $uid = (int)$_SESSION['usuario_id'];
        $s = $conexion->prepare("SELECT 1 FROM ofertas_academicas o
            JOIN matriculas m ON m.aula_periodo_id=o.aula_periodo_id AND m.estado='activo'
            JOIN aulas_periodo ap ON ap.id=o.aula_periodo_id AND ap.activo=1
            WHERE o.docente_id=? AND m.estudiante_id=? AND ap.periodo_id=? AND o.activo=1 LIMIT 1");
        $s->bind_param('iii', $uid, $estudianteId, $periodoId); $s->execute();
        $ok = (bool)$s->get_result()->fetch_row(); $s->close();
        if ($ok) return true;
    }
    if ($soloPersonal || !esRepresentanteOperativo()) return false;
    $uid = (int)$_SESSION['usuario_id'];
    $s = $conexion->prepare('SELECT 1 FROM sga_representantes_estudiantes WHERE representante_id=? AND estudiante_id=? AND activo=1 LIMIT 1');
    $s->bind_param('ii', $uid, $estudianteId); $s->execute(); $ok = (bool)$s->get_result()->fetch_row(); $s->close();
    return $ok;
}

/** Acceso exclusivo de administradores (no basta ser representante). */
function sgaRepPuedeVincular(int $estudianteId, int $periodoId): bool {
    return esAdminAcademico() && sgaRepPuedeConsultarEstudiante($estudianteId, $periodoId, true);
}

function sgaRepBuscarEstudiantes(string $consulta, int $periodoId): array {
    global $conexion;
    $consulta = trim($consulta);
    if ($periodoId <= 0 || strlen($consulta) < 3 || strlen($consulta) > 80) return [];
    if (!esAdminAcademico() && !esDocenteOperativo($periodoId)) return [];
    $like = '%'.$consulta.'%';
    $s = $conexion->prepare("SELECT DISTINCT u.id,u.cedula,u.apellidos,u.nombres,
        CONCAT(a.nivel,' ',a.nombre,' ',a.paralelo) aula
        FROM usuarios u JOIN matriculas m ON m.estudiante_id=u.id AND m.estado='activo'
        JOIN aulas_periodo ap ON ap.id=m.aula_periodo_id AND ap.activo=1
        JOIN aulas a ON a.id=ap.aula_id
        WHERE ap.periodo_id=? AND u.activo=1
          AND (u.cedula LIKE ? OR u.apellidos LIKE ? OR u.nombres LIKE ? OR CONCAT(u.apellidos,' ',u.nombres) LIKE ?)
        ORDER BY u.apellidos,u.nombres LIMIT 200");
    $s->bind_param('issss',$periodoId,$like,$like,$like,$like);$s->execute();
    $rows=$s->get_result()->fetch_all(MYSQLI_ASSOC);$s->close();
    return array_values(array_filter($rows, static fn($r)=>sgaRepPuedeConsultarEstudiante((int)$r['id'],$periodoId,true)));
}

function sgaRepBuscarRepresentantes(string $consulta): array {
    global $conexion;
    $consulta=trim($consulta);
    if (!esAdminAcademico() || strlen($consulta)<3 || strlen($consulta)>80) return [];
    $like='%'.$consulta.'%';
    $s=$conexion->prepare("SELECT DISTINCT u.id,u.cedula,u.apellidos,u.nombres,u.correo FROM usuarios u
        JOIN usuario_roles ur ON ur.usuario_id=u.id AND ur.periodo_id IS NULL
        JOIN roles r ON r.id=ur.rol_id AND r.codigo='representante'
        WHERE u.activo=1 AND (u.cedula LIKE ? OR u.apellidos LIKE ? OR u.nombres LIKE ?) ORDER BY u.apellidos,u.nombres LIMIT 30");
    $s->bind_param('sss',$like,$like,$like);
    $s->execute();$rows=$s->get_result()->fetch_all(MYSQLI_ASSOC);$s->close();return $rows;
}

function sgaRepDatosRepresentante(int $representanteId): ?array {
    global $conexion;
    if($representanteId<=0 || !esAdminAcademico())return null;
    $s=$conexion->prepare("SELECT u.id,u.cedula,u.apellidos,u.nombres,u.correo FROM usuarios u
        JOIN usuario_roles ur ON ur.usuario_id=u.id AND ur.periodo_id IS NULL
        JOIN roles r ON r.id=ur.rol_id AND r.codigo='representante'
        WHERE u.id=? AND u.activo=1 LIMIT 1");
    $s->bind_param('i',$representanteId);$s->execute();$row=$s->get_result()->fetch_assoc()?:null;$s->close();return $row;
}

function sgaRepDatosEstudiante(int $estudianteId, int $periodoId, bool $personal = true): ?array {
    global $conexion;
    if(!sgaRepPuedeConsultarEstudiante($estudianteId,$periodoId,$personal))return null;
    $s=$conexion->prepare("SELECT u.id,u.cedula,u.apellidos,u.nombres,
        CONCAT(a.nivel,' ',a.nombre,' ',a.paralelo) aula
        FROM usuarios u JOIN matriculas m ON m.estudiante_id=u.id AND m.estado='activo'
        JOIN aulas_periodo ap ON ap.id=m.aula_periodo_id AND ap.activo=1
        JOIN aulas a ON a.id=ap.aula_id
        WHERE u.id=? AND ap.periodo_id=? LIMIT 1");
    $s->bind_param('ii',$estudianteId,$periodoId);$s->execute();$row=$s->get_result()->fetch_assoc()?:null;$s->close();return $row;
}

function sgaRepRepresentantesDe(int $estudianteId): array {
    global $conexion;
    $s=$conexion->prepare("SELECT re.id vinculacion_id,u.id,u.cedula,u.apellidos,u.nombres,u.correo,
        CASE WHEN u.correo IS NOT NULL AND u.correo<>'' THEN 1 ELSE 0 END tiene_correo
        FROM sga_representantes_estudiantes re JOIN usuarios u ON u.id=re.representante_id AND u.activo=1
        JOIN usuario_roles ur ON ur.usuario_id=u.id AND ur.periodo_id IS NULL
        JOIN roles r ON r.id=ur.rol_id AND r.codigo='representante'
        WHERE re.estudiante_id=? AND re.activo=1 ORDER BY u.apellidos,u.nombres");
    $s->bind_param('i',$estudianteId);$s->execute();$rows=$s->get_result()->fetch_all(MYSQLI_ASSOC);$s->close();return $rows;
}

function sgaRepVincular(int $representanteId,int $estudianteId,int $periodoId): bool {
    global $conexion;
    if (!sgaRepPuedeVincular($estudianteId,$periodoId)) throw new DomainException('Estudiante fuera de tu jornada o sin matrícula activa.');
    $rep=sgaRepDatosRepresentante($representanteId);
    if (!$rep) throw new DomainException('Representante inexistente, inactivo o sin rol asignado.');
    if (!filter_var($rep['correo']??'',FILTER_VALIDATE_EMAIL)) throw new DomainException('El representante debe tener un correo válido antes de ser vinculado.');
    if ($representanteId===$estudianteId) throw new DomainException('No puedes vincular una cuenta consigo misma.');
    $actor=(int)$_SESSION['usuario_id'];
    $s=$conexion->prepare('INSERT INTO sga_representantes_estudiantes (representante_id,estudiante_id,creado_por,actualizado_por) VALUES(?,?,?,?) '
        .'ON DUPLICATE KEY UPDATE activo=1,actualizado_por=VALUES(actualizado_por),actualizado_en=CURRENT_TIMESTAMP');
    $s->bind_param('iiii',$representanteId,$estudianteId,$actor,$actor);
    if(!$s->execute()){ $s->close(); throw new RuntimeException('No se pudo vincular al representante.'); }
    $cambio=$s->affected_rows>0;$s->close();return $cambio;
}

function sgaRepDesvincular(int $representanteId,int $estudianteId,int $periodoId): void {
    global $conexion;
    if (!sgaRepPuedeVincular($estudianteId,$periodoId)) throw new DomainException('No tienes autorizacion para modificar este estudiante.');
    $actor=(int)$_SESSION['usuario_id'];
    $s=$conexion->prepare('UPDATE sga_representantes_estudiantes SET activo=0,actualizado_por=? WHERE representante_id=? AND estudiante_id=? AND activo=1');
    $s->bind_param('iii',$actor,$representanteId,$estudianteId);
    if(!$s->execute()){ $s->close(); throw new RuntimeException('No se pudo quitar la vinculacion.'); }$s->close();
}

/** Crear evento y sus correos en una transaccion preexistente o nueva. */
function sgaRepCrearNovedad(int $estudianteId,int $periodoId,int $autor,string $tipo,string $asunto,string $detalle,?string $eventoClave=null): int {
    global $conexion;
    $tipos=['general','academica','asistencia','comportamiento','urgente'];
    if(!in_array($tipo,$tipos,true))throw new DomainException('Tipo de novedad incorrecto.');
    if($estudianteId<=0||$periodoId<=0||$autor<=0)throw new DomainException('Datos de la novedad incorrectos.');
    if($asunto===''||strlen($asunto)>180||$detalle===''||strlen($detalle)>2000)throw new DomainException('Completa el asunto y el detalle (hasta 2.000 caracteres).');
    $conexion->begin_transaction();
    try {
        if($eventoClave!==null){
            $s=$conexion->prepare('SELECT id FROM sga_representantes_novedades WHERE evento_clave=? LIMIT 1');
            $s->bind_param('s',$eventoClave);$s->execute();$ex=$s->get_result()->fetch_assoc();$s->close();
            if($ex){$conexion->commit();return (int)$ex['id'];}
        }
        $s=$conexion->prepare('INSERT INTO sga_representantes_novedades (estudiante_id,periodo_id,creada_por,tipo,asunto,detalle,evento_clave) VALUES(?,?,?,?,?,?,?)');
        $s->bind_param('iiissss',$estudianteId,$periodoId,$autor,$tipo,$asunto,$detalle,$eventoClave);
        if(!$s->execute())throw new RuntimeException('No se pudo registrar la novedad.');
        $id=(int)$conexion->insert_id;$s->close();
        $personas=sgaRepRepresentantesDe($estudianteId);
        foreach($personas as $rep){
            $rid=(int)$rep['id'];$correo=trim((string)($rep['correo']??''));
            $valido=filter_var($correo,FILTER_VALIDATE_EMAIL)!==false;
            $estado=$valido?'pendiente':'sin_correo';$correoDb=$valido?$correo:null;
            $s=$conexion->prepare('INSERT INTO sga_representantes_envios(novedad_id,representante_id,correo_destino,estado) VALUES(?,?,?,?)');
            $s->bind_param('iiss',$id,$rid,$correoDb,$estado);
            if(!$s->execute())throw new RuntimeException('No se pudo registrar el envio al representante.');$s->close();
        }
        if(!$conexion->commit())throw new RuntimeException('No se confirmó la novedad.');
        registrarAuditoria('CREATE','Representantes','novedad',$id,'Se registro una novedad para notificar a los representantes.', $estudianteId, null, ['tipo'=>$tipo,'envios'=>count($personas)]);
        return $id;
    }catch(Throwable $e){$conexion->rollback();throw $e;}
}

/** Envia notificaciones pendientes; nunca revela el error SMTP al destinatario o al alumnado. */
function sgaRepEnviarPendientes(int $limite=12,?int $soloNovedad=null): array {
    global $conexion;
    require_once __DIR__.'/sga_smtp.php';
    $limite=max(1,min($limite,40));
    $config=require __DIR__.'/../config/recuperacion.php';
    $smtpSettings=$config['smtp']??[];
    $resultado=['enviados'=>0,'errores'=>0,'omitidos'=>0];
    // Recupera entregas interrumpidas por cierres de PHP; no reintenta mas de tres veces.
    $conexion->query("UPDATE sga_representantes_envios SET estado='pendiente' WHERE estado='enviando' AND actualizado_en < DATE_SUB(NOW(),INTERVAL 10 MINUTE) AND intentos<3");
    $conexion->query("UPDATE sga_representantes_envios SET estado='error',ultimo_error='Reintentos agotados' WHERE estado='enviando' AND actualizado_en < DATE_SUB(NOW(),INTERVAL 10 MINUTE) AND intentos>=3");
    $where=$soloNovedad!==null?' AND e.novedad_id='.(int)$soloNovedad:'';
    $sql="SELECT e.id,e.novedad_id,e.representante_id,e.correo_destino,n.tipo,n.asunto,n.detalle,n.creada_en,
        u.apellidos,u.nombres,autor.nombres AS autor_nombres,autor.apellidos AS autor_apellidos
        FROM sga_representantes_envios e
        JOIN sga_representantes_novedades n ON n.id=e.novedad_id
        JOIN usuarios u ON u.id=n.estudiante_id
        JOIN usuarios autor ON autor.id=n.creada_por
        WHERE e.estado IN ('pendiente','error') AND e.intentos<3
        AND (e.estado='pendiente' OR e.actualizado_en < DATE_SUB(NOW(),INTERVAL 5 MINUTE))".$where.
        ' ORDER BY e.id LIMIT '.$limite;
    $rows=$conexion->query($sql);
    if(!$rows)throw new RuntimeException('No se pudo consultar la cola de correos.');
    $envios=$rows->fetch_all(MYSQLI_ASSOC);
    foreach($envios as $r){
        $id=(int)$r['id'];$rid=(int)$r['representante_id'];$nid=(int)$r['novedad_id'];
        $s=$conexion->prepare("UPDATE sga_representantes_envios SET estado='enviando',intentos=intentos+1 WHERE id=? AND estado IN ('pendiente','error') AND intentos<3");
        $s->bind_param('i',$id);$s->execute();$locked=$s->affected_rows===1;$s->close();
        if(!$locked)continue;
        $s=$conexion->prepare("SELECT u.correo FROM usuarios u
          JOIN sga_representantes_estudiantes re ON re.representante_id=u.id AND re.activo=1
          JOIN sga_representantes_novedades n ON n.id=? AND n.estudiante_id=re.estudiante_id
          JOIN usuario_roles ur ON ur.usuario_id=u.id AND ur.periodo_id IS NULL
          JOIN roles rol ON rol.id=ur.rol_id AND rol.codigo='representante'
          WHERE u.id=? AND u.activo=1 LIMIT 1");
        $s->bind_param('ii',$nid,$rid);$s->execute();$actual=$s->get_result()->fetch_assoc()?:null;$s->close();
        if(!$actual || !filter_var($actual['correo']??'',FILTER_VALIDATE_EMAIL) || strcasecmp((string)$actual['correo'],(string)$r['correo_destino'])!==0){
            $s=$conexion->prepare("UPDATE sga_representantes_envios SET estado='omitido',ultimo_error='Vinculo o correo no vigente' WHERE id=?");
            $s->bind_param('i',$id);$s->execute();$s->close();$resultado['omitidos']++;continue;
        }
        $asunto='SGA UNEDID | '.$r['asunto'];
        // La novedad ya conserva su autor en creada_por: usarlo en lugar de la sesion,
        // porque los reintentos y el cron tambien envian correos sin usuario conectado.
        $autorNovedad=trim((string)($r['autor_nombres']??'').' '.(string)($r['autor_apellidos']??''));
        $autorNovedad=trim(preg_replace('/\s+/u',' ',$autorNovedad)??$autorNovedad);
        if($autorNovedad==='')$autorNovedad='Usuario registrado del SGA';
        $mensaje="Estimado/a representante:\n\nSe ha registrado una novedad relacionada con el/la estudiante ".$r['apellidos'].' '.$r['nombres'].".\n\nTipo: ".$r['tipo']."\nAsunto: ".$r['asunto']."\nDetalle: \n".$r['detalle']."\n\nFecha de registro: ".$r['creada_en']."\nSuscrito por: ".$autorNovedad."\n\nPuede consultar los detalles ingresando a ".rtrim((string)($config['app_url']??'https://sgaunedid.aulaprofenathaly.com'),'/')."\n\nMensaje informativo de UNEDID. Por favor no responda a este correo.";
        try {
            (new SgaSmtp((int)($smtpSettings['timeout']??10)))->send($smtpSettings,(string)$actual['correo'],$asunto,$mensaje);
            $s=$conexion->prepare("UPDATE sga_representantes_envios SET estado='enviado',ultimo_error=NULL,enviado_en=NOW() WHERE id=?");
            $s->bind_param('i',$id);$s->execute();$s->close();$resultado['enviados']++;
        }catch(Throwable $e){
            error_log('[SGA UNEDID] Fallo de envio a representante, registro '.$id.': '.get_class($e));
            $s=$conexion->prepare("UPDATE sga_representantes_envios SET estado='error',ultimo_error='No se pudo completar el envio SMTP' WHERE id=?");
            $s->bind_param('i',$id);$s->execute();$s->close();$resultado['errores']++;
        }
    }
    return $resultado;
}
