<?php
/** SGA UNEDID v1.6.25 - Importaciones seguras de catalogos CSV con ; (UTF-8). */
require_once __DIR__ . '/areas_jornadas.php';
if (!function_exists('sgaCatalogoCsvCampos')) {
    function sgaCatalogoCsvCampos(string $tipo): array {
        $mapa = [
            'areas' => ['codigo','nombre','orden','jornadas'],
            'jornadas' => ['codigo','nombre','orden'],
            'aulas' => ['codigo','nivel','nombre','paralelo','jornada_codigo','orden','resultados_cualitativos','evaluacion_cualitativa_parametros'],
            'asignaturas' => ['codigo','nombre','area_codigo','usa_literal_especial','solo_visor_comportamiento','jornadas'],
        ];
        if (!isset($mapa[$tipo])) throw new RuntimeException('Tipo de catalogo no permitido.');
        return $mapa[$tipo];
    }

    function sgaCatalogoCsvDescargarPlantilla(string $tipo): void {
        $campos = sgaCatalogoCsvCampos($tipo);
        header('Content-Type: text/csv; charset=UTF-8');
        header('Content-Disposition: attachment; filename="plantilla_'.$tipo.'_unedid.csv"');
        header('Cache-Control: private, no-store, max-age=0');
        header('X-Content-Type-Options: nosniff');
        $out = fopen('php://output', 'wb');
        fwrite($out, "\xEF\xBB\xBF"); // Excel reconoce UTF-8.
        // Ejemplos ilustrativos: el administrador debe reemplazar o quitar la fila antes de importar.
        // Los codigos de referencia corresponden a las otras plantillas demostrativas.
        $ejemplos = [
            'areas' => ['EJ_AREA_01','ÁREA DE EJEMPLO - REEMPLAZAR','99','MAT|VES'],
            'jornadas' => ['EJ_JOR_01','JORNADA DE EJEMPLO - REEMPLAZAR','99'],
            'aulas' => ['EJ_AULA_01','EGB','PRIMERO','A','EJ_JOR_01','99','1','0'],
            'asignaturas' => ['EJ_ASIG_01','ASIGNATURA DE EJEMPLO - REEMPLAZAR','EJ_AREA_01','0','0','MAT|VES'],
        ];
        fputcsv($out, $campos, ';', '"', '');
        fputcsv($out, $ejemplos[$tipo], ';', '"', '');
        fclose($out);
        exit;
    }

    function sgaCatalogoCsvTexto(string $valor, string $campo, int $max, bool $obligatorio = true): string {
        $valor = trim(preg_replace('/\s+/u', ' ', $valor) ?? $valor);
        if (($obligatorio && $valor === '') || preg_match_all('/./us', $valor) > $max) {
            throw new RuntimeException('Valor no valido para '.$campo.' (maximo '.$max.' caracteres).');
        }
        if (strpos($valor, "\0") !== false || !preg_match('//u', $valor)) throw new RuntimeException('Texto UTF-8 invalido en '.$campo.'.');
        return $valor;
    }

    function sgaCatalogoCsvOrden(string $valor): int {
        $valor = trim($valor);
        if (!preg_match('/^[0-9]{1,4}$/D', $valor) || (int)$valor < 1 || (int)$valor > 9999) {
            throw new RuntimeException('El orden debe ser un entero del 1 al 9999.');
        }
        return (int)$valor;
    }

    function sgaCatalogoCsvCodigo(string $valor, bool $obligatorio = true): ?string {
        $valor = strtoupper(trim($valor));
        if ($valor === '' && !$obligatorio) return null;
        if (!preg_match('/^[A-Z0-9_-]{2,30}$/D', $valor)) throw new RuntimeException('Codigo invalido: usa 2 a 30 letras, numeros, guion o guion bajo.');
        return $valor;
    }

    // En Aulas y Asignaturas, a diferencia de Areas/Jornadas, el codigo
    // del formulario individual admite caracteres UTF-8 (ej. MÓ-PRÁC-EXP).
    function sgaCatalogoCsvCodigoLibre(string $valor): ?string {
        $valor = trim($valor);
        if ($valor === '') return null;
        if (strlen($valor) > 30 || !preg_match('//u', $valor)) {
            throw new RuntimeException('El codigo no puede superar 30 bytes y debe ser UTF-8.');
        }
        return $valor;
    }

    function sgaCatalogoCsvBandera(string $valor, string $campo): int {
        $valor = trim($valor);
        if ($valor === '') return 0;
        if (!in_array($valor, ['0','1'], true)) throw new RuntimeException($campo.' debe ser 0 o 1.');
        return (int)$valor;
    }

    function sgaCatalogoCsvLeer(string $tipo): array {
        $cabeceras = sgaCatalogoCsvCampos($tipo);
        $f = $_FILES['archivo_csv'] ?? null;
        if (!is_array($f) || (int)($f['error'] ?? UPLOAD_ERR_NO_FILE) !== UPLOAD_ERR_OK) {
            throw new RuntimeException('Selecciona un archivo CSV valido antes de importar.');
        }
        if (!is_string($f['tmp_name'] ?? null) || !is_uploaded_file($f['tmp_name'])) throw new RuntimeException('El archivo no proviene de una carga valida.');
        $tam = (int)($f['size'] ?? 0);
        if ($tam <= 0 || $tam > 2 * 1024 * 1024) throw new RuntimeException('El CSV debe tener un tamano maximo de 2 MB.');
        if (strtolower(pathinfo((string)($f['name'] ?? ''), PATHINFO_EXTENSION)) !== 'csv') throw new RuntimeException('Solo se permiten archivos .csv.');
        $h = fopen($f['tmp_name'], 'rb');
        if (!$h) throw new RuntimeException('No se pudo leer el CSV.');
        try {
            $fila = fgetcsv($h, 0, ';', '"', '');
            if (!is_array($fila)) throw new RuntimeException('El CSV esta vacio.');
            $fila[0] = preg_replace('/^\xEF\xBB\xBF/', '', (string)($fila[0] ?? ''));
            $fila = array_map(static fn($x) => strtolower(trim((string)$x)), $fila);
            // Compatibilidad con CSV antiguos, sin cambiar la logica de Areas.
            $aulasSinColumna = $tipo === 'aulas'
                && in_array($fila,[['codigo','nivel','nombre','paralelo','jornada_codigo','orden'],['codigo','nivel','nombre','paralelo','jornada_codigo','orden','resultados_cualitativos']],true);
            if ($fila !== $cabeceras && !$aulasSinColumna) {
                // Soporte existente de plantillas antiguas de Areas.
                if ($tipo === 'asignaturas' && end($fila)==='evaluacion_cualitativa_parametros') {
                    throw new RuntimeException('La modalidad por parámetros ahora se configura en Aulas. Quita la última columna del CSV de asignaturas.');
                } elseif ($tipo === 'asignaturas' && in_array($fila, [
                        ['codigo','nombre','area_codigo','usa_literal_especial','solo_visor_comportamiento'],
                        ['codigo','nombre','area_codigo','usa_literal_especial','solo_visor_comportamiento','jornadas']
                    ], true)) {
                    $cabeceras = $fila;
                } elseif ($tipo === 'areas' && $fila === ['codigo','nombre','orden']) {
                    $cabeceras = ['codigo','nombre','orden'];
                } else {
                    throw new RuntimeException('Cabeceras incorrectas o delimitador distinto de ;. Debe contener: '.implode(';', $cabeceras));
                }
            }
            $cabecerasLectura = $aulasSinColumna ? $fila : $cabeceras;
            $resultado = [];
            $linea = 1;
            while (($campos = fgetcsv($h, 0, ';', '"', '')) !== false) {
                $linea++;
                if (count($campos) === 1 && trim((string)$campos[0]) === '') continue;
                if (count($campos) !== count($cabecerasLectura)) throw new RuntimeException('Fila '.$linea.': numero de columnas incorrecto; utiliza punto y coma (;).');
                $datos = array_combine($cabecerasLectura, array_map(static fn($x) => trim((string)$x), $campos));
                if ($aulasSinColumna) { $datos['resultados_cualitativos'] ??= '0'; $datos['evaluacion_cualitativa_parametros']='0'; }
                foreach ($datos as $x) if (!preg_match('//u', $x) || strpos($x, "\0") !== false) throw new RuntimeException('Fila '.$linea.': texto no valido. Guarda el archivo en UTF-8.');
                $resultado[] = ['linea'=>$linea, 'datos'=>$datos];
                if (count($resultado) > 1500) throw new RuntimeException('Maximo 1500 registros por importacion.');
            }
            if (!$resultado) throw new RuntimeException('La plantilla solo contiene cabeceras. Agrega al menos un registro.');
            return $resultado;
        } finally { fclose($h); }
    }

    function sgaCatalogoCsvImportar(mysqli $conexion, string $tipo): int {
        $registros = sgaCatalogoCsvLeer($tipo);
        // Validar referencias unicas contra los catalogos reales.
        $areas = [];
        $jornadas = [];
        $jornadasArea = [];
        $opcionesAsignaturas = [];
        if ($tipo === 'areas') {
            if (!sgaAreasJornadasInstaladas($conexion)) throw new RuntimeException('Ejecuta SQL_SGA_AREAS_JORNADAS.sql antes de importar areas.');
            $jornadasArea = sgaAreasJornadasOpciones($conexion);
            if (!$jornadasArea) throw new RuntimeException('Tu perfil no tiene jornadas activas autorizadas para crear areas.');
        }
        if ($tipo === 'asignaturas') {
            require_once __DIR__ . '/sga_asignaturas_jornadas.php';
            if (!sgaAreasJornadasInstaladas($conexion) || !sgaAsignaturasJornadasInstaladas($conexion)) {
                throw new RuntimeException('Instala las migraciones de jornadas en Areas y Asignaturas antes de importar.');
            }
            $opcionesAsignaturas=sgaAreasJornadasOpciones($conexion);
            foreach ($conexion->query('SELECT id,codigo,activo,nombre,jornadas_ids FROM areas WHERE archivado_en IS NULL')->fetch_all(MYSQLI_ASSOC) as $a) {
                if (sgaAsignaturasAreaVisible($a)) $areas[strtoupper($a['codigo'])] = $a;
            }
        }
        if ($tipo === 'aulas') {
            foreach ($conexion->query('SELECT id,codigo,activo,nombre FROM jornadas')->fetch_all(MYSQLI_ASSOC) as $j) $jornadas[strtoupper($j['codigo'])] = $j;
        }
        $enTransaccion = false;
        try {
            if (!$conexion->begin_transaction()) throw new RuntimeException('No fue posible abrir la transaccion.');
            $enTransaccion = true;
            foreach ($registros as $fila) {
                $linea = $fila['linea'];
                $d = $fila['datos'];
                try {
                    if ($tipo === 'areas' || $tipo === 'jornadas') {
                        $codigo = sgaCatalogoCsvCodigo($d['codigo']);
                        $nombre = sgaCatalogoCsvTexto($d['nombre'],'nombre', $tipo === 'areas' ? 150 : 100);
                        $orden = sgaCatalogoCsvOrden($d['orden']);
                        if ($tipo === 'areas') {
                            $idsArea = isset($d['jornadas'])
                                ? sgaAreasJornadasLeerCsv($d['jornadas'], $jornadasArea)
                                : sgaAreasJornadasValidarSeleccion(array_map('strval', array_column($jornadasArea,'id')), $jornadasArea);
                            $s = $conexion->prepare('INSERT INTO areas (codigo,nombre,orden,activo) VALUES (?,?,?,1)');
                        } else $s = $conexion->prepare('INSERT INTO jornadas (codigo,nombre,orden,activo) VALUES (?,?,?,1)');
                        if (!$s) throw new RuntimeException('No se pudo preparar el registro.');
                        $s->bind_param('ssi',$codigo,$nombre,$orden);
                        if (!$s->execute()) throw new RuntimeException('Codigo o nombre duplicado.');
                        $id = (int)$conexion->insert_id; $s->close();
                        if ($tipo === 'areas') sgaAreasJornadasGuardar($conexion, $id, $idsArea);
                        registrarAuditoria('CREATE', $tipo === 'areas' ? 'Áreas' : 'Jornadas', $tipo === 'areas' ? 'area' : 'jornada', $id, 'Registro creado mediante importacion CSV.', null, null, ['codigo'=>$codigo,'nombre'=>$nombre,'orden'=>$orden,'activo'=>1] + ($tipo === 'areas' ? ['jornadas'=>$idsArea] : []));
                    } elseif ($tipo === 'aulas') {
                        $codigo = sgaCatalogoCsvCodigoLibre($d['codigo']);
                        $nivel = sgaCatalogoCsvTexto($d['nivel'],'nivel',100);
                        $nombre = sgaCatalogoCsvTexto($d['nombre'],'nombre',100);
                        $paralelo = sgaCatalogoCsvTexto($d['paralelo'],'paralelo',20);
                        $jornadaCodigo = strtoupper(trim($d['jornada_codigo']));
                        $jornada = $jornadas[$jornadaCodigo] ?? null;
                        if (!$jornada || (int)$jornada['activo'] !== 1) throw new RuntimeException('Jornada inexistente o inactiva: '.$jornadaCodigo.'.');
                        $jornadaId = (int)$jornada['id'];
                        if(esSubadmin()){
                            $periodoGestion=(int)(periodoActivo()['id']??0);
                            if(!puedeAccederJornada($jornadaId,$periodoGestion))
                                throw new RuntimeException('La jornada del aula CSV no está asignada a tu perfil.');
                        }
                        $orden = sgaCatalogoCsvOrden($d['orden']);
                        $resultadosCualitativos = sgaCatalogoCsvBandera($d['resultados_cualitativos'],'resultados_cualitativos');
                        $porParametros=sgaCatalogoCsvBandera($d['evaluacion_cualitativa_parametros']??'0','evaluacion_cualitativa_parametros');
                        $s = $conexion->prepare('INSERT INTO aulas (codigo,nivel,nombre,paralelo,jornada_id,orden,resultados_cualitativos,evaluacion_cualitativa_parametros) VALUES (?,?,?,?,?,?,?,?)');
                        if (!$s) throw new RuntimeException('No se pudo preparar el aula.');
                        $s->bind_param('ssssiiii', $codigo, $nivel, $nombre, $paralelo, $jornadaId, $orden, $resultadosCualitativos,$porParametros);
                        if (!$s->execute()) throw new RuntimeException('Aula repetida (codigo o combinacion de nivel, nombre y paralelo).');
                        $id = (int)$conexion->insert_id; $s->close();
                        registrarAuditoria('CREATE','Aulas','aula',$id,'Aula creada mediante importacion CSV.',null,null,['codigo'=>$codigo,'nivel'=>$nivel,'nombre'=>$nombre,'paralelo'=>$paralelo,'jornada_id'=>$jornadaId,'orden'=>$orden,'resultados_cualitativos'=>$resultadosCualitativos,'evaluacion_cualitativa_parametros'=>$porParametros]);
                    } elseif ($tipo === 'asignaturas') {
                        $codigo = sgaCatalogoCsvCodigoLibre($d['codigo']);
                        $nombre = sgaCatalogoCsvTexto($d['nombre'],'nombre',150);
                        $areaCodigo = strtoupper(trim($d['area_codigo']));
                        $area = $areas[$areaCodigo] ?? null;
                        if (!$area || (int)$area['activo'] !== 1) throw new RuntimeException('Area inexistente, inactiva o fuera de la jornada visible: '.$areaCodigo.'.');
                        $areaId = (int)$area['id'];
                        $especial = sgaCatalogoCsvBandera($d['usa_literal_especial'],'usa_literal_especial');
                        $visor = sgaCatalogoCsvBandera($d['solo_visor_comportamiento'],'solo_visor_comportamiento');

                        $asigPermitidas=sgaAsignaturasJornadasOpciones($area,$opcionesAsignaturas);
                        $idsAsig=isset($d['jornadas'])
                          ? sgaAsignaturasValidarJornadas(sgaAreasJornadasLeerCsv($d['jornadas'],$opcionesAsignaturas),$area,$opcionesAsignaturas)
                          : sgaAsignaturasValidarJornadas(array_map('strval',array_column($asigPermitidas,'id')),$area,$opcionesAsignaturas);
                        $s = $conexion->prepare('INSERT INTO asignaturas (codigo,nombre,area_id,usa_literal_especial,solo_visor_comportamiento) VALUES (?,?,?,?,?)');
                        if (!$s) throw new RuntimeException('No se pudo preparar la asignatura.');
                        $s->bind_param('ssiii',$codigo,$nombre,$areaId,$especial,$visor);
                        if (!$s->execute()) throw new RuntimeException('Asignatura repetida (codigo o nombre).');
                        $id = (int)$conexion->insert_id; $s->close();
                        sgaAsignaturasJornadasGuardar($conexion,$id,$idsAsig);
                        registrarAuditoria('CREATE','Asignaturas','asignatura',$id,'Asignatura creada mediante importacion CSV.',null,null,['codigo'=>$codigo,'nombre'=>$nombre,'area_id'=>$areaId,'usa_literal_especial'=>$especial,'solo_visor_comportamiento'=>$visor,'jornadas'=>$idsAsig]);
                    }
                } catch (Throwable $e) {
                    $detalle = (int)($e->getCode() ?? 0) === 1062 ? 'Codigo o nombre ya existente.' : $e->getMessage();
                    throw new RuntimeException('Fila '.$linea.': '.$detalle, 0, $e);
                }
            }
            if (!$conexion->commit()) throw new RuntimeException('No fue posible confirmar el lote.');
            $enTransaccion = false;
            return count($registros);
        } catch (Throwable $e) {
            if ($enTransaccion) $conexion->rollback();
            throw $e;
        }
    }
}
