# KOFMULTI | Diagnóstico de KO, equipos y tiempo (MAME 0.289)

**Versión v1.5 — detección de PERFECT por KO y por tiempo, sin puntuar ni alterar MAME.**

## Cálculo de PERFECT (regla solicitada)

Cada vez que el contador interno de un jugador aumenta una pérdida (0→1,
1→2 o 2→3), el script determina si su oponente consiguió un PERFECT en
**ese enfrentamiento entre personajes**:

1. El **ganador conserva 102/102** puntos de vida en el momento de la pérdida.
2. **Por KO:** la vida del derrotado es **0** o un Byte interpretado con
   signo como negativo (128–255; en capturas reales: 252–255).
3. **Por tiempo:** el reloj llegó a **00** hace como máximo 500 fotogramas,
   sigue en 00 cuando se registra la derrota, y el derrotado tenía menos
   de 102 de vida (aunque no haya llegado a 0).
4. Un incremento confirmado del contador genera **como máximo un PERFECT**;
   no se vuelve a contar mientras la vida permanezca a 0.
5. Si ambos tienen la vida completa, **no se cuenta PERFECT** por tiempo.
   Tampoco si quien sobrevive conserva menos de 102 puntos.

| Captura ya analizada | P1 | P2 | Detalle |
|---|---:|---:|---|
| Primera partida, pierde equipo P2 | **3 PERFECT** | 0 | KO en fotogramas 4323 y 9733; tiempo en 8373 |
| Segunda partida, pierde equipo P1 | 0 | **1 PERFECT** | KO en fotograma 3895 |

En nuevos registros se generan los eventos `PERFECT_P1_KO`,
`PERFECT_P2_KO`, `PERFECT_P1_TIEMPO` y `PERFECT_P2_TIEMPO`.

**Importante:** son PERFECT calculados **por caída de personaje**, no
PERFECT globales confirmados por la pantalla final de un 3 contra 3.
La aplicación los muestra y los exporta en TSV/CSV, pero **no añade puntos
al ranking del anfitrión**, cuya actualización requiere todavía una
verificación independiente del resultado de la pelea completa.

---

**Versión v1.4 — incorpora análisis de dos sesiones reales (P1 y P2), lectura de HP con signo como hipótesis y marcas locales persistentes.**

## Segunda sesión: P1 pierde tres luchadores (16/11/2026)

Se analizaron **219 eventos válidos** y **1.200 filas de clips** del segundo paquete.

| Fotograma | Situación | HP P1 | HP P2 | Contador P1 | Contador P2 |
|---|---|---:|---:|---:|---:|
| 3895 | P1 pierde primer luchador | 252 | 102 | 0→1 | 0 |
| 5860 | P1 pierde segundo luchador | 254 | 98 | 1→2 | 0 |
| 7765 | P2 pierde su primer luchador | 90 | 253 | 2 | 0→1 |
| 9810 | P1 pierde tercer luchador (posible fin de equipo) | 254 | 92 | 2→3 | 1 |
| 10343 | P1 reinicia contador | 254 | 92 | 3→0 | 1 |

El contador de P1 confirma la secuencia 0→1→2→3→0, simétrica a P2 en la primera sesión. El intervalo entre la tercera pérdida y el reinicio fue **533 fotogramas** en P1 y **534 fotogramas** en P2. Son pruebas sólidas de una secuencia de final, pero **no equivalen a verificar la pantalla de ganador ni a conceder puntos**.

### Posible explicación de los valores 252, 253, 254 y 255

Cuando se interpreta un Byte **con signo**, 252 = -4, 253 = -3, 254 = -2 y 255 = -1. Por tanto, **es probable que la vida baje por debajo de cero en el golpe final** en vez de tratarse de cuatro códigos de KO distintos. Esto sigue siendo una hipótesis; la muerte del personaje se considera mejor respaldada por el **incremento del contador 0→1→2→3** y no por un Byte particular. Las nuevas versiones muestran la conversión tentativa a negativo, pero conservan el valor sin signo para auditoría.

