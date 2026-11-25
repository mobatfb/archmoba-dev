<?php
/** Pruebas autocontenidas de la politica de escritura, con roles y jornadas simulados. */
if(PHP_SAPI!=='cli'){http_response_code(403);exit;}
require_once __DIR__.'/../lib/sga_calificacion_parametros.php';
$rol='docente';$docente=true;$_SESSION=['usuario_id'=>7];
// Se simulan las funciones oficiales de autenticacion y alcance por oferta.
$ofertasPermitidas=[26];
function rolOperativoActual(){return $GLOBALS['rol'];}
function esDocenteOperativo($pid){return $GLOBALS['docente'] && $pid===1 && rolOperativoActual()==='docente';}
function esSuperadmin(){return rolOperativoActual()==='superadmin';}
function esSubadmin(){return rolOperativoActual()==='subadmin';}
function puedeAccederOfertaSubadmin($oid){return esSubadmin() && in_array($oid,$GLOBALS['ofertasPermitidas'],true);}
function verificar($ok,$msg){if(!$ok){fwrite(STDERR,"FALLO: $msg\n");exit(1);}echo "OK: $msg\n";}
$o=['id'=>26,'evaluacion_aula'=>1,'aula_evaluacion_parametros'=>1,'aula_periodo_activo'=>1,'activo'=>1,'periodo_estado'=>'activo','periodo_id'=>1,'docente_id'=>7];
verificar(sgaParametrosPuedeCalificar($o)&&!sgaParametrosSoloVista($o),'Docente responsable califica');
verificar(!sgaParametrosPuedeConfigurar($o),'Docente no modifica configuracion');
foreach(['docente_id'=>9,'periodo_id'=>2] as $k=>$v){$x=$o;$x[$k]=$v;verificar(!sgaParametrosPuedeCalificar($x),'Docente bloqueado: '.$k);}
$docente=false;verificar(!sgaParametrosPuedeCalificar($o),'Sin rol docente en el periodo no califica');$docente=true;
$rol='superadmin';$_SESSION['usuario_id']=99;$otra=$o;$otra['id']=27;$otra['periodo_id']=2;
verificar(sgaParametrosPuedeCalificar($o)&&sgaParametrosPuedeConfigurar($o),'Administrador global califica y configura sin ser docente asignado');
verificar(sgaParametrosPuedeCalificar($otra)&&sgaParametrosPuedeConfigurar($otra),'Administrador global accede a otras jornadas y periodos abiertos');
$rol='subadmin';
verificar(sgaParametrosPuedeCalificar($o)&&sgaParametrosPuedeConfigurar($o),'Subadministrador califica y configura oferta autorizada');
verificar(!sgaParametrosPuedeCalificar($otra)&&!sgaParametrosPuedeConfigurar($otra)&&sgaParametrosSoloVista($otra),'Subadministrador no califica ni configura oferta ajena');
$ofertasPermitidas=[];verificar(!sgaParametrosPuedeCalificar($o),'Sin jornada asignada no califica');$ofertasPermitidas=[26];
// La alternancia a docente no debe conservar permisos administrativos.
$rol='docente';verificar(!sgaParametrosPuedeCalificar($o),'Subadministrador en rol docente sin asignacion no califica');
$_SESSION['usuario_id']=7;verificar(sgaParametrosPuedeCalificar($o),'Subadministrador en rol docente con asignacion califica');
foreach(['representante','estudiante',''] as $rol){verificar(!sgaParametrosPuedeCalificar($o)&&!sgaParametrosPuedeConfigurar($o),'Sin escritura en rol '.($rol?:'invalido'));}
foreach(['docente','superadmin','subadmin'] as $rol){
    foreach(['id'=>0,'periodo_id'=>0,'evaluacion_aula'=>0,'aula_evaluacion_parametros'=>0,'aula_periodo_activo'=>0,'activo'=>0,'periodo_estado'=>'cerrado'] as $k=>$v){
        $x=$o;$x[$k]=$v;
        verificar(!sgaParametrosPuedeCalificar($x)&&!sgaParametrosPuedeConfigurar($x)&&sgaParametrosSoloVista($x),$rol.' bloqueo: '.$k);
    }
}
$rol='superadmin';$_SESSION=[];verificar(!sgaParametrosPuedeCalificar($o)&&!sgaParametrosPuedeConfigurar($o),'Sin sesion no escribe');
verificar(sgaParametrosOpciones()===['A+','A-','B+','B-','C+','C-','D+','D-','E+','E-'],'Diez literales originales');
verificar(count(sgaParametrosModeloInicial())===9,'Nueve ambitos del modelo inicial');
