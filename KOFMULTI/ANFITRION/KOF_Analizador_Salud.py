# -*- coding: utf-8 -*-
"""KOFMULTI | Analizador de salud y golpes (laboratorio, solo lectura).

Asocia ataques aceptados por KOF_Anfitrion.py con bajadas en la memoria local
de mame.exe. No altera la RAM y NO modifica el marcador ni transmite video.
Windows; Python 64 bits recomendado. Sin librerias externas.
Ejecutar: py -B KOF_Analizador_Salud.py  |  py -B KOF_Analizador_Salud.py --selftest
"""
from __future__ import annotations

import collections
import ctypes
import json
import os
import queue
import re
import socket
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk

ANALYZER_VERSION = "v1.5"
PORT = 38724  # Solo 127.0.0.1; el anfitrion informa ataques, no resultados.
P2_HP_HISTORICAL = 0x13C1AA58  # Solo referencia: NO es estable al reiniciar MAME.
P2_HP_BYTES = 1
NEAR_P2_RADII = {"64 KiB": 0x10000, "256 KiB": 0x40000,
                 "1 MiB": 0x100000, "4 MiB": 0x400000}
HEALTH_POLL_SECONDS = 0.25  # Poco consumo, lectura de un solo Byte.
MAX_SCAN_BYTES = 24 * 1024 * 1024
BLOCK = 64 * 1024
ATTACKS = frozenset(("A", "B", "C", "D"))
PROCESS_VM_READ = 0x10
PROCESS_QUERY_INFORMATION = 0x400
MEM_COMMIT = 0x1000
MEM_PRIVATE = 0x20000
MEM_MAPPED = 0x40000
VK_LMENU = 0xA4  # Alt izquierdo, VK_LMENU (no Alt derecho)
PAGE_READWRITE = 0x04
PAGE_WRITECOPY = 0x08
PAGE_EXECUTE_READWRITE = 0x40
PAGE_EXECUTE_WRITECOPY = 0x80
PAGE_GUARD = 0x100
TH32CS_SNAPPROCESS = 2


class ScoreLearner:
    """Filtra cambios de salud contrastando DAÑO REAL frente a SIN DAÑO.

    Una pulsación aislada no crea candidatos; se requieren al menos dos
    muestras de daño confirmado y una muestra de control (golpe fallido).
    """

    def __init__(self):
        # [bajadas por ataque P1, bajadas por ataque P2, ultimo valor,
        #  cambios SIN daño P2, cambios SIN daño P1]
        self.hits = collections.defaultdict(lambda: [0, 0, 0, 0, 0])
        self.samples = [0, 0]    # acciones con daño confirmado
        self.controls = [0, 0]   # acciones sin daño confirmado
        self.rejected = set()    # descartadas manualmente, solo en memoria
        self.limit = 160000

    def observe(self, before, after, attacker, width=1, confirmed=True):
        if attacker not in (1, 2) or width not in (1, 2, 4):
            return 0
        index = attacker - 1
        if confirmed:
            self.samples[index] += 1
        else:
            self.controls[index] += 1
        relevant = 0
        for start, prior in before.items():
            current = after.get(start)
            if current is None or prior == current:
                continue
            if isinstance(prior, int):
                candidates = ((start, prior, current),)
            elif width == 1:
                candidates = ((start + i, a, b)
                              for i, (a, b) in enumerate(zip(prior, current))
                              if a != b)
            else:
                candidates = (
                    (start + i, int.from_bytes(prior[i:i + width], "little"),
                     int.from_bytes(current[i:i + width], "little"))
                    for i in range(0, min(len(prior), len(current)) - width + 1, width)
                    if prior[i:i + width] != current[i:i + width])
            upper = 255 if width == 1 else (65535 if width == 2 else 10000000)
            max_drop = 160 if width == 1 else (4096 if width == 2 else 400000)
            for address, old, new in candidates:
                if (address in self.rejected or
                        not (0 <= old <= upper and 0 <= new <= upper)):
                    continue
                if confirmed:
                    # En daño confirmado solo interesan valores descendentes.
                    if not (5 <= old and 0 <= new < old and
                            1 <= old - new <= max_drop):
                        continue
                elif old == new:
                    continue
                if address not in self.hits and len(self.hits) >= self.limit:
                    continue
                record = self.hits[address]
                record[2] = new
                if confirmed:
                    record[index] += 1
                else:
                    # Cualquier cambio cuando NO hay daño reduce la validez,
                    # aunque la variable suba en vez de bajar.
                    record[3 + index] += 1
                relevant += 1
        return relevant

    def reject(self, address):
        """Descarta una direccion elegida por el usuario en esta sesion."""
        address = int(address)
        self.rejected.add(address)
        self.hits.pop(address, None)

    def top(self, n=45):
        ranked = []
        for address, (after_p1, after_p2, value, noise_p1, noise_p2) in self.hits.items():
            if address in self.rejected:
                continue
            for victim, matched, other, noise, attack_index in (
                (2, after_p1, after_p2, noise_p1, 0),
                (1, after_p2, after_p1, noise_p2, 1),
            ):
                good_total = self.samples[attack_index]
                bad_total = self.controls[attack_index]
                # Sin al menos una prueba en la que no haya daño, una
                # correlacion con ALT no demuestra nada sobre la salud.
                if matched < 2 or good_total < 2 or bad_total < 1:
                    continue
                good_rate = matched / max(1, good_total)
                bad_rate = noise / max(1, bad_total)
                if bad_rate >= good_rate or noise >= matched:
                    continue
                contrast = good_rate - bad_rate
                consistency = matched / max(1, matched + other + 2 * noise)
                quality = max(0, min(100, round(contrast * consistency * 100)))
                rating = matched * contrast * consistency - other - noise
                ranked.append((rating, victim, address, value,
                               matched, noise + other, quality))
        ranked.sort(reverse=True)
        return ranked[:n]


