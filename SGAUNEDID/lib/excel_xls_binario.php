<?php
/**
 * Escritor pequeno de Excel 97-2003 (.xls) BIFF8 dentro de OLE2.
 * Solo usa funciones nativas PHP (pack, iconv, file_put_contents).
 * No utiliza ZIP, ZipArchive, librerias externas ni procesos del servidor.
 * Cada hoja admite 65.536 filas y 256 columnas, limites propios de .xls.
 */
final class SgaExcelXlsBinario
{
    private array $hojas = [];
    private const SECTOR = 512;
    private const ENDOFCHAIN = 0xFFFFFFFE;
    private const FREESECT = 0xFFFFFFFF;
    private const FATSECT = 0xFFFFFFFD;

    /** @param array<int,array<int,array{0:mixed,1?:string}>> $filas */
    public function agregarHoja(string $nombre, array $filas, array $anchos = []): void
    {
        $nombre = trim(str_replace(['\\','/','*','?',':','[',']'], '', $nombre));
        $nombre = iconv_substr($nombre, 0, 31, 'UTF-8') ?: 'Hoja';
        if ($nombre === '') $nombre = 'Hoja';
        if (count($filas) > 65536) {
            throw new RuntimeException('El formato Excel .xls admite un máximo de 65.536 filas por hoja.');
        }
        if (count($this->hojas) >= 200) throw new RuntimeException('Exceso de hojas del libro.');
        foreach ($this->hojas as $hoja) {
            if (strcasecmp($hoja['nombre'], $nombre) === 0) {
                throw new RuntimeException('No se pueden repetir los nombres de hojas.');
            }
        }
        $this->hojas[] = ['nombre'=>$nombre, 'filas'=>$filas, 'anchos'=>$anchos];
    }

    private static function registro(int $tipo, string $datos = ''): string
    {
        if (strlen($datos) > 8224) throw new RuntimeException('Registro BIFF8 demasiado largo.');
        return pack('vv', $tipo, strlen($datos)).$datos;
    }

    private static function unicode(string $texto, int $limite = 4000): array
    {
        $texto = (string)preg_replace('/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/', '', $texto);
        // iconv garantiza que se conservan las tildes y caracteres en Excel.
        $utf16 = iconv('UTF-8', 'UTF-16LE//IGNORE', $texto);
        if ($utf16 === false) $utf16 = iconv('UTF-8', 'UTF-16LE//IGNORE', '');
        if ($utf16 === false) $utf16 = '';
        $cantidad = (int)(strlen($utf16) / 2);
        if ($cantidad > $limite) {
            $utf16 = substr($utf16, 0, $limite * 2);
            // No se debe dejar la primera mitad de un par suplente.
            $ultimo = unpack('v', substr($utf16, -2))[1];
            if ($ultimo >= 0xD800 && $ultimo <= 0xDBFF) $utf16 = substr($utf16, 0, -2);
            $cantidad = (int)(strlen($utf16) / 2);
        }
        return [$cantidad, $utf16];
    }

    private static function bof(int $tipo): string
    {
        return self::registro(0x0809, pack('vvvvVV', 0x0600, $tipo, 0x0DBB, 0x07CC, 0x00000041, 0x00000006));
    }

    private static function fuente(string $nombre, bool $negrita, int $color): string
    {
        [$n,$texto] = self::unicode($nombre, 30);
        $datos = pack('vvvvvCCCCCC', 200, 0, $color, $negrita ? 700 : 400, 0, 0, 0, 0, 0, $n, 1).$texto;
        return self::registro(0x0031, $datos);
    }

    private static function xf(int $fuente, bool $esEstilo, int $formato = 0): string
    {
        $atributos = $esEstilo ? 0xFFF4 : 0;
        $datos = pack('vvvCCCCVVv', $fuente, $formato, $atributos, 0, 0, 0, 0, 0, 0, 0);
        return self::registro(0x00E0, $datos);
    }