### Nuevos eventos v1.4

- `P1_PERSONAJE_PERDIDO` / `P2_PERSONAJE_PERDIDO` cuando el contador aumenta
- `P1_HP_NEGATIVA_POSIBLE` / `P2_HP_NEGATIVA_POSIBLE` si un Byte de vida pasa de 1–102 a un valor ≥128
- `POSIBLE_FIN_EQUIPO_P1` / `POSIBLE_FIN_EQUIPO_P2` cuando el contador alcanza 3
- `SECUENCIA_P1_3_A_0` / `SECUENCIA_P2_3_A_0` cuando dicho contador vuelve a 0
- `TIEMPO_LLEGO_CERO` y `P1_DERROTA_POR_TIEMPO_POSIBLE` / `P2_DERROTA_POR_TIEMPO_POSIBLE` cuando corresponda

### Marcas del usuario

En la segunda captura el archivo de comandos contiene **FIN_COMBATE**, pero no hay un evento `MARCA_FIN_COMBATE` en el archivo de eventos. Una explicación probable es que MAME no avanzó un nuevo fotograma después de pulsar el botón. Para evitarlo, **desde v1.4 las marcas se guardan inmediatamente también en `KOF_DIAG_MARCAS_LOCALES.tsv`**, con hora de Windows y último fotograma disponible. El Lua añadirá el fotograma de recepción si el juego vuelve a avanzar. La marca local NO debe presentarse como fotograma exacto.

**Siguiente prueba:** observa en pantalla el final de un equipo y marca el resultado, prueba una victoria por tiempo y, cuando sea posible, un PERFECT. Solo entonces evaluar la integración con `record_game_outcome` del anfitrión.


## Resultados reales analizados — 16/11/2026 (v1.1)

Se estudiaron los archivos facilitados por el usuario: **5.332 eventos** y
**2.759 registros de clips** de MAME con `kf2k2mp2`.

| Fotograma | P1 | P2 | Contador P2 | Tiempo (BCD) | Interpretación |
|---|---:|---:|---:|---|---|
| 4323 | 102 | 255 | 0 → 1 | `0x38` = 38 | Primera derrota, estado especial 255 |
| 8019 | 102 | 35 | 1 | `0x00` = 0 | Se agota el tiempo |
| 8373 | 102 | 35 | 1 → 2 | `0x00` = 0 | Segunda derrota, probablemente por tiempo |
| 9733 | 102 | 254 | 2 → 3 | `0x41` = 41 | Tercera derrota; posible fin de equipo P2 |
| 10267 | 102 | 254 | 3 → 0 | `0x41` = 41 | Reinicio del contador tras el combate |

**Conclusión técnica:** un luchador NO siempre pasa a `254`; se observó
`255` en la primera derrota. Una derrota por tiempo puede incrementar el
contador sin pasar por ninguno de esos estados. El indicador más consistente
en este combate es `0x10A80B` pasando de `0` a `1`, a `2` y a `3`.

El reloj usa un formato compatible con **BCD**: `0x60 = 60`,
`0x59 = 59`, `0x41 = 41` y `0x00 = 0`. El subcontador `0x10A7D3`
recorre aproximadamente de 50 a 0 antes de cada cambio de segundo del juego.

**El equipo P1 no registró pérdidas y conservó HP=102** durante los
eventos válidos de combate capturados. Esto NO prueba por sí solo que la
pantalla haya concedido un PERFECT ni autoriza sumar puntos.

Los eventos del arranque en fotogramas 3, 16, 28 y 238 representan
valores transitorios de RAM antes de iniciar la pelea. No se deben contar
como derrotas ni finales por tiempo. El comando `OBSERVACION` figura
en el archivo enviado pero **no aparece ninguna marca `MARCA_...`**
confirmada en los eventos disponibles.

### Mejoras de la versión 1.1

- Detecta entradas a los estados **254 y 255** sin modificar la RAM.
- Registra cada incremento de contadores como `P1_PERSONAJE_PERDIDO`
  o `P2_PERSONAJE_PERDIDO`.
