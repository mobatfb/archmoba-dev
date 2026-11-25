# SORTEOWEB v1.1.0 — Portada y acceso por correo

Parche incremental sobre v1.0.6, para MariaDB 11.4 (aulaprof_sorteos) y PHP 8.1+ con PDO MySQL, Fileinfo, OpenSSL, sesiones y HTTPS. No reinstala ni borra la base. Los datos existentes de administración y sus contraseñas se conservan.

## Instalación en cPanel

1. Respalda archivos y base. En phpMyAdmin selecciona `aulaprof_sorteos` e importa `database/migrations/1.1.0.sql`. Requiere el parche 1.0.1 ya instalado. No importes nuevamente esquemas antiguos. Añade `users`, `auth_otp`, `auth_attempts`, `mail_logs` y una relación opcional `participants.user_id`.
2. Extrae el ZIP sobre tu instalación v1.0.6, incluyendo los archivos ocultos `.htaccess`. No reemplaza `config.php`, `config.local.php`, ni `storage/`. No mezcles archivos de otras versiones. Elimina el SQL del directorio web tras importarlo o asegúrate de que Apache impide descargarlo.
3. Configura el secreto OTP: copia `auth/config.example.php` como `auth/config.local.php` y escribe en `otp_secret` un valor secreto aleatorio de 64 caracteres hexadecimales. Genera en una terminal privada: `php -r 'echo bin2hex(random_bytes(32)), PHP_EOL;'`. Alternativamente define la variable de entorno `SW_OTP_SECRET`. El ZIP incluye un `auth/config.local.php` inicial generado exclusivamente para esta entrega: consérvalo para esta instalación, no lo subas a GitHub, y cámbialo si compartes el ZIP o creas otra instalación.
4. Copia `mail/config.example.php` como `mail/config.local.php`. Completa `from_email` con una dirección real autorizada de tu dominio y `from_name`. Para cPanel PHP mail, usa `transport => 'mail'`. Si el proveedor exige SMTP, usa `transport => 'smtp'` y completa `smtp_host`, `smtp_port`, `smtp_security` (`starttls` para 587 o `tls` para 465), `smtp_user` y `smtp_password` con los datos del buzón. SMTP necesita TLS con certificado válido y AUTH LOGIN. No publiques estos archivos locales. Comprueba SPF/DKIM/DMARC y entrega a un buzón de prueba; aceptar el mensaje en SMTP no garantiza su recepción.
5. Abre `https://tudominio/sorteos/` para la portada. Para la administración usa `index.php?admin=1` o el enlace del pie. No requiere privacidad del directorio de cPanel. Los accesos administrativos y públicos usan cookies independientes.
6. Activa un sorteo desde el panel para que aparezca en el carrusel. Cada carga elige una foto al azar de cada sorteo activo. Si no hay fotos se usa un marcador, y si no hay activos se muestra una bienvenida.
7. Prueba con un correo propio: pide código, verifica los seis dígitos, comprueba que expira a los cinco minutos y que no se puede reutilizar; registra nombres y apellidos. Después prueba volver a ingresar y revisar la cuenta. Si no llega el correo, revisa las configuraciones del paso 4 y los registros de correo de cPanel.

## Arquitectura

- `index.php`: enrutamiento público o admin. URL administrativas anteriores `?page=...` y `?photo=...` se conservan.
- `core/`: sesiones, acceso PDO, funciones comunes y consultas públicas.
- `admin/`: despacho y servicios administrativos. Se conservan `panel.php`, `modules/` y `assets/` del panel anterior.
- `landing/`: portada, cabecera, carrusel, pie, CSS y JS.
- `auth/`: solicitud, verificación, límites y pantallas del código.
- `mail/`: transportes, plantilla de correo y configuración local.
- `usuario/`: perfil obligatorio y vistas privadas de sorteos, boletos, premios y pagos.
- `database/migrations/`: actualización incremental.

## Seguridad y alcance

El código es uniforme de 000000 a 999999, de un solo uso, válido 300 s desde su generación; se guarda solo su HMAC ligado al desafío y correo. El desafío está vinculado a la sesión que lo solicitó. Se admiten cinco intentos por código, reenvío tras 60 s, tres solicitudes por correo y 20 por IP cada 15 min; también se limitan las verificaciones por correo e IP. Solicitudes rechazadas pueden consumir cupo. La cuenta nace solo después de la verificación; mientras falten nombres o apellidos, se fuerza el perfil. Los registros de correo guardan el digest del destinatario, no el código ni su contenido. Si falla el transporte, el código se invalida. Para mantenimiento, purgar `auth_otp` expirados antiguos, `auth_attempts` antiguos y `mail_logs` conforme a la política de retención del sitio. No guardar códigos ni credenciales en logs.

En Participantes del admin se puede marcar explícitamente «Vincular a la cuenta verificada de este correo» para asociar un boleto al usuario correspondiente (perfil completo). No se asignan boletos antiguos automáticamente por correo: comprueba la titularidad antes de vincular. El usuario solo ve registros asociados a su ID. Los boletos ya vinculados no cambian de titular mediante edición normal. La selección pública de boletos, pasarela de pago y publicación/revelación del ZIP ganador siguen pendientes; el panel público consulta únicamente los registros vinculados. El acceso de administradores conserva su contraseña independiente. No se afirma que el sorteo sea verificable hasta implementar las evidencias.

La aplicación depende de que el servidor Apache proteja archivos internos y secretos con `.htaccess`; comprobar que `auth/config.local.php`, `mail/config.local.php`, `config.php`, `database/migrations/1.1.0.sql`, `storage/` y `admin/service.php` no se puedan acceder por HTTP. En un servidor distinto a Apache configurar reglas equivalentes. Para pruebas locales: `php -S 127.0.0.1:8000`, nunca exponer el servidor de desarrollo a Internet. No hay servidor MariaDB ni PDO MySQL en el entorno de generación; validar SQL y entrega real en tu hosting antes de abrir al público.
