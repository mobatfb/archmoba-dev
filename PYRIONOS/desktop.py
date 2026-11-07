#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PYRION OS - Escritorio X11 con buscador sobre fondo blanco.

La actualizacion en caliente mediante app.py sigue siendo compatible.
Python estandar + ctypes + libX11. Interfaz publica: PyrionDesktop y main().
"""
from __future__ import annotations

import ctypes as C
import ctypes.util
import csv
import io
import json
import queue
import re
import subprocess
import tempfile
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
APP_VERSION = "0.2.27-pestanas-superiores"
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
            "%used%": sorted(self.catalog_tools, key=lambda t: -int(usage.get(t["key"], 0)))[:10],
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
            remaining = width - x - 13
            if remaining < 52:
                break
            natural = self.text_width(title, "tab") + 22
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

            label = title
            # Acortar títulos que exceden el ancho de la pestaña.
            while label and self.text_width(label, "tab") > width - 18:
                label = label[:-1]
            if label != title and len(label) > 1:
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

    def click_ui(self, x, y):
        for title, tx, ty, tw, th in self._top_tabs_layout():
            if tx <= x < tx + tw and ty <= y < ty + th:
                self.selected_top_tab = title
                self.search_focus = False
                self.paint()
                return
        bx, by, bw, bh = self._search_bounds()
        if bx <= x < bx + bw and by <= y < by + bh:
            _, _, clear_x = self._search_input_layout()
            if clear_x is not None and abs(x - clear_x) <= 9 and abs(y - (by + 22)) <= 11:
                # La X borra solo la consulta y deja el cursor listo para escribir.
                self.search_text = ""
                self.search_focus = True
            elif bx + bw - 84 <= x < bx + bw - 50:
                # Boton rojo (accion Buscar/Enter): no elimina lo escrito.
                self.search_focus = False
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
                    self.search_focus = False
                    self.paint()
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
            self.search_focus = False
        elif 0 < count <= 31:
            value = buffer.raw[:count].decode("utf-8", "ignore")
            if value.isprintable():
                available = MAX_SEARCH_CHARS - len(self.search_text)
                if available > 0:
                    self.search_text += value[:available]
        self.paint()

    def paint(self):
        """Dibuja fondo blanco y buscador centrado del escritorio."""
        w, h = self.size
        if self.pixmap:
            self.pixmap_free(self.dpy, self.pixmap)
        self.pixmap = self.pixmap_create(self.dpy, self.window, w, h, self.depth)
        self.rect(0, 0, w, h, "#FFFFFF")
        self.draw_top_tabs()
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
