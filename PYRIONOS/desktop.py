#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PYRION OS - Escritorio X11 con buscador sobre fondo blanco.

La actualizacion en caliente mediante app.py sigue siendo compatible.
Python estandar + ctypes + libX11. Interfaz publica: PyrionDesktop y main().
"""
from __future__ import annotations

import ast
import importlib
import importlib.util
import importlib.metadata
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
APP_VERSION = "0.2.35-medidor-dependencias"
MAX_SEARCH_CHARS = 30
CATALOG_URL = "https://raw.githubusercontent.com/mobatfb/archmoba-dev/main/PTM/guide.csv"
TOOLS_URL = "https://raw.githubusercontent.com/mobatfb/archmoba-dev/main/PTM/"
PIP_BOOTSTRAP_URL = "https://bootstrap.pypa.io/get-pip.py"

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
        self.enter_refresh_queued = False
        self.expanded_loading = False
        self.expanded_notice = ""
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
        # Los paquetes se comparten entre herramientas, no modifican Python.
        self.deps_root = self.cache_dir / "python_runtime"
        self.deps_lib = self.deps_root / "packages"
        self.pip_lib = self.deps_root / "pip_bootstrap"
        self.deps_lock = threading.Lock()
        for dep_path in (self.deps_lib, self.pip_lib):
            if str(dep_path) not in sys.path:
                sys.path.insert(0, str(dep_path))
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
        bh = 44
        if self.show_all_results:
            # PTM al pulsar Enter: logo pequeño a la izquierda del buscador.
            if w >= 480:
                bw = min(500, max(260, w - 150))
                group_width = 110 + 12 + bw
                x = (w - group_width) // 2 + 122
                return x, 83, bw, bh
            bw = max(180, w - 24)
            return (w - bw) // 2, 133, bw, bh
        bw = max(260, min(500, w - 40))
        x = (w - bw) // 2
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

    def draw_pyrionos_logo_compact(self, x, y):
        """Logotipo pequeño del modo Enter, equivalente al logo PTM compacto."""
        width, height = 110, 50
        self.rect(x, y, width, height, "#1D6684")
        self.rect(x, y, width, 1, "#161616")
        self.rect(x, y, 1, height, "#161616")
        self.rect(x + width - 1, y, 1, height, "#161616")
        corner = 17
        for i in range(corner):
            self.rect(x + width - corner + i, y + i,
                      corner - i, 1, "#FF1B1B")
        caption = "PYRIONOS"
        left = x + (width - self.text_width(caption, "tab_active")) // 2
        self.text(left, y + 29, caption, "#FFFFFF", "tab_active")
        self.rect(x, y + height - 9, width, 9, "#FF1B1B")

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
        """PTM coloca los filtros debajo de la barra, a su izquierda en Enter."""
        x, _, bw, _ = self._search_bounds()
        tabs = ("Recientes", "Favoritos", "Más usados", "Recomendados")
        widths = [max(self.text_width(tab, "tab"),
                      self.text_width(tab, "tab_active")) for tab in tabs]
        gap = 18
        total = sum(widths) + gap * (len(tabs) - 1)
        cursor = x if self.show_all_results else x + (bw - total) // 2
        result = []
        for tab, width in zip(tabs, widths):
            result.append((tab, cursor, width))
            cursor += width + gap
        return result

    @staticmethod
    def _tk_launcher_source():
        """Proceso Tk embebido: autoajuste y zoom manual por cada pestaña."""
        return r'''#!/usr/bin/env python3
import ctypes as C
import ctypes.util
import importlib.util
import inspect
import json
import sys
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk, font as tkfont

tool_path = Path(sys.argv[1]).resolve()
xid_path = Path(sys.argv[2])
ready_path = Path(sys.argv[3])
control_path = Path(sys.argv[4])
status_path = Path(sys.argv[5])
initial_width = max(120, int(sys.argv[6]))
initial_height = max(100, int(sys.argv[7]))

root = tk.Tk()
root.withdraw()
root.overrideredirect(True)
root.configure(bg="#FFFFFF")
root.geometry("%dx%d" % (initial_width, initial_height))

viewport = {}
tool_widget = None

def ensure_viewport():
    if viewport:
        return viewport["host"]
    shell = tk.Frame(root, bg="#FFFFFF", bd=0)
    shell.pack(fill="both", expand=True)
    shell.columnconfigure(0, weight=1)
    shell.rowconfigure(0, weight=1)
    canvas = tk.Canvas(shell, bg="#FFFFFF", bd=0, highlightthickness=0)
    vbar = ttk.Scrollbar(shell, orient="vertical", command=canvas.yview)
    hbar = ttk.Scrollbar(shell, orient="horizontal", command=canvas.xview)
    canvas.configure(xscrollcommand=hbar.set, yscrollcommand=vbar.set)
    canvas.grid(row=0, column=0, sticky="nsew")
    host = tk.Frame(canvas, bg="#FFFFFF", bd=0)
    window_id = canvas.create_window(0, 0, window=host, anchor="nw")
    viewport.update(shell=shell, canvas=canvas, vbar=vbar, hbar=hbar,
                    host=host, window=window_id)
    canvas.bind("<Button-4>", lambda _e: canvas.yview_scroll(-3, "units"))
    canvas.bind("<Button-5>", lambda _e: canvas.yview_scroll(3, "units"))
    canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(
        -3 if e.delta > 0 else 3, "units"))
    return host

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
    for name in ("App", "Application", "create_tool",
                 "create_app", "build_app", "build_ui"):
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
        parent = ensure_viewport()
        params = tuple(inspect.signature(entry).parameters.values())
        positional = [p for p in params if p.kind in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD)]
        varargs = any(p.kind == inspect.Parameter.VAR_POSITIONAL
                      for p in params)
        if varargs or len(positional) >= 2:
            widget = entry(parent, Bridge())
        elif len(positional) == 1:
            widget = entry(parent)
        else:
            widget = entry()
        if isinstance(widget, (tuple, list)):
            widget = widget[0] if widget else None
        if not isinstance(widget, tk.Widget):
            raise RuntimeError("La herramienta no devolvio un widget Tk")
        if not widget.winfo_manager():
            widget.pack(fill="both", expand=True)
        return widget

    main = getattr(module, "main", None)
    if not callable(main):
        raise RuntimeError("La herramienta necesita App, create_tool o main")
    real_tk, real_mainloop, loop = tk.Tk, tk.mainloop, root.mainloop
    try:
        tk.Tk = lambda *args, **kwargs: root
        tk.mainloop = lambda *args, **kwargs: None
        root.mainloop = lambda *args, **kwargs: None
        main()
    finally:
        tk.Tk, tk.mainloop, root.mainloop = real_tk, real_mainloop, loop
    return root

class ZoomController:
    """Ajuste 50-100%; manual 50-125%, conserva estado en este proceso."""
    def __init__(self, widget, width, height):
        self.widget = widget
        self.width = int(width)
        self.height = int(height)
        self.mode = "fit"
        self.factor = 1.0
        self.last_seq = -1
        self.state = []
        self.fonts = []
        self.styles = []
        self.last_size = (self.width, self.height)
        self.refresh_job = None
        self._adjusting = False
        root.update_idletasks()
        area = viewport.get("host") or widget
        self.natural_w = max(1, int(area.winfo_reqwidth()),
                             int(widget.winfo_reqwidth()))
        self.natural_h = max(1, int(area.winfo_reqheight()),
                             int(widget.winfo_reqheight()))
        self.capture(widget)
        self.update("fit", width, height)

        if viewport:
            viewport["canvas"].bind("<Configure>", self.on_viewport_size, add="+")

    def capture(self, parent):
        stack = [parent]
        seen = set()
        while stack:
            w = stack.pop()
            if w in seen:
                continue
            seen.add(w)
            try:
                stack.extend(w.winfo_children())
                keys = set(w.keys())
            except Exception:
                continue
            data = {"widget": w, "font": None, "options": {},
                    "manager": "", "pad": {}, "style": None}
            if "font" in keys:
                try:
                    font = tkfont.Font(root=root, font=w.cget("font"))
                    data["font"] = font.actual()
                except Exception:
                    pass
            for option in ("width", "height", "padx", "pady", "padding",
                           "wraplength"):
                if option in keys:
                    try:
                        data["options"][option] = w.cget(option)
                    except Exception:
                        pass
            try:
                data["manager"] = w.winfo_manager()
                if data["manager"] == "grid":
                    info = w.grid_info()
                elif data["manager"] == "pack":
                    info = w.pack_info()
                elif data["manager"] == "place":
                    info = w.place_info()
                else:
                    info = {}
                data["pad"] = {k: info[k] for k in
                               ("padx", "pady", "ipadx", "ipady",
                                "x", "y", "width", "height") if k in info}
            except Exception:
                pass
            if isinstance(w, ttk.Widget):
                try:
                    style = ttk.Style(root)
                    base = str(w.cget("style") or "").strip() or w.winfo_class()
                    custom = "PYZoom%d.%s" % (len(self.state), w.winfo_class())
                    config = dict(style.configure(base) or {})
                    if config:
                        style.configure(custom, **config)
                    mapped = dict(style.map(base) or {})
                    if mapped:
                        style.map(custom, **mapped)
                    layout = style.layout(base)
                    if layout:
                        style.layout(custom, layout)
                    font_value = style.lookup(base, "font")
                    data["style"] = {
                        "custom": custom,
                        "font": (tkfont.Font(root=root, font=font_value).actual()
                                 if font_value else None),
                        "padding": style.lookup(base, "padding"),
                        "rowheight": style.lookup(base, "rowheight"),
                    }
                except Exception:
                    pass
            if isinstance(w, ttk.Treeview):
                try:
                    show = str(w.cget("show"))
                    cols = (["#0"] if "tree" in show else [])
                    cols += list(w.tk.splitlist(w.cget("columns")))
                    data["tree_columns"] = {
                        col: (int(w.column(col, "width")),
                              int(w.column(col, "minwidth")))
                        for col in cols
                    }
                except (tk.TclError, ValueError, TypeError):
                    pass
            self.state.append(data)

    @staticmethod
    def scalar(value, factor, min_value=0):
        try:
            return max(min_value, int(round(float(value) * factor)))
        except (ValueError, TypeError):
            return value

    @staticmethod
    def padding(value, factor):
        try:
            parts = root.tk.splitlist(value)
            output = [str(max(0, round(float(p) * factor))) for p in parts]
            return " ".join(output) if output else value
        except (ValueError, TypeError, tk.TclError):
            return value

    def font_value(self, info, factor):
        size = int(info.get("size", 10) or 10)
        sign = -1 if size < 0 else 1
        size = sign * max(5, round(abs(size) * factor))
        return (info.get("family", "DejaVu Sans"), size,
                info.get("weight", "normal"), info.get("slant", "roman"))

    def scale(self, factor):
        self.fonts.clear()
        style = ttk.Style(root)
        for info in self.state:
            w = info["widget"]
            try:
                if not w.winfo_exists():
                    continue
            except Exception:
                continue
            if info["font"]:
                try:
                    font = tkfont.Font(root=root, font=self.font_value(info["font"], factor))
                    self.fonts.append(font)
                    w.configure(font=font)
                except Exception:
                    pass
            for option, value in info["options"].items():
                try:
                    if option in ("padx", "pady", "padding"):
                        scaled = self.padding(value, factor)
                    elif option in ("width", "height") and str(value).strip() in ("", "0"):
                        continue
                    else:
                        scaled = self.scalar(value, factor, 1 if option in ("width", "height") else 0)
                    w.configure(**{option: scaled})
                except Exception:
                    pass
            styling = info["style"]
            if styling:
                changes = {}
                if styling.get("font"):
                    changes["font"] = self.font_value(styling["font"], factor)
                if styling.get("padding"):
                    changes["padding"] = self.padding(styling["padding"], factor)
                if styling.get("rowheight"):
                    changes["rowheight"] = self.scalar(styling["rowheight"], factor, 1)
                try:
                    if changes:
                        style.configure(styling["custom"], **changes)
                    w.configure(style=styling["custom"])
                except Exception:
                    pass
            if info.get("tree_columns"):
                for col, (base_width, base_minimum) in info["tree_columns"].items():
                    try:
                        w.column(col,
                            width=max(30, int(round(base_width * factor))),
                            minwidth=max(16, int(round(base_minimum * factor))),
                            stretch=True)
                    except tk.TclError:
                        pass
            mgr = info["manager"]
            changes = {}
            for attr, value in info["pad"].items():
                if attr in ("padx", "pady", "ipadx", "ipady"):
                    changes[attr] = self.padding(value, factor)
                elif mgr == "place":
                    changes[attr] = self.scalar(value, factor)
            try:
                if mgr == "pack" and changes:
                    w.pack_configure(**changes)
                elif mgr == "grid" and changes:
                    w.grid_configure(**changes)
                elif mgr == "place" and changes:
                    w.place_configure(**changes)
            except Exception:
                pass
        self.factor = factor
        root.update_idletasks()

    def _available_viewport(self):
        """Tamaño real disponible: no confundir ancho solicitado con ancho visible."""
        canvas = viewport["canvas"]
        actual_w, actual_h = canvas.winfo_width(), canvas.winfo_height()
        width = self.width if actual_w < 100 else min(self.width, actual_w)
        height = self.height if actual_h < 90 else min(self.height, actual_h)
        return max(90, width - 4), max(80, height - 4)

    def _fit_treeview_columns(self):
        """Distribuir las columnas Treeview dentro de su ancho real."""
        for info in self.state:
            columns = info.get("tree_columns")
            if not columns:
                continue
            widget = info["widget"]
            try:
                if not widget.winfo_exists():
                    continue
                available = max(70, widget.winfo_width() - 12)
                sizes = {
                    col: max(30, int(round(base_w * self.factor)))
                    for col, (base_w, _minimum) in columns.items()
                }
                total = sum(sizes.values())
                if total <= 0:
                    continue
                ratio = min(1.0, available / total)
                for col, orig in sizes.items():
                    target = max(28, int(round(orig * ratio)))
                    widget.column(col, width=target, minwidth=24, stretch=True)
            except (tk.TclError, ValueError, TypeError):
                continue

    def _layout_overflow(self, width, height):
        """Detecta controles realmente fuera del viewport, como hace PTM."""
        host = viewport["host"]
        host.update_idletasks()
        req_w = max(1, int(host.winfo_reqwidth()))
        req_h = max(1, int(host.winfo_reqheight()))
        if not root.winfo_ismapped():
            return req_w > width + 8, req_h > height + 8
        try:
            origin_x = host.winfo_rootx()
            origin_y = host.winfo_rooty()
        except tk.TclError:
            return req_w > width + 8, req_h > height + 8
        x_over = False
        y_over = False
        # Los lienzos y areas desplazables ya administran su propio contenido.
        exempt = (tk.Canvas, tk.Text, tk.Listbox, tk.Scrollbar,
                  ttk.Scrollbar, tk.Scale, ttk.Scale, ttk.Treeview)
        interactive = (tk.Button, ttk.Button, tk.Entry, ttk.Entry,
                       tk.Checkbutton, ttk.Checkbutton,
                       tk.Radiobutton, ttk.Radiobutton, ttk.Combobox)
        stack = [self.widget]
        while stack:
            child = stack.pop()
            try:
                stack.extend(child.winfo_children())
                if isinstance(child, exempt) or not child.winfo_ismapped():
                    continue
                cw = int(child.winfo_width())
                ch = int(child.winfo_height())
                if cw <= 1 or ch <= 1:
                    continue
                dx = int(child.winfo_rootx()) - origin_x
                dy = int(child.winfo_rooty()) - origin_y
                if dx + cw > width + 5 or dx < -5:
                    x_over = True
                if dy + ch > height + 5:
                    y_over = True
                if isinstance(child, interactive):
                    if int(child.winfo_reqwidth()) > cw + 12:
                        x_over = True
                    if int(child.winfo_reqheight()) > ch + 10:
                        y_over = True
            except tk.TclError:
                continue
            if x_over and y_over:
                break
        return x_over, y_over

    def manage_scroll(self, fallback=False):
        """Primero fuerza el ancho disponible; scroll solo si no hay alternativa."""
        if not viewport:
            return False, False
        canvas, host = viewport["canvas"], viewport["host"]
        hbar, vbar = viewport["hbar"], viewport["vbar"]
        try:
            hbar.grid_remove()
            vbar.grid_remove()
            canvas.update_idletasks()
            width, height = self._available_viewport()
            # Este es el cambio clave: no imponer host.winfo_reqwidth().
            canvas.itemconfigure(viewport["window"], width=width, height=height)
            canvas.configure(scrollregion=(0, 0, width, height))
            host.update_idletasks()
            if self.mode == "fit":
                self._fit_treeview_columns()
                host.update_idletasks()
            over_x, over_y = self._layout_overflow(width, height)
            if not fallback:
                return over_x, over_y

            # Recalcular al habilitar el scroll vertical, que consume ancho.
            if over_y:
                vbar.grid(row=0, column=1, sticky="ns")
                canvas.update_idletasks()
                width, height = self._available_viewport()
                canvas.itemconfigure(viewport["window"], width=width,
                                     height=height)
                host.update_idletasks()
                if self.mode == "fit":
                    self._fit_treeview_columns()
                over_x, _ = self._layout_overflow(width, height)

            # Horizontal únicamente para interfaces de tamaño fijo imposible
            # de ajustar. No habilitarlo por la anchura solicitada de host.
            if over_x:
                hbar.grid(row=1, column=0, sticky="ew")
                canvas.update_idletasks()
                width, height = self._available_viewport()

            requested_w = max(width, int(host.winfo_reqwidth())) if over_x else width
            requested_h = max(height, int(host.winfo_reqheight())) if over_y else height
            canvas.itemconfigure(viewport["window"],
                                 width=requested_w, height=requested_h)
            canvas.configure(scrollregion=(0, 0, requested_w, requested_h))
            return over_x, over_y
        except (tk.TclError, ValueError, TypeError):
            return False, False

    def write_status(self):
        info = {"zoom": round(self.factor, 4), "mode": self.mode,
                "ready": True, "natural": [self.natural_w, self.natural_h],
                "viewport": [self.width, self.height]}
        try:
            tmp = status_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(info), encoding="utf-8")
            tmp.replace(status_path)
        except OSError:
            pass

    def update(self, action, width=None, height=None, value=None):
        """Comprime el layout al ancho disponible antes de ofrecer scroll."""
        if self._adjusting:
            return
        self._adjusting = True
        try:
            if width is not None:
                self.width = max(120, int(width))
            if height is not None:
                self.height = max(100, int(height))
            self.last_size = (self.width, self.height)
            if action == "fit":
                self.mode = "fit"
            elif action == "zoom":
                self.mode = "manual"

            if self.mode == "fit":
                factor = min(1.0, self.width / self.natural_w,
                             self.height / self.natural_h)
                if factor < 0.995:
                    factor *= 0.97
                factor = max(0.50, min(1.0, factor))
            elif action == "zoom" and value is not None:
                factor = max(0.50, min(1.25, float(value)))
            else:
                factor = self.factor

            for attempt in range(8):
                if abs(factor - self.factor) > 0.002:
                    self.scale(factor)
                self.factor = factor
                over_x, over_y = self.manage_scroll(fallback=False)

                # Igual que PTM: reducir varias veces antes de mostrar barras.
                if (self.mode == "fit" and (over_x or over_y)
                        and factor > 0.501 and attempt < 7):
                    reduced = max(0.50, factor * 0.92)
                    if abs(reduced - factor) > 0.002:
                        factor = reduced
                        continue
                break

            self.manage_scroll(fallback=True)
            self.write_status()
        finally:
            self._adjusting = False

    def on_viewport_size(self, event):
        """Solo recalcular al cambiar la ventana, no por las scrollbars."""
        if self._adjusting:
            return
        try:
            size = (max(120, int(root.winfo_width())),
                    max(100, int(root.winfo_height())))
        except tk.TclError:
            return
        if abs(size[0] - self.width) < 6 and abs(size[1] - self.height) < 6:
            return
        if self.refresh_job:
            try:
                root.after_cancel(self.refresh_job)
            except tk.TclError:
                pass
        self.refresh_job = root.after(
            100, lambda: self.update("resize", size[0], size[1]))

    def poll_commands(self):
        try:
            event = json.loads(control_path.read_text(encoding="utf-8"))
            seq = int(event.get("seq", -1))
            if seq > self.last_seq:
                self.last_seq = seq
                self.update(event.get("action", "resize"),
                            event.get("width"), event.get("height"),
                            event.get("value"))
        except (OSError, ValueError, TypeError, KeyError):
            pass
        root.after(150, self.poll_commands)

def get_outer_xid():
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
    tool_widget = run_tool()
except Exception as error:
    traceback.print_exc()
    if viewport:
        viewport["shell"].destroy()
        viewport.clear()
    for child in root.winfo_children():
        child.destroy()
    tk.Label(root, text="No se pudo cargar la herramienta",
             fg="#BD2020", font=("DejaVu Sans", 14, "bold")).pack(pady=24)
    tk.Label(root, text=str(error), fg="#374151", wraplength=650,
             justify="left").pack(padx=20)
    tool_widget = root

root.update_idletasks()
zoom = ZoomController(tool_widget, initial_width, initial_height)
root.geometry("%dx%d" % (initial_width, initial_height))
root.update_idletasks()
root.update()
xid_path.write_text(str(get_outer_xid()), encoding="ascii")

def wait_for_host():
    if ready_path.exists():
        root.deiconify()
        root.update_idletasks()
        # La geometria real existe despues del reparent/map: recalcularla.
        root.after(80, lambda: zoom.update(
            "resize", root.winfo_width(), root.winfo_height()))
        zoom.poll_commands()
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
        meta["deps_progress"] = 0
        meta["deps_progress_visible"] = True
        local = self.cache_dir / "tools" / self._tool_safe_id(key) / Path(tool["repo_path"]).name
        version_file = local.with_name(local.name + ".version")
        requested_version = str(tool.get("version", "")).strip()
        def worker():
            try:
                # Consultar la versión del guide: nunca ejecutar una copia antigua
                # después de actualizar una herramienta en GitHub.
                refresh = force_remote or not local.is_file()
                if not refresh:
                    try:
                        installed = version_file.read_text(encoding="utf-8").strip()
                        refresh = installed != requested_version
                    except OSError:
                        refresh = True
                if refresh:
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
                    version_tmp = version_file.with_suffix(version_file.suffix + ".tmp")
                    version_tmp.write_text(requested_version, encoding="utf-8")
                    version_tmp.replace(version_file)
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

    @staticmethod
    def _distribution_name(spec):
        return re.split(r"[<>=!~\[]", str(spec or "").strip(), 1)[0].strip()

    @staticmethod
    def _import_to_package(module):
        mapping = {
            "PIL": "Pillow", "cv2": "opencv-python",
            "sklearn": "scikit-learn", "yaml": "PyYAML",
            "bs4": "beautifulsoup4", "docx": "python-docx",
            "pptx": "python-pptx", "fitz": "PyMuPDF",
            "serial": "pyserial", "dateutil": "python-dateutil",
            "dotenv": "python-dotenv", "Crypto": "pycryptodome",
            "imageio_ffmpeg": "imageio-ffmpeg",
            "vlc": "python-vlc", "ffmpeg": "ffmpeg-python",
            "pkg_resources": "setuptools<81",
            "win32api": "pywin32", "win32com": "pywin32",
            "pythoncom": "pywin32", "System": "pythonnet",
            "clr": "pythonnet",
        }
        return mapping.get(module, module)

    def _compatible_package(self, spec):
        """Equivalencias de PTM, ajustadas para MiniLinux."""
        value = str(spec).strip()
        name = self._distribution_name(value).lower()
        if os.name != "nt" and name == "opencv-python":
            # Grabador usa VideoWriter, no cv2.imshow: evita Qt/GL innecesario.
            return re.sub(r"(?i)^opencv-python", "opencv-python-headless",
                          value, count=1)
        if os.name != "nt" and name == "pywebview":
            return re.sub(r"(?i)^pywebview(?:\[[^\]]*\])?",
                          "pywebview[qt]", value, count=1)
        if sys.version_info >= (3, 14) and name == "pygame":
            return "pygame-ce"
        return value

    @staticmethod
    def _local_import(module_name, path):
        return ((path.parent / (module_name + ".py")).is_file()
                or (path.parent / module_name / "__init__.py").is_file()
                or (path.parent / module_name).is_dir())

    @staticmethod
    def _extract_python_imports(path):
        """AST: analiza imports, incluidos los usados dentro de funciones."""
        source = path.read_text(encoding="utf-8-sig")
        tree = ast.parse(source, filename=str(path))
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:
                    names.add(node.module.split(".")[0])
        return names

    @staticmethod
    def _module_available(module):
        try:
            return importlib.util.find_spec(module) is not None
        except (ImportError, ValueError, AttributeError, OSError):
            return False

    def _dist_available(self, spec):
        name = self._distribution_name(spec)
        if not name:
            return True
        module_by_dist = {
            "pillow": "PIL", "opencv-python": "cv2",
            "opencv-python-headless": "cv2",
            "scikit-learn": "sklearn", "pyyaml": "yaml",
            "beautifulsoup4": "bs4", "python-docx": "docx",
            "python-pptx": "pptx", "pymupdf": "fitz",
            "pyserial": "serial", "python-dateutil": "dateutil",
            "python-dotenv": "dotenv", "pycryptodome": "Crypto",
            "imageio-ffmpeg": "imageio_ffmpeg",
            "python-vlc": "vlc", "ffmpeg-python": "ffmpeg",
            "pywebview": "webview", "pygame-ce": "pygame",
        }
        lowered = name.lower()
        name_to_check = module_by_dist.get(lowered,
            name.replace("-", "_"))
        if lowered == "pywebview" and os.name != "nt":
            return (self._module_available("webview")
                    and (self._module_available("PyQt6.QtWebEngineWidgets")
                         or self._module_available("PySide6.QtWebEngineWidgets")
                         or self._module_available("PyQt5.QtWebEngineWidgets")))
        if lowered in module_by_dist:
            return self._module_available(name_to_check)
        if self._module_available(name_to_check):
            return True
        try:
            importlib.metadata.distribution(name)
            return True
        except (importlib.metadata.PackageNotFoundError,
                ValueError, ImportError):
            return False

    def _missing_tool_dependencies(self, tool, file_path):
        """Cruza dependencias del guide y los imports reales del .py."""
        declared = str(tool.get("dependencias") or "").strip()
        declared_specs = [p.strip() for p in re.split(r"[;,\n]+", declared)
                          if p.strip()]
        required = []
        recorded = set()
        def add(package):
            package = self._compatible_package(package)
            key = self._distribution_name(package).lower().replace("_", "-")
            if key and key not in recorded and not self._dist_available(package):
                required.append(package)
                recorded.add(key)

        for package in declared_specs:
            # Referencias a otros archivos .py del repositorio no son paquetes pip.
            if package.lower().endswith(".py"):
                continue
            add(package)

        stdlib = set(getattr(sys, "stdlib_module_names", ()))
        stdlib.update({"tkinter", "os", "sys", "ctypes", "pathlib",
                       "threading", "time", "typing", "queue", "json",
                       "subprocess", "datetime", "asyncio", "importlib"})
        linux_only_skip = {"msvcrt", "winreg", "winsound", "win32api",
                           "win32com", "pythoncom", "win32gui", "win32con"}
        for module in sorted(self._extract_python_imports(file_path)):
            if module in stdlib:
                continue
            if os.name != "nt" and module in linux_only_skip:
                continue
            if self._local_import(module, file_path):
                continue
            if self._module_available(module):
                continue
            add(self._import_to_package(module))
        return required

    def _deps_python_env(self):
        env = os.environ.copy()
        paths = [str(self.deps_lib), str(self.pip_lib)]
        if env.get("PYTHONPATH"):
            paths.append(env["PYTHONPATH"])
        env["PYTHONPATH"] = os.pathsep.join(paths)
        env["PYTHONUNBUFFERED"] = "1"
        return env

    def _deps_status(self, key, token, message, progress=None):
        """Notificar progreso real por etapas, sin calcular porcentajes por tiempo."""
        event = {"token": token, "message": str(message)}
        if progress is not None:
            event["progress"] = max(0, min(100, int(progress)))
        self.tool_events.put(("deps_status", key, event))

    @staticmethod
    def _pip_observed_stage(log_path):
        """Solo indicios del registro de pip, no una estimacion temporal."""
        try:
            output = log_path.read_text(
                encoding="utf-8", errors="replace")[-16000:].lower()
        except OSError:
            return 0.0
        if "successfully installed" in output:
            return 0.98
        if "installing collected packages:" in output:
            return 0.83
        if "building wheel" in output or "preparing metadata" in output:
            return 0.44
        if "downloading" in output or "using cached" in output:
            return 0.32
        if "collecting " in output or "looking in indexes:" in output:
            return 0.16
        return 0.0

    def _pip_works(self, env):
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "--version"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                env=env, timeout=20, check=False)
            return result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False

    def _ensure_pip(self, key, token):
        """Usa pip, ensurepip y get-pip oficial como PTM para Python mínimos."""
        env = self._deps_python_env()
        if self._pip_works(env):
            return env
        self.deps_root.mkdir(parents=True, exist_ok=True)
        self._deps_status(key, token, "Python no incluye pip. Preparando instalador...", 6)
        details = []
        try:
            cmd = [sys.executable, "-m", "ensurepip", "--upgrade"]
            if os.name != "nt":
                cmd.append("--user")
            completed = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, errors="replace", env=env, timeout=160)
            if completed.stdout:
                details.append(completed.stdout[-650:])
            if self._pip_works(env):
                return env
        except (OSError, subprocess.TimeoutExpired) as error:
            details.append("ensurepip: " + str(error))

        self._deps_status(key, token, "Descargando pip para MiniLinux...", 8)
        bootstrap = self.deps_root / "get-pip.py"
        try:
            request = urllib.request.Request(
                PIP_BOOTSTRAP_URL, headers={"User-Agent": "PYRIONOS/" + APP_VERSION})
            with urllib.request.urlopen(request, timeout=30) as reply:
                data = reply.read(4_000_001)
            if not data or len(data) > 4_000_000:
                raise RuntimeError("Bootstrap pip inválido o demasiado grande")
            bootstrap.write_bytes(data)
            self.pip_lib.mkdir(parents=True, exist_ok=True)
            completed = subprocess.run([
                sys.executable, str(bootstrap), "--disable-pip-version-check",
                "--no-warn-script-location", "--target", str(self.pip_lib),
            ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, errors="replace", env=env, timeout=600)
            if completed.stdout:
                details.append(completed.stdout[-850:])
            importlib.invalidate_caches()
            if self._pip_works(self._deps_python_env()):
                return self._deps_python_env()
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
            details.append("get-pip: " + str(error))
        finally:
            try:
                bootstrap.unlink(missing_ok=True)
            except OSError:
                pass
        raise RuntimeError(
            "No se pudo preparar pip en Python. " +
            (" | ".join(details)[-1200:] or "Verifica la conexión a Internet."))

    def _install_package(self, key, token, name, index, total, env):
        """Avanza por etapas confirmadas de pip y paquetes terminados."""
        self.deps_lib.mkdir(parents=True, exist_ok=True)
        # Del 12% al 92% se reparte entre los paquetes pendientes.
        base = 12.0 + (index - 1) * 80.0 / max(1, total)
        span = 80.0 / max(1, total)
        log_path = self.deps_root / ("pip-" + self._tool_safe_id(key) + ".log")
        for attempt in range(1, 6):
            self._deps_status(
                key, token,
                "Instalando %s (%d/%d), intento %d/5..." %
                (name, index, total, attempt), base)
            command = [
                sys.executable, "-m", "pip", "install", "--no-input",
                "--disable-pip-version-check", "--prefer-binary",
                "--upgrade", "--target", str(self.deps_lib), name,
            ]
            try:
                with log_path.open("wb") as output:
                    proc = subprocess.Popen(command, stdout=output,
                                            stderr=subprocess.STDOUT, env=env)
                    start = time.monotonic()
                    next_message = start + 2.0
                    while proc.poll() is None:
                        if time.monotonic() - start > 600:
                            proc.kill()
                            proc.wait(timeout=10)
                            raise TimeoutError("pip superó 10 minutos")
                        if time.monotonic() >= next_message:
                            elapsed = int(time.monotonic() - start)
                            observed = self._pip_observed_stage(log_path)
                            self._deps_status(key, token,
                                "Descargando/instalando %s (%d/%d): %ds" %
                                (name, index, total, elapsed),
                                base + span * observed)
                            next_message = time.monotonic() + 2.0
                        time.sleep(0.2)
                    result = proc.returncode
                if result == 0:
                    importlib.invalidate_caches()
                    self._deps_status(
                        key, token,
                        "Paquete %d/%d instalado: %s" % (index, total, name),
                        base + span)
                    return
                tail = log_path.read_text(
                    encoding="utf-8", errors="replace")[-900:]
                error = "pip devolvió %d: %s" % (result, tail.strip())
            except (OSError, subprocess.TimeoutExpired, TimeoutError) as exc:
                error = str(exc)
            if attempt < 5:
                time.sleep(2)
        raise RuntimeError(
            "No se pudo instalar %s tras 5 intentos. %s" %
            (name, error[-900:]))

    def _prepare_tool_async(self, tool, key, filename):
        """No ejecutar el .py hasta resolver imports y guide.csv."""
        meta = self.open_tabs.get(key)
        if not meta:
            return
        token = int(meta.get("deps_token", 0)) + 1
        meta["deps_token"] = token
        meta["state"] = "preparing"
        meta["message"] = "Comparando imports y dependencias..."
        meta["deps_progress"] = 0
        meta["deps_progress_visible"] = True
        def worker():
            try:
                path = Path(filename).resolve()
                missing = self._missing_tool_dependencies(tool, path)
                self._deps_status(
                    key, token,
                    ("Faltan: " + ", ".join(missing)) if missing else
                    "Todos los imports estan disponibles.", 5)
                if missing:
                    # Pip modifica un entorno compartido: no ejecutar
                    # dos instalaciones simultáneamente.
                    with self.deps_lock:
                        missing = self._missing_tool_dependencies(tool, path)
                        if missing:
                            env = self._ensure_pip(key, token)
                            self._deps_status(
                                key, token, "Instalador pip listo.", 12)
                            for index, package in enumerate(missing, 1):
                                # Otra wheel pudo traer esta dependencia como
                                # transitiva: evitar instalaciones duplicadas.
                                if not self._dist_available(package):
                                    self._install_package(
                                        key, token, package, index,
                                        len(missing), env)
                                else:
                                    self._deps_status(
                                        key, token,
                                        "Dependencia disponible: " + package,
                                        12.0 + index * 80.0 / len(missing))
                            self._deps_status(
                                key, token, "Verificando dependencias...", 95)
                            importlib.invalidate_caches()
                            missing = self._missing_tool_dependencies(tool, path)
                            if missing:
                                raise RuntimeError(
                                    "Tras instalar faltan: " + ", ".join(missing))
                self._deps_status(
                    key, token, "Dependencias instaladas y verificadas.", 100)
                self.tool_events.put(("deps_ready", key,
                    {"token": token, "filename": str(path)}))
            except Exception as error:
                self.tool_events.put(("deps_failed", key,
                    {"token": token, "message": str(error)}))
        threading.Thread(target=worker, daemon=True).start()

    def _tool_view_rect(self):
        """Área útil: bajo las pestañas; nunca cubre la barra superior."""
        w, h = self.size
        return 6, 51, max(120, w - 12), max(100, h - 99)

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

    def _zoom_files(self, key):
        label = self._tool_safe_id(key)
        return (self.cache_dir / ("zoom_" + label + ".control.json"),
                self.cache_dir / ("zoom_" + label + ".status.json"))

    def _send_zoom_action(self, key, action, value=None):
        meta = self.open_tabs.get(key)
        if not meta or not meta.get("process") or not meta.get("zoom_control"):
            return
        control = meta["zoom_control"]
        _, _, width, height = self._tool_view_rect()
        seq = int(meta.get("zoom_seq", 0)) + 1
        cmd = {"seq": seq, "action": action,
               "width": width, "height": height}
        if value is not None:
            cmd["value"] = round(max(.5, min(1.25, float(value))), 4)
        try:
            tmp = control.with_suffix(".tmp")
            tmp.write_text(json.dumps(cmd), encoding="utf-8")
            tmp.replace(control)
        except OSError as error:
            print("PYRION: zoom:", error, file=sys.stderr)
            return
        meta["zoom_seq"] = seq

    def _change_tool_zoom(self, key, delta=None, fit=False):
        meta = self.open_tabs.get(key)
        if not meta or not meta.get("zoom_ready"):
            return
        if fit:
            meta["zoom_mode"] = "fit"
            self._send_zoom_action(key, "fit")
        else:
            factor = max(.5, min(1.25, float(meta.get("zoom", 1.0)) + delta))
            meta["zoom"] = factor
            meta["zoom_mode"] = "manual"
            self._send_zoom_action(key, "zoom", factor)
        self.paint()
        # Devolver el foco a la herramienta después de usar el zoom.
        if meta.get("embedded") and meta.get("xid") and key == self.selected_top_tab:
            self.sync(self.dpy, 0)
            self.set_input_focus(self.dpy, meta["xid"], 1, 0)

    def _zoom_footer_controls(self):
        """Posiciones compartidas: - porcentaje + Ajustar."""
        w, h = self.size
        y = h - 35
        buttons = (("minus", 25), ("percent", 79),
                   ("plus", 25), ("fit", 67))
        used = sum(width for _, width in buttons) + 6 * (len(buttons) - 1)
        x = max(8, w - used - 12)
        boxes = {}
        for name, width in buttons:
            boxes[name] = (x, y, width, 26)
            x += width + 6
        return boxes

    def draw_zoom_footer(self):
        """Footer de zoom estilo PTM, visible solo en pestañas de herramientas."""
        if self.selected_top_tab == "PYRIONOS":
            return
        meta = self.open_tabs.get(self.selected_top_tab)
        if not meta:
            return
        w, h = self.size
        top = h - 42
        self.rect(0, top, w, 42, "#F8FAFC")
        self.rect(0, top, w, 1, "#CFDCE5")
        controls = self._zoom_footer_controls()
        limit = min(item[0] for item in controls.values())
        version = str(meta.get("tool", {}).get("version", "")).strip()
        caption = meta["name"] + ((" · v" + version) if version else "")
        if limit > 95:
            self.text(13, h - 16,
                      self._ellipsize(caption, limit - 24, "caption"),
                      "#556B7B", "caption")
        ready = meta.get("zoom_ready", False)
        percent = int(round(float(meta.get("zoom", 1.0)) * 100))
        auto = meta.get("zoom_mode", "fit") == "fit"
        for name, (x, y, bw, bh) in controls.items():
            selected = name == "fit" and auto and ready
            background = "#DDEEF4" if selected else "#FFFFFF"
            ink = "#64748B" if not ready else "#17536F"
            self.rect(x, y, bw, bh, background)
            self.rect(x, y, bw, 1, "#C4D0DA")
            self.rect(x, y + bh - 1, bw, 1, "#C4D0DA")
            self.rect(x, y, 1, bh, "#C4D0DA")
            self.rect(x + bw - 1, y, 1, bh, "#C4D0DA")
            label = {
                "minus": "-", "plus": "+", "fit": "Ajustar",
                "percent": "%d%%%s" % (percent, " Auto" if auto else ""),
            }[name]
            style = "tab" if name != "percent" else "caption"
            tx = x + (bw - self.text_width(label, style)) // 2
            self.text(tx, y + 18, label, ink, style)

    def _click_zoom_footer(self, x, y, button):
        if button != 1 or self.selected_top_tab == "PYRIONOS":
            return False
        if y < self.size[1] - 42:
            return False
        for name, (bx, by, bw, bh) in self._zoom_footer_controls().items():
            if bx <= x < bx + bw and by <= y < by + bh:
                key = self.selected_top_tab
                if name == "minus":
                    self._change_tool_zoom(key, delta=-0.10)
                elif name == "plus":
                    self._change_tool_zoom(key, delta=0.10)
                else:
                    self._change_tool_zoom(key, fit=True)
                return True
        return True

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
            "zoom": 1.0, "zoom_mode": "fit", "zoom_ready": False,
            "zoom_control": None, "zoom_status": None,
            "zoom_mtime": 0, "zoom_seq": 0,
            "deps_progress": 0, "deps_progress_visible": True,
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
        for file_key in ("xid_file", "ready_file",
                         "zoom_control", "zoom_status"):
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
        meta["zoom_control"] = None
        meta["zoom_status"] = None
        meta["zoom_mtime"] = 0
        meta["zoom_ready"] = False
        meta["zoom_seq"] = 0
        meta["zoom"] = 1.0
        meta["zoom_mode"] = "fit"
        meta["deps_progress_visible"] = False
        meta["deps_progress"] = 0
        # Invalida notificaciones antiguas de preparacion.
        meta["deps_token"] = int(meta.get("deps_token", 0)) + 1

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
            zoom_ctrl, zoom_status = self._zoom_files(key)
            for marker in (xid_file, ready_file, zoom_ctrl, zoom_status):
                marker.unlink(missing_ok=True)
            meta.update({
                "xid_file": xid_file, "ready_file": ready_file,
                "log_file": logfile, "state": "starting",
                "message": "Cargando y autoajustando la interfaz...",
                "zoom_control": zoom_ctrl, "zoom_status": zoom_status,
                "zoom_ready": False, "zoom_mtime": 0, "zoom_seq": 0,
                "zoom": 1.0, "zoom_mode": "fit",
                "xid": None, "embedded": False,
            })
            wrapper = self.cache_dir / "tk_launcher.py"
            wrapper.write_text(self._tk_launcher_source(), encoding="utf-8")
            env = self._deps_python_env()
            _, _, width, height = self._tool_view_rect()
            command = [sys.executable, str(wrapper), str(path),
                       str(xid_file), str(ready_file),
                       str(zoom_ctrl), str(zoom_status),
                       str(width), str(height)]
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
            meta = self.open_tabs[key]
            if action == "downloaded":
                # Primero validar imports + instalar paquetes. NO iniciar el .py.
                self._prepare_tool_async(meta["tool"], key, data)
            elif action == "failed":
                meta["state"] = "error"
                meta["message"] = data
            elif action in ("deps_status", "deps_ready", "deps_failed"):
                # Evitar mensajes rezagados de una instalacion anterior.
                if data.get("token") != meta.get("deps_token"):
                    continue
                if action == "deps_status":
                    meta["state"] = "preparing"
                    meta["message"] = data["message"]
                    if "progress" in data:
                        # Nunca retrocede si pip necesita reintentar.
                        meta["deps_progress"] = max(
                            int(meta.get("deps_progress", 0)),
                            min(100, int(data["progress"])))
                    meta["deps_progress_visible"] = True
                elif action == "deps_failed":
                    meta["state"] = "error"
                    meta["message"] = "Dependencias: " + data["message"]
                else:
                    meta["deps_progress"] = 100
                    meta["deps_progress_visible"] = True
                    meta["message"] = "Dependencias listas. Iniciando..."
                    self._start_tool_process(key, data["filename"])
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
            status_file = meta.get("zoom_status")
            if status_file:
                try:
                    st = status_file.stat()
                    if st.st_mtime_ns != meta.get("zoom_mtime"):
                        status = json.loads(status_file.read_text(encoding="utf-8"))
                        if status.get("ready"):
                            meta["zoom"] = max(.50, min(1.25,
                                float(status.get("zoom", 1.0))))
                            meta["zoom_mode"] = (
                                "manual" if status.get("mode") == "manual" else "fit")
                            meta["zoom_ready"] = True
                            meta["zoom_mtime"] = st.st_mtime_ns
                            dirty = True
                except (OSError, ValueError, TypeError):
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
        """Estado de la herramienta y barra de avance real 0% - 100%."""
        meta = self.open_tabs.get(self.selected_top_tab)
        if not meta:
            return
        if meta.get("embedded"):
            return
        w, h = self.size
        compact = h < 255
        title_y = 66 if compact else 85
        status_y = 100 if compact else 119
        self.text(22, title_y,
                  self._ellipsize(meta["name"], max(80, w - 44), "label"),
                  "#173B50", "label")
        info = str(meta.get("message", ""))
        limit = max(90, w - 44)
        rows = [""]
        for word in info.split():
            candidate = (rows[-1] + " " + word).strip()
            if rows[-1] and self.text_width(candidate, "tab") > limit:
                rows.append(word)
            else:
                rows[-1] = candidate
        # El progreso no puede tapar el footer, incluso en resoluciones bajas.
        max_rows = 1 if compact else 6
        shown = rows[:max_rows]
        for index, row in enumerate(shown):
            self.text(22, status_y + index * 21,
                      self._ellipsize(row, limit, "tab"),
                      "#546673", "tab")

        bottom_of_status = status_y + (len(shown) - 1) * 21
        next_y = bottom_of_status + 26
        if meta.get("deps_progress_visible"):
            progress = max(0, min(100, int(meta.get("deps_progress", 0))))
            bar_x = 22
            bar_width = max(90, min(w - 44, 640))
            bar_height = 13
            bar_y = max(bottom_of_status + 22, 136)
            bar_y = min(bar_y, max(108, h - 58))
            text_y = bar_y - 8

            self.text(bar_x, text_y, "0%", "#576979", "caption")
            label = "%d%%" % progress
            self.text(bar_x + (bar_width - self.text_width(label, "label")) // 2,
                      text_y, label, "#1D6684", "label")
            label100 = "100%"
            self.text(bar_x + bar_width - self.text_width(label100, "caption"),
                      text_y, label100, "#576979", "caption")
            self.rect(bar_x, bar_y, bar_width, bar_height, "#E7EEF3")
            self.rect(bar_x, bar_y, bar_width, 1, "#B5C6D1")
            self.rect(bar_x, bar_y + bar_height - 1, bar_width, 1, "#B5C6D1")
            self.rect(bar_x, bar_y, 1, bar_height, "#B5C6D1")
            self.rect(bar_x + bar_width - 1, bar_y, 1, bar_height, "#B5C6D1")
            filled = int((bar_width - 2) * progress / 100)
            if filled:
                color = "#C44E4E" if meta.get("state") == "error" else "#1D6684"
                self.rect(bar_x + 1, bar_y + 1, filled, bar_height - 2, color)
            next_y = bar_y + 28

        if meta.get("state") in ("error", "ended"):
            self.text(22, min(next_y, h - 53),
                      "Haz clic para reintentar", "#176684", "tab")

    def _click_tool_panel(self, x, y, button):
        if button != 1 or not (115 <= y <= self.size[1] - 55):
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
            if meta.get("process") and meta["process"].poll() is None:
                self._send_zoom_action(meta["tool"]["key"], "resize")

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
        """PTM: Enter espera la respuesta remota, con copia local como respaldo."""
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
                    action = "error"
                    value = "Catalogo invalido: " + str(error)
            if action == "error" and not self.catalog_tools:
                self.catalog_status = "Sin acceso a catalogo PTM: " + value[:85]
                dirty = True
            if self.expand_after_update and self.show_all_results:
                if self.enter_refresh_queued:
                    # Consulta exclusiva solicitada por Enter despues de la anterior.
                    self.enter_refresh_queued = False
                    self._refresh_catalog_async(force=True)
                    continue
                self.expand_after_update = False
                self.expanded_loading = False
                if action == "error":
                    self.expanded_notice = (
                        "Sin conexión con GitHub; mostrando catálogo local."
                        if self.catalog_tools else
                        "Sin acceso remoto ni catálogo local válido.")
                else:
                    self.expanded_notice = ""
                self.results_scroll = 0
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

    def _cancel_expanded_search(self):
        """Al editar o borrar se restaura el modo de 5 sugerencias de PTM."""
        self.show_all_results = False
        self.expand_after_update = False
        self.enter_refresh_queued = False
        self.expanded_loading = False
        self.expanded_notice = ""
        self.results_scroll = 0

    def _set_search_command(self, command):
        self.search_text = command[:MAX_SEARCH_CHARS]
        self.search_focus = False
        self._expand_results()

    def _expand_results(self):
        """Enter/rojo: panel PTM expandido, catalogo actualizado antes de listar."""
        self.results_scroll = 0
        self.search_focus = False
        # No abrir una herramienta automáticamente al pulsar Enter.
        # La selección y ejecución corresponden al clic sobre un resultado.
        self.show_all_results = True
        self.expanded_loading = True
        self.expanded_notice = "Actualizando catálogo..."
        self.expand_after_update = True
        # Si habia una revision al escribir, Enter solicita su propia revision
        # despues de ella para no usar un catalogo remoto anterior al Enter.
        self.enter_refresh_queued = bool(self.catalog_fetching)
        if not self.catalog_fetching:
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
        top = y + bh + (66 if self.show_all_results else 51)
        bottom = max(top + 12, self.size[1] - 30)
        row_height = 78 if self.show_all_results else 39
        count = max(1, min(10, (bottom - top - 8) // row_height))
        return x, top, bw, row_height, count

    def _ellipsize(self, value, max_px, style="body"):
        text = str(value or "")
        if self.text_width(text, style) <= max_px:
            return text
        while text and self.text_width(text + "…", style) > max_px:
            text = text[:-1]
        return text + "…" if text else ""

    def draw_results(self):
        """PTM: 5 sugerencias compactas o listado detallado y desplazable con Enter."""
        self.results_click_areas = []
        if self.selected_top_tab != "PYRIONOS":
            return
        expanded = self.show_all_results
        if not expanded and not self.search_text.strip():
            return
        x, top, bw, rh, max_rows = self._result_geom()
        if expanded and self.expanded_loading:
            self.text(x + 2, top - 14, "Actualizando catálogo...",
                      "#5B6974", "tab")
            return

        matches = self._search_matches()
        total = len(matches)
        if expanded:
            if self.expanded_notice:
                info = self.expanded_notice
            elif not self.search_text.strip():
                info = "%s herramientas disponibles · escribe para buscar" % len(self.catalog_tools)
            else:
                info = "%s coincidencia(s)" % total
            self.text(x, top - 17, self._ellipsize(info, bw, "tab"),
                      "#596B78", "tab")
        if not self.search_text.strip():
            return
        if not total:
            self.text(x + 6, top + 22, "Sin coincidencias",
                      "#5B6974", "tab")
            return

        shown = matches if expanded else matches[:5]
        max_scroll = max(0, len(shown) - max_rows)
        self.results_scroll = min(max(0, self.results_scroll), max_scroll)
        displayed = shown[self.results_scroll:self.results_scroll + max_rows]

        for index, tool in enumerate(displayed):
            ry = top + index * rh
            self.rect(x, ry, bw, rh - 4, "#F3F6F8")
            self.rect(x, ry, bw, 1, "#D8E0E7")
            self.rect(x, ry + rh - 5, bw, 1, "#D8E0E7")
            self.rect(x, ry, 1, rh - 4, "#D8E0E7")
            self.rect(x + bw - 1, ry, 1, rh - 4, "#D8E0E7")
            favored = tool["key"] in self.user_state["favorites"]
            name = ("★ " if favored else "") + tool["name"]
            if expanded:
                left_width = max(116, int(bw * 0.61) - 16)
                right_x = x + left_width + 17
                right_width = max(75, bw - (right_x - x) - 10)
                self.text(x + 10, ry + 20,
                          self._ellipsize(name, left_width - 5, "label"),
                          "#172B40", "label")
                description = tool.get("descripcion", "").strip() or "Sin descripción."
                self.text(x + 10, ry + 40,
                          self._ellipsize(description, left_width - 5, "tab"),
                          "#536470", "tab")
                author = tool.get("autor", "") or "Sin autor"
                self.text(right_x, ry + 19,
                          self._ellipsize(author, right_width, "tab_active"),
                          "#263B4A", "tab_active")
                self.text(right_x, ry + 37,
                          self._ellipsize(
                              "%s · v%s · %s visitas" % (
                                  tool.get("categoria", ""),
                                  tool.get("version", "-"), tool["visits"]),
                              right_width, "caption"), "#647484", "caption")
                self.text(right_x, ry + 54,
                          self._ellipsize(
                              "%s · %s" % (
                                  tool.get("modo", "Integrado"),
                                  tool.get("dependencias", "") or "Sin dependencias"),
                              right_width, "caption"), "#647484", "caption")
                self.text(x + 10, ry + 59,
                          self._ellipsize(
                              "Clic: abrir en pestaña · derecho: favorito",
                              left_width - 5, "caption"), "#677683", "caption")
            else:
                self.text(x + 9, ry + 25,
                          self._ellipsize(name, bw - 175, "label"),
                          "#172B40", "label")
                meta = "%s · v%s" % (tool.get("categoria", ""),
                                     tool.get("version", "-"))
                self.text(x + bw - 165, ry + 25,
                          self._ellipsize(meta, 150, "caption"),
                          "#56636D", "caption")
            self.results_click_areas.append((x, ry, bw, rh - 4, tool))

        if max_scroll:
            track_x, track_y = x + bw - 7, top + 2
            track_h = max(12, max_rows * rh - 9)
            thumb_h = max(18, int(track_h * max_rows / len(shown)))
            thumb_y = track_y + int(
                (track_h - thumb_h) * self.results_scroll / max_scroll)
            self.rect(track_x, track_y, 4, track_h, "#E1E8ED")
            self.rect(track_x, thumb_y, 4, thumb_h, "#69899B")

        if not expanded:
            tip = ("%s coincidencias · mostrando 5 · Enter para ver todas" % total
                   if total > 5 else "%s coincidencia(s)" % total)
            self.text(x, self.size[1] - 10,
                      self._ellipsize(tip, bw, "caption"),
                      "#607384", "caption")

    def _result_scroll(self, delta):
        if (self.expanded_loading or not self.search_text.strip()
                or self.selected_top_tab != "PYRIONOS"):
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
        if self.show_all_results:
            # Enter: PYRIONOS compacto a la izquierda, estilo PTM.
            if self.size[0] >= 480:
                self.draw_pyrionos_logo_compact(x - 122, y - 4)
            else:
                self.draw_pyrionos_logo_compact(
                    (self.size[0] - 110) // 2, y - 60)
        else:
            logo_w, logo_h, gap = 226, 101, 14
            self.draw_pyrionos_logo(x + (bw - logo_w) // 2,
                                   y - logo_h - gap)

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
            if self._click_zoom_footer(x, y, button):
                return
            self._click_tool_panel(x, y, button)
            return
        # La barra lateral del listado PTM también permite saltar de posición.
        if (button == 1 and self.show_all_results
                and not self.expanded_loading and self.search_text.strip()):
            list_x, list_y, list_w, row_h, rows = self._result_geom()
            total = len(self._search_matches())
            if (total > rows and list_x + list_w - 15 <= x <= list_x + list_w
                    and list_y <= y <= list_y + rows * row_h):
                proportion = (y - list_y) / max(1, rows * row_h)
                self.results_scroll = min(
                    total - rows, max(0, round(proportion * (total - rows))))
                self.paint()
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
                self._cancel_expanded_search()
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
        # PTM: escribir de nuevo restaura 5 resultados, sin abrir herramientas.
        self._cancel_expanded_search()
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
        self.draw_zoom_footer()
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
