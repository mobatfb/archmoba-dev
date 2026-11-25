<?php
/** Evaluacion cualitativa, UNA valoracion por matricula, asignatura y semestre. */
function sgaComportamientoOpciones(): array {
    return ['A+','A-','B+','B-','C+','C-','D+','D-','E+','E-','F+','F-'];
}
function sgaComportamientoValorValido(string $valor): bool {
    return in_array($valor, sgaComportamientoOpciones(), true);
}
/** Sin conversion numerica ni promedios. */
function sgaComportamientoResumen(?string $s1, ?string $s2): string {
    $partes=[];
    if ($s1 !== null && sgaComportamientoValorValido($s1)) $partes[]='S1: '.$s1;
    if ($s2 !== null && sgaComportamientoValorValido($s2)) $partes[]='S2: '.$s2;
    return implode(' / ', $partes);
}
/** Resultado [matricula_id => [1 => literal, 2 => literal]]. */
function sgaComportamientoPorOferta(mysqli $db, int $ofertaId): array {
    $stmt=$db->prepare('SELECT matricula_id,semestre,literal FROM calificaciones_comportamiento_semestre WHERE oferta_id=?');
    $stmt->bind_param('i',$ofertaId);$stmt->execute();
    $mapa=[];
    foreach($stmt->get_result()->fetch_all(MYSQLI_ASSOC) as $fila){
        $mapa[(int)$fila['matricula_id']][(int)$fila['semestre']]=$fila['literal'];
    }
    $stmt->close();
    return $mapa;
}
