<?php
require_once __DIR__.'/../../lib/funciones.php';
exigirLogin();
if($_SERVER['REQUEST_METHOD']!=='POST'){http_response_code(405);die('Método no permitido.');}
$oid=(int)($_POST['oferta_id']??0);
if(!$oid||!puedeGestionarOferta($oid)){http_response_code(403);die('Operación no permitida.');}
impedirNotasEnVisorComportamiento($oid);
$o=ofertaDetalle($oid);
if(!$o || !empty($o['solo_visor_comportamiento'])){http_response_code(403);die('No corresponde supletorio a una asignatura de comportamiento.');}
$apid=(int)$o['aula_periodo_id'];
$datos=$_POST['supletorio']??[];
$grupoAud=auditoriaGrupo();$n=0;
try{
  sgaAsegurarPeriodoEditable((int)$o['periodo_id']);
  if(!is_array($datos))throw new DomainException('Formulario de supletorios incorrecto.');
  // Cargar en una consulta las notas de los 3 trimestres y las matrículas elegibles.
  $c=$conexion->prepare("SELECT m.id mid,m.estudiante_id,u.apellidos,u.nombres,
       c1.nota_final t1,c2.nota_final t2,c3.nota_final t3,nf.examen_supletorio anterior
       FROM matriculas m JOIN usuarios u ON u.id=m.estudiante_id
       LEFT JOIN calificaciones_trimestre c1 ON c1.matricula_id=m.id AND c1.oferta_id=? AND c1.trimestre=1
       LEFT JOIN calificaciones_trimestre c2 ON c2.matricula_id=m.id AND c2.oferta_id=? AND c2.trimestre=2
       LEFT JOIN calificaciones_trimestre c3 ON c3.matricula_id=m.id AND c3.oferta_id=? AND c3.trimestre=3
       LEFT JOIN notas_finales nf ON nf.matricula_id=m.id AND nf.oferta_id=?
       WHERE m.aula_periodo_id=? AND m.estado='activo'");
  $c->bind_param('iiiii',$oid,$oid,$oid,$oid,$apid);sgaEjecutar($c,'consultar los trimestres');
  $matriculas=[];foreach($c->get_result()->fetch_all(MYSQLI_ASSOC) as $r)$matriculas[(int)$r['mid']]=$r;$c->close();
  $config=obtenerConfiguracion((int)$o['periodo_id']);
  $pendientes=[];
  foreach($datos as $id=>$valor){
      if(!ctype_digit((string)$id)||!isset($matriculas[(int)$id]))throw new DomainException('Se recibió una matrícula que no pertenece al curso.');
      if(!is_scalar($valor))throw new DomainException('La calificación recibida no es válida.');
      $nota=notaEntrada($valor);
      if($nota===null)continue; // No convertir celdas vacias en 0 ni borrar registros.
      $r=$matriculas[(int)$id];
      sgaValidarSupletorio($r['t1']===null?null:(float)$r['t1'],$r['t2']===null?null:(float)$r['t2'],$r['t3']===null?null:(float)$r['t3'],$nota,$config);
      $pendientes[]=['id'=>(int)$id,'nota'=>$nota,'estudiante'=>$r];
  }
  if(!$pendientes)throw new DomainException('No hay notas de supletorio nuevas para guardar.');
  $conexion->begin_transaction();
  $save=$conexion->prepare('INSERT INTO notas_finales(oferta_id,matricula_id,examen_supletorio) VALUES(?,?,?) ON DUPLICATE KEY UPDATE examen_supletorio=VALUES(examen_supletorio)');
  foreach($pendientes as $p){
      $mid=$p['id'];$nota=$p['nota'];$r=$p['estudiante'];
      $save->bind_param('iid',$oid,$mid,$nota);sgaEjecutar($save,'guardar la nota de supletorio');$n++;
      sgaAuditoriaObligatoria($r['anterior']===null?'CREATE':'UPDATE','Calificaciones','nota_supletorio',$oid.'-'.$mid,
          'Supletorio de '.$r['apellidos'].' '.$r['nombres'].' guardado en '.$o['asignatura'].'.',(int)$r['estudiante_id'],
          ['examen_supletorio'=>$r['anterior']],['examen_supletorio'=>$nota],'exito',null,$grupoAud,'advertencia');
  }
  $save->close();if(!$conexion->commit())throw new RuntimeException('No se pudo confirmar el supletorio.');
  flash('success','Se guardaron '.$n.' notas de supletorio elegibles.');
}catch(Throwable $e){
  try{$conexion->rollback();}catch(Throwable $ignored){}
  registrarAuditoria('UPDATE','Calificaciones','notas_supletorio',$oid,'Fallo al guardar supletorios: '.$e->getMessage(),null,null,null,'fallo',null,$grupoAud,'critica');
  flash('error','No se pudieron guardar los supletorios: '.$e->getMessage());
}
redir('modulos/calificaciones/finales.php?oferta_id='.$oid);
