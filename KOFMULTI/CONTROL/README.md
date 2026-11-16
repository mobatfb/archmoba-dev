# KOFMULTI — CONTROL v.0.0.4

Interfaz compacta de **520 × 240 píxeles** para los jugadores, con el nombre encima del botón central y controles de teclado y tactiles ASZX.

## Nombre recordado localmente

- La primera vez que escribes tu nombre, se guarda automáticamente al terminar de editarlo, al pulsar **CONECTAR** o al cerrar la ventana.
- En las próximas ejecuciones aparece ya rellenado en el campo **Tu nombre**.
- Se guarda **solo el nombre** en `nombre_jugador.txt` dentro del directorio de caché local de la cuenta de usuario (resuelto por Qt con `QStandardPaths.CacheLocation`).
- Puedes modificarlo: el nuevo nombre sustituye al anterior.
- Si eliminas la caché del sistema, la próxima vez aparecerá vacío.
- No se guardan contraseñas, enlaces, teclas, sesiones, estadísticas ni logs. No se necesita ningún archivo junto al ejecutable para recordar el nombre.

## Conexión

1. Abre y publica la sala en el anfitrión.
2. Ejecuta **`KOF_Control.pyw`** (no abre consola negra) o **`ABRIR_CONTROL_SIN_CONSOLA.vbs`**.
3. Escribe o confirma tu nombre y pulsa **CONECTAR**.
4. El programa consulta `https://api.isupol.edu.ec/api/geturlkof` y abre un WebSocket seguro a la sala anunciada de Cloudflare.
5. Cuando el anfitrión confirme la conexión, CONECTAR se convierte en **START**.
6. El anfitrión te asigna P1, P2 o la lista de espera.

La versión **v.0.0.4** se presenta solo en la barra superior; no se repite en los mensajes de la consola interna.

## Controles

| Entrada local | Acción |
|---|---|
| Flechas | Movimiento |
| A | Puñetazo leve |
| S | Puñetazo fuerte |
| Z | Patada leve |
| X | Patada fuerte |
| ENTER / START | COIN + START si tienes P1 o P2 |
| 5 | COIN manual |

El control remoto usa las mismas teclas para P1 y P2; el anfitrión realiza la conversión. No hay transmisión de video ni audio.

## Requisitos

Instala PySide6 una vez con `py -m pip install --no-cache-dir PySide6`; luego abre `KOF_Control.pyw`.

El cliente no almacena caché de red, archivos de configuración ni historial; **la única excepción es el nombre del jugador** solicitado para autocompletarlo al iniciar.
