"""FUTUREO LIVE - Base limpia: solo el fondo de pantalla.

Version 1.2.0
Sin paneles, botones, textos, chat, webcam ni captura de pantalla.
El fondo ocupa el 100 % de la ventana y se ajusta al cambiar su tamano.
F11 activa/desactiva pantalla completa (app.py o ejecucion directa).
"""

from __future__ import annotations

import tkinter as tk

VERSION = "1.2.0"

# Colores de base; aqui podremos personalizar el fondo en el siguiente paso.
COLOR_SUPERIOR = "#070A16"
COLOR_INFERIOR = "#101B32"


def _rgb(color: str) -> tuple[int, int, int]:
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


class FondoFutureo(tk.Canvas):
    """Una unica capa de fondo que llena todo el espacio disponible."""

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(
            parent,
            bg=COLOR_SUPERIOR,
            bd=0,
            highlightthickness=0,
            relief="flat",
        )
        self.bind("<Configure>", self._redibujar)

    def _redibujar(self, event: tk.Event) -> None:
        ancho = max(1, event.width)
        alto = max(1, event.height)
        self.delete("fondo")
        inicio = _rgb(COLOR_SUPERIOR)
        fin = _rgb(COLOR_INFERIOR)
        franjas = min(160, alto)
        for i in range(franjas):
            t = i / max(1, franjas - 1)
            rgb = tuple(round(a + (b - a) * t) for a, b in zip(inicio, fin))
            color = "#{:02x}{:02x}{:02x}".format(*rgb)
            y0 = (i * alto) // franjas
            y1 = ((i + 1) * alto) // franjas + 1
            self.create_rectangle(
                0, y0, ancho + 1, y1,
                fill=color, outline=color, tags=("fondo",),
            )


def render(parent: tk.Misc) -> tk.Widget:
    """Contrato utilizado por el lanzador app.py."""
    return FondoFutureo(parent)


def main() -> None:
    ventana = tk.Tk()
    ventana.title("FUTUREO LIVE")
    ventana.geometry("1366x768")
    ventana.minsize(800, 450)
    ventana.configure(bg=COLOR_SUPERIOR)

    def alternar_pantalla_completa(_evento=None):
        actual = bool(ventana.attributes("-fullscreen"))
        ventana.attributes("-fullscreen", not actual)

    ventana.bind("<F11>", alternar_pantalla_completa)
    ventana.bind("<Escape>", lambda _e: ventana.attributes("-fullscreen", False))
    render(ventana).pack(fill="both", expand=True)
    ventana.mainloop()


if __name__ == "__main__":
    main()
