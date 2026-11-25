<?php
/**
 * Evaluacion cualitativa por parametros, SGA UNEDID.
 * Modelo inicial tomado de los ejes y ambitos de "INFORME APRENDIZAJE
 * TRIMESTRAL_INICIAL_PREPARATORIA.docx" proporcionado por la institucion.
 * No calcula promedios: cada ambito conserva su valoracion por trimestre.
 */
function sgaParametrosOpciones(): array {
    return ['A+','A-','B+','B-','C+','C-','D+','D-','E+','E-'];
}
function sgaParametrosModeloInicial(): array {
    return [
        ['DESARROLLO PERSONAL Y SOCIAL', 'IDENTIDAD Y AUTONOMÍA'],
        ['DESARROLLO PERSONAL Y SOCIAL', 'CONVIVENCIA'],
        ['CONOCIMIENTO DEL MEDIO NATURAL Y CULTURAL', 'DESCUBRIMIENTO Y COMPRENSIÓN DEL MEDIO NATURAL Y CULTURAL'],
        ['CONOCIMIENTO DEL MEDIO NATURAL Y CULTURAL', 'RELACIONES LÓGICO-MATEMÁTICA'],
        ['COMUNICACIÓN VERBAL Y NO VERBAL', 'COMPRENSIÓN Y EXPRESIÓN ORAL Y ESCRITA'],
        ['COMUNICACIÓN VERBAL Y NO VERBAL', 'COMPRENSIÓN ARTÍSTICA'],
        ['COMUNICACIÓN VERBAL Y NO VERBAL', 'EXPRESIÓN CORPORAL'],
        ['OTROS ÁMBITOS', 'EDUCACION FISICA'],
        ['OTROS ÁMBITOS', 'EDUCACION CULTURAL Y ARTISTICA'],
    ];
}
function sgaParametrosSoloVista(array $oferta): bool {
    return !sgaParametrosPuedeCalificar($oferta);
}
/** Crea los parametros iniciales solo una vez por oferta; no los regenera si estan inactivos. */
function sgaParametrosInicializar(mysqli $db, int $ofertaId, int $periodoId): void {
    sgaAsegurarPeriodoEditable($periodoId);
    $actual=ofertaDetalle($ofertaId);
    if(!$actual)throw new DomainException('Evaluación inexistente.');
    $apid=(int)$actual['aula_periodo_id'];
    if (!$db->begin_transaction()) throw new RuntimeException('No se pudo iniciar la configuracion de parametros.');
    try {
        sgaParametrosBloquearAula($db,$apid);
        $actual=ofertaDetalle($ofertaId);
        if(!$actual)throw new DomainException('Evaluación inexistente.');
        if(!sgaParametrosPuedeConfigurar($actual) && !sgaParametrosPuedeCalificar($actual))throw new DomainException('La evaluación no admite cambios.');
        $s=$db->prepare('SELECT id FROM ofertas_academicas WHERE id=? FOR UPDATE');
        $s->bind_param('i',$ofertaId); sgaEjecutar($s,'verificar la oferta'); $of=$s->get_result()->fetch_assoc(); $s->close();
        if (!$of) throw new DomainException('La asignatura no existe.');
        $s=$db->prepare('SELECT COUNT(*) total FROM sga_parametros_cualitativos WHERE oferta_id=?');
        $s->bind_param('i',$ofertaId); sgaEjecutar($s,'buscar parametros existentes');
        $total=(int)$s->get_result()->fetch_assoc()['total']; $s->close();
        if ($total === 0) {
            $s=$db->prepare('INSERT INTO sga_parametros_cualitativos (oferta_id,eje,ambito,orden,activo) VALUES (?,?,?,?,1)');
            foreach (sgaParametrosModeloInicial() as $n=>$param) {
                $eje=$param[0];$ambito=$param[1];$orden=$n+1;
                $s->bind_param('issi',$ofertaId,$eje,$ambito,$orden);sgaEjecutar($s,'cargar el modelo inicial');
            }
            $s->close();
            sgaAuditoriaObligatoria('CREATE','Calificaciones','parametros_cualitativos',$ofertaId,
                'Modelo de aprendizaje cualitativo inicializado para la oferta.',null,null,
                ['cantidad'=>count(sgaParametrosModeloInicial()),'modelo'=>'Inicial/Preparatoria'],'exito');
        }
        if (!$db->commit()) throw new RuntimeException('No se pudo confirmar la creacion de parametros.');
    } catch(Throwable $e) { $db->rollback();throw $e; }
}
function sgaParametrosDeOferta(mysqli $db, int $ofertaId, bool $soloActivos=true): array {
    $sql='SELECT p.id,p.eje,p.ambito,p.orden,p.activo,
      (SELECT COUNT(*) FROM sga_calificaciones_parametros c WHERE c.parametro_id=p.id) registros
      FROM sga_parametros_cualitativos p WHERE p.oferta_id=?';
    if ($soloActivos) $sql.=' AND p.activo=1';
    $sql.=' ORDER BY p.orden,p.id';
    $s=$db->prepare($sql);$s->bind_param('i',$ofertaId);sgaEjecutar($s,'consultar parametros');
    $res=$s->get_result()->fetch_all(MYSQLI_ASSOC);$s->close();return $res;
}
function sgaParametrosNotasDeOferta(mysqli $db, int $ofertaId, ?int $matriculaId=null): array {
    if ($matriculaId) {
        $s=$db->prepare('SELECT c.matricula_id,c.parametro_id,c.trimestre,c.literal FROM sga_calificaciones_parametros c JOIN sga_parametros_cualitativos p ON p.id=c.parametro_id AND p.oferta_id=c.oferta_id WHERE c.oferta_id=? AND c.matricula_id=?');
        $s->bind_param('ii',$ofertaId,$matriculaId);
    } else {
        $s=$db->prepare('SELECT c.matricula_id,c.parametro_id,c.trimestre,c.literal FROM sga_calificaciones_parametros c JOIN sga_parametros_cualitativos p ON p.id=c.parametro_id AND p.oferta_id=c.oferta_id WHERE c.oferta_id=?');
        $s->bind_param('i',$ofertaId);
    }
    sgaEjecutar($s,'consultar calificaciones cualitativas');$notas=[];
    foreach($s->get_result()->fetch_all(MYSQLI_ASSOC) as $r) {
        $notas[(int)$r['matricula_id']][(int)$r['parametro_id']][(int)$r['trimestre']]=$r['literal'];
    }
    $s->close();return $notas;
}
function sgaParametrosAlumnosDeOferta(mysqli $db,int $aulaPeriodoId): array {
    $s=$db->prepare("SELECT m.id matricula_id,m.numero_lista,u.apellidos,u.nombres,u.cedula
        FROM matriculas m JOIN usuarios u ON u.id=m.estudiante_id
        WHERE m.aula_periodo_id=? AND m.estado IN ('activo','finalizado')
        ORDER BY COALESCE(m.numero_lista,999999),u.apellidos,u.nombres");
    $s->bind_param('i',$aulaPeriodoId);sgaEjecutar($s,'consultar estudiantes');
    $rows=$s->get_result()->fetch_all(MYSQLI_ASSOC);$s->close();return $rows;
}

/** Bloqueo comun para asignacion del responsable, configuracion y notas. */
function sgaParametrosBloquearAula(mysqli $db,int $apid): array {
    $s=$db->prepare('SELECT id,periodo_id,aula_id,activo,evaluacion_cualitativa_parametros FROM aulas_periodo WHERE id=? FOR UPDATE');
    $s->bind_param('i',$apid);sgaEjecutar($s,'bloquear el aula');$r=$s->get_result()->fetch_assoc();$s->close();
    if(!$r)throw new DomainException('Aula inexistente.');
    return $r;
}
function sgaParametrosOfertasAula(mysqli $db,int $apid): array {
    $s=$db->prepare("SELECT o.id,o.docente_id,o.activo,o.evaluacion_aula,o.evaluacion_parametros_historica,s.nombre asignatura,
       CONCAT(u.apellidos,' ',u.nombres) docente,
       (SELECT COUNT(*) FROM sga_parametros_cualitativos q WHERE q.oferta_id=o.id) ambitos,
       (SELECT COUNT(*) FROM sga_calificaciones_parametros c WHERE c.oferta_id=o.id) valoraciones
       FROM ofertas_academicas o JOIN asignaturas s ON s.id=o.asignatura_id JOIN usuarios u ON u.id=o.docente_id
       WHERE o.aula_periodo_id=? AND (o.evaluacion_aula=1 OR o.evaluacion_parametros_historica=1) ORDER BY o.evaluacion_aula DESC,o.id");
    $s->bind_param('i',$apid);sgaEjecutar($s,'consultar evaluacion del aula');$rows=$s->get_result()->fetch_all(MYSQLI_ASSOC);$s->close();return $rows;
}
/** Invocar dentro de la transaccion del catalogo de aulas. No altera periodos cerrados. */
function sgaParametrosActualizarModoAula(mysqli $db,int $aulaId,int $periodoId,int $modo): void {
    if($periodoId<=0)return;
    $s=$db->prepare('SELECT ap.id,p.estado FROM aulas_periodo ap JOIN periodos_academicos p ON p.id=ap.periodo_id WHERE ap.aula_id=? AND ap.periodo_id=? LIMIT 1 FOR UPDATE');
    $s->bind_param('ii',$aulaId,$periodoId);sgaEjecutar($s,'consultar modalidad vigente');$r=$s->get_result()->fetch_assoc();$s->close();
    if(!$r || $r['estado']==='cerrado')return;
    $apid=(int)$r['id'];$ap=sgaParametrosBloquearAula($db,$apid);
    $antes=(int)$ap['evaluacion_cualitativa_parametros'];if($antes===$modo)return;
    if(!$modo){
        foreach(sgaParametrosOfertasAula($db,$apid) as $of){
            if((int)$of['valoraciones']>0)throw new DomainException('El aula tiene valoraciones cualitativas en este período. No se puede desactivar la modalidad sin perder su acceso académico.');
        }
    }
    // La seleccion de asignaturas y las notas/asistencias se conservan; no se restauran ofertas automaticamente.
    $s=$db->prepare('UPDATE ofertas_academicas SET activo=0 WHERE aula_periodo_id=? AND activo=1');
    $s->bind_param('i',$apid);sgaEjecutar($s,'desactivar las asignaciones anteriores');$n=$s->affected_rows;$s->close();
    $s=$db->prepare('UPDATE aulas_periodo SET evaluacion_cualitativa_parametros=? WHERE id=?');$s->bind_param('ii',$modo,$apid);sgaEjecutar($s,'guardar modalidad del aula');$s->close();
    sgaAuditoriaObligatoria('UPDATE','Gestión académica','aula_periodo',$apid,'Modalidad de evaluación del aula actualizada.',null,['evaluacion_cualitativa_parametros'=>$antes],['evaluacion_cualitativa_parametros'=>$modo,'ofertas_desactivadas'=>$n],'exito',null,null,'advertencia');
}
/** Un solo responsable; conserva la misma oferta/ID cuando cambia el docente. Transaccion externa. */
function sgaParametrosAsignarDocenteAula(mysqli $db,int $apid,int $docenteId,int $origenId=0): int {
    $ap=sgaParametrosBloquearAula($db,$apid);
    if(!(int)$ap['evaluacion_cualitativa_parametros'] || !(int)$ap['activo'])throw new DomainException('El aula no está activa en la modalidad por parámetros.');
    sgaAsegurarPeriodoEditable((int)$ap['periodo_id']);
    $ofertas=sgaParametrosOfertasAula($db,$apid);$principal=null;$previas=[];
    foreach($ofertas as $of){if((int)$of['evaluacion_aula'])$principal=$of;elseif((int)$of['ambitos'])$previas[(int)$of['id']]=$of;}
    if(!$principal && $previas){
        if($origenId===0 && count($previas)===1)$origenId=(int)array_key_first($previas);
        if(!isset($previas[$origenId]))throw new DomainException('Selecciona el registro anterior que será la evaluación principal del aula. Los demás permanecerán en el historial.');
        $principal=$previas[$origenId];
    }
    if($principal){
        $oid=(int)$principal['id'];
        $s=$db->prepare('UPDATE ofertas_academicas SET docente_id=?,activo=1,evaluacion_aula=1 WHERE id=? AND aula_periodo_id=?');
        $s->bind_param('iii',$docenteId,$oid,$apid);sgaEjecutar($s,'asignar responsable del aula');$s->close();
    }else{
        $s=$db->prepare("SELECT s.id FROM asignaturas s JOIN areas ar ON ar.id=s.area_id WHERE s.codigo='SGA_PARAM_AULA_INTERNO' AND ar.codigo='SGA_PARAM_AULA_INTERNO' AND s.archivado_en IS NULL AND ar.archivado_en IS NULL AND s.activo=0 AND ar.activo=0 LIMIT 1");
        sgaEjecutar($s,'buscar registro interno de evaluación');$fila=$s->get_result()->fetch_assoc();$s->close();
        if(!$fila)throw new DomainException('Instala SQL_SGA_EVALUACION_CUALITATIVA_POR_AULA.sql. Falta el registro interno de evaluación.');
        $asig=(int)$fila['id'];
        $s=$db->prepare('INSERT INTO ofertas_academicas(aula_periodo_id,asignatura_id,docente_id,activo,evaluacion_aula) VALUES(?,?,?,1,1)');
        $s->bind_param('iii',$apid,$asig,$docenteId);sgaEjecutar($s,'crear evaluación del aula');$oid=(int)$db->insert_id;$s->close();
    }
    $s=$db->prepare('UPDATE ofertas_academicas SET activo=0 WHERE aula_periodo_id=? AND id<>? AND activo=1');
    $s->bind_param('ii',$apid,$oid);sgaEjecutar($s,'asegurar un único docente');$s->close();
    sgaAuditoriaObligatoria($principal?'UPDATE':'CREATE','Gestión académica','evaluacion_aula',$oid,'Docente único responsable de los tres trimestres.', $docenteId,$principal,['aula_periodo_id'=>$apid,'docente_id'=>$docenteId,'evaluacion_aula'=>1],'exito',null,null,'advertencia');
    return $oid;
}
/** Solo el registro principal activo de un aula por parametros admite escritura. */
function sgaParametrosEvaluacionEditable(array $o): bool {
    return (int)($o['id']??0)>0 && (int)($o['periodo_id']??0)>0
        && !empty($o['evaluacion_aula']) && !empty($o['aula_evaluacion_parametros'])
        && !empty($o['aula_periodo_activo']) && !empty($o['activo'])
        && !empty($o['periodo_estado']) && $o['periodo_estado']!=='cerrado';
}
/** Administrador (superadmin) global o subadministrador de la jornada y periodo reales de la oferta. */
function sgaParametrosAdministracionAutorizada(array $o): bool {
    if((int)($_SESSION['usuario_id']??0)<=0 || (int)($o['id']??0)<=0)return false;
    if(esSuperadmin())return true;
    return esSubadmin() && puedeAccederOfertaSubadmin((int)$o['id']);
}
function sgaParametrosPuedeConfigurar(array $o): bool {
    return sgaParametrosEvaluacionEditable($o) && sgaParametrosAdministracionAutorizada($o);
}
function sgaParametrosPuedeCalificar(array $o): bool {
    if(!sgaParametrosEvaluacionEditable($o))return false;
    // Administrar calificaciones no reasigna al docente responsable del aula.
    if(sgaParametrosAdministracionAutorizada($o))return true;
    $uid=(int)($_SESSION['usuario_id']??0);
    return $uid>0 && rolOperativoActual()==='docente'
        && esDocenteOperativo((int)$o['periodo_id']) && (int)($o['docente_id']??0)===$uid;
}
/** El registro interno no puede ser editado desde catalogos. No archivar fuentes de historial. */
function sgaParametrosProtegerCatalogo(mysqli $db,string $tipo,int $id,string $accion=''): void {
    if(!in_array($tipo,['asignaturas','areas'],true))throw new DomainException('Catálogo inválido.');
    $s=$db->prepare('SELECT codigo FROM '.$tipo.' WHERE id=?');$s->bind_param('i',$id);sgaEjecutar($s,'verificar registro de catálogo');$f=$s->get_result()->fetch_assoc();$s->close();
    if(($f['codigo']??'')==='SGA_PARAM_AULA_INTERNO')throw new DomainException('Registro interno reservado del sistema.');
    if($accion!=='eliminar')return;
    $campo=$tipo==='areas'?'s.area_id':'s.id';
    $s=$db->prepare('SELECT 1 FROM ofertas_academicas o JOIN asignaturas s ON s.id=o.asignatura_id WHERE '.$campo.'=? AND (o.evaluacion_aula=1 OR o.evaluacion_parametros_historica=1) LIMIT 1');
    $s->bind_param('i',$id);sgaEjecutar($s,'proteger historial cualitativo');$existe=(bool)$s->get_result()->fetch_row();$s->close();
    if($existe)throw new DomainException('El registro conserva evaluaciones cualitativas históricas. No puede archivarse.');
}

/** Presenta únicamente las valoraciones de la matrícula autorizada por el portal. */
function sgaParametrosResumenConsulta(mysqli $db,int $oid,int $mid): void {
    $params=sgaParametrosDeOferta($db,$oid);$notas=sgaParametrosNotasDeOferta($db,$oid,$mid);
    echo '<section class="card" style="margin-top:16px"><h2>Evaluación cualitativa del aula</h2>';
    if(!$params){echo '<p class="muted">Todavía no se han configurado los parámetros.</p></section>';return;}
    echo '<div class="table-wrap"><table class="table"><thead><tr><th>Eje</th><th>Ámbito / indicador</th><th>Trimestre 1</th><th>Trimestre 2</th><th>Trimestre 3</th></tr></thead><tbody>';
    foreach($params as $p){echo '<tr><td>'.e($p['eje']).'</td><td>'.e($p['ambito']).'</td>';for($t=1;$t<=3;$t++){echo '<td>'.e($notas[$mid][(int)$p['id']][$t]??'Pendiente').'</td>';}echo '</tr>';}
    echo '</tbody></table></div></section>';
}
