<?php
/**
 * Escala ordinal de comportamiento: F- (1) ... A+ (12).
 * Se promedian SOLAMENTE las valoraciones registradas; los campos sin nota
 * no cuentan. El resultado se redondea a la categoria ordinal mas cercana.
 * La conversion sirve exclusivamente para consolidar comportamiento y no
 * representa una nota academica sobre 10.
 */
function promedioCualitativoComportamiento(array $literales): ?string {
    $escala = ['F-','F+','E-','E+','D-','D+','C-','C+','B-','B+','A-','A+'];
    $numeros = array_flip($escala);
    $suma = 0;
    $cantidad = 0;
    foreach ($literales as $literal) {
        $literal = strtoupper(trim((string)$literal));
        if (!array_key_exists($literal, $numeros)) continue;
        $suma += $numeros[$literal] + 1;
        $cantidad++;
    }
    if ($cantidad === 0) return null;
    $ordinal = (int)round($suma / $cantidad, 0, PHP_ROUND_HALF_UP);
    return $escala[max(0, min(11, $ordinal - 1))];
}

/** Las notas anteriores sin asignatura se usan solo si no hay evaluaciones
 * nuevas en ese mismo trimestre, para no duplicar ni perder historicos. */
function comportamientoConRespaldoHistorico(array $nuevoPorTrimestre, array $antiguoPorTrimestre): array {
    $resultado = [];
    foreach ([1,2,3] as $t) {
        $actual = $nuevoPorTrimestre[$t] ?? [];
        if (!$actual && !empty($antiguoPorTrimestre[$t])) {
            $actual = [$antiguoPorTrimestre[$t]];
        }
        $resultado[$t] = $actual;
    }
    return $resultado;
}
