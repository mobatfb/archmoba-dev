<?php
require_once __DIR__.'/_lib.php';
exigirSuperadmin();
$seccion=(string)($_GET['seccion']??'todas');
if(!in_array($seccion,['todas','matutina','vespertina'],true)) $seccion='todas';
header('Location: '.url('modulos/votaciones/resultados_csv.php?seccion='.urlencode($seccion)));
exit;
