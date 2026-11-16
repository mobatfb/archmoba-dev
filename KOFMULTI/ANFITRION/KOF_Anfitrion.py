#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KOF ARENA REMOTA - servidor/anfitrion exclusivo de Windows.

El anfitrion aloja una instancia de MAME en Windows; los invitados envian
EXCLUSIVAMENTE acciones permitidas para P1 o P2. NO SE TRANSMITE VIDEO.
Compatible con Cloudflare Quick Tunnel (WSS) sin abrir puertos.

Este software no modifica los archivos ROM, no instala acceso remoto al
escritorio y no ejecuta comandos recibidos de los invitados.
"""
from __future__ import annotations

import collections
import ctypes
import json
import math
import os
import pathlib
import queue
import random
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import zipfile
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

try:
    from KOF_AutoResultados import AutoResultMonitor
except ImportError:
    AutoResultMonitor = None

try:
    from KOF_MAME_Lua_Bridge import LuaHealthMonitor, STATE_FILE_NAME
except ImportError:
    LuaHealthMonitor = None
    STATE_FILE_NAME = "KOF_ARENA_LUA_ESTADO.txt"

APP_VERSION = "1.16.7"
BASE_DIR = pathlib.Path(__file__).resolve().parent
GAME_ARCHIVE = "KOF2022GAME.zip"
GAME_FOLDER = "KOF2022GAME"
DEFAULT_PORT = 8765
API_POST_URL = "https://api.isupol.edu.ec/api/posturlkof"
MAX_GUESTS = 24
MAX_INPUTS_PER_SECOND = 85
HEALTH_ANALYZER_PORT = 38724  # Diagnóstico local 127.0.0.1 únicamente.
START_LIMIT_SECONDS = 30
START_WARNING_AFTER = 20
IDLE_LIMIT_SECONDS = 60
IDLE_WARNING_AFTER = 50
# Ranuras del MAME antiguo dedicadas a la Arena (no utilizar manualmente 8 ni 9).
STATE_KEYS = {1: "8", 2: "9"}
STATE_FOLDER = "KOF_ARENA_ESTADOS"
STATE_WRITE_TIMEOUT = 3.5
BOT_MAX_SECONDS = 90.0
MODE_TECHNICAL = "Victoria tecnica + reiniciar"
MODE_BOT = "Bot temporal (experimental)"
MODE_RESTART = "Solo reiniciar"
MODE_RESTORE = "Restaurar Save State"
CHAMPION_EXIT_MODES = (MODE_TECHNICAL, MODE_BOT, MODE_RESTART, MODE_RESTORE)
# COIN_START is one complete, atomic player gesture; it is NOT a MAME key.
# The host expands it into COIN, pause, START for the assigned slot.
SINGLE_ACTIONS = frozenset(("UP", "DOWN", "LEFT", "RIGHT", "A", "B", "C", "D", "START", "COIN"))
ACTIONS = SINGLE_ACTIONS | {"COIN_START"}
COIN_KEY_HOLD_SECONDS = 0.14
COIN_BEFORE_START_SECONDS = 0.28
START_KEY_HOLD_SECONDS = 0.14

try:
    from websockets.sync.server import serve as ws_serve
    from websockets.sync.client import connect as ws_connect
except ImportError:
    ws_serve = None
    ws_connect = None


# Los recursos del juego no se incluyen en el script; se leen del ZIP del usuario.


def get_game_folder() -> pathlib.Path:
    """Devuelve carpeta existente o extrae solo archivos seguros del ZIP propio."""
    for folder in (BASE_DIR, BASE_DIR / GAME_FOLDER):
        if (folder / "mame.exe").is_file() and (folder / "kf2k2mp2.zip").is_file():
            return folder
    archive = BASE_DIR / GAME_ARCHIVE
    if not archive.is_file():
        raise FileNotFoundError(
            f"No encuentro mame.exe ni {GAME_ARCHIVE} junto a {pathlib.Path(__file__).name}."
        )
    target = BASE_DIR / GAME_FOLDER
    target.mkdir(parents=True, exist_ok=True)
    allowed = {
        "mame.exe", "mame.ini", "default.cfg", "kf2k2mp2.cfg", "kf2k2mp2.nv",
        "kf2k2mp2.zip", "kof2002.zip", "neogeo.zip", "Launch.bat",
    }
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            if info.filename not in allowed or info.is_dir():
                raise ValueError(f"Archivo inesperado o ruta insegura en ZIP: {info.filename}")
            if info.file_size > 140 * 1024 * 1024:
                raise ValueError("El ZIP contiene un archivo inesperadamente grande.")
            dest = target / info.filename
            if dest.exists() and dest.stat().st_size == info.file_size:
                continue
            temp = dest.with_name(dest.name + ".parcial")
            try:
                with zf.open(info, "r") as src, temp.open("wb") as dst:
                    shutil.copyfileobj(src, dst, length=1024 * 1024)
                temp.replace(dest)
            finally:
                if temp.exists():
                    temp.unlink()
    if not (target / "mame.exe").is_file():
        raise FileNotFoundError("No se encontro mame.exe en el ZIP.")
    return target


def clean_address(raw: str) -> str:
    """Acepta https://sala.trycloudflare.com o ws(s)://servidor:puerto."""
    raw = raw.strip()
    if not raw:
        raise ValueError("Ingresa el enlace o direccion del anfitrion.")
    if "://" not in raw:
        raw = "ws://" + raw
    parsed = urlsplit(raw)
    scheme = {"http": "ws", "https": "wss", "ws": "ws", "wss": "wss"}.get(parsed.scheme.lower())
    if not scheme or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Direccion no valida. Ejemplo: https://sala.trycloudflare.com")
    if parsed.port is not None and not (1 <= parsed.port <= 65535):
        raise ValueError("Puerto fuera de rango.")
    if parsed.query or parsed.fragment:
        raise ValueError("Usa solo el dominio de la sala, sin parametros.")
    return urlunsplit((scheme, parsed.netloc, parsed.path or "/", "", ""))



def publish_api_url(url: str, timeout: float = 8.0) -> dict:
    """POST al registro público; url vacía despublica la sala."""
    url = str(url or "").strip().rstrip("/")
    if url and not re.fullmatch(r"https://[a-z0-9-]+\.trycloudflare\.com", url, flags=re.I):
        raise ValueError("La URL de Cloudflare no tiene el formato esperado.")
    payload = json.dumps({"url": url}, ensure_ascii=False).encode("utf-8")
    request = Request(API_POST_URL, data=payload, method="POST", headers={
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "KOF-Arena-Host/1.16",
    })
    with urlopen(request, timeout=timeout) as response:
        result = json.load(response)
    if not isinstance(result, dict) or result.get("status") != "success":
        raise RuntimeError("La API no confirmó la actualización del enlace.")
    return result


def _json(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


@dataclass
class Guest:
    uid: int
    name: str
    websocket: Any = None
    slot: int = 0
    queued: bool = False
    held: set[str] = field(default_factory=set)
    input_times: collections.deque = field(default_factory=collections.deque)
    messages: queue.Queue = field(default_factory=lambda: queue.Queue(maxsize=40))
    wake: threading.Event = field(default_factory=threading.Event)
    active: bool = True
    granted_at: float = 0.0
    start_pressed: bool = False
    last_input_at: float = 0.0
    warned_start: bool = False
    warned_idle: bool = False
    combo_epoch: int = 0
    combo_running: bool = False
    input_feedback_at: float = 0.0

    def tell(self, msg: dict) -> None:
        try:
            self.messages.put_nowait(_json(msg))
        except queue.Full:
            self.active = False
        self.wake.set()


class NullInput:
    """Adaptador para las pruebas en equipo sin Windows/MAME."""
    def __init__(self):
        self.events: list[tuple[int, str, bool]] = []

    def apply(self, slot: int, action: str, down: bool):
        self.events.append((slot, action, down))

    def release_slot(self, slot: int):
        pass


class MameKeyboard:
    """Puente de acciones P1/P2 a teclado Windows para MAME.

    Preparación del foco, diagnóstico y tiempo mínimo de pulsación evitan
    que los toques rápidos de un control táctil desaparezcan entre fotogramas.
    Todas las teclas se envían EXCLUSIVAMENTE al juego iniciado por este host.
    """
    VK = {
        "CTRL": 0xA2, "ALT": 0xA4, "SHIFT": 0xA0, "SPACE": 0x20,
        "F7": 0x76, "F3": 0x72,
        "UP": 0x26, "DOWN": 0x28, "LEFT": 0x25, "RIGHT": 0x27,
    }
    for _ch in "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        VK[_ch] = ord(_ch)
    P1_KEYS = {
        "UP": "UP", "DOWN": "DOWN", "LEFT": "LEFT", "RIGHT": "RIGHT",
        "A": "CTRL", "B": "ALT", "C": "SPACE", "D": "SHIFT",
        "START": "1", "COIN": "5",
    }
    P2_KEYS = {
        "UP": "R", "DOWN": "F", "LEFT": "D", "RIGHT": "G",
        "A": "A", "B": "S", "C": "Q", "D": "W",
        "START": "2", "COIN": "6",
    }
    MAP = {1: P1_KEYS, 2: P2_KEYS}
    MIN_HOLD = 0.105  # >= 6 fotogramas en una emulación a 60 Hz

    @classmethod
    def game_key(cls, slot: int, action: str) -> str:
        if slot not in (1, 2) or action not in SINGLE_ACTIONS:
            raise ValueError("Puesto o acción de juego no válida")
        return cls.MAP[slot][action]

    def __init__(self, game_process_provider: Callable[[], Any],
                 status_notify: Optional[Callable[[str, Any], None]] = None):
        if sys.platform != "win32":
            raise OSError("El anfitrión de MAME debe utilizar Windows.")
        from ctypes import wintypes
        self.wintypes = wintypes
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._process = game_process_provider
        self.status_notify = status_notify
        self.key_states: dict[str, bool] = {}
        self._pressed_at: dict[str, float] = {}
        self._release_timers: dict[str, threading.Timer] = {}
        self._lock = threading.RLock()
        self.input_error = ""
        self._last_info = ""
        self._last_info_at = 0.0
        ulong_ptr = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                        ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                        ("dwExtraInfo", ulong_ptr)]

        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                        ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                        ("time", wintypes.DWORD), ("dwExtraInfo", ulong_ptr)]

        class HARDWAREINPUT(ctypes.Structure):
            _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD),
                        ("wParamH", wintypes.WORD)]

        class UNION(ctypes.Union):
            _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]

        class INPUT(ctypes.Structure):
            _fields_ = [("type", wintypes.DWORD), ("data", UNION)]

        self.INPUT, self.UNION, self.KEYBDINPUT = INPUT, UNION, KEYBDINPUT
        self.send_input = self.user32.SendInput
        self.send_input.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
        self.send_input.restype = wintypes.UINT
        self.map_vk = self.user32.MapVirtualKeyW
        self.map_vk.argtypes = [wintypes.UINT, wintypes.UINT]
        self.map_vk.restype = wintypes.UINT
        self.user32.GetForegroundWindow.restype = wintypes.HWND
        self.user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        self.user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        self.user32.IsWindowVisible.argtypes = [wintypes.HWND]
        self.user32.IsWindowVisible.restype = wintypes.BOOL
        self.user32.IsIconic.argtypes = [wintypes.HWND]
        self.user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        self.user32.SetForegroundWindow.restype = wintypes.BOOL
        self.user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        self.user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
        self.user32.AttachThreadInput.restype = wintypes.BOOL
        self.kernel32.GetCurrentThreadId.restype = wintypes.DWORD

    def _status(self, message: str, *, failed: bool = False) -> None:
        if failed:
            self.input_error = message
        if self.status_notify is None:
            return
        now = time.monotonic()
        if message != self._last_info or now - self._last_info_at > 3:
            self._last_info, self._last_info_at = message, now
            self.status_notify("input_status", message)
            if failed:
                self.status_notify("log", "CONTROL: " + message)

    def _running_process(self):
        process = self._process()
        return process if process is not None and process.poll() is None else None

    def _game_has_focus(self) -> bool:
        process = self._running_process()
        if process is None:
            return False
        hwnd = self.user32.GetForegroundWindow()
        if not hwnd:
            return False
        pid = self.wintypes.DWORD()
        self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value == process.pid

    def _find_game_window(self):
        process = self._running_process()
        if process is None:
            return None
        callback_type = ctypes.WINFUNCTYPE(self.wintypes.BOOL, self.wintypes.HWND, self.wintypes.LPARAM)
        candidates = []

        def enumerate_window(hwnd, _):
            pid = self.wintypes.DWORD()
            self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == process.pid and self.user32.IsWindowVisible(hwnd):
                candidates.append(hwnd)
                return False
            return True

        callback = callback_type(enumerate_window)
        self.user32.EnumWindows(callback, 0)
        return candidates[0] if candidates else None

    def _focus_mame(self) -> bool:
        if self._game_has_focus():
            return True
        if self._running_process() is None:
            self._status("MAME no está iniciado. Pulsa 3. INICIAR KOF en el anfitrión.", failed=True)
            return False
        hwnd = self._find_game_window()
        if not hwnd:
            self._status("MAME está abierto pero no encuentro su ventana. Espera a que cargue.", failed=True)
            return False
        if self.user32.IsIconic(hwnd):
            self.user32.ShowWindow(hwnd, 9)  # SW_RESTORE solamente si estaba minimizada.
        self.user32.SetForegroundWindow(hwnd)
        if self._game_has_focus():
            return True
        # Windows a veces prohíbe el foco desde el hilo WebSocket.
        # Acoplar temporalmente su cola con la ventana en primer plano.
        foreground = self.user32.GetForegroundWindow()
        foreground_thread = (self.user32.GetWindowThreadProcessId(foreground, None)
                             if foreground else 0)
        this_thread = self.kernel32.GetCurrentThreadId()
        attached = False
        try:
            if foreground_thread and foreground_thread != this_thread:
                attached = bool(self.user32.AttachThreadInput(this_thread, foreground_thread, True))
            self.user32.SetForegroundWindow(hwnd)
        finally:
            if attached:
                self.user32.AttachThreadInput(this_thread, foreground_thread, False)
        if self._game_has_focus():
            return True
        self._status("Windows no permitió activar MAME. Haz clic en la ventana del juego; comprueba también que MAME y Python tengan el mismo nivel de permisos.", failed=True)
        return False

    def prepare(self, slot: int) -> bool:
        """Solo se prepara una ventana del proceso MAME de esta sala."""
        if slot not in self.MAP:
            return False
        with self._lock:
            return self._focus_mame()

    def _send(self, key: str, pressed: bool) -> bool:
        vk = self.VK[key]
        scan = int(self.map_vk(vk, 0))
        if scan <= 0:
            self._status(f"No se pudo resolver la tecla {key} de Windows.", failed=True)
            return False
        flags = 0x0008  # KEYEVENTF_SCANCODE
        if key in {"UP", "DOWN", "LEFT", "RIGHT"}:
            flags |= 0x0001  # KEYEVENTF_EXTENDEDKEY
        if not pressed:
            flags |= 0x0002  # KEYEVENTF_KEYUP
        event = self.INPUT(type=1, data=self.UNION(
            ki=self.KEYBDINPUT(0, scan, flags, 0, 0)))
        sent = int(self.send_input(1, ctypes.byref(event), ctypes.sizeof(self.INPUT)))
        if sent != 1:
            code = ctypes.get_last_error()
            self._status(f"Windows bloqueó SendInput para {key} (código {code}). Revisa los permisos de MAME y Python.", failed=True)
            return False
        return True

    def _cancel_release(self, key: str):
        timer = self._release_timers.pop(key, None)
        if timer is not None:
            timer.cancel()

    def _release_now(self, key: str) -> bool:
        self._cancel_release(key)
        self._pressed_at.pop(key, None)
        if not self.key_states.get(key):
            return True
        ok = self._send(key, False)
        # Se mantiene el estado si Windows rechazó el key-up para poder reintentar.
        if ok:
            self.key_states.pop(key, None)
        return ok

    def _finish_delayed_release(self, key: str):
        with self._lock:
            self._release_timers.pop(key, None)
            self._release_now(key)

    def apply(self, slot: int, action: str, down: bool) -> bool:
        key = self.game_key(slot, action)
        with self._lock:
            if down:
                if not self._focus_mame():
                    return False
                self._cancel_release(key)
                if self.key_states.get(key):
                    return True
                if not self._send(key, True):
                    return False
                self.key_states[key] = True
                self._pressed_at[key] = time.monotonic()
                self.input_error = ""
                self._status(f"P{slot}: {action} => tecla MAME {key} enviada a Windows")
                return True
            if not self.key_states.get(key):
                return True
            remaining = self.MIN_HOLD - (time.monotonic() - self._pressed_at.get(key, 0))
            if remaining > 0:
                self._cancel_release(key)
                timer = threading.Timer(remaining, self._finish_delayed_release, args=(key,))
                timer.daemon = True
                self._release_timers[key] = timer
                timer.start()
                return True
            return self._release_now(key)

    def release_slot(self, slot: int):
        with self._lock:
            for key in self.MAP[slot].values():
                self._release_now(key)

    def release_all(self):
        for slot in (1, 2):
            self.release_slot(slot)

