<?php
declare(strict_types=1);

// First administrator: only available through the server terminal.
if (PHP_SAPI !== 'cli') {
    http_response_code(404);
    exit;
}

function ask(string $label, bool $secret = false): string {
    fwrite(STDERR, $label . ': ');
    $hidden = false;
    if ($secret && PHP_OS_FAMILY !== 'Windows' && function_exists('exec') && function_exists('stream_isatty') && stream_isatty(STDIN)) {
        exec('stty -echo 2>/dev/null', $output, $status);
        $hidden = $status === 0;
    }
    try {
        $line = fgets(STDIN);
        if ($line === false) throw new RuntimeException('Entrada cancelada.');
        return rtrim($line, "\r\n");
    } finally {
        if ($hidden) {
            exec('stty echo 2>/dev/null');
            fwrite(STDERR, PHP_EOL);
        }
    }
}

try {
    $sqlOnly = in_array('--sql', $argv, true);
    if (!$sqlOnly) {
        require __DIR__ . '/app.php';
        if (count_rows("SELECT COUNT(*) FROM ve_users WHERE role='admin'")) {
            fwrite(STDERR, "Ya existe un administrador. No se realizaron cambios.\n");
            exit(0);
        }
    }
    $name = trim(ask('Nombre del administrador'));
    $email = strtolower(trim(ask('Correo electronico')));
    $password = ask('Contrasena (12 a 72 bytes)', true);
    if ($name === '' || strlen($name) > 150 || strlen($email) > 190 || !filter_var($email, FILTER_VALIDATE_EMAIL) || strlen($password) < 12 || strlen($password) > 72) {
        throw new DomainException('Nombre, correo o contrasena invalidos.');
    }
    $hash = password_hash($password, PASSWORD_DEFAULT);
    if ($sqlOnly) {
        $literal = static fn(string $s): string => 'CONVERT(0x' . bin2hex($s) . ' USING utf8mb4)';
        echo "INSERT INTO ve_users(name,email,password_hash,role) SELECT " . $literal($name) . ',' . $literal($email) . ',' . $literal($hash) . ",'admin' WHERE NOT EXISTS (SELECT 1 FROM ve_users WHERE role='admin');" . PHP_EOL;
        exit(0);
    }
    if ((int)query("SELECT GET_LOCK('virtualeduc_install',5)")->fetchColumn() !== 1) throw new RuntimeException('Instalacion ocupada.');
    try {
        if (count_rows("SELECT COUNT(*) FROM ve_users WHERE role='admin'")) throw new DomainException('Ya existe un administrador.');
        query('INSERT INTO ve_users(name,email,password_hash,role) VALUES(?,?,?,?)', [$name, $email, $hash, 'admin']);
    } finally {
        query("SELECT RELEASE_LOCK('virtualeduc_install')");
    }
    fwrite(STDOUT, "Administrador creado. Inicia sesion desde index.php.\n");
} catch (Throwable $e) {
    fwrite(STDERR, "No se pudo completar la instalacion: " . ($e instanceof DomainException ? $e->getMessage() : 'verifica la configuracion, la base de datos y los datos ingresados.') . PHP_EOL);
    exit(1);
}
