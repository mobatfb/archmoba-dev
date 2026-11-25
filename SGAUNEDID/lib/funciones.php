<?php
require_once __DIR__ . '/auth.php';
require_once __DIR__ . '/auditoria.php';
require_once __DIR__ . '/academico_integridad.php';
require_once __DIR__ . '/sga_resultados_cualitativos.php';
require_once __DIR__ . '/sga_calificacion_parametros.php';

function e($v): string { return htmlspecialchars((string)$v, ENT_QUOTES, 'UTF-8'); }
function flash(string $tipo,string $mensaje): void { $_SESSION['flash']=['tipo'=>$tipo,'mensaje'=>$mensaje]; }
function tomarFlash(): ?array { $f=$_SESSION['flash']??null; unset($_SESSION['flash']); return $f; }
function redir(string $ruta): never { header('Location: '.url($ruta)); exit; }
function notaEntrada($valor): ?float { if($valor===null||$valor==='')return null; $v=str_replace(',','.',trim((string)$valor)); if(!is_numeric($v))return null; $n=(float)$v; if($n<0||$n>10)throw new InvalidArgumentException('Las notas deben estar entre 0 y 10.'); return round($n,2); }
function truncar2(float $v): float { return floor(($v+1e-9)*100)/100; }
function fmt($v,int $d=2): string { return number_format((float)$v,$d,'.',''); }
function valorInput($v): string { return ($v===null||$v==='')?'':fmt($v); }
function promedioNotasIngresadas(array $notas): float { $v=array_values(array_filter($notas,fn($n)=>$n!==null)); return !$v?0.0:round(array_sum($v)/count($v),2); }
/** El refuerzo de aportes solo mejora promedios inferiores a 7; la mejora se topa en 7. */
function aplicarRefuerzo(float $p, ?float $r): float {
    $base = round(max(0.0, min(10.0, $p)), 2);
    if ($base >= 7.0 || $r === null || $r <= $base) return $base;
    return round(max($base, min(7.0, ($base + $r) / 2)), 2);
}
/** Fórmula AF del registro 2026: nunca reduce la nota y limita la mejora a 7 / 9. */
function promedioDisciplinar(?float $nota, ?float $refuerzo): float {
    $base = (float)($nota ?? 0);
    if ($base <= 0) return 0.0;
    if ($refuerzo === null || $refuerzo <= 0) return round($base, 2);
    $limite = ($base >= 7 && $base < 9) ? 9.0 : 7.0;
    return round(max($base, min($limite, round(($base + $refuerzo) / 2, 2))), 2);
}
/** AH: si existe al menos una nota positiva, siempre se divide entre dos. */
function promedioSumativaNueva(float $disciplina, ?float $producto): float {
    $p = (float)($producto ?? 0);
    return ($disciplina > 0 || $p > 0) ? round(($disciplina + $p) / 2, 2) : 0.0;
}
/** Compatibilidad: no atribuye la antigua nota de proyecto a un componente distinto. */
function esSumativaHistorica(array $notas): bool {
    return ($notas['nota_disciplinar'] ?? null) === null
        && ($notas['trabajo_refuerzo_disciplinar'] ?? null) === null
        && ($notas['nota_producto_final'] ?? null) === null
        && (float)($notas['proyecto_interdisciplinar'] ?? 0) > 0;
}
/** Se conserva únicamente para calcular el histórico cuando aún no hay notas nuevas. */
function promedioProyectoHistorico(?float $p, ?float $r, ?float $m): float {
    if($p===null||$p<=0)return 0.0;
    if(($r??0)>0&&($m??0)>0){$n=round(($p+$r+$m)/3,2);return $n>$p?$n:round($p,2);}
    if(($m??0)>0){$n=round(($p+$m)/2,2);return $n>$p?$n:round($p,2);}
    return round($p,2);
}
/** Conversión del promedio sobre 10 a la escala cualitativa institucional de cuatro niveles. */
function literalEspecial(float $n): string {
    $n = round(max(0.0,min(10.0,$n)),2);
    if ($n >= 9.0) return 'A+';
    if ($n >= 8.0) return 'A-';
    if ($n >= 7.0) return 'B+';
    return 'B-';
}
/** Solo cambia la presentación; para cálculos, aprobaciones y refuerzos se conserva la nota /10. */
function notaFinalVisible(float $nota, bool $especial, bool $registrada = true): string {
    if (!$registrada) return '—';
    if (!$especial) return fmt($nota);
    return literalEspecial($nota);
}
function cualitativo(float $n,string $materia='',bool $especial=false): string { if($especial)return literalEspecial($n); if($n<=0)return ''; if($n>=9)return 'D.A.R.'; if($n>=7)return 'A.A.R.'; if($n>=4)return 'P.A.A.R.'; return 'N.A.R.'; }