if os.name == "nt":
    from ctypes import wintypes as wt

    class MemoryRegion(ctypes.Structure):
        _fields_ = [
            ("BaseAddress", ctypes.c_void_p),
            ("AllocationBase", ctypes.c_void_p),
            ("AllocationProtect", wt.DWORD),
            ("PartitionId", wt.WORD),
            ("RegionSize", ctypes.c_size_t),
            ("State", wt.DWORD),
            ("Protect", wt.DWORD),
            ("Type", wt.DWORD),
        ]

    class ProcessEntry(ctypes.Structure):
        _fields_ = [
            ("dwSize", wt.DWORD),
            ("cntUsage", wt.DWORD),
            ("th32ProcessID", wt.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wt.DWORD),
            ("cntThreads", wt.DWORD),
            ("th32ParentProcessID", wt.DWORD),
            ("pcPriClassBase", wt.LONG),
            ("dwFlags", wt.DWORD),
            ("szExeFile", wt.WCHAR * 260),
        ]

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenProcess.argtypes = (wt.DWORD, wt.BOOL, wt.DWORD)
    k32.OpenProcess.restype = wt.HANDLE
    k32.CloseHandle.argtypes = (wt.HANDLE,)
    k32.CloseHandle.restype = wt.BOOL
    k32.ReadProcessMemory.argtypes = (
        wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t))
    k32.ReadProcessMemory.restype = wt.BOOL
    k32.VirtualQueryEx.argtypes = (
        wt.HANDLE, ctypes.c_void_p, ctypes.POINTER(MemoryRegion),
        ctypes.c_size_t)
    k32.VirtualQueryEx.restype = ctypes.c_size_t
    k32.CreateToolhelp32Snapshot.argtypes = (wt.DWORD, wt.DWORD)
    k32.CreateToolhelp32Snapshot.restype = wt.HANDLE
    k32.Process32FirstW.argtypes = (wt.HANDLE, ctypes.POINTER(ProcessEntry))
    k32.Process32NextW.argtypes = (wt.HANDLE, ctypes.POINTER(ProcessEntry))
    k32.Process32FirstW.restype = wt.BOOL
    k32.Process32NextW.restype = wt.BOOL
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
    user32.GetAsyncKeyState.restype = ctypes.c_short
    user32.GetForegroundWindow.restype = wt.HWND
    user32.GetWindowThreadProcessId.argtypes = (
        wt.HWND, ctypes.POINTER(wt.DWORD))
    user32.GetWindowThreadProcessId.restype = wt.DWORD


def find_mame_pid():
    if os.name != "nt":
        return None
    snapshot = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snapshot or snapshot == ctypes.c_void_p(-1).value:
        return None
    try:
        entry = ProcessEntry()
        entry.dwSize = ctypes.sizeof(ProcessEntry)
        good = k32.Process32FirstW(snapshot, ctypes.byref(entry))
        while good:
            if entry.szExeFile.lower() == "mame.exe":
                return int(entry.th32ProcessID)
            good = k32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        k32.CloseHandle(snapshot)
    return None


