# FUTUREO / MULTIMANDO - SOLUCION A DIRECCION DERECHA RETENIDA

## Sintoma observado
El log de Python recibe DIRECHA (e1) PRESIONADO y DERECHA (e0)
SOLTADO, o el analogico CENTRADO (0, 0), pero el juego sigue
moviendose a la derecha.

El log de Python verifica la recepcion de la orden, NO verifica
por si solo que Windows aplico la neutralizacion HID.

## Correccion en DOS COMPONENTES

**1. FUTUREO VJOY HOST v0.8.5 (EXE Windows)**

El puente localhost 127.0.0.1:38472 confirma que recibio
un paquete y lo encolo; el envio a HIDMaestro se hace despues
en el hilo de la interfaz.
Antes, los estados identicos no se reenviaban al dispositivo HID.
Si un SubmitState fallaba tras una liberacion, el estado interno
podria quedar neutral aunque el dispositivo fisico permaneciera
activado.

La v0.8.5 refuerza la neutralizacion:
- Reenvia el estado HID al menos cada 450 ms, aunque sea igual.
- Si SubmitState falla, recupera el ultimo estado confirmado y
  vuelve a intentar con el siguiente snapshot del anfitrion.
- Si no llegan datos durante 2 s, neutraliza ejes, botones y D-pad.
- Si la primera orden de neutralizacion falla, sigue intentando.
- Muestra registros de cambios en PROBAR/MONITOR.
- Mantiene el mismo motor HIDMaestro / driver UMDF2 / dispositivos
  FUTUREO_VJOY1..8. No toca otros controladores.

**2. Anfitrion Python v2.4.1**

En JUGADORES Y COLA se agrega el boton:
**LIBERAR MANDOS REMOTOS**.

Al pulsarlo:
- Soltar todos los botones (A/B/X/Y/START/SELECT/L/R).
- Centrar stick analogico X/Y en 0.
- Devolver cruceta D-Pad a neutral.
- Cancelar temporizadores de liberacion corta.
- Avisar al navegador para que libere sus controles locales.
- Conservar jugadores, slots P1..P8, cola FIFO y tiempo restante.
- No intervenir mandos configurados CONTROLADO (USB/Wi-Fi local).
- No alterar la API, WebSocket, Cloudflare ni FULL/DELTA/SMART.

## INSTALACION

1. Cierra el anfitrion Python y FUTUREO VJOY antiguo (EXE).
2. Descomprime el ZIP completo.
3. Ejecuta FUTUREO_VJOY_PORTABLE_HOST_v0_8_5_WIN64.exe.
4. Utiliza INICIAR para activar los mandos y deja FUTUREO abierto.
5. Ejecuta MULTIMANDO_FUTUREO_Anfitrion_v2_4_1.py con Python.
6. Configura mandos, ABRIR SALA, PUBLICAR INTERNET y transmite igual.

Mantener juntos:
- MULTIMANDO_FUTUREO_Anfitrion_v2_4_1.py
- futureo_stream_v30.py
- futureo_stream_v22.py

NO necesitas actualizar MULTIMANDO Web. La web existente
v2.3.0 con FULL/DELTA/SMART sigue funcionando.

## SI CONTINUA EL MOVIMIENTO

1. Con P1 activo, abre Win+R -> joy.cpl.
2. Selecciona FUTUREO_VJOY1 -> Propiedades y deja de tocar el mando.
3. Mira D-Pad y eje X. Deben quedar centrados. Pulsa en el PY
   JUGADORES Y COLA -> LIBERAR MANDOS REMOTOS.
4. Si joy.cpl queda centrado pero el juego sigue a la derecha:
   revisar asignacion de teclado/mando dentro del juego o un
   dispositivo fisico adicional. No es una prueba de fallo de red.
5. Si joy.cpl muestra DERECHA pese a la neutralizacion y con
   FUTUREO v0.8.5, reunir el log del MONITOR FUTUREO y del PY
   para aislar el problema entre el motor HID y el driver.

## VALIDACION
Tests automatizados en GitHub Actions: Python sin hardware, interfaz
Tkinter, compilacion .NET WinForms, paquete HIDMaestro oficial SHA256
verificado y autopruebas del EXE aislado. No sustituye una prueba
de un mando real en Windows.
