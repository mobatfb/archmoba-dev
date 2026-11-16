# KOFMULTI | Analizador de salud v1.5

## La dirección absoluta de P2 cambia al reiniciar MAME

Cheat Engine identificó la **salud de P2 como Byte en 0x13C1AA58**, pero esa dirección **solo era válida en la ejecución donde se midió**. Al cerrar y volver a abrir MAME, Windows o el emulador pueden colocar los datos en otra posición.

**El programa ya no lee automáticamente 0x13C1AA58 en nuevas sesiones.** Se conserva solo como referencia histórica, sin utilizarla como ubicación real de salud.

## Prueba con el MAME actual

1. Inicia el juego desde el anfitrión y abre `KOF_Analizador_Salud.pyw`.
2. Pulsa **BUSCAR MAME.EXE** para seleccionar el proceso nuevo.
3. En Cheat Engine encuentra el Byte que corresponde a la vida de P2 **en esta ejecución**. Comprueba que disminuye con daño real y no cambia si golpeas al aire.
4. Introduce esa dirección hexadecimal en el campo **Dirección actual de P2 (hex, Byte)** y pulsa **CALIBRAR P2**.
5. El analizador mostrará la lectura en vivo y sus variaciones cada 250 ms. No edita ni congela el Byte.
6. Si cambias nuevamente de MAME, **vuelve a calibrar**: el programa no confía en una dirección anterior. Si el analizador permanece abierto, comprueba periódicamente el PID y borra la dirección anterior al detectar otro proceso.

## Utilizar P2 como referencia para localizar P1

Una vez calibrada P2, selecciona un radio de **64 KiB, 256 KiB, 1 MiB o 4 MiB** y pulsa **BUSCAR SALUD P1 CERCA DE P2**. El programa explora los Bytes cercanos a la dirección actual, sin suponer que P1 está a una distancia determinada.

Para aprender qué dirección podría ser P1:

1. Pulsa **CAPTURAR ANTES**.
2. Vuelve al juego y haz que **P1 reciba un golpe real** mientras P2 conserva su salud.
3. Regresa y pulsa **P1 RECIBIÓ DAÑO**.
4. Repite con una nueva captura y un segundo golpe que baje la salud de P1.
5. Haz otra captura y una acción que NO le quite vida a P1; pulsa **P1 SIN DAÑO**.
6. Compara las filas candidatas, especialmente el campo **Offset desde P2**.

El analizador descarta la muestra si detecta que P2 también cambió de salud. El offset mostrado es solo la diferencia observada **en la sesión actual**, no un puntero estable.

**No hay garantía de que P1 esté cerca de P2**; si la búsqueda dirigida no lo encuentra, usa **EXPLORAR RAM (24 MiB)** o introduce candidatas de Cheat Engine en **SEGUIR DIRECCIONES CE**.

## Cómo lograr una dirección automática entre reinicios

Identificar una única dirección absoluta NO permite reconstruir por sí sola la dirección después de un reinicio. Para eso debemos encontrar una referencia estable y comprobarla a través de varias ejecuciones.

En Cheat Engine, con la barra de P2 identificada, puedes utilizar **Pointer scan for this address**, guardar el resultado y repetir la búsqueda o reescanear el mapa después de reiniciar MAME. Conviene también utilizar **Find out what accesses this address** para investigar qué registros y desplazamientos la referencian.

Cuando encontremos una cadena de punteros estable o un patrón verificable en varias ejecuciones, podremos automatizar su resolución en Python. No conviene asumir ni publicar una dirección nueva sin hacer esas pruebas.

## Garantías

- Todo funciona localmente en el equipo Windows anfitrión.
- El analizador usa `OpenProcess` y `ReadProcessMemory` **solo lectura**.
- No escribe RAM, no guarda archivos de memoria, no transmite video y no altera los contadores del anfitrión.
- ALT izquierdo informa una pulsación, no demuestra que el golpe haya hecho daño.
- La puntuación sigue deshabilitada hasta verificar ganadores, derrotas, PERFECT y resultados al finalizar los tres luchadores.
- Las direcciones ingresadas para P2 **no quedan guardadas entre ejecuciones** para evitar reutilizar datos obsoletos.

Autopruebas con datos simulados (no validan direcciones de la ROM):

```powershell
py -B KOF_Analizador_Salud.py --selftest
```