class MameStateHotkeys(MameKeyboard):
    """Teclas especiales del MAME antiguo; restringidas a su propia ventana.

    MAME 2010: Shift+F7 = guardar + ranura, F7 = cargar + ranura.
    No da acceso al teclado del escritorio ni acepta teclas desde Internet.
    """

    def _focus_mame(self) -> bool:
        return super()._focus_mame()

    def send_state(self, action: str, slot_key: str) -> bool:
        if action not in ("save", "load") or slot_key not in ("8", "9"):
            return False
        with self._lock:
            if not self._focus_mame():
                return False
            if action == "save":
                self._send("SHIFT", True)
            try:
                self._send("F7", True)
                time.sleep(0.09)
                self._send("F7", False)
            finally:
                if action == "save":
                    self._send("SHIFT", False)
            time.sleep(0.18)
            if not self._game_has_focus():
                return False
            self._send(slot_key, True)
            time.sleep(0.09)
            self._send(slot_key, False)
            return True

    def reset_game(self) -> bool:
        """Solicita F3 al MAME de la sala; nunca envia teclas a otras ventanas."""
        with self._lock:
            if not self._focus_mame():
                return False
            self._send("F3", True)
            time.sleep(0.10)
            self._send("F3", False)
            return True


class MameCheckpointManager:
    """Save State por puesto, con validación de escritura y PID de MAME.

    ATENCIÓN: cada .sta incluye el estado global del juego (P1, P2, créditos).
    La carga no puede deshacerse únicamente para uno de los participantes.
    """

    def __init__(self, process_provider: Callable[[], Any],
                 game_folder_provider: Callable[[], pathlib.Path],
                 input_device: Any, notify: Callable[[str, Any], None],
                 enabled: bool = True, hotkeys: Any = None):
        self.process_provider = process_provider
        self.game_folder_provider = game_folder_provider
        self.device = input_device
        self.notify = notify
        self.enabled = bool(enabled)
        self.hotkeys = hotkeys  # Permite un sustituto en las pruebas de Linux.
        self.room: Optional[Room] = None
        self.valid: dict[int, tuple[int, int, pathlib.Path]] = {}
        self.pid: Optional[int] = None
        self._failed_attempts: dict[tuple[int, int], float] = {}
        self._lock = threading.RLock()

    def _context(self):
        process = self.process_provider()
        if process is None or process.poll() is not None:
            self.valid.clear()
            self.pid = None
            return None
        if self.pid != process.pid:
            self.pid = process.pid
            self.valid.clear()
            self._failed_attempts.clear()
        return process, self.game_folder_provider() / STATE_FOLDER

    @staticmethod
    def _state_files(folder: pathlib.Path, key: str) -> list[pathlib.Path]:
        # MAME 0.139 suele escribir <state_directory>/<rom>/<ranura>.sta.
        if not folder.exists():
            return []
        return [p for p in folder.rglob("*.sta")
                if p.is_file() and p.stem.lower() == key.lower()]

    def _hotkeys(self):
        if self.hotkeys is None:
            self.hotkeys = MameStateHotkeys(self.process_provider)
        return self.hotkeys

    def _log(self, text: str):
        self.notify("log", "SAVE STATE: " + text)

    def _save(self, slot: int, uid: int) -> bool:
        if not self.enabled:
            return False
        ctx = self._context()
        if ctx is None:
            return False
        process, folder = ctx
        key = STATE_KEYS[slot]
        old = {str(p): (p.stat().st_mtime_ns, p.stat().st_size)
               for p in self._state_files(folder, key)}
        try:
            # No permitimos acciones de jugadores mientras se guarda.
            # Room.lock serializa la entrada y la transición de turnos.
            self.device.release_all() if hasattr(self.device, "release_all") else None
            if self.room is not None:
                for g in self.room.guests.values():
                    g.held.clear()
            if not self._hotkeys().send_state("save", key):
                self._log(f"P{slot}: no se pudo enfocar MAME. No se creó punto de control.")
                self._failed_attempts[(slot, uid)] = time.monotonic() + 4.0
                return False
            end = time.monotonic() + STATE_WRITE_TIMEOUT
            previous_size = 0
            previous_file = None
            stable = 0
            while time.monotonic() < end:
                time.sleep(0.12)
                for file in self._state_files(folder, key):
                    stamp = (file.stat().st_mtime_ns, file.stat().st_size)
                    if stamp[1] < 64 or old.get(str(file)) == stamp:
                        continue
                    if file == previous_file and stamp[1] == previous_size:
                        stable += 1
                    else:
                        previous_file, previous_size, stable = file, stamp[1], 0
                    if stable >= 1:
                        self.valid[slot] = (uid, process.pid, file)
                        self._failed_attempts.pop((slot, uid), None)
                        self._log(f"P{slot}: punto de control guardado (ranura {key}).")
                        return True
            self._log(f"P{slot}: MAME no generó un .sta nuevo; la recuperación queda inactiva para ese turno.")
        except Exception as ex:
            self._log(f"P{slot}: error al guardar ({type(ex).__name__}: {ex}).")
        self._failed_attempts[(slot, uid)] = time.monotonic() + 4.0
        return False

    def _restore(self, slot: int, uid: int, *, manual: bool = False) -> bool:
        ctx = self._context()
        entry = self.valid.get(slot)
        if ctx is None or not entry or entry[0] != uid or entry[1] != self.pid:
            self._log(f"P{slot}: no hay Save State comprobado para ese jugador; no se cargó un estado antiguo.")
            return False
        _, folder = ctx
        path = entry[2]
        if not path.is_file() or path.stat().st_size < 64 or folder not in path.parents:
            self._log(f"P{slot}: falta el archivo de recuperación. No se carga.")
            self.valid.pop(slot, None)
            return False
        try:
            if hasattr(self.device, "release_all"):
                self.device.release_all()
            if self.room is not None:
                for g in self.room.guests.values():
                    g.held.clear()
            if not self._hotkeys().send_state("load", STATE_KEYS[slot]):
                self._log(f"P{slot}: no se pudo enviar la carga (MAME fuera de foco).")
                return False
            # Los puntos posteriores a un rollback quedan obsoletos para AMBOS mandos.
            self.valid.clear()
            self._failed_attempts.clear()
            self._log(f"Se pidió a MAME restaurar el punto P{slot}. Afecta P1, P2 y créditos.")
            if self.room is not None:
                for guest in self.room.guests.values():
                    guest.tell({"type": "notice", "level": "warning",
                                "message": f"Se solicitó volver al Save State P{slot}; afecta P1, P2 y créditos."})
                # Tras un retroceso, los .sta de otros turnos ya no representan
                # la partida actual. Reestablecemos sus puntos de control.
                time.sleep(0.3)
                for guest in tuple(self.room.guests.values()):
                    if guest.slot and (manual or guest.uid != uid):
                        self._save(guest.slot, guest.uid)
                        # El rebobinado y la escritura consumen segundos reales.
                        # Los participantes que siguen jugando recuperan su plazo.
                        now = self.room.clock()
                        if guest.start_pressed:
                            guest.last_input_at = now
                            guest.warned_idle = False
                        else:
                            guest.granted_at = now
                            guest.warned_start = False
            return True
        except Exception as ex:
            self._log(f"P{slot}: error al recuperar ({type(ex).__name__}: {ex}).")
            return False

    def slot_event(self, event: str, slot: int, guest: Guest):
        """Invocado con Room.lock durante entrega, entrada o liberación."""
        with self._lock:
            try:
                if event == "assigned":
                    self.valid.pop(slot, None)
                    self._failed_attempts.pop((slot, guest.uid), None)
                    self._save(slot, guest.uid)
                elif event == "before_input":
                    current = self.valid.get(slot)
                    if (self.enabled and not (current and current[0] == guest.uid)
                            and time.monotonic() >= self._failed_attempts.get((slot, guest.uid), 0)):
                        self._save(slot, guest.uid)
                elif event.startswith("released:"):
                    reason = event.split(":", 1)[1]
                    if self.enabled and reason in {
                        "disconnect", "expired_start", "expired_idle", "kick", "yield"
                    }:
                        self._restore(slot, guest.uid)
                    self.valid.pop(slot, None)
            except Exception as ex:
                self._log(f"No se completó la transición P{slot}: {ex}")

    def invalidate_all(self):
        """Tras un reinicio los estados previos son obsoletos para P1 y P2."""
        with self._lock:
            self.valid.clear()
            self._failed_attempts.clear()

    def manual_restore(self, slot: int) -> bool:
        """Solo botón local del anfitrión; un invitado remoto no puede invocarlo."""
        if not self.room:
            return False
        with self.room.lock:
            guest = next((g for g in self.room.guests.values() if g.slot == slot), None)
            if not guest:
                self._log(f"P{slot}: no hay jugador activo para restaurar.")
                return False
            return self._restore(slot, guest.uid, manual=True)



