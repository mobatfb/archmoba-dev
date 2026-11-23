# MULTIMANDO FUTUREO - ANFITRION v2.3.0 CON PANELES

Actualización exclusivamente de la interfaz Windows del anfitrión.
No se modifica FUTUREO VJOY v0.8.4, el puente 38472, WebSocket 8766,
Cloudflare, las colas FIFO, la duración de turnos ni los comandos web.

## CINCO PESTAÑAS

1. **INICIO:** estado de sala, enlace Cloudflare, API, controles de abrir,
   publicar y cerrar, preview pequeño y resumen de P1-P8.
2. **TRANSMISION:** seleccionar pantalla o ventana del juego, tamaño
   320x180 / 480x270 / 640x360, FPS 1-20, JPEG, modo rápido,
   vista previa de mayor tamaño, iniciar y detener.
   La transmisión sigue siendo pública, sin conectarse como jugador.
3. **JUGADORES Y COLA:** tabla de todos los mandos y jugadores,
   tiempo restante, fila FIFO, expulsar jugador seleccionado,
   botones para pasar turno P1-Pn (solo se ven los habilitados).
4. **CONFIGURACION:** puerto, jugadores 1-8, aplicar capacidad
   en vivo, red local, configurar REMOTO/CONTROLADO,
   identificación de FUTUREO_VJOYn mediante botón 8.
5. **EVENTOS:** registro ampliado, con opciones copiar y limpiar vista.

En la parte superior permanecen indicadores de sala, ocupación de
jugadores, Cloudflare y transmisión. Una barra inferior muestra
siempre el estado general del servidor. La interfaz mantiene la
identidad azul oscuro de MULTIMANDO y acentos celeste institucionales.

## INSTALACIÓN WINDOWS

Conserva **ambos** archivos en la misma carpeta:
- `MULTIMANDO_FUTUREO_Anfitrion_v2_3_0.py`
- `futureo_stream_v22.py`

Ejecutar con Python 3.10+:

```bat
py MULTIMANDO_FUTUREO_Anfitrion_v2_3_0.py
```

El motor FUTUREO VJOY v0.8.4 debe estar abierto para utilizar mandos
Windows. Este ZIP no instala drivers, no incluye binarios EXE de FUTUREO,
ni toca testsigning. Si deseas cambiar entre la versión v2.2.1
y v2.3.0, cierra primero el anfitrión anterior: ambos utilizan
el mismo puerto WebSocket y no deben ejecutarse simultáneamente.

**No necesitas cambiar MULTIMANDO Web:** v2.3.0 solo reorganiza
Tkinter del anfitrión. Si tu web tiene fallos del módulo
`control.php`, son independientes de esta actualización.

## VALIDACIÓN

```bat
py MULTIMANDO_FUTUREO_Anfitrion_v2_3_0.py --selftest
```

El repositorio comprueba sintaxis Python y el `--selftest` del
motor. La prueba gráfica `tests/test_gui_panels_v230.py` monta
las cinco pestañas con Tk bajo un display virtual Xvfb en CI,
verifica que los widgets siguen conectados y prueba la
vista previa sin requerir Windows o driver.

La prueba final con mandos físicos y ventana real se realiza
en Windows. Las pruebas CI no prueban automáticamente los
controles USB del equipo del usuario.