function obtenerConfiguracion(int $periodoId): array {
    global $conexion; $c=['ponderacion_aportes'=>.70,'ponderacion_sumativa'=>.30,'nota_aprobacion'=>7.00,'nota_min_supletorio'=>4.00];
    $stmt=$conexion->prepare('SELECT ponderacion_aportes,ponderacion_sumativa,nota_aprobacion,nota_min_supletorio FROM configuracion_evaluacion WHERE periodo_id=? LIMIT 1');$stmt->bind_param('i',$periodoId);$stmt->execute();if($r=$stmt->get_result()->fetch_assoc()){$c=array_map('floatval',$r);} $stmt->close();return $c;
}
function obtenerEstadoAportes(int $ofertaId,int $trimestre): array {
    global $conexion; $campos=['deber_ap1','deber_ap2','deber_ap3','tarea_ap1','tarea_ap2','tarea_ap3','leccion_ap1','leccion_ap2','leccion_ap3','grupo_ap1','grupo_ap2','grupo_ap3'];$e=array_fill_keys($campos,true);
    $stmt=$conexion->prepare('SELECT campo,activo FROM configuracion_aportes WHERE oferta_id=? AND trimestre=?');$stmt->bind_param('ii',$ofertaId,$trimestre);$stmt->execute();$res=$stmt->get_result();while($r=$res->fetch_assoc())if(array_key_exists($r['campo'],$e))$e[$r['campo']]=(bool)$r['activo'];$stmt->close();return $e;
}
function aporteActivo(array $e,string $c): bool { return !array_key_exists($c,$e)||(bool)$e[$c]; }
function calcularTrimestre(array $n,array $config,string $materia='',bool $especial=false,array $estado=[],bool $resultadosCualitativos=false): array {
    $notaAp=function(string $c)use($n,$estado):?float{if(!aporteActivo($estado,$c))return null;return ($n[$c]??null)===null?0.0:(float)$n[$c];};
    $naturaleza=function(array $notas,?float $refuerzo):array{
        $activos=count(array_filter($notas,static fn($v)=>$v!==null));
        if(!$activos)return ['incluida'=>false,'promedio'=>0.0,'aporte'=>0.0];
        $promedio=promedioNotasIngresadas($notas);
        return ['incluida'=>true,'promedio'=>$promedio,'aporte'=>aplicarRefuerzo($promedio,$refuerzo)];
    };
    $d=$naturaleza([$notaAp('deber_ap1'),$notaAp('deber_ap2'),$notaAp('deber_ap3')],$n['deber_refuerzo']??null);
    $t=$naturaleza([$notaAp('tarea_ap1'),$notaAp('tarea_ap2'),$notaAp('tarea_ap3')],$n['tarea_refuerzo']??null);
    $l=$naturaleza([$notaAp('leccion_ap1'),$notaAp('leccion_ap2'),$notaAp('leccion_ap3')],$n['leccion_refuerzo']??null);
    $g=$naturaleza([$notaAp('grupo_ap1'),$notaAp('grupo_ap2'),$notaAp('grupo_ap3')],$n['grupo_refuerzo']??null);
    $dp=$d['promedio'];$da=$d['aporte'];$tp=$t['promedio'];$ta=$t['aporte'];
    $lp=$l['promedio'];$la=$l['aporte'];$gp=$g['promedio'];$ga=$g['aporte'];
    // Fully disabled categories did not occur in the trimester; they must NOT gift 10 points.
    $aplicadas=array_values(array_filter([$d,$t,$l,$g],static fn($v)=>$v['incluida']));
    $pa=$aplicadas?array_sum(array_column($aplicadas,'aporte'))/count($aplicadas):0.0;
    $pondA=$pa>0?truncar2($pa*(float)$config['ponderacion_aportes']):0.0;
    $disciplina=promedioDisciplinar($n['nota_disciplinar'] ?? null,$n['trabajo_refuerzo_disciplinar'] ?? null);
    $historico=esSumativaHistorica($n);
    if($historico){
        // Se mantienen los dos resultados SUMATIVA existentes, sin adjudicar notas antiguas.
        $pp=(float)($n['promedio_proyecto'] ?? promedioProyectoHistorico($n['proyecto_interdisciplinar'] ?? null,$n['proyecto_refuerzo'] ?? null,$n['actividad_mejora'] ?? null));
        $pondS=(float)($n['ponderado_sumativa'] ?? round($pp*(float)$config['ponderacion_sumativa'],2));
    }else{
        $pp=promedioSumativaNueva($disciplina,$n['nota_producto_final'] ?? null);
        $pondS=$pp>0?round($pp*(float)$config['ponderacion_sumativa'],2):0.0;
    }
    $nf=round($pondA+$pondS,2);
    return ['deber_promedio'=>$dp,'deber_promedio_aporte'=>$da,'tarea_promedio'=>$tp,'tarea_promedio_aporte'=>$ta,'leccion_promedio'=>$lp,'leccion_promedio_aporte'=>$la,'grupo_promedio'=>$gp,'grupo_promedio_aporte'=>$ga,'promedio_aportes'=>round($pa,3),'ponderado_aportes'=>$pondA,'promedio_disciplinar'=>$disciplina,'promedio_proyecto'=>$pp,'promedio_evaluacion_sumativa'=>$pp,'ponderado_sumativa'=>$pondS,'nota_final'=>$nf,'cualitativo'=>$resultadosCualitativos?sgaLetraResultadoCualitativo($nf):cualitativo($nf,$materia,$especial),'sumativa_historica'=>$historico];
}
function calcularFinalAnual(?float $t1,?float $t2,?float $t3,?float $sup,array $config): array {
    return sgaResultadoAnual($t1,$t2,$t3,$sup,$config);
}