def create_mame_virtual_profile(directory: pathlib.Path) -> pathlib.Path:
    """Perfil adicional para MAME 0.132, sin sobrescribir sus .cfg originales.

    Obliga a relacionar las entradas de KOF a los botones Xbox visibles como
    joysticks DirectInput. Solo se usa cuando el anfitrion usa mandos virtuales.
    """
    import xml.etree.ElementTree as ET
    mapping = {
        1: {"UP": "KEYCODE_UP", "DOWN": "KEYCODE_DOWN", "LEFT": "KEYCODE_LEFT", "RIGHT": "KEYCODE_RIGHT",
            "A": "KEYCODE_LCONTROL", "B": "KEYCODE_LALT", "C": "KEYCODE_SPACE", "D": "KEYCODE_LSHIFT",
            "START": "KEYCODE_1", "COIN": "KEYCODE_5"},
        2: {"UP": "KEYCODE_R", "DOWN": "KEYCODE_F", "LEFT": "KEYCODE_D", "RIGHT": "KEYCODE_G",
            "A": "KEYCODE_A", "B": "KEYCODE_S", "C": "KEYCODE_Q", "D": "KEYCODE_W",
            "START": "KEYCODE_2", "COIN": "KEYCODE_6"},
    }
    axis = {"UP": "YAXIS_UP_SWITCH", "DOWN": "YAXIS_DOWN_SWITCH",
            "LEFT": "XAXIS_LEFT_SWITCH", "RIGHT": "XAXIS_RIGHT_SWITCH"}
    port_names = {"UP": "JOYSTICK_UP", "DOWN": "JOYSTICK_DOWN",
                  "LEFT": "JOYSTICK_LEFT", "RIGHT": "JOYSTICK_RIGHT",
                  "A": "BUTTON1", "B": "BUTTON2", "C": "BUTTON3", "D": "BUTTON4"}
    root = ET.Element('mameconfig', {'version': '10'})
    input_root = ET.SubElement(ET.SubElement(root, 'system', {'name': 'default'}), 'input')
    for slot in (1, 2):
        for action, ptype in port_names.items():
            if action in axis:
                joystick_code = f'JOYCODE_{slot}_{axis[action]}'
            else:
                joystick_code = f'JOYCODE_{slot}_BUTTON{1 + "ABCD".index(action)}'
            node = ET.SubElement(input_root, 'port', {'type': f'P{slot}_{ptype}'})
            ET.SubElement(node, 'newseq', {'type': 'standard'}).text = (
                f'{mapping[slot][action]} OR {joystick_code}')
        for action, ptype, btn in (("START", f"START{slot}", 8),
                                   ("COIN", f"COIN{slot}", 7)):
            node = ET.SubElement(input_root, 'port', {'type': ptype})
            ET.SubElement(node, 'newseq', {'type': 'standard'}).text = (
                f'{mapping[slot][action]} OR JOYCODE_{slot}_BUTTON{btn}')
    path = directory / 'ctrlr' / 'kof_arena.cfg'
    path.parent.mkdir(parents=True, exist_ok=True)
    tree = ET.ElementTree(root)
    ET.indent(tree, space='    ')
    tree.write(path, encoding='utf-8', xml_declaration=True)
    return path


class VirtualPads:
    """Dos mandos Xbox 360 virtuales para evitar la lectura RawInput del teclado.

    MAME 0.132 usa RawInput/DirectInput y puede ignorar SendInput. La emulacion de
    dispositivos Xbox permite que MAME vea dos mandos DirectInput reales.
    """
    BUTTONS = {"A": "XUSB_GAMEPAD_A", "B": "XUSB_GAMEPAD_B",
               "C": "XUSB_GAMEPAD_X", "D": "XUSB_GAMEPAD_Y",
               "START": "XUSB_GAMEPAD_START", "COIN": "XUSB_GAMEPAD_BACK",
               "UP": "XUSB_GAMEPAD_DPAD_UP", "DOWN": "XUSB_GAMEPAD_DPAD_DOWN",
               "LEFT": "XUSB_GAMEPAD_DPAD_LEFT", "RIGHT": "XUSB_GAMEPAD_DPAD_RIGHT"}

    @staticmethod
    def axes(actions: set[str]) -> tuple[int, int]:
        # Eje analogico + cruceta: MAME antiguo suele leer el eje analogico.
        x = (32767 if "RIGHT" in actions else 0) - (32767 if "LEFT" in actions else 0)
        y = (32767 if "UP" in actions else 0) - (32767 if "DOWN" in actions else 0)
        return x, y

    def __init__(self, process_provider: Callable[[], Any],
                 status_notify: Optional[Callable[[str, Any], None]] = None):
        if sys.platform != "win32":
            raise OSError("Los mandos virtuales requieren Windows.")
        try:
            import vgamepad as vg
        except ImportError as ex:
            raise RuntimeError("Falta vgamepad en el anfitrion. Instala con: py -m pip install vgamepad; acepta el controlador ViGEmBus.") from ex
        self.vg = vg
        try:
            self.pads = [vg.VX360Gamepad(), vg.VX360Gamepad()]
            for pad in self.pads:
                pad.reset()
                pad.update()
        except Exception as ex:
            raise RuntimeError("No se pudieron crear dos mandos Xbox virtuales. Revisa que el controlador ViGEmBus este instalado y habilitado. " + str(ex)) from ex
        self.states: dict[int, set[str]] = {1: set(), 2: set()}
        self._lock = threading.RLock()
        self._pressed_at: dict[tuple[int, str], float] = {}
        self._release_timers: dict[tuple[int, str], threading.Timer] = {}
        self.MIN_HOLD = 0.11  # Toque tactil corto: mantener durante varios fotogramas
        # Focus is best-effort: a virtual HID controller must not be rejected
        # merely because SetForegroundWindow is disallowed for this thread.
        self._process_provider = process_provider
        self._focuser = MameKeyboard(process_provider, status_notify=None)
        self.status_notify = status_notify
        self.input_error = ""
        self._warned_focus_at = 0.0

    def prepare(self, slot: int) -> bool:
        if slot not in (1, 2):
            return False
        game = self._process_provider()
        if game is None or game.poll() is not None:
            self.input_error = "Primero inicia MAME en el anfitrión."
            return False
        try:
            focused = self._focuser.prepare(slot)
        except (OSError, AttributeError, RuntimeError):
            focused = False
        if not focused and self.status_notify is not None:
            now = time.monotonic()
            if now - self._warned_focus_at > 8:
                self._warned_focus_at = now
                self.status_notify("input_status", "Mandos virtuales activos; si MAME no responde, haz clic una vez en la ventana del juego. Las órdenes NO se bloquean por el foco.")
        # HID virtual input is independent of SendInput and will be delivered
        # whether or not Windows permits a focus change.
        self.input_error = ""
        return True

    def _update(self, slot: int):
        current = self.states[slot]
        pad = self.pads[slot - 1]
        pad.reset()
        for action_now in current:
            pad.press_button(button=getattr(self.vg.XUSB_BUTTON, self.BUTTONS[action_now]))
        pad.left_joystick(*self.axes(current))
        pad.update()

    def _cancel_release(self, key: tuple[int, str]):
        timer = self._release_timers.pop(key, None)
        if timer is not None:
            timer.cancel()

    def _release_now(self, slot: int, action: str):
        key = slot, action
        self._cancel_release(key)
        self._pressed_at.pop(key, None)
        self.states[slot].discard(action)
        self._update(slot)

    def _finish_delayed_release(self, slot: int, action: str):
        with self._lock:
            self._release_now(slot, action)

    def apply(self, slot: int, action: str, down: bool) -> bool:
        if slot not in (1, 2) or action not in SINGLE_ACTIONS:
            return False
        with self._lock:
            key = slot, action
            if down:
                self._cancel_release(key)
                if action not in self.states[slot]:
                    self.states[slot].add(action)
                    self._pressed_at[key] = time.monotonic()
                    self._update(slot)
                return True
            if action not in self.states[slot]:
                return True
            remaining = self.MIN_HOLD - (time.monotonic() - self._pressed_at.get(key, 0.0))
            if remaining > 0:
                self._cancel_release(key)
                timer = threading.Timer(remaining, self._finish_delayed_release,
                                        args=(slot, action))
                timer.daemon = True
                self._release_timers[key] = timer
                timer.start()
            else:
                self._release_now(slot, action)
            return True

    def release_slot(self, slot: int):
        with self._lock:
            for key in tuple(self._release_timers):
                if key[0] == slot:
                    self._cancel_release(key)
            for key in tuple(self._pressed_at):
                if key[0] == slot:
                    self._pressed_at.pop(key, None)
            self.states[slot].clear()
            self._update(slot)

    def release_all(self):
        for slot in (1, 2):
            self.release_slot(slot)