    private static function globales(): string
    {
        $b = self::bof(0x0005);
        $b .= self::registro(0x0042, pack('v', 1200)); // Unicode
        $b .= self::registro(0x0022, pack('v', 0)); // Fechas 1900
        // Fuentes 0=normal, 1=negrita, 2=titulo, 3=correcto, 5=error, 6=aviso.
        $b .= self::fuente('Arial', false, 0x7FFF);
        $b .= self::fuente('Arial', true, 0x7FFF);
        $b .= self::fuente('Arial', true, 0x0012);
        $b .= self::fuente('Arial', true, 0x0011);
        // En BIFF8, índice de fuente 4 está reservado y se omite.
        $b .= self::fuente('Arial', true, 0x000A);
        $b .= self::fuente('Arial', true, 0x0013);
        for ($i=0; $i<16; $i++) $b .= self::xf(0, true);
        foreach ([0,1,2,3,5,6] as $fuente) $b .= self::xf($fuente, false);
        $b .= self::xf(0, false, 0x000A); // porcentaje nativo 0.00%
        $b .= self::xf(1, false, 0x000A);
        return $b;
    }

    private static function obtenerXf(string $estilo): int
    {
        return match ($estilo) {
            'titulo', 'cabecera', 'subtitulo' => 18,
            'negrita', 'total' => 17,
            'presente', 'justificado' => 19,
            'ausente' => 20,
            'atraso' => 21,
            'porcentaje' => 22,
            'porcentajeTotal' => 23,
            default => 16,
        };
    }

    private static function hojaBinaria(array $hoja): string
    {
        $filas = $hoja['filas'];
        $maxCols = 0;
        foreach ($filas as $fila) $maxCols = max($maxCols, count($fila));
        if ($maxCols > 256) throw new RuntimeException('El archivo .xls admite 256 columnas por hoja.');

        $b = self::bof(0x0010);
        $b .= self::registro(0x0200, pack('VVvvv', 0, count($filas), 0, $maxCols, 0));
        foreach ($hoja['anchos'] as $col => $ancho) {
            $col = (int)$col;
            if ($col < 0 || $col > 255) continue;
            $ancho = max(5, min(75, (int)$ancho));
            $b .= self::registro(0x007D, pack('vvvvvv', $col, $col, $ancho*256, 16, 0, 0));
        }
        foreach ($filas as $y => $fila) {
            foreach ($fila as $x => $celda) {
                if ($x > 255) throw new RuntimeException('Exceso de columnas para el formato .xls.');
                $valor = $celda[0] ?? null;
                $tipo = $celda[1] ?? 'texto';
                $estilo = $celda[2] ?? 'normal';
                $xf = self::obtenerXf($estilo);
                if ($tipo === 'numero' || $tipo === 'porcentaje') {
                    $n = is_numeric($valor) ? (float)$valor : 0.0;
                    $b .= self::registro(0x0203, pack('vvv', $y, $x, $xf).pack('e', $n));
                } elseif ($valor !== null && (string)$valor !== '') {
                    [$cantidad,$texto] = self::unicode((string)$valor);
                    $b .= self::registro(0x0204, pack('vvvvC', $y, $x, $xf, $cantidad, 1).$texto);
                }
            }
        }
        return $b.self::registro(0x000A);
    }

    private static function entradaDirectorio(string $nombre, int $tipo, int $inicio, int $tamano, int $hijo): string
    {
        [$c,$nombre16] = self::unicode($nombre, 31);
        $entrada = str_repeat("\0", 128);
        $entrada = substr_replace($entrada, substr($nombre16."\0\0", 0, 64), 0, min(strlen($nombre16)+2,64));
        $entrada = substr_replace($entrada, pack('v', min(64, ($c+1)*2)), 64, 2);
        $entrada[66] = chr($tipo);
        $entrada[67] = "\x01";
        $entrada = substr_replace($entrada, pack('V', self::FREESECT), 68, 4);
        $entrada = substr_replace($entrada, pack('V', self::FREESECT), 72, 4);
        $entrada = substr_replace($entrada, pack('V', $hijo), 76, 4);
        $entrada = substr_replace($entrada, pack('V', $inicio), 116, 4);
        $entrada = substr_replace($entrada, pack('V', $tamano), 120, 4);
        $entrada = substr_replace($entrada, pack('V', 0), 124, 4);
        return $entrada;
    }