function ofertaDetalle(int $ofertaId): ?array {
    global $conexion; $sql="SELECT o.*,ap.periodo_id,ap.activo aula_periodo_activo,ap.evaluacion_cualitativa_parametros aula_evaluacion_parametros,p.nombre periodo,p.estado periodo_estado,p.fecha_inicio,p.fecha_fin,a.id aula_id,a.nivel,a.nombre aula,a.paralelo,a.resultados_cualitativos aula_resultados_cualitativos,CASE WHEN o.evaluacion_aula=1 THEN 'Evaluación cualitativa del aula' ELSE s.nombre END asignatura,s.codigo asignatura_codigo,s.usa_literal_especial,CASE WHEN o.evaluacion_aula=1 OR o.evaluacion_parametros_historica=1 THEN 0 ELSE s.solo_visor_comportamiento END solo_visor_comportamiento,(o.evaluacion_aula=1 OR o.evaluacion_parametros_historica=1) evaluacion_cualitativa_parametros,u.nombres docente_nombres,u.apellidos docente_apellidos FROM ofertas_academicas o JOIN aulas_periodo ap ON ap.id=o.aula_periodo_id JOIN periodos_academicos p ON p.id=ap.periodo_id JOIN aulas a ON a.id=ap.aula_id JOIN asignaturas s ON s.id=o.asignatura_id JOIN usuarios u ON u.id=o.docente_id WHERE o.id=? LIMIT 1";$stmt=$conexion->prepare($sql);$stmt->bind_param('i',$ofertaId);$stmt->execute();$r=$stmt->get_result()->fetch_assoc()?:null;$stmt->close();return $r;
}

/** Una asignatura de comportamiento solo admite su valoracion cualitativa trimestral.
 * Bloquea rutas antiguas de notas numericas, importaciones y supletorios. */
