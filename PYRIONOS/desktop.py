#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PYRION OS - Escritorio X11 minimalista: solo fondo PNG a pantalla completa.

Sin barra, textos, iconos, pestañas ni botones. La descarga del fondo y la
actualizacion automatica en caliente mediante app.py se mantienen activas.
Python estandar + ctypes + libX11. Interfaz publica: PyrionDesktop y main().
"""
from __future__ import annotations

import ctypes as C
import ctypes.util
import hashlib
from pathlib import Path
import os
import signal
import struct
import sys
import time
import urllib.request
import zlib

APP_NAME = "PYRION OS"
APP_VERSION = "0.2.15-fondo-renovado"
SERVER = "https://raw.githubusercontent.com/mobatfb/archmoba-dev/main/PYRIONOS/assets/"
BACKGROUND_URL = SERVER + "pyrion-fondo-v2.png"

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
    """Ventana de escritorio X11 que muestra exclusivamente el fondo."""

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
        self.running = True
        self.background = None
        self._load_assets()

    def _load_assets(self):
        # El unico recurso grafico del escritorio es el fondo remoto.
        try:
            self.background = fetch_png(BACKGROUND_URL)
            print("PYRION: fondo cargado (GitHub o RAM).", flush=True)
        except (OSError, ValueError, UnicodeError) as error:
            print("PYRION: no se pudo cargar el fondo: " + str(error),
                  file=sys.stderr, flush=True)

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
                or nbytes > 40_000_000):
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

    def paint(self):
        """Solo dibuja el PNG original del fondo, sin ninguna superposicion."""
        w, h = self.size
        if self.pixmap:
            self.pixmap_free(self.dpy, self.pixmap)
        self.pixmap = self.pixmap_create(self.dpy, self.window, w, h, self.depth)
        self.rect(0, 0, w, h, "#FFFFFF")
        if self.background:
            self._image(self.background, 0, 0, w, h)
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
        print("PYRION: escritorio iniciado; solo fondo.", flush=True)

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
