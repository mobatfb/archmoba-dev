# KOFMULTI — CONTROL v.0.0.2

Interfaz compacta de **520 × 240 píxeles**, con botones SVG de `assets/` y texto tipo consola **dentro de la ventana del mando**. Al iniciar, lo primero que aparece en ese panel es `v.0.0.2`.

## Ejecutar sin consola negra de Python en Windows

**Recomendado:** haz doble clic en `KOF_Control.pyw`. Se abrirá únicamente el mando gráfico.

**Alternativa:** haz doble clic en `ABRIR_CONTROL_SIN_CONSOLA.vbs`. Este iniciador utiliza `pyw -3 -B` y no muestra la consola.

El archivo `ABRIR_CONTROL.bat` también inicia la aplicación sin una consola de Python persistente, aunque Windows puede mostrar brevemente el CMD del propio BAT. Para evitar incluso ese destello, usa el `.pyw` o el `.vbs`.

## Instalación inicial (solo una vez)

```powershell
py -m pip install --no-cache-dir PySide6
```

Si falta PySide6, el iniciador `.pyw` muestra un aviso de Windows con el problema, sin escribir registros.

## Controles de prueba

- Flechas o cruceta: movimiento.
- **A S** (fila superior) y **Z X** (fila inferior): cuatro acciones.
- ENTER o botón START: acción START. Cuando se implemente la conexión, el anfitrión traducirá la acción en COIN y START según P1/P2.
- Tecla 5: COIN de prueba.

## Privacidad y almacenamiento

- Sin `QSettings`, historial, base de datos, preferencias locales ni registros de aplicación.
- Las pulsaciones y los textos de la consola de la GUI solo viven en memoria.
- Los lanzadores evitan generar archivos `__pycache__` del proyecto.
- Esta versión todavía es un **prototipo local**: no envía pulsaciones a Internet ni se conecta al anfitrión.

Nota: la ventana de consola de esta interfaz es **un panel de texto dentro de la GUI**, no la consola negra externa de Python.