class Room:
    """Arbitro de P1/P2 y cola FIFO; los temporizadores se verifican en el servidor.

    La regla de START y la inactividad se controlan exclusivamente en el anfitrion;
    modificar el reloj del cliente no modifica los plazos.
    """
    def __init__(self, input_device: Any, max_guests: int = MAX_GUESTS,
                 clock: Callable[[], float] = time.monotonic,
                 start_limit: float = START_LIMIT_SECONDS,
                 start_warning_after: float = START_WARNING_AFTER,
                 idle_limit: float = IDLE_LIMIT_SECONDS,
                 idle_warning_after: float = IDLE_WARNING_AFTER,
                 slot_events: Optional[Callable[[str, int, Guest], None]] = None,
                 input_observer: Optional[Callable[[int, str], None]] = None):
        self.input = input_device
        self.slot_events = slot_events
        self.input_observer = input_observer
        self.max_guests = max_guests
        self.clock = clock
        self.start_limit = start_limit
        self.start_warning_after = start_warning_after
        self.idle_limit = idle_limit
        self.idle_warning_after = idle_warning_after
        self.guests: dict[int, Guest] = {}
        self.order: collections.deque[int] = collections.deque()
        self.next_uid = 1
        self.lock = threading.RLock()

    def register(self, name: str, websocket=None) -> Guest:
        with self.lock:
            if len(self.guests) >= self.max_guests:
                raise ValueError("Sala llena; vuelve a intentarlo despues.")
            uid = self.next_uid
            self.next_uid += 1
            guest = Guest(uid, name[:24] or f"Jugador {uid}", websocket)
            self.guests[uid] = guest
            self._take_or_queue(guest)
            return guest

    def _assign_slot(self, guest: Guest, slot: int):
        guest.combo_epoch += 1
        guest.combo_running = False
        guest.slot = slot
        guest.queued = False
        guest.granted_at = 0.0
        guest.last_input_at = 0.0
        guest.start_pressed = False
        guest.warned_start = False
        guest.warned_idle = False
        guest.held.clear()
        guest.input_times.clear()
        if self.slot_events:
            self.slot_events("assigned", slot, guest)
        # Los segundos del jugador comienzan DESPUÉS de guardar el punto.
        guest.granted_at = self.clock()

    def _clear_slot(self, guest: Guest, reason: str = "normal"):
        # Invalidate delayed COIN/START actions before releasing/reassigning a pad.
        guest.combo_epoch += 1
        guest.combo_running = False
        if guest.slot:
            slot = guest.slot
            self.input.release_slot(slot)
            if self.slot_events:
                self.slot_events("released:" + reason, slot, guest)
        guest.held.clear()
        guest.input_times.clear()
        guest.slot = 0
        guest.granted_at = 0.0
        guest.start_pressed = False
        guest.last_input_at = 0.0
        guest.warned_start = False
        guest.warned_idle = False

    def _take_or_queue(self, guest: Guest):
        occupied = {x.slot for x in self.guests.values()}
        for slot in (1, 2):
            if slot not in occupied:
                self._assign_slot(guest, slot)
                return
        guest.slot, guest.queued = 0, True
        self.order.append(guest.uid)

    def _fill_vacancies(self):
        while self.order:
            occupied = {x.slot for x in self.guests.values() if x.slot}
            available = next((slot for slot in (1, 2) if slot not in occupied), None)
            if available is None:
                return
            uid = self.order.popleft()
            guest = self.guests.get(uid)
            if guest is not None and guest.queued:
                self._assign_slot(guest, available)

    def yield_slot(self, uid: int) -> bool:
        """Cede un mando y queda de espectador; para volver debe pedir turno."""
        with self.lock:
            guest = self.guests.get(uid)
            if not guest or not guest.slot:
                return False
            self._clear_slot(guest, "yield")
            self._fill_vacancies()
            return True

    def request_slot(self, uid: int) -> bool:
        with self.lock:
            guest = self.guests.get(uid)
            if not guest or guest.slot or guest.queued:
                return False
            self._take_or_queue(guest)
            return True

    def remove(self, uid: int, reason: str = "disconnect") -> Optional[Guest]:
        with self.lock:
            guest = self.guests.pop(uid, None)
            if guest is None:
                return None
            self._clear_slot(guest, reason)
            self.order = collections.deque(u for u in self.order if u != uid)
            guest.active = False
            guest.wake.set()
            self._fill_vacancies()
            return guest

    def _deadline(self, guest: Guest) -> float:
        if not guest.slot:
            return 0.0
        if guest.start_pressed:
            return guest.last_input_at + self.idle_limit
        return guest.granted_at + self.start_limit

    def check_timeouts(self, now: Optional[float] = None) -> list[tuple[str, Guest, int]]:
        """Advierte una sola vez y libera mandos vencidos, reasignando por FIFO.

        Eventos: warning_start, warning_idle, expired_start, expired_idle.
        Se puede invocar desde cualquier hilo: la operación completa es atómica.
        """
        with self.lock:
            when = self.clock() if now is None else now
            events: list[tuple[str, Guest, int]] = []
            for guest in tuple(self.guests.values()):
                if not guest.slot:
                    continue
                slot = guest.slot
                if not guest.start_pressed:
                    elapsed = when - guest.granted_at
                    if elapsed >= self.start_limit:
                        self._clear_slot(guest, "expired_start")
                        events.append(("expired_start", guest, slot))
                    elif elapsed >= self.start_warning_after and not guest.warned_start:
                        guest.warned_start = True
                        events.append(("warning_start", guest, slot))
                else:
                    elapsed = when - guest.last_input_at
                    if elapsed >= self.idle_limit:
                        self._clear_slot(guest, "expired_idle")
                        events.append(("expired_idle", guest, slot))
                    elif elapsed >= self.idle_warning_after and not guest.warned_idle:
                        guest.warned_idle = True
                        events.append(("warning_idle", guest, slot))
            if any(kind.startswith("expired") for kind, _, _ in events):
                self._fill_vacancies()
            return events

    def _combo_is_current(self, guest: Guest, slot: int, epoch: int) -> bool:
        """Reject late key pulses after a disconnect, turn change or new session."""
        return (self.guests.get(guest.uid) is guest and guest.active and
                guest.slot == slot and guest.combo_epoch == epoch)

    def _coin_start_worker(self, guest: Guest, slot: int, epoch: int) -> None:
        """One tap: COIN down/up, small pause, then START down/up.

        Runs without holding the room lock while sleeping, so the rival's
        controls, the video stream and the waiting queue do not freeze.
        """
        def pulse(action: str, down: bool) -> bool:
            with self.lock:
                if not self._combo_is_current(guest, slot, epoch):
                    return False
                self.input.apply(slot, action, down)
                return True

        try:
            if not pulse("COIN", True):
                return
            time.sleep(COIN_KEY_HOLD_SECONDS)
            if not pulse("COIN", False):
                return
            time.sleep(COIN_BEFORE_START_SECONDS)
            if not pulse("START", True):
                return
            time.sleep(START_KEY_HOLD_SECONDS)
            pulse("START", False)
        finally:
            with self.lock:
                if self._combo_is_current(guest, slot, epoch):
                    # A short tap must never leave coin or start held down.
                    self.input.apply(slot, "COIN", False)
                    self.input.apply(slot, "START", False)
                    guest.combo_running = False

    def input_event(self, uid: int, action: str, down: bool) -> bool:
        with self.lock:
            guest = self.guests.get(uid)
            if not guest or not guest.slot or action not in ACTIONS or not isinstance(down, bool):
                return False
            now = self.clock()
            # Impide que un paquete tardío reactive un turno cuyo plazo venció.
            if now >= self._deadline(guest):
                return False
            while guest.input_times and guest.input_times[0] < now - 1:
                guest.input_times.popleft()
            if len(guest.input_times) >= MAX_INPUTS_PER_SECOND:
                return False
            guest.input_times.append(now)
            # No considerar autorepeticiones ni eventos de soltar como actividad nueva.
            if (action in guest.held) == down:
                return True
            # Si el emulador no existe/no puede recibir la tecla, no confirmar START.
            # La cuenta regresiva sigue activa y el cliente recibe un aviso visible.
            if down and hasattr(self.input, "prepare") and not self.input.prepare(guest.slot):
                return False
            if down and self.slot_events:
                self.slot_events("before_input", guest.slot, guest)
                now = self.clock()  # no descontar el tiempo de escritura del Save State
            # No iniciar temporizador de actividad si Windows rechazó el comando.
            if action != "COIN_START":
                applied = self.input.apply(guest.slot, action, down)
                if applied is False:
                    return False
            if down:
                guest.held.add(action)
                if action in ("START", "COIN_START") and not guest.start_pressed:
                    guest.start_pressed = True
                    guest.last_input_at = now
                    guest.warned_idle = False
                elif guest.start_pressed:
                    guest.last_input_at = now
                    guest.warned_idle = False
            else:
                guest.held.discard(action)
            # Informar SOLO a la herramienta local de aprendizaje: haber
            # pulsado no implica haber golpeado. No modifica estadísticas.
            if down and action in ("A", "B", "C", "D") and self.input_observer:
                try:
                    self.input_observer(guest.slot, action)
                except (OSError, RuntimeError, ValueError):
                    pass
            if action == "COIN_START":
                # The remote sends the same action for both players. Only the
                # host knows the assigned slot and expands it to 5/1 or 6/2.
                # Ignore keyup; this is a one-shot pulse, not a held button.
                if down and not guest.combo_running:
                    guest.combo_running = True
                    threading.Thread(
                        target=self._coin_start_worker,
                        args=(guest, guest.slot, guest.combo_epoch),
                        daemon=True,
                        name=f"KOF-CoinStart-P{guest.slot}",
                    ).start()
                return True
            # La conversión P1/P2 se hizo al aplicar la acción; nunca en el cliente.
            return True

    def _timer_state(self, guest: Guest, now: float) -> tuple[str, int]:
        if not guest.slot:
            return "none", 0
        phase = "activity" if guest.start_pressed else "start"
        remaining = max(0, math.ceil(self._deadline(guest) - now))
        return phase, remaining

    def snapshot(self) -> dict:
        with self.lock:
            players = {}
            now = self.clock()
            for slot in (1, 2):
                guest = next((x for x in self.guests.values() if x.slot == slot), None)
                if guest:
                    phase, remaining = self._timer_state(guest, now)
                    players[str(slot)] = {"id": guest.uid, "name": guest.name,
                                          "timer_phase": phase, "timer_remaining": remaining}
                else:
                    players[str(slot)] = None
            return {
                "players": players,
                "queue": [{"id": u, "name": self.guests[u].name}
                          for u in self.order if u in self.guests],
                "spectators": [{"id": g.uid, "name": g.name}
                               for g in self.guests.values() if not g.slot and not g.queued],
                "total": len(self.guests),
            }

    def personalized_snapshots(self) -> list[tuple[Guest, dict]]:
        with self.lock:
            snapshot = self.snapshot()
            return [(guest, {"type": "state", "you": guest.uid, "slot": guest.slot,
                             "waiting_position": list(self.order).index(guest.uid) + 1
                             if guest.queued and guest.uid in self.order else 0,
                             "timer_phase": self._timer_state(guest, self.clock())[0],
                             "timer_remaining": self._timer_state(guest, self.clock())[1],
                             **snapshot}) for guest in self.guests.values()]


