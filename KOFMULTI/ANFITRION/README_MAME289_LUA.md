# KOFMULTI — Salud en vivo con MAME 0.289 y Lua

**Versión mínima del anfitrión: 1.16.8 (experimental, protocolo Lua V3).**

Este modo evita depender de direcciones variables de Cheat Engine en Windows.
MAME lee la memoria de la CPU Neo Geo mediante Lua y remite los valores
observados al anfitrión. **No se escriben cheats, no se alteran barras de vida,
no se otorgan automáticamente victorias ni puntos.**

## Archivos necesarios juntos

- `KOF_Anfitrion.py` (actualizado)
- `KOF_Salud_MAME289.lua` (script del emulador)
- `KOF_MAME_Lua_Bridge.py` (receptor Python)
- Los demás archivos habituales del anfitrión y sus dependencias
  (`websockets`, `vgamepad` y ViGEmBus).
- Un ejecutable de **MAME 0.289 para Windows** y las ROM originales
  que ya utilizas para `kf2k2mp2`.

No copies el ejecutable del MAME nuevo encima del antiguo si quieres mantener
un respaldo funcional: el anfitrión permite seleccionar el ejecutable externo.

## Inicio desde la interfaz del anfitrión

1. Abre `KOF_Anfitrion.py`.
2. Pulsa **Elegir MAME 0.289 + Lua** y selecciona el **mame.exe** correcto;
   el sistema consulta `mame.exe -version` y requiere `0.289`.
3. Pulsa **1. ABRIR SALA**. Esto crea primero los dos joysticks virtuales.
4. Pulsa **3. INICIAR KOF**. El anfitrión inicia MAME con
   `-autoboot_script`, habilita el perfil de mandos y crea el receptor de salud.
5. Verás un estado como **VIDA P1: 102 | VIDA P2: 102**,
   **TIEMPO: 60** y **PERFECT OBSERVADOS: P1=0 | P2=0**.
6. Golpea a cualquiera de los dos personajes: observa que el valor adecuado baja.
   Si el vencedor conserva **102/102** cuando el rival pierde un personaje
   por KO (vida 0 o negativa) o por tiempo, la cuenta de PERFECT aumenta una vez.
7. Verifica los controles con **Ver mandos** y, si hace falta, con
   TAB > Input Assignments en MAME 0.289. No se asegura que el perfil
   histórico de dos mandos sea 100 % compatible sin probarlo en Windows.
8. Para regresar al modo anterior, cierra el juego y pulsa
   **Usar MAME 0.132** antes de INICIAR KOF.

El ZIP original del juego se conserva. Los estados guardados del MAME 0.289
utilizan una carpeta separada: `KOF_ARENA_ESTADOS_0289`.

## ¿Qué hacen los archivos?

`KOF_Salud_MAME289.lua` revisa los valores **cada fotograma de MAME** y publica el estado aproximadamente 10 veces por segundo o inmediatamente al detectar un PERFECT:

| Campo | Dirección interna del juego | Notas |
|---|---|---|
| P1 HP | `0x108239` | Byte, inicialmente 102 |
| P2 HP | `0x108439` | Byte, inicialmente 102 |
| P1 Rounds Lost | `0x10A7E5` | Datos experimentales |
| P2 Rounds Lost | `0x10A80B` | Aumenta cuando se pierde un personaje |
| Tiempo del juego | `0x10A7D2` | BCD: 0x60 = 60, 0x00 = 0 |

El Lua crea un único archivo pequeño de telemetría
`KOF_ARENA_LUA_ESTADO.txt` (en la carpeta del anfitrión cuando se lanza
desde este). Las líneas utilizan el protocolo interno:

```text
KOF_LUA_V3<TAB>secuencia<TAB>hp1<TAB>hp2<TAB>perdidas1<TAB>perdidas2<TAB>ko1<TAB>ko2<TAB>tiempo<TAB>perfect1<TAB>perfect2
```

