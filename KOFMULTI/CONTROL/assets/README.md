# KOFMULTI — Botones del control remoto

Esta carpeta contiene los recursos gráficos vectoriales SVG para montar el mando compacto de KOFMULTI (ventana total **520 × 240 píxeles**). Todos los archivos tienen fondo transparente y se pueden redimensionar sin perder definición.

## Botones y disposición

| Archivo | Uso | Posición |
|---|---|---|
| `dpad_up.svg` | Arriba | Cruceta, izquierda |
| `dpad_down.svg` | Abajo | Cruceta, izquierda |
| `dpad_left.svg` | Izquierda | Cruceta, izquierda |
| `dpad_right.svg` | Derecha | Cruceta, izquierda |
| `dpad_center.svg` | Centro visual | Cruceta, izquierda |
| `btn_a.svg` | Golpe leve, rojo | Fila 1, columna 1 |
| `btn_s.svg` | Golpe fuerte, amarillo | Fila 1, columna 2 |
| `btn_z.svg` | Patada leve, verde | Fila 2, columna 1 |
| `btn_x.svg` | Patada fuerte, azul | Fila 2, columna 2 |
| `btn_start.svg` | START | Centro |

El área superior de la ventana se reserva para el texto de consola; **no se transmite video**.

## Tamaños de los recursos originales

- Cruceta y botones A/S/Z/X: `128 × 128` SVG.
- START: `330 × 108` SVG.

El tamaño visual final será ajustado por la futura interfaz; no utilizar estas dimensiones originales como tamaños de pantalla.

## Comportamiento previsto

Los controles del cliente emitirán acciones neutras `UP`, `DOWN`, `LEFT`, `RIGHT`, `A`, `S`, `Z`, `X` y `START`. El anfitrión decidirá si corresponden a P1 o P2; START activará **COIN y después START** según la lógica acordada.

Nota: estos SVG son archivos de imagen, sin lógica de eventos ni transmisión. Si la interfaz se implementa en Tkinter, será necesario convertirlos a PNG transparentes o utilizar una biblioteca que soporte SVG.
