#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PYRION OS - Paso 2: maqueta visual tipo navegador (X11 nativo).

Interfaz de boceto: pestañas, búsqueda y aplicaciones no realizan acciones.
Solo el botón Cerrar responde al ratón y finaliza el escritorio.
El fondo se descarga como PNG desde GitHub y se usa solo en RAM.
Los espacios del icono superior y del logotipo central quedan vacios.
Si una imagen no se descarga, se informa del error: no se imita con dibujos.

Python estandar + ctypes + libX11; libXft es opcional para texto UTF-8.
Conserva el contrato que exige app.py: PyrionDesktop y main().
"""
from __future__ import annotations

import ctypes as C
import ctypes.util
import hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import os
import signal
import struct
import sys
import time
import urllib.request
import zlib

APP_NAME = "PYRION OS"
APP_VERSION = "0.2.13-sin-iconos"
SERVER = "https://raw.githubusercontent.com/mobatfb/archmoba-dev/main/PYRIONOS/assets/"
BACKGROUND_URL = SERVER + "pyrion-fondo.png"

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


class XImage(C.Structure):
    # XImage layout from X11/Xlib.h. Only the public fields needed by XPutImage.
    _fields_ = [("width", I), ("height", I), ("xoffset", I), ("format", I),
                ("data", P), ("byte_order", I), ("bitmap_unit", I),
                ("bitmap_bit_order", I), ("bitmap_pad", I), ("depth", I),
                ("bytes_per_line", I), ("bits_per_pixel", I),
                ("red_mask", U), ("green_mask", U), ("blue_mask", U),
                ("obdata", P)]


class XButtonEvent(C.Structure):
    # Diseño ABI de Xlib.h: XButtonEvent (64 bits y 32 bits).
    _fields_ = [
        ("type", I), ("serial", U), ("send_event", I), ("display", P),
        ("window", U), ("root", U), ("subwindow", U), ("time", U),
        ("x", I), ("y", I), ("x_root", I), ("y_root", I),
        ("state", UI), ("button", UI), ("same_screen", I),
    ]


class XEvent(C.Union):
    _fields_ = [("type", I), ("xbutton", XButtonEvent),
                ("pad", C.c_long * 24)]


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


ASSET_CACHE_TTL = 90.0  # Solo RAM; se renueva en actualizaciones posteriores.


def _read_asset_cache(path):
    """Lee pixeles decodificados de RAM, sin volver a descomprimir PNG."""
    with path.open("rb") as cache:
        header = cache.read(12)
        if len(header) != 12:
            raise ValueError("cache RAM incompleta")
        width, height, channels = struct.unpack(">III", header)
        size = width * height * channels
        if not (0 < width <= 8192 and 0 < height <= 8192 and
                channels in (3, 4) and size <= 32 * 1024 * 1024):
            raise ValueError("cache RAM invalida")
        pixels = cache.read(size + 1)
        if len(pixels) != size:
            raise ValueError("pixeles de cache incompletos")
        return width, height, channels, pixels


def fetch_png(url):
    """Descarga PNG o reutiliza pixeles decodificados en tmpfs/ramfs."""
    cache_dir = os.environ.get("PYRION_RAM_ASSETS_DIR")
    cached = (Path(cache_dir) / (hashlib.sha256(url.encode("utf-8")).hexdigest() + ".pixels")
              if cache_dir else None)
    if cached is not None:
        try:
            if time.time() - cached.stat().st_mtime < ASSET_CACHE_TTL:
                return _read_asset_cache(cached)
        except (OSError, ValueError):
            pass

    req = urllib.request.Request(url + "?pyrion_asset=" + str(time.time_ns()),
                                 headers={"User-Agent": "PYRIONOS-X11/" + APP_VERSION,
                                          "Cache-Control": "no-cache, no-store"})
    try:
        with urllib.request.urlopen(req, timeout=7) as response:
            raw = response.read(2_000_001)
        if not raw or len(raw) > 2_000_000:
            raise ValueError("imagen vacia o demasiado grande")
        result = decode_png(raw)
    except (OSError, ValueError, UnicodeError):
        if cached is not None:
            try:
                return _read_asset_cache(cached)
            except (OSError, ValueError):
                pass
        raise

    if cached is not None:
        temporary = cached.with_name(cached.name + "." + str(os.getpid()) + ".tmp")
        try:
            temporary.write_bytes(struct.pack(">III", *result[:3]) + result[3])
            os.replace(temporary, cached)
        except OSError:
            pass  # El cache es opcional: la imagen descargada sigue funcionando.
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
    return result


def decode_png(raw):
    """Small pure-Python PNG decoder: 8-bit RGB or RGBA, non-interlaced."""
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("archivo remoto no es PNG")
    offset, image_data, width, height, channels = 8, bytearray(), 0, 0, 0
    while offset + 12 <= len(raw):
        size = struct.unpack_from(">I", raw, offset)[0]
        kind = raw[offset + 4:offset + 8]
        end = offset + 12 + size
        if size > 2_000_000 or end > len(raw):
            raise ValueError("PNG incompleto o demasiado grande")
        data = raw[offset + 8:offset + 8 + size]
        if kind == b"IHDR":
            width, height, depth, color, comp, flt, interlace = struct.unpack(">IIBBBBB", data)
            if not (0 < width <= 2048 and 0 < height <= 1536 and depth == 8
                    and color in (2, 6) and comp == flt == interlace == 0):
                raise ValueError("PNG debe ser RGB/RGBA 8-bit sin entrelazado")
            channels = 3 if color == 2 else 4
        elif kind == b"IDAT":
            image_data.extend(data)
            if len(image_data) > 2_000_000:
                raise ValueError("PNG comprimido excede el limite")
        elif kind == b"IEND":
            break
        offset = end
    if not channels or not image_data:
        raise ValueError("PNG sin pixeles")
    stride = width * channels
    expected = (stride + 1) * height
    if expected > 12_000_000:
        raise ValueError("PNG excede la memoria permitida")
    inflater = zlib.decompressobj()
    filtered = inflater.decompress(bytes(image_data), expected + 1)
    if len(filtered) != expected or inflater.unconsumed_tail:
        raise ValueError("PNG contiene datos incompatibles")
    previous = bytearray(stride)
    pixels = bytearray(width * height * channels)
    ip = 0
    for y in range(height):
        start = y * (stride + 1)
        filt = filtered[start]
        row = bytearray(filtered[start + 1:start + stride + 1])
        if filt > 4:
            raise ValueError("filtro PNG no compatible")
        for x in range(stride):
            a = row[x - channels] if x >= channels else 0
            b = previous[x]
            c = previous[x - channels] if x >= channels else 0
            if filt == 1: v = a
            elif filt == 2: v = b
            elif filt == 3: v = (a + b) // 2
            elif filt == 4:
                p = a + b - c
                da, db, dc = abs(p-a), abs(p-b), abs(p-c)
                v = a if da <= db and da <= dc else b if db <= dc else c
            else: v = 0
            row[x] = (row[x] + v) & 255
        pixels[ip:ip + stride] = row
        ip += stride
        previous = row
    return width, height, channels, bytes(pixels)


class PyrionDesktop:
    """Layered white desktop with a static, browser-inspired mockup."""

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
        self.create_image = bind(x, "XCreateImage", P, P, P, UI, I, I, P,
                                 UI, UI, I, I)
        self.put_image = bind(x, "XPutImage", I, P, U, P, P, I, I, I, I, UI, UI)
        self.destroy_image = bind(x, "XDestroyImage", I, P)
        self.drawstring = bind(x, "XDrawString", I, P, U, P, I, I, C.c_char_p, I)
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
        self.xft = None
        self.ftdraw = None
        self.fonts = {}
        self.ftcolors = {}
        self.running = True
        self.close_bounds = None  # x, y, ancho, alto del único botón activo.
        self.background = None
        self._load_assets()
        self._init_fonts()

    def _load_assets(self):
        assets = (("background", BACKGROUND_URL),)
        # Solo descargamos el fondo; no se cargan iconos ni logotipos.
        with ThreadPoolExecutor(max_workers=1) as pool:
            futures = [pool.submit(fetch_png, url) for _, url in assets]
            for (name, url), future in zip(assets, futures):
                try:
                    item = future.result()
                    setattr(self, name, item)
                    print("PYRION: imagen lista (GitHub o RAM):", url, flush=True)
                except (OSError, ValueError, UnicodeError) as error:
                    print("PYRION: ERROR al cargar %s desde %s: %s" %
                          (name, url, error), file=sys.stderr, flush=True)

    def _init_fonts(self):
        try:
            ft = C.CDLL(ctypes.util.find_library("Xft") or "libXft.so.2")
            self.xft_open = bind(ft, "XftFontOpenName", P, P, I, C.c_char_p)
            self.xft_close = bind(ft, "XftFontClose", None, P, P)
            self.xft_draw_create = bind(ft, "XftDrawCreate", P, P, U, P, U)
            self.xft_draw_destroy = bind(ft, "XftDrawDestroy", None, P)
            self.xft_draw_text = bind(ft, "XftDrawStringUtf8", None, P,
                                      C.POINTER(XftColor), P, I, I, P, I)
            self.xft_extents = bind(ft, "XftTextExtentsUtf8", None, P, P, P, I,
                                    C.POINTER(XGlyphInfo))
            self.xft_alloc = bind(ft, "XftColorAllocValue", I, P, P, U,
                                  C.POINTER(XRenderColor), C.POINTER(XftColor))
            self.xft_free = bind(ft, "XftColorFree", None, P, P, U,
                                 C.POINTER(XftColor))
            names = {
                "small": b"DejaVu Sans:size=10",
                "body": b"DejaVu Sans:size=12",
                "medium": b"DejaVu Sans:style=Bold:size=12",
                "brand": b"DejaVu Sans:style=Bold:size=16",
                "title": b"DejaVu Sans:style=Bold:size=32",
                "tagline": b"DejaVu Sans:size=18",
                "tab": b"DejaVu Sans:size=12",
            }
            for key, fontname in names.items():
                font = self.xft_open(self.dpy, self.screen, fontname)
                if font:
                    self.fonts[key] = font
            if not self.fonts:
                return
            self.xft = ft
        except (OSError, AttributeError):
            self.xft = None

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

    def _rounded_shape(self, x, y, w, h, r):
        r = min(int(r), int(w//2), int(h//2))
        if r <= 0:
            self.fillrect(self.dpy, self.pixmap, self.gc, int(x), int(y), int(w), int(h))
            return
        self.fillrect(self.dpy, self.pixmap, self.gc,
                      int(x+r), int(y), int(w-2*r), int(h))
        self.fillrect(self.dpy, self.pixmap, self.gc,
                      int(x), int(y+r), int(w), int(h-2*r))
        for xx, yy, angle in ((x, y, 90), (x+w-2*r, y, 0),
                              (x, y+h-2*r, 180), (x+w-2*r, y+h-2*r, 270)):
            self.fillarc(self.dpy, self.pixmap, self.gc, int(xx), int(yy),
                         UI(2*r), UI(2*r), int(angle*64), 90*64)

    def round(self, x, y, w, h, r, fill, border=None):
        if w <= 0 or h <= 0: return
        if border:
            self.pen(border)
            self._rounded_shape(x, y, w, h, r)
            self.pen(fill)
            self._rounded_shape(x+1, y+1, w-2, h-2, max(0, r-1))
        else:
            self.pen(fill)
            self._rounded_shape(x, y, w, h, r)

    def line(self, x1, y1, x2, y2, color):
        self.pen(color)
        self.drawline(self.dpy, self.pixmap, self.gc, int(x1), int(y1), int(x2), int(y2))

    def text_width(self, value, style="body"):
        if self.xft and self.fonts:
            font = self.fonts.get(style) or next(iter(self.fonts.values()))
            b = value.encode("utf-8")
            out = XGlyphInfo()
            self.xft_extents(self.dpy, font, b, len(b), C.byref(out))
            return int(out.xOff)
        return len(value) * (9 if style == "title" else 8)

    def text(self, value, x, baseline, color="#27313E", style="body"):
        if self.xft and self.ftdraw:
            f = self.fonts.get(style) or next(iter(self.fonts.values()), None)
            if f:
                if color not in self.ftcolors:
                    r, g, b = (int(color[i:i+2], 16) for i in (1, 3, 5))
                    raw = XRenderColor(r*257, g*257, b*257, 65535)
                    out = XftColor()
                    if self.xft_alloc(self.dpy, self.visual, self.colormap,
                                      C.byref(raw), C.byref(out)):
                        self.ftcolors[color] = out
                col = self.ftcolors.get(color)
                if col:
                    buf = value.encode("utf-8")
                    self.xft_draw_text(self.ftdraw, C.byref(col), f,
                                       int(x), int(baseline), buf, len(buf))
                    return
        # Fallback for minimal installations without libXft.
        text = value.encode("latin-1", "replace")
        self.pen(color)
        self.drawstring(self.dpy, self.pixmap, self.gc,
                        int(x), int(baseline), text, len(text))

    def _image(self, image, dx, dy, dw, dh):
        if not image or dw <= 0 or dh <= 0:
            return
        iw, ih, channels, pixels = image
        # Avoid large intermediate images: scale directly into XImage memory.
        raw = self.create_image(self.dpy, self.visual, self.depth, 2, 0, None,
                                int(dw), int(dh), 32, 0)
        if not raw:
            return
        img = C.cast(raw, C.POINTER(XImage)).contents
        line_bytes = img.bytes_per_line
        nbytes = line_bytes * int(dh)
        if (not (24 <= img.bits_per_pixel <= 32) or nbytes <= 0
                or nbytes > 14_000_000):
            self.destroy_image(raw)
            return
        row = (C.c_ubyte * nbytes)()
        img.data = C.cast(row, P)
        pixel_bytes = img.bits_per_pixel // 8
        # X11 commonly uses red_mask=0x00ff0000 etc; respect server pixel format.
        masks = (img.red_mask, img.green_mask, img.blue_mask)
        components = []
        for mask in masks:
            shift = (int(mask) & -int(mask)).bit_length()-1 if mask else 0
            bits = int(mask >> shift).bit_count() if mask else 0
            components.append((mask, shift, bits))
        alpha_blend = channels == 4
        for y in range(int(dh)):
            sy = min(ih-1, y*ih//int(dh))
            row_start = y*line_bytes
            src_y = sy*iw*channels
            for x in range(int(dw)):
                sx = min(iw-1, x*iw//int(dw))
                source = src_y + sx*channels
                r, g, b = pixels[source], pixels[source+1], pixels[source+2]
                if alpha_blend:
                    a = pixels[source+3]
                    r = (r*a + 255*(255-a))//255
                    g = (g*a + 255*(255-a))//255
                    b = (b*a + 255*(255-a))//255
                pix = 0
                for v, (mask, shift, bits) in zip((r,g,b), components):
                    if mask:
                        q = v if bits == 8 else v*((1 << bits)-1)//255
                        pix |= (q << shift) & mask
                at = row_start + x*pixel_bytes
                row[at:at+pixel_bytes] = pix.to_bytes(pixel_bytes,
                                                      "little" if img.byte_order == 0 else "big")
        self.put_image(self.dpy, self.pixmap, self.gc, raw, 0, 0,
                       int(dx), int(dy), int(dw), int(dh))
        img.data = None  # XDestroyImage must not free the Python-owned bytearray.
        self.destroy_image(raw)

    def _magnifier(self, x, y, color):
        self.pen(color)
        self.drawarc(self.dpy, self.pixmap, self.gc,
                     x, y, 18, 18, 0, 360*64)
        self.line(x+15, y+15, x+24, y+24, color)

    def _home_icon(self, x, y, color):
        self.line(x, y+9, x+10, y, color)
        self.line(x+10, y, x+20, y+9, color)
        self.line(x+3, y+7, x+3, y+20, color)
        self.line(x+17, y+7, x+17, y+20, color)
        self.line(x+3, y+20, x+17, y+20, color)

    def _folder_icon(self, x, y, color):
        self.round(x, y+5, 25, 17, 3, "#FFFFFF", color)
        self.line(x+2, y+5, x+2, y+2, color)
        self.line(x+2, y+2, x+10, y+2, color)
        self.line(x+10, y+2, x+13, y+5, color)

    def _calc_icon(self, x, y, color):
        self.round(x, y, 18, 23, 3, "#FFFFFF", color)
        self.line(x+4, y+8, x+14, y+8, color)
        for dx in (5, 12):
            for dy in (13, 19):
                self.round(x+dx, y+dy, 2, 2, 1, color)

    def paint(self):
        w, h = self.size
        if self.ftdraw:
            self.xft_draw_destroy(self.ftdraw)
            self.ftdraw = None
        if self.pixmap:
            self.pixmap_free(self.dpy, self.pixmap)
        self.pixmap = self.pixmap_create(self.dpy, self.window, w, h, self.depth)
        self.ftdraw = self.xft_draw_create(self.dpy, self.pixmap, self.visual, self.colormap) if self.xft else None
        self.rect(0, 0, w, h, "#FFFFFF")
        if self.background:
            self._image(self.background, 0, 0, w, h)
        # Boceto tipo navegador. Solo Cerrar recibe clics.
        margin = 9
        bar_y, bar_h = 9, 83 if w >= 980 else 114
        self.round(margin+1, bar_y+3, w-2*margin, bar_h, 23, "#F3F6F9")
        self.round(margin, bar_y, w-2*margin, bar_h, 23, "#FFFFFF", "#DCE5EE")
        brand_y = bar_y+23
        # Espacio del icono superior libre, sin imagen ni sustituto.
        self.text("PYRION", margin+79, brand_y+22, "#283342", "brand")
        os_x = margin + 79 + self.text_width("PYRION", "brand")+7
        self.text("OS", os_x, brand_y+22, "#25BEF0", "brand")
        right_brand = os_x+self.text_width("OS", "brand")+20
        self.line(right_brand, bar_y+23, right_brand, bar_y+60, "#E6EBF2")
        is_wide = w>=980
        tabs_y = bar_y+16 if is_wide else bar_y+65
        tabs_x = right_brand+16 if is_wide else margin+25
        tabs = [("Inicio", 120, "home"), ("Calculadora", 153, "calc"), ("Archivos", 130, "folder")]
        available = max(160, (w*0.44)-tabs_x) if is_wide else (w - margin*2-110)
        natural = sum(x[1]+7 for x in tabs)
        scale = min(1.0, available/natural)
        for j,(label, natural_width, symbol) in enumerate(tabs):
            tw = max(64,int(natural_width*scale))
            active = j==0
            self.round(tabs_x, tabs_y, tw, 52 if is_wide else 38, 22,
                       "#E9F9FF" if active else "#FFFFFF",
                       "#30C5FF" if active else "#E2E7EF")
            icon_x = tabs_x+13
            icon_y = tabs_y+(14 if is_wide else 7)
            if symbol=="home": self._home_icon(icon_x,icon_y,"#33495E")
            elif symbol=="calc": self._calc_icon(icon_x+1,icon_y-1,"#516275")
            else: self._folder_icon(icon_x,icon_y,"#516275")
            if tw > 90:
                self.text(label, tabs_x+39, tabs_y+(33 if is_wide else 26),
                          "#253444" if active else "#536072", "medium" if active else "tab")
            tabs_x += tw+7
        if is_wide:
            sx = max(int(w*0.48), tabs_x+15)
            sy = bar_y+16
        else:
            sx = right_brand+18
            sy = bar_y+15
        # Reservar espacio para [+] y [Cerrar] en el extremo derecho.
        search_w = max(95, w - sx - 186)
        self.round(sx,sy,search_w,51 if is_wide else 41,24,"#F5FCFF","#25BDF0")
        self._magnifier(int(sx+20),int(sy+(14 if is_wide else 10)),"#4D5E70")
        hint = "Buscar aplicaciones, archivos o comandos..."
        if search_w < 350: hint = "Buscar aplicaciones..."
        if search_w < 240: hint = "Buscar..."
        self.text(hint,sx+62,sy+(33 if is_wide else 27),"#647181","body")
        button_h = 51 if is_wide else 41
        plus_x = w - 171
        self.round(plus_x, sy, 51, button_h, 21, "#FFFFFF", "#CDD7E1")
        plus_mid = sy + button_h // 2
        self.line(plus_x+25, plus_mid-11, plus_x+25, plus_mid+11, "#4F5D6E")
        self.line(plus_x+14, plus_mid, plus_x+36, plus_mid, "#4F5D6E")

        # Botón Cerrar: es el único control con una acción en esta fase.
        cx, cy, cw, ch = w-108, sy, 82, button_h
        self.close_bounds = (cx, cy, cw, ch)
        self.round(cx, cy, cw, ch, 19, "#FFF6F7", "#E3A0AB")
        cross_x, cross_y = cx + 14, cy + ch//2
        self.line(cross_x-5, cross_y-5, cross_x+5, cross_y+5, "#AE4357")
        self.line(cross_x+5, cross_y-5, cross_x-5, cross_y+5, "#AE4357")
        self.text("Cerrar", cx + 25, cy + ch//2 + 5, "#95384C", "small")
        # Area del logotipo central libre: solo queda visible el fondo.
        c = w//2
        logo_side = min(118, max(75, w//11))
        logo_top = int(h*.335)
        title_y=logo_top+logo_side+47
        a,b="PYRION"," OS"
        total=self.text_width(a,"title")+self.text_width(b,"title")
        x=c-total//2
        self.text(a,x,title_y,"#293441","title")
        self.text(b,x+self.text_width(a,"title"),title_y,"#21BDF1","title")
        self.line(c-87,title_y+37,c-33,title_y+37,"#E6EDF2")
        self.line(c-33,title_y+37,c+31,title_y+37,"#12C0ED")
        self.line(c+31,title_y+37,c+87,title_y+37,"#E6EDF2")
        caption="Tu espacio de trabajo"
        self.text(caption,c-self.text_width(caption,"tagline")//2,
                  title_y+98,"#758396","tagline")
        # Numero visible del desktop en el borde inferior derecho.
        # Es informativo: no tiene acciones ni modifica otras capas.
        version_label = "Desktop v" + APP_VERSION.split("-", 1)[0]
        version_x = max(10, w - self.text_width(version_label, "tab") - 22)
        self.text(version_label, version_x, h-22, "#697D93", "tab")
        self.copy(self.dpy,self.pixmap,self.window,self.gc,0,0,w,h,0,0)
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
        self.name(self.dpy,self.window,b"PYRION OS - Boceto sin logica")
        self.select(self.dpy,self.window,(1<<15)|(1<<17)|(1<<2))
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
        print("PYRION: boceto visual; Cerrar disponible; imagenes remotas.",flush=True)

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
                if ev.type==12:  # Expose
                    self.copy(self.dpy,self.pixmap,self.window,self.gc,
                              0,0,*self.size,0,0)
                    self.flush(self.dpy)
                elif ev.type == 4 and ev.xbutton.button == 1:  # Click izquierdo
                    if self.close_bounds:
                        x, y, width, height = self.close_bounds
                        if (x <= ev.xbutton.x < x+width and
                                y <= ev.xbutton.y < y+height):
                            print("PYRION: cerrado desde el boton superior.", flush=True)
                            self.stop()
            else:
                time.sleep(.05)

    def stop(self,*_):
        self.running=False

    def close(self):
        if self.dpy:
            if self.ftdraw:self.xft_draw_destroy(self.ftdraw)
            for font in self.fonts.values():self.xft_close(self.dpy,font)
            for item in self.ftcolors.values():
                self.xft_free(self.dpy,self.visual,self.colormap,C.byref(item))
            if self.pixmap:self.pixmap_free(self.dpy,self.pixmap)
            if self.gc:self.gc_free(self.dpy,self.gc)
            if self.window:self.destroy_window(self.dpy,self.window)
            self.close_dpy(self.dpy)
            self.dpy=None


def main():
    if "--check" in sys.argv[1:]:
        try:
            C.CDLL(ctypes.util.find_library("X11") or "libX11.so.6")
            print("OK: PYRION X11 disponible. Fondo:", BACKGROUND_URL)
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
