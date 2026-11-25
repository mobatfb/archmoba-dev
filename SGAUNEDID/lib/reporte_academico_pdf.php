<?php
require_once __DIR__ . '/simple_pdf.php';
require_once __DIR__ . '/sga_resultados_cualitativos.php';
require_once __DIR__ . '/comportamiento_trimestres.php';

/**
 * Reporte academico UNEDID, distribuido segun el formato A4 facilitado por
 * la institucion. Se usan calificaciones efectivamente almacenadas en el SGA.
 * La presencia de un membrete no sustituye autorizacion, firma o validacion.
 */
function reporteNormalizarAsignatura(string $valor): string {
    $texto = @iconv('UTF-8', 'ASCII//TRANSLIT//IGNORE', $valor);
    if ($texto === false) $texto = $valor;
    $texto = strtoupper($texto);
    return trim(preg_replace('/[^A-Z0-9]+/', ' ', $texto) ?? '');
}

function reporteEquivalencia(?float $nota, string $literal = '', bool $especial = false): array {
    if ($nota === null) return ['', ''];
    // La escala especial se presenta solo como literal en el certificado.
    // La equivalencia academica sigue calculandose con la nota numerica
    // que permanece almacenada en la base de datos.
    $literal = $especial ? '' : trim($literal);
    if (in_array($literal, ['D.A.R.', 'A.A.R.', 'P.A.A.R.', 'N.A.R.'], true)) {
        $codigo = $literal;
    } else {
        $codigo = $nota >= 9 ? 'D.A.R.' : ($nota >= 7 ? 'A.A.R.' : ($nota >= 4 ? 'P.A.A.R.' : 'N.A.R.'));
    }
    $descripcion = [
        'D.A.R.' => 'Domina los aprendizajes',
        'A.A.R.' => 'Alcanza los aprendizajes',
        'P.A.A.R.' => 'Próximo a alcanzar',
        'N.A.R.' => 'No alcanza los aprendizajes',
    ];
    return [$codigo, $descripcion[$codigo] ?? $codigo];
}

/** Equivalencia por rangos del aula; independiente de comportamiento. */
function reporteEquivalenciaResultadoCualitativo(?float $nota): array {
    return [sgaLetraResultadoCualitativo($nota), sgaRangoResultadoCualitativo($nota)];
}

/**
 * Equivalencia descriptiva del literal de la asignatura de comportamiento.
 * Es una valoracion cualitativa, no una calificacion academica numerica.
 */
function reporteEquivalenciaComportamiento(string $literal): string {
    $valor = strtoupper(trim(str_replace('−', '-', $literal)));
    if ($valor === 'A+') return 'Domina los aprendizajes';
    if (in_array($valor, ['A-', 'B+'], true)) return 'Alcanza los aprendizajes';
    if (in_array($valor, ['B-', 'C+', 'C-'], true)) return 'Próximo a alcanzar';
    if (in_array($valor, ['D+', 'D-', 'E+', 'E-', 'F+', 'F-'], true)) return 'No alcanza los aprendizajes';
    return '';
}

function reporteEtiquetaTrimestre(int $trimestre): string {
    return [1 => 'PRIMER', 2 => 'SEGUNDO', 3 => 'TERCER'][$trimestre] ?? 'ANUAL';
}

/**
 * El examen supletorio solo corresponde a EGB Media (5-7), EGB Superior
 * (8-10) y Bachillerato. En la BD, nivel suele ser "EGB" y el grado esta
 * en aulas.nombre; NO clasificar toda EGB como apta (Inicial/1-4 no lo son).
 * Ante un grado no reconocible se conserva el certificado sin esa columna.
 * Es una decision de presentacion; NO concede permiso para registrar notas.
 */
function reporteCertificadoAdmiteSupletorio(array $est): bool {
    $nivel = reporteNormalizarAsignatura((string)($est['nivel'] ?? ''));
    $curso = reporteNormalizarAsignatura((string)($est['aula'] ?? ''));
    $nombreCompleto = trim($nivel . ' ' . $curso);
    if (preg_match('/\b(INICIAL|PREPARATORIA|ELEMENTAL)\b/', $nombreCompleto)) return false;
    if (preg_match('/\b(BACHILLERATO|BGU|BTP|BTI|BTD|TECNICO)\b/', $nivel)) return true;
    if (preg_match('/\b(MEDIA|SUPERIOR)\b/', $nivel)) return true;
    if (!preg_match('/\b(EGB|BASICA)\b/', $nivel)) return false;
    if (preg_match('/\b(QUINTO|SEXTO|SEPTIMO|OCTAVO|NOVENO|DECIMO)\b/', $curso)) return true;
    if (preg_match('/(?:^| )(?:10|[5-9])(?: |$)/', $curso)) return true;
    if (preg_match('/^(?:10|[5-9])\s*(?:EGB|TO|TA|VO|VA|MO|MA|NO|NA|T0|\x{00BA}|\x{00B0})\b/u', $curso)) return true;
    return false;
}

