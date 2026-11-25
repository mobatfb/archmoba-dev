<?php
require_once __DIR__.'/../../lib/funciones.php';
require_once __DIR__.'/importacion_helper.php';
exigirLogin();
$oid=(int)($_POST['oferta_id']??$_GET['oferta_id']??0);
$trim=(int)($_POST['trimestre']??$_GET['trimestre']??1);
if(!$oid || $trim<1 || $trim>3 || !puedeGestionarOferta($oid)){
    http_response_code(403);die('No tienes acceso a la asignatura o trimestre seleccionados.');
}
impedirNotasEnVisorComportamiento($oid);
$o=ofertaDetalle($oid);
if(!$o){http_response_code(404);die('Asignatura inexistente.');}
if(empty($_SESSION['imp_calificaciones_csrf']))$_SESSION['imp_calificaciones_csrf']=bin2hex(random_bytes(20));
$csrf=$_SESSION['imp_calificaciones_csrf'];
$urlActual='modulos/calificaciones/importar.php?oferta_id='.$oid.'&trimestre='.$trim;
$alumnos=[];
$st=$conexion->prepare("SELECT m.id,m.estudiante_id,u.apellidos,u.nombres,u.cedula,m.numero_lista FROM matriculas m JOIN usuarios u ON u.id=m.estudiante_id WHERE m.aula_periodo_id=? AND m.estado='activo' ORDER BY COALESCE(m.numero_lista,9999),u.apellidos,u.nombres");
$apid=(int)$o['aula_periodo_id'];
$st->bind_param('i',$apid);$st->execute();$alumnos=$st->get_result()->fetch_all(MYSQLI_ASSOC);$st->close();
$porId=[];foreach($alumnos as $al)$porId[(int)$al['id']]=$al;