class HostServer:
    def __init__(self, port: int, ui_notify: Callable[[str, Any], None],
                 device: Any, bind_lan: bool = False,
                 process_provider: Callable[[], Any] = lambda: None,
                 restore_state: bool = True,
                 game_folder_provider: Callable[[], pathlib.Path] = get_game_folder,
                 state_hotkeys: Any = None,
                 champion_exit_mode: str = MODE_TECHNICAL):
        if ws_serve is None:
            raise RuntimeError("Falta websockets: py -m pip install websockets")
        self.port = port
        self.ui_notify = ui_notify
        self.champion_exit_mode = champion_exit_mode if champion_exit_mode in CHAMPION_EXIT_MODES else MODE_TECHNICAL
        self.last_winner_uid: Optional[int] = None
        self.last_winner_name = ""
        self.scores: dict[int, int] = {}  # victorias
        self.losses: dict[int, int] = {}
        self.perfects: dict[int, int] = {}
        self.bot_until: dict[int, float] = {}
        self.bot_held: dict[int, set[str]] = {}
        self.bot_next: dict[int, float] = {}
        self.bot_rng = random.Random()
        self.checkpoints = MameCheckpointManager(
            process_provider, game_folder_provider, device, ui_notify,
            enabled=restore_state, hotkeys=state_hotkeys)
        self._health_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._health_socket.setblocking(False)
        self.room = Room(device, slot_events=self._slot_event,
                         input_observer=self._observe_attack)
        self.checkpoints.room = self.room
        self.bind_lan = bind_lan
        self.process_provider = process_provider
        self.server = None
        self.thread = None
        self.timer_thread = None
        self.stop_event = threading.Event()

    def _observe_attack(self, slot: int, action: str):
        """Enviar input de golpe aceptado al analizador en localhost, no a Internet."""
        game = self.process_provider()
        if game is None or game.poll() is not None:
            return
        payload = json.dumps({
            "type": "attack", "slot": slot, "action": action,
            "pid": game.pid,
        }, separators=(",", ":")).encode("utf-8")
        self._health_socket.sendto(payload, ("127.0.0.1", HEALTH_ANALYZER_PORT))

    def record_game_outcome(self, winner_slot: int, perfect: bool,
                            expected_uids: tuple[int, int]) -> bool:
        """Solo acepta resultados corroborados por lectura LOCAL del juego.

        Nunca se puntúa por teclas, cola, desconexiones ni botones manuales.
        Solo cuenta enfrentamientos P1 contra P2 con los mismos jugadores.
        """
        if winner_slot not in (1, 2) or len(expected_uids) != 2:
            return False
        with self.room.lock:
            participants = {
                guest.slot: guest for guest in self.room.guests.values()
                if guest.slot in (1, 2) and guest.start_pressed and guest.active
            }
            if set(participants) != {1, 2}:
                return False
            if (participants[1].uid, participants[2].uid) != tuple(expected_uids):
                return False
            winner = participants[winner_slot]
            loser = participants[3 - winner_slot]
            self.scores[winner.uid] = self.scores.get(winner.uid, 0) + 1
            self.losses[loser.uid] = self.losses.get(loser.uid, 0) + 1
            if perfect:
                self.perfects[winner.uid] = self.perfects.get(winner.uid, 0) + 1
            self.last_winner_uid = winner.uid
            self.last_winner_name = winner.name
            points = self.scores[winner.uid] + self.perfects.get(winner.uid, 0)
            self.ui_notify(
                "log",
                f"RESULTADO DEL JUEGO: P{winner_slot} {winner.name} ganó "
                f"contra {loser.name}. PERFECT: {'sí' if perfect else 'no'}. "
                f"Puntaje: {points}.")
            self._broadcast_state()
            return True

    def _stop_bot(self, slot: int, message: bool = True):
        was_active = slot in self.bot_until
        self.bot_until.pop(slot, None)
        self.bot_next.pop(slot, None)
        self.bot_held.pop(slot, None)
        if was_active:
            self.room.input.release_slot(slot)
            if message:
                self.ui_notify("log", f"P{slot}: bot temporal terminado; mando liberado.")

    def _reset_game(self) -> bool:
        process = self.process_provider()
        if process is None or process.poll() is not None:
            self.ui_notify("log", "Reinicio pendiente: MAME no esta abierto.")
            return False
        try:
            result = bool(self.checkpoints._hotkeys().reset_game())
        except Exception as ex:
            result = False
            self.ui_notify("log", f"Fallo al enviar F3: {ex}")
        self.ui_notify("log", "MAME: comando F3 de reinicio enviado." if result else
                       "MAME: no se pudo enviar F3; revisa el foco de la ventana.")
        return result

    def _champion_left(self, slot: int, guest: Guest):
        """Aplica la politica al salir quien gano la pelea anterior.

        El reinicio y el marcador son globales, no una victoria dentro de
        la ROM. Se procesa antes de asignar el asiento a la cola FIFO.
        """
        mode = self.champion_exit_mode
        self.ui_notify("log", f"Se fue el ultimo ganador {guest.name} (P{slot}). Politica: {mode}.")
        if mode == MODE_RESTORE:
            self.checkpoints.slot_event("released:disconnect", slot, guest)
            self.last_winner_uid = None
            self.last_winner_name = ""
            return
        if mode == MODE_BOT:
            self.checkpoints.valid.pop(slot, None)
            self.checkpoints._failed_attempts.pop((slot, guest.uid), None)
            self.last_winner_uid = None
            self.last_winner_name = ""
            if not self.room.order:
                self.bot_until[slot] = time.monotonic() + BOT_MAX_SECONDS
                self.bot_next[slot] = 0.0
                self.bot_held[slot] = set()
                self.ui_notify("log", f"P{slot}: bot basico activado por hasta {int(BOT_MAX_SECONDS)} s; no es la IA nativa ni garantiza ganar.")
                for recipient in self.room.guests.values():
                    if recipient.uid != guest.uid:
                        recipient.tell({"type":"notice", "level":"info",
                                        "message":f"P{slot} ahora pelea con bot basico, hasta que entre otro jugador."})
            return
        # Al reiniciar, los checkpoints de ambos jugadores ya no tienen sentido.
        self.checkpoints.invalidate_all()
        if hasattr(self.room.input, "release_all"):
            self.room.input.release_all()
        for bot_slot in list(self.bot_until):
            self._stop_bot(bot_slot)
        rival = next((g for g in self.room.guests.values()
                      if g.uid != guest.uid and g.slot in (1, 2) and g.start_pressed), None)
        if mode == MODE_TECHNICAL and rival is not None:
            # La desconexion NO es una victoria del videojuego.
            self.last_winner_uid = None
            self.last_winner_name = ""
            self.ui_notify("log", "Ganador desconectado: reinicio sin sumar resultados.")
        else:
            self.last_winner_uid = None
            self.last_winner_name = ""
            message = "Ultimo ganador desconectado: se solicitara reiniciar KOF sin otorgar victoria."
            if mode == MODE_TECHNICAL:
                message = "Ganador desconectado, pero no hay rival activo: reinicio sin victoria."
            self.ui_notify("log", message)
        restarted = self._reset_game()
        for remaining in self.room.guests.values():
            if remaining.uid == guest.uid:
                continue
            if remaining.slot:
                remaining.held.clear()
                remaining.start_pressed = False
                remaining.granted_at = self.room.clock()
                remaining.last_input_at = 0.0
                remaining.warned_start = False
                remaining.warned_idle = False
            remaining.tell({"type": "notice", "level": "warning",
                            "message": message + (" Pulsa ENTER para insertar moneda e iniciar." if restarted else
                                                   " AVISO: verifica manualmente el reinicio en MAME.")})

    def _slot_event(self, event: str, slot: int, guest: Guest):
        # El arbitro Room invoca este metodo bajo su RLock.
        if event == "assigned":
            self._stop_bot(slot)
            self.checkpoints.slot_event(event, slot, guest)
            return
        if event.startswith("released:"):
            reason = event.split(":", 1)[1]
            is_champion = guest.uid == self.last_winner_uid
            if is_champion and reason in ("disconnect", "expired_start", "expired_idle"):
                self._champion_left(slot, guest)
                return
        self.checkpoints.slot_event(event, slot, guest)

    def _tick_bots(self):
        """Pequeno autopiloto de botones. No analiza la pantalla ni asegura victorias."""
        with self.room.lock:
            now = time.monotonic()
            for slot in list(self.bot_until):
                if (any(g.slot == slot for g in self.room.guests.values()) or
                    now >= self.bot_until[slot] or self.stop_event.is_set()):
                    self._stop_bot(slot)
                    continue
                if now < self.bot_next.get(slot, 0):
                    continue
                for action in self.bot_held.get(slot, set()):
                    self.room.input.apply(slot, action, False)
                moves = (('LEFT', 'A'), ('RIGHT', 'B'), ('DOWN', 'C'),
                         ('LEFT', 'D'), ('A',), ('B',), ('C',),
                         ('D',), ('UP', 'A'), ('RIGHT', 'C'))
                actions = set(self.bot_rng.choice(moves))
                try:
                    for action in actions:
                        self.room.input.apply(slot, action, True)
                except Exception as ex:
                    self.ui_notify("log", f"Bot P{slot} no puede enviar controles: {ex}")
                    self._stop_bot(slot)
                    continue
                self.bot_held[slot] = actions
                self.bot_next[slot] = now + self.bot_rng.uniform(0.22, 0.52)

    def start(self):
        bind = "0.0.0.0" if self.bind_lan else "127.0.0.1"
        self.server = ws_serve(self._handle, bind, self.port, max_size=4096,
                               compression=None, ping_interval=15, ping_timeout=15,
                               open_timeout=10, close_timeout=3)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.ui_notify("log", f"Sala sin contraseña activa en {bind}:{self.port} (P1/P2 + cola FIFO).")
        self.timer_thread = threading.Thread(target=self._timer_loop, daemon=True)
        self.timer_thread.start()
        self.ui_notify("log", "Reglas: 30 s para ENTER (moneda + inicio); 60 s sin pulsaciones.")
        self.ui_notify("log", "Marcador: solo resultados leídos del MAME local; sin botones de registro manual.")
        if self.checkpoints.enabled:
            self.ui_notify("log", "Recuperación: Save State de P1/P2 al asumir turno; carga al salir o perder el mando.")
            self.ui_notify("log", "IMPORTANTE: restaurar retrocede TODA la partida y créditos, incluidos los de P2/P1.")
        self.ui_notify("log", "Transmisión de video y audio desactivada.")

    def _handle(self, ws):
        guest = None
        try:
            hello_raw = ws.recv(timeout=12)
            if not isinstance(hello_raw, str) or len(hello_raw) > 4096:
                ws.send(_json({"type": "error", "message": "Solicitud no valida."}))
                return
            data = json.loads(hello_raw)
            if not isinstance(data, dict) or data.get("type") != "hello":
                ws.send(_json({"type": "error", "message": "Protocolo incorrecto."}))
                return
            # Sala abierta: un nombre es suficiente; no se pide clave.
            # Solo se admiten acciones de juego enumeradas en ACTIONS.
            raw_name = str(data.get("name", "Jugador"))
            name = "".join(ch for ch in raw_name if ch.isprintable())[:24].strip() or "Jugador"
            try:
                guest = self.room.register(name, ws)
            except ValueError as ex:
                ws.send(_json({"type": "error", "message": str(ex)}))
                return
            ws.send(_json({"type": "welcome", "you": guest.uid, "version": APP_VERSION,
                           "control_layout": "P1_UNIFICADO"}))
            threading.Thread(target=self._sender_loop, args=(guest,), daemon=True).start()
            self._broadcast_state()
            self.ui_notify("log", f"{guest.name} entro como " + (f"P{guest.slot}" if guest.slot else "espera"))
            for raw in ws:
                if not guest.active:
                    break
                if not isinstance(raw, str) or len(raw) > 4096:
                    continue
                try:
                    data = json.loads(raw)
                except (ValueError, TypeError):
                    continue
                if not isinstance(data, dict):
                    continue
                kind = data.get("type")
                if kind == "input":
                    action, down = data.get("action"), data.get("down")
                    if isinstance(action, str) and isinstance(down, bool):
                        # Enviar actualización inmediata solo en la primera confirmación;
                        # evitar broadcasts en repetición de START.
                        confirmation = False
                        if action in ("START", "COIN_START") and down:
                            with self.room.lock:
                                current = self.room.guests.get(guest.uid)
                                confirmation = bool(current and current.slot and not current.start_pressed)
                        accepted = self.room.input_event(guest.uid, action, down)
                        if down and time.monotonic() - guest.input_feedback_at > (2.0 if not accepted else 0.25):
                            guest.input_feedback_at = time.monotonic()
                            if accepted:
                                guest.tell({"type": "input_ack", "slot": guest.slot, "action": action,
                                            "message": f"P{guest.slot} recibió {action}: enviado al dispositivo de entrada"})
                            else:
                                reason = (getattr(self.room.input, "input_error", "") or
                                          "Entrada rechazada o turno vencido")
                                guest.tell({"type": "notice", "level": "warning",
                                            "message": "Control no aplicado: " + reason})
                                self.ui_notify("input_status", "ENTRADA NO APLICADA: " + reason)
                        if accepted and confirmation:
                            self._broadcast_state()
                elif kind == "yield":
                    if self.room.yield_slot(guest.uid):
                        self._broadcast_state()
                elif kind == "request":
                    if self.room.request_slot(guest.uid):
                        self._broadcast_state()
        except Exception as ex:
            if guest is None:
                self.ui_notify("log", f"Conexion inicial rechazada: {type(ex).__name__}")
        finally:
            if guest is not None:
                self.room.remove(guest.uid, reason="shutdown" if self.stop_event.is_set() else "disconnect")
                self._broadcast_state()
                self.ui_notify("log", f"{guest.name} salio; cola actualizada.")
            try:
                ws.close()
            except Exception:
                pass

    def _sender_loop(self, guest: Guest):
        ws = guest.websocket
        try:
            while guest.active and not self.stop_event.is_set():
                guest.wake.wait(1.0)
                guest.wake.clear()
                while guest.active:
                    try:
                        msg = guest.messages.get_nowait()
                    except queue.Empty:
                        break
                    ws.send(msg)
        except Exception:
            guest.active = False
            try:
                ws.close()
            except Exception:
                pass

    def _broadcast_state(self):
        with self.room.lock:
            roster = self.room.snapshot()
            for slot, until in self.bot_until.items():
                if roster["players"][str(slot)] is None:
                    roster["players"][str(slot)] = {
                        "id": -slot, "name": "BOT TEMPORAL",
                        "timer_phase": "bot",
                        "timer_remaining": max(0, int(until - time.monotonic()))}
            roster["last_winner"] = self.last_winner_name
            roster["scores"] = dict(self.scores)
            roster["losses"] = dict(self.losses)
            roster["perfects"] = dict(self.perfects)
            for guest, state in self.room.personalized_snapshots():
                state.update({"players": roster["players"],
                              "last_winner": self.last_winner_name,
                              "scores": dict(self.scores)})
                guest.tell(state)
            self.ui_notify("roster", roster)

    def _timer_loop(self):
        """Control de tiempo en el anfitrion, independiente de los clientes."""
        descriptions = {
            "warning_start": ("Aviso: te quedan 10 segundos para pulsar START o perderás tu mando.", "warning"),
            "warning_idle": ("Aviso: llevas 50 segundos sin pulsar botones. Tienes 10 segundos antes de perder tu mando.", "warning"),
            "expired_start": ("Turno perdido: no pulsaste START en 30 segundos. Ahora eres espectador; pulsa Solicitar turno para volver a la cola.", "expired"),
            "expired_idle": ("Turno perdido por 60 segundos de inactividad. Ahora eres espectador; pulsa Solicitar turno para volver a la cola.", "expired"),
        }
        last_state_push = 0.0
        while not self.stop_event.is_set():
            events = self.room.check_timeouts()
            for kind, guest, slot in events:
                message, level = descriptions[kind]
                guest.tell({"type": "notice", "level": level, "message": message})
                if kind.startswith("expired"):
                    self.ui_notify("log", f"P{slot} liberado: {guest.name} perdió el turno ({'sin START' if kind == 'expired_start' else 'inactividad'}).")
                else:
                    self.ui_notify("log", f"Aviso a {guest.name} (P{slot}): quedan 10 s.")
            self._tick_bots()
            # Los bots necesitan pulsaciones mas frecuentes; el video y los
            # estados se transmiten por separado para no saturar a invitados.
            now = time.monotonic()
            if events or now - last_state_push >= 0.8:
                self._broadcast_state()
                last_state_push = now
            self.stop_event.wait(0.12 if self.bot_until else 0.8)

    def kick(self, uid: int):
        with self.room.lock:
            guest = self.room.guests.get(uid)
        if guest is not None and guest.websocket:
            try:
                guest.websocket.close(code=1000, reason="Desconexion del anfitrion")
            except Exception:
                pass

    def stop(self):
        self.stop_event.set()
        with self.room.lock:
            for slot in list(self.bot_until):
                self._stop_bot(slot)
            guests = list(self.room.guests.values())
        for guest in guests:
            try:
                guest.websocket.close(code=1001, reason="Sala cerrada")
            except Exception:
                pass
        if self.server is not None:
            try:
                self.server.shutdown()
            except Exception:
                pass
        for guest in guests:
            self.room.remove(guest.uid, reason="shutdown")
        if hasattr(self.room.input, "release_all"):
            self.room.input.release_all()
        try:
            self._health_socket.close()
        except OSError:
            pass
        self.ui_notify("log", "Sala cerrada y controles liberados.")