El archivo se **sobrescribe** cuando hay cambios o aproximadamente cada
0,5 segundos; no acumula partidas ni imágenes. El receptor Python comprueba
rango de Byte, formato y número secuencial para evitar muestras incompletas.

## Cómo se calcula PERFECT

La verificación se realiza **en cada incremento del contador de personajes
perdidos**, no simplemente al presionar un botón. El ganador debe conservar
**102/102 HP**. El motivo puede ser:

- **KO:** el rival llega a 0 HP o tiene un Byte de vida negativo
  (128–255 interpretados como valores con signo).
- **Tiempo:** el reloj llega a `00` y, cuando el contador finalmente
  confirma quién perdió (hasta 500 fotogramas después), ese jugador
  tiene menos de 102 puntos de vida.

Si ambos permanecen en 102 HP cuando el tiempo termina, **no se contabiliza
PERFECT** con esta regla. Cada pérdida da como máximo un PERFECT, aunque
la vida permanezca en 0 durante muchos fotogramas.

**Estos PERFECT son observaciones por personaje vencido, no victorias
oficiales ni puntos de clasificación.** Se muestran en la interfaz del
anfitrión, pero no se invoca `record_game_outcome` ni se modifica la tabla
de Ganados, Perdidos, Perfecto y Puntaje hasta validar el final del combate.

Con las dos capturas originales la regla produce estos resultados:
**P1 = 3 PERFECT (2 KO, 1 por tiempo)** en la primera partida;
**P2 = 1 PERFECT (KO)** en la segunda.

Actualiza **los tres archivos a la vez**: `KOF_Anfitrion.py`,
`KOF_Salud_MAME289.lua` y `KOF_MAME_Lua_Bridge.py`.
La nueva telemetría V3 es recibida correctamente por el puente actualizado,
que mantiene la lectura de los formatos V1 y V2.

---

## Prueba aislada desde PowerShell (sin anfitrión)

Coloca `KOF_Salud_MAME289.lua` junto a tu MAME 0.289.
Desde la carpeta donde está `mame.exe`, ejecuta:

```powershell
.\mame.exe kf2k2mp2 -console -window -autoboot_script .\KOF_Salud_MAME289.lua
```

Luego consulta el archivo en esa misma carpeta:

```powershell
Get-Content .\KOF_ARENA_LUA_ESTADO.txt
```

Deberías ver números separados por tabulaciones, que cambian al golpear.
Si ves `KOF ARENA Lua activo (SOLO LECTURA)` en la consola, el script
se cargó. Si el archivo no existe, comprueba que tienes permisos de
escritura, que la ROM inició y que la versión de MAME es la indicada.

También puedes probar el receptor Python sin MAME:

```powershell
py -B KOF_MAME_Lua_Bridge.py --selftest
```

## Situaciones importantes

- **MAME se abre pero no aparece salud:** comprueba el archivo de telemetría.
  Si no existe, puede que Lua no se haya cargado o no pueda escribir.
- **MAME da error de ROM:** consulta `mame.exe -verifyroms kf2k2mp2`. No todas
  las colecciones antiguas coinciden con los requisitos de MAME moderno.
- **Mando P1/P2 incorrecto:** comprueba la configuración de joystick en MAME
  antes de jugar una partida en red.
- **La salud baja hasta cero:** eso puede indicar que solo cayó un luchador,
  y NO necesariamente que terminó el combate 3 contra 3.
- **Rounds Lost:** los bytes se muestran solo como datos experimentales. Falta
  validar cuándo cambian a lo largo de un combate completo y tras reinicios.

### Siguiente fase

Comprobar, con partidas reales, el estado de selección de personajes,
los tres luchadores agotados, la pantalla de victoria y PERFECT.
Solo entonces deberá llamarse a `record_game_outcome` del anfitrión.

Este modo no modifica puntuaciones actuales, no añade accesos remotos,
y no modifica ni parchea la ROM.
