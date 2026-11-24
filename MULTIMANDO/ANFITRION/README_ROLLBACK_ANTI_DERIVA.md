# RECUPERACION MULTIMANDO - MOVIMIENTO ANORMAL / DERIVA

Este paquete NO incorpora cambios nuevos en el control HID ni en Python.
Reune las versiones originales previamente publicadas, sin modificarlas.

## PRIORIDAD: RECUPERAR CONTROL NORMAL

Al reportarse comportamiento anormal despues de FUTUREO v0.8.5
y anfitrion v2.4.1, se recomienda volver a las versiones anteriores.
Esta reversion NO es una confirmacion de la causa del defecto.

1. Cierra el juego y el anfitrion MULTIMANDO.
2. Cierra completamente FUTUREO VJOY v0.8.5.
3. Extrae este ZIP en una NUEVA carpeta, no sobre la carpeta anterior.
4. Inicia FUTUREO_VJOY_PORTABLE_HOST_v0_8_4_WIN64.exe.
5. Activa los dispositivos FUTUREO_VJOY1..N.
6. Inicia MULTIMANDO_FUTUREO_Anfitrion_v2_4_0.py.
7. Abre sala y prueba con joy.cpl el centrado del joystick y la cruceta.
8. Si la aplicacion sigue comportandose raro, cierra el anfitrion
   v2.4.0 y usa MULTIMANDO_FUTUREO_Anfitrion_v2_3_1.py como
   respaldo (FULL JPEG STREAM sin DELTA ni SMART en el anfitrion).

## COMPONENTES

- FUTUREO VJOY EXE v0.8.4: puente HID original ya publicado.
- Anfitrion Python v2.4.0: FULL, DELTA y SMART.
- Anfitrion Python v2.3.1: alternativa anterior de FULL JPEG.
- futureo_stream_v30.py: motor de las tres tecnologias.
- futureo_stream_v22.py: capturador del anfitrion anterior.
- Este manual.

La WEB /multimando/ NO se modifica. El visor web v3 funciona
con el anfitrion v2.4.0, y admite FJ22 del anfitrion v2.3.1.

## DIAGNOSTICO DE DERIVA

Si P1 se mueve solo a la derecha, abre Win+R -> joy.cpl y
selecciona FUTUREO_VJOY1 -> Propiedades. Sin tocar controles:
- Si X o D-Pad apunta DERECHA: comprobar puente HID / controlador.
- Si todos los ejes estan neutros: comprobar la asignacion del
  juego, segundo mando conectado o teclado fisico.

Esto NO elimina drivers ni desinstala programas del equipo. El
EXE portable es el motor original v0.8.4. Evita ejecutar en
paralelo el EXE v0.8.4 y v0.8.5.

No se puede certificar la correccion completa hasta probar
con el dispositivo virtual real de Windows.
