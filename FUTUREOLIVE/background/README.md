# FUTUREO LIVE — Fondo por capas

La imagen de referencia del usuario se recompuso en **1357 × 628 px** usando recursos independientes.

| Archivo | Función |
|---|---|
| `layer0.svg` | Degradado azul marino de reserva |
| `layers/layer1_base.png` | Base oscura con zonas neutras |
| `layers/layer2_diagonales.png` | Franjas y destellos diagonales |
| `layers/layer3_humo_violeta.png` | Humo violeta de la izquierda |
| `layers/layer4_humo_cian.png` | Humo cian de la derecha |
| `layers/layer5_particulas.png` | Partículas luminosas |
| `layers.json` | Orden, visibilidad, transparencia y animación |
| `index.html` | Visualizador que carga los archivos remotamente desde GitHub |

Al superponer los PNG sin filtros en su resolución nativa, se recompone pixel por pixel la imagen proporcionada. El HTML agrega un brillo animado muy leve en determinadas capas.

## Uso

1. Descarga y abre `index.html` con conexión a Internet. No requiere descargar las capas.
2. Agrega `?debug=1` a la URL para mostrar un inspector que permite ocultar capas individualmente.
3. Para agregar o modificar una capa, sube el nuevo archivo y edita `layers.json`.
4. Incrementa `version` en `layers.json` para que el visor cargue los archivos actualizados sin reutilizar la caché.
5. El visor revisa `layers.json` cada 60 segundos.

**Relación de aspecto:** el original mide 1357 × 628. El modo `fit: "fill"` conserva todo el encuadre en pantallas 16:9 estirando ligeramente la imagen. Puedes cambiar **todas las capas** a `cover` para mantener proporciones con recorte lateral.

El visor es una composición visual, no una herramienta para emitir video. Se puede añadir como fuente de navegador en OBS.