/**
 * Muestra exclusivamente las asignaturas asociadas a las ofertas academicas
 * activas del aula y periodo del estudiante. No completa el reporte con el
 * catalogo del modelo PDF ni sustituye el nombre de la asignatura en la BD.
 * El filtro de aula y periodo, y la lectura del area real, se realizan en
 * modulos/reportes/certificacion.php.
 */
function reporteAsignaturasDeOferta(array $registradas): array {
    $salida = [];
    foreach ($registradas as $registro) {
        $nombre = trim((string)($registro['asignatura'] ?? ''));
        if ($nombre === '') continue;
        $registro['asignatura'] = $nombre;
        $registro['area'] = trim((string)($registro['area'] ?? ''));
        // El area proviene de la relacion asignaturas.area_id -> areas.id; no se adivina por texto.
        // La asignatura civica se extiende sobre las primeras dos columnas,
        // igual que en el modelo, solamente cuando esta asignada al aula.
        $registro['fusionar_area'] = reporteNormalizarAsignatura($nombre) ===
            'CIVICA Y ACOMPANAMIENTO INTEGRAL EN EL AULA';
        $salida[] = $registro;
    }
    return $salida;
}

/** @return array{pdf:SimplePdf,filename:string,registradas:int,pendientes:int} */
function crearReporteAcademicoInstitucional(array $est, array $rows, int $trimestre, array $configEvaluacion, bool $esFinal=false): array {
    $institucion = require __DIR__ . '/../config/reportes_institucional.php';
    $resultadoCualitativo = !empty($est['resultados_cualitativos']);
    $pdf = new SimplePdf();
    $colores = [
        'azul' => '#194B73', 'azulOscuro' => '#153F61', 'texto' => '#28323E',
        'gris' => '#637484', 'cabecera' => '#E8EFF4', 'borde' => '#B8C5CF',
    ];
    // El certificado anual muestra el supletorio solo donde aplica al grado.
    // Los certificados T1, T2 y T3 nunca cambian de formato.
    $conSupletorio = $trimestre === 0 && reporteCertificadoAdmiteSupletorio($est);
    $datos = []; $suma = 0.0; $nNotas = 0; $pendientes = 0;
    $pendientesSupletorio = 0;
    foreach ($rows as $r) {
        // Nunca contar como materia una fila sin asignatura de la oferta.
        if (trim((string)($r['asignatura'] ?? '')) === '') continue;
        $item = $r;
        // Una valoracion por trimestre; el resultado anual es una letra calculada.
        if (!empty($r['evaluacion_cualitativa_parametros'])) {
            // Esta modalidad registra varios ambitos por trimestre, no una
            // unica nota numerica. No utilizar posibles valores historicos.
            $item['por_parametros']=true;
            $item['nota_reporte']=null;
            $item['promedio_anual']=null;
            $item['supletorio_visible']=null;
            $item['eq']=['','Evaluación por parámetros (informe separado)'];
            $datos[]=$item;
            continue;
        }
        if (!empty($r['solo_visor_comportamiento'])) {
            foreach ([1,2,3] as $t) {
                $literal = $r['comp_t'.$t] ?? null;
                $item['comportamiento_t'.$t] = ($literal !== null && sgaComportamientoValorValido((string)$literal))
                    ? (string)$literal : null;
            }
            // El certificado anual muestra la letra final derivada de T1/T2/T3.
            // No modificar la columna de promedio academico ni la base de datos.
            $item['comportamiento_final']=sgaComportamientoFinal(
                $item['comportamiento_t1'],$item['comportamiento_t2'],$item['comportamiento_t3']);
            $item['comportamiento_visible'] = $trimestre>=1 && $trimestre<=3
                ? ($item['comportamiento_t'.$trimestre] ?? '')
                : ($item['comportamiento_final'] ?? '');
            $item['nota_reporte']=null;
            $item['promedio_anual']=null;
            $item['supletorio_visible']=null;
            // La equivalencia descriptiva corresponde a la letra realmente visible:
            // la del trimestre solicitado o la final calculada de T1/T2/T3.
            // No convierte comportamiento a una nota /10 ni afecta promedios.
            $item['eq'] = ['', reporteEquivalenciaComportamiento((string)$item['comportamiento_visible'])];
            $datos[]=$item;
            continue;
        }
        $especial = !empty($r['usa_literal_especial']);
        if ($trimestre > 0) {
            $val = $r['t'.$trimestre] ?? null;
            $nota = ($val === null || $val === '') ? null : (float)$val;
            $literal = (string)($r['c'.$trimestre.'_cual'] ?? '');
        } else {
            $t1 = $r['t1'] ?? null; $t2 = $r['t2'] ?? null; $t3 = $r['t3'] ?? null;
            $item['promedio_anual'] = null;
            $item['supletorio_visible'] = null;
            $item['nota_final_pendiente'] = false;
            if ($t1 !== null && $t2 !== null && $t3 !== null) {
                $supletorio = isset($r['examen_supletorio']) ? (float)$r['examen_supletorio'] : null;
                // La calculadora del SGA ya fija la nota de promocion en 7.00
                // cuando un supletorio es aprobado. No modificar sus reglas.
                $fin = calcularFinalAnual((float)$t1, (float)$t2, (float)$t3,
                    $conSupletorio ? $supletorio : null, $configEvaluacion);
                $item['promedio_anual'] = $fin['promedio_tres'];
                $nota = $conSupletorio ? $fin['promedio_final'] : $fin['promedio_tres'];
                if ($conSupletorio) {
                    $promedioTres = (float)$fin['promedio_tres'];
                    $enRango = $promedioTres >= (float)$configEvaluacion['nota_min_supletorio']
                        && $promedioTres < (float)$configEvaluacion['nota_aprobacion'];
                    if ($enRango && $supletorio !== null && $supletorio > 0.0) {
                        $item['supletorio_visible'] = $supletorio;
                    }
                    if ($enRango && ($supletorio === null || $supletorio <= 0.0)) {
                        // No presentar el promedio original como una nota FINAL
                        // definitiva cuando aun falta rendir el supletorio.
                        $nota = null;
                        $item['nota_final_pendiente'] = true;
                        $pendientesSupletorio++;
                    }
                }
            } else {
                $nota = null;
            }
            $literal = '';
        }
        $item['nota_reporte'] = $nota;
        // Para aulas cualitativas la calificacion se presenta SOLO como letra;
        // la columna de equivalencia muestra el rango de la nueva escala.
        // Todos los promedios permanecen calculados con valores numericos reales.
        $item['eq'] = $resultadoCualitativo
            ? reporteEquivalenciaResultadoCualitativo($nota)
            : reporteEquivalencia($nota, $literal, $especial);
        $datos[] = $item;
        if ($nota === null) $pendientes++; else { $nNotas++; $suma += $nota; }
    }
    $filas = reporteAsignaturasDeOferta($datos);
    $promedio = $nNotas ? truncar2($suma / $nNotas) : null;
    $nombreAlumno = trim((string)($est['apellidos'] ?? '') . ' ' . (string)($est['nombres'] ?? ''));
    $periodo = (string)($est['periodo'] ?? '');
    $curso = trim((string)($est['nivel'] ?? '') . '  ' . (string)($est['aula'] ?? '') . '  ' . (string)($est['paralelo'] ?? ''));
    // La denominacion visible se configura sin modificar los 3 periodos T1/T2/T3 de la BD.
    $unidadPeriodo = strtoupper(trim((string)($institucion['unidad_periodo_certificado'] ?? 'TRIMESTRE')));
    if (!in_array($unidadPeriodo, ['TRIMESTRE', 'SEMESTRE'], true)) $unidadPeriodo = 'TRIMESTRE';
    $titulo = $trimestre > 0
        ? 'CERTIFICADO DE CALIFICACIONES DEL ' . reporteEtiquetaTrimestre($trimestre) . ' ' . $unidadPeriodo
        : ($esFinal ? 'CERTIFICADO DE CALIFICACIONES FINALES' : 'CERTIFICADO DE CALIFICACIONES ANUALES');
    // Un ciclo anual no tiene tres semestres: T3 se presenta de forma neutral
    // hasta que la institucion confirme la denominacion oficial de T3.
    if ($unidadPeriodo === 'SEMESTRE' && $trimestre === 3) {
        $titulo = 'CERTIFICADO DE CALIFICACIONES DEL TERCER PERÍODO ACADÉMICO';
    }
    $fecha = (new DateTimeImmutable('now', new DateTimeZone('America/Guayaquil')))->format('d/m/Y');
    $identificador = 'SGA/' . preg_replace('/[^0-9-]/', '', $periodo) . '/'
        . ($trimestre ? 'T'.$trimestre : ($esFinal ? 'FINAL' : 'ANUAL')) . '/' . str_pad((string)($est['id'] ?? 0), 6, '0', STR_PAD_LEFT);
    // En el reporte ANUAL se muestran también las tres notas trimestrales.
    // Los reportes individuales T1/T2/T3 conservan la tabla original.
    $esAnual = ($trimestre === 0);
    $x = $conSupletorio
        ? [36.0, 124.0, 242.0, 272.0, 302.0, 332.0, 379.0, 429.0, 475.0, 559.0]
        : ($esAnual
            ? [36.0, 138.0, 260.0, 301.0, 342.0, 383.0, 459.0, 559.0]
            : [36.0, 166.0, 297.0, 394.0, 559.0]);
    $indiceNota = $conSupletorio ? 7 : ($esAnual ? 5 : 2);
    $indiceEquivalencia = $conSupletorio ? 8 : ($esAnual ? 6 : 3);
    $ultimoIndice = count($x) - 1;
    $tablaSuperior = 595.0;
    $cabezaAlto = 38.0;
    // Ajustar a las asignaturas reales del aula; reservar el bloque de firma
    // y sello, con una zona libre de unos 90 puntos antes de la linea.
    // Para paralelos con mas de 20 materias se pasa a la siguiente pagina.
    $altoTotal = 18.3;
    $minYTabla = 250.0;
    $altoFila = min(19.0, ($tablaSuperior - $cabezaAlto - $minYTabla - $altoTotal)
        / max(1, min(20, count($filas))));
    $pageNum = 0;
    $nombreInst = trim((string)($institucion['institucion'] ?? 'UNIDAD EDUCATIVA DE INICIACIÓN Y DESARROLLO DEPORTIVO DEL AZUAY'));
    $ciudad = trim((string)($institucion['ciudad'] ?? 'Cuenca, Azuay'));

    $dibujarCabecera = function() use (&$pdf, &$pageNum, $institucion, $colores, $est, $x, $tablaSuperior, $cabezaAlto, $nombreAlumno, $nombreInst, $periodo, $curso, $titulo, $esAnual, $conSupletorio, $ultimoIndice, $resultadoCualitativo) : void {
        $pdf->addPage(); $pageNum++;
        $escudo = (string)($institucion['escudo_ecuador'] ?? '');
        if ($escudo !== '') $pdf->imageJpeg($escudo, 38, 747, 124, 62.5);
        $pdf->rightText(558, 789, 'Ministerio de Educación', 14.2, true, $colores['azul']);
        $pdf->rightText(558, 773, 'UNEDID - Cuenca', 7.6, false, $colores['gris']);

        $pdf->textColor(38, 722, 'CÓDIGO AMIE:', 8.35, true, $colores['texto']);
        $amie = trim((string)($institucion['codigo_amie'] ?? ''));
        $pdf->textColor(127, 722, $amie !== '' ? $amie : '_______________', 8.3, false, $colores['texto']);
        $pdf->textColor(265, 722, 'AÑO LECTIVO:', 8.35, true, $colores['texto']);
        $pdf->textColor(351, 722, $periodo, 8.3, false, $colores['texto']);
        $pdf->textColor(448, 722, 'RÉGIMEN:', 8.35, true, $colores['texto']);
        $pdf->textColor(507, 722, (string)($institucion['regimen'] ?? 'SIERRA'), 8.3, false, $colores['texto']);
        $pdf->centerText(297.5, 700, $pdf->fitText($titulo, 520, 11.4, true), 11.4, true, $colores['texto']);

        if (reporteNormalizarAsignatura($nombreInst) === reporteNormalizarAsignatura('UNIDAD EDUCATIVA DE INICIACIÓN Y DESARROLLO DEPORTIVO DEL AZUAY')) {
            // El titulo institucional ocupa exactamente dos renglones en el modelo.
            $lineasInstitucion = ['UNIDAD EDUCATIVA DE INICIACIÓN Y DESARROLLO', 'DEPORTIVO DEL AZUAY'];
        } else {
            $lineasInstitucion = $pdf->wrapText($nombreInst, 405, 10.6, true);
        }
        foreach (array_slice($lineasInstitucion, 0, 2) as $k => $linea) {
            $pdf->centerText(297.5, 671 - $k * 14.0, $pdf->fitText($linea, 405, 10.6, true), 10.6, true, $colores['texto']);
        }
        $pdf->textColor(38, 631, 'ESTUDIANTE:', 8.3, true, $colores['texto']);
        $pdf->textColor(118, 631, $pdf->fitText($nombreAlumno, 443, 9.1, true), 9.1, true, $colores['texto']);
        $pdf->textColor(38, 614, 'CÉDULA:', 8.0, true, $colores['texto']);
        $pdf->textColor(91, 614, (string)($est['cedula'] ?? ''), 8.0, false, $colores['texto']);
        $pdf->textColor(263, 614, 'CURSO / PARALELO:', 8.0, true, $colores['texto']);
        $pdf->textColor(385, 614, $pdf->fitText($curso, 175, 8.0, false), 8.0, false, $colores['texto']);

        $pdf->fillRect($x[0], $tablaSuperior - $cabezaAlto, $x[$ultimoIndice] - $x[0], $cabezaAlto, $colores['cabecera'], $colores['borde'], 0.5);
        $pdf->centerText(($x[0]+$x[1])/2, $tablaSuperior - 23, 'ÁREA', $esAnual ? 8.2 : 9.2, true, $colores['texto']);
        $pdf->centerText(($x[1]+$x[2])/2, $tablaSuperior - 23, 'ASIGNATURA', $esAnual ? 8.2 : 9.2, true, $colores['texto']);
        if ($esAnual) {
            // Tres cuadros independientes para las notas de T1, T2 y T3.
            $pdf->centerText(($x[2]+$x[5])/2, $tablaSuperior - 12, 'TRIMESTRES', 7.2, true, $colores['texto']);
            $pdf->lineColor($x[2], $tablaSuperior - 19, $x[5], $tablaSuperior - 19, .45, $colores['borde']);
            for ($t=1; $t<=3; $t++) {
                $pdf->centerText(($x[$t+1]+$x[$t+2])/2, $tablaSuperior - 30, $t . 'T', 8.8, true, $colores['azulOscuro']);
            }
            if ($conSupletorio) {
                $pdf->centerText(($x[5]+$x[6])/2, $tablaSuperior - 15, 'EXAMEN', 7.1, true, $colores['texto']);
                $pdf->centerText(($x[5]+$x[6])/2, $tablaSuperior - 29, 'SUPLETORIO', 6.5, true, $colores['texto']);
                $pdf->centerText(($x[6]+$x[7])/2, $tablaSuperior - 15, ($resultadoCualitativo?'RESULTADO':'PROMEDIO'), 6.5, true, $colores['texto']);
                $pdf->centerText(($x[6]+$x[7])/2, $tablaSuperior - 29, 'ANUAL', 7.5, true, $colores['texto']);
                $pdf->centerText(($x[7]+$x[8])/2, $tablaSuperior - 15, ($resultadoCualitativo?'RESULTADO':'NOTA'), $resultadoCualitativo?6.1:7.9, true, $colores['texto']);
                $pdf->centerText(($x[7]+$x[8])/2, $tablaSuperior - 29, 'FINAL', 7.9, true, $colores['texto']);
                $pdf->centerText(($x[8]+$x[9])/2, $tablaSuperior - 15, 'PROMEDIO', 7.6, true, $colores['texto']);
                $pdf->centerText(($x[8]+$x[9])/2, $tablaSuperior - 29, 'EQUIVALENCIA', 6.8, true, $colores['texto']);
            } else {
                $pdf->centerText(($x[5]+$x[6])/2, $tablaSuperior - 15, ($resultadoCualitativo?'RESULTADO':'PROMEDIO'), 7.2, true, $colores['texto']);
                $pdf->centerText(($x[5]+$x[6])/2, $tablaSuperior - 29, 'ANUAL', 8.4, true, $colores['texto']);
                $pdf->centerText(($x[6]+$x[7])/2, $tablaSuperior - 15, 'PROMEDIO', 8.5, true, $colores['texto']);
                $pdf->centerText(($x[6]+$x[7])/2, $tablaSuperior - 29, 'EQUIVALENCIA', 7.3, true, $colores['texto']);
            }
        } else {
            $pdf->centerText(($x[2]+$x[3])/2, $tablaSuperior - 17, 'CALIFICACIÓN', 8.7, true, $colores['texto']);
            $pdf->centerText(($x[2]+$x[3])/2, $tablaSuperior - 30, ($resultadoCualitativo?'CUALITATIVA':'CUANTITATIVA'), 8.25, true, $colores['texto']);
            $pdf->centerText(($x[3]+$x[4])/2, $tablaSuperior - 15, 'PROMEDIO', 10.2, true, $colores['texto']);
            $pdf->centerText(($x[3]+$x[4])/2, $tablaSuperior - 29, 'EQUIVALENCIA', 8.5, true, $colores['texto']);
        }
        for ($i=1; $i<$ultimoIndice; $i++) {
            // Las líneas de separación internas de 1T/2T/3T no atraviesan
            // el título agrupador «TRIMESTRES».
            $hasta = ($esAnual && ($i === 3 || $i === 4))
                ? $tablaSuperior - 19 : $tablaSuperior;
            $pdf->lineColor($x[$i], $tablaSuperior - $cabezaAlto, $x[$i], $hasta, .44, $colores['borde']);
        }
    };
    $dibujarPie = function() use (&$pdf, $colores, &$pageNum, $identificador): void {
        $pdf->lineColor(36, 45, 559, 45, .5, $colores['borde']);
        $pdf->textColor(38, 32, 'Emitido desde SGA UNEDID   ·   Ref. ' . $identificador, 6.65, false, $colores['gris']);
        $pdf->rightText(558, 32, 'Página ' . $pageNum, 6.65, false, $colores['gris']);
    };
    $dibujarCabecera();
    $y = $tablaSuperior - $cabezaAlto;
    foreach ($filas as $f) {
        if ($y - $altoFila - $altoTotal < $minYTabla) {
            $dibujarPie();
            $dibujarCabecera();
            $y = $tablaSuperior - $cabezaAlto;
        }
        $bottom = $y - $altoFila;
        $pdf->fillRect($x[0], $bottom, $x[$ultimoIndice]-$x[0], $altoFila, '#FFFFFF', $colores['borde'], .35);
        if ($esAnual) {
            // Sombreado sutil para identificar los tres cuadros trimestrales.
            $pdf->fillRect($x[2], $bottom, $x[5]-$x[2], $altoFila, '#F4F8FC');
        }
        $fusion = !empty($f['fusionar_area']);
        if ($fusion) {
            $tamArea = $esAnual ? 6.6 : 7.0;
            $pdf->textColor($x[0]+6, $bottom+5.2,
                $pdf->fitText((string)$f['area'], $x[2]-$x[0]-10, $tamArea),
                $tamArea, false, $colores['texto']);
        } else {
            $tamArea = $esAnual ? 6.6 : 7.25;
            $pdf->textColor($x[0]+4, $bottom+5.1,
                $pdf->fitText((string)$f['area'], $x[1]-$x[0]-8, $tamArea),
                $tamArea, false, $colores['texto']);
            if ($esAnual) {
                // Mantener legibles asignaturas largas en las columnas más estrechas.
                $nombre = (string)$f['asignatura'];
                $anchoNombre = $x[2]-$x[1]-8;
                // Ajustar tamaño e interlineado a la altura disponible;
                // incluso con 20 asignaturas, ninguna línea sale de su fila.
                $tamNombre = min(6.8, max(5.5, ($altoFila - 2.0) / 2));
                $lineas = $pdf->wrapText($nombre, $anchoNombre, $tamNombre);
                while (count($lineas) > 2 && $tamNombre > 5.5) {
                    $tamNombre = max(5.5, $tamNombre - .25);
                    $lineas = $pdf->wrapText($nombre, $anchoNombre, $tamNombre);
                }
                if (count($lineas) > 2) {
                    $lineas[1] = $pdf->fitText(implode(' ', array_slice($lineas, 1)), $anchoNombre, $tamNombre);
                }
                $lineas = array_slice($lineas, 0, 2);
                if (count($lineas) === 2) {
                    $espacio = 0.6;
                    $segundoY = $bottom + max(1.0, ($altoFila - 2*$tamNombre - $espacio)/2);
                    $pdf->textColor($x[1]+4, $segundoY+$tamNombre+$espacio, $lineas[0], $tamNombre, false, $colores['texto']);
                    $pdf->textColor($x[1]+4, $segundoY, $lineas[1], $tamNombre, false, $colores['texto']);
                } else {
                    $pdf->textColor($x[1]+4, $bottom+5.1,
                        $pdf->fitText($nombre, $anchoNombre, $tamNombre), $tamNombre, false, $colores['texto']);
                }
            } else {
                $pdf->textColor(170, $bottom+5.1, $pdf->fitText((string)$f['asignatura'], 122, 7.35), 7.35, false, $colores['texto']);
            }
            $pdf->lineColor($x[1], $bottom, $x[1], $y, .33, $colores['borde']);
        }
        if ($esAnual) {
            for ($t=1; $t<=3; $t++) {
                $esVisor = !empty($f['solo_visor_comportamiento']);
                $valorTrimestre = !empty($f['por_parametros']) ? null : ($esVisor
                    ? ($f['comportamiento_t'.$t] ?? null)
                    : ($f['t'.$t] ?? null));
                $notaDisponible = $valorTrimestre !== null && $valorTrimestre !== '';
                $textoTrimestre = !$notaDisponible ? '-'
                    : ($esVisor ? (string)$valorTrimestre
                        : ($resultadoCualitativo
                            ? sgaLetraResultadoCualitativo((float)$valorTrimestre)
                            : number_format((float)$valorTrimestre, 2, '.', '')));
                // En las asignaturas con escala especial se muestra solamente
                // el literal, sin numero ni parentesis, en los tres trimestres.
                $conLiteral = $notaDisponible && !$esVisor && !empty($f['usa_literal_especial']) && empty($est['resultados_cualitativos']);
                if ($conLiteral) {
                    $textoTrimestre = literalEspecial((float)$valorTrimestre);
                }
                // No cortar las equivalencias aunque cambie el ancho de la celda.
                $anchoDisponible = $x[$t+2] - $x[$t+1] - 5.0;
                $tamTrimestre = 7.4;
                while ($tamTrimestre > 6.0 && $pdf->textWidth($textoTrimestre, $tamTrimestre, $conLiteral) > $anchoDisponible) {
                    $tamTrimestre -= 0.2;
                }
                $pdf->centerText(($x[$t+1]+$x[$t+2])/2, $bottom+5.1,
                    $pdf->fitText($textoTrimestre, $anchoDisponible, $tamTrimestre, $conLiteral),
                    $tamTrimestre, $conLiteral,
                    $notaDisponible ? $colores['texto'] : $colores['gris']);
            }
        }
        for ($i=2; $i<$ultimoIndice; $i++) {
            $pdf->lineColor($x[$i], $bottom, $x[$i], $y, .33, $colores['borde']);
        }
        if ($conSupletorio && empty($f['solo_visor_comportamiento'])) {
            // Celdas de la nota de examen y del promedio ANTES del supletorio.
            $sup = $f['supletorio_visible'] ?? null;
            if ($sup !== null) {
                $pdf->centerText(($x[5]+$x[6])/2, $bottom+5.1,
                    ($resultadoCualitativo?sgaLetraResultadoCualitativo((float)$sup):number_format((float)$sup, 2, '.', '')), 7.2, true, $colores['texto']);
            }
            $original = $f['promedio_anual'] ?? null;
            if ($original !== null) {
                $especial = !empty($f['usa_literal_especial']) && empty($est['resultados_cualitativos']);
                $originalVisible = $resultadoCualitativo ? sgaLetraResultadoCualitativo((float)$original)
                    : ($especial ? literalEspecial((float)$original)
                    : number_format((float)$original, 2, '.', ''));
                $pdf->centerText(($x[6]+$x[7])/2, $bottom+5.1,
                    $originalVisible, 7.2, true, $colores['texto']);
            }
        }
        $nota = $f['nota_reporte'] ?? null;
        $comportamientoVisible = !empty($f['solo_visor_comportamiento'])
            ? trim((string)($f['comportamiento_visible'] ?? '')) : '';
        if ($comportamientoVisible !== '') {
            // Misma celda, tipografia y fondo que el resto de asignaturas.
            // En esta fila no se convierte el comportamiento a escala /10.
            $tamVisor = $esAnual ? 7.6 : 8.0;
            $pdf->centerText(($x[$indiceNota]+$x[$indiceNota+1])/2,
                $bottom+5.0,
                $pdf->fitText($comportamientoVisible,$x[$indiceNota+1]-$x[$indiceNota]-6,$tamVisor,true),
                $tamVisor, true, $colores['texto']);
        } elseif ($nota === null && $conSupletorio && !empty($f['nota_final_pendiente'])) {
            $pdf->centerText(($x[$indiceNota]+$x[$indiceNota+1])/2,
                $bottom+5.0, 'PEND.', 6.5, true, $colores['gris']);
        } elseif ($nota !== null) {
            // El certificado imprime solo A+/A-/B+/B- para materias
            // cualitativas; la nota numerica queda para calculos y promedios.
            $notaVisible = $resultadoCualitativo ? sgaLetraResultadoCualitativo((float)$nota)
                : (!empty($f['usa_literal_especial']) ? literalEspecial((float)$nota)
                : number_format((float)$nota, 2, '.', ''));
            $tamNota = $esAnual ? 7.4 : 8.0;
            $pdf->centerText(($x[$indiceNota]+$x[$indiceNota+1])/2, $bottom+5.0,
                $pdf->fitText($notaVisible, $x[$indiceNota+1]-$x[$indiceNota]-6, $tamNota, true),
                $tamNota, true, $colores['texto']);
        }
        $eq = (string)($f['eq'][1] ?? '');
        if ($eq !== '') {
            $tamEq = $esAnual ? 6.6 : 7.45;
            $anchoEq = $x[$indiceEquivalencia+1]-$x[$indiceEquivalencia]-6;
            while ($tamEq > 5.3 && $pdf->textWidth($eq, $tamEq) > $anchoEq) {
                $tamEq -= .2;
            }
            $pdf->centerText(($x[$indiceEquivalencia]+$x[$indiceEquivalencia+1])/2,
                $bottom+5.3,
                $pdf->fitText($eq, $anchoEq, $tamEq),
                $tamEq, false, $colores['texto']);
        }
        $y = $bottom;
    }
    // El promedio general se mantiene en la ultima fila del cuadro.
    // Ya se reservo su altura al dibujar las materias para evitar una pagina
    // adicional que contenga solamente el promedio.
    $h = $altoTotal; $bottom = $y-$h;
    $pdf->fillRect($x[0], $bottom, $x[$ultimoIndice]-$x[0], $h, '#FFFFFF', $colores['borde'], .48);
    if ($esAnual) {
        $pdf->fillRect($x[2], $bottom, $x[5]-$x[2], $h, '#EAF2F9');
    }
    for ($i=2; $i<$ultimoIndice; $i++) {
        $pdf->lineColor($x[$i], $bottom, $x[$i], $y, .48, $colores['borde']);
    }
    $pdf->centerText(($x[0]+$x[2])/2, $bottom+5.7, $resultadoCualitativo?'RESULTADO GENERAL':'PROMEDIO GENERAL', 8.4, true, $colores['texto']);
    if ($esAnual) {
        // Cada promedio de trimestre incluye solo las notas efectivamente registradas.
        for ($t=1; $t<=3; $t++) {
            $sumaTrimestre = 0.0;
            $cantidadTrimestre = 0;
            foreach ($filas as $fila) {
                if (!empty($fila['solo_visor_comportamiento'])) continue;
                $notaTrimestre = $fila['t'.$t] ?? null;
                if ($notaTrimestre === null || $notaTrimestre === '') continue;
                $sumaTrimestre += (float)$notaTrimestre;
                $cantidadTrimestre++;
            }
            if ($cantidadTrimestre > 0) {
                $promedioTrimestre = truncar2($sumaTrimestre / $cantidadTrimestre);
                $pdf->centerText(($x[$t+1]+$x[$t+2])/2, $bottom+5.3,
                    ($resultadoCualitativo?sgaLetraResultadoCualitativo($promedioTrimestre):number_format($promedioTrimestre, 2, '.', '')), 7.4, true, $colores['texto']);
            }
        }
    }
    if ($conSupletorio) {
        $sumaOriginal = 0.0; $nOriginales = 0;
        foreach ($filas as $fila) {
            if (!empty($fila['solo_visor_comportamiento'])) continue;
            $original = $fila['promedio_anual'] ?? null;
            if ($original === null) continue;
            $sumaOriginal += (float)$original;
            $nOriginales++;
        }
        if ($nOriginales > 0) {
            $pdf->centerText(($x[6]+$x[7])/2, $bottom+5.3,
                ($resultadoCualitativo?sgaLetraResultadoCualitativo(truncar2($sumaOriginal/$nOriginales)):number_format(truncar2($sumaOriginal / $nOriginales), 2, '.', '')),
                7.4, true, $colores['texto']);
        }
    }
    if ($promedio !== null) {
        $pdf->centerText(($x[$indiceNota]+$x[$indiceNota+1])/2,
            $bottom+5.6, ($resultadoCualitativo?sgaLetraResultadoCualitativo($promedio):number_format($promedio, 2, '.', '')), $esAnual ? 8.0 : 8.8,
            true, $colores['texto']);
        $eqGeneral = $resultadoCualitativo ? reporteEquivalenciaResultadoCualitativo($promedio) : reporteEquivalencia($promedio);
        $tamEqGeneral = $esAnual ? 6.6 : 7.45;
        $pdf->centerText(($x[$indiceEquivalencia]+$x[$indiceEquivalencia+1])/2,
            $bottom+5.5,
            $pdf->fitText((string)$eqGeneral[1], $x[$indiceEquivalencia+1]-$x[$indiceEquivalencia]-6, $tamEqGeneral),
            $tamEqGeneral, false, $colores['texto']);
    }

    $autoridad = trim((string)($institucion['autoridad'] ?? ''));
    $cargo = trim((string)($institucion['cargo_autoridad'] ?? 'RECTOR(A)'));
    // Zona reservada de 94 puntos para la firma fisica de la autoridad,
    // sin insertar firma ni sello digital de manera automatica.
    $pdf->textColor(38, 219, 'AUTORIDAD INSTITUCIONAL - FIRMA Y SELLO:', 7.6, true, $colores['gris']);
    $pdf->lineColor(38, 125, 317, 125, .75, $colores['texto']);
    $pdf->textColor(38, 109, $autoridad !== '' ? $pdf->fitText($autoridad, 284, 8.8, true) : 'Nombre y firma de la autoridad', 8.8, true, $colores['texto']);
    $pdf->textColor(38, 94, $cargo, 8.0, false, $colores['texto']);
    $pdf->textColor(38, 73, $ciudad . ' - Fecha de emisión: ' . $fecha, 7.8, false, $colores['gris']);
    if ($pendientesSupletorio > 0) {
        $pdf->textColor(38, 59,
            'Hay supletorios pendientes; la nota final y el promedio general son provisionales.',
            6.8, false, $colores['gris']);
    } elseif ($pendientes > 0) {
        $pdf->textColor(38, 59,
            'Existen asignaturas pendientes; el promedio mostrado es parcial.',
            6.8, false, $colores['gris']);
    }

    $logo = (string)($institucion['logo'] ?? '');
    if ($logo !== '') $pdf->imageJpeg($logo, 472, 130, 76, 76);
    $pdf->rightText(559, 115, 'UNIDAD EDUCATIVA DE INICIACIÓN', 7.4, true, $colores['azulOscuro']);
    $pdf->rightText(559, 104, 'Y DESARROLLO DEPORTIVO DEL AZUAY', 7.4, true, $colores['azulOscuro']);
    $pdf->rightText(559, 88, 'UNEDID - CUENCA', 7.4, true, $colores['gris']);
    $dibujarPie();

    $nombreArchivo = ($trimestre ? 'reporte_T' . $trimestre : ($esFinal ? 'reporte_final' : 'reporte_anual')) . '_'
        . preg_replace('/[^0-9A-Za-z_-]/', '', (string)($est['cedula'] ?? '')) . '_'
        . preg_replace('/[^0-9-]/', '', $periodo) . '.pdf';
    return ['pdf'=>$pdf, 'filename'=>$nombreArchivo, 'registradas'=>$nNotas, 'pendientes'=>$pendientes];
}
