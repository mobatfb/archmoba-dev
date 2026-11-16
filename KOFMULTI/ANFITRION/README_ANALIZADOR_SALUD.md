# KOFMULTI | Analizador de salud - ALT IZQUIERDO (v1.1)

Este analizador experimental busca direcciones de memoria en `mame.exe` relacionadas con las dos barras de salud. Ahora puede **detectar ALT IZQUIERDO directamente en el teclado del anfitrión**, aunque la ventana del MAME tenga el foco. No necesitas conectar un control remoto para esta prueba.

## Cómo probar ALT izquierdo sin Cheat Engine

1. Abre MAME con `kf2k2mp2` y una pelea activa. Puedes iniciarlo desde el anfitrión.
2. Abre `KOF_Analizador_Salud.pyw` (sin consola negra), o el botón **Analizar salud** del anfitrión.
3. Pulsa **1. BUSCAR MAME.EXE**.
4. Elige **Byte** y pulsa **2. EXPLORAR RAM (24 MiB)**. En la actividad debe aparecer cuántos bloques y megabytes fueron leídos. El proceso puede consumir recursos, por lo que conviene hacer las pruebas con el juego pausado hasta terminar la búsqueda.
5. Vuelve a la **ventana de MAME** y golpea a P2 pulsando **ALT IZQUIERDO** (P1). Deja aproximadamente 2 segundos entre golpes.
6. Regresa al analizador. El contador **ALT IZQUIERDO (P1)** tiene que haber aumentado. Si la memoria contiene valores descendentes, aparecerán como **Salud P2**.

### Si ALT se detecta pero sigues teniendo 0 candidatos

- Comprueba que el golpe alcanzó al rival. El programa no puede saber si el golpe acertó solo por la pulsación.
- Cambia el tipo a **2 Bytes**, pulsa de nuevo **EXPLORAR RAM** y repite.
- Prueba el modo guiado: pulsa **3. CAPTURAR ANTES**, vuelve a MAME, golpea con ALT izquierdo y deja que el analizador compare automáticamente. **No hace falta pulsar P2 RECIBIÓ DAÑO en este modo**.
- Si quieres confirmar el daño **sin depender de la tecla ALT**, pulsa CAPTURAR ANTES, provoca el daño por otro método y pulsa **4. P2 RECIBIÓ DAÑO**. Este botón está destinado a la comparación manual cuando no se activó la captura automática con ALT.
- Si ninguno de esos métodos encuentra la salud, busca direcciones con Cheat Engine y pégalas en **SEGUIR DIRECCIONES CE**. Este método es más preciso y consume menos CPU. Soporta **Byte, 2 Bytes y 4 Bytes**.

### Si ALT izquierdo queda en 0

- Asegúrate de haber pulsado **BUSCAR MAME.EXE** y que el programa muestre un PID conectado.
- La pulsación debe producirse **con MAME en primer plano**. No se cuenta ALT pulsado dentro de Cheat Engine, el escritorio o el analizador.
- Comprueba que es ALT **izquierdo**, no AltGr/ALT derecho.
- Si pulsas ALT muy rápidamente y no lo reconoce, mantenlo una fracción de segundo o repite la prueba: la lectura del teclado es por sondeo local.

## Cómo interpretar los resultados

Las columnas **Bajadas relacionadas** y **Bajadas contradictorias** contabilizan descensos de valores cercanos a la pulsación. **Coincidencia** es solo una puntuación heurística preliminar, **no una probabilidad real de acertar**.

Algunas variables de MAME cambian cuando se ejecutan animaciones, temporizadores o personajes. Repite al menos 4-5 golpes acertados y fallidos antes de confiar en una candidata y verifica en Cheat Engine que el valor realmente acompaña la barra de vida P2, incluso al cambiar de luchador.

**Limitación:** la exploración automática está limitada a 24 MiB repartidos entre regiones legibles de MAME, incluyendo memoria privada y mapeada. Puede omitir el bloque real. Para una dirección de Cheat Engine el seguimiento es más específico. Las direcciones absolutas deben volver a comprobarse al reiniciar MAME.

## Información del proyecto

- Solo lee memoria: `ReadProcessMemory` / `VirtualQueryEx`. No modifica ni congela salud.
- Los resultados no afectan todavía Ganados, Perdidos, Perfecto ni Puntaje.
- No envía imágenes ni captura video; no crea archivos de caché ni logs de diagnóstico.
- Puede seguir escuchando ataques remotos del anfitrión por UDP local `127.0.0.1:38724`, pero la **prueba con ALT izquierdo no necesita esos eventos**.
- Todo lo anterior requiere **Windows**. Se recomienda Python de 64 bits.

Prueba de lógica sin iniciar MAME:

```powershell
py -B KOF_Analizador_Salud.py --selftest
```

Conserva en la misma carpeta `KOF_Anfitrion.py`, `KOF_Analizador_Salud.py` y su iniciador `.pyw`. Las cifras y direcciones reales de salud todavía deben identificarse en tu ROM y validarse mediante una partida.
