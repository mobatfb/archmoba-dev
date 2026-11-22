# MULTIMANDO - Palanca web v5.2 (6 botones)

Proyecto totalmente independiente de KOFMULTI. **PHP es sólo un mando remoto**: el anfitrión Python (a desarrollar) administra P1, P2, cola FIFO, usuarios y 10 minutos por turno sólo cuando exista cola.

## Vista del mando

- **Palanca digital:** arrastrar con ratón o dedo, 8 direcciones y diagonales; flechas del teclado; cruceta física D-pad o analógico izquierdo de mando USB/Bluetooth compatible con Gamepad API.
- **Seis botones con letras, sin figuras**: primera fila **A B C**, segunda fila **D E F**.
- **TECLAS:** botón para configurar localmente cada tecla (direcciones, A-F, START y SELECT), guardado en `localStorage`. Si una tecla ya está asignada, se intercambian las asignaciones; no se envía la configuración a Python.
- **Perfil predeterminado del teclado**: **W = arriba, A = izquierda, S = abajo, D = derecha**; botones **A/B/C = U/I/O** y **D/E/F = J/K/L**. **Enter** = START, **Retroceso / Backspace** = SELECT. El usuario puede cambiarlo mediante TECLAS y restaurar el perfil predeterminado cuando quiera.
- **Mando físico estándar**: analógico izquierdo o D-pad; botones físicos 0-5 corresponden a A-F; 9 START y 8 SELECT. Dependiendo del control físico algunas plataformas pueden exponer otras asignaciones.

## Contrato WebSocket con el nuevo Python

El navegador envía inicialmente `{"type":"hello","name":"Ana"}`. Después, cada pulsación envía, por ejemplo, `{"type":"input","action":"iz","down":true}` y su liberación `{"type":"input","action":"iz","down":false}`.

| Control | Comando | Control | Comando |
|---|---|---|---|
| Arriba | `ar` | A | `ba` |
| Abajo | `ab` | B | `bb` |
| Izquierda | `iz` | C | `bc` |
| Derecha | `de` | D | `bd` |
| START | `start` | E | `be` |
| SELECT | `select` | F | `bf` |

Una diagonal envía dos comandos simultáneos, p. ej. `ar` + `iz`. Los comandos no dependen de la tecla elegida por el usuario. Python debe reconocer **exactamente estas acciones**, no las acciones anteriores de KOF ni de MULTIMANDO v2.

El anfitrión Python emitirá `welcome`, `state`, `notice`, `error` con `slot` (1 o 2), `waiting_position`, `queue`, `timer_remaining`, `timer_running`; la web sólo los representa. **No administra** colas o tiempos y **no usa la API POST**.

## Instalación

1. Hosting HTTPS con **PHP 8.1+, OpenSSL y zlib**.
2. Subir la carpeta `MULTIMANDO` del ZIP privado, incluido `private/FRASE_CIFRADO.php` y `private/palanca.enc`.
3. Abrir `https://tusitio.example/MULTIMANDO/` (`index.php` abre `palanca.php`).
4. Introducir nombre, conectar y aguardar a que el anfitrión Python asigne un control.
5. `sala.php` sólo consulta `https://api.isupol.edu.ec/api/geturlmultimando`, y acepta Cloudflare Quick Tunnel con HTTPS/WSS. Como alternativa está el enlace directo.

`config.php` guarda la API GET y un enlace manual opcional. El cifrado AES-256-GCM + gzip protege el JS almacenado, pero **no puede impedir que alguien inspeccione el JavaScript servido a su navegador**. El archivo `private/FRASE_CIFRADO.php` se incluye **solo en el ZIP privado**, nunca en el repositorio público. Protege `private` en Apache o Nginx.

Se ha probado la interfaz y la lógica de pulsaciones con WebSocket simulado. La interoperabilidad con el futuro anfitrión Python requiere implementarlo y probar con control físico real.

### Migración de perfiles desde v4

La configuración guardada por el usuario en v4 se respeta en sus teclas personalizadas; las teclas que seguían con el valor de fábrica migran a WASD + UIO/JKL. Una vez guardada una modificación nueva, se utiliza `multimando_keys_v5`.

### Parche v5.1: SELECT en retroceso

El valor predeterminado de SELECT pasa de `Digit5` a `Backspace`. Los perfiles anteriores conservan los ajustes personalizados; si SELECT seguía usando la tecla `5` predeterminada, se migra a Backspace automáticamente. Backspace mantiene su comportamiento normal al escribir en un campo de texto. El comando WebSocket para Python no cambia: `select`.

### Parche v5.2: palanca visual con WASD y cruceta física

- Al pulsar W/A/S/D, el círculo central de la palanca digital se desplaza hacia arriba, izquierda, abajo y derecha, aunque no se haya abierto una sala.
- W+A, W+D, S+A y S+D muestran correctamente las diagonales, respetando simultáneamente los comandos que recibe el anfitrión.
- El mismo indicador se mueve con cruceta D-pad y analógico izquierdo de un gamepad reconocido por el navegador.
- Cuando un usuario conecta desde el campo de su nombre, se pasa el foco a la palanca para que WASD funcione sin un clic adicional; las teclas siguen escribiendo normalmente en los campos editables.
- Al soltar, la palanca se recentra. Si el dedo se levanta pero una tecla continúa pulsada, representa la dirección que siga activa.
- **Sólo PHP/control remoto:** Python seguirá administrando jugadores, puestos, cola y tiempos. No se cambiaron los comandos enviados.