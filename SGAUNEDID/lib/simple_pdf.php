<?php
/**
 * Generador PDF ligero sin dependencias de Composer.
 * Mantiene la API original (text, line, rect, addPage, output) y agrega
 * colores, alineación e imágenes JPEG para reportes institucionales.
 */
class SimplePdf {
    private array $pages = [];
    private array $cmd = [];
    private array $images = [];

    public function addPage(): void {
        if ($this->cmd) $this->pages[] = $this->cmd;
        $this->cmd = [];
    }

    private function enc(string $s): string {
        $converted = @iconv('UTF-8', 'Windows-1252//TRANSLIT', $s);
        if ($converted !== false) $s = $converted;
        return str_replace(['\\', '(', ')', "\r", "\n"], ['\\\\', '\\(', '\\)', ' ', ' '], $s);
    }

    private static function rgb(string $hex): string {
        $hex = ltrim($hex, '#');
        if (!preg_match('/^[0-9a-fA-F]{6}$/', $hex)) $hex = '000000';
        $parts = [hexdec(substr($hex, 0, 2)), hexdec(substr($hex, 2, 2)), hexdec(substr($hex, 4, 2))];
        return sprintf('%.4f %.4f %.4f', $parts[0] / 255, $parts[1] / 255, $parts[2] / 255);
    }

    public function text(float $x, float $y, string $text, float $size = 10, bool $bold = false): void {
        $font = $bold ? 'F2' : 'F1';
        $this->cmd[] = sprintf('BT /%s %.2f Tf %.2f %.2f Td (%s) Tj ET', $font, $size, $x, $y, $this->enc($text));
    }

    public function textColor(float $x, float $y, string $text, float $size, bool $bold, string $hex): void {
        $this->cmd[] = 'q ' . self::rgb($hex) . ' rg';
        $this->text($x, $y, $text, $size, $bold);
        $this->cmd[] = 'Q';
    }

    public function textWidth(string $text, float $size = 10, bool $bold = false): float {
        $latin = @iconv('UTF-8', 'Windows-1252//TRANSLIT', $text);
        if ($latin === false) $latin = $text;
        $width = 0.0;
        $widths = [' '=>.278, 'i'=>.222, 'l'=>.222, 'I'=>.278, 'j'=>.222, 'f'=>.278,
            't'=>.278, 'r'=>.333, 's'=>.5, 'm'=>.833, 'w'=>.722, 'W'=>.944,
            'M'=>.833, 'N'=>.722, 'n'=>.556, 'o'=>.556, 'a'=>.556, 'e'=>.556,
            'c'=>.5, 'u'=>.556, 'v'=>.5, 'x'=>.5, 'y'=>.5, 'z'=>.5, 'A'=>.667,
            'B'=>.667, 'C'=>.722, 'D'=>.722, 'E'=>.667, 'F'=>.611, 'G'=>.778,
            'H'=>.722, 'J'=>.5, 'K'=>.667, 'L'=>.556, 'O'=>.778, 'P'=>.667,
            'Q'=>.778, 'R'=>.722, 'S'=>.667, 'T'=>.611, 'U'=>.722, 'V'=>.667,
            'X'=>.667, 'Y'=>.667, 'Z'=>.611, '0'=>.556, '1'=>.556, '2'=>.556,
            '3'=>.556, '4'=>.556, '5'=>.556, '6'=>.556, '7'=>.556, '8'=>.556,
            '9'=>.556, '.'=>.278, ','=>.278, ':'=>.278, ';'=>.278, '-'=>.333,
            '/'=>.278, '('=>.333, ')'=>.333];
        for ($i = 0, $l = strlen($latin); $i < $l; $i++) {
            $width += $widths[$latin[$i]] ?? .57;
        }
        return $width * $size * ($bold ? 1.025 : 1.0);
    }

    public function fitText(string $text, float $maxWidth, float $size, bool $bold = false): string {
        if ($this->textWidth($text, $size, $bold) <= $maxWidth) return $text;
        $chars = preg_split('//u', $text, -1, PREG_SPLIT_NO_EMPTY);
        if (!is_array($chars)) $chars = str_split($text);
        $suffix = '...';
        while ($chars) {
            array_pop($chars);
            $candidate = rtrim(implode('', $chars)) . $suffix;
            if ($this->textWidth($candidate, $size, $bold) <= $maxWidth) return $candidate;
        }
        return $suffix;
    }

    public function wrapText(string $text, float $maxWidth, float $size, bool $bold = false): array {
        $text = trim(preg_replace('/\s+/u', ' ', $text));
        if ($text === '') return [];
        $words = preg_split('/\s+/u', $text) ?: [$text];
        $lines = []; $line = '';
        foreach ($words as $word) {
            $candidate = ($line === '') ? $word : $line . ' ' . $word;
            if ($this->textWidth($candidate, $size, $bold) <= $maxWidth) {
                $line = $candidate;
                continue;
            }
            if ($line !== '') { $lines[] = $line; $line = ''; }
            if ($this->textWidth($word, $size, $bold) <= $maxWidth) {
                $line = $word;
            } else {
                $lines[] = $this->fitText($word, $maxWidth, $size, $bold);
            }
        }
        if ($line !== '') $lines[] = $line;
        return $lines;
    }

    public function centerText(float $centerX, float $y, string $text, float $size = 10, bool $bold = false, string $hex = '000000'): void {
        $x = $centerX - $this->textWidth($text, $size, $bold) / 2;
        $this->textColor($x, $y, $text, $size, $bold, $hex);
    }