- Reconoce el patrón de **derrota probable por tiempo** si el contador
  aumenta durante los siguientes 500 fotogramas y el reloj está en cero.
- Señala **POSIBLE_FIN_EQUIPO_P1/P2** al observar que el contador pasa
  hasta tres pérdidas, incluso sin 254.
- Ignora cambios espurios de RAM antes de comenzar el juego.
- Reduce el ruido de registros del subcontador y evita guardar varios
  clips idénticos de un mismo fotograma.
- Muestra tiempo BCD y un aviso visual de posible fin de equipo.

**No hay validación suficiente para activar resultados automáticos**
hasta contrastar otras partidas, un equipo P1 que pierda y la pantalla
de resultado correspondiente.

---



El objetivo es **encontrar el instante exacto, medido en fotogramas del emulador, en que un luchador muere, cambia el personaje, termina todo un equipo o se agota el tiempo**. El proyecto todavía NO concede victorias automáticas ni escribe en la RAM.

## Archivos

Debes colocar **juntos**, en una misma carpeta Windows:

- [KOF_Diagnostico_Combate.py](./KOF_Diagnostico_Combate.py) — ventana independiente de captura y análisis
- [KOF_Diagnostico_Combate.lua](./KOF_Diagnostico_Combate.lua) — observador interno de MAME
- El emulador **MAME 0.289** debe estar instalado y `kf2k2mp2` debe poder abrirse correctamente

El diagnóstico NO altera ni reemplaza `KOF_Anfitrion.py` ni su configuración de dos mandos. Para aislar las pruebas, el diagnosticador abre una nueva instancia del emulador; **cierra primero el MAME que tengas abierto**.

## Cómo usar

1. Desde PowerShell, en la carpeta del archivo Python:

   ```powershell
   py -B .\KOF_Diagnostico_Combate.py
   ```

2. Haz clic en **Examinar...** y elige el `mame.exe` de la versión 0.289 que ya usaste para comprobar Lua.
3. En **Carpeta ROM**, elige la carpeta donde está tu ROM (`kf2k2mp2.zip`) o la carpeta principal con una subcarpeta `roms`. Deja el nombre de juego `kf2k2mp2`.
4. Haz clic en **INICIAR MAME CON DIAGNÓSTICO**. El programa cargará automáticamente el script Lua mediante `-autoboot_script`.
5. Juega normalmente y observa vida de P1, vida de P2 y el tiempo.
6. Cuando muera el primer luchador, confirma lo que estás viendo con **KO P1 confirmado** o **KO P2 confirmado** y, cuando aparezca el siguiente, usa **Entró otro P1/P2**. Repite hasta eliminar al último personaje.
7. Pulsa **Equipo P1 eliminado** o **Equipo P2 eliminado** al ver la victoria en pantalla. Si se acaba el tiempo, pulsa **Se agotó el tiempo**.
8. Haz clic en **ABRIR CARPETA DE CAPTURAS** y envíame los archivos TSV resultantes, especialmente `KOF_DIAG_EVENTOS.tsv` y `KOF_DIAG_CLIPS.tsv`. Así podremos comprobar cuáles son las señales reales de fin de equipo y cuál fue su orden.

**Importante:** los botones solo etiquetan lo observado. Si cambias el foco desde MAME a Python y el emulador se pausa, la marca se registrará en el **siguiente fotograma en que MAME avance**. Los eventos automáticos del Lua sí capturan el fotograma exacto de la transición.

## Qué se mide

| Variable | Dirección interna Neo Geo | Interpretación inicial |
|---|---|---|
| Vida P1 | `0x108239` | Byte, valor inicial observado 102 |
| Vida P2 | `0x108439` | Byte, valor inicial observado 102 |
| Estado 254 o 255 | Ambas direcciones de vida | La sesión registró muerte con 255 y 254; no equivale todavía a ganador |
| Contador P1 | `0x10A7E5` | "Rounds Lost" según cheats; por validar con 3 personajes |
| Contador P2 | `0x10A80B` | "Rounds Lost"; por validar |
| Tiempo | `0x10A7D2` | Temporizador del juego; 0x99 podría representar 99 en BCD |
| Tiempo auxiliar | `0x10A7D3` | Posible estado vinculado al tiempo; por validar |