class HostGUI:
    """Interfaz que SOLO administra el servidor y la partida local."""

    def __init__(self):
        import tkinter as tk
        from tkinter import ttk, messagebox
        self.tk = tk
        self.ttk = ttk
        self.messagebox = messagebox
        self.root = tk.Tk()
        self.root.title(f"KOF ARENA - ANFITRION v{APP_VERSION}")
        # Respetar el alto util de Windows (barra de tareas incluida).
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        window_w = max(490, min(940, sw - 65))
        window_h = max(410, min(780, sh - 80))
        self.root.geometry(f"{window_w}x{window_h}")
        self.root.minsize(min(670, window_w), min(470, window_h))
        self.root.configure(bg="#0b1323")
        self._theme()
        self.events: queue.Queue = queue.Queue(maxsize=400)
        self.server: Optional[HostServer] = None
        self.game_process = None
        self.lua_mame_exe = None
        self.lua_monitor = None
        self.lua_state_path = BASE_DIR / STATE_FILE_NAME
        self.tunnel_process = None
        self.public_address = ""
        self._api_jobs: queue.Queue = queue.Queue()
        self._api_worker = threading.Thread(target=self._api_publish_loop, name="KOF-API", daemon=False)
        self._api_worker.start()
        self.auto_monitor = None
        self.member_by_tree_row: dict[str, int] = {}
        self._build()
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self._poll_job = self.root.after(80, self._poll)

    def _theme(self):
        st = self.ttk.Style()
        st.theme_use("clam")
        st.configure("TFrame", background="#0b1323")
        st.configure("TLabel", background="#0b1323", foreground="#eaf0ff", font=("Segoe UI", 10))
        st.configure("Title.TLabel", background="#0b1323", foreground="#ffffff",
                     font=("Segoe UI Semibold", 15))
        st.configure("Muted.TLabel", background="#0b1323", foreground="#96aace",
                     font=("Segoe UI", 9))
        st.configure("TButton", font=("Segoe UI Semibold", 9), padding=(5, 3))
        st.configure("TEntry", padding=5)
        st.configure("TCombobox", padding=4)
        st.configure("TCheckbutton", background="#0b1323", foreground="#eaf0ff")
        st.map("TCheckbutton", background=[("active", "#0b1323")],
               foreground=[("active", "#ffffff")])
        st.configure("Treeview", background="#172641", foreground="#f1f5ff",
                     fieldbackground="#172641", rowheight=23, borderwidth=0)
        st.configure("Treeview.Heading", background="#213654", foreground="#ffffff",
                     font=("Segoe UI Semibold", 10))
        st.map("Treeview", background=[("selected", "#275dbd")])

    def _entry(self, parent, title, var, width=20):
        group = self.ttk.Frame(parent)
        group.pack(side="left", padx=(0, 12))
        self.ttk.Label(group, text=title, style="Muted.TLabel").pack(anchor="w")
        widget = self.ttk.Entry(group, textvariable=var, width=width)
        widget.pack(pady=(3, 0))
        return widget

    def _build(self):
        """Panel compacto con prioridad para participantes y lista de espera."""
        tk, ttk = self.tk, self.ttk

        self.port_var = tk.StringVar(value=str(DEFAULT_PORT))
        self.lan_var = tk.BooleanVar(value=False)
        self.input_diagnostic_var = tk.StringVar(
            value="Abre la sala antes de iniciar MAME.")
        self.mame_choice_var = tk.StringVar(
            value="Emulador: MAME 0.132 original (selecciona 0.289 para Lua)")
        self.lua_health_var = tk.StringVar(
            value="VIDA P1: --  |  VIDA P2: --  |  Lua desactivado")
        self.host_url_var = tk.StringVar(value="Sala no publicada.")
        self.api_status_var = tk.StringVar(value="API: sala no publicada")
        self.roster_count_var = tk.StringVar(
            value="0 conectados | P1 libre | P2 libre | En espera: 0")
        self.activity_visible = False

        body = ttk.Frame(self.root)
        body.pack(fill="both", expand=True, padx=10, pady=7)

        # La consola se aloja al final y solo ocupa altura si el usuario la abre.
        activity_shell = ttk.Frame(body)
        activity_shell.pack(side="bottom", fill="x", pady=(5, 0))
        activity_heading = ttk.Frame(activity_shell)
        activity_heading.pack(fill="x")
        self.activity_toggle = ttk.Button(
            activity_heading, text="ACTIVIDAD DEL SERVIDOR ▸",
            command=self._toggle_activity)
        self.activity_toggle.pack(side="left")
        self.log = tk.Text(
            activity_shell, height=5, bg="#101d34", fg="#dce9ff",
            relief="flat", font=("Consolas", 9),
            insertbackground="#fff", wrap="word", state="disabled")
        # La consola no se empaqueta hasta pulsar el boton de actividad.

        header = ttk.Frame(body)
        header.pack(side="top", fill="x", pady=(0, 5))
        ttk.Label(header, text=f"KOFMULTI | ANFITRION v{APP_VERSION}",
                  style="Title.TLabel").pack(side="left")
        ttk.Checkbutton(header, text="Permitir LAN",
                        variable=self.lan_var).pack(side="right")
        port_group = ttk.Frame(header)
        port_group.pack(side="right", padx=(0, 10))
        ttk.Label(port_group, text="Puerto:").pack(side="left", padx=(0, 4))
        ttk.Entry(port_group, textvariable=self.port_var,
                  width=7).pack(side="left")

        commands = ttk.Frame(body)
        commands.pack(side="top", fill="x", pady=(0, 5))
        ttk.Button(commands, text="1. ABRIR SALA",
                   command=self._start_server).pack(side="left", padx=(0, 6))
        ttk.Button(commands, text="2. PUBLICAR EN INTERNET",
                   command=self._start_tunnel).pack(side="left", padx=(0, 6))
        ttk.Button(commands, text="3. INICIAR KOF",
                   command=self._start_game).pack(side="left")
        ttk.Button(commands, text="CERRAR SALA",
                   command=self._stop_server).pack(side="right")

        emulator = ttk.Frame(body)
        emulator.pack(side="top", fill="x", pady=(0, 3))
        ttk.Button(emulator, text="Elegir MAME 0.289 + Lua",
                   command=self._choose_mame_lua).pack(side="left", padx=(0, 6))
        ttk.Button(emulator, text="Usar MAME 0.132",
                   command=self._use_legacy_mame).pack(side="left", padx=(0, 8))
        ttk.Label(emulator, textvariable=self.mame_choice_var,
                  style="Muted.TLabel").pack(side="left", fill="x", expand=True)
        ttk.Label(body, textvariable=self.lua_health_var,
                  style="TLabel").pack(side="top", fill="x", pady=(0, 4))

        pads = ttk.Frame(body)
        pads.pack(side="top", fill="x", pady=(0, 4))
        ttk.Label(pads, text="2 joysticks Xbox 360",
                  style="Muted.TLabel").pack(side="left", padx=(0, 8))
        ttk.Button(pads, text="Ver mandos",
                   command=self._show_windows_gamepads).pack(side="right")
        ttk.Button(pads, text="Analizar salud",
                   command=self._launch_health_analyzer).pack(side="right", padx=(0, 6))
        ttk.Label(pads, textvariable=self.input_diagnostic_var,
                  style="Muted.TLabel", width=30, anchor="w").pack(
                      side="left", fill="x", expand=True)

        address = ttk.Frame(body)
        address.pack(side="top", fill="x", pady=(0, 3))
        ttk.Label(address, text="Sala:").pack(side="left", padx=(0, 5))
        ttk.Button(address, text="Copiar acceso",
                   command=self._copy_join).pack(side="right")
        ttk.Button(address, text="Reenviar API",
                   command=self._resync_api).pack(side="right", padx=(0, 5))
        ttk.Entry(address, textvariable=self.host_url_var,
                  state="readonly").pack(side="left", fill="x", expand=True)

        ttk.Label(body, textvariable=self.api_status_var,
                  style="Muted.TLabel").pack(
                      side="top", fill="x", pady=(0, 4))

        roster_header = ttk.Frame(body)
        roster_header.pack(side="top", fill="x", pady=(1, 3))
        ttk.Label(roster_header, text="JUGADORES Y LISTA DE ESPERA",
                  style="TLabel").pack(side="left")
        ttk.Button(roster_header, text="Expulsar seleccionado",
                   command=self._kick_selected).pack(side="right")
        ttk.Label(roster_header, textvariable=self.roster_count_var,
                  style="Muted.TLabel").pack(side="right", padx=(0, 10))

        # La lista tiene todo el alto restante y crece al maximizar.
        table_holder = ttk.Frame(body)
        table_holder.pack(side="top", fill="both", expand=True)
        self.roster = ttk.Treeview(
            table_holder,
            columns=("slot", "name", "id", "wins", "losses", "perfects", "points"),
            show="headings", height=12, selectmode="browse")
        for key, title, width, stretch in (
            ("slot", "Posicion", 120, True),
            ("name", "Participante", 205, True),
            ("id", "ID", 40, False),
            ("wins", "Ganados", 62, False),
            ("losses", "Perdidos", 62, False),
            ("perfects", "Perfecto", 62, False),
            ("points", "Puntaje", 62, False),
        ):
            self.roster.heading(key, text=title)
            self.roster.column(
                key, width=width, minwidth=40, stretch=stretch,
                anchor="w" if key == "name" else "center")
        self.roster.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(
            table_holder, orient="vertical", command=self.roster.yview)
        self.roster.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")

        self._append("Sala sin contrasena. Comparte el enlace solo con tus invitados.")
        self._append("El enlace de la sala se publica automaticamente en la API.")
        self._append("Primero abre sala, despues inicia MAME con P1 y P2 virtuales.")
        self._append("No se transmite video ni audio. Los mandos requieren ViGEmBus.")
        self._append("Temporizadores: 30 s para START y 60 s sin actividad.")
        self._append("Lua MAME 0.289: lee vida P1/P2 desde RAM emulada, sin escribir ni sumar puntos.")
        self._append("Entrenamiento de salud: los golpes se observan en RAM, pero nunca suman puntos por sí solos.")
        self._append("Puntaje = Ganados + Perfecto (1 punto por cada uno).")
        self._show_roster({
            "players": {"1": None, "2": None},
            "queue": [], "spectators": [], "total": 0})

    def _toggle_activity(self):
        """Muestra u oculta la consola sin desplazar a la tabla."""
        self.activity_visible = not self.activity_visible
        if self.activity_visible:
            self.log.pack(fill="x", pady=(4, 0))
            self.activity_toggle.configure(
                text="OCULTAR ACTIVIDAD DEL SERVIDOR ▾")
            self.log.see("end")
        else:
            self.log.pack_forget()
            self.activity_toggle.configure(
                text="ACTIVIDAD DEL SERVIDOR ▸")

    def _append(self, line):
        self.log.configure(state="normal")
        self.log.insert("end", f"[{time.strftime('%H:%M:%S')}] {line}\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def notify(self, kind: str, data: Any):
        try:
            self.events.put_nowait((kind, data))
        except queue.Full:
            pass

    def _api_publish_loop(self):
        """Publicación ordenada sin bloquear la interfaz gráfica."""
        while True:
            url = self._api_jobs.get()
            try:
                if url is None:
                    return
                publish_api_url(url)
                if url:
                    self.notify("api_status", "API: enlace publicado correctamente en amo_users.email")
                    self.notify("log", "API POST correcto: los jugadores ya pueden encontrar la sala.")
                else:
                    self.notify("api_status", "API: enlace retirado (sala cerrada)")
                    self.notify("log", "API POST correcto: dirección pública despublicada.")
            except HTTPError as exc:
                self.notify("api_status", f"API: error HTTP {exc.code}")
                self.notify("log", f"Error al publicar en la API (HTTP {exc.code}). Revisa Laravel y la ruta /api/posturlkof.")
            except (URLError, TimeoutError, OSError, ValueError, RuntimeError) as exc:
                self.notify("api_status", "API: no fue posible sincronizar el enlace")
                self.notify("log", f"La API no se actualizó: {exc}")
            finally:
                self._api_jobs.task_done()

    def _poll(self):
        for _ in range(45):
            try:
                kind, data = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "log":
                self._append(str(data))
            elif kind == "roster":
                self._show_roster(data)
            elif kind == "public_url":
                if self.public_address != str(data):
                    self.public_address = str(data)
                    self.host_url_var.set("ENLACE PUBLICO: " + self.public_address)
                    self._append("Enlace disponible: " + self.public_address)
                    self.api_status_var.set("API: publicando enlace en la base de datos...")
                    self._api_jobs.put(self.public_address)
            elif kind == "api_status":
                self.api_status_var.set(str(data))
            elif kind == "input_status":
                self.input_diagnostic_var.set("CONTROLES: " + str(data)[:210])
            elif kind == "lua_health":
                # Son valores de RAM en observacion, no resultados definitivos.
                self.lua_health_var.set(
                    f"VIDA P1: {data.p1}  |  VIDA P2: {data.p2}"
                    f"  |  Rondas perdidas?: P1={data.rounds_lost_p1}"
                    f" / P2={data.rounds_lost_p2}  |  solo lectura")
            elif kind == "lua_status":
                if str(data).startswith("Lua conectado:"):
                    if "Lua desactivado" in self.lua_health_var.get():
                        self.lua_health_var.set(
                            "VIDA P1: --  |  VIDA P2: --  |  esperando lecturas Lua...")
                elif not str(data).startswith("Lua: esperando"):
                    self._append(str(data))
                if "MAME se cerró" in str(data):
                    self.lua_health_var.set("VIDA P1: --  |  VIDA P2: --  |  MAME cerrado")
            elif kind == "tunnel_closed":
                if self.tunnel_process is data:
                    self.tunnel_process = None
                    if self.public_address:
                        self.public_address = ""
                        self._api_jobs.put("")
                        self.host_url_var.set("Túnel interrumpido. Pulsa PUBLICAR EN INTERNET de nuevo.")
                        self.api_status_var.set("API: retirando enlace antiguo...")
        try:
            self._poll_job = self.root.after(80, self._poll)
        except Exception:
            pass

    def _show_roster(self, data):
        """Redibuja todos los jugadores con sus contadores y sin perder scroll."""
        selection = self.roster.selection()
        selected_uid = self.member_by_tree_row.get(selection[0]) if selection else None
        old_scroll = self.roster.yview()
        for item in self.roster.get_children():
            self.roster.delete(item)
        self.member_by_tree_row.clear()
        wins = data.get("scores", {})
        losses = data.get("losses", {})
        perfects = data.get("perfects", {})

        def count(table, person):
            uid = person["id"]
            return int(table.get(uid, table.get(str(uid), 0)))

        def display(position, person):
            won = count(wins, person)
            lost = count(losses, person)
            perfect = count(perfects, person)
            # Un perfecto suma 1 punto, igual que un ganado.
            return (position, person["name"], person["id"],
                    won, lost, perfect, won + perfect)

        for slot in (1, 2):
            guest = data.get("players", {}).get(str(slot))
            if guest:
                phase = guest.get("timer_phase")
                remaining = guest.get("timer_remaining", 0)
                state = (f"BOT {remaining}s" if phase == "bot" else
                         f"START {remaining}s" if phase == "start" else f"ACTIVO {remaining}s")
                row = self.roster.insert("", "end", values=display(f"P{slot} - {state}", guest))
                if guest["id"] > 0:
                    self.member_by_tree_row[row] = guest["id"]
            else:
                self.roster.insert(
                    "", "end",
                    values=(f"P{slot} - DISPONIBLE", "Libre", "", "", "", "", ""))

        waiting = data.get("queue", [])
        for i, guest in enumerate(waiting, 1):
            row = self.roster.insert("", "end",
                                     values=display(f"EN ESPERA {i}", guest))
            self.member_by_tree_row[row] = guest["id"]
        spectators = data.get("spectators", [])
        for guest in spectators:
            row = self.roster.insert("", "end",
                                     values=display("ESPECTADOR", guest))
            self.member_by_tree_row[row] = guest["id"]

        for row, uid in self.member_by_tree_row.items():
            if uid == selected_uid:
                self.roster.selection_set(row)
                self.roster.focus(row)
                break
        if old_scroll:
            self.roster.yview_moveto(old_scroll[0])

        players = data.get("players", {})
        p1 = "ocupado" if players.get("1") else "libre"
        p2 = "ocupado" if players.get("2") else "libre"
        total = data.get("total")
        if total is None:
            total = sum(bool(players.get(str(p))) for p in (1, 2))
            total += len(waiting) + len(spectators)
        self.roster_count_var.set(
            f"{total} conectados  |  P1 {p1}  |  P2 {p2}"
            f"  |  En espera: {len(waiting)}")

    def _start_server(self):
        if self.server is not None:
            self._append("La sala ya está abierta.")
            return
        if sys.platform != "win32":
            self.messagebox.showerror("Windows necesario", "Este MAME y el anfitrión necesitan Windows.")
            return
        try:
            port = int(self.port_var.get().strip())
            if not (1024 <= port <= 65535):
                raise ValueError("Utiliza un puerto entre 1024 y 65535.")
            if self.game_process is not None and self.game_process.poll() is None:
                raise RuntimeError("Cierra MAME antes de abrir una sala nueva: los mandos virtuales deben existir ANTES del juego.")
            device = VirtualPads(lambda: self.game_process, status_notify=self.notify)
            new = HostServer(port, self.notify, device,
                             bind_lan=self.lan_var.get(),
                             process_provider=lambda: self.game_process,
                             restore_state=False,
                             champion_exit_mode=MODE_RESTART)
            new.start()
            self.server = new
            self._append("DOS JOYSTICKS VIRTUALES CREADOS. Verifica en joy.cpl y luego inicia el MAME ANTIGUO desde aquí.")
            self.input_diagnostic_var.set("LISTOS: 2 mandos virtuales. Pulsa VER MANDOS EN WINDOWS y después INICIAR KOF.")
            self.host_url_var.set(f"SOLO LOCAL: ws://127.0.0.1:{port} (publica para jugar por Internet)")
        except Exception as ex:
            self.messagebox.showerror("No se pudo abrir la sala", str(ex))

    def _show_windows_gamepads(self):
        if sys.platform != "win32":
            return
        try:
            subprocess.Popen(["control.exe", "joy.cpl"])
            self._append("Abierto joy.cpl: verifica dos controles Xbox 360 (P1 y P2).")
        except Exception as ex:
            self.messagebox.showerror("No se pueden mostrar los mandos", str(ex))

    def _launch_health_analyzer(self):
        """Abrir herramienta visual de correlación sin consola Python."""
        script = BASE_DIR / "KOF_Analizador_Salud.py"
        if not script.is_file():
            self.messagebox.showwarning(
                "Analizador no encontrado",
                "Coloca KOF_Analizador_Salud.py en la misma carpeta del anfitrión.")
            return
        pythonw = pathlib.Path(sys.executable).with_name("pythonw.exe")
        interpreter = str(pythonw) if pythonw.is_file() else sys.executable
        try:
            subprocess.Popen([interpreter, "-B", str(script)], cwd=str(BASE_DIR),
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self._append("Analizador de salud iniciado: detecta inputs y observa RAM en solo lectura.")
        except OSError as exc:
            self.messagebox.showerror("Analizador de salud", str(exc))

    def _start_tunnel(self):
        if self.server is None:
            self.messagebox.showwarning("Primero abre la sala", "Pulsa 1. ABRIR SALA.")
            return
        if self.tunnel_process is not None and self.tunnel_process.poll() is None:
            self._append("El túnel ya está activo.")
            return
        binary = shutil.which("cloudflared")
        if not binary:
            local = BASE_DIR / ("cloudflared.exe" if os.name == "nt" else "cloudflared")
            if local.is_file():
                binary = str(local)
        if not binary:
            self.messagebox.showinfo("Instalar Cloudflare Tunnel",
                "Instala cloudflared para publicar la sala sin abrir puertos.\n\n"
                "https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/\n\n"
                "También puedes usar: winget install --id Cloudflare.cloudflared\n"
                "o colocar cloudflared.exe junto a KOF_Anfitrion.py.")
            return
        if self.public_address:
            self._api_jobs.put("")
        self.public_address = ""
        self._append("Solicitando enlace público de Cloudflare...")
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            self.tunnel_process = subprocess.Popen(
                [binary, "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{self.server.port}"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                errors="replace", bufsize=1, creationflags=flags)
            threading.Thread(target=self._read_tunnel, args=(self.tunnel_process,), daemon=True).start()
        except Exception as ex:
            self._append("Error de Cloudflare: " + str(ex))

    def _read_tunnel(self, process):
        pattern = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com", re.I)
        found = False
        try:
            for line in process.stdout:
                match = pattern.search(line)
                if match and self.tunnel_process is process:
                    found = True
                    self.notify("public_url", match.group(0))
                elif " ERR " in line or ("error" in line.lower() and "cloudflare" not in line.lower()):
                    self.notify("log", "Túnel: " + line.strip()[:170])
        except Exception as ex:
            self.notify("log", "Error de conexión del túnel: " + str(ex))
        finally:
            if not found and self.tunnel_process is process:
                self.notify("log", "El túnel terminó sin crear URL. Revisa Internet y cloudflared.")
            self.notify("tunnel_closed", process)

    def _choose_mame_lua(self):
        """Seleccionar MAME 0.289 real; no sustituir el ejecutable antiguo."""
        if self.game_process is not None and self.game_process.poll() is None:
            self.messagebox.showwarning(
                "Cierra el juego", "Cierra MAME antes de cambiar de emulador.")
            return
        from tkinter import filedialog
        filename = filedialog.askopenfilename(
            title="Selecciona mame.exe de MAME 0.289 (64 bits)",
            filetypes=[("Ejecutable MAME", "mame*.exe"),
                       ("Programas Windows", "*.exe")])
        if not filename:
            return
        executable = pathlib.Path(filename).resolve()
        try:
            detected = subprocess.run(
                [str(executable), "-version"], cwd=str(executable.parent),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, errors="replace", timeout=8,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            description = detected.stdout.strip()
            if detected.returncode != 0 or re.search(r"\\b0\\.289\\b", description) is None:
                raise ValueError(
                    f"El ejecutable no parece MAME 0.289. Respuesta: {description[:160]}")
            if LuaHealthMonitor is None:
                raise RuntimeError(
                    "Falta KOF_MAME_Lua_Bridge.py junto al anfitrión.")
            script = BASE_DIR / "KOF_Salud_MAME289.lua"
            if not script.is_file():
                raise FileNotFoundError(
                    "Falta KOF_Salud_MAME289.lua junto al anfitrión.")
        except (OSError, ValueError, RuntimeError) as exc:
            self.messagebox.showerror("MAME 0.289", str(exc))
            return
        self.lua_mame_exe = executable
        self.mame_choice_var.set("Lua: " + executable.name + " (" + str(executable.parent) + ")")
        self.lua_health_var.set(
            "VIDA P1: --  |  VIDA P2: --  |  inicia el juego para leer Lua")
        self._append("Seleccionado MAME 0.289, sin tocar tu MAME 0.132. "
                     "Se activará el monitor Lua al INICIAR KOF.")

    def _use_legacy_mame(self):
        if self.game_process is not None and self.game_process.poll() is None:
            self.messagebox.showwarning(
                "Cierra el juego", "Cierra MAME antes de cambiar de emulador.")
            return
        self.lua_mame_exe = None
        self.mame_choice_var.set("Emulador: MAME 0.132 original")
        self.lua_health_var.set("VIDA P1: --  |  VIDA P2: --  |  Lua desactivado")
        self._append("Volviste al MAME 0.132 original sin alterar ROM ni mandos.")

    def _start_game(self):
        if sys.platform != "win32":
            self.messagebox.showerror("Windows necesario", "mame.exe solo se ejecuta en Windows.")
            return
        if self.game_process is not None and self.game_process.poll() is None:
            self._append("MAME ya está ejecutándose. Si cambiaste el modo de mando, cierra MAME y vuelve a iniciarlo.")
            return
        if self.server is None or not isinstance(self.server.room.input, VirtualPads):
            self.messagebox.showwarning("Primero abre la sala",
                "Para que MAME reconozca ambos controles, pulsa primero ABRIR SALA "
                "con 2 joysticks virtuales y DESPUES INICIAR KOF.")
            return
        self._append("Buscando o extrayendo KOF2022GAME.zip original ...")
        threading.Thread(target=self._game_worker, daemon=True).start()

    def _game_worker(self):
        try:
            chosen_exe = self.lua_mame_exe
            if chosen_exe is None:
                # Ruta antigua probada: no modificar comportamiento de MAME 0.132.
                directory = get_game_folder()
                command = [str(directory / "mame.exe"), "kf2k2mp2",
                           "-window", "-maximize",
                           "-state_directory", str(directory / STATE_FOLDER)]
                profile = create_mame_virtual_profile(directory)
                command.extend(["-ctrlr", profile.stem])
                self.notify("log",
                            "MAME 0.132 del ZIP. Perfil de 2 joysticks: "
                            "ctrlr/" + profile.name)
                if self.lua_monitor is not None:
                    self.lua_monitor.stop()
                    self.lua_monitor = None
                self.game_process = subprocess.Popen(
                    command, cwd=str(directory))
                if os.environ.get("KOF_ENABLE_OCR_RESULTS") == "1":
                    self._start_auto_results(self.game_process, self.server)
                else:
                    self.notify("log",
                                "OCR desactivado: los inputs NO suman puntuación.")
                self.notify("log",
                            f"MAME 0.132 iniciado, PID {self.game_process.pid}.")
                return

            if LuaHealthMonitor is None:
                raise RuntimeError(
                    "Falta KOF_MAME_Lua_Bridge.py en la carpeta del anfitrión.")
            script = BASE_DIR / "KOF_Salud_MAME289.lua"
            if not script.is_file():
                raise FileNotFoundError(
                    "Falta el script KOF_Salud_MAME289.lua en el anfitrión.")
            if not chosen_exe.is_file():
                raise FileNotFoundError(
                    f"El ejecutable seleccionado ya no existe: {chosen_exe}")

            # Preferir las ROM del proyecto; permitir también el directorio
            # independiente con el que el usuario ya abrió MAME 0.289.
            try:
                directory = get_game_folder()
            except FileNotFoundError:
                own = chosen_exe.parent
                if ((own / "kf2k2mp2.zip").is_file() or
                        (own / "roms" / "kf2k2mp2.zip").is_file()):
                    directory = own
                else:
                    raise FileNotFoundError(
                        "No se encontró kf2k2mp2.zip. Coloca la ROM en "
                        "KOF2022GAME o en la carpeta roms del MAME 0.289.")

            if self.lua_monitor is not None:
                self.lua_monitor.stop()
                self.lua_monitor = None
            self.lua_state_path.parent.mkdir(parents=True, exist_ok=True)
            # Nunca consumir datos de una partida o PID anterior.
            try:
                self.lua_state_path.unlink()
            except FileNotFoundError:
                pass

            # Los save states del MAME antiguo NO deben abrirse en el nuevo.
            modern_state_dir = directory / "KOF_ARENA_ESTADOS_0289"
            modern_state_dir.mkdir(parents=True, exist_ok=True)
            profile = create_mame_virtual_profile(directory)
            rom_paths = list(dict.fromkeys((
                str(directory), str(directory / "roms"),
                str(chosen_exe.parent / "roms"),
                str(chosen_exe.parent))))
            command = [str(chosen_exe), "kf2k2mp2", "-window", "-maximize",
                       "-rompath", os.pathsep.join(rom_paths),
                       "-state_directory", str(modern_state_dir),
                       "-ctrlrpath", str(profile.parent),
                       "-ctrlr", profile.stem,
                       "-joystick", "-autoboot_script", str(script)]
            env = os.environ.copy()
            env["KOF_ARENA_LUA_STATE"] = str(self.lua_state_path)
            self.notify("log",
                        "Iniciando MAME 0.289 con Lua y dos joysticks "
                        "virtuales; marcador automático sigue desactivado.")
            self.game_process = subprocess.Popen(
                command, cwd=str(chosen_exe.parent), env=env)
            self.lua_monitor = LuaHealthMonitor(
                process=self.game_process,
                file_path=self.lua_state_path,
                notify=self.notify)
            self.lua_monitor.start()
            self.notify("log",
                        f"MAME 0.289 iniciado PID {self.game_process.pid}. "
                        "Lectura Neo Geo P1 0x108239 / P2 0x108439, "
                        "sin modificación de RAM.")
        except Exception as ex:
            self.notify("log", "No se pudo abrir KOF: " + str(ex))

    def _start_auto_results(self, process, server):
        if self.auto_monitor is not None:
            self.auto_monitor.stop()
            self.auto_monitor = None
        if AutoResultMonitor is None:
            self.notify("log",
                        "AUTO MARCADOR NO ACTIVO: falta KOF_AutoResultados.py junto al anfitrión.")
            return
        if server is None:
            return
        self.auto_monitor = AutoResultMonitor(
            process=process, server=server,
            notify=self.notify, base_dir=BASE_DIR)
        self.auto_monitor.start()

    def _resync_api(self):
        if not self.public_address:
            self.messagebox.showwarning("Falta enlace público", "Publica primero la sala con Cloudflare.")
            return
        self._api_jobs.put(self.public_address)
        self.api_status_var.set("API: reenviando enlace público...")

    def _copy_join(self):
        if not self.public_address:
            self.messagebox.showinfo("Falta enlace público",
                "Publica primero la sala en Internet. Para una conexión local puedes usar ws://IP:PUERTO.")
            return
        data = (f"KOF ARENA - ENLACE DE SALA\n"
                f"Enlace: {self.public_address}\n\n"
                f"Abre KOF_Control_Remoto.py, introduce este enlace y tu nombre."
                f" No se requiere contraseña.")
        self.root.clipboard_clear()
        self.root.clipboard_append(data)
        self.root.update_idletasks()
        self._append("Enlace copiado. Cualquier persona que lo tenga puede entrar a la sala.")

    def _stop_server(self):
        if self.lua_monitor is not None:
            self.lua_monitor.stop()
            self.lua_monitor = None
        if self.auto_monitor is not None:
            self.auto_monitor.stop()
            self.auto_monitor = None
        if self.public_address:
            self._api_jobs.put("")
            self.api_status_var.set("API: despublicando enlace...")
        if self.tunnel_process is not None:
            try:
                self.tunnel_process.terminate()
            except Exception:
                pass
            self.tunnel_process = None
        self.public_address = ""
        if self.server is not None:
            old = self.server
            self.server = None
            threading.Thread(target=old.stop, daemon=True).start()
        self.host_url_var.set("Sala cerrada. Abre una nueva sala para recibir jugadores.")
        self._show_roster({"players": {"1": None, "2": None}, "queue": [], "spectators": []})

    def _kick_selected(self):
        if not self.server:
            return
        selected = self.roster.selection()
        if selected:
            uid = self.member_by_tree_row.get(selected[0])
            if uid:
                self.server.kick(uid)

    def _close(self):
        try:
            self.root.after_cancel(self._poll_job)
        except Exception:
            pass
        self._stop_server()
        self._api_jobs.put(None)
        self.root.destroy()

    def mainloop(self):
        self.root.mainloop()


def main():
    if "--selftest" in sys.argv:
        run_selftest()
        return
    if sys.platform != "win32":
        print("La versión anfitrión requiere Windows para ejecutar MAME.")
        return
    if ws_serve is None:
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk(); root.withdraw()
            messagebox.showerror("Instala dependencias",
                "Ejecuta INSTALAR_ANFITRION.bat o: py -m pip install websockets vgamepad")
            root.destroy()
        except Exception:
            print("Instala: websockets, vgamepad")
        return
    HostGUI().mainloop()


def run_selftest():
    """Comprueba asignación P1/P2, lista FIFO y liberación automática."""
    # Un resultado confirmado por el juego registra ambos lados y PERFECT;
    # los datos nunca cambian por pulsaciones ni por editarlos desde la tabla.
    simulator = HostServer.__new__(HostServer)
    simulator.room = Room(NullInput())
    player_1 = simulator.room.register("Test P1")
    player_2 = simulator.room.register("Test P2")
    player_1.start_pressed = True
    player_2.start_pressed = True
    simulator.scores = {}
    simulator.losses = {}
    simulator.perfects = {}
    simulator.last_winner_uid = None
    simulator.last_winner_name = ""
    simulator.ui_notify = lambda *_args: None
    simulator._broadcast_state = lambda: None
    pair = (player_1.uid, player_2.uid)
    assert simulator.record_game_outcome(1, True, pair)
    assert simulator.scores[player_1.uid] == 1
    assert simulator.losses[player_2.uid] == 1
    assert simulator.perfects[player_1.uid] == 1
    assert simulator.scores[player_1.uid] + simulator.perfects[player_1.uid] == 2
    assert not simulator.record_game_outcome(1, False, (player_1.uid, 999))
    assert simulator.scores[player_1.uid] == 1

    mock = NullInput()
    room = Room(mock)
    a, b, c, d = [room.register(n) for n in ("Ana", "Beto", "Cata", "Dani")]
    assert (a.slot, b.slot, c.slot, d.slot) == (1, 2, 0, 0)
    assert [p["name"] for p in room.snapshot()["queue"]] == ["Cata", "Dani"]
    assert room.input_event(a.uid, "UP", True)
    assert mock.events[-1] == (1, "UP", True)
    room.remove(a.uid)
    assert c.slot == 1
    room.remove(b.uid)
    assert d.slot == 2
    assert room.yield_slot(c.uid)
    assert room.request_slot(c.uid) and c.slot == 1

    clock = [100.0]
    rules = Room(NullInput(), clock=lambda: clock[0])
    one, two, next_one = [rules.register(n) for n in ("1", "2", "siguiente")]
    clock[0] = 105.0
    assert rules.input_event(two.uid, "START", True)
    clock[0] = 120.0
    assert [x[0] for x in rules.check_timeouts()] == ["warning_start"]
    clock[0] = 130.0
    assert [x[0] for x in rules.check_timeouts()] == ["expired_start"]
    assert one.slot == 0 and next_one.slot == 1
    clock[0] = 155.0
    assert [x[0] for x in rules.check_timeouts()] == ["warning_idle", "warning_start"]
    clock[0] = 156.0
    assert rules.input_event(two.uid, "UP", True)
    clock[0] = 159.0
    assert rules.input_event(next_one.uid, "START", True)
    clock[0] = 209.0
    assert [x[0] for x in rules.check_timeouts()] == ["warning_idle", "warning_idle"]
    clock[0] = 216.0
    assert [x[0] for x in rules.check_timeouts()] == ["expired_idle"]
    assert two.slot == 0
    for action in SINGLE_ACTIONS:
        assert MameKeyboard.game_key(1, action) == MameKeyboard.P1_KEYS[action]
        assert MameKeyboard.game_key(2, action) == MameKeyboard.P2_KEYS[action]
    for action, wanted in {"UP": "R", "DOWN": "F", "LEFT": "D", "RIGHT": "G",
                           "A": "A", "B": "S", "C": "Q", "D": "W",
                           "START": "2", "COIN": "6"}.items():
        assert MameKeyboard.game_key(2, action) == wanted

    sim = NullInput()
    same_controls = Room(sim)
    first = same_controls.register("mando P1")
    second = same_controls.register("mando P1 de otro equipo")
    for guest in (first, second):
        for action in ("UP", "A", "START", "COIN"):
            assert same_controls.input_event(guest.uid, action, True)
            assert sim.events[-1] == (guest.slot, action, True)
            assert MameKeyboard.game_key(guest.slot, action) == MameKeyboard.MAP[guest.slot][action]
            assert same_controls.input_event(guest.uid, action, False)

    # A single COIN_START event produces one coin followed by one start.
    # The server's slot, not the client's keyboard, decides 5/1 or 6/2.
    import unittest.mock as mock_mod
    fast_delay = mock_mod.patch(__name__ + ".time.sleep", lambda _seconds: None)
    with fast_delay:
        for expected_slot in (1, 2):
            record = NullInput()
            combo_room = Room(record)
            if expected_slot == 2:
                combo_room.register("reserved P1")
            guest = combo_room.register("combo")
            assert guest.slot == expected_slot
            assert combo_room.input_event(guest.uid, "COIN_START", True)
            assert combo_room.input_event(guest.uid, "COIN_START", False)
            import time as _time
            end = _time.monotonic() + 1.5
            while guest.combo_running and _time.monotonic() < end:
                threading.Event().wait(0.001)
            assert not guest.combo_running, "Combo did not finish"
            events = [event for event in record.events if event[1] in ("COIN", "START")]
            assert events == [(expected_slot, "COIN", True),
                              (expected_slot, "COIN", False),
                              (expected_slot, "START", True),
                              (expected_slot, "START", False),
                              (expected_slot, "COIN", False),
                              (expected_slot, "START", False)], events
            assert guest.start_pressed
            assert MameKeyboard.game_key(expected_slot, "COIN") == ("5" if expected_slot == 1 else "6")
            assert MameKeyboard.game_key(expected_slot, "START") == ("1" if expected_slot == 1 else "2")
    assert VirtualPads.axes({"RIGHT", "UP"}) == (32767, 32767)
    assert VirtualPads.axes({"LEFT", "DOWN"}) == (-32767, -32767)
    assert VirtualPads.axes({"LEFT", "RIGHT"}) == (0, 0)
    from tempfile import TemporaryDirectory
    from xml.etree import ElementTree
    with TemporaryDirectory() as tmp:
        profile = create_mame_virtual_profile(pathlib.Path(tmp))
        root = ElementTree.parse(profile).getroot()
        ports = {node.attrib["type"]: node.findtext("newseq") for node in root.findall("./system/input/port")}
        assert len(ports) == 20, len(ports)
        assert "JOYCODE_1_BUTTON1" in ports["P1_BUTTON1"]
        assert "JOYCODE_2_BUTTON4" in ports["P2_BUTTON4"]
        assert "JOYCODE_1_BUTTON7" in ports["COIN1"]
        assert "JOYCODE_2_BUTTON8" in ports["START2"]
        assert "JOYCODE_2_YAXIS_UP_SWITCH" in ports["P2_JOYSTICK_UP"]
    print("OK: mandos Xbox virtuales, XML MAME 0.132, ASZX, cola y ENTER=COIN+START.")


if __name__ == "__main__":
    main()
