<?php
/** Escala de resultados cualitativos por aula (V6). No modifica la nota /10. */
function sgaEscalaResultadosCualitativos(): array {
    return [
        ['min'=>950,'max'=>1000,'letra'=>'A+'],
        ['min'=>850,'max'=>949,'letra'=>'A-'],
        ['min'=>750,'max'=>849,'letra'=>'B+'],
        ['min'=>650,'max'=>749,'letra'=>'B-'],
        ['min'=>550,'max'=>649,'letra'=>'C+'],
        ['min'=>450,'max'=>549,'letra'=>'C-'],
        ['min'=>350,'max'=>449,'letra'=>'D+'],
        ['min'=>250,'max'=>349,'letra'=>'D-'],
        ['min'=>150,'max'=>249,'letra'=>'E+'],
        ['min'=>100,'max'=>149,'letra'=>'E-'],
    ];
}
/** Las notas ya calculadas se comparan a dos decimales, no a enteros. */
function sgaNivelResultadoCualitativo(?float $nota): ?array {
    if ($nota === null || !is_finite($nota)) return null;
    $centavos=(int)round(max(0.0,min(10.0,$nota))*100,0,PHP_ROUND_HALF_UP);
    foreach(sgaEscalaResultadosCualitativos() as $nivel) {
        if($centavos >= $nivel['min']) return $nivel;
    }
    // Compatibilidad con notas registradas inferiores a 1,00 (incluido cero).
    return ['min'=>0,'max'=>99,'letra'=>'E-'];
}
function sgaLetraResultadoCualitativo(?float $nota): string {
    return sgaNivelResultadoCualitativo($nota)['letra'] ?? '';
}
function sgaRangoResultadoCualitativo(?float $nota): string {
    $nivel=sgaNivelResultadoCualitativo($nota);
    if($nivel===null)return '';
    return number_format($nivel['min']/100,2,',','').' - '.number_format($nivel['max']/100,2,',','');
}
/** Las consultas muestran solo la letra; las notas no registradas no son E-. */
function sgaNotaResultadoParaConsulta(?float $nota, bool $resultadosCualitativos): string {
    if($nota===null || !is_finite($nota))return '—';
    return $resultadosCualitativos ? sgaLetraResultadoCualitativo($nota) : number_format($nota,2,'.','');
}
