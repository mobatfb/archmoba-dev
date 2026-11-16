# KOFMULTI | Diagnóstico de KO, equipos y tiempo (MAME 0.289)

**Versión v1.1 — incorpora análisis de la primera sesión real.**

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

El script emite eventos como `P1_ENTRO_254`, `P2_ENTRO_255`, `P1_PERSONAJE_PERDIDO`, `P2_PERSONAJE_PERDIDO`, `P2_DERROTA_POR_TIEMPO_POSIBLE`, `VIDA_P1_DISMINUYE`, `VIDA_P2_DISMINUYE`, `CONTADOR_P1_CAMBIO`, `CONTADOR_P2_CAMBIO`, `TIEMPO_CAMBIO`, `TIEMPO_LLEGO_CERO` y `POSIBLE_FIN_EQUIPO_P1/P2`. Los nombres indican hipótesis; no se otorgan puntos.

**Los eventos "POSIBLE_FIN_EQUIPO" son hipótesis** basadas en vida 254 y contador de rondas. NO equivalen todavía a una victoria real. No se guardan puntos ni se altera el ranking.

## Control del tiempo

Hay dos indicadores independientes:

- **TIEMPO DEL JUEGO**: lee el Byte `0x10A7D2` y el Byte auxiliar `0x10A7D3`, registra sus cambios y el instante en que llega a cero.
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
