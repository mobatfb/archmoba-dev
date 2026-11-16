# KOFMULTI — CONTROL v.0.0.1

Primera versión visual del control remoto. La ventana es de **520 × 240 píxeles** y usa los SVG de `assets/`.

## Primer mensaje visible
`v.0.0.1` aparece siempre como primera línea de la consola y también en la barra superior.

## Cómo ejecutar en Windows
1. Desde esta carpeta instala la dependencia una sola vez: `py -m pip install --no-cache-dir PySide6`.
2. Ejecuta `ABRIR_CONTROL.bat` o `py -B KOF_Control.py`.

## Controles de prueba
- Flechas o cruceta: movimiento.
- **A S** (arriba) / **Z X** (abajo): cuatro acciones.
- ENTER o botón START: START. El futuro anfitrión se encargará de insertar COIN y START según P1/P2.
- Tecla 5: COIN de prueba (sin botón visual).

## Qué incluye y qué no
- Botones táctiles y teclado con estados de presionar/soltar.
- Log de prueba **solo en memoria**.
- **No** guarda caché, preferencias, usuario ni historial; no utiliza base de datos ni escribe archivos.
- **Todavía no** envía entradas por Internet: se implementará cuando integremos el servidor/anfitrión.

El archivo BAT utiliza `-B` y `PYTHONDONTWRITEBYTECODE=1` para evitar archivos `__pycache__` del código Python.