    public function rightText(float $rightX, float $y, string $text, float $size = 10, bool $bold = false, string $hex = '000000'): void {
        $this->textColor($rightX - $this->textWidth($text, $size, $bold), $y, $text, $size, $bold, $hex);
    }

    public function line(float $x1, float $y1, float $x2, float $y2, float $w = .5): void {
        $this->cmd[] = sprintf('q 0 0 0 RG %.2f w %.2f %.2f m %.2f %.2f l S Q', $w, $x1, $y1, $x2, $y2);
    }

    public function lineColor(float $x1, float $y1, float $x2, float $y2, float $w, string $hex): void {
        $this->cmd[] = sprintf('q %s RG %.2f w %.2f %.2f m %.2f %.2f l S Q', self::rgb($hex), $w, $x1, $y1, $x2, $y2);
    }

    public function rect(float $x, float $y, float $w, float $h): void {
        $this->cmd[] = sprintf('q 0 0 0 RG %.2f %.2f %.2f %.2f re S Q', $x, $y, $w, $h);
    }

    public function fillRect(float $x, float $y, float $w, float $h, string $fill, ?string $border = null, float $borderWidth = .5): void {
        $q = 'q ' . self::rgb($fill) . ' rg ';
        if ($border !== null) $q .= self::rgb($border) . ' RG ' . sprintf('%.2f w ', $borderWidth);
        $q .= sprintf('%.2f %.2f %.2f %.2f re ', $x, $y, $w, $h);
        $q .= ($border === null ? 'f' : 'B') . ' Q';
        $this->cmd[] = $q;
    }

    public function imageJpeg(string $path, float $x, float $y, float $w, float $h): bool {
        if (!is_file($path) || !is_readable($path)) return false;
        if (!isset($this->images[$path])) {
            $info = @getimagesize($path);
            if (!$info || ($info['mime'] ?? '') !== 'image/jpeg') return false;
            $data = @file_get_contents($path);
            if ($data === false) return false;
            $channels = (int)($info['channels'] ?? 3);
            $color = $channels === 4 ? '/DeviceCMYK' : ($channels === 1 ? '/DeviceGray' : '/DeviceRGB');
            $this->images[$path] = [
                'name' => 'Im' . (count($this->images) + 1),
                'w' => (int)$info[0], 'h' => (int)$info[1],
                'color' => $color, 'data' => $data,
            ];
        }
        $name = $this->images[$path]['name'];
        $this->cmd[] = sprintf('q %.2f 0 0 %.2f %.2f %.2f cm /%s Do Q', $w, $h, $x, $y, $name);
        return true;
    }

    public function build(): string {
        $pages = $this->pages;
        if ($this->cmd || !$pages) $pages[] = $this->cmd;
        $objs = [];
        $objs[1] = '<< /Type /Catalog /Pages 2 0 R >>';
        $objs[3] = '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>';
        $objs[4] = '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>';

        $object = 5; $imageRefs = [];
        foreach ($this->images as $img) {
            $num = $object++;
            $imageRefs[] = '/' . $img['name'] . ' ' . $num . ' 0 R';
            $data = $img['data'];
            $objs[$num] = '<< /Type /XObject /Subtype /Image /Width ' . $img['w']
                . ' /Height ' . $img['h'] . ' /ColorSpace ' . $img['color']
                . ' /BitsPerComponent 8 /Filter /DCTDecode /Length ' . strlen($data)
                . ' >>' . "\nstream\n" . $data . "\nendstream";
        }
        $imagesPart = $imageRefs ? ' /XObject << ' . implode(' ', $imageRefs) . ' >>' : '';
        $kids = [];
        foreach ($pages as $commands) {
            $content = implode("\n", $commands);
            $contentObj = $object++;
            $pageObj = $object++;
            $objs[$contentObj] = '<< /Length ' . strlen($content) . ' >>' . "\nstream\n" . $content . "\nendstream";
            $objs[$pageObj] = '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] '
                . '/Resources << /Font << /F1 3 0 R /F2 4 0 R >>' . $imagesPart . ' >> '
                . '/Contents ' . $contentObj . ' 0 R >>';
            $kids[] = $pageObj . ' 0 R';
        }
        $objs[2] = '<< /Type /Pages /Kids [' . implode(' ', $kids) . '] /Count ' . count($kids) . ' >>';
        ksort($objs, SORT_NUMERIC);
        $pdf = "%PDF-1.4\n%\xE2\xE3\xCF\xD3\n";
        $offsets = [0 => 0];
        $last = max(array_keys($objs));
        for ($i = 1; $i <= $last; $i++) {
            $offsets[$i] = strlen($pdf);
            $pdf .= $i . " 0 obj\n" . $objs[$i] . "\nendobj\n";
        }
        $xref = strlen($pdf);
        $pdf .= "xref\n0 " . ($last + 1) . "\n0000000000 65535 f \n";
        for ($i = 1; $i <= $last; $i++) $pdf .= sprintf('%010d 00000 n ', $offsets[$i]) . "\n";
        $pdf .= 'trailer' . "\n<< /Size " . ($last + 1) . " /Root 1 0 R >>\nstartxref\n" . $xref . "\n%%EOF";
        return $pdf;
    }

    public function output(string $filename, bool $inline = false): never {
        $pdf = $this->build();
        header('Content-Type: application/pdf');
        header('Content-Disposition: ' . ($inline ? 'inline' : 'attachment') . '; filename="' . preg_replace('/[^A-Za-z0-9._-]/', '_', $filename) . '"');
        header('Content-Length: ' . strlen($pdf));
        header('X-Content-Type-Options: nosniff');
        echo $pdf;
        exit;
    }
}
