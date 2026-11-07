#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PYRION OS - Paso 1: fondo blanco a pantalla completa.

Solo Python estandar + ctypes + libX11 (ya presente en Mini Linux).
No usa PySide6, Tkinter, FLTK, discos ni archivos de configuracion.

Crea una ventana blanca sin bordes del tamano de la pantalla X11.
La marca como ventana de escritorio y la mantiene en el nivel inferior.
Todo lo que abramos despues se mostrara por delante de este fondo.

Ejecutar: python3 desktop.py
Comprobar biblioteca: python3 desktop.py --check
"""

from __future__ import annotations

import ctypes as C
import ctypes.util
import os
import signal
import sys
import time

APP_NAME = "PYRION OS"
APP_VERSION = "0.1.0-fondo-blanco"

# Tipos y constantes de Xlib.
Display = C.c_void_p
Window = C.c_ulong
Atom = C.c_ulong
CWOverrideRedirect = 1 << 9
PropModeReplace = 0
XA_ATOM = 4


class XSetWindowAttributes(C.Structure):
    """Estructura Xlib para indicar que el WM no gestione nuestro fondo."""

    _fields_ = [
        ("background_pixmap", C.c_ulong),
        ("background_pixel", C.c_ulong),
        ("border_pixmap", C.c_ulong),
        ("border_pixel", C.c_ulong),
        ("bit_gravity", C.c_int),
        ("win_gravity", C.c_int),
        ("backing_store", C.c_int),
        ("backing_planes", C.c_ulong),
        ("backing_pixel", C.c_ulong),
        ("save_under", C.c_int),
        ("event_mask", C.c_long),
        ("do_not_propagate_mask", C.c_long),
        ("override_redirect", C.c_int),
        ("colormap", C.c_ulong),
        ("cursor", C.c_ulong),
    ]


def bind(lib, name, result_type, *argument_types):
    function = getattr(lib, name)
    function.restype = result_type
    function.argtypes = list(argument_types)
    return function


class PyrionDesktop:
    """Unicamente una capa blanca situada debajo de las otras ventanas."""

    def __init__(self):
        library = ctypes_libx11()
        self.x = C.CDLL(library)
        self._bind_x11()
        self.display = self.XOpenDisplay(None)
        if not self.display:
            raise RuntimeError("No hay conexion con X11. Comprueba DISPLAY y Xorg.")
        self.window = Window(0)
        self.running = True
        self.size = (0, 0)

    def _bind_x11(self):
        x = self.x
        self.XOpenDisplay = bind(x, "XOpenDisplay", Display, C.c_char_p)
        self.XCloseDisplay = bind(x, "XCloseDisplay", C.c_int, Display)
        self.XDefaultScreen = bind(x, "XDefaultScreen", C.c_int, Display)
        self.XRootWindow = bind(x, "XRootWindow", Window, Display, C.c_int)
        self.XWhitePixel = bind(x, "XWhitePixel", C.c_ulong, Display, C.c_int)
        self.XBlackPixel = bind(x, "XBlackPixel", C.c_ulong, Display, C.c_int)
        self.XGetGeometry = bind(
            x, "XGetGeometry", C.c_int, Display, Window,
            C.POINTER(Window), C.POINTER(C.c_int), C.POINTER(C.c_int),
            C.POINTER(C.c_uint), C.POINTER(C.c_uint),
            C.POINTER(C.c_uint), C.POINTER(C.c_uint),
        )
        self.XCreateSimpleWindow = bind(
            x, "XCreateSimpleWindow", Window, Display, Window,
            C.c_int, C.c_int, C.c_uint, C.c_uint,
            C.c_uint, C.c_ulong, C.c_ulong,
        )
        self.XChangeWindowAttributes = bind(
            x, "XChangeWindowAttributes", C.c_int, Display, Window,
            C.c_ulong, C.POINTER(XSetWindowAttributes),
        )
        self.XInternAtom = bind(x, "XInternAtom", Atom, Display, C.c_char_p, C.c_int)
        self.XChangeProperty = bind(
            x, "XChangeProperty", C.c_int, Display, Window, Atom, Atom,
            C.c_int, C.c_int, C.POINTER(C.c_ubyte), C.c_int,
        )
        self.XStoreName = bind(x, "XStoreName", C.c_int, Display, Window, C.c_char_p)
        self.XMapWindow = bind(x, "XMapWindow", C.c_int, Display, Window)
        self.XMoveResizeWindow = bind(
            x, "XMoveResizeWindow", C.c_int, Display, Window,
            C.c_int, C.c_int, C.c_uint, C.c_uint,
        )
        self.XLowerWindow = bind(x, "XLowerWindow", C.c_int, Display, Window)
        self.XFlush = bind(x, "XFlush", C.c_int, Display)
        self.XDestroyWindow = bind(x, "XDestroyWindow", C.c_int, Display, Window)

    def _screen_size(self):
        root_return = Window()
        x = C.c_int()
        y = C.c_int()
        width = C.c_uint()
        height = C.c_uint()
        border = C.c_uint()
        depth = C.c_uint()
        status = self.XGetGeometry(
            self.display, self.root, C.byref(root_return),
            C.byref(x), C.byref(y), C.byref(width), C.byref(height),
            C.byref(border), C.byref(depth),
        )
        if not status or not width.value or not height.value:
            raise RuntimeError("No se pudo determinar el tamano de la pantalla X11.")
        return width.value, height.value

    def _set_desktop_type(self):
        """Marca EWMH DESKTOP; los gestores compatibles mantienen el fondo atras."""
        property_atom = self.XInternAtom(self.display, b"_NET_WM_WINDOW_TYPE", 0)
        desktop_atom = self.XInternAtom(self.display, b"_NET_WM_WINDOW_TYPE_DESKTOP", 0)
        if property_atom and desktop_atom:
            atom_data = Atom(desktop_atom)
            self.XChangeProperty(
                self.display, self.window, property_atom, XA_ATOM,
                32, PropModeReplace,
                C.cast(C.byref(atom_data), C.POINTER(C.c_ubyte)), 1,
            )

    def create_background(self):
        screen = self.XDefaultScreen(self.display)
        self.root = self.XRootWindow(self.display, screen)
        width, height = self._screen_size()
        self.size = (width, height)
        white = self.XWhitePixel(self.display, screen)
        black = self.XBlackPixel(self.display, screen)

        # Esta es la unica figura del paso 1: un rectangulo completamente blanco.
        self.window = self.XCreateSimpleWindow(
            self.display, self.root, 0, 0, width, height, 0, black, white,
        )
        if not self.window:
            raise RuntimeError("No se pudo crear la capa blanca.")

        attributes = XSetWindowAttributes()
        attributes.override_redirect = 1  # Sin bordes ni barra del gestor de ventanas.
        self.XChangeWindowAttributes(
            self.display, self.window, CWOverrideRedirect, C.byref(attributes),
        )
        self._set_desktop_type()
        self.XStoreName(self.display, self.window, b"PYRION OS - Fondo blanco")
        self.XMapWindow(self.display, self.window)
        self.XLowerWindow(self.display, self.window)
        self.XFlush(self.display)
        print(f"PYRION: fondo blanco {width}x{height}, capa inferior X11.", flush=True)

    def run(self):
        self.create_background()
        while self.running:
            # Por si cambia la resolucion, el fondo sigue cubriendo toda la pantalla.
            new_size = self._screen_size()
            if new_size != self.size:
                self.XMoveResizeWindow(self.display, self.window, 0, 0, *new_size)
                self.size = new_size

            # Otras ventanas, aplicaciones y cuadros de dialogo quedan por encima.
            self.XLowerWindow(self.display, self.window)
            self.XFlush(self.display)
            time.sleep(1)

    def stop(self, *_args):
        self.running = False

    def close(self):
        if self.display:
            if self.window:
                self.XDestroyWindow(self.display, self.window)
                self.window = Window(0)
            self.XCloseDisplay(self.display)
            self.display = None


def ctypes_libx11():
    """Usa libX11 ya instalada; no descarga ni instala paquetes."""
    return ctypes.util.find_library("X11") or "libX11.so.6"


def main():
    if "--check" in sys.argv[1:]:
        try:
            C.CDLL(ctypes_libx11())
            print("OK: libX11 disponible. DISPLAY=" + os.environ.get("DISPLAY", "(no definido)"))
            return 0
        except OSError as exc:
            print("ERROR: libX11 no disponible: " + str(exc), file=sys.stderr)
            return 2

    try:
        desktop = PyrionDesktop()
    except (OSError, RuntimeError) as exc:
        print("PYRION: " + str(exc), file=sys.stderr)
        return 1

    signal.signal(signal.SIGINT, desktop.stop)
    signal.signal(signal.SIGTERM, desktop.stop)
    try:
        desktop.run()
        return 0
    except (OSError, RuntimeError) as exc:
        print("PYRION: " + str(exc), file=sys.stderr)
        return 1
    finally:
        desktop.close()


if __name__ == "__main__":
    raise SystemExit(main())