class ReadOnlyMemory:
    """API Win32 solo con PROCESS_VM_READ/QUERY_INFORMATION."""

    def __init__(self, pid):
        if os.name != "nt":
            raise OSError("La lectura de procesos requiere Windows.")
        self.pid = int(pid)
        self.handle = k32.OpenProcess(
            PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, self.pid)
        if not self.handle:
            raise OSError(
                f"No se pudo abrir mame.exe PID {pid}. "
                "Comprueba los permisos de Windows y usa Python 64 bits.")

    def close(self):
        if self.handle:
            k32.CloseHandle(self.handle)
            self.handle = None

    def read(self, address, size):
        buf = ctypes.create_string_buffer(size)
        read = ctypes.c_size_t(0)
        good = k32.ReadProcessMemory(
            self.handle, ctypes.c_void_p(int(address)), buf,
            size, ctypes.byref(read))
        if not good or read.value != size:
            return None
        return buf.raw[:size]

    def scan_near(self, center, radius):
        """Lee bloques de 4 KiB alrededor del Byte conocido de P2.

        No intenta deducir la direccion de P1 por un offset supuesto; verifica
        primero que cada bloque sea legible. Como máximo 8 MiB.
        """
        radius = int(radius)
        if radius not in NEAR_P2_RADII.values():
            raise ValueError("Radio no permitido para buscar P1.")
        start = max(0x10000, (int(center) - radius) & ~0xFFF)
        end = (int(center) + radius + 0xFFF) & ~0xFFF
        if self.read(center, 1) is None:
            raise ValueError("La direccion de P2 ya no es legible en este MAME.")
        return [(addr, 4096) for addr in range(start, end, 4096)
                if self.read(addr, 4096) is not None]

    def scan_plan(self):
        """Muestrea RAM escribible y mapeada por regiones, no solo la primera."""
        regions = []
        position = 0x10000
        maximum = 0x7FFFFFFF0000 if ctypes.sizeof(ctypes.c_void_p) == 8 else 0x7FFF0000
        count = 0
        while position < maximum and count < 150000:
            info = MemoryRegion()
            result = k32.VirtualQueryEx(
                self.handle, ctypes.c_void_p(position), ctypes.byref(info),
                ctypes.sizeof(info))
            if not result:
                break
            start, size = int(info.BaseAddress or position), int(info.RegionSize)
            position = max(position + 4096, start + size)
            count += 1
            writable = bool(info.Protect & (
                PAGE_READWRITE | PAGE_WRITECOPY |
                PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY))
            if (info.State == MEM_COMMIT and info.Type in (MEM_PRIVATE, MEM_MAPPED)
                    and writable and not info.Protect & PAGE_GUARD
                    and size >= 4096):
                regions.append((start, size, info.Type))

        # Distribuir los 24 MiB entre regiones grandes y sus distintas zonas.
        # Si MAME almacena la RAM emulada en el final de una región, ya no
        # queda fuera de muestra por visitar únicamente los primeros bytes.
        regions.sort(key=lambda rec: (rec[2] == MEM_PRIVATE, rec[1]), reverse=True)
        result = []
        used = 0
        for base, size, _kind in regions:
            if used >= MAX_SCAN_BYTES:
                break
            budget = min(size, 2 * 1024 * 1024, MAX_SCAN_BYTES - used)
            region_used = 0
            sample_size = min(700 * 1024, budget)
            anchors = (0, max(0, size // 2 - sample_size // 2),
                       max(0, size - sample_size))
            seen = set()
            for anchor in anchors:
                if region_used >= budget:
                    break
                for off in range(anchor, min(size, anchor + sample_size), BLOCK):
                    address = base + off
                    if address in seen:
                        continue
                    seen.add(address)
                    n = min(BLOCK, size - off, budget - region_used,
                            MAX_SCAN_BYTES - used)
                    if n <= 0:
                        break
                    if self.read(address, n) is not None:
                        result.append((address, n))
                        used += n
                        region_used += n
                    else:
                        # Unos bytes protegidos no deben hacer descartar 64 KiB.
                        page = 4096
                        for part in range(0, n, page):
                            count_part = min(page, n - part)
                            if self.read(address + part, count_part) is not None:
                                result.append((address + part, count_part))
                                used += count_part
                                region_used += count_part
                                if used >= MAX_SCAN_BYTES or region_used >= budget:
                                    break
                    if used >= MAX_SCAN_BYTES or region_used >= budget:
                        break
        return result

    def snapshot(self, plan):
        data = {}
        for address, size in plan:
            chunk = self.read(address, size)
            if chunk is not None:
                data[address] = chunk
        return data


def parse_addresses(text):
    """Direcciones absolutas de Cheat Engine: 0x1234 o 1234 (hex)."""
    addresses = set()
    for part in re.split(r"[\s,;]+", text):
        token = part.strip().rstrip(":")
        if not token:
            continue
        if token.lower().startswith("dec:"):
            addr = int(token[4:], 10)
        else:
            token = token.removeprefix("0x").removeprefix("0X")
            if not re.fullmatch(r"[0-9a-fA-F]+", token):
                raise ValueError("Utiliza direcciones absolutas en hexadecimal.")
            addr = int(token, 16)
        if not 0x10000 <= addr <= 0x7FFFFFFFFFFF:
            raise ValueError("Dirección fuera de rango: " + hex(addr))
        addresses.add(addr)
    if len(addresses) > 500:
        raise ValueError("Máximo 500 direcciones por sesión.")
    return sorted(addresses)


class Worker:
    """Memoria y telemetría en hilo aparte; jamás bloquea la GUI."""

    def __init__(self, results):
        self.results = results
        self.jobs = queue.Queue()
        self.stop_event = threading.Event()
        self.reader = None
        self.plan = []
        self.mode = "none"
        self.learner = ScoreLearner()
        self.baseline = {}
        self.baseline_at = 0.0
        self.pending = None
        self.manual_before = None
        self.manual_p2_before = None
        self.alt_down = False
        self.alt_count = 0
        self.width = 1
        self.attacks = [0, 0]
        self.p2_hp_last = None
        self.p2_hp_poll_at = 0.0
        self.p2_hp_unreadable = False
        self.p2_address = None  # Obligatorio recalibrar al reiniciar MAME.
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(("127.0.0.1", PORT))
        self.socket.settimeout(0.025)
        self.thread = threading.Thread(target=self.loop, name="KOF-Salud-RAM", daemon=True)
        self.thread.start()

    def emit(self, kind, payload):
        self.results.put((kind, payload))

    def attach(self, pid):
        if self.reader:
            self.reader.close()
            self.reader = None
        self.plan = []
        self.mode = "none"
        self.baseline = {}
        self.pending = None
        self.manual_before = None
        self.manual_p2_before = None
        self.alt_down = False
        self.learner = ScoreLearner()
        self.p2_hp_last = None
        self.p2_hp_poll_at = 0.0
        self.p2_hp_unreadable = False
        self.p2_address = None
        self.reader = ReadOnlyMemory(pid)
        self.emit("p2_address", None)
        self.emit("p2_health", (None, None))
        self.emit("log", f"Conectado en solo lectura a mame.exe PID {pid}.")
        self.emit("log", "P2: dirección dinámica, no se reutiliza tras reiniciar. "
                         "Pega la dirección vigente de Cheat Engine (Byte).")

    def set_p2_address(self, text):
        """Calibrar P2 solo para el PID actual, sin guardar dirección absoluta."""
        if self.reader is None:
            raise ValueError("Primero pulsa BUSCAR MAME.EXE.")
        addresses = parse_addresses(text)
        if len(addresses) != 1:
            raise ValueError("Introduce una sola dirección hexadecimal de P2.")
        address = addresses[0]
        current = self.reader.read(address, 1)
        if current is None:
            raise ValueError(
                f"La dirección 0x{address:08X} no es legible en el MAME actual.")
        self.p2_address = address
        self.p2_hp_last = None
        self.p2_hp_poll_at = 0.0
        self.p2_hp_unreadable = False
        self.emit("p2_address", address)
        self.emit("log", f"P2 calibrado en PID {self.reader.pid}: "
                         f"0x{address:08X} (Byte). Verifica golpes reales "
                         "y golpes fallidos antes de confiar en el valor.")
        self.poll_p2_health(force=True)

    def poll_p2_health(self, force=False):
        """Lectura de UN Byte calibrado en la sesión actual; no puntúa."""
        if not self.reader or self.p2_address is None:
            return
        now = time.monotonic()
        if not force and now - self.p2_hp_poll_at < HEALTH_POLL_SECONDS:
            return
        self.p2_hp_poll_at = now
        current = self.reader.read(self.p2_address, P2_HP_BYTES)
        if current is None:
            if not self.p2_hp_unreadable:
                self.p2_hp_unreadable = True
                self.p2_hp_last = None
                self.emit("p2_health", (None, None))
                self.emit("log", "P2: el Byte elegido dejó de ser legible; "
                                 "revisa el PID y la dirección de esta sesión.")
            return
        value = current[0]
        delta = None if self.p2_hp_last is None else value - self.p2_hp_last
        if self.p2_hp_unreadable or self.p2_hp_last != value:
            self.emit("p2_health", (value, delta))
        self.p2_hp_unreadable = False
        self.p2_hp_last = value

    def configure(self, mode, text="", width=1):
        if not self.reader:
            raise ValueError("Primero conecta con mame.exe.")
        self.plan = []
        self.learner = ScoreLearner()
        self.baseline = {}
        self.pending = None
        self.manual_before = None
        self.manual_p2_before = None
        self.width = width
        if mode == "near_p2":
            radius = NEAR_P2_RADII.get(text)
            if self.p2_address is None:
                raise ValueError("Primero ingresa la dirección de P2 VIGENTE en esta sesión.")
            if radius is None or width != 1:
                raise ValueError("Selecciona un radio valido y tipo Byte.")
            self.plan = self.reader.scan_near(self.p2_address, radius)
            if not self.plan:
                raise ValueError("No hay memoria legible cerca de P2.")
            self.mode = "near_p2"
            # La barra de P2 es una referencia, no candidata a P1.
            self.learner.reject(self.p2_address)
            sampled = sum(n for _, n in self.plan)
            self.emit("log", f"Buscando P1 alrededor de P2: +/-{text}, "
                             f"{sampled / 1024:.0f} KiB legibles.")
            self.emit("log", "Da 2 golpes reales a P1 y un golpe fallido; "
                             "marca P1 RECIBIO DANO o P1 SIN DANO.")
        elif mode == "ce":
            addresses = parse_addresses(text)
            if not addresses:
                raise ValueError("Pega al menos una dirección de Cheat Engine.")
            self.plan = [(address, width) for address in addresses]
            self.mode = "ce"
            self.emit("log", f"Seguimiento de {len(addresses)} direcciones CE ({width} byte(s)).")
        else:
            self.plan = self.reader.scan_plan()
            if not self.plan:
                raise ValueError("No se encontraron regiones legibles para explorar.")
            self.mode = "auto"
            size = sum(length for _, length in self.plan)
            self.emit("log", f"Explorando {size / (1024 * 1024):.1f} MiB de RAM ({width} Byte).")
        self.baseline = self.reader.snapshot(self.plan)
        if not self.baseline:
            raise ValueError(
                "No se pudo leer RAM; revisa permisos y prueba direcciones de Cheat Engine.")
        self.baseline_at = time.monotonic()
        self.emit("samples", ((0, 0), (0, 0)))
        self.emit("rank", [])
        available = sum(len(block) for block in self.baseline.values())
        self.emit("log",
                  f"Memoria preparada: {len(self.baseline)} bloques, "
                  f"{available / 1048576:.1f} MiB leídos. ALT IZQUIERDO = golpe P1.")
        self.emit("snapshot", (self.mode, len(self.plan)))

    def _register_attack(self, slot, source):
        """Cuenta pulsaciones, pero NO asume que causaron daño."""
        self.attacks[slot - 1] += 1
        self.emit("attack", tuple(self.attacks))
        if not self.plan:
            self.emit("log",
                      f"{source}: tecla detectada. Primero explora RAM.")
        elif self.manual_before is None:
            self.emit("log",
                      f"{source}: no se suma evidencia sin CAPTURAR ANTES "
                      "y confirmar si el rival recibio daño.")
        else:
            self.emit("log",
                      f"{source}: pulsa ahora P2 CON DAÑO o P2 SIN DAÑO "
                      "segun lo que ocurrio realmente.")

    def _mame_has_focus(self):
        """Solo contabilizar ALT si el proceso activo es MAME, no otro programa."""
        if not self.reader or os.name != "nt":
            return False
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return False
        pid = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value == self.reader.pid

    def poll_left_alt(self):
        """Detección global de ALT IZQUIERDO, también con MAME en primer plano.

        GetAsyncKeyState lee el estado del teclado, no captura ni bloquea teclas.
        """
        if os.name != "nt" or not self.reader:
            return
        try:
            active = self._mame_has_focus()
            pressed = bool(user32.GetAsyncKeyState(VK_LMENU) & 0x8000)
        except OSError:
            return
        down = active and pressed
        if down and not self.alt_down:
            self.alt_count += 1
            self.last_alt_at = time.monotonic()
            self.emit("alt", self.alt_count)
            self._register_attack(1, "ALT IZQUIERDO (P1)")
        self.alt_down = down

    def capture_manual_before(self):
        if not self.reader or not self.plan:
            raise ValueError(
                "Primero BUSCAR MAME y EXPLORAR RAM (o direcciones CE).")
        self.manual_before = self.reader.snapshot(self.plan)
        self.manual_p2_before = (self.reader.read(self.p2_address, P2_HP_BYTES)
                                 if self.p2_address is not None else None)
        if self.mode == "near_p2" and self.manual_p2_before is None:
            self.manual_before = None
            raise ValueError("La vida de P2 no se pudo leer. Verifica MAME y el PID.")
        if not self.manual_before:
            raise ValueError("No se pudo leer memoria; revisa direcciones o permisos.")
        self.emit("log",
                  "CAPTURA ANTES lista: en MAME observa quien recibe el daño "
                  "y vuelve a confirmar DAÑO o SIN DAÑO de ese jugador.")

    def confirm_manual_damage(self, victim, damaged=True):
        if victim not in (1, 2) or not self.reader:
            raise ValueError("El jugador debe ser P1 o P2, con MAME abierto.")
        if self.manual_before is None:
            raise ValueError("Primero pulsa CAPTURAR ANTES.")
        if self.mode == "near_p2" and victim != 1:
            raise ValueError("Busqueda P1: usa P1 RECIBIO DANO o P1 SIN DANO.")
        old = self.manual_before
        old_p2 = self.manual_p2_before
        self.manual_before = None
        self.manual_p2_before = None
        current = self.reader.snapshot(self.plan)
        if self.mode == "near_p2":
            current_p2 = self.reader.read(self.p2_address, P2_HP_BYTES)
            if old_p2 is None or current_p2 is None:
                raise ValueError("No se pudo verificar la barra de P2. "
                                 "Repite la captura en esta sesion.")
            if current_p2 != old_p2:
                self.emit("log",
                          "Muestra DESCARTADA: P2 tambien cambio de salud. "
                          "Para identificar P1, deja a P2 sin recibir daño.")
                return
        if not current:
            raise ValueError("MAME no permitio leer la memoria despues.")
        attacker = 3 - victim
        changed = self.learner.observe(
            old, current, attacker, self.width, confirmed=damaged)
        self.baseline = current
        self.baseline_at = time.monotonic()
        self.emit("rank", self.learner.top())
        self.emit("samples", (tuple(self.learner.samples),
                              tuple(self.learner.controls)))
        if damaged:
            self.emit("log",
                      f"DAÑO REAL confirmado en P{victim}: {changed} descensos "
                      "de memoria (aun sin verificar).")
        else:
            self.emit("log",
                      f"SIN DAÑO confirmado en P{victim}: {changed} valores "
                      "cambiaron sin tocar la salud; se penalizan.")
        matches = self.learner.top()
        if not matches:
            self.emit("log",
                      "Sin candidatos contrastados: realiza al menos "
                      "2 capturas CON DAÑO y 1 captura SIN DAÑO; si persiste "
                      "prueba otras zonas de RAM o direcciones Cheat Engine.")

    def reject_candidate(self, address):
        self.learner.reject(address)
        self.emit("rank", self.learner.top())
        self.emit("log", f"Descartada dirección 0x{address:X} para esta sesión.")

    def event_attack(self, packet):
        """Mantiene soporte para botones remotos sin duplicar ALT local."""
        if packet.get("type") != "attack":
            return
        slot = packet.get("slot")
        if slot not in (1, 2) or packet.get("action") not in ATTACKS:
            return
        pid = packet.get("pid")
        if type(pid) is not int or pid <= 0:
            return
        if not self.reader:
            try:
                self.attach(pid)
            except OSError as exc:
                self.emit("log", str(exc))
                return
        elif self.reader.pid != pid:
            try:
                self.attach(pid)
                self.emit("log", "MAME cambió de PID: prepara nuevamente la memoria.")
            except OSError as exc:
                self.emit("log", str(exc))
            return
        if slot == 1 and time.monotonic() - getattr(self, "last_alt_at", -100) < 0.8:
            # ALT local y evento del control pueden referirse al mismo golpe.
            return
        self._register_attack(slot, f"Input remoto P{slot}")

    def capture(self):
        """En el modo guiado no analizamos RAM continuamente.

        Esto evita resultados falsos por animaciones y reduce la CPU de MAME.
        """
        return

    def loop(self):
        while not self.stop_event.is_set():
            try:
                wire, _ = self.socket.recvfrom(1024)
                packet = json.loads(wire.decode("utf-8"))
                if isinstance(packet, dict):
                    self.event_attack(packet)
            except socket.timeout:
                pass
            except (ValueError, UnicodeError):
                pass
            except OSError as exc:
                self.emit("log", str(exc))
                break
            # ALT se consulta incluso si el juego tiene el foco y no hay
            # ningún control remoto conectado.
            self.poll_left_alt()
            for _ in range(8):
                try:
                    job = self.jobs.get_nowait()
                except queue.Empty:
                    break
                try:
                    command, *args = job
                    if command == "attach":
                        pid = find_mame_pid()
                        if not pid:
                            raise ValueError("mame.exe no está abierto.")
                        self.attach(pid)
                    elif command == "learn":
                        self.configure(*args)
                    elif command == "p2_address":
                        self.set_p2_address(args[0])
                    elif command == "before":
                        self.capture_manual_before()
                    elif command == "manual_damage":
                        self.confirm_manual_damage(args[0], True)
                    elif command == "manual_no_damage":
                        self.confirm_manual_damage(args[0], False)
                    elif command == "reject":
                        self.reject_candidate(args[0])
                    elif command == "reset":
                        self.pending = None
                        self.manual_before = None
                        self.learner = ScoreLearner()
                        self.emit("rank", [])
                        self.emit("samples", ((0, 0), (0, 0)))
                        self.emit("log", "Aprendizaje reiniciado. Alterna DAÑO y SIN DAÑO.")
                except (OSError, ValueError) as exc:
                    self.emit("log", "ERROR: " + str(exc))
            # La busqueda extensa solo se compara cuando el operador confirma
            # daño. La direccion ya identificada de P2 lee 1 Byte cada 250 ms.
            self.poll_p2_health()
        if self.reader:
            self.reader.close()
        self.socket.close()


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"KOFMULTI | Salud ALT IZQUIERDO {ANALYZER_VERSION}")
        self.root.geometry("1020x680")
        self.root.minsize(720, 450)
        self.root.configure(bg="#0b1323")
        theme = ttk.Style()
        theme.theme_use("clam")
        theme.configure("TFrame", background="#0b1323")
        theme.configure("TLabel", background="#0b1323", foreground="#eaf0ff",
                        font=("Segoe UI", 10))
        theme.configure("TButton", font=("Segoe UI", 9), padding=5)
        theme.configure("Treeview", background="#142940", foreground="#eaf0ff",
                        fieldbackground="#142940", rowheight=24)
        theme.configure("Treeview.Heading", background="#20466a",
                        foreground="#ffffff")
        self.messages = queue.Queue()
        self.worker = Worker(self.messages)
        self.counter = tk.StringVar(value="P1: 0 ataques | P2: 0 ataques")
        self.state = tk.StringVar(
            value="Paso 1: BUSCAR MAME.EXE; Paso 2: EXPLORAR RAM; Paso 3: ALT IZQUIERDO dentro del juego.")
        self.alt_status = tk.StringVar(value="ALT IZQUIERDO (P1): 0 pulsaciones detectadas")
        self.sample_status = tk.StringVar(
            value="Muestras confirmadas: P2 daño 0 / sin daño 0 | P1 daño 0 / sin daño 0")
        self.p2_health_status = tk.StringVar(
            value="VIDA P2 | Byte | sin dirección en esta sesión")
        self.p2_address_var = tk.StringVar(value="")
        self.current_p2_address = None
        self.p1_hint = tk.StringVar(value="P1: aún no se ha identificado.")
        self.near_radius_var = tk.StringVar(value="256 KiB")
        self.value_width = tk.IntVar(value=1)

        body = ttk.Frame(self.root)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        ttk.Label(body, text="APRENDIZAJE DE SALUD — MAME (SOLO LECTURA)",
                  font=("Segoe UI", 15, "bold")).pack(anchor="w", pady=(0, 5))
        ttk.Label(
            body,
            text="ALT izquierdo detecta pulsación P1; confirma si P2 RECIBIÓ o NO RECIBIÓ daño. "
                 "Sin controles negativos no hay resultados confiables."
        ).pack(anchor="w")
        ttk.Label(body, textvariable=self.alt_status).pack(anchor="w", pady=(3, 0))
        ttk.Label(body, textvariable=self.sample_status).pack(anchor="w", pady=(2, 0))
        ttk.Label(body, textvariable=self.p2_health_status,
                  font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(5, 1))
        ttk.Label(body, textvariable=self.p1_hint).pack(anchor="w", pady=(0, 3))
        calibration = ttk.Frame(body)
        calibration.pack(fill="x", pady=(1, 5))
        ttk.Label(calibration, text="Dirección actual de P2 (hex, Byte):").pack(
            side="left", padx=(0, 6))
        self.p2_entry = ttk.Entry(calibration, textvariable=self.p2_address_var,
                                  width=18)
        self.p2_entry.pack(side="left", padx=(0, 7))
        self.p2_entry.bind("<Return>", lambda _event: self.calibrate_p2())
        ttk.Button(calibration, text="CALIBRAR P2",
                   command=self.calibrate_p2).pack(side="left")
        ttk.Label(calibration, text="Se borra al cambiar de MAME.",
                  style="TLabel").pack(side="right")
        actions = ttk.Frame(body)
        actions.pack(fill="x", pady=(9, 6))
        ttk.Button(actions, text="1. BUSCAR MAME.EXE",
                   command=lambda: self.worker.jobs.put(("attach",))).pack(
                       side="left", padx=(0, 6))
        ttk.Button(actions, text="2. EXPLORAR RAM (24 MiB)",
                   command=lambda: self.worker.jobs.put(("learn", "auto", "", int(self.value_width.get())))).pack(
                       side="left", padx=(0, 6))
        ttk.Button(actions, text="REINICIAR APRENDIZAJE",
                   command=lambda: self.worker.jobs.put(("reset",))).pack(side="right")

        near_controls = ttk.Frame(body)
        near_controls.pack(fill="x", pady=(0, 8))
        ttk.Label(near_controls,
                  text="Buscar P1 en RAM cercana a P2 | Radio:").pack(
                      side="left", padx=(0, 8))
        ttk.Combobox(near_controls, state="readonly", width=12,
                     textvariable=self.near_radius_var,
                     values=tuple(NEAR_P2_RADII.keys())).pack(
                         side="left", padx=(0, 8))
        ttk.Button(near_controls, text="BUSCAR SALUD P1 CERCA DE P2",
                   command=self.search_p1_near).pack(side="left")

        ttk.Label(body, text="Opcional: pega direcciones ABSOLUTAS de Cheat Engine "
                            "(hexadecimal, una por línea):").pack(anchor="w")
        self.ce = tk.Text(body, height=3, bg="#142940", fg="#eaf0ff",
                          relief="flat", font=("Consolas", 10),
                          insertbackground="white")
        self.ce.pack(fill="x", pady=(4, 4))
        ce_controls = ttk.Frame(body)
        ce_controls.pack(fill="x", pady=(0, 6))
        ttk.Radiobutton(ce_controls, text="Byte", value=1,
                        variable=self.value_width).pack(side="left")
        ttk.Radiobutton(ce_controls, text="2 Bytes", value=2,
                        variable=self.value_width).pack(side="left", padx=(8, 0))
        ttk.Radiobutton(ce_controls, text="4 Bytes (CE)", value=4,
                        variable=self.value_width).pack(side="left", padx=(8, 0))
        ttk.Button(ce_controls, text="SEGUIR DIRECCIONES CE",
                   command=self.load_ce).pack(side="left", padx=(14, 0))
        ttk.Label(ce_controls, textvariable=self.counter).pack(side="right")

        guided = ttk.Frame(body)
        guided.pack(fill="x", pady=(0, 7))
        ttk.Button(
            guided, text="3. CAPTURAR ANTES",
            command=lambda: self.worker.jobs.put(("before",))
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            guided, text="4. P2 RECIBIÓ DAÑO",
            command=lambda: self.worker.jobs.put(("manual_damage", 2))
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            guided, text="4. P2 SIN DAÑO",
            command=lambda: self.worker.jobs.put(("manual_no_damage", 2))
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            guided, text="Descartar seleccionado",
            command=self.reject_selected
        ).pack(side="right")
        guided_p1 = ttk.Frame(body)
        guided_p1.pack(fill="x", pady=(0, 6))
        ttk.Button(
            guided_p1, text="P1 RECIBIÓ DAÑO",
            command=lambda: self.worker.jobs.put(("manual_damage", 1))
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            guided_p1, text="P1 SIN DAÑO",
            command=lambda: self.worker.jobs.put(("manual_no_damage", 1))
        ).pack(side="left")

        ttk.Label(body, textvariable=self.state).pack(fill="x", pady=(0, 6))
        holder = ttk.Frame(body)
        holder.pack(fill="both", expand=True)
        cols = ("health", "address", "offset", "value", "evidence", "opposite", "confidence")
        self.table = ttk.Treeview(holder, columns=cols, show="headings")
        for name, title, width in (
            ("health", "Posible barra", 115),
            ("address", "Dirección RAM", 148),
            ("offset", "Offset desde P2", 128),
            ("value", "Valor actual", 90),
            ("evidence", "Daño confirmado", 145),
            ("opposite", "Ruido / sin daño", 165),
            ("confidence", "Calidad orientativa", 130),
        ):
            self.table.heading(name, text=title)
            self.table.column(name, width=width, minwidth=60, stretch=True,
                              anchor="center")
        self.table.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(holder, orient="vertical", command=self.table.yview)
        scrollbar.pack(side="right", fill="y")
        self.table.configure(yscrollcommand=scrollbar.set)

        self.log = tk.Text(body, height=5, bg="#091725", fg="#8cebc3",
                           relief="flat", font=("Consolas", 9), state="disabled")
        self.log.pack(fill="x", pady=(8, 0))
        self._line("Paso 1: CAPTURAR ANTES; paso 2: golpear con ALT y mirar la barra.")
        self._line("Paso 3: marcar P2 RECIBIÓ DAÑO o P2 SIN DAÑO según lo observado.")
        self._line("Repite con una nueva CAPTURAR ANTES en cada prueba. Mínimo 2 daños y 1 fallo.")
        self._line("P2 cambia de dirección al reiniciar. Calibra con la dirección actual de CE.")
        self._line("Descarta falsas direcciones seleccionándolas. NO se modifica MAME.")
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(130, self.poll)

    def _line(self, msg):
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n")
        # Conservar solo 80 lineas en memoria.
        if int(self.log.index("end-1c").split(".")[0]) > 80:
            self.log.delete("1.0", "2.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    def load_ce(self):
        self.worker.jobs.put((
            "learn", "ce", self.ce.get("1.0", "end"), int(self.value_width.get())))

    def calibrate_p2(self):
        value = self.p2_address_var.get().strip()
        if not value:
            self._line("P2: introduce la dirección ACTUAL de Cheat Engine.")
            self.p2_entry.focus_set()
            return
        self.worker.jobs.put(("p2_address", value))

    def search_p1_near(self):
        if self.current_p2_address is None:
            self._line("Primero calibra P2 con una dirección válida de esta sesión.")
            return
        self.value_width.set(1)  # Tipo Byte, igual que P2.
        radius = self.near_radius_var.get()
        self.p1_hint.set(f"P1: buscando alrededor de P2 (+/- {radius}).")
        self.worker.jobs.put(("learn", "near_p2", radius, 1))

    def reject_selected(self):
        selected = self.table.selection()
        if not selected:
            self._line("Selecciona primero la dirección que comprobaste que NO es salud.")
            return
        values = self.table.item(selected[0], "values")
        try:
            address = int(values[1], 16)
        except (ValueError, TypeError, IndexError):
            self._line("No se pudo leer la dirección seleccionada.")
            return
        self.worker.jobs.put(("reject", address))

    def poll(self):
        for _ in range(80):
            try:
                kind, val = self.messages.get_nowait()
            except queue.Empty:
                break
            if kind == "log":
                self._line(str(val))
                self.state.set(str(val))
            elif kind == "attack":
                self.counter.set(
                    f"P1: {val[0]} ataques | P2: {val[1]} ataques")
            elif kind == "alt":
                self.alt_status.set(
                    f"ALT IZQUIERDO (P1): {val} pulsaciones detectadas")
            elif kind == "samples":
                good, bad = val
                self.sample_status.set(
                    f"Muestras: P2 daño {good[0]} / sin daño {bad[0]}"
                    f" | P1 daño {good[1]} / sin daño {bad[1]}")
            elif kind == "p2_address":
                self.current_p2_address = val
                if val is None:
                    self.p2_address_var.set("")
                    self.p2_health_status.set(
                        "VIDA P2 | Byte | dirección pendiente para el MAME actual")
                    self.p1_hint.set("P1: pendiente. Primero calibra P2.")
                else:
                    self.p2_address_var.set(f"0x{val:08X}")
                    self.p2_health_status.set(
                        f"VIDA P2 | 0x{val:08X} | Byte | verificando...")
            elif kind == "p2_health":
                value, delta = val
                address = self.current_p2_address
                if address is None:
                    continue
                suffix = (
                    "sin lectura (revisar PID y dirección)" if value is None else
                    f"valor {value} (Byte)" if delta is None else
                    f"valor {value} (Byte) | cambio {delta:+d}"
                )
                self.p2_health_status.set(
                    f"VIDA P2 | 0x{address:08X} | Byte | {suffix}")
            elif kind == "rank":
                selected = self.table.selection()
                selection_value = (
                    self.table.item(selected[0], "values")[1] if selected else None)
                for row in self.table.get_children():
                    self.table.delete(row)
                for _, health, address, value, matched, contrary, conf in val:
                    if self.current_p2_address is None:
                        offset = "desconocido"
                    else:
                        delta = address - self.current_p2_address
                        offset = f"{'+' if delta >= 0 else '-'}0x{abs(delta):X}"
                    row = self.table.insert("", "end", values=(
                        f"Salud P{health}", f"0x{address:08X}", offset,
                        value, matched, contrary, f"{conf}/100 (orientativo)"))
                    if f"0x{address:08X}" == selection_value:
                        self.table.selection_set(row)
            elif kind == "snapshot":
                self._line("RAM lista. CAPTURAR ANTES > ALT en MAME > confirmar DAÑO o SIN DAÑO.")
        if not self.worker.stop_event.is_set():
            self.root.after(130, self.poll)

    def close(self):
        self.worker.stop_event.set()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def selftest():
    # No aceptar correlaciones sin ejemplos negativos.
    learner = ScoreLearner()
    health_p2, animation, health_p1 = 0x10000, 0x11000, 0x20000
    for n in range(5):
        old = {health_p2: 120 - 5 * n, animation: 120 - 5 * n,
               health_p1: 125}
        new = {health_p2: 115 - 5 * n, animation: 115 - 5 * n,
               health_p1: 125}
        learner.observe(old, new, 1, confirmed=True)
    for n in range(5):
        learner.observe({health_p2: 95, animation: 95,
                         health_p1: 125 - 5 * n},
                        {health_p2: 95, animation: 95,
                         health_p1: 120 - 5 * n}, 2, confirmed=True)
    assert learner.top() == [], "No mostrar candidatos sin golpes fallidos"

    # Animacion sigue cambiando cuando P2 no recibe daño.
    learner.observe({health_p2: 95, animation: 95, health_p1: 100},
                    {health_p2: 95, animation: 94, health_p1: 100},
                    1, confirmed=False)
    learner.observe({health_p2: 95, animation: 94, health_p1: 100},
                    {health_p2: 95, animation: 94, health_p1: 100},
                    2, confirmed=False)
    ranked = learner.top(10)
    assert any(row[1] == 2 and row[2] == health_p2 for row in ranked)
    assert any(row[1] == 1 and row[2] == health_p1 for row in ranked)
    assert all(row[2] != animation for row in ranked), "No mostrar falso positivo"
    learner.reject(health_p2)
    assert all(row[2] != health_p2 for row in learner.top())

    # Lecturas multibyte de direcciones CE requieren también control sin daño.
    assert P2_HP_HISTORICAL == 0x13C1AA58 and P2_HP_BYTES == 1
    assert NEAR_P2_RADII["256 KiB"] == 0x40000
    assert parse_addresses("13C1AA58") == [P2_HP_HISTORICAL]
    assert parse_addresses("00123000\n0x00124000") == [0x123000, 0x124000]
    for width, value, delta in ((2, 1200, 20), (4, 150000, 100)):
        model = ScoreLearner()
        address = 0x40000
        for n in range(3):
            model.observe(
                {address: (value - n * delta).to_bytes(width, "little")},
                {address: (value - (n + 1) * delta).to_bytes(width, "little")},
                1, width=width, confirmed=True)
        assert model.top() == []
        same = (value - 3 * delta).to_bytes(width, "little")
        model.observe({address: same}, {address: same}, 1,
                      width=width, confirmed=False)
        assert any(row[1] == 2 and row[2] == address for row in model.top())

    print("OK: daño/no daño, rechazo de falso positivo y lectura 1/2/4 bytes.")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    elif os.name != "nt":
        print("Esta herramienta requiere Windows para leer mame.exe.")
    else:
        try:
            App().run()
        except OSError as exc:
            import tkinter.messagebox as messagebox
            messagebox.showerror("KOFMULTI", str(exc))
