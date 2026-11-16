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

PORT = 38724  # Solo 127.0.0.1; el anfitrion informa ataques, no resultados.
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
    """Aprendizaje por correlacion, NO detector confirmado de impacto."""

    def __init__(self):
        self.hits = collections.defaultdict(lambda: [0, 0, 0])
        self.samples = [0, 0]
        self.last_value = {}
        self.limit = 160000

    def observe(self, before, after, attacker, width=1):
        if attacker not in (1, 2):
            return 0
        # Atacante P1 => buscar salud de P2, y viceversa.
        self.samples[attacker - 1] += 1
        positives = 0
        for start, prior in before.items():
            current = after.get(start)
            if current is None:
                continue
            if isinstance(prior, int):
                candidates = [(start, prior, current)]
            elif prior == current:
                continue
            elif width == 1:
                candidates = ((start + i, a, b)
                              for i, (a, b) in enumerate(zip(prior, current))
                              if a != b)
            else:
                candidates = ((start + i, int.from_bytes(prior[i:i+width], "little"),
                               int.from_bytes(current[i:i+width], "little"))
                              for i in range(0, min(len(prior), len(current)) - width + 1, width)
                              if prior[i:i+width] != current[i:i+width])
            for address, old, new in candidates:
                # Los medidores de salud son normalmente valores positivos
                # que disminuyen; excluir cambios enormes y punteros.
                upper = 255 if width == 1 else (65535 if width == 2 else 10000000)
                max_drop = 160 if width == 1 else (4096 if width == 2 else 400000)
                if not (5 <= old <= upper and 0 <= new < old
                        and 1 <= old - new <= max_drop):
                    continue
                if address not in self.hits and len(self.hits) >= self.limit:
                    continue
                record = self.hits[address]
                record[attacker - 1] += 1
                record[2] = new
                self.last_value[address] = new
                positives += 1
        return positives

    def top(self, n=45):
        results = []
        for address, (after_p1, after_p2, value) in self.hits.items():
            # Una ubicacion de salud debe variar tras el atacante opuesto
            # con mucha mayor frecuencia que tras el propio jugador.
            for victim, matched, contrary, total in (
                (2, after_p1, after_p2, self.samples[0]),
                (1, after_p2, after_p1, self.samples[1]),
            ):
                if matched == 0:
                    continue
                precision = matched / max(1, matched + contrary)
                frequency = matched / max(1, total)
                confidence = precision * frequency
                rating = matched * precision - contrary * 0.6
                results.append((rating, victim, address, value,
                                matched, contrary, round(confidence * 100)))
        results.sort(reverse=True)
        return results[:n]


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
        self.alt_down = False
        self.alt_count = 0
        self.width = 1
        self.attacks = [0, 0]
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
        self.alt_down = False
        self.learner = ScoreLearner()
        self.reader = ReadOnlyMemory(pid)
        self.emit("log", f"Conectado en solo lectura a mame.exe PID {pid}.")

    def configure(self, mode, text="", width=1):
        if not self.reader:
            raise ValueError("Primero conecta con mame.exe.")
        self.plan = []
        self.learner = ScoreLearner()
        self.baseline = {}
        self.pending = None
        self.manual_before = None
        self.width = width
        if mode == "ce":
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
        available = sum(len(block) for block in self.baseline.values())
        self.emit("log",
                  f"Memoria preparada: {len(self.baseline)} bloques, "
                  f"{available / 1048576:.1f} MiB leídos. ALT IZQUIERDO = golpe P1.")
        self.emit("snapshot", (self.mode, len(self.plan)))

    def _register_attack(self, slot, source):
        """Inicia comparación en RAM; pulsación no equivale a impacto."""
        self.attacks[slot - 1] += 1
        self.emit("attack", tuple(self.attacks))
        if not self.plan:
            self.emit("log",
                      f"{source}: pulsación detectada, pero falta preparar RAM. "
                      "Pulsa EXPLORAR RAM o SEGUIR DIRECCIONES CE.")
            return
        if self.pending is not None:
            # Conservar la muestra previa: el segundo botón no la cancela.
            return
        now = time.monotonic()
        before = (self.manual_before if self.manual_before is not None
                  else self.baseline)
        if not before:
            self.emit("log", "No hay referencia de RAM: pulsa CAPTURAR ANTES.")
            return
        if self.manual_before is None and now - self.baseline_at > 2.0:
            self.emit("log",
                      "Referencia muy antigua; usa CAPTURAR ANTES y vuelve a golpear.")
            return
        self.pending = (slot, now, before)
        self.manual_before = None
        self.emit("log", f"{source}: comparando salud P{3 - slot} después del golpe...")

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
            raise ValueError("Primero BUSCAR MAME y EXPLORAR RAM (o direcciones CE).")
        self.pending = None
        self.manual_before = self.reader.snapshot(self.plan)
        if not self.manual_before:
            raise ValueError("No se pudo leer ninguna región; revisa direcciones o permisos.")
        self.emit("log", "Memoria ANTES capturada. Haz un golpe real "
                         "con ALT IZQUIERDO, o pulsa P2 RECIBIÓ DAÑO después del golpe.")

    def confirm_manual_damage(self, victim):
        if victim not in (1, 2) or not self.reader:
            return
        if self.manual_before is None:
            raise ValueError("Primero pulsa CAPTURAR ANTES para crear referencia.")
        old = self.manual_before
        self.manual_before = None
        self.pending = None
        now = time.monotonic()
        current = self.reader.snapshot(self.plan)
        if not current:
            raise ValueError("MAME no permitió leer la RAM posterior.")
        attacker = 3 - victim
        result = self.learner.observe(old, current, attacker, self.width)
        self.baseline, self.baseline_at = current, now
        self.emit("rank", self.learner.top())
        self.emit("log", f"P{victim} RECIBIÓ DAÑO: {result} valores descendentes "
                         "candidatos. Repite el mismo procedimiento varias veces."
                         if result else
                         f"P{victim}: 0 valores compatibles; intenta 2 Bytes o CE.")

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
        if not self.reader or not self.plan:
            return
        now = time.monotonic()
        if self.pending:
            slot, stamp, old = self.pending
            if now - stamp >= 0.65:
                after = self.reader.snapshot(self.plan)
                count = self.learner.observe(old, after, slot, self.width)
                self.baseline, self.baseline_at = after, time.monotonic()
                self.pending = None
                self.emit("rank", self.learner.top())
                if count:
                    self.emit("log",
                              f"P{slot} atacó: {count} descensos posibles en "
                              f"salud P{3-slot}. Comprueba los candidatos en CE.")
                else:
                    self.emit("log",
                              "0 candidatos en memoria explorada: prueba "
                              "CAPTURAR ANTES / P2 RECIBIÓ DAÑO, "
                              "2 Bytes o direcciones CE.")
        elif now - self.baseline_at >= 0.75:
            self.baseline = self.reader.snapshot(self.plan)
            self.baseline_at = time.monotonic()

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
                    elif command == "before":
                        self.capture_manual_before()
                    elif command == "manual_damage":
                        self.confirm_manual_damage(args[0])
                    elif command == "reset":
                        self.pending = None
                        self.manual_before = None
                        self.learner = ScoreLearner()
                        self.emit("rank", [])
                except (OSError, ValueError) as exc:
                    self.emit("log", "ERROR: " + str(exc))
            try:
                self.capture()
            except (OSError, ValueError) as exc:
                self.emit("log", "Lectura RAM: " + str(exc))
        if self.reader:
            self.reader.close()
        self.socket.close()


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("KOFMULTI | Entrenador de memoria P1 / P2")
        self.root.geometry("1020x620")
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
        self.value_width = tk.IntVar(value=1)

        body = ttk.Frame(self.root)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        ttk.Label(body, text="APRENDIZAJE DE SALUD — MAME (SOLO LECTURA)",
                  font=("Segoe UI", 15, "bold")).pack(anchor="w", pady=(0, 5))
        ttk.Label(
            body,
            text="Golpea a P2 con ALT IZQUIERDO mientras MAME esté activo. "
                 "El analizador detectará la tecla sin necesitar otro jugador remoto."
        ).pack(anchor="w")
        ttk.Label(body, textvariable=self.alt_status).pack(anchor="w", pady=(3, 0))
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
            guided, text="4. P1 RECIBIÓ DAÑO",
            command=lambda: self.worker.jobs.put(("manual_damage", 1))
        ).pack(side="left")
        ttk.Label(body, textvariable=self.state).pack(fill="x", pady=(0, 6))
        holder = ttk.Frame(body)
        holder.pack(fill="both", expand=True)
        cols = ("health", "address", "value", "evidence", "opposite", "confidence")
        self.table = ttk.Treeview(holder, columns=cols, show="headings")
        for name, title, width in (
            ("health", "Posible barra", 115),
            ("address", "Dirección RAM", 190),
            ("value", "Valor actual", 100),
            ("evidence", "Bajadas relacionadas", 145),
            ("opposite", "Bajadas contradictorias", 165),
            ("confidence", "Coincidencia", 105),
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
        self._line("En MAME pulsa ALT IZQUIERDO: verás subir su contador y aparecerán candidatos.")
        self._line("Si aparecen 0 candidatos: usa CAPTURAR ANTES y un golpe ALT, o pega CE.")
        self._line("Si necesitas confirmar daño manualmente, usa CAPTURAR ANTES, "
                   "daño sin ALT y pulsa P2/P1 RECIBIÓ DAÑO.")
        self._line("Las direcciones propuestas son hipótesis, valida todo en Cheat Engine.")
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
            elif kind == "rank":
                selected = self.table.selection()
                selection_value = (
                    self.table.item(selected[0], "values")[1] if selected else None)
                for row in self.table.get_children():
                    self.table.delete(row)
                for _, health, address, value, matched, contrary, conf in val:
                    row = self.table.insert("", "end", values=(
                        f"Salud P{health}", f"0x{address:08X}", value,
                        matched, contrary, f"{conf}% (preliminar)"))
                    if f"0x{address:08X}" == selection_value:
                        self.table.selection_set(row)
            elif kind == "snapshot":
                self._line("Memoria preparada. Realiza golpes aislados alternando P1 y P2.")
        if not self.worker.stop_event.is_set():
            self.root.after(130, self.poll)

    def close(self):
        self.worker.stop_event.set()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def selftest():
    learner = ScoreLearner()
    # Direcciones simuladas; P1 golpea => barra P2 baja, al revés P2 => P1.
    for n in range(5):
        learner.observe({0x10000: 120 - n * 5, 0x20000: 125},
                        {0x10000: 115 - n * 5, 0x20000: 125}, 1)
    for n in range(5):
        learner.observe({0x10000: 95, 0x20000: 125 - n * 5},
                        {0x10000: 95, 0x20000: 120 - n * 5}, 2)
    leaders = learner.top(8)
    assert any(row[1] == 2 and row[2] == 0x10000 and row[4] == 5 for row in leaders)
    assert any(row[1] == 1 and row[2] == 0x20000 and row[4] == 5 for row in leaders)
    assert parse_addresses("00123000\n0x00124000") == [0x123000, 0x124000]
    print("OK: asociacion P1/P2, memoria solo lectura y direcciones CE.")


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
