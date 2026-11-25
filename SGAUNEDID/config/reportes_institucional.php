<?php
/**
 * Identidad del reporte de calificaciones de UNEDID.
 * El encabezado reproduce la disposicion del PDF facilitado por la institucion.
 * Codigo AMIE 01H00363 y nombre de autoridad proporcionados por la institucion.
 * El reporte lo emite UNEDID; no implica certificacion directa del Ministerio.
 */
return [
    'institucion' => 'UNIDAD EDUCATIVA DE INICIACIÓN Y DESARROLLO DEPORTIVO DEL AZUAY',
    'sigla' => 'UNEDID',
    'ciudad' => 'Cuenca, Azuay',
    'regimen' => 'SIERRA',
    'codigo_amie' => '01H00363',
    // Texto solicitado para el certificado. El sistema mantiene T1, T2 y T3;
    // confirme la denominacion del periodo antes de emitir certificados reales.
    // Alternativa: 'TRIMESTRE'.
    'unidad_periodo_certificado' => 'SEMESTRE',
    'autoridad' => 'Dra. Ruth Isabel Lojano Guerrero',
    'cargo_autoridad' => 'RECTORA',
    'logo' => __DIR__ . '/../assets/img/logo.jpeg',
    'escudo_ecuador' => __DIR__ . '/../assets/img/escudo_republica_ecuador.jpeg',
];
