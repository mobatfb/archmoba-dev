# KOFMULTI | Analizador de salud v1.3 — Byte de P2 identificado

**Cambio importante:** las direcciones sugeridas por pulsaciones de ALT izquierdo no resultaron ser la salud real. La versión v1.2 descarta ese método como evidencia suficiente. Ya NO muestra candidatos únicamente porque un valor disminuyó después de pulsar ALT.

El analizador sigue siendo una herramienta de aprendizaje local y **no cambia el marcador del anfitrión**.

## Dirección de salud P2 registrada

El usuario identificó con Cheat Engine la dirección absoluta **`0x13C1AA58`**, tipo **Byte (1 byte)**, correspondiente a la vida de **P2** en su sesión de `mame.exe`.

- El analizador guarda esta dirección en el código, **sin modificar el contenido de la memoria**.
- Al pulsar **BUSCAR MAME.EXE**, lee automáticamente ese Byte aproximadamente cada 250 milisegundos.
- Arriba aparece **VIDA P2 | 0x13C1AA58 | Byte | valor ...** y los cambios positivos o negativos.
- El campo de direcciones de Cheat Engine comienza rellenado con esa dirección, por si deseas seguirla mediante el analizador.
- **El valor máximo de vida aún es desconocido**. Byte define el tipo de almacenamiento, no que 255 sea la vida máxima.
- Esta es una dirección absoluta de Windows; puede cambiar tras reiniciar el emulador. Hay que comprobarla en una partida nueva.
- **P1 todavía está pendiente**. Tener únicamente la salud de P2 no permite deducir automáticamente victorias, derrotas ni PERFECT ni identificar la eliminación del equipo completo.

Prueba rápida: abre el juego, pulsa **BUSCAR MAME.EXE**, golpea a P2 con Alt izquierdo y observa si el valor baja. Haz también un golpe al aire y confirma que permanece estable. Si aparece **no legible**, verifica la dirección en Cheat Engine después de reiniciar MAME.

## Cómo utilizarlo en Windows

1. Abre `KOF_Anfitrion.py`, pulsa **ABRIR SALA**, luego **INICIAR KOF**; abre el analizador desde **Analizar salud** o desde `KOF_Analizador_Salud.pyw`.
2. Selecciona **1. BUSCAR MAME.EXE** y el tipo **Byte**; después pulsa **2. EXPLORAR RAM (24 MiB)**. Si no se encuentra nada repetiremos con **2 Bytes** y, cuando haga falta, con direcciones de Cheat Engine.
3. Coloca a los personajes frente a frente con la vida de P2 relativamente alta. En el analizador pulsa **3. CAPTURAR ANTES**.
4. Vuelve a la ventana de MAME y presiona **ALT IZQUIERDO** para golpear a P2. Observa la barra de vida.
5. Regresa al analizador: si **la salud de P2 realmente bajó**, pulsa **4. P2 RECIBIÓ DAÑO**. Si el golpe **falló o fue bloqueado sin pérdida de salud**, pulsa **4. P2 SIN DAÑO**.
6. Repite **CAPTURAR ANTES → un solo golpe → confirmar** en cada intento. Para ver candidatos, se necesitan como mínimo **2 muestras etiquetadas como daño y 1 como sin daño**.
7. Para identificar la salud de P1, repite las capturas cuando P2 ataque y selecciona los botones P1 RECIBIÓ DAÑO / P1 SIN DAÑO.

**Importante:** pulsar ALT izquierdo únicamente incrementa el contador de pulsaciones; **no confirma impactos ni genera puntuaciones**. Debes usar siempre un botón de confirmación para guardar la muestra.

## Qué significa la tabla

| Columna | Significado |
|---|---|
| Posible barra | P1 o P2 que habría recibido daño |
| Dirección RAM | Dirección candidata; puede cambiar cuando reinicias MAME |
| Valor actual | Último valor registrado |
| Daño confirmado | Veces que bajó en una muestra que tú marcaste con daño |
| Ruido / sin daño | Veces que cambió durante pruebas sin daño o tras el otro jugador |
| Calidad orientativa | Índice de contraste, **no** probabilidad científica |

Las ubicaciones que también cambian cuando fallas un golpe o te mueves reciben penalización. Si confirmaste que una dirección es falsa, selecciónala en la tabla y pulsa **Descartar seleccionado**. El descarte se mantiene en memoria hasta reiniciar el aprendizaje.

Las antiguas candidatas `0x0B05EA4D`, `0x0B05EA45` y `0x0B05E04D` fueron descartadas. La dirección registrada de P2 es `0x13C1AA58` (Byte).

## Si sigues sin encontrar la salud

- El explorador automático solo muestrea **24 MiB** del proceso Windows; puede no cubrir la RAM emulada real.
- La alternativa más precisa es buscar en **Cheat Engine**: tipo Byte o 2 Bytes, **Unknown initial value**; tras un daño real, **Decreased value**; cuando el golpe no causa daño, **Unchanged value**; al cambiar de personaje, comprueba si se restablece. Repite hasta encontrar pocas candidatas.
- Pega únicamente las **direcciones absolutas** obtenidas en Cheat Engine, en hexadecimal, una por línea, y pulsa **SEGUIR DIRECCIONES CE**. Admite Byte / 2 Bytes / 4 Bytes (enteros). Las expresiones `mame.exe+offset` o cadenas de punteros todavía no se resuelven.
- El juego puede reflejar la salud en campos diferentes del valor numérico de una barra, y también puede tener duplicados.

## Garantías y límites

El analizador utiliza `ReadProcessMemory` y `VirtualQueryEx`: no escribe ni congela memoria, no guarda capturas, no transmite video y no modifica el juego. La detección de ALT izquierdo exige que `mame.exe` esté en primer plano, pero la confirmación se realiza desde la ventana del analizador.

**El programa no puede garantizar una dirección correcta solo a partir de estas comparaciones.** Antes de automatizar Ganados, Perdidos y Perfecto hay que verificar que las direcciones candidatas describen la salud real de cada equipo durante cambios de luchador, rondas y reinicios.

Para verificar la lógica de aprendizaje con datos simulados:

```powershell
py -B KOF_Analizador_Salud.py --selftest
```

Archivos en `KOFMULTI/ANFITRION`: `KOF_Analizador_Salud.py` y `KOF_Analizador_Salud.pyw`. El anfitrión v1.16.6 sigue siendo compatible con ellos sin modificaciones adicionales.
