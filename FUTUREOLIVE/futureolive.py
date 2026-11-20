"""FUTUREO LIVE: fondo animado limpio y adaptable (sin paneles).

El fondo web original esta en assets/fondo.html para navegadores y OBS.
Tkinter no ejecuta CSS: esta clase dibuja una version animada nativa
con la misma paleta, sin dependencias adicionales.
"""
from __future__ import annotations

import math
import random
import tkinter as tk

VERSION = "1.3.0"
COLOR_SUPERIOR = "#050919"
COLOR_INFERIOR = "#0C1830"


def _rgb(color: str) -> tuple[int, int, int]:
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


def _mezcla(a: str, b: str, factor: float) -> str:
    izq, der = _rgb(a), _rgb(b)
    valores = (round(x + (y - x) * factor) for x, y in zip(izq, der))
    return "#{:02x}{:02x}{:02x}".format(*valores)


class FondoFutureo(tk.Canvas):
    """Fondo de toda la ventana, con animacion ligera a ~15 FPS."""

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent, bg=COLOR_SUPERIOR, bd=0, highlightthickness=0)
        self._time = 0.0
        self._job: str | None = None
        self._points: list[tuple[int, float, float, float, float]] = []
        self._arcos: list[tuple[int, float]] = []
        self._rayos: list[tuple[int, float, float]] = []
        self.bind("<Configure>", self._redibujar)
        self.bind("<Destroy>", self._limpiar, add="+")
        self._job = self.after(66, self._animar)

    def _halo(self, x: float, y: float, radius: float, shade: str, base: str) -> None:
        # Los contornos escalonados simulan brillo sin transparencias externas.
        for i in range(19, 0, -1):
            radio = radius * i / 19
            fuerza = 0.025 + (1 - i / 19) * 0.085
            self.create_oval(
                x - radio, y - radio, x + radio, y + radio,
                outline=_mezcla(base, shade, fuerza), width=2,
            )

    def _redibujar(self, event: tk.Event) -> None:
        w, h = int(event.width), int(event.height)
        if w < 10 or h < 10:
            return
        self.delete("all")
        self._points.clear()
        self._arcos.clear()
        self._rayos.clear()
        bandas = min(140, h)
        for i in range(bandas):
            t = i / max(1, bandas - 1)
            y0 = i * h // bandas
            y1 = (i + 1) * h // bandas + 2
            color = _mezcla(COLOR_SUPERIOR, COLOR_INFERIOR, t)
            self.create_rectangle(0, y0, w + 2, y1, outline=color, fill=color)

        self._halo(w * 1.03, h * 0.01, max(w, h) * 0.49, "#11BDFF", "#091329")
        self._halo(-w * 0.04, h * 1.0, max(w, h) * 0.46, "#8349E6", "#0A1028")
        for x in range(0, w, 82):
            self.create_line(x, 0, x, h, fill="#10223A", width=1)
        for y in range(0, h, 82):
            self.create_line(0, y, w, y, fill="#10223A", width=1)

        # Orbitas suaves en las esquinas, centro libre para el gameplay futuro.
        arco1 = self.create_arc(
            w * .58, -h * .68, w * 1.35, h * .66,
            start=30, extent=135, style=tk.ARC, outline="#1373B5", width=2,
        )
        arco2 = self.create_arc(
            -w * .31, h * .40, w * .39, h * 1.63,
            start=210, extent=118, style=tk.ARC, outline="#5939A9", width=2,
        )
        self._arcos.extend(((arco1, 1.0), (arco2, -.65)))

        # Luces que se desplazan lentamente por bordes opuestos.
        for posicion, color in ((.12, "#1377A9"), (.81, "#6245A7")):
            rayo = self.create_line(0, 0, 0, 0, fill=color, width=2)
            self._rayos.append((rayo, posicion, 0.0 if posicion < .5 else 2.1))

        # Particulas pequenas sin contenido textual ni indicadores falsos.
        rng = random.Random(3000)
        for _ in range(42):
            x, y = rng.random() * w, rng.random() * h
            radio = rng.choice((0.9, 1.2, 1.6))
            fase = rng.random() * 2 * math.pi
            part = self.create_oval(
                x - radio, y - radio, x + radio, y + radio,
                fill="#16415D", outline="",
            )
            self._points.append((part, x, y, radio, fase))

        # Esquinas y filetes neon discretos.
        borde = min(125, w * .11, h * .19)
        margen = 18
        self.create_line(
            margen, margen + borde, margen, margen, margen + borde, margen,
            fill="#1389CE", width=2, smooth=False,
        )
        self.create_line(
            w - margen - borde, margen, w - margen, margen,
            w - margen, margen + borde, fill="#7948C3", width=2,
        )
        self.create_line(
            margen, h - margen - borde, margen, h - margen,
            margen + borde, h - margen, fill="#7948C3", width=2,
        )
        self.create_line(
            w - margen - borde, h - margen, w - margen, h - margen,
            w - margen, h - margen - borde, fill="#1389CE", width=2,
        )
        self.create_line(w * .14, 1, w * .45, 1, fill="#0E9ACE", width=2)
        self.create_line(w * .58, h - 2, w * .87, h - 2, fill="#7043B6", width=2)

    def _animar(self) -> None:
        if not self.winfo_exists():
            return
        self._time += 0.066
        for i, (ident, x, y, radio, fase) in enumerate(self._points):
            brillo = (math.sin(self._time * .9 + fase) + 1) / 2
            color = "#346B8E" if brillo > .7 else "#1B4669" if brillo > .3 else "#12314C"
            self.itemconfigure(ident, fill=color)
            dy = math.sin(self._time * .23 + fase) * 2
            self.coords(ident, x - radio, y + dy - radio, x + radio, y + dy + radio)
        for ident, rapidez in self._arcos:
            self.itemconfigure(ident, start=(self._time * rapidez * 7) % 360)
        w, h = max(self.winfo_width(), 1), max(self.winfo_height(), 1)
        for ident, posicion, fase in self._rayos:
            delta = math.sin(self._time * .24 + fase) * .11
            centro = (posicion + delta) * w
            self.coords(
                ident, centro - w * .16, h * (.08 if posicion < .5 else .9),
                centro + w * .11, h * (.04 if posicion < .5 else .85),
            )
        self._job = self.after(66, self._animar)

    def _limpiar(self, event: tk.Event) -> None:
        if event.widget is self and self._job is not None:
            try:
                self.after_cancel(self._job)
            except tk.TclError:
                pass
            self._job = None


def render(parent: tk.Misc) -> tk.Widget:
    """API de integracion que usa app.py al descargar actualizaciones."""
    return FondoFutureo(parent)


def main() -> None:
    ventana = tk.Tk()
    ventana.title("FUTUREO LIVE")
    ventana.geometry("1366x768")
    ventana.minsize(800, 450)
    ventana.configure(bg=COLOR_SUPERIOR)

    def pantalla_completa(_evento=None):
        ventana.attributes("-fullscreen", not bool(ventana.attributes("-fullscreen")))

    ventana.bind("<F11>", pantalla_completa)
    ventana.bind("<Escape>", lambda _e: ventana.attributes("-fullscreen", False))
    render(ventana).pack(fill="both", expand=True)
    ventana.mainloop()


if __name__ == "__main__":
    main()
