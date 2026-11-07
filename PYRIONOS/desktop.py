#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PYRION OS - Escritorio X11 con buscador sobre fondo blanco.

La actualizacion en caliente mediante app.py sigue siendo compatible.
Python estandar + ctypes + libX11. Interfaz publica: PyrionDesktop y main().
"""
from __future__ import annotations

import ctypes as C
import ctypes.util
from pathlib import Path
import os
import signal
import sys
import time

APP_NAME = "PYRION OS"
APP_VERSION = "0.2.21-logo-pyrionos"

U = C.c_ulong
P = C.c_void_p
I = C.c_int
UI = C.c_uint


class XColor(C.Structure):
    _fields_ = [("pixel", U), ("red", C.c_ushort), ("green", C.c_ushort),
                ("blue", C.c_ushort), ("flags", C.c_byte), ("pad", C.c_byte)]


class XRenderColor(C.Structure):
    _fields_ = [("red", C.c_ushort), ("green", C.c_ushort),
                ("blue", C.c_ushort), ("alpha", C.c_ushort)]


class XftColor(C.Structure):
    _fields_ = [("pixel", U), ("color", XRenderColor)]


class XGlyphInfo(C.Structure):
    _fields_ = [("width", C.c_ushort), ("height", C.c_ushort),
                ("x", C.c_short), ("y", C.c_short),
                ("xOff", C.c_short), ("yOff", C.c_short)]


class XButtonEvent(C.Structure):
    # Diseño ABI de Xlib.h: XButtonEvent (64 bits y 32 bits).
    _fields_ = [
        ("type", I), ("serial", U), ("send_event", I), ("display", P),
        ("window", U), ("root", U), ("subwindow", U), ("time", U),
        ("x", I), ("y", I), ("x_root", I), ("y_root", I),
        ("state", UI), ("button", UI), ("same_screen", I),
    ]


class XKeyEvent(C.Structure):
    _fields_ = [("type", I), ("serial", U), ("send_event", I), ("display", P),
                ("window", U), ("root", U), ("subwindow", U), ("time", U),
                ("x", I), ("y", I), ("x_root", I), ("y_root", I),
                ("state", UI), ("keycode", UI), ("same_screen", I)]


class XEvent(C.Union):
    _fields_ = [("type", I), ("xbutton", XButtonEvent),
                ("xkey", XKeyEvent), ("pad", C.c_long * 24)]


class XSetWindowAttributes(C.Structure):
    _fields_ = [("background_pixmap", U), ("background_pixel", U),
                ("border_pixmap", U), ("border_pixel", U),
                ("bit_gravity", I), ("win_gravity", I),
                ("backing_store", I), ("backing_planes", U),
                ("backing_pixel", U), ("save_under", I),
                ("event_mask", C.c_long), ("do_not_propagate_mask", C.c_long),
                ("override_redirect", I), ("colormap", U), ("cursor", U)]


def bind(lib, name, result, *args):
    fn = getattr(lib, name)
    fn.restype = result
    fn.argtypes = list(args)
    return fn


class PyrionDesktop:
    """Ventana de escritorio X11 con el buscador principal de PYRIONOS."""

    def __init__(self):
        self.x = C.CDLL(ctypes.util.find_library("X11") or "libX11.so.6")
        x = self.x
        self.open = bind(x, "XOpenDisplay", P, C.c_char_p)
        self.close_dpy = bind(x, "XCloseDisplay", I, P)
        self.screen_idx = bind(x, "XDefaultScreen", I, P)
        self.root_of = bind(x, "XRootWindow", U, P, I)
        self.visual_of = bind(x, "XDefaultVisual", P, P, I)
        self.depth_of = bind(x, "XDefaultDepth", I, P, I)
        self.colormap_of = bind(x, "XDefaultColormap", U, P, I)
        self.screen_w = bind(x, "XDisplayWidth", I, P, I)
        self.screen_h = bind(x, "XDisplayHeight", I, P, I)
        self.new_window = bind(x, "XCreateSimpleWindow", U, P, U, I, I,
                               UI, UI, UI, U, U)
        self.change_attr = bind(x, "XChangeWindowAttributes", I, P, U, U,
                                C.POINTER(XSetWindowAttributes))
        self.change_prop = bind(x, "XChangeProperty", I, P, U, U, U, I, I,
                                C.POINTER(C.c_ubyte), I)
        self.atom = bind(x, "XInternAtom", U, P, C.c_char_p, I)
        self.name = bind(x, "XStoreName", I, P, U, C.c_char_p)
        self.select = bind(x, "XSelectInput", I, P, U, C.c_long)
        self.map = bind(x, "XMapWindow", I, P, U)
        self.lower = bind(x, "XLowerWindow", I, P, U)
        self.resize = bind(x, "XMoveResizeWindow", I, P, U, I, I, UI, UI)
        self.alloc_color = bind(x, "XAllocColor", I, P, U, C.POINTER(XColor))
        self.gc_create = bind(x, "XCreateGC", P, P, U, U, P)
        self.gc_free = bind(x, "XFreeGC", I, P, P)
        self.pixmap_create = bind(x, "XCreatePixmap", U, P, U, UI, UI, UI)
        self.pixmap_free = bind(x, "XFreePixmap", I, P, U)
        self.foreground = bind(x, "XSetForeground", I, P, P, U)
        self.fillrect = bind(x, "XFillRectangle", I, P, U, P, I, I, UI, UI)
        self.fillarc = bind(x, "XFillArc", I, P, U, P, I, I, UI, UI, I, I)
        self.drawline = bind(x, "XDrawLine", I, P, U, P, I, I, I, I)
        self.drawarc = bind(x, "XDrawArc", I, P, U, P, I, I, UI, UI, I, I)
        self.copy = bind(x, "XCopyArea", I, P, U, U, P, I, I, UI, UI, I, I)
        self.drawstring = bind(x, "XDrawString", I, P, U, P, I, I, C.c_char_p, I)
        self.lookup = bind(x, "XLookupString", I, C.POINTER(XKeyEvent), C.c_char_p, I, C.POINTER(U), P)
        self.flush = bind(x, "XFlush", I, P)
        self.pending = bind(x, "XPending", I, P)
        self.next_event = bind(x, "XNextEvent", I, P, C.POINTER(XEvent))
        self.destroy_window = bind(x, "XDestroyWindow", I, P, U)
        self.dpy = self.open(None)
        if not self.dpy:
            raise RuntimeError("No se pudo abrir DISPLAY (Xorg/X11)")
        self.screen = self.screen_idx(self.dpy)
        self.root = self.root_of(self.dpy, self.screen)
        self.visual = self.visual_of(self.dpy, self.screen)
        self.depth = self.depth_of(self.dpy, self.screen)
        self.colormap = self.colormap_of(self.dpy, self.screen)
        self.size = (0, 0)
        self.window = 0
        self.pixmap = 0
        self.gc = None
        self.colors = {}
        self.running = True
        self.search_text = ""
        self.search_focus = False
        self.active_tab = "Recientes"

    def _allocate(self, color):
        if color not in self.colors:
            rgb = [int(color[i:i+2], 16) for i in (1, 3, 5)]
            xc = XColor(0, rgb[0]*257, rgb[1]*257, rgb[2]*257, 7, 0)
            if not self.alloc_color(self.dpy, self.colormap, C.byref(xc)):
                return 0
            self.colors[color] = xc.pixel
        return self.colors[color]

    def pen(self, color):
        self.foreground(self.dpy, self.gc, self._allocate(color))

    def rect(self, x, y, w, h, color):
        if w <= 0 or h <= 0: return
        self.pen(color)
        self.fillrect(self.dpy, self.pixmap, self.gc,
                      int(x), int(y), int(w), int(h))

    def text(self, x, y, value, color="#111111"):
        encoded = value.encode("latin-1", "replace")
        self.pen(color)
        self.drawstring(self.dpy, self.pixmap, self.gc, int(x), int(y),
                        encoded, len(encoded))

    def _search_bounds(self):
        w, h = self.size
        bw = max(260, min(500, w - 40))
        bh = 44
        x = (w - bw) // 2
        # Centrar verticalmente el conjunto: logo (101), espacio (14), buscador (44) y categorias.
        y = max(115, (h + 40) // 2)
        return x, y, bw, bh

    def draw_pyrionos_logo(self, x, y):
        """Logo estilo PTM dibujado localmente con primitivas X11."""
        lw, main_h, footer_h = 226, 82, 19
        self.rect(x, y, lw, main_h, "#1D6684")
        # Borde oscuro de la tarjeta.
        self.rect(x, y, lw, 1, "#161616")
        self.rect(x, y, 1, main_h, "#161616")
        self.rect(x + lw - 1, y, 1, main_h, "#161616")
        self.rect(x, y + main_h - 1, lw, 1, "#161616")

        # Esquina roja diagonal superior derecha.
        corner = 29
        for i in range(corner):
            self.rect(x + lw - corner + i, y + i, corner - i, 1,
                      "#FF1B1B")

        # Letras grandes de PYRIONOS, sin depender de fuentes externas.
        glyphs = {
            "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
            "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
            "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
            "I": ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
            "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
            "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
            "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
        }
        title = "PYRIONOS"
        scale, spacing = 4, 4
        glyph_w = 5 * scale
        text_w = len(title) * (glyph_w + spacing) - spacing
        tx = x + (lw - text_w) // 2
        ty = y + (main_h - 7 * scale) // 2
        for ch in title:
            for row, bits in enumerate(glyphs[ch]):
                for col, bit in enumerate(bits):
                    if bit == "1":
                        self.rect(tx + col * scale, ty + row * scale,
                                  scale, scale, "#FFFFFF")
            tx += glyph_w + spacing

        # Franja inferior roja y leyenda, como el icono de referencia.
        self.rect(x, y + main_h, lw, footer_h, "#FF1B1B")
        self.text(x + 8, y + main_h + 13,
                  "Buscador y lanzador de herramientas", "#FFFFFF")

    def draw_search(self):
        """Cabecera PYRIONOS, buscador y enlaces inspirados en el boceto."""
        x, y, bw, bh = self._search_bounds()
        # Logo centrado encima del buscador sobre el fondo blanco.
        logo_w, logo_h, gap = 226, 101, 14
        self.draw_pyrionos_logo(x + (bw - logo_w) // 2, y - logo_h - gap)

        # Borde fino con cuatro esquinas redondeadas, sin circulos.
        self.rect(x + 6, y, bw - 12, 1, "#111111")
        self.rect(x + 6, y + bh - 1, bw - 12, 1, "#111111")
        self.rect(x, y + 6, 1, bh - 12, "#111111")
        self.rect(x + bw - 1, y + 6, 1, bh - 12, "#111111")
        self.pen("#111111")
        for ax, ay, start in (
            (x, y, 90),                   # superior izquierda
            (x + bw - 13, y, 0),         # superior derecha
            (x, y + bh - 13, 180),       # inferior izquierda
            (x + bw - 13, y + bh - 13, 270),  # inferior derecha
        ):
            self.drawarc(self.dpy, self.pixmap, self.gc, ax, ay,
                         12, 12, start * 64, 90 * 64)

        value = self.search_text or "Buscar"
        if self.search_focus:
            value += "|"
        self.text(x + 18, y + 27, value[:max(1, (bw - 110) // 7)], "#111111")

        # Boton circular rojo.
        self.pen("#F01818")
        self.fillarc(self.dpy, self.pixmap, self.gc, x + bw - 79, y + 11,
                     23, 23, 0, 360 * 64)
        self.pen("#111111")
        self.drawarc(self.dpy, self.pixmap, self.gc, x + bw - 79, y + 11,
                     23, 23, 0, 360 * 64)

        # Icono de subir: bandeja y flecha dibujadas con primitivas X11.
        ix = x + bw - 34
        self.pen("#111111")
        self.drawline(self.dpy, self.pixmap, self.gc, ix, y + 13, ix, y + 29)
        self.drawline(self.dpy, self.pixmap, self.gc, ix, y + 13, ix - 5, y + 18)
        self.drawline(self.dpy, self.pixmap, self.gc, ix, y + 13, ix + 5, y + 18)
        self.drawline(self.dpy, self.pixmap, self.gc, ix - 9, y + 26, ix - 9, y + 32)
        self.drawline(self.dpy, self.pixmap, self.gc, ix - 9, y + 32, ix + 9, y + 32)
        self.drawline(self.dpy, self.pixmap, self.gc, ix + 9, y + 32, ix + 9, y + 26)

        tabs = ("Recientes", "Favoritos", "Más usados", "Recomendados")
        total_tabs = sum(len(tab) * 6 + 6 for tab in tabs) + 15 * (len(tabs) - 1)
        cursor = x + (bw - total_tabs) // 2
        for tab in tabs:
            self.text(cursor, y + bh + 20, tab, "#111111")
            tw = len(tab) * 6 + 6
            self.pen("#111111" if tab == self.active_tab else "#777777")
            self.drawline(self.dpy, self.pixmap, self.gc,
                          cursor, y + bh + 23, cursor + tw - 7,
                          y + bh + 23)
            cursor += tw + 15

    def click_ui(self, x, y):
        bx, by, bw, bh = self._search_bounds()
        if bx <= x < bx + bw and by <= y < by + bh:
            if x >= bx + bw - 84 and x < bx + bw - 50:
                self.search_text = ""
                self.search_focus = True
            elif x >= bx + bw - 47:
                # El icono de subir se conecta al gestor de archivos mas adelante.
                self.search_focus = False
            else:
                self.search_focus = True
            self.paint()
            return
        tabs = ("Recientes", "Favoritos", "Más usados", "Recomendados")
        total_tabs = sum(len(tab) * 6 + 6 for tab in tabs) + 15 * (len(tabs) - 1)
        cursor = bx + (bw - total_tabs) // 2
        if by + bh + 5 <= y <= by + bh + 30:
            for tab in ("Recientes", "Favoritos", "Más usados", "Recomendados"):
                tw = len(tab) * 6 + 6
                if cursor <= x <= cursor + tw:
                    self.active_tab = tab
                    self.search_focus = False
                    self.paint()
                    return
                cursor += tw + 15
        self.search_focus = False
        self.paint()

    def key_ui(self, event):
        if not self.search_focus:
            return
        buffer = C.create_string_buffer(32)
        keysym = U()
        count = self.lookup(C.byref(event), buffer, 31, C.byref(keysym), None)
        if keysym.value == 0xFF08:  # Backspace
            self.search_text = self.search_text[:-1]
        elif keysym.value in (0xFF0D, 0xFF8D):  # Enter
            self.search_focus = False
        elif 0 < count <= 31:
            value = buffer.raw[:count].decode("utf-8", "ignore")
            if value.isprintable() and len(self.search_text) + len(value) <= 120:
                self.search_text += value
        self.paint()

    def paint(self):
        """Dibuja fondo blanco y buscador centrado del escritorio."""
        w, h = self.size
        if self.pixmap:
            self.pixmap_free(self.dpy, self.pixmap)
        self.pixmap = self.pixmap_create(self.dpy, self.window, w, h, self.depth)
        self.rect(0, 0, w, h, "#FFFFFF")
        self.draw_search()
        self.copy(self.dpy, self.pixmap, self.window, self.gc,
                  0, 0, w, h, 0, 0)
        self.flush(self.dpy)

    def create(self):
        w,h=self.screen_w(self.dpy,self.screen),self.screen_h(self.dpy,self.screen)
        self.size=(w,h)
        self.window=self.new_window(self.dpy,self.root,0,0,w,h,0,0,
                                    self._allocate("#FFFFFF"))
        opts=XSetWindowAttributes()
        opts.override_redirect=1
        self.change_attr(self.dpy,self.window,1<<9,C.byref(opts))
        atom=self.atom(self.dpy,b"_NET_WM_WINDOW_TYPE",0)
        kind=self.atom(self.dpy,b"_NET_WM_WINDOW_TYPE_DESKTOP",0)
        if atom and kind:
            value=U(kind)
            self.change_prop(self.dpy,self.window,atom,4,32,0,
                             C.cast(C.byref(value),C.POINTER(C.c_ubyte)),1)
        self.name(self.dpy,self.window,b"PYRION OS")
        self.select(self.dpy,self.window,(1<<15)|(1<<17)|(1<<2)|(1<<0))
        self.gc=self.gc_create(self.dpy,self.window,0,None)
        self.map(self.dpy,self.window)
        self.lower(self.dpy,self.window)
        self.paint()
        # Confirma que la nueva ventana X11 ya se ha pintado.
        # app.py espera esta senal antes de cerrar la ventana anterior.
        ready_file = os.environ.get("PYRION_DESKTOP_READY_FILE")
        if ready_file:
            try:
                Path(ready_file).write_text(str(os.getpid()), encoding="ascii")
            except OSError as error:
                print("PYRION: no se pudo indicar que el escritorio esta listo: " +
                      str(error), file=sys.stderr, flush=True)
        print("PYRION: escritorio con buscador iniciado.", flush=True)

    def run(self):
        self.create()
        last_check=0
        while self.running:
            now=time.monotonic()
            if now-last_check>1.2:
                new=(self.screen_w(self.dpy,self.screen),self.screen_h(self.dpy,self.screen))
                if new!=self.size:
                    self.size=new
                    self.resize(self.dpy,self.window,0,0,*new)
                    self.paint()
                self.lower(self.dpy,self.window)
                last_check=now
            if self.pending(self.dpy):
                ev=XEvent()
                self.next_event(self.dpy,C.byref(ev))
                if ev.type == 4:  # ButtonPress
                    self.click_ui(ev.xbutton.x, ev.xbutton.y)
                elif ev.type == 2:  # KeyPress
                    self.key_ui(ev.xkey)
                elif ev.type==12:  # Expose
                    self.copy(self.dpy,self.pixmap,self.window,self.gc,
                              0,0,*self.size,0,0)
                    self.flush(self.dpy)
            else:
                time.sleep(.05)

    def stop(self,*_):
        self.running=False

    def close(self):
        if self.dpy:
            if self.pixmap:self.pixmap_free(self.dpy,self.pixmap)
            if self.gc:self.gc_free(self.dpy,self.gc)
            if self.window:self.destroy_window(self.dpy,self.window)
            self.close_dpy(self.dpy)
            self.dpy=None


def main():
    if "--check" in sys.argv[1:]:
        try:
            C.CDLL(ctypes.util.find_library("X11") or "libX11.so.6")
            print("OK: PYRION X11 disponible. Fondo blanco local.")
            return 0
        except OSError as error:
            print("ERROR:",error,file=sys.stderr)
            return 2
    desktop=None
    try:
        desktop=PyrionDesktop()
        signal.signal(signal.SIGINT,desktop.stop)
        signal.signal(signal.SIGTERM,desktop.stop)
        desktop.run()
        return 0
    except (OSError,RuntimeError,ValueError) as error:
        print("PYRION:",error,file=sys.stderr)
        return 1
    finally:
        if desktop:desktop.close()


if __name__=="__main__":
    raise SystemExit(main())
