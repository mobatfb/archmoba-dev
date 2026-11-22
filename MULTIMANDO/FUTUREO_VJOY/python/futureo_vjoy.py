#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FUTUREO VJOY - puente local de Windows al driver experimental.

Escribe en \\.\FUTJOY1 a \\.\FUTJOY8: int16 X, int16 Y y uint16 botones.
NO crea un driver ni cambia los nombres de vJoy existentes.
Necesita compilar, firmar e instalar FutJoy.sys por separado.
"""
from __future__ import annotations
import argparse
import ctypes
import os
import struct
import sys
import time

FILE_DEVICE_UNKNOWN = 0x22
FILE_WRITE_DATA = 2
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 1
FILE_SHARE_WRITE = 2
OPEN_EXISTING = 3

def ctl_code(function: int) -> int:
    return (FILE_DEVICE_UNKNOWN << 16) | (FILE_WRITE_DATA << 14) | (function << 2)

IOCTL_SET_STATE = ctl_code(0x801)
IOCTL_NEUTRAL = ctl_code(0x802)
BUTTONS = {
    "A": 0, "B": 1, "X": 2, "Y": 3, "LB": 4, "RB": 5,
    "START": 6, "SELECT": 7, "B9": 8, "B10": 9, "B11": 10,
    "B12": 11, "B13": 12, "B14": 13, "B15": 14, "B16": 15,
}

def make_report(x: int = 0, y: int = 0, buttons: int = 0) -> bytes:
    if not all(type(v) is int for v in (x, y, buttons)):
        raise TypeError("Ejes y botones deben ser enteros")
    if not (-32768 <= x <= 32767 and -32768 <= y <= 32767):
        raise ValueError("Eje fuera del rango de 16 bits")
    if not (0 <= buttons <= 65535):
        raise ValueError("Mascara de botones invalida")
    return struct.pack("<hhH", x, y, buttons)

class FutJoy:
    def __init__(self, slot: int):
        if type(slot) is not int or not (1 <= slot <= 8):
            raise ValueError("Slot fuera de rango [1..8]")
        if os.name != "nt":
            raise OSError("El driver solo puede abrirse en Windows")
        from ctypes import wintypes
        self.slot = slot
        self.path = rf"\\.\FUTJOY{slot}"
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.CreateFileW.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
            wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
        self.kernel.CreateFileW.restype = ctypes.c_void_p
        self.kernel.DeviceIoControl.argtypes = [
            ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
            ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
            ctypes.c_void_p]
        self.kernel.DeviceIoControl.restype = wintypes.BOOL
        self.kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        self.kernel.CloseHandle.restype = wintypes.BOOL
        self.handle = self.kernel.CreateFileW(
            self.path, GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE,
            None, OPEN_EXISTING, 0, None)
        if self.handle in (0, ctypes.c_void_p(-1).value):
            raise ctypes.WinError(ctypes.get_last_error())

    def _ioctl(self, code: int, payload: bytes) -> None:
        from ctypes import wintypes
        if self.handle is None:
            raise RuntimeError("El dispositivo esta cerrado")
        buf = ctypes.create_string_buffer(payload) if payload else None
        returned = wintypes.DWORD()
        ok = self.kernel.DeviceIoControl(
            self.handle, code, buf, len(payload), None, 0,
            ctypes.byref(returned), None)
        if not ok:
            raise ctypes.WinError(ctypes.get_last_error())

    def state(self, x: int = 0, y: int = 0, buttons: int = 0) -> None:
        self._ioctl(IOCTL_SET_STATE, make_report(x, y, buttons))

    def neutral(self) -> None:
        self._ioctl(IOCTL_NEUTRAL, b"")

    def close(self) -> None:
        if self.handle is not None:
            try:
                self.neutral()
            finally:
                self.kernel.CloseHandle(self.handle)
                self.handle = None

    def __enter__(self) -> "FutJoy":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

def selftest() -> None:
    assert struct.calcsize("<hhH") == 6
    assert make_report() == b"\x00" * 6
    assert make_report(-32768, 32767, 65535) == b"\x00\x80\xff\x7f\xff\xff"
    assert IOCTL_SET_STATE == 0x22A004
    assert IOCTL_NEUTRAL == 0x22A008
    assert len(set(BUTTONS.values())) == 16
    for values in [(-32769, 0, 0), (0, 32768, 0), (0, 0, 65536)]:
        try:
            make_report(*values)
        except ValueError:
            continue
        raise AssertionError("No rechazo datos invalidos")
    print("OK: IOCTL, ejes, botones, reporte")

def demo(slot: int) -> None:
    with FutJoy(slot) as pad:
        print("5 segundos para cambiar a joy.cpl...")
        time.sleep(5)
        for _ in range(3):
            pad.state(x=24000, buttons=1)
            time.sleep(0.3)
            pad.neutral()
            time.sleep(0.3)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--demo", type=int)
    options = parser.parse_args()
    if options.selftest:
        selftest()
    elif options.demo is not None:
        demo(options.demo)
    else:
        parser.print_help()
