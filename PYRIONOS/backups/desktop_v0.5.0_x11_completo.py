#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PYRION OS Desktop - interfaz nativa X11 con Python y ctypes.

No depende de PySide6, Tkinter, FLTK, Python-Xlib ni pip. Utiliza libX11
(ya incluida en Mini Linux) y, cuando existe, libXft para texto UTF-8.
Los paneles y botones redondeados se dibujan directamente mediante X11.
La extensión opcional XShape recorta realmente las esquinas exteriores.

Compatible con app.py RAM/GitHub: contiene PyrionDesktop y main().
Ejecucion: python3 desktop.py
Diagnostico: python3 desktop.py --check

El programa no particiona, formatea, monta ni escribe en discos por si solo.
"""
from __future__ import annotations

import ast
import ctypes as C
import ctypes.util
import csv
import datetime as dt
import math
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass

APP_NAME = "PYRION OS"
APP_VERSION = "0.5.0-x11"

# ===== X11 ABI, para maquinas Linux de 32 o 64 bits =====
ulong = C.c_ulong
uint = C.c_uint
voidp = C.c_void_p
int32 = C.c_int

class XColor(C.Structure):
    _fields_ = [("pixel", ulong), ("red", C.c_ushort), ("green", C.c_ushort),
                ("blue", C.c_ushort), ("flags", C.c_byte), ("pad", C.c_byte)]

class XRenderColor(C.Structure):
    _fields_ = [("red", C.c_ushort), ("green", C.c_ushort),
                ("blue", C.c_ushort), ("alpha", C.c_ushort)]

class XftColor(C.Structure):
    _fields_ = [("pixel", ulong), ("color", XRenderColor)]

class XGlyphInfo(C.Structure):
    _fields_ = [("width", C.c_ushort), ("height", C.c_ushort),
                ("x", C.c_short), ("y", C.c_short),
                ("xOff", C.c_short), ("yOff", C.c_short)]

class XPoint(C.Structure):
    _fields_ = [("x", C.c_short), ("y", C.c_short)]

class XKeyEvent(C.Structure):
    _fields_ = [("type", int32), ("serial", ulong), ("send_event", int32),
                ("display", voidp), ("window", ulong), ("root", ulong),
                ("subwindow", ulong), ("time", ulong), ("x", int32),
                ("y", int32), ("x_root", int32), ("y_root", int32),
                ("state", uint), ("keycode", uint), ("same_screen", int32)]

class XButtonEvent(C.Structure):
    _fields_ = [("type", int32), ("serial", ulong), ("send_event", int32),
                ("display", voidp), ("window", ulong), ("root", ulong),
                ("subwindow", ulong), ("time", ulong), ("x", int32),
                ("y", int32), ("x_root", int32), ("y_root", int32),
                ("state", uint), ("button", uint), ("same_screen", int32)]

class XMotionEvent(C.Structure):
    _fields_ = [("type", int32), ("serial", ulong), ("send_event", int32),
                ("display", voidp), ("window", ulong), ("root", ulong),
                ("subwindow", ulong), ("time", ulong), ("x", int32),
                ("y", int32), ("x_root", int32), ("y_root", int32),
                ("state", uint), ("is_hint", C.c_byte), ("same_screen", int32)]

class XConfigureEvent(C.Structure):
    _fields_ = [("type", int32), ("serial", ulong), ("send_event", int32),
                ("display", voidp), ("event", ulong), ("window", ulong),
                ("x", int32), ("y", int32), ("width", int32), ("height", int32),
                ("border_width", int32), ("above", ulong), ("override_redirect", int32)]

class XClientMessageData(C.Union):
    _fields_ = [("b", C.c_char*20), ("s", C.c_short*10), ("l", C.c_long*5)]

class XClientMessageEvent(C.Structure):
    _fields_ = [("type", int32), ("serial", ulong), ("send_event", int32),
                ("display", voidp), ("window", ulong), ("message_type", ulong),
                ("format", int32), ("data", XClientMessageData)]

class XEvent(C.Union):
    _fields_ = [("type", int32), ("xkey", XKeyEvent),
                ("xbutton", XButtonEvent), ("xmotion", XMotionEvent),
                ("xconfigure", XConfigureEvent), ("xclient", XClientMessageEvent),
                ("pad", C.c_long*24)]

class X11Error(RuntimeError):
    pass


def bind(library, name, result, *args, required=True):
    function = getattr(library, name, None)
    if function is None:
        if required:
            raise X11Error("No existe %s en la biblioteca X11" % name)
        return None
    function.restype = result
    function.argtypes = list(args)
    return function


def rgb(hex_value):
    n = hex_value.strip().lstrip("#")
    return tuple(int(n[i:i+2], 16) for i in (0, 2, 4))


class X11Canvas:
    def __init__(self):
        if not sys.platform.startswith("linux"):
            raise X11Error("PYRION X11 requiere Linux (DISPLAY/Xorg).")
        try:
            self.x = C.CDLL(ctypes.util.find_library("X11") or "libX11.so.6")
        except OSError as exc:
            raise X11Error("Falta libX11: %s" % exc) from exc
        x = self.x
        self.open_display = bind(x, "XOpenDisplay", voidp, C.c_char_p)
        self.close_display = bind(x, "XCloseDisplay", int32, voidp)
        self.default_screen = bind(x, "XDefaultScreen", int32, voidp)
        self.default_visual = bind(x, "XDefaultVisual", voidp, voidp, int32)
        self.default_colormap = bind(x, "XDefaultColormap", ulong, voidp, int32)
        self.default_depth = bind(x, "XDefaultDepth", int32, voidp, int32)
        self.root_window = bind(x, "XRootWindow", ulong, voidp, int32)
        self.screen_width = bind(x, "XDisplayWidth", int32, voidp, int32)
        self.screen_height = bind(x, "XDisplayHeight", int32, voidp, int32)
        self.create_window = bind(x, "XCreateSimpleWindow", ulong, voidp, ulong,
                                  int32, int32, uint, uint, uint, ulong, ulong)
        self.store_name = bind(x, "XStoreName", int32, voidp, ulong, C.c_char_p)
        self.select_input = bind(x, "XSelectInput", int32, voidp, ulong, C.c_long)
        self.intern_atom = bind(x, "XInternAtom", ulong, voidp, C.c_char_p, int32)
        self.set_wm_protocols = bind(x, "XSetWMProtocols", int32, voidp, ulong, C.POINTER(ulong), int32)
        self.map_window = bind(x, "XMapWindow", int32, voidp, ulong)
        self.create_gc = bind(x, "XCreateGC", voidp, voidp, ulong, ulong, voidp)
        self.free_gc = bind(x, "XFreeGC", int32, voidp, voidp)
        self.create_pixmap = bind(x, "XCreatePixmap", ulong, voidp, ulong, uint, uint, uint)
        self.free_pixmap = bind(x, "XFreePixmap", int32, voidp, ulong)
        self.copy_area = bind(x, "XCopyArea", int32, voidp, ulong, ulong, voidp,
                              int32, int32, uint, uint, int32, int32)
        self.alloc_color = bind(x, "XAllocColor", int32, voidp, ulong, C.POINTER(XColor))
        self.set_foreground = bind(x, "XSetForeground", int32, voidp, voidp, ulong)
        self.set_line_attributes = bind(x, "XSetLineAttributes", int32, voidp, voidp,
                                        uint, int32, int32, int32)
        self.fill_rectangle = bind(x, "XFillRectangle", int32, voidp, ulong, voidp,
                                   int32, int32, uint, uint)
        self.fill_arc = bind(x, "XFillArc", int32, voidp, ulong, voidp,
                             int32, int32, uint, uint, int32, int32)
        self.draw_arc = bind(x, "XDrawArc", int32, voidp, ulong, voidp,
                             int32, int32, uint, uint, int32, int32)
        self.draw_line = bind(x, "XDrawLine", int32, voidp, ulong, voidp,
                              int32, int32, int32, int32)
        self.draw_rectangle = bind(x, "XDrawRectangle", int32, voidp, ulong, voidp,
                                   int32, int32, uint, uint)
        self.fill_polygon = bind(x, "XFillPolygon", int32, voidp, ulong, voidp,
                                 C.POINTER(XPoint), int32, int32, int32)
        self.next_event = bind(x, "XNextEvent", int32, voidp, C.POINTER(XEvent))
        self.pending = bind(x, "XPending", int32, voidp)
        self.flush = bind(x, "XFlush", int32, voidp)
        self.lookup_string = bind(x, "XLookupString", int32, C.POINTER(XKeyEvent),
                                  voidp, int32, C.POINTER(ulong), voidp)
        self.connection_number = bind(x, "XConnectionNumber", int32, voidp)
        self.load_query_font = bind(x, "XLoadQueryFont", voidp, voidp, C.c_char_p)
        self.set_font = bind(x, "XSetFont", int32, voidp, voidp, ulong)
        self.draw_string = bind(x, "XDrawString", int32, voidp, ulong, voidp,
                                int32, int32, C.c_char_p, int32)
        self.free_font = bind(x, "XFreeFont", int32, voidp, voidp)
        self.create_font_cursor = bind(x, "XCreateFontCursor", ulong, voidp, uint)
        self.define_cursor = bind(x, "XDefineCursor", int32, voidp, ulong, ulong)
        self.undefine_cursor = bind(x, "XUndefineCursor", int32, voidp, ulong)
        self.destroy_window = bind(x, "XDestroyWindow", int32, voidp, ulong)
        self.dpy = self.open_display(None)
        if not self.dpy:
            raise X11Error("No se pudo conectar a X11. DISPLAY=%r. Inicia Xorg primero." % os.getenv("DISPLAY"))
        self.screen = self.default_screen(self.dpy)
        self.root = self.root_window(self.dpy, self.screen)
        self.visual = self.default_visual(self.dpy, self.screen)
        self.colormap = self.default_colormap(self.dpy, self.screen)
        sw = self.screen_width(self.dpy, self.screen)
        sh = self.screen_height(self.dpy, self.screen)
        self.width = min(1260, max(520, sw - 55))
        self.height = min(820, max(460, sh - 65))
        self.window = self.create_window(self.dpy, self.root,
                                          max(0, (sw-self.width)//2),
                                          max(0, (sh-self.height)//2),
                                          self.width, self.height, 0, 0, 0)
        if not self.window:
            raise X11Error("XCreateSimpleWindow no devolvio una ventana.")
        self.store_name(self.dpy, self.window, b"PYRION OS - Native X11 Desktop")
        # KeyPress / ButtonPress / Motion / Expose / StructureNotify.
        self.select_input(self.dpy, self.window,
                          (1 << 0) | (1 << 2) | (1 << 6) | (1 << 15) | (1 << 17))
        self.delete_atom = self.intern_atom(self.dpy, b"WM_DELETE_WINDOW", 0)
        protocol = (ulong*1)(self.delete_atom)
        self.set_wm_protocols(self.dpy, self.window, protocol, 1)
        self.colors = {}
        self.ftcolors = {}
        self.core_font = self.load_query_font(self.dpy, b"fixed")
        self.offscreen = 0
        self.gc = self.create_gc(self.dpy, self.window, 0, None)
        self.shapes_enabled = False
        self.shape = None
        self._init_shape()
        self.xft = None
        self.ftdraw = None
        self.fonts = {}
        self._init_xft()
        self.hand = self.create_font_cursor(self.dpy, 60)  # XC_hand2
        self.has_pointer = False
        self._new_backbuffer()
        self._apply_shape()
        self.map_window(self.dpy, self.window)
        self.flush(self.dpy)

    def _init_shape(self):
        try:
            ext = C.CDLL(ctypes.util.find_library("Xext") or "libXext.so.6")
            query = bind(ext, "XShapeQueryExtension", int32, voidp,
                         C.POINTER(int32), C.POINTER(int32))
            self.shape_combine = bind(ext, "XShapeCombineMask", None,
                                      voidp, ulong, int32, int32, int32, ulong, int32)
            event, err = int32(), int32()
            if query(self.dpy, C.byref(event), C.byref(err)):
                self.shapes_enabled = True
                self.shape = ext
        except (OSError, X11Error):
            pass

    def _init_xft(self):
        try:
            ft = C.CDLL(ctypes.util.find_library("Xft") or "libXft.so.2")
            self.xft_font_open = bind(ft, "XftFontOpenName", voidp, voidp, int32, C.c_char_p)
            self.xft_font_close = bind(ft, "XftFontClose", None, voidp, voidp)
            self.xft_draw_create = bind(ft, "XftDrawCreate", voidp, voidp, ulong, voidp, ulong)
            self.xft_draw_destroy = bind(ft, "XftDrawDestroy", None, voidp)
            self.xft_draw_string = bind(ft, "XftDrawStringUtf8", None,
                                        voidp, C.POINTER(XftColor), voidp, int32, int32,
                                        C.c_char_p, int32)
            self.xft_extents = bind(ft, "XftTextExtentsUtf8", None, voidp, voidp,
                                    C.c_char_p, int32, C.POINTER(XGlyphInfo))
            self.xft_color_alloc = bind(ft, "XftColorAllocValue", int32, voidp, voidp,
                                        ulong, C.POINTER(XRenderColor), C.POINTER(XftColor))
            self.xft_color_free = bind(ft, "XftColorFree", None, voidp, voidp,
                                       ulong, C.POINTER(XftColor))
            families = {
                'small': b'DejaVu Sans:size=9',
                'body': b'DejaVu Sans:size=11',
                'medium': b'DejaVu Sans:style=Bold:size=11',
                'head': b'DejaVu Sans:style=Bold:size=16',
                'hero': b'DejaVu Sans:style=Bold:size=21',
                'brand': b'DejaVu Sans:style=Bold:size=21',
                'mono': b'DejaVu Sans Mono:size=10',
            }
            for k, name in families.items():
                f = self.xft_font_open(self.dpy, self.screen, name)
                if f:
                    self.fonts[k] = f
            if self.fonts:
                self.xft = ft
        except (OSError, X11Error):
            pass

    def _new_backbuffer(self):
        if self.ftdraw:
            self.xft_draw_destroy(self.ftdraw)
            self.ftdraw = None
        if self.offscreen:
            self.free_pixmap(self.dpy, self.offscreen)
        self.offscreen = self.create_pixmap(self.dpy, self.window,
                                            max(1, self.width), max(1, self.height),
                                            self.default_depth(self.dpy, self.screen))
        if not self.offscreen:
            raise X11Error("No hay memoria X11 para el buffer grafico.")
        if self.xft:
            self.ftdraw = self.xft_draw_create(self.dpy, self.offscreen,
                                               self.visual, self.colormap)

    def _apply_shape(self):
        if not self.shapes_enabled:
            return
        mask = self.create_pixmap(self.dpy, self.window,
                                  max(1, self.width), max(1, self.height), 1)
        if not mask:
            return
        gc = self.create_gc(self.dpy, mask, 0, None)
        if not gc:
            self.free_pixmap(self.dpy, mask)
            return
        self.set_foreground(self.dpy, gc, 0)
        self.fill_rectangle(self.dpy, mask, gc, 0, 0, self.width, self.height)
        self.set_foreground(self.dpy, gc, 1)
        self._round_on(mask, gc, 0, 0, self.width, self.height, 19)
        self.shape_combine(self.dpy, self.window, 0, 0, 0, mask, 0)
        self.free_gc(self.dpy, gc)
        self.free_pixmap(self.dpy, mask)

    def resize(self, width, height):
        width, height = max(480, width), max(430, height)
        if width != self.width or height != self.height:
            self.width, self.height = width, height
            self._new_backbuffer()
            self._apply_shape()
            return True
        return False

    def pixel(self, color):
        if color in self.colors:
            return self.colors[color]
        r,g,b = rgb(color)
        item = XColor(0, r*257, g*257, b*257, 7, 0)
        if not self.alloc_color(self.dpy, self.colormap, C.byref(item)):
            # On truecolor displays this should not fail; use black otherwise.
            return 0
        self.colors[color] = item.pixel
        return item.pixel

    def foreground(self, color, gc=None):
        self.set_foreground(self.dpy, gc or self.gc, self.pixel(color))

    def rect(self, x, y, w, h, color):
        if w<=0 or h<=0: return
        self.foreground(color)
        self.fill_rectangle(self.dpy, self.offscreen, self.gc,
                            int(x), int(y), int(w), int(h))

    def _round_on(self, target, gc, x, y, w, h, r):
        x,y,w,h,r = int(x),int(y),int(w),int(h),int(r)
        if w<=0 or h<=0: return
        r=max(0,min(r,w//2,h//2))
        if not r:
            self.fill_rectangle(self.dpy,target,gc,x,y,w,h)
            return
        d=2*r
        self.fill_rectangle(self.dpy,target,gc,x+r,y,w-2*r,h)
        self.fill_rectangle(self.dpy,target,gc,x,y+r,w,h-2*r)
        for px,py,a in ((x,y,90),(x+w-d,y,0),(x,y+h-d,180),(x+w-d,y+h-d,270)):
            self.fill_arc(self.dpy,target,gc,px,py,d,d,a*64,90*64)

    def rounded(self, x, y, w, h, r, color, border=None):
        if w<=0 or h<=0: return
        if border:
            self.foreground(border)
            self._round_on(self.offscreen,self.gc,x,y,w,h,r)
            if w>=3 and h>=3:
                self.foreground(color)
                self._round_on(self.offscreen,self.gc,x+1,y+1,w-2,h-2,max(0,r-1))
        else:
            self.foreground(color)
            self._round_on(self.offscreen,self.gc,x,y,w,h,r)

    def line(self, x1, y1, x2, y2, color, thickness=1):
        self.foreground(color)
        self.set_line_attributes(self.dpy,self.gc,max(1,int(thickness)),0,1,0)
        self.draw_line(self.dpy,self.offscreen,self.gc,
                       int(x1),int(y1),int(x2),int(y2))
        if thickness!=1:
            self.set_line_attributes(self.dpy,self.gc,1,0,1,0)

    def circle(self, x, y, radius, color, border=None):
        self.rounded(x-radius,y-radius,2*radius,2*radius,radius,color,border)

    def polygon(self, points, color):
        if len(points)<3:return
        self.foreground(color)
        array=(XPoint*len(points))(*(XPoint(int(x),int(y)) for x,y in points))
        self.fill_polygon(self.dpy,self.offscreen,self.gc,array,len(points),0,0)

    def _font(self, style):
        return self.fonts.get(style) or self.fonts.get('body') or next(iter(self.fonts.values()),None)

    def text_width(self, text, style='body'):
        if not text: return 0
        font = self._font(style)
        if self.xft and font:
            data=str(text).encode('utf-8')
            ext=XGlyphInfo()
            self.xft_extents(self.dpy,font,data,len(data),C.byref(ext))
            return int(ext.xOff)
        return len(str(text))*8

    def _ftcolor(self, hexvalue):
        if hexvalue in self.ftcolors:
            return self.ftcolors[hexvalue]
        r,g,b=rgb(hexvalue)
        raw=XRenderColor(r*257,g*257,b*257,65535)
        item=XftColor()
        if not self.xft_color_alloc(self.dpy,self.visual,self.colormap,C.byref(raw),C.byref(item)):
            return None
        self.ftcolors[hexvalue]=item
        return item

    def text(self, string, x, baseline, color='#e9f5ff', style='body', max_width=None):
        if string is None:return
        string=str(string).replace('\n',' ')
        if max_width is not None and self.text_width(string,style)>max_width:
            while string and self.text_width(string+'…',style)>max_width:
                string=string[:-1]
            string+='…' if string else ''
        if not string:return
        if self.xft and self.ftdraw and self._font(style):
            ftc=self._ftcolor(color)
            if ftc is not None:
                data=string.encode('utf-8')
                self.xft_draw_string(self.ftdraw,C.byref(ftc),self._font(style),
                                     int(x),int(baseline),data,len(data))
                return
        # Sin Xft: usar fuente core de X11, sustituyendo glifos no latin1.
        self.foreground(color)
        if self.core_font:
            # XFontStruct.fid no se lee de forma insegura; se usa la fuente GC por defecto.
            pass
        encoded=string.encode('latin-1','replace')
        self.draw_string(self.dpy,self.offscreen,self.gc,int(x),int(baseline),encoded,len(encoded))

    def flush_buffer(self):
        self.copy_area(self.dpy,self.offscreen,self.window,self.gc,
                       0,0,self.width,self.height,0,0)
        self.flush(self.dpy)

    def pointer(self, enabled):
        if enabled!=self.has_pointer:
            self.has_pointer=enabled
            if enabled:
                self.define_cursor(self.dpy,self.window,self.hand)
            else:
                self.undefine_cursor(self.dpy,self.window)

    def cleanup(self):
        try:
            if self.ftdraw:self.xft_draw_destroy(self.ftdraw)
            for item in self.ftcolors.values():
                self.xft_color_free(self.dpy,self.visual,self.colormap,C.byref(item))
            for font in self.fonts.values():self.xft_font_close(self.dpy,font)
            if self.offscreen:self.free_pixmap(self.dpy,self.offscreen)
            if self.gc:self.free_gc(self.dpy,self.gc)
            if self.core_font:self.free_font(self.dpy,self.core_font)
            if self.window:self.destroy_window(self.dpy,self.window)
        finally:
            if self.dpy:self.close_display(self.dpy)


@dataclass
class Hit:
    x:int; y:int; w:int; h:int; action:object; tooltip:str=''
    def contains(self,px,py):
        return self.x<=px<self.x+self.w and self.y<=py<self.y+self.h


class PyrionDesktop:
    """Escritorio X11 autonomo: sin motor Qt, sin montajes ni persistencia."""
    BG='#091321'; HEADER='#111e30'; SIDEBAR='#101c2e'; SURFACE='#13253b'
    PANEL='#152a42'; LINE='#294765'; TEXT='#ecf6ff'; MUTED='#a3b7cd'
    CYAN='#62d7ff'; BLUE='#207fca'; GREEN='#57e2ac'

    def __init__(self):
        self.x=X11Canvas()
        self.page='Inicio'
        self.focus=None
        self.query=''
        self.console_cmd=''
        self.console_log=['PYRION Console  ·  X11 nativo',
                          'Escribe help para ver los comandos disponibles.']
        self.history=[]
        self.notifications='Sistema listo · Sin dependencias Python externas'
        self.hits=[]
        self.hover=-1
        self.tool_tab=None
        self.calc_expr=''
        self.csv_path=None
        self.csv_data=[]
        self.files_dir=Path.home()
        self.file_entries=[]
        self.file_scroll=0
        self.last_clock=''
        self.running=True
        self._refresh_files()
        self.record('Escritorio X11 iniciado')
        self.paint()

    def record(self,what):
        self.history.insert(0,(dt.datetime.now().strftime('%H:%M:%S'),what))
        self.history=self.history[:80]

    def add_hit(self,x,y,w,h,action,tooltip=''):
        self.hits.append(Hit(int(x),int(y),int(w),int(h),action,tooltip))

    def text(self,txt,x,y,color=None,style='body',max_width=None):
        self.x.text(txt,x,y,color or self.TEXT,style,max_width)

    def button(self,text,x,y,w,h,action,selected=False,primary=False,small=False,rounding=12):
        c=self.x
        fill=('#1fc1ed' if primary else '#244c72' if selected else '#17283e')
        border=('#67e1ff' if primary else '#3c78a7' if selected else '#344f6c')
        c.rounded(x,y,w,h,rounding,fill,border)
        tc='#09243a' if primary else '#ffffff' if selected else '#d1e0f0'
        st='medium' if not small else 'small'
        tw=c.text_width(text,st)
        self.text(text,x+max(9,(w-tw)//2),y+(h//2)+(4 if not small else 3),tc,st,max(0,w-14))
        self.add_hit(x,y,w,h,action,text)

    def _nav(self,label,y,icon):
        c=self.x
        w=c.width
        side=208 if w>=830 else 62
        selected=self.page==label
        c.rounded(12,y,side-24,47,13,'#176eab' if selected else '#19283d',
                  '#54cffa' if selected else '#2d455f')
        self.text(icon,27,y+30,'#c6f5ff' if selected else '#9fd5ec','medium')
        if side>=160:
            self.text(label,61,y+30,'#ffffff' if selected else '#d5e5f6','medium',side-80)
        self.add_hit(12,y,side-24,47,lambda name=label:self.set_page(name))

    def set_page(self,name):
        self.page=name
        self.focus=None
        self.notifications=f'{name} · PYRION UI X11'
        self.record('Abrir '+name)
        self.paint()

    def open_tool(self,name):
        if name=='Visor de archivos':
            self.set_page('Archivos');return
        if name=='PYRION Console':
            self.set_page('Consola');return
        self.tool_tab=name
        self.set_page(name)

    def _draw_hero_mountains(self,x,y,w,h):
        c=self.x
        # Decoracion de montanas, sin imagen externa ni carga de archivos.
        if w<460:return
        right=x+w-14
        moon=min(86,h//2-12)
        if moon>15:
            c.circle(right-95,y+int(h*.51),moon,'#075681')
            c.circle(right-95,y+int(h*.51),max(1,moon-9),'#086c9c')
            c.circle(right-92,y+int(h*.51)+5,max(1,moon-14),'#0d436c')
        bottom=y+h-7
        for dx,col in ((0,'#0d2842'),(17,'#0a3654'),(32,'#0c2641')):
            pts=[(right-210-dx,bottom),(right-145-dx,y+h//2+40),
                 (right-105-dx,y+h//2+52),(right-63-dx,y+h//2+5),
                 (right-25,bottom-45),(right,bottom),(right-210-dx,bottom)]
            c.polygon(pts,col)
        c.line(right-130,y+h//2+58,right-64,y+h//2+6,'#1779ad',2)

    def _header(self):
        c=self.x;w,h=c.width,c.height
        c.rounded(0,0,w,78,19,self.HEADER)
        c.rect(0,60,w,18,self.HEADER)
        c.line(0,77,w,77,'#2d4766')
        # Logos geometricos azul cian, vectoriales
        c.polygon([(29,55),(49,18),(68,55),(53,47),(49,36),(43,47)],'#4acaf4')
        c.polygon([(40,55),(49,36),(58,55)],'#145282')
        self.text('PYRION',82,46,'#d3f2ff','brand')
        if w>=760:
            c.rounded(232,23,120,33,16,'#153b34','#2f6f65')
            c.circle(250,40,5,'#31e2a9')
            self.text('X11 ACTIVO',263,44,'#8cfbd3','small')
        right=w-165
        if w>=940:
            self.text('Linux  •  Python  •  Ligero',right-180,43,'#8eacc7','small')
        self.text(dt.datetime.now().strftime('%H:%M'),w-94,45,'#d7e9fa','medium')
        self.button('×',w-44,23,30,29,self.stop,small=False,rounding=10)

    def _sidebar(self):
        c=self.x;h=c.height;w=c.width
        side=208 if w>=830 else 62
        c.rect(0,79,side,h-117,self.SIDEBAR)
        c.line(side,79,side,h-40,'#27435e')
        if side>140:
            self.text('ESCRITORIO',21,116,'#7295b4','small')
        for i,(p,icon) in enumerate((('Inicio','⌂'),('Aplicaciones','▦'),
                                     ('Consola','>_'),('Archivos','▱'),
                                     ('Configuración','⚙'))):
            self._nav(p,130+i*61,icon)
        if side>140 and h>=610:
            by=h-144
            c.rounded(12,by,side-24,96,13,'#11263c','#315b78')
            c.polygon([(45,by+39),(62,by+6),(80,by+39),(66,by+31),
                       (62,by+21),(58,by+31)],'#43c9f4')
            self.text('PYRION OS',27,by+62,'#bdedff','medium')
            self.text('Linux · X11 · Ligero',27,by+80,'#90abc6','small')

    def _tabbar(self,left,right):
        c=self.x
        titles=['Inicio','Aplicaciones','Archivos','Consola','Configuración']
        width=right-left
        if width<650:
            titles=[self.page if self.page in titles else 'Inicio']
        x=left
        for t in titles:
            tw=min(141,max(100,c.text_width(t,'small')+32))
            if x+tw>right:break
            active=(self.page==t)
            self.button(t,x,91,tw,36,lambda val=t:self.set_page(val),selected=active,
                        primary=active,small=True,rounding=16)
            x+=tw+9
        c.line(left,137,right,137,'#243e5a')

    def _home(self,left,right,top,bottom):
        c=self.x;w=right-left;avail=bottom-top
        compact=avail<475
        hero_h=137 if compact else 171
        c.rounded(left,top,w,hero_h,18,'#132944','#326489')
        self._draw_hero_mountains(left,top,w,hero_h)
        self.text('¿Qué quieres hacer hoy?',left+25,top+42,'#f1f8ff','hero',w-58)
        self.text('Busca una herramienta, archivo o comando.',left+26,top+67,'#acc3d9','body',w-50)
        sx=left+25;sy=top+91 if not compact else top+79
        sh=48 if not compact else 42
        sbw=min(139,max(97,w//5))
        iw=max(70,w-77-sbw)
        c.rounded(sx,sy,iw,sh,sh//2,'#1b314d','#59c7ee' if self.focus=='search' else '#446e92')
        self.text('⌕',sx+17,sy+sh//2+5,'#75c8eb','medium')
        search=self.query if self.query else 'Buscar o escribir un comando...'
        self.text(search,sx+48,sy+sh//2+5,'#ffffff' if self.query else '#a0b6d0','body',iw-65)
        if self.focus=='search':
            pos=min(sx+49+c.text_width(self.query),sx+iw-16)
            c.line(pos,sy+10,pos,sy+sh-11,self.CYAN)
        self.add_hit(sx,sy,iw,sh,lambda:self.set_focus('search'))
        self.button('Ejecutar',sx+iw+11,sy,sbw,sh,self.search,primary=True,rounding=sh//2)
        y=top+hero_h+31
        self.text('▦  Aplicaciones destacadas',left+5,y,'#eaf4ff','medium')
        action_w=80
        self.text('Ver todas >',right-action_w,y,self.CYAN,'small',action_w)
        self.add_hit(right-action_w,y-18,action_w,24,lambda:self.set_page('Aplicaciones'))
        card_y=y+17
        gap=12
        apps=[('Calculadora','Cálculos rápidos','＋','#4547c1'),
              ('Editor CSV','Hojas de datos','▦','#13784f'),
              ('PDF a Word','Documentos PDF','PDF','#a73250'),
              ('Visor de archivos','Explorar carpetas','▱','#1465a1')]
        columns=4 if w>=730 else 2
        card_w=(w-(columns-1)*gap)//columns
        card_h=88 if columns==4 else 62
        if compact and columns==2:card_h=57
        for i,(name,desc,icon,col) in enumerate(apps):
            ix=i%columns;iy=i//columns
            cx=left+ix*(card_w+gap);cy=card_y+iy*(card_h+9)
            c.rounded(cx,cy,card_w,card_h,14,self.PANEL,'#315471')
            ic=39 if columns==4 else 33
            c.rounded(cx+11,cy+(card_h-ic)//2,ic,ic,10,col)
            self.text(icon,cx+19,cy+card_h//2+5,'#ffffff','medium',ic-9)
            off=11+ic+12
            self.text(name,cx+off,cy+card_h//2-3,'#eff7ff','medium',card_w-off-8)
            self.text(desc,cx+off,cy+card_h//2+16,'#aec2d5','small',card_w-off-8)
            self.add_hit(cx,cy,card_w,card_h,lambda n=name:self.open_tool(n))
        lower=card_y+((len(apps)+columns-1)//columns)*(card_h+9)+9
        remaining=bottom-lower
        if remaining<60:return
        gap=14
        half=(w-gap)//2
        self._console_preview(left,lower,half,remaining)
        self._recent_preview(left+half+gap,lower,w-half-gap,remaining)

    def _console_preview(self,x,y,w,h):
        c=self.x
        c.rounded(x,y,w,h,16,'#13263d','#335676')
        self.text('>_  Consola (vista previa)',x+18,y+29,'#e9f5ff','medium',w-120)
        if w>350:
            self.text('Abrir consola >',x+w-115,y+29,self.CYAN,'small',110)
            self.add_hit(x+w-125,y+12,120,28,lambda:self.set_page('Consola'))
        c.rounded(x+10,y+40,w-20,h-49,11,'#081521','#243a56')
        lines=['pyrion@pyrion:~$ python3 --version',
               'Python 3 · X11 nativo',
               'PYRION OS  |  interfaz ligera',
               'Sin Qt ni Tkinter',
               'pyrion@pyrion:~$ _']
        for i,text in enumerate(lines[:max(1,(h-56)//20)]):
            self.text(text,x+23,y+64+i*20,
                      '#78e0b0' if i==0 or i==4 else '#a4cbe2',
                      'mono',w-48)
        self.add_hit(x,y,w,h,lambda:self.set_page('Consola'))

    def _recent_preview(self,x,y,w,h):
        c=self.x
        c.rounded(x,y,w,h,16,'#14273d','#345c7b')
        self.text('▱  Archivos recientes',x+18,y+29,'#eff8ff','medium',w-140)
        if w>330:
            self.text('Abrir archivos >',x+w-118,y+29,self.CYAN,'small',113)
        lines=[('▦','Reporte de datos','CSV'),('▤','Documentos','TXT'),
               ('▱','Carpetas de trabajo','DIR')]
        for i,(icon,name,ext) in enumerate(lines):
            yy=y+48+i*39
            if yy+28>y+h:break
            c.rounded(x+12,yy,w-24,35,7,'#172c44')
            self.text(icon,x+22,yy+23,'#64d9fa','medium')
            self.text(name,x+55,yy+23,'#d0e5f7','body',w-127)
            self.text(ext,x+w-47,yy+22,'#88abc8','small')
        self.add_hit(x,y,w,h,lambda:self.set_page('Archivos'))

    def _section_heading(self,title,subtitle,left,top,max_width):
        self.text(title,left,top+20,self.TEXT,'head',max_width)
        self.text(subtitle,left,top+47,self.MUTED,'body',max_width)

    def _apps(self,left,right,top,bottom):
        c=self.x;w=right-left
        self._section_heading('Aplicaciones','Herramientas de PYRION OS disponibles en esta sesión.',left,top,w)
        apps=[('Calculadora','Cálculos matemáticos básicos','＋','#4d48b5'),
              ('Editor CSV','Consultar archivos CSV','▦','#13784f'),
              ('PDF a Word','Integración pendiente de biblioteca','PDF','#a6324b'),
              ('Visor de archivos','Examinar archivos y directorios','▱','#135f9a'),
              ('PYRION Console','Terminal básico integrado','>_','#33667c')]
        cols=3 if w>=710 else 2 if w>=410 else 1
        gap=14
        cw=(w-gap*(cols-1))//cols
        for i,(name,desc,ico,col) in enumerate(apps):
            x=left+(i%cols)*(cw+gap);y=top+69+(i//cols)*107
            if y+85>bottom:break
            c.rounded(x,y,cw,94,15,'#182d46','#345575')
            c.rounded(x+12,y+16,43,43,11,col)
            self.text(ico,x+23,y+44,'#ffffff','medium',32)
            self.text(name,x+69,y+36,'#f1f9ff','medium',cw-80)
            self.text(desc,x+69,y+58,'#a6c1d8','small',cw-81)
            self.add_hit(x,y,cw,94,lambda n=name:self.open_tool(n))

    def _console(self,left,right,top,bottom):
        c=self.x;w=right-left
        self._section_heading('PYRION Console','Comandos básicos desde una pestaña X11.',left,top,w)
        y=top+64
        c.rounded(left,y,w,max(70,bottom-y-65),14,'#07131f','#315370')
        lines=self.console_log[-max(2,(bottom-y-89)//22):]
        for i,s in enumerate(lines):
            col=self.GREEN if s.startswith('pyrion@') else '#b7d2e8'
            self.text(s,left+19,y+31+i*22,col,'mono',w-42)
        sy=bottom-53
        c.rounded(left,sy,w-118,44,12,'#1b304a','#63bddf' if self.focus=='console' else '#395d7d')
        prompt='> '+self.console_cmd if self.console_cmd else '> Escribe help, ls, pwd, uname...'
        self.text(prompt,left+14,sy+29,self.TEXT if self.console_cmd else '#9bb3cc','mono',w-153)
        self.add_hit(left,sy,w-118,44,lambda:self.set_focus('console'))
        self.button('Ejecutar',right-105,sy,105,44,self.run_console,primary=True)

    def _files(self,left,right,top,bottom):
        c=self.x;w=right-left
        self._section_heading('Archivos','Explorador de solo lectura: ninguna operación de disco automática.',left,top,w)
        nav_y=top+65
        c.rounded(left,nav_y,w,44,11,'#1a3049','#385979')
        self.text('▱  '+str(self.files_dir),left+15,nav_y+28,self.CYAN,'small',w-139)
        self.button('Subir',right-95,nav_y+6,85,32,self.up_directory,small=True)
        y=nav_y+56
        for item in self.file_entries[self.file_scroll:self.file_scroll+max(1,(bottom-y)//39)]:
            if y+34>bottom:break
            path,isdir,size=item
            c.rounded(left,y,w,35,8,'#152b43','#2b4865')
            self.text('▱' if isdir else '▤',left+14,y+24,'#6dc8ef','medium')
            self.text(path.name,left+52,y+24,'#e1f0ff','body',w-190)
            self.text('CARPETA' if isdir else self._bytes(size),right-110,y+23,'#96aec6','small',100)
            self.add_hit(left,y,w,35,lambda p=path,d=isdir:self.open_file(p,d))
            y+=40

    @staticmethod
    def _bytes(n):
        if n<1024:return str(n)+' B'
        if n<1024*1024:return '%.1f KiB'%(n/1024)
        return '%.1f MiB'%(n/1024/1024)

    def _refresh_files(self):
        result=[]
        try:
            for idx,p in enumerate(self.files_dir.iterdir()):
                if idx>800:break
                try:
                    stat=p.stat()
                    result.append((p,p.is_dir(),stat.st_size))
                except (PermissionError,OSError):continue
        except (PermissionError,OSError) as exc:
            self.notifications='No se puede leer directorio: '+str(exc)
        self.file_entries=sorted(result,key=lambda item:(not item[1],item[0].name.lower()))
        self.file_scroll=0

    def up_directory(self):
        self.files_dir=self.files_dir.parent
        self._refresh_files();self.paint()

    def open_file(self,path,is_directory):
        if is_directory:
            self.files_dir=path
            self._refresh_files();self.paint()
            return
        if path.suffix.lower() in ('.csv','.tsv'):
            self.csv_path=path;self._load_csv();self.open_tool('Editor CSV')
        elif path.suffix.lower() in ('.txt','.md','.log','.json','.py','.ini','.cfg'):
            try:
                data=path.read_text(encoding='utf-8',errors='replace')[:5000]
                self.console_log=['Archivo: '+str(path)]+data.splitlines()[:90]
                self.set_page('Consola')
            except OSError as exc:
                self.notifications=str(exc);self.paint()
        else:
            self.notifications='Archivo seleccionado: '+str(path)
            self.paint()

    def _load_csv(self):
        if self.csv_path is None:return
        try:
            with self.csv_path.open('r',encoding='utf-8-sig',errors='replace',newline='') as fh:
                sample=fh.read(2048);fh.seek(0)
                try:dialect=csv.Sniffer().sniff(sample,delimiters=';,\t|')
                except csv.Error:dialect=csv.excel
                self.csv_data=[row[:10] for _,row in zip(range(100),csv.reader(fh,dialect))]
            self.notifications='CSV cargado: '+self.csv_path.name
        except OSError as exc:
            self.notifications='CSV no disponible: '+str(exc)

    def _csv(self,left,right,top,bottom):
        c=self.x;w=right-left
        self._section_heading('Editor CSV','Vista de datos ligera, sin bibliotecas externas.',left,top,w)
        self.button('Abrir CSV desde Archivos',left,top+61,min(w,238),39,
                    lambda:self.set_page('Archivos'),small=True)
        if not self.csv_data:
            c.rounded(left,top+118,w,95,12,self.PANEL,'#355675')
            self.text('Selecciona un archivo .csv en Archivos para visualizar su contenido.',
                      left+18,top+162,self.MUTED,'body',w-35)
            return
        y=top+116
        ncols=min(6,max(1,max(len(a) for a in self.csv_data)))
        cellw=max(45,(w-4)//ncols)
        for row_idx,row in enumerate(self.csv_data[:max(1,(bottom-y)//33)]):
            bg='#214361' if row_idx==0 else '#152b43' if row_idx%2==0 else '#10263a'
            c.rounded(left,y,w,32,4,bg)
            for ci in range(ncols):
                value=row[ci] if ci<len(row) else ''
                self.text(value,left+ci*cellw+8,y+22,self.TEXT,'small',cellw-14)
            y+=34

    def _calc(self,left,right,top,bottom):
        c=self.x;w=right-left
        self._section_heading('Calculadora','Operaciones seguras mediante Python, sin eval().',left,top,w)
        panelw=min(450,w)
        x=left+(w-panelw)//2;y=top+60
        c.rounded(x,y,panelw,63,13,'#11263d','#436a8a')
        value=self.calc_expr if self.calc_expr else '0'
        self.text(value,x+17,y+41,self.TEXT,'head',panelw-32)
        rows=[['7','8','9','/'],['4','5','6','*'],['1','2','3','-'],['C','0','.','+'],['(',')','⌫','=']]
        gap=9;cell=(panelw-3*gap)//4
        bh=max(33,min(47,(bottom-(y+83)-4*gap)//5))
        for ri,row in enumerate(rows):
            for ci,key in enumerate(row):
                xx=x+ci*(cell+gap);yy=y+83+ri*(bh+gap)
                if yy+bh>bottom:continue
                self.button(key,xx,yy,cell,bh,lambda k=key:self.calc_press(k),
                            primary=key=='=',selected=key in ('/','*','-','+'),rounding=10)

    @staticmethod
    def _calculate(expression):
        ops={ast.Add:lambda a,b:a+b,ast.Sub:lambda a,b:a-b,
             ast.Mult:lambda a,b:a*b,ast.Div:lambda a,b:a/b,
             ast.Pow:lambda a,b:a**b,ast.Mod:lambda a,b:a%b}
        def walk(node,depth=0):
            if depth>30:raise ValueError('Expresión demasiado larga')
            if isinstance(node,ast.Expression):return walk(node.body,depth+1)
            if isinstance(node,ast.Constant) and type(node.value) in (int,float):
                if abs(node.value)>10**18:raise ValueError('Número demasiado grande')
                return node.value
            if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.UAdd,ast.USub)):
                v=walk(node.operand,depth+1)
                return v if isinstance(node.op,ast.UAdd) else -v
            if isinstance(node,ast.BinOp) and type(node.op) in ops:
                a=walk(node.left,depth+1);b=walk(node.right,depth+1)
                if isinstance(node.op,ast.Pow) and abs(b)>30:
                    raise ValueError('Exponente demasiado grande')
                return ops[type(node.op)](a,b)
            raise ValueError('Operación no permitida')
        r=walk(ast.parse(expression,mode='eval'))
        if not math.isfinite(r) or abs(r)>10**30:raise ValueError('Resultado fuera de rango')
        return ('%g'%r) if isinstance(r,float) else str(r)

    def calc_press(self,key):
        if key=='C':self.calc_expr=''
        elif key=='⌫':self.calc_expr=self.calc_expr[:-1]
        elif key=='=':
            try:self.calc_expr=self._calculate(self.calc_expr)
            except (ArithmeticError,ValueError,SyntaxError,OverflowError) as exc:
                self.notifications='Calculadora: '+str(exc)
        elif len(self.calc_expr)<90:self.calc_expr+=key
        self.paint()

    def _pdf(self,left,right,top,bottom):
        c=self.x;w=right-left
        self._section_heading('PDF a Word','Convertidor de documentos.',left,top,w)
        c.rounded(left,top+67,w,145,15,'#172e47','#365d7e')
        self.text('▤  Conversión PDF → DOCX',left+21,top+112,self.TEXT,'head',w-44)
        self.text('Esta operación necesita pdf2docx u otro convertidor externo.',
                  left+23,top+149,self.MUTED,'body',w-44)
        self.text('No se instala ni descarga ninguna dependencia automáticamente.',
                  left+23,top+177,self.MUTED,'small',w-44)

    def _history(self,left,right,top,bottom):
        self._section_heading('Actividad de sesión','El historial se mantiene solo en RAM.',left,top,right-left)
        y=top+69
        for when,what in self.history[:max(1,(bottom-y)//38)]:
            self.x.rounded(left,y,right-left,32,8,'#172c44','#2e4b68')
            self.text(when,left+13,y+22,self.CYAN,'small')
            self.text(what,left+88,y+22,self.TEXT,'body',right-left-103)
            y+=38

    def _settings(self,left,right,top,bottom):
        self._section_heading('Configuración','Información del motor gráfico nativo.',left,top,right-left)
        blocks=[('MOTOR GRÁFICO','Python + ctypes + libX11','Sin PySide6, Tkinter, FLTK ni pip.'),
                ('TIPOGRAFÍA','Xft opcional para UTF-8','Si no está disponible, utiliza fuente X11 básica.'),
                ('ALMACENAMIENTO','Modo RAM / Sesión','No examina, monta, particiona ni formatea discos.'),
                ('VENTANAS','Bordes redondeados reales','Se utiliza XShape cuando el servidor lo admite.')]
        y=top+68
        for title,value,desc in blocks:
            if y+90>bottom:break
            self.x.rounded(left,y,right-left,87,13,'#162a43','#345778')
            self.text(title,left+18,y+21,'#7fc7e5','small')
            self.text(value,left+18,y+46,'#f4fbff','medium',right-left-38)
            self.text(desc,left+18,y+67,self.MUTED,'small',right-left-38)
            y+=99

    def _statusbar(self):
        c=self.x;h=c.height;w=c.width
        c.rect(0,h-39,w,39,'#101f31')
        c.line(0,h-40,w,h-40,'#315678')
        self.text('◈  PYRION OS    |    X11 NATIVO',19,h-16,'#d4f1ff','small',min(300,w//2))
        right='●  RAM TEMPORAL    |    '+APP_VERSION
        self.text(right,w-c.text_width(right,'small')-16,h-16,self.GREEN,'small',w//2-30)

    def paint(self):
        c=self.x;w,h=c.width,c.height
        self.hits=[]
        c.rounded(0,0,w,h,19,'#07111d')
        c.rect(0,78,w,h-118,self.BG)
        self._header();self._sidebar()
        side=208 if w>=830 else 62
        left=side+23;right=w-22
        self._tabbar(left,right)
        top=153;bottom=h-55
        if self.page=='Inicio':self._home(left,right,top,bottom)
        elif self.page=='Aplicaciones':self._apps(left,right,top,bottom)
        elif self.page=='Consola':self._console(left,right,top,bottom)
        elif self.page=='Archivos':self._files(left,right,top,bottom)
        elif self.page=='Configuración':self._settings(left,right,top,bottom)
        elif self.page=='Calculadora':self._calc(left,right,top,bottom)
        elif self.page=='Editor CSV':self._csv(left,right,top,bottom)
        elif self.page=='PDF a Word':self._pdf(left,right,top,bottom)
        elif self.page=='Historial':self._history(left,right,top,bottom)
        else:self._apps(left,right,top,bottom)
        self._statusbar()
        c.flush_buffer()

    def set_focus(self,field):
        self.focus=field
        self.paint()

    def search(self):
        value=self.query.strip()
        if not value:return
        clean=value.lower()
        self.record('Buscar: '+value)
        keywords=[(('calcul','matem','cuent'), 'Calculadora'),
                  (('csv','excel','tabla'), 'Editor CSV'),
                  (('pdf','word','docx'), 'PDF a Word'),
                  (('archivo','carpeta','explor'), 'Visor de archivos'),
                  (('consola','terminal','comando','shell'), 'PYRION Console')]
        for terms,target in keywords:
            if any(t in clean for t in terms):
                self.query='';self.open_tool(target);return
        self.notifications='No se encontró herramienta: '+value
        self.console_log=['Solicitud: '+value,'No hay herramienta local para esta solicitud.']
        self.query=''
        self.paint()

    def run_console(self):
        cmd=self.console_cmd.strip()
        if not cmd:return
        self.console_log.append('pyrion@os:$ '+cmd)
        self.record('Consola: '+cmd)
        self.console_cmd=''
        try:
            parts=shlex.split(cmd)
        except ValueError as exc:
            self.console_log.append(str(exc));self.paint();return
        if not parts:self.paint();return
        op=parts[0]
        try:
            if op=='help':out='Comandos: help, pwd, ls, cd, echo, whoami, uname, date, clear, python3 --version'
            elif op=='clear':self.console_log=[];out=''
            elif op=='pwd':out=str(self.files_dir)
            elif op=='ls':
                p=Path(parts[1]).expanduser() if len(parts)>1 else self.files_dir
                out='   '.join(a.name for i,a in enumerate(p.iterdir()) if i<40)
            elif op=='cd':
                p=(self.files_dir/(parts[1] if len(parts)>1 else str(Path.home()))).expanduser().resolve()
                if not p.is_dir():raise ValueError('No es un directorio: '+str(p))
                self.files_dir=p;self._refresh_files();out=str(p)
            elif op=='echo':out=' '.join(parts[1:])
            elif op=='whoami':out=os.getenv('USER') or str(os.getuid())
            elif op=='uname':out=os.uname().sysname+' '+os.uname().release
            elif op=='date':out=dt.datetime.now().isoformat(sep=' ',timespec='seconds')
            elif op=='python3' and len(parts)==2 and parts[1]=='--version':out=sys.version.split()[0]
            else:out='Comando no disponible en la consola básica. Use una terminal del sistema.'
        except (OSError,ValueError) as exc:out='Error: '+str(exc)
        for l in out.splitlines()[:40]:self.console_log.append(l[:600])
        self.console_log=self.console_log[-100:]
        self.paint()

    def click(self,x,y):
        for hit in reversed(self.hits):
            if hit.contains(x,y):
                try:hit.action()
                except Exception as exc:
                    self.notifications='Error interno: '+str(exc)
                    self.paint()
                return
        self.focus=None
        self.paint()

    def key(self,evt):
        buf=C.create_string_buffer(128)
        symbol=ulong()
        count=self.x.lookup_string(C.byref(evt),buf,127,C.byref(symbol),None)
        code=int(symbol.value)
        control=bool(evt.state & (1<<2))
        if code==0xff1b:
            if self.focus:self.focus=None
            else:self.page='Inicio'
        elif self.focus in ('search','console'):
            field='query' if self.focus=='search' else 'console_cmd'
            value=getattr(self,field)
            if code in (0xff0d,0xff8d):
                if self.focus=='search':self.search()
                else:self.run_console()
                return
            if code==0xff08:value=value[:-1]
            elif code==0xffff:value=''
            elif control and code in (ord('a'),ord('A')):value=''
            elif count>0 and not control:
                chars=buf.raw[:count].decode('utf-8','replace')
                if chars.isprintable() and len(value)<240:value+=chars
            setattr(self,field,value)
        elif self.page=='Calculadora':
            if code in (0xff0d,0xff8d):self.calc_press('=');return
            if code==0xff08:self.calc_press('⌫');return
            if count and buf.raw[:count].decode('utf-8','ignore') in '0123456789.+-*/()':
                self.calc_press(buf.raw[:count].decode('utf-8','ignore'));return
        elif code in (ord('/'),):self.focus='search'
        self.paint()

    def stop(self):
        self.running=False

    def event_loop(self,smoke_seconds=None):
        import select
        c=self.x
        start=time.monotonic()
        try:
            while self.running:
                if smoke_seconds and time.monotonic()-start>smoke_seconds:break
                if not c.pending(c.dpy):
                    # Se despierta para refrescar el reloj sin alto consumo CPU.
                    try:select.select([c.connection_number(c.dpy)],[],[],0.30)
                    except (OSError,ValueError):time.sleep(.1)
                while c.pending(c.dpy):
                    event=XEvent()
                    c.next_event(c.dpy,C.byref(event))
                    kind=event.type
                    if kind==12:self.paint()  # Expose
                    elif kind==22:
                        if c.resize(event.xconfigure.width,event.xconfigure.height):self.paint()
                    elif kind==33:
                        if event.xclient.data.l[0]==c.delete_atom:self.running=False
                    elif kind==4 and event.xbutton.button==1:
                        self.click(event.xbutton.x,event.xbutton.y)
                    elif kind==4 and event.xbutton.button in (4,5):
                        if self.page=='Archivos':
                            self.file_scroll=max(0,min(max(0,len(self.file_entries)-4),
                                                    self.file_scroll + (-3 if event.xbutton.button==4 else 3)))
                            self.paint()
                    elif kind==6:
                        hover=next((i for i,hit in reversed(list(enumerate(self.hits)))
                                    if hit.contains(event.xmotion.x,event.xmotion.y)),-1)
                        if hover!=self.hover:
                            self.hover=hover;c.pointer(hover>=0)
                    elif kind==2:self.key(event.xkey)
                clock=dt.datetime.now().strftime('%H:%M')
                if clock!=self.last_clock:
                    self.last_clock=clock
                    self.paint()
        finally:
            c.cleanup()
        return 0


def main():
    args=list(sys.argv[1:])
    if '--check' in args:
        print(APP_NAME,APP_VERSION)
        print('Python:',sys.version.split()[0])
        for library in ('X11','Xft','Xext'):
            print(library+':',ctypes.util.find_library(library) or 'no detectada')
        print('DISPLAY:',os.getenv('DISPLAY') or '(sin X11)')
        print('Motor: ctypes + libX11; sin PySide6 ni Tkinter')
        return 0
    smoke=None
    if '--smoke' in args:
        i=args.index('--smoke')
        try:smoke=float(args[i+1])
        except (ValueError,IndexError):smoke=2
    try:
        app=PyrionDesktop()
        return app.event_loop(smoke)
    except (X11Error,OSError) as exc:
        print('PYRION X11: '+str(exc),file=sys.stderr)
        return 1


if __name__=='__main__':
    raise SystemExit(main())