function impPersistirCampos(): array {
    return [
        'deber_ap1','deber_ap2','deber_ap3','deber_promedio','deber_refuerzo','deber_promedio_aporte',
        'tarea_ap1','tarea_ap2','tarea_ap3','tarea_promedio','tarea_refuerzo','tarea_promedio_aporte',
        'leccion_ap1','leccion_ap2','leccion_ap3','leccion_promedio','leccion_refuerzo','leccion_promedio_aporte',
        'grupo_ap1','grupo_ap2','grupo_ap3','grupo_promedio','grupo_refuerzo','grupo_promedio_aporte',
        'promedio_aportes','ponderado_aportes',
        'nota_disciplinar','trabajo_refuerzo_disciplinar','promedio_disciplinar','nota_producto_final',
        'promedio_proyecto','promedio_evaluacion_sumativa','ponderado_sumativa','nota_final','cualitativo',
    ];
}
function impEjecutarGuardado(mysqli_stmt $save,array $persistir,int $oid,int $mid,int $trim,array $n,array $calc): void {
    $valores=array_merge($n,$calc);
    $params=[$oid,$mid,$trim];
    foreach($persistir as $campo)$params[]=$valores[$campo]??null;
    $tipos='iii'.str_repeat('d',count($persistir)-1).'s';
    $refs=[];foreach($params as $k=>&$v)$refs[$k]=&$v;
    unset($v);array_unshift($refs,$tipos);
    call_user_func_array([$save,'bind_param'],$refs);
    if(!$save->execute())throw new RuntimeException('No se pudo guardar una calificacion: '.$save->error);
}
function impCommitir(array $preview,array $elegidos,array $o,array $porId): array {
    global $conexion;
    $oid=(int)$preview['oferta_id'];$trim=(int)$preview['trimestre'];
    $filas=$preview['contenido']['filas'];$validos=[];$destinos=[];$omitidos=0;
    foreach($filas as $fila) {
        $f=(int)$fila['fila'];$seleccion=$elegidos[$f]??'0';
        if(!is_scalar($seleccion) || !preg_match('/^[0-9]+$/',(string)$seleccion))
            throw new RuntimeException('Seleccion de matricula invalida en fila '.$f.'.');
        $mid=(int)$seleccion;
        if(!$mid){$omitidos++;continue;}
        if(trim($fila['nombre'])==='' || !$fila['notas'])throw new RuntimeException('Hay una fila sin nombre o calificaciones seleccionada.');
        if(!isset($porId[$mid]))throw new RuntimeException('Un estudiante seleccionado ya no pertenece a este paralelo.');
        if(isset($destinos[$mid]))throw new RuntimeException('Un estudiante fue seleccionado en mas de una fila ('.$destinos[$mid].' y '.$f.'). Corrige la asignacion antes de importar.');
        $destinos[$mid]=$f;
        $validos[]=['fila'=>$f,'matricula_id'=>$mid,'notas'=>$fila['notas']];
    }
    if(!$validos)throw new RuntimeException('Selecciona al menos una fila con estudiante y notas para importar.');
    // Entirely blank AP columns are not used this term. A literal 0 is a grade, not an empty cell.
    $activas=array_fill_keys(array_values(impCamposAportes()),false);
    foreach($validos as $registro)foreach(array_keys($activas) as $col)if(array_key_exists($col,$registro['notas']))$activas[$col]=true;
    $config=obtenerConfiguracion((int)$o['periodo_id']);
    $grupoAud=auditoriaGrupo();$audits=[];$guardados=0;$recalculados=0;
    $persistir=impPersistirCampos();
    $columnas=array_merge(['oferta_id','matricula_id','trimestre'],$persistir);
    $sql='INSERT INTO calificaciones_trimestre (`'.implode('`,`',$columnas).'`) VALUES ('.implode(',',array_fill(0,count($columnas),'?')).') ON DUPLICATE KEY UPDATE '.implode(',',array_map(static fn($c)=>'`'.$c.'`=VALUES(`'.$c.'`)',$persistir));
    $camposRecalcular=['deber_promedio','deber_promedio_aporte','tarea_promedio','tarea_promedio_aporte',
        'leccion_promedio','leccion_promedio_aporte','grupo_promedio','grupo_promedio_aporte',
        'promedio_aportes','ponderado_aportes','promedio_disciplinar','promedio_proyecto',
        'promedio_evaluacion_sumativa','ponderado_sumativa','nota_final','cualitativo'];
    $sqlRec='UPDATE calificaciones_trimestre SET '.implode(',',array_map(static fn($c)=>'`'.$c.'`=?',$camposRecalcular)).' WHERE id=?';
    $raw=array_merge(array_values(impCamposAportes()),array_values(impCamposOtros()));
    $conexion->begin_transaction();
    try {
        // Configuration applies to this subject AND ONLY the explicitly selected trimester.
        $stCfg=$conexion->prepare('INSERT INTO configuracion_aportes(oferta_id,trimestre,campo,activo) VALUES(?,?,?,?) ON DUPLICATE KEY UPDATE activo=VALUES(activo)');
        foreach($activas as $campo=>$estaActivo) {
            $activo=$estaActivo?1:0;
            $stCfg->bind_param('iisi',$oid,$trim,$campo,$activo);
            sgaEjecutar($stCfg,'guardar configuracion del Excel');
        }
        $stCfg->close();
        $save=$conexion->prepare($sql);
        $sel=$conexion->prepare('SELECT * FROM calificaciones_trimestre WHERE oferta_id=? AND matricula_id=? AND trimestre=? LIMIT 1 FOR UPDATE');
        foreach($validos as $reg) {
            $mid=(int)$reg['matricula_id'];
            $sel->bind_param('iii',$oid,$mid,$trim);$sel->execute();
            $antes=$sel->get_result()->fetch_assoc()?:null;
            $n=[];
            foreach($raw as $c)$n[$c]=$antes && $antes[$c]!==null?(float)$antes[$c]:null;
            // Retain previous subject grades in inactive columns, but ignore them in calculations.
            // In active AP columns, an empty student cell means the student received 0.
            foreach($activas as $c=>$activo)if($activo)$n[$c]=$reg['notas'][$c]??0.0;
            // Only explicitly filled reinforcement/summative cells update previous values.
            foreach(impCamposOtros() as $c)if(array_key_exists($c,$reg['notas']))$n[$c]=$reg['notas'][$c];
            foreach(['proyecto_interdisciplinar','proyecto_refuerzo','actividad_mejora','promedio_proyecto','ponderado_sumativa'] as $c)
                $n[$c]=$antes && $antes[$c]!==null?(float)$antes[$c]:null;
            $calc=calcularTrimestre($n,$config,$o['asignatura'],(bool)$o['usa_literal_especial'],$activas,!empty($o['aula_resultados_cualitativos']));
            impEjecutarGuardado($save,$persistir,$oid,$mid,$trim,$n,$calc);
            $guardados++;
            $audits[]=['uid'=>(int)$porId[$mid]['estudiante_id'],'matricula_id'=>$mid,
                'nombre'=>$porId[$mid]['apellidos'].' '.$porId[$mid]['nombres'],
                'fila'=>$reg['fila'],'campos'=>$reg['notas'],'anterior'=>$antes?'UPDATE':'CREATE'];
        }
        $sel->close();$save->close();
        // Other students already in this subject/term must use the new AP activation state too.
        $stRec=$conexion->prepare($sqlRec);
        $stAll=$conexion->prepare('SELECT * FROM calificaciones_trimestre WHERE oferta_id=? AND trimestre=?');
        $stAll->bind_param('ii',$oid,$trim);$stAll->execute();
        $rAll=$stAll->get_result();
        while($r=$rAll->fetch_assoc()) {
            $n=[];
            foreach(array_merge($raw,['proyecto_interdisciplinar','proyecto_refuerzo','actividad_mejora','promedio_proyecto','ponderado_sumativa']) as $c)
                $n[$c]=$r[$c]===null?null:(float)$r[$c];
            $calc=calcularTrimestre($n,$config,$o['asignatura'],(bool)$o['usa_literal_especial'],$activas,!empty($o['aula_resultados_cualitativos']));
            $vals=[];foreach($camposRecalcular as $c)$vals[]=$calc[$c];
            $vals[]=(int)$r['id'];
            $refs=[];foreach($vals as $i=>&$v)$refs[$i]=&$v;
            unset($v);array_unshift($refs,str_repeat('d',count($camposRecalcular)-1).'si');
            call_user_func_array([$stRec,'bind_param'],$refs);
            sgaEjecutar($stRec,'recalcular calificaciones importadas');$recalculados++;
        }
        $stAll->close();$stRec->close();
        // Las calificaciones y su auditoria se confirman o revierten juntas.
        foreach($audits as $a) {
            sgaAuditoriaObligatoria($a['anterior'],'Calificaciones','calificacion_trimestre',$oid.'-'.$a['matricula_id'].'-'.$trim,
                'Importacion XLSX TRIM '.$trim.' fila '.$a['fila'].' para '.$a['nombre'].'.',
                $a['uid'],null,['origen'=>'xlsx','fila'=>$a['fila'],'campos_importados'=>$a['campos']],
                'exito',null,$grupoAud,'advertencia');
        }
        sgaAuditoriaObligatoria('IMPORT','Calificaciones','calificaciones_xlsx',$oid,
            'Importacion de notas desde Excel: '.$guardados.' estudiantes, T'.$trim.'.',null,null,
            ['trimestre'=>$trim,'registrados'=>$guardados,'omitidos'=>$omitidos,'recalculados'=>$recalculados,'columnas_activas'=>array_keys(array_filter($activas))],
            'exito',null,$grupoAud,'info');
        if (!$conexion->commit()) throw new RuntimeException('No se pudo confirmar la importacion de calificaciones.');
    } catch(Throwable $e) {
        $conexion->rollback();throw $e;
    }
    return ['guardados'=>$guardados,'omitidos'=>$omitidos,'recalculados'=>$recalculados,'activas'=>count(array_filter($activas))];
}