function impedirNotasEnVisorComportamiento(int $ofertaId): void {
    $o=ofertaDetalle($ofertaId);
    if ($o && (!empty($o['solo_visor_comportamiento']) || !empty($o['evaluacion_cualitativa_parametros']) || !empty($o['aula_evaluacion_parametros']))) {
        http_response_code(403);
        exit('Esta asignatura utiliza un visor cualitativo propio. Accede desde Calificaciones.');
    }
}

function promedioFinalOfertaMatricula(int $ofertaId,int $matriculaId): array {
    global $conexion; $of=ofertaDetalle($ofertaId); if(!$of)return ['promedio_final'=>null,'promedio_tres'=>null,'observacion'=>'EN CURSO','trimestres_completos'=>false];$config=obtenerConfiguracion((int)$of['periodo_id']);
    $stmt=$conexion->prepare('SELECT c1.nota_final t1,c2.nota_final t2,c3.nota_final t3,nf.examen_supletorio FROM matriculas m LEFT JOIN calificaciones_trimestre c1 ON c1.matricula_id=m.id AND c1.oferta_id=? AND c1.trimestre=1 LEFT JOIN calificaciones_trimestre c2 ON c2.matricula_id=m.id AND c2.oferta_id=? AND c2.trimestre=2 LEFT JOIN calificaciones_trimestre c3 ON c3.matricula_id=m.id AND c3.oferta_id=? AND c3.trimestre=3 LEFT JOIN notas_finales nf ON nf.matricula_id=m.id AND nf.oferta_id=? WHERE m.id=? LIMIT 1');$stmt->bind_param('iiiii',$ofertaId,$ofertaId,$ofertaId,$ofertaId,$matriculaId);$stmt->execute();$r=$stmt->get_result()->fetch_assoc()?:[];$stmt->close();
    $sup = ($r['examen_supletorio'] ?? null) === null ? null : (float)$r['examen_supletorio'];
    $resultado = calcularFinalAnual(isset($r['t1'])?(float)$r['t1']:null,isset($r['t2'])?(float)$r['t2']:null,isset($r['t3'])?(float)$r['t3']:null,$sup,$config);
    // Metadatos solo para presentar el estado del supletorio en el consolidado.
    $resultado['examen_supletorio'] = $sup;
    $resultado['trimestres_completos'] = ($r['t1'] ?? null) !== null
        && ($r['t2'] ?? null) !== null && ($r['t3'] ?? null) !== null;
    return $resultado;
}

/**
 * Devuelve el siguiente numero de lista disponible entre matriculas activas.
 */
function siguienteNumeroLista(int $aulaPeriodoId): int {
    global $conexion;
    // Bloquea el aula para asignaciones concurrentes durante la transaccion.
    $lock=$conexion->prepare('SELECT id FROM aulas_periodo WHERE id=? FOR UPDATE');
    $lock->bind_param('i',$aulaPeriodoId);sgaEjecutar($lock,'reservar el numero de lista');$lock->close();
    $stmt=$conexion->prepare("SELECT COALESCE(MAX(numero_lista),0)+1 n FROM matriculas WHERE aula_periodo_id=? AND estado='activo'");
    $stmt->bind_param('i',$aulaPeriodoId);
    $stmt->execute();
    $n=(int)($stmt->get_result()->fetch_assoc()['n']??1);
    $stmt->close();
    return max(1,$n);
}

/**
 * Matricula o reactiva un estudiante en un aula del periodo.
 * - Si ya esta activo en esta aula: no duplica.
 * - Si esta retirado/finalizado en esta aula: reactiva la misma matricula.
 * - Si esta activo en otra aula del mismo periodo: devuelve conflicto.
 */
