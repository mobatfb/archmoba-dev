# KOFMULTI - Analizador inteligente de salud (fase de aprendizaje)

**Versión anfitrión:** 1.16.6

El archivo `KOF_Analizador_Salud.py` investiga posibles ubicaciones de las barras de salud **P1 y P2** en la memoria del proceso `mame.exe`. Recibe automáticamente los **golpes aceptados** A/B/C/D desde `KOF_Anfitrion.py`.

**Objetivo:** asociar un ataque de P1 con una posible disminución del valor de salud P2 y un ataque de P2 con una posible disminución de salud P1. Las direcciones sugeridas son hipótesis, **no prueba de que un golpe impactó**.

## 1. Archivos necesarios

Coloca juntos:
```text
KOFMULTI/ANFITRION/
  KOF_Anfitrion.py
  KOF_Analizador_Salud.py
  KOF_Analizador_Salud.pyw
  KOF_AutoResultados.py  # opcional, detector OCR antiguo
```
El analizador utiliza únicamente Python estándar, Tkinter y las funciones de Windows `ReadProcessMemory`/`VirtualQueryEx`. Se recomienda **Python de 64 bits**. No necesita pip ni Cheat Engine instalado.

## 2. Cómo aprender con los inputs del anfitrión

1. Ejecuta el anfitrión **v1.16.6** y pulsa **ABRIR SALA** y **INICIAR KOF**.
2. Pulsa **Analizar salud** desde el anfitrión. También puedes hacer doble clic en `KOF_Analizador_Salud.pyw`, que no muestra consola negra.
3. En el analizador pulsa **1. BUSCAR MAME.EXE**.
4. Selecciona **2. EXPLORAR RAM (12 MiB)** para una búsqueda inicial limitada; o pega direcciones de Cheat Engine y pulsa **SEGUIR DIRECCIONES CE**, que es más preciso.
5. Conecta **dos jugadores** y lanza golpes **aislados**, dejando unos **2 segundos** entre ellos, primero de P1 y después de P2. Es importante alternarlos y hacer algunas pulsaciones que fallen para descartar coincidencias falsas.
6. Observa las candidatas **Salud P1** y **Salud P2**. Los contadores significan cuántas veces un valor bajó poco después de un input del atacante opuesto y cuántas veces bajó tras inputs que contradicen esa hipótesis.
7. Copia las direcciones sugeridas y verifícalas con Cheat Engine: deben cambiar en sincronía con los golpes **reales** y, cuando un personaje sale del combate, restaurarse para el siguiente personaje del equipo.

## 3. Uso con Cheat Engine

Cheat Engine muestra direcciones en hexadecimal. Puedes pegar varias direcciones absolutas (una por línea), por ejemplo:
```text
0x00ABCDEF
00ABD120
```
Estos números son **solo ejemplos**, no direcciones conocidas del juego.

Selecciona el ancho **Byte** o **2 Bytes** según el tipo encontrado en Cheat Engine. El analizador acepta direcciones absolutas; expresiones con punteros, `mame.exe+offset` y cadenas de punteros todavía no están implementadas. Las direcciones pueden cambiar al reiniciar el emulador.

La búsqueda automática está acotada a aproximadamente **12 MiB de memoria privada escribible**, priorizando rendimiento. No garantiza incluir la RAM emulada donde se almacenan las barras. El modo de direcciones CE evita esa limitación y consume menos recursos.

## 4. Cómo interpretar la tabla

| Columna | Qué significa |
|---|---|
| Posible barra | P1 si bajó tras ataques de P2; P2 si bajó tras ataques de P1 |
| Dirección RAM | Posible dirección de memoria **de MAME en Windows**, no necesariamente de la ROM |
| Valor actual | Último valor observado al medir |
| Bajadas relacionadas | Coincidencias después de ataques del jugador opuesto |
| Bajadas contradictorias | Cambios después de ataques del mismo jugador |
| Coincidencia | Indicador estadístico **preliminar**, no probabilidad real de que sea salud |

Se descartan secuencias de golpes superpuestos porque no permiten atribuir cambios a un jugador. Si la captura de referencia es antigua, también se descarta.

## 5. Seguridad, rendimiento y límites

- Se emplean **solo** `OpenProcess` con permisos de consulta/lectura, `ReadProcessMemory` y `VirtualQueryEx`; nunca `WriteProcessMemory`.
- Los eventos de botones pasan de anfitrión a analizador mediante **UDP en 127.0.0.1:38724**. No se publican al exterior ni se envía video.
- No se crean archivos de caché, registros ni volcados de memoria; el análisis permanece en RAM.
- Pulsar A/B/C/D no implica impacto: puede haber golpes al aire, defensas, proyectiles, daño simultáneo o transiciones de personajes.
- El algoritmo todavía no puede deducir ganador, derrota o PERFECT solo a partir de un descenso aislado. **No modifica el marcador** del anfitrión.
- Para evitar interferencias, el OCR antiguo de resultados queda desactivado **por defecto** durante el aprendizaje de RAM. Se puede habilitar deliberadamente con `KOF_ENABLE_OCR_RESULTS=1`, pero no se recomienda hasta validarlo.
- Si se cierra y vuelve a abrir MAME, repite la búsqueda porque su PID y las direcciones del proceso pueden cambiar.

## 6. Comprobación de la correlación sin MAME

Desde la carpeta del anfitrión:
```powershell
py -B KOF_Analizador_Salud.py --selftest
```

Ese autocontrol usa datos simulados, no valida direcciones reales. Una vez encuentres dos direcciones candidatas, las validaremos con daño real en KOF 2002 antes de vincularlas a un contador de partidas.