    /** Devuelve los bytes del archivo Excel 97-2003 real (.xls). */
    public function bytes(): string
    {
        if (!$this->hojas) throw new RuntimeException('El libro no tiene hojas.');
        $sheets = [];
        foreach ($this->hojas as $hoja) $sheets[] = self::hojaBinaria($hoja);

        $cabeceraGlobal = self::globales();
        $boundLen = 0;
        foreach ($this->hojas as $hoja) {
            [$len,] = self::unicode($hoja['nombre'],31);
            $boundLen += 4+8+$len*2;
        }
        $siguiente = strlen($cabeceraGlobal)+$boundLen+4; // EOF global
        $bounds = '';
        foreach ($this->hojas as $i => $hoja) {
            [$len,$utf16] = self::unicode($hoja['nombre'],31);
            $bounds .= self::registro(0x0085, pack('VCCCC', $siguiente, 0, 0, $len, 1).$utf16);
            $siguiente += strlen($sheets[$i]);
        }
        $stream = $cabeceraGlobal.$bounds.self::registro(0x000A).implode('', $sheets);
        $streamSize = max(4096, strlen($stream));
        $streamSectores = (int)ceil($streamSize / self::SECTOR);
        $directorioSector = $streamSectores;
        $fatSectores = 1;
        while (128*$fatSectores < ($streamSectores+1+$fatSectores)) $fatSectores++;
        if ($fatSectores > 109) throw new RuntimeException('Archivo Excel demasiado grande para este exportador.');
        $primeroFAT = $directorioSector+1;

        $cabecera = str_repeat("\0",512);
        $cabecera = substr_replace($cabecera, hex2bin('d0cf11e0a1b11ae1'), 0, 8);
        foreach ([24=>pack('v',0x003E),26=>pack('v',0x0003),28=>pack('v',0xFFFE),30=>pack('v',9),32=>pack('v',6),40=>pack('V',0),44=>pack('V',$fatSectores),48=>pack('V',$directorioSector),52=>pack('V',0),56=>pack('V',4096),60=>pack('V',self::ENDOFCHAIN),64=>pack('V',0),68=>pack('V',self::ENDOFCHAIN),72=>pack('V',0)] as $pos=>$dato) {
            $cabecera = substr_replace($cabecera, $dato, $pos, strlen($dato));
        }
        for ($i=0; $i<109; $i++) {
            $id = $i<$fatSectores ? $primeroFAT+$i : self::FREESECT;
            $cabecera = substr_replace($cabecera, pack('V',$id), 76+4*$i, 4);
        }

        $dir = self::entradaDirectorio('Root Entry', 5, self::ENDOFCHAIN, 0, 1)
            .self::entradaDirectorio('Workbook', 2, 0, $streamSize, self::FREESECT)
            .str_repeat("\0",256);
        $fat = [];
        for ($i=0; $i<$streamSectores; $i++) $fat[] = ($i+1<$streamSectores) ? $i+1 : self::ENDOFCHAIN;
        $fat[] = self::ENDOFCHAIN; // directorio
        for ($i=0; $i<$fatSectores; $i++) $fat[] = self::FATSECT;
        while (count($fat) < 128*$fatSectores) $fat[] = self::FREESECT;
        $tablaFat = '';
        foreach ($fat as $id) $tablaFat .= pack('V',$id);

        return $cabecera.str_pad($stream, $streamSectores*512, "\0").$dir.$tablaFat;
    }

    public function guardarTemporal(): string
    {
        $archivo = tempnam(sys_get_temp_dir(), 'sga_xls_');
        if ($archivo === false) throw new RuntimeException('No se pudo crear el Excel temporal.');
        if (file_put_contents($archivo, $this->bytes(), LOCK_EX) === false) {
            @unlink($archivo);
            throw new RuntimeException('No se pudo escribir el archivo Excel.');
        }
        return $archivo;
    }
}
