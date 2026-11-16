# KOFMULTI | Diagnóstico de KO, equipos y tiempo (MAME 0.289)

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
| Estado 254 | Ambas direcciones de vida | Usuario observó 254 al morir; se marca como transición compatible con KO |
| Contador P1 | `0x10A7E5` | "Rounds Lost" según cheats; por validar con 3 personajes |
| Contador P2 | `0x10A80B` | "Rounds Lost"; por validar |
| Tiempo | `0x10A7D2` | Temporizador del juego; 0x99 podría representar 99 en BCD |
| Tiempo auxiliar | `0x10A7D3` | Posible estado vinculado al tiempo; por validar |

El script emite eventos con nombres como `P1_ENTRO_254`, `P2_ENTRO_254`, `DANO_P1`, `DANO_P2`, `CONTADOR_P1_CAMBIO`, `CONTADOR_P2_CAMBIO`, `TIEMPO_CAMBIO`, `TIEMPO_LLEGO_CERO` y `POSIBLE_FIN_EQUIPO_P1/P2`.

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