function matricularUsuarioEnAula(int $usuarioId,int $aulaPeriodoId,int $periodoId): array {
    // El control se aplica también cuando se matricula mediante CSV.
    if(esSubadmin() && (!puedeAccederAulaPeriodo($aulaPeriodoId) || !puedeGestionarUsuarioJornada($usuarioId,$periodoId)))
        return ['estado'=>'conflicto','mensaje'=>'El usuario o aula no está disponible para esta operación.'];
    global $conexion;
    sgaAsegurarPeriodoEditable($periodoId);

    $stmt=$conexion->prepare('SELECT id,cedula,apellidos,nombres,activo FROM usuarios WHERE id=? LIMIT 1');
    $stmt->bind_param('i',$usuarioId);$stmt->execute();$usuario=$stmt->get_result()->fetch_assoc();$stmt->close();
    if(!$usuario || (int)$usuario['activo']!==1) return ['estado'=>'error','mensaje'=>'Usuario inexistente o inactivo.'];

    // Evitar asignar el rol estudiante por matrícula a administradores o docentes.
    $stmt=$conexion->prepare("SELECT r.codigo FROM usuario_roles ur JOIN roles r ON r.id=ur.rol_id
       WHERE ur.usuario_id=? AND r.codigo IN ('superadmin','subadmin','docente')
         AND (ur.periodo_id IS NULL OR ur.periodo_id=?) LIMIT 1");
    $stmt->bind_param('ii',$usuarioId,$periodoId);$stmt->execute();$rolIncompatible=$stmt->get_result()->fetch_assoc();$stmt->close();
    if ($rolIncompatible) return ['estado'=>'conflicto','mensaje'=>'El usuario tiene rol administrativo o docente en este período. Cambia su rol desde el módulo Roles.'];

    $stmt=$conexion->prepare("SELECT m.id,m.aula_periodo_id,m.estado,a.nivel,a.nombre aula,a.paralelo
      FROM matriculas m
      JOIN aulas_periodo ap ON ap.id=m.aula_periodo_id
      JOIN aulas a ON a.id=ap.aula_id
      WHERE m.estudiante_id=? AND ap.periodo_id=? AND m.estado='activo'
      LIMIT 1 FOR UPDATE");
    $stmt->bind_param('ii',$usuarioId,$periodoId);$stmt->execute();$activa=$stmt->get_result()->fetch_assoc();$stmt->close();
    if($activa){
        if((int)$activa['aula_periodo_id']===$aulaPeriodoId){
            return ['estado'=>'existente','mensaje'=>'Ya se encuentra matriculado en este paralelo.','matricula_id'=>(int)$activa['id']];
        }
        return ['estado'=>'conflicto','mensaje'=>'Ya tiene matricula activa en '.$activa['nivel'].' · '.$activa['aula'].' '.$activa['paralelo'].'.'];
    }

    $stmt=$conexion->prepare('SELECT id,estado FROM matriculas WHERE aula_periodo_id=? AND estudiante_id=? LIMIT 1 FOR UPDATE');
    $stmt->bind_param('ii',$aulaPeriodoId,$usuarioId);$stmt->execute();$previa=$stmt->get_result()->fetch_assoc();$stmt->close();
    $numero=siguienteNumeroLista($aulaPeriodoId);

    if($previa){
        $mid=(int)$previa['id'];
        $stmt=$conexion->prepare("UPDATE matriculas SET estado='activo',numero_lista=? WHERE id=?");
        $stmt->bind_param('ii',$numero,$mid);$stmt->execute();$stmt->close();
        asignarRolPeriodo($usuarioId,'estudiante',$periodoId);
        return ['estado'=>'reactivado','mensaje'=>'Matricula reactivada.','matricula_id'=>$mid];
    }

    $stmt=$conexion->prepare('INSERT INTO matriculas(aula_periodo_id,estudiante_id,numero_lista,estado) VALUES(?,?,?,\'activo\')');
    $stmt->bind_param('iii',$aulaPeriodoId,$usuarioId,$numero);$stmt->execute();$mid=(int)$conexion->insert_id;$stmt->close();
    asignarRolPeriodo($usuarioId,'estudiante',$periodoId);
    return ['estado'=>'creado','mensaje'=>'Matricula creada.','matricula_id'=>$mid];
}

function usuarioPorCedula(string $cedula): ?array {
    global $conexion;
    $cedula=trim($cedula);
    if($cedula==='') return null;
    $stmt=$conexion->prepare('SELECT id,cedula,apellidos,nombres,activo FROM usuarios WHERE cedula=? LIMIT 1');
    $stmt->bind_param('s',$cedula);$stmt->execute();$r=$stmt->get_result()->fetch_assoc()?:null;$stmt->close();
    return $r;
}
