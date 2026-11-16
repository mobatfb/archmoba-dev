# KOFMULTI — CONTROL v.0.0.3

Interfaz gráfica compacta de **520 × 240 píxeles**, con botones SVG de `assets/`, cruceta, disposición de golpes **A S / Z X** y botón central dinámico.

## Cambios de la versión 0.0.3

- **Nombre del jugador**: campo encima del botón central; el nombre se envía al anfitrión al conectarse.
- **Desconectado**: el botón central dice **CONECTAR**.
- **Conectando**: muestra **CONECTANDO** y consulta `https://api.isupol.edu.ec/api/geturlkof`.
- **Conectado**: se convierte en **START**. Cuando tienes P1 o P2, realiza **COIN + START** en una pulsación.
- **Conectado sin mando**: START permite solicitar un turno si estás en modo espectador. Si estás en cola, conserva tu posición.
- La versión `v.0.0.3` figura **solamente arriba, en la barra de la ventana**. La consola interna muestra exclusivamente mensajes de conexión, turno y avisos.
- El mando no transmite video ni audio.

## Para abrir sin consola negra (Windows)

1. Instala PySide6 una sola vez: `py -m pip install --no-cache-dir PySide6`.
2. Haz doble clic en `KOF_Control.pyw` (recomendado) o en `ABRIR_CONTROL_SIN_CONSOLA.vbs`.

`ABRIR_CONTROL.bat` también funciona, pero el propio CMD del archivo BAT puede verse un instante.

## Conexión

1. En el PC anfitrión, inicia MAME y abre/publica la sala con Cloudflare.
2. Abre `KOF_Control.pyw` en el PC del jugador.
3. Escribe tu nombre y pulsa **CONECTAR**.
4. El control consulta la API GET, convierte el enlace `https://*.trycloudflare.com` a WSS y establece el WebSocket, sin pedir contraseña ni escribir un enlace manualmente.
5. El anfitrión asigna automáticamente P1, P2 o una posición en la cola.

**Seguridad:** solo se aceptan URLs `*.trycloudflare.com` de HTTPS/WSS para evitar seguir destinos arbitrarios publicados en la API sin autenticación. Si cambias a un dominio propio más adelante, también deberás actualizar esta validación.

## Controles

| Tecla local | Acción del jugador | Acción transmitida |
|---|---|---|
| Flechas | Movimiento | UP/DOWN/LEFT/RIGHT |
| A | Puñetazo leve | A |
| S | Puñetazo fuerte | C |
| Z | Patada leve | B |
| X | Patada fuerte | D |
| ENTER / botón central | Moneda + inicio | COIN_START |
| 5 | Moneda manual | COIN |

La traducción final a P1 o P2 sigue siendo responsabilidad exclusiva del anfitrión. El cliente nunca necesita saber las teclas internas de P2.

## Sin caché ni archivos locales

No se utilizan `QSettings`, bases de datos, logs, preferencias guardadas ni caché de disco. La API utiliza política `no-store`, la conexión se mantiene en memoria y los iniciadores evitan `__pycache__` del proyecto. El nombre debe escribirse de nuevo cada vez que abras el programa.

## Verificación pendiente

La conexión con el servicio público y el reconocimiento del joystick por MAME requieren una prueba real en Windows.
