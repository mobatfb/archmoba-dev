<?php
/** Envio SMTP autenticado con TLS estricto. No requiere Composer. PHP 8.1+ y OpenSSL. */
final class SgaSmtp {
    private $socket = null;
    private int $timeout;

    public function __construct(int $timeout = 10) {
        $this->timeout = max(3, min(20, $timeout));
    }

    private function readReply(): array {
        if (!is_resource($this->socket)) throw new RuntimeException('Conexion SMTP cerrada.');
        $lines = [];
        for ($i = 0; $i < 50; $i++) {
            $line = fgets($this->socket, 2048);
            if (!is_string($line)) throw new RuntimeException('Sin respuesta SMTP.');
            $lines[] = rtrim($line, "\r\n");
            $info = stream_get_meta_data($this->socket);
            if (!empty($info['timed_out'])) throw new RuntimeException('Tiempo SMTP agotado.');
            if (!preg_match('/^([0-9]{3})([ -])/', $line, $matches)) {
                throw new RuntimeException('Respuesta SMTP invalida.');
            }
            if ($matches[2] === ' ') return [(int)$matches[1], implode("\n", $lines)];
        }
        throw new RuntimeException('Respuesta SMTP excesiva.');
    }

    private function writeAll(string $command): void {
        if (!is_resource($this->socket)) throw new RuntimeException('Conexion SMTP cerrada.');
        $length = strlen($command);
        $offset = 0;
        while ($offset < $length) {
            $count = fwrite($this->socket, substr($command, $offset));
            if ($count === false || $count === 0) throw new RuntimeException('No se pudo escribir en SMTP.');
            $offset += $count;
        }
    }

    private function expect(array $codes): string {
        [$status, $reply] = $this->readReply();
        if (!in_array($status, $codes, true)) throw new RuntimeException('El servidor SMTP rechazo la operacion: '.$status);
        return $reply;
    }

    private function cmd(string $command, array $codes): string {
        $this->writeAll($command."\r\n");
        return $this->expect($codes);
    }

    public function send(array $settings, string $recipient, string $subject, string $body): void {
        $host = (string)($settings['host'] ?? '');
        $port = (int)($settings['port'] ?? 0);
        $security = (string)($settings['security'] ?? '');
        $user = (string)($settings['username'] ?? '');
        $pass = (string)($settings['password'] ?? '');
        $from = (string)($settings['from'] ?? '');
        $senderName = (string)($settings['from_name'] ?? 'SGA UNEDID');
        if (!preg_match('/^[a-zA-Z0-9.-]{1,253}$/D', $host)
            || $port < 1 || $port > 65535
            || !in_array($security, ['ssl', 'tls'], true)
            || !filter_var($user, FILTER_VALIDATE_EMAIL)
            || !filter_var($from, FILTER_VALIDATE_EMAIL)
            || !filter_var($recipient, FILTER_VALIDATE_EMAIL)
            || $pass === '' || strcasecmp($from, $user) !== 0) {
            throw new RuntimeException('Configuracion SMTP incompleta o no valida.');
        }
        // Solo se aceptan canales cifrados con verificacion de certificado del servidor.
        $context = stream_context_create(['ssl' => [
            'verify_peer' => true,
            'verify_peer_name' => true,
            'allow_self_signed' => false,
            'peer_name' => $host,
            'SNI_enabled' => true,
        ]]);
        $endpoint = ($security === 'ssl' ? 'ssl://' : 'tcp://').$host.':'.$port;
        $errno = 0; $errstr = '';
        $this->socket = @stream_socket_client($endpoint, $errno, $errstr, $this->timeout, STREAM_CLIENT_CONNECT, $context);
        if (!is_resource($this->socket)) throw new RuntimeException('No se pudo conectar al servidor SMTP.');
        stream_set_timeout($this->socket, $this->timeout);
        try {
            $this->expect([220]);
            $capabilities = $this->cmd('EHLO sga-unedid', [250]);
            if ($security === 'tls') {
                if (stripos($capabilities, 'STARTTLS') === false) {
                    throw new RuntimeException('Servidor SMTP sin STARTTLS.');
                }
                $this->cmd('STARTTLS', [220]);
                if (!@stream_socket_enable_crypto($this->socket, true, STREAM_CRYPTO_METHOD_TLS_CLIENT)) {
                    throw new RuntimeException('No fue posible establecer TLS SMTP.');
                }
                $capabilities = $this->cmd('EHLO sga-unedid', [250]);
            }
            // Preferir AUTH LOGIN cuando esta disponible; credenciales solo via TLS.
            if (preg_match('/(?:^|\n)250[ -]AUTH[^\r\n]*\bLOGIN\b/i', $capabilities)) {
                $this->cmd('AUTH LOGIN', [334]);
                $this->cmd(base64_encode($user), [334]);
                $this->cmd(base64_encode($pass), [235]);
            } elseif (preg_match('/(?:^|\n)250[ -]AUTH[^\r\n]*\bPLAIN\b/i', $capabilities)) {
                $this->cmd('AUTH PLAIN '.base64_encode("\0".$user."\0".$pass), [235]);
            } else {
                throw new RuntimeException('El servidor SMTP no admite autenticacion compatible.');
            }
            $this->cmd('MAIL FROM:<'.$from.'>', [250]);
            $this->cmd('RCPT TO:<'.$recipient.'>', [250, 251]);
            $this->cmd('DATA', [354]);
            $mimeName = '=?UTF-8?B?'.base64_encode($senderName).'?=';
            $mimeSubject = '=?UTF-8?B?'.base64_encode($subject).'?=';
            $headers = [
                'From: '.$mimeName.' <'.$from.'>',
                'To: <'.$recipient.'>',
                'Subject: '.$mimeSubject,
                'Date: '.date('r'),
                'MIME-Version: 1.0',
                'Content-Type: text/plain; charset=UTF-8',
                'Content-Transfer-Encoding: base64',
                'Auto-Submitted: auto-generated',
                'X-Auto-Response-Suppress: All',
            ];
            $message = implode("\r\n", $headers)."\r\n\r\n".chunk_split(base64_encode($body), 76, "\r\n");
            // Proteger el terminador SMTP si alguna linea comienza con punto.
            $message = preg_replace('/(^|\r\n)\./', '$1..', $message);
            $this->writeAll($message."\r\n.\r\n");
            $this->expect([250]);
            $this->cmd('QUIT', [221]);
        } finally {
            if (is_resource($this->socket)) fclose($this->socket);
            $this->socket = null;
        }
    }
}
