<?php
/** Evaluacion cualitativa, UNA valoracion por matricula, asignatura y trimestre. */
function sgaComportamientoOpciones(): array {
    return ['A+','A-','B+','B-','C+','C-','D+','D-','E+','E-','F+','F-'];
}
function sgaComportamientoValorValido(string $valor): bool {
    return in_array($valor, sgaComportamientoOpciones(), true);
}
/**
 * Promedio cualitativo de tres trimestres completos.
 * Se asignan rangos equidistantes: A+=12, A-=11, ..., F-=1;
 * se calcula su media aritmetica y se redondea a la letra mas cercana.
 * Es solo una conversion interna para elegir la letra: nunca una nota /10.
 * Retorna null cuando falta al menos una valoracion valida.
 */
function sgaComportamientoFinal(?string $t1, ?string $t2, ?string $t3): ?string {
    $opciones=sgaComportamientoOpciones();
    $indices=array_flip($opciones);
    foreach ([$t1,$t2,$t3] as $letra) {
        if ($letra === null || !isset($indices[$letra])) return null;
    }
    $posicion=(int)round(($indices[$t1]+$indices[$t2]+$indices[$t3])/3,0,PHP_ROUND_HALF_UP);
    return $opciones[$posicion];
}

/** Sin conversion numerica ni promedios. */
function sgaComportamientoResumen(?string $t1, ?string $t2, ?string $t3): string {
    $partes=[];
    foreach ([1=>$t1,2=>$t2,3=>$t3] as $trimestre=>$literal) {
        if ($literal !== null && sgaComportamientoValorValido($literal)) {
            $partes[]='T'.$trimestre.': '.$literal;
        }
    }
    return implode(' / ', $partes);
}

/** Tonos para destacar la seleccion, sin convertir la letra en nota numerica. */
function sgaComportamientoTono(string $literal): string {
    if (in_array($literal,['A+','A-','B+','B-'],true)) return 'alto';
    if (in_array($literal,['C+','C-'],true)) return 'medio';
    return 'bajo'; // D, E y F son valoraciones bajas.
}
/** Resultado [matricula_id => [1 => literal, 2 => literal, 3 => literal]]. */
function sgaComportamientoPorOferta(mysqli $db, int $ofertaId): array {
    $stmt=$db->prepare('SELECT matricula_id,trimestre,literal FROM calificaciones_comportamiento_trimestre WHERE oferta_id=?');
    $stmt->bind_param('i',$ofertaId);$stmt->execute();
    $mapa=[];
    foreach($stmt->get_result()->fetch_all(MYSQLI_ASSOC) as $fila){
        $mapa[(int)$fila['matricula_id']][(int)$fila['trimestre']]=$fila['literal'];
    }
    $stmt->close();
    return $mapa;
}
