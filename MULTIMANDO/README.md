# MULTIMANDO · Palanca web v2.0

Control remoto web **independiente de KOFMULTI**. Todo el mando cabe en **una sola pantalla** en computadora, tablet y teléfono móvil (vertical u horizontal), sin panel de administración. El PHP **no gestiona usuarios ni tiempos**: sólo permite conectarse a la sala WebSocket y enviar controles; muestra el estado que publica el anfitrión Python.

## Instalación

1. En un hosting HTTPS con **PHP 8.1+**, OpenSSL y zlib, subir toda la carpeta `MULTIMANDO` del **ZIP privado**, incluidos `private/FRASE_CIFRADO.php` y `private/palanca.enc`.
2. Abrir `https://tusitio.example/MULTIMANDO/` o `.../MULTIMANDO/palanca.php`.
3. Escribir un nombre y pulsar **CONECTAR**. `sala.php` consulta **únicamente por GET** `https://api.isupol.edu.ec/api/geturlmultimando` y valida el enlace HTTPS de `*.trycloudflare.com`.
4. Opcionalmente, desplegar el botón **URL** (🔗) y pegar un enlace HTTPS válido de Cloudflare para conectarse sin depender del GET.
5. Cuando Python asigne P1 o P2, usar la palanca y los botones. Si Python envía un estado de espera, se mostrará el puesto correspondiente.

## Controles del jugador

- **Palanca:** arrastre táctil/mouse con diagonales; teclado con flechas; cruceta o analógico izquierdo de un gamepad estándar conectado al navegador.
- **Acciones:** teclado A/S/Z/X, que envía `A/C/B/D` respectivamente; botones táctiles A/S/Z/X; gamepad estándar A/B/X/Y (se traduce a `A/B/C/D`).
- **START:** Enter o botón START; gamepad estándar Start.
- **SELECT:** tecla 5 o botón SELECT; gamepad estándar Back/Select.
- **CONECTAR/SALIR:** sólo inician o cierran la propia conexión; **no hay botones para administrar turnos, expulsar personas, editar la cola o cambiar los tiempos**.

## Responsabilidades

| Parte | Responsabilidad |
|---|---|
| PHP `palanca.php`/`index.php` | Mostrar exclusivamente la interfaz del control remoto. |
| PHP `sala.php` | Leer, **nunca escribir**, la URL publicada en la API de MULTIMANDO. |
| PHP `control.php` | Descifrar en servidor el JavaScript y entregarlo al navegador. |
| JS `private/palanca.enc` | Enviar `hello` y acciones `input` por WebSocket, leer `welcome`, `state`, `notice`, `error`. |
| Python (pendiente) | Abrir la sala, publicar la URL con `/api/posturlmultimando`, validar nombres, administrar P1/P2, cola FIFO, sesiones y 10 minutos por jugador sólo mientras exista cola. |

El cronómetro mostrado por el navegador **no decide ni aplica vencimientos**: únicamente representa `timer_remaining`/`remaining_seconds` y `timer_running` recibidos del servidor Python. Cuando el anfitrión no envía tiempo, se indica `--:--`, sin inventar un valor. El cliente **no envía** `request`, `yield`, cambios de turnos, ni acciones administrativas.

### Mensajes WebSocket esperados del Python

```json
{"type":"hello","name":"Ana"}
{"type":"welcome","you":1,"room_id":"ABC123"}
{"type":"state","slot":1,"waiting_position":0,"room_id":"ABC123","queue":[{"name":"Beto"}],"timer_remaining":599,"timer_running":true}
{"type":"input","action":"UP","down":true}
{"type":"input","action":"UP","down":false}
```

Acciones admitidas: `UP`, `DOWN`, `LEFT`, `RIGHT`, `A`, `B`, `C`, `D`, `START`, `SELECT`. Python define las asignaciones y su propia lógica de sesión; la estructura anterior es el contrato propuesto para el futuro anfitrión MULTIMANDO, no una promesa de compatibilidad con otro anfitrión.

## Cifrado y seguridad

- El archivo JavaScript está cifrado en reposo como **AES-256-GCM + gzip** en `private/palanca.enc`.
- La frase se encuentra **sólo en el paquete ZIP privado**, bajo `MULTIMANDO/private/FRASE_CIFRADO.php`. **No está en GitHub público**. Mantén ese archivo protegido; Apache bloquea el directorio `private` mediante `.htaccess`. En Nginx configura una denegación equivalente.
- La página puede inspeccionarse en el navegador; el cifrado **no impide por completo copiar el JS que el navegador necesita ejecutar**.
- `config.php` guarda sólo la API GET y un enlace directo opcional. No contiene contraseñas. El navegador nunca usa `/api/posturlmultimando`.
- No publicar el ZIP privado en repositorios públicos.

## Pruebas realizadas

PHP validado sintácticamente; cifrado descifrado y comparado con el JavaScript original; pruebas de diseño sin scroll a 1440×900, 1366×768, 1024×768, 390×844, 360×640, 320×568, 844×390 y 1280×600. Simulación WebSocket: conexión, P1, entradas de teclado/botones, cola y tiempo desde Python. La comunicación con un anfitrión Python real queda pendiente de implementarlo.