El script emite eventos como `P1_HP_NEGATIVA_POSIBLE`, `P2_HP_NEGATIVA_POSIBLE`, `P1_PERSONAJE_PERDIDO`, `P2_PERSONAJE_PERDIDO`, `P2_DERROTA_POR_TIEMPO_POSIBLE`, `VIDA_P1_DISMINUYE`, `VIDA_P2_DISMINUYE`, `CONTADOR_P1_CAMBIO`, `CONTADOR_P2_CAMBIO`, `TIEMPO_CAMBIO`, `TIEMPO_LLEGO_CERO`, `POSIBLE_FIN_EQUIPO_P1/P2` y `SECUENCIA_P1_3_A_0` / `SECUENCIA_P2_3_A_0`. Los nombres indican hipótesis; no se otorgan puntos.

**Los eventos "POSIBLE_FIN_EQUIPO" son hipótesis** basadas en vida 254 y contador de rondas. NO equivalen todavía a una victoria real. No se guardan puntos ni se altera el ranking.

## Control del tiempo

Hay dos indicadores independientes:

- **TIEMPO DEL JUEGO**: lee el Byte `0x10A7D2` y el Byte auxiliar `0x10A7D3`, registra sus cambios y el instante en que llega a cero; en las pruebas, el primer Byte siguió un formato compatible con BCD.
- **Cronómetro local**: botones **Iniciar/Reanudar**, **Pausar** y **Reiniciar** para comparar el tiempo real transcurrido en Windows con el reloj de MAME.

El cronómetro no detiene, no congela ni modifica el tiempo del videojuego. El valor hexadecimal y la posible interpretación BCD aparecen juntos para evitar confusiones.

## Archivos generados por sesión

En la carpeta `KOF_DIAG_SESIONES\AAAAMMDD_HHMMSS`:

| Archivo | Contenido |
|---|---|
| `KOF_DIAG_ESTADO.tsv` | Estado vivo de ambos jugadores, tiempo y contadores |
| `KOF_DIAG_EVENTOS.tsv` | Cambios y marcas con número de fotograma, valores y hasta 5 ventanas hexadecimales de RAM |
| `KOF_DIAG_CLIPS.tsv` | En un evento crítico, hasta **180 fotogramas anteriores y 120 posteriores** |
| `KOF_DIAG_COMANDO.tsv` | Última marca solicitada por la interfaz |
| `KOF_DIAG_MARCAS_LOCALES.tsv` | Marcas persistidas en el momento de pulsar el botón, incluso si MAME está pausado (desde v1.4) |
| `INSTRUCCIONES.txt` | Versión, ROM y referencias del diagnóstico |

Usa **EXPORTAR EVENTOS CSV** para abrir resultados fácilmente en Excel. Los archivos TSV originales incluyen contexto adicional; no los descartes.

## Comprobación sin abrir MAME

```powershell
py -B .\KOF_Diagnostico_Combate.py --selftest
```

Debe mostrar una salida `OK` sobre el protocolo, el 254, y el cronómetro. Estas son pruebas de datos simulados: no sustituyen las observaciones en una partida real.

## Qué necesito que capturemos

Realiza una partida donde P1 y P2 pierdan al menos un luchador, y una donde uno de los equipos pierda sus tres luchadores. Luego, si puedes, deja agotarse el tiempo en una ronda distinta.

Con esos datos verificaremos, por separado, **KO individual**, **entrada del siguiente personaje**, **fin de combate 3 contra 3** y **final por tiempo**, antes de activar la puntuación automática en KOFMULTI.

Referencia de direcciones internas: [cheats de kf2k2mp2, proyecto FBNeo](https://github.com/finalburnneo/FBNeo-cheats/blob/master/cheats/kf2k2mp2.ini).
