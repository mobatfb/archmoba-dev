<?php
declare(strict_types=1);
// FUTUREO STUDIO: one directory per new project; legacy flat FPRJ files remain readable.
function projectName(string $name): bool {
    return strlen($name) <= 160 && preg_match('/\A[A-Za-z0-9_-]+\.fprj\z/i', $name) === 1;
}
function projectFolder(string $root, string $name): string { return $root . '/' . substr($name, 0, -5); }
function projectPath(string $root, string $name): ?string {
    if (!projectName($name) || is_link($root)) return null;
    $folder = projectFolder($root, $name);
    if (is_link($folder)) return null;
    foreach ([$folder . '/' . $name, $root . '/' . $name] as $path) {
        if (is_file($path) && !is_link($path)) return $path;
    }
    return null;
}
function projects(string $root): array {
    $found = [];
    if (is_link($root)) return [];
    foreach (glob($root . '/*', GLOB_NOSORT) ?: [] as $path) {
        if (is_link($path)) continue;
        $name = basename($path) . (is_dir($path) ? '.fprj' : '');
        $file = projectPath($root, $name);
        if ($file !== null) $found[$name] = ['name'=>$name,'mtime'=>(int)filemtime($file)];
    }
    $out = array_values($found);
    usort($out, static function ($a, $b) { return ($b['mtime'] <=> $a['mtime']) ?: strcmp($b['name'], $a['name']); });
    return $out;
}
function createProject(string $root): string {
    if (is_link($root) || (!is_dir($root) && !@mkdir($root,0750,true) && !is_dir($root)) || !is_writable($root)) throw new RuntimeException('La carpeta proyectos no permite escritura.');
    $base = 'sin_nombre_' . date('Ymd');
    for ($i = 1; $i <= 9999; $i++) {
        $stem = $base . ($i === 1 ? '' : '_' . sprintf('%02d',$i));
        $name = $stem . '.fprj';
        $folder = $root . '/' . $stem;
        $legacy = $root . '/' . $name;
        if (file_exists($legacy) || is_link($legacy) || file_exists($folder) || is_link($folder)) continue;
        if (!@mkdir($folder,0750)) {
            if (file_exists($folder) || is_link($folder)) continue;
            throw new RuntimeException('No se pudo crear la carpeta del proyecto.');
        }
        $file = $folder . '/' . $name;
        $assets = $folder . '/assets';
        $data = json_encode(['format'=>'FPRJ','version'=>1,'name'=>$stem,'status'=>'temporal','created_at'=>date(DATE_ATOM),'module'=>null,'content'=>new stdClass()],JSON_PRETTY_PRINT|JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE) . "\n";
        if (!@mkdir($assets,0750) || @file_put_contents($file,$data,LOCK_EX) !== strlen($data)) {
            @unlink($file); @rmdir($assets); @rmdir($folder);
            throw new RuntimeException('No se pudo crear el proyecto completo.');
        }
        return $name;
    }
    throw new RuntimeException('Se alcanzó el límite de nombres para hoy.');
}
