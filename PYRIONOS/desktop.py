#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PYRION OS - Escritorio X11 con buscador sobre fondo blanco.

La actualizacion en caliente mediante app.py sigue siendo compatible.
Python estandar + ctypes + libX11. Interfaz publica: PyrionDesktop y main().
"""
from __future__ import annotations

import ctypes as C
import ctypes.util
import hashlib
import csv
import io
import json
import queue
import re
import subprocess
import threading
import unicodedata
import urllib.request
import zipfile
from pathlib import Path
import os
import signal
import sys
import time

APP_NAME = "PYRION OS"
APP_VERSION = "0.2.29-tools-embebidas"
MAX_SEARCH_CHARS = 30
CATALOG_URL = "https://raw.githubusercontent.com/mobatfb/archmoba-dev/main/PTM/guide.csv"
TOOLS_URL = "https://raw.githubusercontent.com/mobatfb/archmoba-dev/main/PTM/"

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


class XFontHandle(C.Structure):
    _fields_ = [("ext_data", P), ("fid", U)]


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
        self.load_query_font = bind(x, "XLoadQueryFont", P, P, C.c_char_p)
        self.free_font = bind(x, "XFreeFont", I, P, P)
        self.set_font = bind(x, "XSetFont", I, P, P, U)
        self.xtext_width = bind(x, "XTextWidth", I, P, C.c_char_p, I)
        self.foreground_gc = bind(x, "XSetForeground", I, P, P, U)
        self.lookup = bind(x, "XLookupString", I, C.POINTER(XKeyEvent), C.c_char_p, I, C.POINTER(U), P)
        self.flush = bind(x, "XFlush", I, P)
        self.sync = bind(x, "XSync", I, P, I)
        self.pending = bind(x, "XPending", I, P)
        self.next_event = bind(x, "XNextEvent", I, P, C.POINTER(XEvent))
        self.reparent_window = bind(x, "XReparentWindow", I, P, U, U, I, I)
        self.unmap_window = bind(x, "XUnmapWindow", I, P, U)
        self.map_raised = bind(x, "XMapRaised", I, P, U)
        self.set_input_focus = bind(x, "XSetInputFocus", I, P, U, I, U)
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
        # Al estilo PTM: inicio permanente; las demas pestañas nacen al abrir tools.
        self.top_tabs = ["PYRIONOS"]
        self.selected_top_tab = "PYRIONOS"
        self.open_tabs = {}
        self.catalog_tools = []
        self.catalog_status = "Cargando catalogo PTM..."
        self.catalog_queue = queue.Queue()
        self.catalog_fetching = False
        self.catalog_last_check = 0.0
        self.catalog_check_pending = False
        self.expand_after_update = False
        self.show_all_results = False
        self.results_scroll = 0
        self.last_search_edit = 0.0
        self.cache_dir = Path.home() / ".cache" / "pyrionos" / "ptm"
        self.catalog_cache = self.cache_dir / "guide.csv"
        self.state_file = self.cache_dir / "user_state.json"
        self.user_state = self._load_user_state()
        self.results_click_areas = []
        self.tab_menu = None
        self.tool_events = queue.Queue()
        self.xft_lib = None
        self.logo_xft_font = None
        self.logo_core_font = None
        self.logo_gc = None
        self.ui_fonts = {}
        self._prepare_logo_font()

    def _prepare_logo_font(self):
        """Tipografia antialias Xft para toda la interfaz; fallback X11."""
        try:
            ft = C.CDLL(ctypes.util.find_library("Xft") or "libXft.so.2")
            self.xft_font_open = bind(ft, "XftFontOpenName", P, P, I, C.c_char_p)
            self.xft_font_close = bind(ft, "XftFontClose", None, P, P)
            self.xft_draw_create = bind(ft, "XftDrawCreate", P, P, U, P, U)
            self.xft_draw_destroy = bind(ft, "XftDrawDestroy", None, P)
            self.xft_draw_string = bind(
                ft, "XftDrawStringUtf8", None, P, C.POINTER(XftColor), P,
                I, I, C.c_char_p, I)
            self.xft_extents = bind(
                ft, "XftTextExtentsUtf8", None, P, P, C.c_char_p, I,
                C.POINTER(XGlyphInfo))
            self.xft_color_alloc = bind(
                ft, "XftColorAllocValue", I, P, P, U,
                C.POINTER(XRenderColor), C.POINTER(XftColor))
            self.xft_color_free = bind(
                ft, "XftColorFree", None, P, P, U, C.POINTER(XftColor))
            for face in (
                b"DejaVu Sans:style=Bold:pixelsize=32",
                b"Liberation Sans:style=Bold:pixelsize=32",
                b"sans:style=Bold:pixelsize=32",
            ):
                font = self.xft_font_open(self.dpy, self.screen, face)
                if font:
                    self.xft_lib = ft
                    self.logo_xft_font = font
                    break
            if self.xft_lib:
                families = {
                    "body": b"DejaVu Sans:pixelsize=14",
                    "label": b"DejaVu Sans:style=Bold:pixelsize=14",
                    "tab": b"DejaVu Sans:pixelsize=13",
                    "tab_active": b"DejaVu Sans:style=Bold:pixelsize=13",
                    "caption": b"DejaVu Sans:pixelsize=11",
                }
                for style, face in families.items():
                    font = self.xft_font_open(self.dpy, self.screen, face)
                    if font:
                        self.ui_fonts[style] = font
        except (OSError, AttributeError) as error:
            print("PYRION: Xft no disponible: " + str(error),
                  file=sys.stderr, flush=True)

        # Alternativa X11 para el logotipo si Xft no esta disponible.
        if not self.logo_xft_font:
            for face in (
                b"-*-helvetica-bold-r-normal--34-*-*-*-*-*-iso8859-1",
                b"9x15bold",
                b"fixed",
            ):
                font = self.load_query_font(self.dpy, face)
                if font:
                    self.logo_core_font = font
                    break

    def draw_logo_title(self, x, y, width):
        """Dibuja PYRIONOS centrado con letras blancas negritas."""
        title = b"PYRIONOS"
        baseline = y + 56
        if self.xft_lib and self.logo_xft_font:
            draw = self.xft_draw_create(self.dpy, self.pixmap,
                                        self.visual, self.colormap)
            if draw:
                white = XftColor()
                rgba = XRenderColor(65535, 65535, 65535, 65535)
                allocated = self.xft_color_alloc(
                    self.dpy, self.visual, self.colormap,
                    C.byref(rgba), C.byref(white))
                try:
                    if allocated:
                        metrics = XGlyphInfo()
                        self.xft_extents(self.dpy, self.logo_xft_font,
                                         title, len(title), C.byref(metrics))
                        left = x + (width - metrics.xOff) // 2
                        self.xft_draw_string(draw, C.byref(white),
                                             self.logo_xft_font, int(left),
                                             int(baseline), title, len(title))
                        return
                finally:
                    if allocated:
                        self.xft_color_free(self.dpy, self.visual,
                                            self.colormap, C.byref(white))
                    self.xft_draw_destroy(draw)

        if self.logo_core_font and self.logo_gc:
            font = C.cast(self.logo_core_font, C.POINTER(XFontHandle)).contents
            self.set_font(self.dpy, self.logo_gc, font.fid)
            self.foreground_gc(self.dpy, self.logo_gc,
                               self._allocate("#FFFFFF"))
            width_px = self.xtext_width(self.logo_core_font, title, len(title))
            self.drawstring(self.dpy, self.pixmap, self.logo_gc,
                            x + (width - width_px) // 2, baseline,
                            title, len(title))
        else:
            self.text(x + (width - len(title) * 6) // 2, baseline,
                      title.decode("ascii"), "#FFFFFF")

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

    def text_width(self, value, style="body"):
        """Ancho real del texto; necesario para el cursor y los clics."""
        value = str(value)
        font = self.ui_fonts.get(style)
        if self.xft_lib and font:
            data = value.encode("utf-8")
            metrics = XGlyphInfo()
            self.xft_extents(self.dpy, font, data, len(data),
                             C.byref(metrics))
            return int(metrics.xOff)
        return len(value) * 6

    def text(self, x, y, value, color="#111111", style="body"):
        """Texto suavizado UTF-8 con Xft; respaldo basico de X11."""
        value = str(value)
        font = self.ui_fonts.get(style)
        if self.xft_lib and font:
            draw = self.xft_draw_create(self.dpy, self.pixmap,
                                        self.visual, self.colormap)
            if draw:
                rgba = [int(color[i:i+2], 16) * 257 for i in (1, 3, 5)]
                tint = XRenderColor(rgba[0], rgba[1], rgba[2], 65535)
                ink = XftColor()
                allocated = self.xft_color_alloc(
                    self.dpy, self.visual, self.colormap,
                    C.byref(tint), C.byref(ink))
                try:
                    if allocated:
                        data = value.encode("utf-8")
                        self.xft_draw_string(draw, C.byref(ink), font,
                                             int(x), int(y), data, len(data))
                        return
                finally:
                    if allocated:
                        self.xft_color_free(self.dpy, self.visual,
                                            self.colormap, C.byref(ink))
                    self.xft_draw_destroy(draw)
        # Mantener funcionamiento incluso sin libreria Xft.
        data = value.encode("latin-1", "replace")
        self.pen(color)
        self.drawstring(self.dpy, self.pixmap, self.gc,
                        int(x), int(y), data, len(data))

    def _search_bounds(self):
        w, h = self.size
        bw = max(260, min(500, w - 40))
        bh = 44
        x = (w - bw) // 2
        # Centrar verticalmente el conjunto: logo (101), espacio (14), buscador (44) y categorias.
        y = max(125, (h + 40) // 2 - (70 if self.search_text.strip() else 0))
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

        # Titulo con tipografia real en lugar del dibujo bitmap 5x7.
        self.draw_logo_title(x, y, lw)

        # Franja inferior roja y leyenda, como el icono de referencia.
        self.rect(x, y + main_h, lw, footer_h, "#FF1B1B")
        subtitle = "Buscador y lanzador de herramientas"
        subtitle_x = x + (lw - self.text_width(subtitle, "caption")) // 2
        self.text(subtitle_x, y + main_h + 13, subtitle,
                  "#FFFFFF", "caption")

    def _search_input_layout(self):
        """Texto visible y boton de borrar usando anchuras de fuente reales."""
        x, _, bw, _ = self._search_bounds()
        label_right = x + 18 + self.text_width("Buscar", "label")
        tx = label_right + 24
        text_limit = x + bw - 107
        # Mostrar el final de la consulta sin invadir controles derechos.
        visible = self.search_text
        allowance = max(0, text_limit - tx - (18 if visible else 0))
        while visible and self.text_width(visible, "body") > allowance:
            visible = visible[1:]
        clear_x = tx + self.text_width(visible, "body") + 13 if self.search_text else None
        return tx, visible, clear_x

    def _tab_layout(self):
        """Posiciones estables para pintar y seleccionar las categorias."""
        x, _, bw, _ = self._search_bounds()
        tabs = ("Recientes", "Favoritos", "Más usados", "Recomendados")
        widths = [max(self.text_width(tab, "tab"),
                      self.text_width(tab, "tab_active")) for tab in tabs]
        gap = 18
        total = sum(widths) + gap * (len(tabs) - 1)
        cursor = x + (bw - total) // 2
        result = []
        for tab, width in zip(tabs, widths):
            result.append((tab, cursor, width))
            cursor += width + gap
        return result

    @staticmethod
    def _tk_launcher_source():
        """Inicia una herramienta Tk oculta hasta integrarla en la pestaña X11."""
        return r'''#!/usr/bin/env python3
import ctypes as C
import ctypes.util
import importlib.util
import inspect
import sys
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

tool_path = Path(sys.argv[1]).resolve()
xid_path = Path(sys.argv[2])
ready_path = Path(sys.argv[3])
root = tk.Tk()
root.withdraw()                       # Nunca mostrar una ventana externa.
root.overrideredirect(True)            # Sin decoraciones del gestor de ventanas.
root.configure(bg="#FFFFFF")
root.geometry("900x650")

class Bridge:
    def __init__(self):
        self.root = root

    def show_dialog(self, title, message, kind="info", **kwargs):
        show = (messagebox.showerror if kind == "error" else
                messagebox.showwarning if kind == "warning" else
                messagebox.showinfo)
        return show(title, message, parent=root)

    def set_tool_processing(self, active=True, key=None):
        return None

    def tool_processing(self, key=None):
        class Context:
            def __enter__(self): return self
            def __exit__(self, *exc): return False
        return Context()

def run_tool():
    sys.path.insert(0, str(tool_path.parent))
    spec = importlib.util.spec_from_file_location(
        "pyrion_embedded_" + tool_path.stem, tool_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("No se puede abrir el modulo Python")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    exec(compile(tool_path.read_bytes(), str(tool_path), "exec"), module.__dict__)

    entry = None
    for name in ("App", "Application", "create_tool", "create_app",
                 "build_app", "build_ui"):
        candidate = getattr(module, name, None)
        if callable(candidate):
            entry = candidate
            break
    if entry is None:
        for candidate in vars(module).values():
            if not inspect.isclass(candidate):
                continue
            if candidate.__module__ != module.__name__:
                continue
            try:
                if issubclass(candidate, (tk.Frame, ttk.Frame)):
                    entry = candidate
                    break
            except (TypeError, AttributeError):
                continue

    if entry is not None:
        signature = inspect.signature(entry)
        params = tuple(signature.parameters.values())
        positional = [p for p in params if p.kind in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD)]
        varargs = any(p.kind == inspect.Parameter.VAR_POSITIONAL
                      for p in params)
        if varargs or len(positional) >= 2:
            widget = entry(root, Bridge())
        elif len(positional) == 1:
            widget = entry(root)
        else:
            widget = entry()
        if isinstance(widget, (tuple, list)):
            widget = widget[0] if widget else None
        if not isinstance(widget, tk.Widget):
            raise RuntimeError("La herramienta no devolvio un widget Tk.")
        if not widget.winfo_manager():
            widget.pack(fill="both", expand=True)
        return widget

    # Programas sencillos que solo exponen main() tambien se ejecutan dentro.
    main = getattr(module, "main", None)
    if not callable(main):
        raise RuntimeError("Esta herramienta requiere interfaz Tk o adaptador.")
    real_tk = tk.Tk
    real_mainloop = tk.mainloop
    original_loop = root.mainloop
    try:
        tk.Tk = lambda *args, **kwargs: root
        tk.mainloop = lambda *args, **kwargs: None
        root.mainloop = lambda *args, **kwargs: None
        main()
    finally:
        tk.Tk = real_tk
        tk.mainloop = real_mainloop
        root.mainloop = original_loop
    return root

def get_outer_xid():
    """Obtener la ventana Tk superior real, no el hijo de contenido."""
    lib = C.CDLL(ctypes.util.find_library("X11") or "libX11.so.6")
    lib.XOpenDisplay.argtypes = [C.c_char_p]
    lib.XOpenDisplay.restype = C.c_void_p
    lib.XDefaultRootWindow.argtypes = [C.c_void_p]
    lib.XDefaultRootWindow.restype = C.c_ulong
    lib.XQueryTree.argtypes = [
        C.c_void_p, C.c_ulong, C.POINTER(C.c_ulong),
        C.POINTER(C.c_ulong), C.POINTER(C.POINTER(C.c_ulong)),
        C.POINTER(C.c_uint)]
    lib.XQueryTree.restype = C.c_int
    lib.XFree.argtypes = [C.c_void_p]
    lib.XFree.restype = C.c_int
    lib.XCloseDisplay.argtypes = [C.c_void_p]
    lib.XCloseDisplay.restype = C.c_int
    dpy = lib.XOpenDisplay(None)
    if not dpy:
        raise RuntimeError("DISPLAY X11 no disponible")
    try:
        root_id = int(lib.XDefaultRootWindow(dpy))
        wid = int(root.winfo_id())
        for _ in range(16):
            actual_root = C.c_ulong()
            parent = C.c_ulong()
            children = C.POINTER(C.c_ulong)()
            count = C.c_uint()
            if not lib.XQueryTree(dpy, wid, C.byref(actual_root),
                                  C.byref(parent), C.byref(children),
                                  C.byref(count)):
                break
            if children:
                lib.XFree(children)
            if parent.value == root_id or parent.value == 0:
                break
            wid = int(parent.value)
        return wid
    finally:
        lib.XCloseDisplay(dpy)

try:
    run_tool()
except Exception as error:
    traceback.print_exc()
    for child in root.winfo_children():
        child.destroy()
    tk.Label(root, text="No se pudo cargar la herramienta",
             fg="#BD2020", font=("DejaVu Sans", 14, "bold")).pack(pady=24)
    tk.Label(root, text=str(error), fg="#374151", wraplength=650,
             justify="left").pack(padx=20)

root.update_idletasks()
root.update()
xid = get_outer_xid()
xid_path.write_text(str(xid), encoding="ascii")

def wait_for_host():
    if ready_path.exists():
        root.deiconify()   # Ahora su padre es la pestaña, no la pantalla.
        root.update_idletasks()
        return
    root.after(50, wait_for_host)

root.after(50, wait_for_host)
root.mainloop()
'''
    def _download_tool_async(self, tool, key, force_remote=False):
        meta = self.open_tabs.get(key)
        if not meta:
            return
        meta["state"] = "loading"
        meta["message"] = "Descargando herramienta..."
        local = self.cache_dir / "tools" / self._tool_safe_id(key) / Path(tool["repo_path"]).name
        def worker():
            try:
                if force_remote or not local.is_file():
                    url = TOOLS_URL + tool["repo_path"]
                    req = urllib.request.Request(url, headers={
                        "User-Agent": "PYRIONOS/" + APP_VERSION})
                    max_size = 15_000_000 if tool["file_type"] == "zip" else 5_000_000
                    with urllib.request.urlopen(req, timeout=18) as response:
                        data = response.read(max_size + 1)
                    if not data or len(data) > max_size:
                        raise ValueError("Tool vacia o demasiado grande")
                    local.parent.mkdir(parents=True, exist_ok=True)
                    tmp = local.with_suffix(local.suffix + ".tmp")
                    tmp.write_bytes(data)
                    tmp.replace(local)
                main = local
                if tool["file_type"] == "zip":
                    folder = local.parent / "extracted"
                    folder.mkdir(exist_ok=True)
                    with zipfile.ZipFile(local) as package:
                        contents = package.infolist()
                        if len(contents) > 100 or sum(e.file_size for e in contents) > 40_000_000:
                            raise ValueError("ZIP demasiado grande")
                        for entry in contents:
                            parts = Path(entry.filename).parts
                            if (not parts or entry.filename.startswith("/")
                                    or any(p in ("..", "") for p in parts)
                                    or (entry.external_attr >> 16) & 0o170000 == 0o120000):
                                raise ValueError("Ruta insegura en ZIP")
                        package.extractall(folder)
                    main_name = tool.get("archivo_principal", "").strip()
                    target = folder / main_name
                    if not main_name or ".." in Path(main_name).parts or not target.is_file():
                        raise ValueError("Archivo principal no encontrado en ZIP")
                    main = target
                self.tool_events.put(("downloaded", key, str(main)))
            except Exception as error:
                self.tool_events.put(("failed", key, str(error)))
        threading.Thread(target=worker, daemon=True).start()

    def _tool_view_rect(self):
        """Área útil: bajo las pestañas; nunca cubre la barra superior."""
        w, h = self.size
        return 6, 51, max(120, w - 12), max(100, h - 58)

    def _new_tool_host(self):
        """Cada pestaña posee su propia ventana contenedora hija de X11."""
        px, py, pw, ph = self._tool_view_rect()
        return self.new_window(self.dpy, self.window, px, py, pw, ph,
                               0, 0, self._allocate("#FFFFFF"))

    @staticmethod
    def _tool_safe_id(key):
        return hashlib.sha256(str(key).encode("utf-8")).hexdigest()[:20]

    def _tool_files(self, key):
        label = self._tool_safe_id(key)
        return (self.cache_dir / ("window_" + label + ".xid"),
                self.cache_dir / ("window_" + label + ".ready"),
                self.cache_dir / ("tool_" + label + ".log"))

    def _open_tool(self, tool):
        """Abrir una herramienta de guide.csv dentro de su pestaña."""
        key = tool["key"]
        self._record_tool_open(tool)
        if key in self.open_tabs:
            self._activate_tool_tab(key)
            return
        meta = {
            "name": tool["name"], "tool": tool, "state": "loading",
            "message": "Preparando herramienta...", "process": None,
            "xid": None, "embedded": False,
            "xid_file": None, "ready_file": None,
            "host": self._new_tool_host(), "log_file": None,
        }
        self.open_tabs[key] = meta
        self.top_tabs.append(key)
        self._activate_tool_tab(key)
        self._download_tool_async(tool, key)

    def _stop_tool_runtime(self, meta, destroy_host=True):
        """Finalizar solo el proceso de esta pestaña, sin afectar otras."""
        host = meta.get("host")
        if host and self.dpy:
            self.unmap_window(self.dpy, host)
        process = meta.get("process")
        if process and process.poll() is None:
            try:
                process.terminate()
            except OSError:
                pass
        if destroy_host and host and self.dpy:
            self.destroy_window(self.dpy, host)
            meta["host"] = None
        for file_key in ("xid_file", "ready_file"):
            path = meta.get(file_key)
            if path:
                try:
                    Path(path).unlink(missing_ok=True)
                except OSError:
                    pass
        meta["process"] = None
        meta["xid"] = None
        meta["embedded"] = False
        meta["xid_file"] = None
        meta["ready_file"] = None

    def _start_tool_process(self, key, local_file):
        meta = self.open_tabs.get(key)
        if not meta:
            return
        try:
            path = Path(local_file).resolve()
            if not path.is_file() or path.suffix.lower() != ".py":
                raise ValueError("No es un archivo Python ejecutable")
            if not meta.get("host"):
                meta["host"] = self._new_tool_host()
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            xid_file, ready_file, logfile = self._tool_files(key)
            for marker in (xid_file, ready_file):
                marker.unlink(missing_ok=True)
            meta.update({
                "xid_file": xid_file, "ready_file": ready_file,
                "log_file": logfile, "state": "starting",
                "message": "Iniciando Python dentro de la pestaña...",
                "xid": None, "embedded": False,
            })
            wrapper = self.cache_dir / "tk_launcher.py"
            wrapper.write_text(self._tk_launcher_source(), encoding="utf-8")
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            command = [sys.executable, str(wrapper), str(path),
                       str(xid_file), str(ready_file)]
            # Tambien las tools marcadas "Externo" usan su pestaña PYRIONOS.
            with logfile.open("ab") as output:
                meta["process"] = subprocess.Popen(
                    command, cwd=str(path.parent), env=env,
                    stdout=output, stderr=subprocess.STDOUT)
            meta["state"] = "running"
            meta["started_at"] = time.monotonic()
        except (OSError, ValueError) as error:
            meta["state"] = "error"
            meta["message"] = str(error)
        self.paint()

    def _attach_tool_window(self, key, xid):
        """Reubicar el top-level Tk REAL dentro del host de su pestaña."""
        meta = self.open_tabs.get(key)
        if not meta or meta.get("embedded") or not meta.get("host"):
            return
        host = meta["host"]
        _, _, width, height = self._tool_view_rect()
        self.reparent_window(self.dpy, xid, host, 0, 0)
        self.resize(self.dpy, xid, 0, 0, width, height)
        # La herramienta solo puede verse a traves de su ventana contenedora.
        self.map(self.dpy, xid)
        meta["xid"] = xid
        meta["embedded"] = True
        meta["state"] = "ready"
        meta["message"] = "Herramienta integrada en su pestaña"
        if self.selected_top_tab == key:
            self.map_raised(self.dpy, host)
            self.sync(self.dpy, 0)
            self.set_input_focus(self.dpy, xid, 1, 0)
        else:
            self.unmap_window(self.dpy, host)
        self.flush(self.dpy)
        # El proceso Tk estaba oculto; puede mostrarse solo tras este aviso.
        try:
            meta["ready_file"].write_text("ready", encoding="ascii")
        except OSError:
            pass

    def _poll_tools(self):
        dirty = False
        while True:
            try:
                action, key, data = self.tool_events.get_nowait()
            except queue.Empty:
                break
            if key not in self.open_tabs:
                continue
            if action == "downloaded":
                self._start_tool_process(key, data)
            elif action == "failed":
                self.open_tabs[key]["state"] = "error"
                self.open_tabs[key]["message"] = data
            dirty = True
        for key, meta in tuple(self.open_tabs.items()):
            process = meta.get("process")
            if not process:
                continue
            if meta.get("xid_file") and not meta.get("embedded"):
                try:
                    xid = int(meta["xid_file"].read_text(encoding="ascii").strip())
                    if xid > 0 and process.poll() is None:
                        self._attach_tool_window(key, xid)
                        dirty = True
                except (OSError, ValueError):
                    pass
            if process.poll() is not None and meta.get("state") not in ("error", "ended"):
                meta["state"] = "ended"
                error_info = ""
                if not meta.get("embedded") and meta.get("log_file"):
                    try:
                        log = meta["log_file"].read_text(
                            encoding="utf-8", errors="replace")
                        error_info = log.strip().splitlines()[-1][:140]
                    except (OSError, IndexError):
                        pass
                meta["message"] = error_info or "La herramienta se ha cerrado"
                dirty = True
        return dirty

    def _activate_tool_tab(self, key):
        if key != "PYRIONOS" and key not in self.open_tabs:
            return
        old = self.open_tabs.get(self.selected_top_tab)
        if old and old.get("host"):
            self.unmap_window(self.dpy, old["host"])
        self.selected_top_tab = key
        self.tab_menu = None
        self.search_focus = False
        self.paint()
        current = self.open_tabs.get(key)
        if current and current.get("embedded") and current.get("host"):
            self.map_raised(self.dpy, current["host"])
            self.sync(self.dpy, 0)
            self.set_input_focus(self.dpy, current["xid"], 1, 0)
        elif key == "PYRIONOS":
            self.set_input_focus(self.dpy, self.window, 1, 0)
        self.flush(self.dpy)

    def _close_tool_tab(self, key):
        meta = self.open_tabs.pop(key, None)
        if not meta:
            return
        if key in self.top_tabs:
            self.top_tabs.remove(key)
        if self.tab_menu and self.tab_menu.get("key") == key:
            self.tab_menu = None
        self._stop_tool_runtime(meta)
        if self.selected_top_tab == key:
            self.selected_top_tab = "PYRIONOS"
            self.set_input_focus(self.dpy, self.window, 1, 0)
        self.paint()

    def _reload_tool_tab(self, key):
        meta = self.open_tabs.get(key)
        if not meta:
            return
        self._stop_tool_runtime(meta)
        meta["host"] = self._new_tool_host()
        meta["state"] = "loading"
        meta["message"] = "Recargando desde GitHub..."
        self._download_tool_async(meta["tool"], key, force_remote=True)
        self._activate_tool_tab(key)

    def draw_tool_panel(self):
        """Mostrar estado solo mientras la herramienta no esta integrada."""
        meta = self.open_tabs.get(self.selected_top_tab)
        if not meta:
            return
        w, _ = self.size
        if meta.get("embedded"):
            return
        self.text(22, 85, self._ellipsize(meta["name"], w - 44, "label"),
                  "#173B50", "label")
        self.text(22, 119, self._ellipsize(meta.get("message", ""),
                  w - 44, "body"), "#546673", "body")
        if meta.get("state") in ("error", "ended"):
            self.text(22, 151, "Haz clic aqui para reintentar", "#176684", "tab")

    def _click_tool_panel(self, x, y, button):
        if button != 1 or not (115 <= y <= 160):
            return
        meta = self.open_tabs.get(self.selected_top_tab)
        if meta and meta.get("state") in ("error", "ended"):
            self._reload_tool_tab(self.selected_top_tab)

    def _resize_tool_windows(self):
        _, _, width, height = self._tool_view_rect()
        x, y, _, _ = self._tool_view_rect()
        for meta in self.open_tabs.values():
            host = meta.get("host")
            if host:
                self.resize(self.dpy, host, x, y, width, height)
            if meta.get("embedded") and meta.get("xid"):
                self.resize(self.dpy, meta["xid"], 0, 0, width, height)

    def _load_user_state(self):
        try:
            state = json.loads(self.state_file.read_text(encoding="utf-8"))
            if isinstance(state, dict):
                return {"recents": list(state.get("recents", []))[:10],
                        "favorites": list(state.get("favorites", [])),
                        "usage": dict(state.get("usage", {}))}
        except (OSError, ValueError, TypeError):
            pass
        return {"recents": [], "favorites": [], "usage": {}}

    def _save_user_state(self):
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            tmp = self.state_file.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.user_state, ensure_ascii=False),
                           encoding="utf-8")
            tmp.replace(self.state_file)
        except OSError as error:
            print("PYRION: estado de tools:", error, file=sys.stderr)

    @staticmethod
    def _normalize_text(value):
        text = unicodedata.normalize("NFKD", str(value or ""))
        text = "".join(c for c in text if not unicodedata.combining(c))
        return " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())

    def _accept_catalog(self, raw):
        reader = csv.DictReader(io.StringIO(raw), delimiter=";")
        fields = set(reader.fieldnames or [])
        required = {"slug", "titulo", "descripcion", "keywords", "categoria",
                    "version", "ruta", "activo", "visitas", "tipo_archivo",
                    "archivo_principal", "autor"}
        if not required.issubset(fields):
            raise ValueError("guide.csv PTM: encabezados no compatibles")
        catalog, seen = [], set()
        for row in reader:
            if not row or None in row:
                continue
            if str(row.get("activo", "")).strip().lower() not in (
                    "1", "true", "si", "sí", "yes", "activo"):
                continue
            rel = str(row.get("ruta", "")).strip().replace("\\", "/")
            parts = rel.split("/")
            typ = str(row.get("tipo_archivo", "")).lower().strip()
            if (len(parts) < 2 or parts[0] != "tools"
                    or any(p in ("", ".", "..") for p in parts)
                    or typ not in ("py", "zip")
                    or not rel.lower().endswith("." + typ)):
                continue
            key = str(row.get("slug", "")).strip()
            if not key or key in seen:
                continue
            seen.add(key)
            item = dict(row)
            item["key"] = key
            item["name"] = row.get("titulo", key).strip()
            item["repo_path"] = rel
            item["file_type"] = typ
            try:
                item["visits"] = int(row.get("visitas", 0) or 0)
            except ValueError:
                item["visits"] = 0
            item["search_fields"] = (
                (self._normalize_text(item["name"]), 50),
                (self._normalize_text(key), 40),
                (self._normalize_text(row.get("keywords")), 30),
                (self._normalize_text(row.get("categoria")), 20),
                (self._normalize_text(rel), 15),
                (self._normalize_text(row.get("descripcion")), 10),
                (self._normalize_text(row.get("autor")), 8),
                (self._normalize_text(row.get("dependencias")), 6),
            )
            catalog.append(item)
        self.catalog_tools = catalog
        self.catalog_status = str(len(catalog)) + " herramientas PTM disponibles"
        self.results_scroll = 0

    def _refresh_catalog_async(self, force=False):
        if self.catalog_fetching:
            return
        if not force and time.monotonic() - self.catalog_last_check < 90:
            return
        self.catalog_fetching = True
        self.catalog_last_check = time.monotonic()

        def worker():
            try:
                req = urllib.request.Request(
                    CATALOG_URL + "?t=" + str(time.time_ns()),
                    headers={"Cache-Control": "no-cache", "User-Agent": "PYRIONOS/" + APP_VERSION})
                with urllib.request.urlopen(req, timeout=7) as response:
                    data = response.read(400001)
                if len(data) > 400000:
                    raise ValueError("Catalogo demasiado grande")
                raw = data.decode("utf-8-sig")
                self.catalog_queue.put(("success", raw))
                try:
                    self.cache_dir.mkdir(parents=True, exist_ok=True)
                    tmp = self.catalog_cache.with_suffix(".tmp")
                    tmp.write_text(raw, encoding="utf-8")
                    tmp.replace(self.catalog_cache)
                except OSError:
                    pass
            except Exception as error:
                self.catalog_queue.put(("error", str(error)))
        threading.Thread(target=worker, daemon=True).start()

    def _init_catalog(self):
        candidates = (self.catalog_cache,
                      Path(__file__).resolve().parent / "guide.csv",
                      Path(__file__).resolve().parent.parent / "PTM" / "guide.csv")
        for path in candidates:
            try:
                self._accept_catalog(path.read_text(encoding="utf-8-sig"))
                break
            except (OSError, ValueError, UnicodeError):
                continue
        self._refresh_catalog_async(force=True)

    def _poll_catalog(self):
        dirty = False
        while True:
            try:
                action, value = self.catalog_queue.get_nowait()
            except queue.Empty:
                break
            self.catalog_fetching = False
            if action == "success":
                try:
                    self._accept_catalog(value)
                    dirty = True
                except (ValueError, TypeError) as error:
                    self.catalog_status = "Error de catalogo: " + str(error)[:100]
            elif not self.catalog_tools:
                self.catalog_status = "Sin conexion PTM: " + value[:85]
            if self.expand_after_update:
                self.show_all_results = True
                self.expand_after_update = False
                dirty = True
        return dirty

    def _search_matches(self):
        q = self.search_text.strip()
        if not q:
            return []
        by_key = {tool["key"]: tool for tool in self.catalog_tools}
        usage = self.user_state["usage"]
        commands = {
            "%todos%": sorted(self.catalog_tools, key=lambda t: t["name"].lower()),
            "%all%": sorted(self.catalog_tools, key=lambda t: t["name"].lower()),
            "%catalogo%": sorted(self.catalog_tools, key=lambda t: t["name"].lower()),
            "%recents%": [by_key[k] for k in self.user_state["recents"] if k in by_key],
            "%favorites%": [by_key[k] for k in self.user_state["favorites"] if k in by_key],
            "%used%": sorted((t for t in self.catalog_tools if int(usage.get(t["key"], 0)) > 0),
                             key=lambda t: -int(usage.get(t["key"], 0)))[:10],
            "%recommended%": sorted(self.catalog_tools, key=lambda t: -t["visits"])[:20],
        }
        if q.lower() in commands:
            return commands[q.lower()]
        normalized = self._normalize_text(q)
        if normalized in ("todos", "todas", "catalogo", "herramientas", "listar herramientas"):
            return commands["%todos%"]
        filler = {"quiero", "necesito", "puedes", "por", "favor", "abrir", "abre",
                  "ejecutar", "ejecuta", "usar", "un", "una", "el", "la",
                  "los", "las", "de", "del", "para", "con", "en", "mi",
                  "me", "al", "a", "que"}
        tokens = [t for t in normalized.split() if t not in filler]
        tokens = tokens or normalized.split()
        phrase = " ".join(tokens)
        hits = []
        for tool in self.catalog_tools:
            fields = tool["search_fields"]
            title, slug = fields[0][0], fields[1][0]
            score = (100 if phrase == title else 70 if title.startswith(phrase) else 0)
            score += (80 if phrase == slug else 55 if slug.startswith(phrase) else 0)
            for token in tokens:
                best = 0
                for field, weight in fields:
                    if token in field.split():
                        best = max(best, weight)
                    elif any(word.startswith(token) for word in field.split()):
                        best = max(best, int(weight * .9))
                    elif token in field:
                        best = max(best, int(weight * .7))
                if best == 0:
                    score = -1
                    break
                score += best
            if score >= 0:
                hits.append((score, tool["visits"], tool["name"].lower(), tool))
        hits.sort(key=lambda hit: (-hit[0], -hit[1], hit[2]))
        return [hit[3] for hit in hits]

    def _set_search_command(self, command):
        self.search_text = command[:MAX_SEARCH_CHARS]
        self.results_scroll = 0
        self.search_focus = True
        self.show_all_results = True
        self.paint()

    def _expand_results(self):
        if not self.search_text.strip():
            return
        self.results_scroll = 0
        self.search_focus = False
        # Igual que PTM: verificar guide remoto antes de mostrar el catalogo completo.
        if self.catalog_fetching:
            self.expand_after_update = True
        else:
            self.show_all_results = True
            self._refresh_catalog_async(force=True)
        self.paint()

    def _record_tool_open(self, tool):
        key = tool["key"]
        recents = self.user_state["recents"]
        if key in recents:
            recents.remove(key)
        recents.insert(0, key)
        del recents[10:]
        usage = self.user_state["usage"]
        usage[key] = int(usage.get(key, 0)) + 1
        self._save_user_state()

    def _toggle_favorite(self, tool):
        key = tool["key"]
        favorites = self.user_state["favorites"]
        if key in favorites:
            favorites.remove(key)
        else:
            favorites.append(key)
        self._save_user_state()
        self.paint()

    def add_top_tab(self, title):
        """Permite a futuras aplicaciones registrar su pestaña."""
        title = str(title).strip()[:80]
        if not title:
            return
        if title not in self.top_tabs:
            self.top_tabs.append(title)
        self.selected_top_tab = title
        if self.window and self.gc:
            self.paint()

    def _top_tabs_layout(self):
        """Geometría compartida por dibujo y detección de clics."""
        width = self.size[0]
        x, y, height, gap = 13, 16, 25, 7
        boxes = []
        for title in self.top_tabs:
            label = self.open_tabs[title]["name"] if title in self.open_tabs else title
            remaining = width - x - 13
            if remaining < 52:
                break
            natural = self.text_width(label, "tab") + 25
            tab_width = min(max(58, natural), 170, remaining)
            boxes.append((title, x, y, tab_width, height))
            x += tab_width + gap
        return boxes

    def draw_top_tabs(self):
        """Pestañas horizontales azul/rojo, con activa blanca y subrayada."""
        for title, x, y, width, height in self._top_tabs_layout():
            active = title == self.selected_top_tab
            fill = "#FFFFFF" if active else "#1D6684"
            fg = "#155773" if active else "#FFFFFF"
            self.rect(x, y, width, height, fill)
            if active:
                # Pestaña activa como la del ejemplo: borde azul y base roja.
                self.rect(x, y, width, 1, "#155773")
                self.rect(x, y, 1, height - 4, "#155773")
                self.rect(x + width - 1, y, 1, height - 4, "#155773")
                self.rect(x, y + height - 5, width, 5, "#FF1B1B")
            else:
                self.rect(x, y + height - 1, width, 1, "#164D64")

            # Corte rojo en diagonal en la esquina superior derecha.
            corner = 15
            for i in range(corner):
                self.rect(x + width - corner + i, y + i,
                          corner - i, 1, "#FF1B1B")

            full_label = self.open_tabs[title]["name"] if title in self.open_tabs else title
            label = full_label
            # Acortar solo cuando el texto REAL supera el espacio disponible.
            while label and self.text_width(label, "tab") > width - 18:
                label = label[:-1]
            if label != full_label and len(label) > 1:
                label = label[:-1] + "…"
            self.text(x + 9, y + 17, label, fg, "tab")

    def rounded_outline(self, x, y, w, h, radius=14, color="#111111"):
        """Borde fino de esquinas amplias y antialias sin dependencias extra.

        Los cuatro arcos se calculan con supermuestreo 4x4 y se mezclan
        con el fondo blanco del escritorio, evitando escalones de XDrawArc.
        """
        radius = max(2, min(int(radius), int(w) // 2, int(h) // 2))
        rgb = tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))
        self.rect(x + radius, y, w - 2 * radius, 1, color)
        self.rect(x + radius, y + h - 1, w - 2 * radius, 1, color)
        self.rect(x, y + radius, 1, h - 2 * radius, color)
        self.rect(x + w - 1, y + radius, 1, h - 2 * radius, color)

        outer = radius * radius
        inner = (radius - 1) * (radius - 1)
        for py in range(radius):
            for px in range(radius):
                covered = 0
                for sy in range(4):
                    dy = py + (sy + 0.5) / 4 - radius
                    for sx in range(4):
                        dx = px + (sx + 0.5) / 4 - radius
                        d2 = dx * dx + dy * dy
                        if inner <= d2 <= outer:
                            covered += 1
                if not covered:
                    continue
                # Tono intermedio para un contorno suave sobre blanco.
                shade = tuple(255 - round((255 - c) * covered / 16)
                              for c in rgb)
                tint = "#%02X%02X%02X" % shade
                self.rect(x + px, y + py, 1, 1, tint)
                self.rect(x + w - 1 - px, y + py, 1, 1, tint)
                self.rect(x + px, y + h - 1 - py, 1, 1, tint)
                self.rect(x + w - 1 - px, y + h - 1 - py, 1, 1, tint)

    def draw_tab_context_menu(self):
        info = self.tab_menu
        if not info or info["key"] not in self.open_tabs:
            return
        x, y = info["x"], info["y"]
        w, row_h = 171, 29
        favorites = self.user_state["favorites"]
        is_fav = info["key"] in favorites
        items = (("Quitar favorito" if is_fav else "Añadir favorito"),
                 "Recargar desde GitHub", "Cerrar pestaña")
        self.rect(x, y, w, len(items) * row_h, "#FFFFFF")
        self.rect(x, y, w, 1, "#C8D3DD")
        self.rect(x, y, 1, len(items) * row_h, "#C8D3DD")
        self.rect(x+w-1, y, 1, len(items)*row_h, "#C8D3DD")
        for index, label in enumerate(items):
            top = y + row_h * index
            if index:
                self.rect(x+1, top, w-2, 1, "#E7EDF1")
            self.text(x+10, top+19, label, "#173B50", "tab")

    def _tab_menu_action(self, x, y):
        info = self.tab_menu
        self.tab_menu = None
        if not info:
            return False
        mx, my, key = info["x"], info["y"], info["key"]
        if mx <= x < mx + 171 and my <= y < my + 87:
            meta = self.open_tabs.get(key)
            if not meta:
                return True
            choice = (y - my) // 29
            if choice == 0:
                self._toggle_favorite(meta["tool"])
            elif choice == 1:
                self._reload_tool_tab(key)
            else:
                self._close_tool_tab(key)
                return True
            self._activate_tool_tab(self.selected_top_tab)
            return True
        self._activate_tool_tab(self.selected_top_tab)
        return False

    def _result_geom(self):
        x, y, bw, bh = self._search_bounds()
        top = y + bh + 51
        bottom = max(top + 12, self.size[1] - 29)
        row_height = 68 if self.show_all_results else 38
        n_visible = max(1, (bottom - top - 10) // row_height)
        return x, top, bw, row_height, n_visible

    def _ellipsize(self, value, max_px, style="body"):
        text = str(value or "")
        if self.text_width(text, style) <= max_px:
            return text
        while text and self.text_width(text + "…", style) > max_px:
            text = text[:-1]
        return text + "…" if text else ""

    def draw_results(self):
        """Durante escritura: 5 compactos; Enter: todos con scroll y detalles."""
        self.results_click_areas = []
        if self.selected_top_tab != "PYRIONOS" or not self.search_text.strip():
            return
        x, top, bw, rh, max_rows = self._result_geom()
        matches = self._search_matches()
        visible = matches if self.show_all_results else matches[:5]
        if not visible:
            msg = ("Consultando herramientas PTM..." if self.catalog_fetching and
                   not self.catalog_tools else "Sin coincidencias")
            self.text(x + 6, top + 15, msg, "#5B6974", "tab")
            return
        scroll_max = max(0, len(visible) - max_rows)
        self.results_scroll = min(max(0, self.results_scroll), scroll_max)
        display = visible[self.results_scroll:self.results_scroll + max_rows]
        for index, tool in enumerate(display):
            ry = top + index * rh
            self.rect(x, ry, bw, rh - 4, "#F3F6F8")
            self.rect(x, ry, bw, 1, "#D8E0E7")
            self.rect(x, ry + rh - 5, bw, 1, "#D8E0E7")
            self.rect(x, ry, 1, rh - 4, "#D8E0E7")
            self.rect(x + bw - 1, ry, 1, rh - 4, "#D8E0E7")
            starred = tool["key"] in self.user_state["favorites"]
            name = ("* " if starred else "") + tool["name"]
            if self.show_all_results:
                self.text(x + 10, ry + 19, self._ellipsize(name, bw - 26, "label"),
                          "#172B40", "label")
                description = self._ellipsize(tool.get("descripcion", ""), bw - 26, "tab")
                self.text(x + 10, ry + 37, description, "#56636D", "tab")
                desc = (tool.get("categoria", "") + "  ·  v" +
                        tool.get("version", "") + "  ·  " +
                        str(tool["visits"]) + " visitas  ·  " + tool.get("autor", ""))
                self.text(x + 10, ry + 54, self._ellipsize(desc, bw - 26, "caption"),
                          "#677683", "caption")
            else:
                self.text(x + 10, ry + 24, self._ellipsize(name, bw - 180, "label"),
                          "#172B40", "label")
                meta = tool.get("categoria", "") + " · v" + tool.get("version", "")
                tw = self.text_width(meta, "caption")
                self.text(x + bw - min(bw - 15, tw + 10), ry + 24,
                          self._ellipsize(meta, 150, "caption"), "#56636D", "caption")
            self.results_click_areas.append((x, ry, bw, rh - 4, tool))
        if len(visible) > max_rows:
            tip = ("%s resultados · rueda del raton para desplazarse" % len(matches))
            self.text(x + 3, self.size[1] - 10, tip, "#607384", "caption")
        elif not self.show_all_results and len(matches) > 5:
            self.text(x + 3, self.size[1] - 10,
                      "%s coincidencias · mostrando 5 · Enter para ver todas" % len(matches),
                      "#607384", "caption")
        elif self.show_all_results:
            self.text(x + 3, self.size[1] - 10,
                      "%s coincidencias · clic derecho para favoritos" % len(matches),
                      "#607384", "caption")

    def _result_scroll(self, delta):
        if not self.search_text.strip() or self.selected_top_tab != "PYRIONOS":
            return
        _, _, _, _, rows = self._result_geom()
        matches = self._search_matches()
        shown = matches if self.show_all_results else matches[:5]
        max_scroll = max(0, len(shown) - rows)
        self.results_scroll = min(max(0, self.results_scroll + delta), max_scroll)
        self.paint()

    def draw_search(self):
        """Cabecera PYRIONOS, buscador y enlaces inspirados en el boceto."""
        x, y, bw, bh = self._search_bounds()
        # Logo centrado encima del buscador sobre el fondo blanco.
        logo_w, logo_h, gap = 226, 101, 14
        self.draw_pyrionos_logo(x + (bw - logo_w) // 2, y - logo_h - gap)

        # Contorno natural: radio de 14 px y esquinas suavizadas.
        self.rounded_outline(x, y, bw, bh, radius=14, color="#111111")

        # Etiqueta fija en negrita y separador alineado con su ancho real.
        self.text(x + 18, y + 27, "Buscar", "#111111", "label")
        separator_x = x + 18 + self.text_width("Buscar", "label") + 10
        self.pen("#9A9A9A")
        self.drawline(self.dpy, self.pixmap, self.gc,
                      separator_x, y + 11, separator_x, y + 33)

        # Entrada editable y boton X junto a la consulta (solo si hay texto).
        tx, visible, clear_x = self._search_input_layout()
        if visible:
            self.text(tx, y + 27, visible, "#111111", "body")
        caret_x = tx + self.text_width(visible, "body")
        if self.search_focus:
            self.pen("#111111")
            self.drawline(self.dpy, self.pixmap, self.gc,
                          caret_x + 1, y + 14, caret_x + 1, y + 30)
        if clear_x is not None:
            self.pen("#555555")
            self.drawline(self.dpy, self.pixmap, self.gc,
                          clear_x - 4, y + 18, clear_x + 4, y + 26)
            self.drawline(self.dpy, self.pixmap, self.gc,
                          clear_x + 4, y + 18, clear_x - 4, y + 26)

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

        for tab, tx_tab, tab_width in self._tab_layout():
            active = tab == self.active_tab
            style = "tab_active" if active else "tab"
            self.text(tx_tab, y + bh + 23, tab,
                      "#172B40" if active else "#424B54", style)
            # Subrayado sutil; solo resalta la pestaña seleccionada.
            if active:
                self.pen("#1D6684")
                self.drawline(self.dpy, self.pixmap, self.gc,
                              tx_tab, y + bh + 28,
                              tx_tab + tab_width, y + bh + 28)

    def click_ui(self, x, y, button=1):
        if button in (4, 5):
            self._result_scroll(-1 if button == 4 else 1)
            return
        if self.tab_menu and self._tab_menu_action(x, y):
            return
        for title, tx, ty, tw, th in self._top_tabs_layout():
            if tx <= x < tx + tw and ty <= y < ty + th:
                if title != "PYRIONOS" and button == 1 and x >= tx + tw - 20 and y <= ty + 19:
                    self._close_tool_tab(title)
                elif title != "PYRIONOS" and button == 3:
                    # Ocultar la ventana embebida para que el menu X11 quede visible.
                    active = self.open_tabs.get(self.selected_top_tab)
                    if active and active.get("host"):
                        self.unmap_window(self.dpy, active["host"])
                    self.tab_menu = {"key": title,
                                     "x": max(2, min(x, self.size[0]-182)),
                                     "y": max(42, min(y, self.size[1]-94))}
                    self.paint()
                else:
                    self._activate_tool_tab(title)
                return
        if self.selected_top_tab != "PYRIONOS":
            self._click_tool_panel(x, y, button)
            return
        for rx, ry, rw, rh, tool in self.results_click_areas:
            if rx <= x < rx + rw and ry <= y < ry + rh:
                if button == 3:
                    self._toggle_favorite(tool)
                elif button == 1:
                    self._open_tool(tool)
                return
        bx, by, bw, bh = self._search_bounds()
        if bx <= x < bx + bw and by <= y < by + bh:
            _, _, clear_x = self._search_input_layout()
            if clear_x is not None and abs(x - clear_x) <= 9 and abs(y - (by + 22)) <= 11:
                # La X borra solo la consulta y deja el cursor listo para escribir.
                self.search_text = ""
                self.search_focus = True
                self.show_all_results = False
                self.results_scroll = 0
            elif bx + bw - 84 <= x < bx + bw - 50:
                # Boton rojo equivale a Enter: todas las coincidencias PTM.
                self._expand_results()
                return
            elif x >= bx + bw - 47:
                # El icono de subir se conecta al gestor de archivos mas adelante.
                self.search_focus = False
            else:
                self.search_focus = True
            self.paint()
            return
        if by + bh + 6 <= y <= by + bh + 34:
            for tab, cursor, tab_width in self._tab_layout():
                if cursor <= x <= cursor + tab_width:
                    self.active_tab = tab
                    cmd = {"Recientes": "%recents%", "Favoritos": "%favorites%",
                           "Más usados": "%used%", "Recomendados": "%recommended%"}
                    self._set_search_command(cmd[tab])
                    return
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
            self._expand_results()
            return
        elif 0 < count <= 31:
            value = buffer.raw[:count].decode("utf-8", "ignore")
            if value.isprintable():
                available = MAX_SEARCH_CHARS - len(self.search_text)
                if available > 0:
                    self.search_text += value[:available]
        # Buscar durante la escritura: mostrar como maximo 5 sugerencias.
        self.show_all_results = False
        self.results_scroll = 0
        self.last_search_edit = time.monotonic()
        self.paint()

    def paint(self):
        """Dibuja fondo blanco y buscador centrado del escritorio."""
        w, h = self.size
        if self.pixmap:
            self.pixmap_free(self.dpy, self.pixmap)
        self.pixmap = self.pixmap_create(self.dpy, self.window, w, h, self.depth)
        self.rect(0, 0, w, h, "#FFFFFF")
        self.draw_top_tabs()
        if self.selected_top_tab == "PYRIONOS":
            self.draw_search()
            self.draw_results()
        else:
            self.draw_tool_panel()
        self.draw_tab_context_menu()
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
        self.logo_gc=self.gc_create(self.dpy,self.window,0,None)
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
        self._init_catalog()
        print("PYRION: escritorio con buscador PTM iniciado.", flush=True)

    def run(self):
        self.create()
        last_check=0
        while self.running:
            now=time.monotonic()
            if self._poll_catalog():
                self.paint()
            if (self.search_text.strip() and self.last_search_edit
                    and now - self.last_search_edit > 0.8
                    and now - self.catalog_last_check > 90):
                self._refresh_catalog_async()
            if self._poll_tools():
                self.paint()
            if now-last_check>1.2:
                new=(self.screen_w(self.dpy,self.screen),self.screen_h(self.dpy,self.screen))
                if new!=self.size:
                    self.size=new
                    self.resize(self.dpy,self.window,0,0,*new)
                    self.paint()
                    self._resize_tool_windows()
                self.lower(self.dpy,self.window)
                last_check=now
            if self.pending(self.dpy):
                ev=XEvent()
                self.next_event(self.dpy,C.byref(ev))
                if ev.type == 4:  # ButtonPress
                    self.click_ui(ev.xbutton.x, ev.xbutton.y, ev.xbutton.button)
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
        for key in list(self.open_tabs):
            self._close_tool_tab(key)
        if self.dpy:
            if self.pixmap:self.pixmap_free(self.dpy,self.pixmap)
            if self.logo_gc:self.gc_free(self.dpy,self.logo_gc)
            for font in self.ui_fonts.values():
                self.xft_font_close(self.dpy, font)
            if self.logo_xft_font:self.xft_font_close(self.dpy,self.logo_xft_font)
            if self.logo_core_font:self.free_font(self.dpy,self.logo_core_font)
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