$previa=$_SESSION['imp_calificaciones_previa']??null;
if($previa && ((int)$previa['usuario_id']!==(int)$_SESSION['usuario_id'] ||
    (int)$previa['oferta_id']!==$oid || (int)$previa['trimestre']!==$trim ||
    time()-(int)$previa['fecha']>1800))$previa=null;

if($_SERVER['REQUEST_METHOD']==='POST') {
    $postToken=(string)($_POST['csrf']??'');
    if(!hash_equals($csrf,$postToken)){http_response_code(403);die('Token de seguridad incorrecto. Recarga la pagina.');}
    $accion=(string)($_POST['accion']??'');
    if($accion==='cancelar') {
        unset($_SESSION['imp_calificaciones_previa']);
        flash('info','Vista previa descartada. No se modificaron calificaciones.');
        redir($urlActual);
    }
    if($accion==='previsualizar') {
        try {
            if(!isset($_FILES['archivo']) || ($_FILES['archivo']['error']??UPLOAD_ERR_NO_FILE)!==UPLOAD_ERR_OK)
                throw new RuntimeException('Selecciona un archivo XLSX valido.');
            $file=$_FILES['archivo'];
            if(($file['size']??0)>5*1024*1024)throw new RuntimeException('El Excel supera 5 MB.');
            if(strtolower(pathinfo((string)$file['name'],PATHINFO_EXTENSION))!=='xlsx')
                throw new RuntimeException('Solo se permiten libros de Excel .xlsx.');
            if(!is_uploaded_file($file['tmp_name']))throw new RuntimeException('No se recibio un archivo cargado correctamente.');
            $datos=impXlsxLeer($file['tmp_name'],$trim);
            $contarNotas=0;$contarNombres=0;
            foreach($datos['filas'] as $f){$contarNotas+=count($f['notas']);if($f['nombre']!=='')$contarNombres++;}
            if(!$contarNotas || !$contarNombres)
                throw new RuntimeException('La hoja TRIM '.$trim.' no tiene estudiantes con nombres y calificaciones ingresadas. Parece una plantilla vacia.');
            $_SESSION['imp_calificaciones_previa']=[
                'usuario_id'=>(int)$_SESSION['usuario_id'],'oferta_id'=>$oid,'trimestre'=>$trim,
                'nombre_archivo'=>basename((string)$file['name']),'fecha'=>time(),'contenido'=>$datos,
            ];
            flash('success','Excel procesado. Revisa los nombres y selecciona las coincidencias pendientes antes de guardar.');
        } catch(Throwable $e) { flash('error','No se pudo analizar el Excel: '.$e->getMessage()); }
        redir($urlActual);
    }
    if($accion==='confirmar') {
        try {
            sgaAsegurarPeriodoEditable((int)$o['periodo_id']);
            if(!$previa)throw new RuntimeException('Vista previa caducada. Vuelve a cargar el Excel.');
            if(empty($_POST['aceptar']))throw new RuntimeException('Confirma que revisaste la asignatura, el trimestre y los estudiantes.');
            $elegidos=$_POST['destino']??[];
            if(!is_array($elegidos))throw new RuntimeException('Seleccion de estudiantes incorrecta.');
            $r=impCommitir($previa,$elegidos,$o,$porId);
            unset($_SESSION['imp_calificaciones_previa']);
            flash('success','Importacion realizada: '.$r['guardados'].' estudiantes, '.$r['activas'].' columnas de aportes utilizadas. '.$r['recalculados'].' registros del trimestre recalculados. '.$r['omitidos'].' filas omitidas.');
            redir('modulos/calificaciones/index.php?oferta_id='.$oid.'&trimestre='.$trim);
        } catch(Throwable $e) {flash('error','No se importaron calificaciones: '.$e->getMessage());redir($urlActual);}
    }
    flash('error','Accion no reconocida.');redir($urlActual);
}
$tituloPagina='Importar calificaciones desde Excel';
$subtituloPagina=$o['asignatura'].' - '.$o['nivel'].' '.$o['aula'].' '.$o['paralelo'].' - Trimestre '.$trim;
require __DIR__.'/../../partials/header.php';
$inicio=url($urlActual);
?>
<style>
.imp-guide{line-height:1.7}.imp-guide strong{color:var(--text,#123)}
.imp-results{overflow-x:auto;max-width:100%;margin-top:14px}
.imp-table{border-collapse:collapse;width:100%;min-width:940px;font-size:13px}
.imp-table th,.imp-table td{padding:10px 12px;border-bottom:1px solid #dde5ef;text-align:left;vertical-align:top}
.imp-table th{background:#eef5fd;color:#183c66}.imp-table tr:nth-child(even){background:#f7f9fc}
.imp-table select{max-width:325px;width:100%;padding:7px 10px;border:1px solid #b4c6d9;border-radius:7px;color:#123;background:#fff}
.imp-state{display:inline-block;border-radius:16px;font-size:12px;padding:3px 8px;background:#e6ecf3;color:#344e69}
.imp-state.ok{background:#e0f3e8;color:#14683d}.imp-state.warn{background:#fff1d6;color:#79510a}
.imp-file{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin:12px 0}.imp-file input{max-width:100%}
.imp-small{font-size:12px;color:#53657d}.imp-notes{display:flex;flex-wrap:wrap;gap:5px;margin-top:6px}.imp-notes span{border-radius:4px;background:#e4effb;color:#1c4677;padding:3px 5px}
.imp-confirm{padding:13px;border:1px solid #ced9e6;border-radius:8px;margin:14px 0}
</style>
<div class="toolbar"><div class="actions">
<a class="btn btn-secondary" href="<?=e(url('modulos/calificaciones/index.php?oferta_id='.$oid.'&trimestre='.$trim))?>">Volver a calificaciones</a>
<?php for($t=1;$t<=3;$t++):?><a class="btn <?=$t===$trim?'btn-primary':'btn-secondary'?>" href="<?=e(url('modulos/calificaciones/importar.php?oferta_id='.$oid.'&trimestre='.$t))?>">T<?=$t?></a><?php endfor;?>
</div></div>
<div class="card imp-guide">
<h3>Importar notas del <?=$trim?>.&#176; trimestre</h3>
<p>Selecciona el libro XLSX de la institucion. El sistema lee <strong>unicamente TRIM <?=$trim?></strong> y solo importa notas originales de deberes, tareas, lecciones, grupo, refuerzos, aporte disciplinar y producto final. Nunca importa formulas de promedios ni notas finales.</p>
<p>Las columnas de AP completamente vacias se bloquean para este trimestre. Las columnas de AP que tienen alguna nota permanecen activas y los vacios individuales de estudiantes importados se consideran 0. Los refuerzos y sumativas en blanco no modifican notas anteriores. La identificacion ignora acentos, guiones, orden de nombres y apellidos, y espacios repetidos.</p>
<form method="post" enctype="multipart/form-data" action="<?=e($inicio)?>">
<input type="hidden" name="csrf" value="<?=e($csrf)?>"><input type="hidden" name="accion" value="previsualizar">
<input type="hidden" name="oferta_id" value="<?=$oid?>"><input type="hidden" name="trimestre" value="<?=$trim?>">
<div class="imp-file"><input type="file" name="archivo" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" required><button class="btn btn-primary" type="submit">Analizar Excel y buscar coincidencias</button></div>
</form>
<p class="imp-small">Hasta 5 MB. Maximo 140 estudiantes por hoja. Se revisan los datos antes de modificar la base de datos.</p>
</div>
<?php if($previa):
    $filas=$previa['contenido']['filas'];$etiquetas=impEtiquetas();$apCampos=impCamposAportes();
    $coincidencias=[];$autos=0;$revisar=0;$faltantes=0;$ocupados=[];
    foreach($filas as $fila){
        $f=(int)$fila['fila'];$coincidencias[$f]=impSugerirNombre($fila['nombre'],$alumnos);
        if($coincidencias[$f]['id']){$autos++;$ocupados[$coincidencias[$f]['id']][]= $f;}
        elseif($coincidencias[$f]['estado']==='sin_nombre'||$coincidencias[$f]['estado']==='no_encontrado')$faltantes++;
        else $revisar++;
    }
    foreach($ocupados as $id=>$duplicadas)if(count($duplicadas)>1){
        foreach($duplicadas as $filaNum){$coincidencias[$filaNum]['id']=0;$coincidencias[$filaNum]['estado']='revisar';}
        $autos-=count($duplicadas);$revisar+=count($duplicadas);
    }
    $usadas=array_fill_keys(array_values($apCampos),false);
    foreach($filas as $fila)foreach(array_keys($usadas) as $c)if(array_key_exists($c,$fila['notas']))$usadas[$c]=true;
    $usadasNombre=array_intersect_key($etiquetas,array_filter($usadas));
    $inactivasNombre=array_intersect_key($etiquetas,array_filter($usadas,static fn($x)=>!$x));
?>
<div class="card">
<h3>Vista previa - <?=e($previa['nombre_archivo'])?></h3>
<p><strong>Asignatura:</strong> <?=e($o['asignatura'])?> &nbsp; <strong>Trimestre:</strong> <?=$trim?> &nbsp; <strong>Alumnos del curso:</strong> <?=count($alumnos)?></p>
<p><strong>Coincidencias automaticas:</strong> <?=$autos?> &nbsp; <strong>Por revisar:</strong> <?=$revisar?> &nbsp; <strong>Sin coincidencia:</strong> <?=$faltantes?> &nbsp; <strong>Filas sin notas omitidas:</strong> <?=(int)($previa['contenido']['filas_sin_notas']??0)?></p>
<p><strong>AP utilizados:</strong> <?=e($usadasNombre?implode(', ',$usadasNombre):'Ninguno')?>.</p>
<p class="imp-small"><strong>AP no utilizados:</strong> <?=e($inactivasNombre?implode(', ',$inactivasNombre):'Ninguno')?>. Esta configuracion se aplicara solo al trimestre <?=$trim?> de esta asignatura.</p>
<?php if($previa['contenido']['formulas_ignoradas']):?><p class="imp-small">Se ignoraron <?=$previa['contenido']['formulas_ignoradas']?> celdas con formulas en columnas de entrada.</p><?php endif;?>
<form method="post" action="<?=e($inicio)?>">
<input type="hidden" name="csrf" value="<?=e($csrf)?>"><input type="hidden" name="accion" value="confirmar">
<input type="hidden" name="oferta_id" value="<?=$oid?>"><input type="hidden" name="trimestre" value="<?=$trim?>">
<div class="imp-results"><table class="imp-table"><thead><tr><th>Fila</th><th>Nombre en el Excel</th><th>Coincidencia</th><th>Vincular con matricula del curso</th><th>Notas originales detectadas</th></tr></thead><tbody>
<?php foreach($filas as $fila):$f=(int)$fila['fila'];$sug=$coincidencias[$f];$valor=(int)$sug['id'];
    $estado=$sug['estado'];$status=($estado==='exacta'?'Exacta':($estado==='alta'?'Muy alta':($estado==='revisar'?'Revisar':'Sin coincidencia')));
    if(!$fila['nombre'])$status='Sin nombre';
    $opcionesOrden=[];foreach($sug['candidatos'] as $c)$opcionesOrden[$c['id']]=$c['score'];
    foreach($alumnos as $al)if(!isset($opcionesOrden[(int)$al['id']]))$opcionesOrden[(int)$al['id']]=null;
?>
<tr>
<td><?=$f?></td><td><strong><?=e($fila['nombre']?:'(sin nombre)')?></strong></td>
<td><span class="imp-state <?=$valor?'ok':($estado==='revisar'?'warn':'')?>"><?=e($status)?> <?=$sug['score']>0?' ('.fmt($sug['score'],1).'%)':''?></span></td>
<td><select name="destino[<?=$f?>]" <?=!$fila['nombre']||!$fila['notas']?'disabled':''?>>
<option value="0">-- No importar esta fila --</option>
<?php foreach($opcionesOrden as $mid=>$score):$al=$porId[$mid]??null;if(!$al)continue;?><option value="<?=$mid?>" <?=$valor===$mid?'selected':''?>><?=e($al['apellidos'].' '.$al['nombres'])?><?=$score!==null?' ('.fmt($score,1).'%)':''?></option><?php endforeach;?>
</select></td>
<td><div class="imp-notes">
<?php foreach($fila['notas'] as $campo=>$n):?><span title="<?=e($campo)?>"><?=e($etiquetas[$campo]??$campo)?>: <?=fmt($n)?></span><?php endforeach;?>
<?php if(!$fila['notas']):?><span>Sin notas para importar</span><?php endif;?>
</div></td>
</tr>
<?php endforeach;?></tbody></table></div>
<div class="imp-confirm"><label><input type="checkbox" name="aceptar" value="1" required> He verificado la asignatura, el trimestre, las coincidencias y los AP que quedaran activos. Comprendo que solo se actualizara este trimestre y que los estudiantes sin vincular se omitiran.</label></div>
<div class="actions"><button type="submit" class="btn btn-primary">Confirmar importacion y recalcular <?=$trim?>.&#176; trimestre</button></div>
</form>
<form method="post" action="<?=e($inicio)?>" style="margin-top:12px"><input type="hidden" name="csrf" value="<?=e($csrf)?>"><input type="hidden" name="oferta_id" value="<?=$oid?>"><input type="hidden" name="trimestre" value="<?=$trim?>"><input type="hidden" name="accion" value="cancelar"><button class="btn btn-secondary" type="submit">Descartar vista previa</button></form>
</div>
<?php endif;?>
<?php require __DIR__.'/../../partials/footer.php'; ?>
