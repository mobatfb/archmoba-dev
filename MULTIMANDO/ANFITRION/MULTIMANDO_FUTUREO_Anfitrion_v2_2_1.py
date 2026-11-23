#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MULTIMANDO: anfitrion para 1-8 joysticks HID genericos vJoy.

Compatible con la palanca PHP v6.0: WASD/UIOJKL en el navegador,
comandos WebSocket ar/ab/iz/de, button_a/button_b/button_x/button_y/button_lb/button_rb, start/select.

Regla: 600 segundos de juego POR JUGADOR, consumidos unicamente mientras
exista al menos un jugador en espera. Sin cola, el reloj se pausa sin reset.
Al agotar el turno, el jugador pasa AL FINAL de la cola FIFO y se entrega
su mando al primer jugador que ya estaba esperando. El servidor es la unica
fuente de verdad; el cliente solo envia pulsaciones.

No necesita KOF, MAME, ROMs, cuenta del usuario ni acceso al escritorio.
No transmite pantalla o audio ni ejecuta instrucciones arbitrarias recibidas.
Windows: instala automaticamente websockets, pyvjoystick, pygame y cloudflared si faltan.
El driver vJoy se instala aparte y sus dispositivos 1-8 se configuran en Configure vJoy.
Pruebas sin hardware: python MULTIMANDO_Anfitrion.py --selftest
"""
from __future__ import annotations

import collections
import ctypes
import json
import math
import os
import pathlib
import queue
import re
import secrets
import hmac
import importlib
import importlib.util
import shutil
import subprocess
import sys
import threading
import time
import unicodedata
from dataclasses import dataclass, field
from typing import Callable, Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

VERSION = "2.2.1"
from futureo_stream_v22 import FrameHub, ScreenBroadcaster, list_sources, stream_selftest
BASE_DIR = pathlib.Path(__file__).resolve().parent
DEFAULT_PORT = 8766  # No interfiere con el puerto 8765 de KOFMULTI.
DEFAULT_SECONDS = 600
COUNTDOWN_SECONDS = 3.0  # Aviso 3, 2, 1 antes de permitir la primera pulsacion.
ACTIVATION_SECONDS = 10.0  # Diez segundos para activar despues del 3, 2, 1.
MAX_NAME_CHARS = 10  # Mismo limite estricto que la web.
RECONNECT_GRACE_SECONDS = 35.0  # Reserva de identidad y mando tras perder el socket.
INPUT_WATCHDOG_SECONDS = 6.0  # Soltar el mando si el heartbeat del navegador deja de llegar.
MAX_GUESTS = 64
MAX_PLAYERS = 8
DEFAULT_PLAYERS = 2
MAX_MESSAGES_PER_SECOND = 100
# La GUI del anfitrion sigue usando el estado completo EN MEMORIA.
# A cada navegador se envia solamente su posicion y reloj, bajo demanda.
STATE_RESYNC_ACTIVE = 10.0  # Reajuste del reloj local cada 10 segundos.
STATE_RESYNC_PAUSED = 60.0  # Sin cola, no enviar estados continuamente.
API_POST = "https://api.isupol.edu.ec/api/posturlmultimando"
API_GET = "https://api.isupol.edu.ec/api/geturlmultimando"
ACTIONS = frozenset(("ar", "ab", "iz", "de", "button_a", "button_b", "button_x", "button_y", "button_lb", "button_rb", "start", "select"))
DIRECTIONS = frozenset(("ar", "ab", "iz", "de"))
URL_REGEX = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com", re.I)
# Protocolo de entradas: un caracter para la accion + 1/0 (presionar/soltar).
# El cliente nunca envía puesto o identidad en estos paquetes: lo define el socket.
WIRE_CODES = {
    "u": "ar", "d": "ab", "i": "iz", "e": "de",
    "x": "button_x", "y": "button_y", "l": "button_lb",
    "a": "button_a", "b": "button_b", "r": "button_rb",
    "t": "start", "s": "select",
}
# Dependencias de usuario; el controlador de kernel vJoy se instala aparte.
PYTHON_DEPS = (("websockets", "websockets"), ("pygame", "pygame"), ("mss", "mss"), ("PIL", "Pillow"))
WINGET_CLOUDFLARED = "Cloudflare.cloudflared"
CLOUDFLARED_RELEASE = "https://github.com/cloudflare/cloudflared/releases/latest/download/"


def missing_python_dependencies() -> list[str]:
    """Detecta bibliotecas faltantes sin importar el driver vJoy."""
    missing = [package for module, package in PYTHON_DEPS
               if importlib.util.find_spec(module) is None]
    if "websockets" not in missing:
        try:
            importlib.import_module("websockets.sync.server")
        except (ImportError, ModuleNotFoundError):
            missing.append("websockets")  # Version antigua sin API sync.
    return missing


def ensure_python_dependencies(report: Callable[[str], None] = print) -> None:
    """Instala solo dependencias faltantes con el mismo interprete del .py."""
    packages = missing_python_dependencies()
    if not packages:
        report("[MULTIMANDO] Dependencias Python listas; no es necesario instalar.")
        return
    report("[MULTIMANDO] Instalando automaticamente: " + ", ".join(packages))
    if importlib.util.find_spec("pip") is None:
        report("[MULTIMANDO] pip no encontrado; activando ensurepip...")
        cmd = [sys.executable, "-m", "ensurepip", "--upgrade"]
        result = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=180)
        if result.returncode != 0:
            raise RuntimeError("No se pudo habilitar pip: " + (result.stderr or result.stdout)[-700:])
        importlib.invalidate_caches()
    # No se actualiza pip en cada arranque; solo se instala lo que falta.
    cmd = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
           "--no-input", "--prefer-binary", *packages]
    result = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=480)
    if result.returncode != 0:
        raise RuntimeError("La instalacion automatica de bibliotecas fallo.\n" +
                           (result.stderr or result.stdout)[-1200:] +
                           "\nReintenta manualmente: " + " ".join(cmd))
    # pip --user puede crear el directorio de usuario despues del arranque.
    import site
    user_site = site.getusersitepackages()
    if pathlib.Path(user_site).is_dir() and user_site not in sys.path:
        site.addsitedir(user_site)
    importlib.invalidate_caches()
    remaining = missing_python_dependencies()
    if remaining:
        raise RuntimeError("Se instalo el paquete pero Python no lo detecta: " +
                           ", ".join(remaining) + ". Reinicia el programa.")
    report("[MULTIMANDO] Instalacion Python terminada correctamente.")


def find_cloudflared() -> str | None:
    """Resuelve el ejecutable en PATH, junto al .py o en rutas de WinGet."""
    candidates: list[str | pathlib.Path | None] = [
        BASE_DIR / "cloudflared.exe", shutil.which("cloudflared")]
    appdata = os.environ.get("LOCALAPPDATA", "")
    if appdata:
        app = pathlib.Path(appdata)
        candidates.extend((app / "MULTIMANDO" / "bin" / "cloudflared.exe",
                           app / "Microsoft" / "WinGet" / "Links" / "cloudflared.exe"))
    for env in ("ProgramFiles", "ProgramFiles(x86)"):
        root = os.environ.get(env, "")
        if root:
            candidates.extend((pathlib.Path(root) / "cloudflared" / "cloudflared.exe",
                               pathlib.Path(root) / "Cloudflare" / "cloudflared.exe"))
    for path in candidates:
        if path and pathlib.Path(path).is_file():
            return str(pathlib.Path(path).resolve())
    return None


def _winget_path() -> str | None:
    found = shutil.which("winget")
    if found:
        return found
    local = os.environ.get("LOCALAPPDATA", "")
    possible = pathlib.Path(local) / "Microsoft" / "WindowsApps" / "winget.exe" if local else None
    return str(possible) if possible and possible.is_file() else None


def _download_official_cloudflared(report: Callable[[str], None]) -> str:
    """Alternativa portable oficial: evita depender de winget o de PATH."""
    local = os.environ.get("LOCALAPPDATA")
    # Con una carpeta de programa de solo lectura, LOCALAPPDATA es escribible.
    base = pathlib.Path(local) / "MULTIMANDO" / "bin" if local else BASE_DIR
    base.mkdir(parents=True, exist_ok=True)
    target = base / "cloudflared.exe"
    temp = base / "cloudflared_download.exe"
    architecture = "amd64" if sys.maxsize > 2**32 else "386"
    url = CLOUDFLARED_RELEASE + f"cloudflared-windows-{architecture}.exe"
    report("[MULTIMANDO] Descargando cloudflared desde Cloudflare/GitHub oficial...")
    try:
        request = Request(url, headers={"User-Agent": f"MULTIMANDO/{VERSION}"})
        with urlopen(request, timeout=60) as response:
            resolved = urlsplit(response.geturl())
            if resolved.scheme != "https" or resolved.hostname not in (
                "github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com"):
                raise RuntimeError("La descarga se redirigio a un sitio no autorizado")
            size = 0
            with temp.open("wb") as fh:
                while True:
                    block = response.read(1024 * 256)
                    if not block:
                        break
                    size += len(block)
                    if size > 140 * 1024 * 1024:
                        raise RuntimeError("El instalador supera el tamano esperado")
                    fh.write(block)
        with temp.open("rb") as fh:
            if size < 2 * 1024 * 1024 or fh.read(2) != b"MZ":
                raise RuntimeError("El archivo descargado no es un ejecutable valido")
        verify = subprocess.run([str(temp), "--version"], capture_output=True,
                                text=True, errors="replace", timeout=20)
        if verify.returncode != 0 or "cloudflared" not in verify.stdout.lower():
            raise RuntimeError("Cloudflared descargado no paso la validacion de version")
        temp.replace(target)
        return str(target)
    except BaseException:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def ensure_cloudflared(report: Callable[[str], None] = print) -> str:
    """Instala cloudflared solo cuando se solicita publicar en Internet."""
    current = find_cloudflared()
    if current:
        report("[MULTIMANDO] Cloudflare Tunnel ya instalado: " + current)
        return current
    winget = _winget_path()
    if winget:
        report("[MULTIMANDO] Cloudflare no encontrado. Instalando con winget...")
        command = [winget, "install", "-e", "--id", WINGET_CLOUDFLARED,
                   "--silent", "--accept-package-agreements", "--accept-source-agreements"]
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            result = subprocess.run(command, capture_output=True, text=True,
                                    errors="replace", timeout=420, creationflags=flags)
            current = find_cloudflared()
            if current:
                report("[MULTIMANDO] Instalado por winget correctamente.")
                return current
            report("[MULTIMANDO] winget no dejo una ruta ejecutable visible; probando descarga oficial.")
            if result.returncode:
                report("[MULTIMANDO] winget: " + (result.stderr or result.stdout)[-350:])
        except (OSError, subprocess.TimeoutExpired) as exc:
            report("[MULTIMANDO] winget no disponible ahora: " + str(exc)[:120])
    else:
        report("[MULTIMANDO] winget no esta disponible. Uso de descarga oficial portable.")
    try:
        return _download_official_cloudflared(report)
    except (OSError, RuntimeError, URLError, HTTPError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("No se pudo instalar cloudflared automaticamente: " + str(exc) +
                           "\nInstalacion manual: winget install -e --id Cloudflare.cloudflared") from exc


LEGACY_INPUT_ACTIONS = {
    "ba": "button_a", "bb": "button_b", "bc": "button_x",
    "bd": "button_y", "be": "button_lb", "bf": "button_rb",
}


def decode_input(raw: str) -> tuple[str, bool] | None:
    """Recibe exactamente 2 caracteres ASCII; JSON antiguo solo para transición.

    No acepta comandos de administración ni códigos desconocidos.
    """
    if not isinstance(raw, str):
        return None
    if len(raw) == 2 and raw[1] in ("0", "1"):
        action = WIRE_CODES.get(raw[0])
        return (action, raw[1] == "1") if action else None
    # Compatibilidad temporal: navegadores con HTML anterior aún cacheado.
    if 0 < len(raw) <= 256 and raw.startswith("{"):
        try:
            msg = json.loads(raw)
        except (ValueError, TypeError):
            return None
        if isinstance(msg, dict) and msg.get("type") == "input":
            action, down = msg.get("action"), msg.get("down")
            if type(action) is str and type(down) is bool:
                action = LEGACY_INPUT_ACTIONS.get(action, action)
                if action in ACTIONS:
                    return action, down
    return None

# Nombres visibles del boton. El host registra la accion LOGICA,
# no la tecla fisica que el usuario haya personalizado en el navegador.
INPUT_NAMES = {
    "ar": "ARRIBA", "ab": "ABAJO", "iz": "IZQUIERDA", "de": "DERECHA",
    "button_x": "X", "button_y": "Y", "button_lb": "L",
    "button_a": "A", "button_b": "B", "button_rb": "R",
    "start": "START", "select": "SELECT",
}



def compact(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def valid_public_url(value: str) -> str:
    """Solo Quick Tunnel HTTPS/WSS, sin parametros ni destinos arbitrarios."""
    value = str(value or "").strip()
    if not value:
        return ""
    parsed = urlsplit(value)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in ("https", "wss") or not re.fullmatch(
            r"[a-z0-9-]+\.trycloudflare\.com", host):
        raise ValueError("URL de Cloudflare no permitida")
    if parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError("El enlace no debe contener usuario ni puerto")
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ValueError("El enlace debe contener solo el dominio Cloudflare")
    return "https://" + host


def publish_url(value: str, timeout: float = 9.0) -> dict:
    """Actualiza la URL de MULTIMANDO, nunca la de KOFMULTI."""
    cleaned = valid_public_url(value)
    request = Request(API_POST, data=compact({"url": cleaned}).encode("utf-8"),
                      method="POST", headers={
                          "Accept": "application/json",
                          "Content-Type": "application/json",
                          "User-Agent": "MULTIMANDO-Anfitrion/" + VERSION,
                      })
    with urlopen(request, timeout=timeout) as response:
        result = json.load(response)
    if not isinstance(result, dict) or result.get("status") != "success":
        raise RuntimeError("La API POST no confirmo la publicacion")
    return result


def get_published_url(timeout: float = 8.0) -> str:
    request = Request(API_GET, headers={
        "Accept": "application/json", "Cache-Control": "no-store",
        "User-Agent": "MULTIMANDO-Anfitrion/" + VERSION,
    })
    with urlopen(request, timeout=timeout) as response:
        result = json.load(response)
    if not isinstance(result, dict) or result.get("status") != "success":
        raise RuntimeError("La API GET respondio sin exito")
    source = result.get("data") if isinstance(result.get("data"), dict) else result
    raw = source.get("url") or source.get("email") or result.get("url") or ""
    return valid_public_url(raw)


def canonical_name(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split()).casefold()


@dataclass
class Guest:
    uid: int
    name: str
    socket: Any = None
    slot: int = 0
    queued: bool = False
    remaining: float = float(DEFAULT_SECONDS)
    last_tick: float = 0.0
    active: bool = True
    held: set[str] = field(default_factory=set)
    direction_mode: str = "legacy"  # Clientes anteriores siguen funcionando.
    input_times: collections.deque = field(default_factory=collections.deque)
    outbound: queue.Queue = field(default_factory=lambda: queue.Queue(maxsize=32))
    wake: threading.Event = field(default_factory=threading.Event)
    warned_last_minute: bool = False
    resume_token: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    disconnected_at: float | None = None
    disconnect_timer: threading.Timer | None = None
    heartbeat_enabled: bool = False
    last_heartbeat: float = 0.0
    input_suspended: bool = False
    activation_deadline: float | None = None  # 10 segundos para confirmar entrada.
    countdown_deadline: float | None = None  # Primeros 3 segundos sin permitir entradas.
    turn_credit: float | None = None  # Tiempo conservado al reducir la capacidad.

    def tell(self, data: Any) -> None:
        self.tell_raw(compact(data))

    def tell_raw(self, payload: str) -> None:
        try:
            self.outbound.put_nowait(payload)
        except queue.Full:
            # Si el navegador lee lento, descartar estados viejos antes de crecer.
            try:
                self.outbound.get_nowait()
                self.outbound.put_nowait(payload)
            except queue.Empty:
                pass
            except queue.Full:
                pass
        self.wake.set()


class DummyPads:
    """Dispositivo inerte para --selftest; nunca se usa en salas publicas."""
    def __init__(self, count: int = DEFAULT_PLAYERS):
        if not (1 <= count <= MAX_PLAYERS):
            raise ValueError('El numero de mandos debe estar entre 1 y 8')
        self.count = count
        self.events: list[tuple[int, str, bool]] = []
        self.held = {slot: set() for slot in range(1, count + 1)}
        self.mode: dict[int, str] = {slot: 'legacy' for slot in range(1, count + 1)}
        self.analog_axes: dict[int, tuple[int, int]] = {slot: (0, 0) for slot in range(1, count + 1)}
        self.analog_events: list[tuple[int, int, int]] = []

    def resize(self, count: int) -> bool:
        if not 1 <= count <= MAX_PLAYERS:
            raise ValueError('La capacidad debe estar entre 1 y 8')
        old = self.count
        if count < old:
            for slot in range(count + 1, old + 1):
                self.held.pop(slot, None)
                self.mode.pop(slot, None)
                self.analog_axes.pop(slot, None)
        elif count > old:
            for slot in range(old + 1, count + 1):
                self.held[slot] = set()
                self.mode[slot] = 'legacy'
                self.analog_axes[slot] = (0, 0)
        self.count = count
        return True

    def set_mode(self, slot: int, mode: str) -> bool:
        if slot not in self.held or mode not in ('legacy', 'analog', 'dpad'): return False
        self.mode[slot] = mode
        self.analog_axes[slot] = (0, 0)
        self.held[slot].difference_update(DIRECTIONS)
        return True

    def analog(self, slot: int, x: int, y: int) -> bool:
        if slot not in self.held or self.mode[slot] != 'analog': return False
        if type(x) is not int or type(y) is not int or not (-127 <= x <= 127 and -127 <= y <= 127): return False
        self.analog_axes[slot] = (x, y)
        self.analog_events.append((slot, x, y))
        return True

    def apply(self, slot: int, action: str, down: bool) -> bool:
        if slot not in self.held or action not in ACTIONS:
            return False
        self.events.append((slot, action, down))
        if down:
            self.held[slot].add(action)
        else:
            self.held[slot].discard(action)
        return True

    def release_slot(self, slot: int) -> None:
        self.held[slot].clear()
        self.analog_axes[slot] = (0, 0)

    def identify(self, slot: int, duration: float = 0.28) -> bool:
        if slot not in self.held:
            return False
        self.release_slot(slot)
        self.events.append((slot, 'identify_button_8', True))
        self.events.append((slot, 'identify_button_8', False))
        return True

    def close(self) -> None:
        for slot in range(1, self.count + 1):
            self.release_slot(slot)


class VirtualVJoyPads:
    """1-8 joysticks HID/DirectInput vJoy, con etiqueta local VJOY1..VJOY8.

    El controlador vJoy expone sus nombres propios a Windows; estas etiquetas
    son identificadores de MULTIMANDO, NO un renombrado PnP del driver.
    """
    BUTTONS = {
        'button_a': 1, 'button_b': 2, 'button_x': 3, 'button_y': 4,
        'button_lb': 5, 'button_rb': 6, 'start': 7, 'select': 8,
    }
    MIN_TAP_SECONDS = 0.095
    HAT_DIRECTIONS = {
        (0, 1): 0, (1, 1): 4500, (1, 0): 9000, (1, -1): 13500,
        (0, -1): 18000, (-1, -1): 22500, (-1, 0): 27000, (-1, 1): 31500,
    }

    @staticmethod
    def axes(actions: set[str]) -> tuple[int, int]:
        return (int('de' in actions) - int('iz' in actions),
                int('ar' in actions) - int('ab' in actions))

    def __init__(self, count: int = DEFAULT_PLAYERS):
        if sys.platform != 'win32':
            raise RuntimeError('Los joysticks virtuales vJoy requieren Windows')
        if not 1 <= count <= MAX_PLAYERS:
            raise ValueError('Elige entre 1 y 8 joysticks')
        try:
            import pyvjoystick.vjoy as vjoy
        except (ImportError, OSError, SystemExit) as exc:
            raise RuntimeError('Instala pyvjoystick y el controlador vJoy. '
                               'Comando: py -m pip install websockets pyvjoystick') from exc
        self.vjoy = vjoy
        self.count = count
        self.lock = threading.RLock()
        self.pads = []
        self.held: dict[int, set[str]] = {n: set() for n in range(1, count + 1)}
        self.mode: dict[int, str] = {n: 'legacy' for n in range(1, count + 1)}
        self.analog_axes: dict[int, tuple[int, int]] = {n: (0, 0) for n in range(1, count + 1)}
        self.pressed_at: dict[tuple[int, str], float] = {}
        self.release_timers: dict[tuple[int, str], threading.Timer] = {}
        self.hat_enabled: dict[int, bool] = {}
        try:
            for slot in range(1, count + 1):
                try:
                    dev = vjoy.VJoyDevice(slot)
                except (Exception, SystemExit) as exc:
                    raise RuntimeError(f'No se pudo adquirir VJOY{slot}. Configura el '
                                       f'Device {slot} en Configure vJoy; verifica que '
                                       'no este ocupado por otro programa. '
                                       f'Detalle: {exc}') from exc
                self.pads.append(dev)
                if int(dev.number_of_buttons) < 8:
                    raise RuntimeError(f'VJOY{slot}: configura al menos 8 botones en Configure vJoy')
                if vjoy.HID_USAGE.X not in dev.available_axis or vjoy.HID_USAGE.Y not in dev.available_axis:
                    raise RuntimeError(f'VJOY{slot}: habilita los ejes X e Y en Configure vJoy')
                from pyvjoystick.vjoy import _sdk
                self.hat_enabled[slot] = _sdk.GetVJDContPovNumber(slot) >= 1
                self.release_slot(slot)
        except BaseException:
            self.close()
            raise

    def _cancel_timer(self, key: tuple[int, str]) -> None:
        timer = self.release_timers.pop(key, None)
        if timer is not None:
            timer.cancel()

    @staticmethod
    def _axis_value(dev: Any, axis: Any, normalized: float) -> int:
        limits = dev.axis_limits[axis]
        center = limits.mean
        span = (limits.maxValue - center) if normalized >= 0 else (center - limits.minValue)
        return max(limits.minValue, min(limits.maxValue, int(round(center + span * normalized))))

    def _update(self, slot: int) -> None:
        dev = self.pads[slot - 1]
        active = set(self.held[slot])
        # Cancelar opuestos, sin generar valores de POV inconsistentes.
        for a, b in (('ar', 'ab'), ('iz', 'de')):
            if a in active and b in active:
                active.discard(a)
                active.discard(b)
        hat = -1
        if self.mode[slot] == 'analog':
            ax, ay = self.analog_axes[slot]
            vx, vy = ax / 127.0, ay / 127.0
        else:
            dx, dy = self.axes(active)
            # CRUCETA con POV real, stick neutral. Si no hay POV, axes como respaldo.
            if self.mode[slot] == 'dpad' and self.hat_enabled.get(slot, False):
                vx, vy = 0.0, 0.0
            else:
                vx, vy = float(dx), float(dy)
            hat = self.HAT_DIRECTIONS.get((dx, dy), -1)
        dev._data.wAxisX = self._axis_value(dev, self.vjoy.HID_USAGE.X, vx)
        # El navegador usa Y positivo = ARRIBA; vJoy Y minimo = ARRIBA.
        dev._data.wAxisY = self._axis_value(dev, self.vjoy.HID_USAGE.Y, -vy)
        dev._data.lButtons = sum(1 << (button - 1) for action, button in self.BUTTONS.items()
                                 if action in active)
        dev._data.bHats = hat if self.hat_enabled.get(slot, False) else 0xFFFFFFFF
        dev._data.bHatsEx1 = 0xFFFFFFFF
        dev._data.bHatsEx2 = 0xFFFFFFFF
        dev._data.bHatsEx3 = 0xFFFFFFFF
        if dev.update() is False:
            raise RuntimeError(f'El controlador vJoy dejo de responder (VJOY{slot})')

    def set_mode(self, slot: int, mode: str) -> bool:
        if slot not in self.held or mode not in ('legacy', 'analog', 'dpad'):
            return False
        with self.lock:
            for key in tuple(self.release_timers):
                if key[0] == slot and key[1] in DIRECTIONS:
                    self._cancel_timer(key)
            for key in tuple(self.pressed_at):
                if key[0] == slot and key[1] in DIRECTIONS:
                    self.pressed_at.pop(key, None)
            self.held[slot].difference_update(DIRECTIONS)
            self.analog_axes[slot] = (0, 0)
            self.mode[slot] = mode
            self._update(slot)
            return True

    def analog(self, slot: int, x: int, y: int) -> bool:
        if (slot not in self.held or type(x) is not int or type(y) is not int
                or not -127 <= x <= 127 or not -127 <= y <= 127):
            return False
        with self.lock:
            if self.mode[slot] != 'analog':
                return False
            if self.analog_axes[slot] == (x, y):
                return True
            previous = self.analog_axes[slot]
            self.analog_axes[slot] = (x, y)
            try:
                self._update(slot)
            except Exception:
                self.analog_axes[slot] = previous
                return False
            return True

    def _release_now(self, slot: int, action: str) -> None:
        key = slot, action
        self._cancel_timer(key)
        self.pressed_at.pop(key, None)
        if action in self.held[slot]:
            self.held[slot].discard(action)
            self._update(slot)

    def _timer_release(self, slot: int, action: str) -> None:
        with self.lock:
            self._release_now(slot, action)

    def apply(self, slot: int, action: str, down: bool) -> bool:
        if slot not in self.held or action not in ACTIONS or type(down) is not bool:
            return False
        with self.lock:
            key = slot, action
            if down:
                self._cancel_timer(key)
                if action in self.held[slot]:
                    return True
                self.held[slot].add(action)
                try:
                    self._update(slot)
                except Exception:
                    self.held[slot].discard(action)
                    return False
                self.pressed_at[key] = time.monotonic()
                return True
            if action not in self.held[slot]:
                return True
            delay = self.MIN_TAP_SECONDS - (time.monotonic() - self.pressed_at.get(key, 0))
            if delay > 0:
                self._cancel_timer(key)
                t = threading.Timer(delay, self._timer_release, args=(slot, action))
                t.daemon = True
                self.release_timers[key] = t
                t.start()
            else:
                self._release_now(slot, action)
            return True

    def release_slot(self, slot: int) -> None:
        if slot not in self.held:
            return
        with self.lock:
            for key in tuple(self.release_timers):
                if key[0] == slot:
                    self._cancel_timer(key)
            for key in tuple(self.pressed_at):
                if key[0] == slot:
                    self.pressed_at.pop(key, None)
            self.held[slot].clear()
            self.analog_axes[slot] = (0, 0)
            if slot <= len(self.pads):
                self._update(slot)

    def identify(self, slot: int, duration: float = 0.28) -> bool:
        """Pulsacion de diagnostico en el boton 8 de un unico dispositivo.

        Invocar bajo el lock de Room: no se mezclan inputs en el intervalo.
        Se suelta incluso si el dispositivo falla mientras esta presionado.
        """
        if slot not in self.held:
            return False
        with self.lock:
            self.release_slot(slot)
            dev = self.pads[slot - 1]
            try:
                dev.set_button(8, 1)
                time.sleep(max(0.12, min(0.55, duration)))
            finally:
                try:
                    dev.set_button(8, 0)
                finally:
                    self.release_slot(slot)
        return True

    def close(self) -> None:
        with self.lock:
            for slot in range(1, self.count + 1):
                try:
                    self.release_slot(slot)
                except Exception:
                    pass
            self.pads.clear()



class FutureoTransport:
    """Puente HTTP exclusivo de localhost al motor HIDMaestro de FUTUREO.

    No comparte puerto con el WebSocket de jugadores ni con Browser Bridge.
    POST /capacity: crea/retira solo mandos del final, sin cerrar la sala.
    POST /input: estado completo de un unico FUTUREO_VJOYn.
    """
    HOST = "127.0.0.1"
    PORT = 38472

    def _call(self, method: str, path: str, payload: dict | None = None,
              timeout: float = 2.5) -> dict:
        import http.client
        raw = None if payload is None else json.dumps(payload, separators=(',', ':'),
                                                       ensure_ascii=True).encode('utf-8')
        conn = http.client.HTTPConnection(self.HOST, self.PORT, timeout=timeout)
        try:
            headers = {"X-Futureo-Client": "MULTIMANDO", "Accept": "application/json"}
            if raw is not None:
                headers["Content-Type"] = "application/json"
            conn.request(method, path, body=raw, headers=headers)
            response = conn.getresponse()
            data = response.read(4096).decode('utf-8', 'replace')
            if response.status != 200:
                raise RuntimeError(f"FUTUREO HTTP {response.status}: {data[:230]}")
            try:
                return json.loads(data)
            except ValueError as exc:
                raise RuntimeError("FUTUREO devolvio un estado JSON invalido") from exc
        except (ConnectionError, OSError, TimeoutError) as exc:
            raise RuntimeError(
                "No hay conexion con FUTUREO v0.8.4 en 127.0.0.1:38472. "
                "Abre FUTUREO, inicia al menos un mando, y cierra versiones anteriores."
            ) from exc
        finally:
            conn.close()

    def health(self) -> dict:
        return self._call("GET", "/health")

    def resize(self, count: int) -> None:
        if type(count) is not int or not 1 <= count <= MAX_PLAYERS:
            raise ValueError("Solo se permiten 1 a 8 mandos FUTUREO")
        result = self._call("POST", "/capacity", {"count": count}, timeout=35.0)
        if result.get("ok") is not True:
            raise RuntimeError("FUTUREO no confirmo la nueva cantidad de mandos")

    def input(self, packet: dict) -> None:
        result = self._call("POST", "/input", packet, timeout=2.5)
        if result.get("ok") is not True:
            raise RuntimeError("FUTUREO no acepto el estado del mando")


class VirtualFutureoPads:
    """Controlador remoto de FUTUREO_VJOY1..8 que REUTILIZA el motor .NET.

    Nunca intenta crear o apropiarse de dispositivos del driver vJoy antiguo.
    Python arbitra los jugadores, la cola y los turnos; FUTUREO transmite HID.
    """
    BUTTONS = {
        'button_x': 0, 'button_y': 1, 'button_lb': 2,
        'button_a': 3, 'button_b': 4, 'button_rb': 5,
        'select': 6, 'start': 7,
    }
    MIN_TAP_SECONDS = .095
    HAT_DIRECTIONS = {
        (0, 1): 1, (1, 1): 2, (1, 0): 3, (1, -1): 4,
        (0, -1): 5, (-1, -1): 6, (-1, 0): 7, (-1, 1): 8,
    }

    @staticmethod
    def axes(actions: set[str]) -> tuple[int, int]:
        return (int('de' in actions) - int('iz' in actions),
                int('ar' in actions) - int('ab' in actions))

    def __init__(self, count: int = DEFAULT_PLAYERS, transport: Any = None):
        if not 1 <= count <= MAX_PLAYERS:
            raise ValueError("Selecciona entre 1 y 8 mandos")
        if transport is None and sys.platform != "win32":
            raise RuntimeError("El anfitrion FUTUREO requiere Windows")
        self.transport = transport if transport is not None else FutureoTransport()
        status = self.transport.health()
        if not isinstance(status, dict) or status.get('engine') != 'FUTUREO_VJOY':
            raise RuntimeError("FUTUREO v0.8.4 debe estar abierto y con puente de anfitrion")
        self.lock = threading.RLock()
        self.session = secrets.token_hex(12)
        self.sequence: dict[int, int] = {}
        self.count = 0
        self.held: dict[int, set[str]] = {}
        self.mode: dict[int, str] = {}
        self.analog_axes: dict[int, tuple[int, int]] = {}
        self.pressed_at: dict[tuple[int, str], float] = {}
        self.release_timers: dict[tuple[int, str], threading.Timer] = {}
        self.closed = False
        self.resize(count)

    def _cancel_timer(self, key: tuple[int, str]) -> None:
        timer = self.release_timers.pop(key, None)
        if timer:
            timer.cancel()

    def _update(self, slot: int) -> None:
        if slot not in self.held or self.closed:
            return
        active = set(self.held[slot])
        for a, b in (('ar', 'ab'), ('iz', 'de')):
            if a in active and b in active:
                active.discard(a)
                active.discard(b)
        direction_x, direction_y = self.axes(active)
        mode = self.mode[slot]
        if mode == 'analog':
            ax, ay = self.analog_axes[slot]
            vx, vy, hat = ax / 127.0, ay / 127.0, 0
        elif mode == 'dpad':
            vx, vy = 0.0, 0.0
            hat = self.HAT_DIRECTIONS.get((direction_x, direction_y), 0)
        else:
            # LEGACY: D-Pad and analog copy to support old game mappings.
            vx, vy = float(direction_x), float(direction_y)
            hat = self.HAT_DIRECTIONS.get((direction_x, direction_y), 0)

        buttons = [0] * 16
        for action, index in self.BUTTONS.items():
            if action in active:
                buttons[index] = 1
        self.sequence[slot] = self.sequence.get(slot, 0) + 1
        packet = {
            'slot': slot,
            'session': self.session,
            'seq': self.sequence[slot],
            'buttons': buttons,
            # Browser Gamepad API Y +1=abajo; Python analog Y +127=arriba.
            'axes': [float(vx), float(-vy)],
            'hat': hat,
        }
        self.transport.input(packet)

    def resize(self, count: int) -> bool:
        if type(count) is not int or not 1 <= count <= MAX_PLAYERS:
            raise ValueError("Cantidad fuera de 1 a 8 jugadores")
        with self.lock:
            if self.closed:
                raise RuntimeError("El anfitrion FUTUREO esta cerrado")
            if count == self.count:
                return True
            previous = self.count
            if count < previous:
                for slot in range(previous, count, -1):
                    self.release_slot(slot)  # botones y ejes neutros primero
            self.transport.resize(count)  # FUTUREO crea o retira el sufijo de slots
            if count > previous:
                for slot in range(previous + 1, count + 1):
                    self.held[slot] = set()
                    self.mode[slot] = 'legacy'
                    self.analog_axes[slot] = (0, 0)
                    self.sequence[slot] = 0
                self.count = count
                for slot in range(previous + 1, count + 1):
                    self._update(slot)
            else:
                for slot in range(count + 1, previous + 1):
                    self.held.pop(slot, None)
                    self.mode.pop(slot, None)
                    self.analog_axes.pop(slot, None)
                    self.sequence.pop(slot, None)
                    for key in list(self.release_timers):
                        if key[0] == slot:
                            self._cancel_timer(key)
                            self.pressed_at.pop(key, None)
                self.count = count
            return True

    def set_mode(self, slot: int, mode: str) -> bool:
        if slot not in self.held or mode not in ('legacy', 'analog', 'dpad'):
            return False
        with self.lock:
            for key in list(self.release_timers):
                if key[0] == slot and key[1] in DIRECTIONS:
                    self._cancel_timer(key)
            for key in list(self.pressed_at):
                if key[0] == slot and key[1] in DIRECTIONS:
                    self.pressed_at.pop(key, None)
            self.held[slot].difference_update(DIRECTIONS)
            self.analog_axes[slot] = (0, 0)
            self.mode[slot] = mode
            self._update(slot)
            return True

    def analog(self, slot: int, x: int, y: int) -> bool:
        if (slot not in self.held or type(x) is not int or type(y) is not int
                or not -127 <= x <= 127 or not -127 <= y <= 127):
            return False
        with self.lock:
            if self.mode[slot] != 'analog':
                return False
            if self.analog_axes[slot] == (x, y):
                return True
            previous = self.analog_axes[slot]
            self.analog_axes[slot] = (x, y)
            try:
                self._update(slot)
            except Exception:
                self.analog_axes[slot] = previous
                return False
            return True

    def _release_now(self, slot: int, action: str) -> None:
        key = slot, action
        self._cancel_timer(key)
        self.pressed_at.pop(key, None)
        if action in self.held[slot]:
            self.held[slot].discard(action)
            self._update(slot)

    def _timer_release(self, slot: int, action: str) -> None:
        with self.lock:
            if not self.closed and slot in self.held:
                try:
                    self._release_now(slot, action)
                except Exception:
                    pass

    def apply(self, slot: int, action: str, down: bool) -> bool:
        if slot not in self.held or action not in ACTIONS or type(down) is not bool:
            return False
        with self.lock:
            key = slot, action
            if down:
                self._cancel_timer(key)
                if action in self.held[slot]:
                    return True
                self.held[slot].add(action)
                try:
                    self._update(slot)
                except Exception:
                    self.held[slot].discard(action)
                    return False
                self.pressed_at[key] = time.monotonic()
                return True
            if action not in self.held[slot]:
                return True
            delay = self.MIN_TAP_SECONDS - (time.monotonic() - self.pressed_at.get(key, 0))
            if delay > 0:
                self._cancel_timer(key)
                t = threading.Timer(delay, self._timer_release, args=(slot, action))
                t.daemon = True
                self.release_timers[key] = t
                t.start()
            else:
                try:
                    self._release_now(slot, action)
                except Exception:
                    return False
            return True

    def release_slot(self, slot: int) -> None:
        if slot not in self.held:
            return
        with self.lock:
            for key in list(self.release_timers):
                if key[0] == slot:
                    self._cancel_timer(key)
            for key in list(self.pressed_at):
                if key[0] == slot:
                    self.pressed_at.pop(key, None)
            self.held[slot].clear()
            self.analog_axes[slot] = (0, 0)
            self._update(slot)

    def identify(self, slot: int, duration: float = .28) -> bool:
        if slot not in self.held:
            return False
        with self.lock:
            self.release_slot(slot)
            try:
                self.held[slot].add('select')
                self._update(slot)
                time.sleep(max(.12, min(.55, duration)))
            finally:
                self.held[slot].discard('select')
                self.release_slot(slot)
            return True

    def heartbeat(self) -> None:
        # Periodic snapshots keep a long button hold alive at the Windows end.
        # A stopped Python host will be neutralized by the FUTUREO watchdog.
        with self.lock:
            if self.closed:
                return
            for slot in range(1, self.count + 1):
                self._update(slot)

    def close(self) -> None:
        with self.lock:
            for slot in range(1, self.count + 1):
                try:
                    self.release_slot(slot)
                except Exception:
                    pass
            for key in tuple(self.release_timers):
                self._cancel_timer(key)
            self.closed = True


LOCAL_BUTTON_DEFAULTS = {
    'button_a': 0, 'button_b': 1, 'button_x': 2, 'button_y': 3,
    'button_lb': 4, 'button_rb': 5, 'start': 7, 'select': 6,
}
CONFIG_FILE = BASE_DIR / 'multimando_config.json'


def load_local_settings() -> dict:
    """Configuracion local solamente; no guarda sesiones ni tokens de invitados."""
    try:
        with CONFIG_FILE.open('r', encoding='utf-8') as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def save_local_settings(data: dict) -> None:
    path = CONFIG_FILE.with_suffix('.json.tmp')
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    path.replace(CONFIG_FILE)


class LocalControllerBridge:
    """Lee mandos fisicos USB/WiFi y alimenta los VJOY en modo CONTROLADO.

    Se ejecuta desde el loop de Tkinter para respetar el pump de SDL.
    Nunca lee VJOY como origen: impediria bucles de retroalimentacion.
    """
    def __init__(self, notify: Callable[[str, Any], None]):
        self.notify = notify
        self.pygame = None
        self.physical: dict[str, dict] = {}
        self.old_buttons: dict[int, dict[str, bool]] = {}
        self.old_axes: dict[int, tuple[int, int]] = {}
        self.missing: set[int] = set()

    def init_pygame(self) -> None:
        if self.pygame is not None:
            return
        try:
            import pygame
        except ImportError as exc:
            raise RuntimeError('Para mandos USB/WiFi instala: py -m pip install pygame') from exc
        os.environ.setdefault('SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS', '1')
        try:
            if not pygame.display.get_init():
                pygame.display.init()
            if pygame.display.get_surface() is None:
                pygame.display.set_mode((1, 1), pygame.HIDDEN)
            if not pygame.joystick.get_init():
                pygame.joystick.init()
            pygame.event.pump()
        except Exception as exc:
            raise RuntimeError('No se pudo iniciar pygame para leer los mandos locales: ' + str(exc)) from exc
        self.pygame = pygame

    @staticmethod
    def _virtual(name: str) -> bool:
        text = name.casefold()
        return 'vjoy' in text or 'virtual joystick' in text or 'futureo' in text

    def scan(self) -> list[str]:
        self.init_pygame()
        pygame = self.pygame
        assert pygame is not None
        pygame.event.pump()
        physical: dict[str, dict] = {}
        duplicates: dict[str, int] = collections.defaultdict(int)
        for i in range(pygame.joystick.get_count()):
            joy = pygame.joystick.Joystick(i)
            joy.init()
            name = str(joy.get_name())
            if self._virtual(name):
                continue
            guid = str(joy.get_guid())
            identity = guid + ':' + name
            duplicates[identity] += 1
            key = f'{identity}:{duplicates[identity]}'
            title = f'{name} [{guid[:8]}] #{duplicates[identity]}'
            physical[title] = {'joy': joy, 'key': key, 'index': i, 'name': name}
        self.physical = physical
        return list(physical)

    def reset_slot(self, slot: int) -> None:
        self.old_buttons.pop(slot, None)
        self.old_axes.pop(slot, None)
        self.missing.discard(slot)

    @staticmethod
    def mapping_for(cfg: dict) -> dict:
        raw = cfg.get('mapping', {}) if isinstance(cfg, dict) else {}
        if not isinstance(raw, dict):
            raw = {}
        buttons = raw.get('buttons', {})
        if not isinstance(buttons, dict):
            buttons = {}
        return {
            'buttons': {action: max(-1, min(127, int(buttons.get(action, number))))
                        for action, number in LOCAL_BUTTON_DEFAULTS.items()},
            'axis_x': max(-1, min(15, int(raw.get('axis_x', 0)))),
            'axis_y': max(-1, min(15, int(raw.get('axis_y', 1)))),
            'invert_y': bool(raw.get('invert_y', True)),
            'deadzone': max(0.05, min(0.45, float(raw.get('deadzone', 0.20)))),
            'hat': bool(raw.get('hat', True)),
        }

    def poll(self, room: Any, assignments: dict[int, dict]) -> None:
        if self.pygame is None or not any(m == 'CONTROLADO' for m in room.slot_modes.values()):
            return
        pygame = self.pygame
        pygame.event.pump()
        with room.lock:
            for slot in room.slots:
                if room.slot_modes.get(slot) != 'CONTROLADO':
                    self.reset_slot(slot)
                    continue
                cfg = assignments.get(slot, {})
                title = str(cfg.get('device', ''))
                record = self.physical.get(title)
                joy = record['joy'] if record else None
                try:
                    if joy is None or not joy.get_init():
                        raise RuntimeError('Mando fisico no disponible')
                    mapping = self.mapping_for(cfg)
                    deadzone = mapping['deadzone']
                    axid, ayid = mapping['axis_x'], mapping['axis_y']
                    ax = float(joy.get_axis(axid)) if 0 <= axid < joy.get_numaxes() else 0.0
                    ay = float(joy.get_axis(ayid)) if 0 <= ayid < joy.get_numaxes() else 0.0
                    if mapping['invert_y']:
                        ay = -ay
                    if abs(ax) < deadzone: ax = 0.0
                    if abs(ay) < deadzone: ay = 0.0
                    if mapping['hat'] and joy.get_numhats():
                        hx, hy = joy.get_hat(0)
                        if hx: ax = float(hx)
                        if hy: ay = float(hy)
                    axes = (int(max(-127, min(127, round(ax * 127)))),
                            int(max(-127, min(127, round(ay * 127)))))
                    if self.old_axes.get(slot) != axes:
                        if room.device.mode.get(slot) != 'analog':
                            room.device.set_mode(slot, 'analog')
                        room.device.analog(slot, *axes)
                        self.old_axes[slot] = axes
                    next_btns = {}
                    for action, button_no in mapping['buttons'].items():
                        next_btns[action] = bool(joy.get_button(button_no)) if 0 <= button_no < joy.get_numbuttons() else False
                    previous = self.old_buttons.get(slot, {})
                    for action, down in next_btns.items():
                        if previous.get(action, False) != down:
                            room.device.apply(slot, action, down)
                    self.old_buttons[slot] = next_btns
                    self.missing.discard(slot)
                except Exception as exc:
                    if slot not in self.missing:
                        self.notify('log', f'VJOY{slot}: mando fisico perdido / sin acceso: {exc}')
                        self.missing.add(slot)
                    room.device.release_slot(slot)
                    self.old_axes.pop(slot, None)
                    self.old_buttons.pop(slot, None)

    def close(self) -> None:
        if self.pygame is not None:
            try:
                self.pygame.joystick.quit()
                self.pygame.display.quit()
            except Exception:
                pass
        self.pygame = None
        self.physical.clear()
        self.old_axes.clear()
        self.old_buttons.clear()

class Room:
    """Arbitro de turnos P1..Pn con cola FIFO y reloj del anfitrion."""
    def __init__(self, device: Any, seconds: float = DEFAULT_SECONDS,
                 clock: Callable[[], float] = time.monotonic,
                 max_guests: int = MAX_GUESTS,
                 slot_modes: dict[int, str] | None = None):
        if seconds <= 0 or not math.isfinite(seconds):
            raise ValueError("Tiempo de turno invalido")
        self.device = device
        self.slot_count = int(getattr(device, 'count', DEFAULT_PLAYERS))
        if not (1 <= self.slot_count <= MAX_PLAYERS):
            raise ValueError('Numero de mandos fuera del rango 1-8')
        self.slots = tuple(range(1, self.slot_count + 1))
        configured = slot_modes or {}
        self.slot_modes = {slot: configured.get(slot, 'REMOTO') for slot in self.slots}
        if any(mode not in ('REMOTO','CONTROLADO') for mode in self.slot_modes.values()):
            raise ValueError('Modo de VJOY no reconocido')
        self.remote_slots = tuple(slot for slot in self.slots if self.slot_modes[slot] == 'REMOTO')
        self.seconds = float(seconds)
        self.clock = clock
        self.max_guests = max_guests
        self.session_id = secrets.token_hex(3).upper()
        self.players: dict[int, Guest] = {}
        self.waiting: collections.deque[int] = collections.deque()
        self.uid = 1
        self.lock = threading.RLock()
        self.events: collections.deque[tuple[str, str, int]] = collections.deque()

    def _activate(self, guest: Guest, slot: int, now: float) -> None:
        guest.slot = slot
        guest.queued = False
        guest.held.clear()
        guest.input_times.clear()
        guest.remaining = (self.seconds if guest.turn_credit is None
                           else min(self.seconds, max(1.0, guest.turn_credit)))
        guest.turn_credit = None
        guest.last_tick = now
        guest.countdown_deadline = now + COUNTDOWN_SECONDS
        guest.activation_deadline = None
        guest.warned_last_minute = False
        self.device.release_slot(slot)
        self.device.set_mode(slot, guest.direction_mode)
        self.events.append(("assigned", guest.name, slot))

    def _vacancy(self, now: float) -> None:
        while self.waiting:
            occupied = {g.slot for g in self.players.values() if g.slot in self.remote_slots}
            slot = next((n for n in self.remote_slots if n not in occupied), None)
            if slot is None:
                return
            uid = self.waiting.popleft()
            guest = self.players.get(uid)
            if guest is not None and guest.queued and guest.active:
                self._activate(guest, slot, now)

    def _neutralize(self, guest: Guest) -> None:
        """Neutralidad absoluta para el puesto afectado (botones + stick + timers)."""
        try:
            if guest.slot:
                self.device.release_slot(guest.slot)
        finally:
            guest.held.clear()
            guest.input_times.clear()

    def _deactivate(self, guest: Guest) -> int:
        slot = guest.slot
        self._neutralize(guest)
        guest.slot = 0
        guest.queued = False
        guest.activation_deadline = None
        guest.countdown_deadline = None
        guest.last_tick = 0.0
        return slot

    def _rotate(self, guest: Guest, now: float, reason: str) -> bool:
        """Cambia un ocupante por el primero que esperaba; pone al anterior al final."""
        if guest.slot == 0 or not self.waiting:
            return False
        slot = self._deactivate(guest)
        guest.queued = True
        self.waiting.append(guest.uid)
        self.events.append((reason, guest.name, slot))
        self._vacancy(now)
        return True

    def _advance(self, now: float) -> None:
        """Turnos: 3 s de aviso -> 10 s de activacion -> 600 s con cola.

        Los segundos 3+10 nunca se cargan al tiempo de juego. Los puestos
        CONTROLADO no participan en la cola ni en estos temporizadores.
        """
        has_queue = bool(self.waiting)
        active = tuple(g for g in self.players.values() if g.slot in self.remote_slots)
        for g in active:
            elapsed = max(0.0, now - g.last_tick)
            if g.countdown_deadline is not None:
                if now >= g.countdown_deadline:
                    g.activation_deadline = g.countdown_deadline + ACTIVATION_SECONDS
                    g.countdown_deadline = None
                    self.events.append(("activation_ready", g.name, g.slot))
            elif g.activation_deadline is None and has_queue:
                g.remaining = max(0.0, g.remaining - elapsed)
            g.last_tick = now
        # Sin persona en espera no se desaloja a nadie por inactividad.
        for g in sorted(active, key=lambda x: x.slot):
            if not g.slot or not self.waiting or g.countdown_deadline is not None:
                continue
            if g.activation_deadline is not None:
                if now >= g.activation_deadline:
                    self._rotate(g, now, "activation_timeout")
            elif g.remaining <= 0.000001:
                self._rotate(g, now, "turn_finished")
        if self.waiting:
            for g in self.players.values():
                if (g.slot and g.activation_deadline is None and
                        g.countdown_deadline is None and g.remaining <= 60
                        and not g.warned_last_minute):
                    g.warned_last_minute = True
                    self.events.append(("last_minute", g.name, g.slot))

    def _confirm_first_input(self, guest: Guest, now: float) -> None:
        """Solo una entrada aceptada del usuario activa su turno de 10 min."""
        if guest.activation_deadline is not None and guest.countdown_deadline is None:
            guest.activation_deadline = None
            guest.remaining = self.seconds
            guest.last_tick = now
            guest.warned_last_minute = False
            self.events.append(("activated", guest.name, guest.slot))

    def register(self, name: str, socket: Any = None, heartbeat: bool = False) -> Guest:
        with self.lock:
            now = self.clock()
            self._advance(now)
            if not self.remote_slots:
                raise ValueError('No hay puestos REMOTO disponibles en esta sala')
            if len(self.players) >= self.max_guests:
                raise ValueError("Sala llena; vuelve a intentarlo mas tarde")
            if not isinstance(name, str):
                raise ValueError("El nombre debe ser texto")
            clean = " ".join("".join(c for c in name if c.isprintable()).split())
            if not clean:
                raise ValueError("Escribe un nombre valido")
            if len(clean) > MAX_NAME_CHARS:
                raise ValueError(f"El nombre no puede superar {MAX_NAME_CHARS} caracteres")
            normalized = canonical_name(clean)
            if any(canonical_name(g.name) == normalized for g in self.players.values()):
                raise ValueError("El nombre '" + clean + "' ya esta en uso en esta sala")
            g = Guest(self.uid, clean, socket, remaining=self.seconds,
                      heartbeat_enabled=heartbeat, last_heartbeat=now)
            self.uid += 1
            self.players[g.uid] = g
            self._vacancy(now)
            vacant = next((s for s in self.remote_slots if not any(p.slot == s for p in self.players.values())), None)
            if vacant is not None and not self.waiting:
                self._activate(g, vacant, now)
            else:
                g.slot = 0
                g.queued = True
                self.waiting.append(g.uid)
                self.events.append(("waiting", g.name, len(self.waiting)))
                # Si el ocupante anterior ya dejo pasar sus 10 segundos,
                # el primer jugador de la cola recibe su puesto inmediatamente.
                self._advance(now)
            return g

    def resume(self, name: str, token: str, socket: Any, heartbeat: bool = False) -> tuple[Guest, Any] | None:
        """Solo el titular del token puede recuperar el puesto, incluso si el socket anterior persiste."""
        if not isinstance(token, str) or not (30 <= len(token) <= 128):
            return None
        with self.lock:
            now = self.clock()
            self._advance(now)
            normalized = canonical_name(str(name))
            guest = next((g for g in self.players.values()
                          if canonical_name(g.name) == normalized and g.active), None)
            if not guest or not hmac.compare_digest(guest.resume_token, token):
                return None
            if guest.disconnected_at is not None and now - guest.disconnected_at > RECONNECT_GRACE_SECONDS:
                return None
            previous = guest.socket
            # Aun si el socket anterior parece vivo (red intermitente), no
            # heredar ninguna tecla, timer de liberacion ni eje analogico.
            # El usuario vuelve a jugar desde estado completamente neutro.
            self._neutralize(guest)
            guest.heartbeat_enabled = heartbeat
            guest.last_heartbeat = now
            guest.input_suspended = False
            if guest.disconnect_timer:
                guest.disconnect_timer.cancel()
                guest.disconnect_timer = None
            guest.disconnected_at = None
            guest.socket = socket
            guest.outbound = queue.Queue(maxsize=32)
            guest.wake = threading.Event()
            guest.input_times.clear()
            self.events.append(("reconnected", guest.name, guest.slot))
            return guest, previous

    def disconnect(self, uid: int, socket: Any) -> bool:
        """Soltar botones y reservar temporalmente la identidad, mando y turno."""
        with self.lock:
            guest = self.players.get(uid)
            if not guest or guest.socket is not socket:
                return False  # Un socket anterior nunca cierra la sesion recuperada.
            self._advance(self.clock())
            guest.socket = None
            guest.disconnected_at = self.clock()
            self._neutralize(guest)
            guest.input_suspended = True
            if guest.disconnect_timer:
                guest.disconnect_timer.cancel()
            timer = threading.Timer(RECONNECT_GRACE_SECONDS, self._expire_disconnect,
                                    args=(uid, guest.resume_token, guest.disconnected_at))
            timer.daemon = True
            guest.disconnect_timer = timer
            timer.start()
            self.events.append(("reconnecting", guest.name, guest.slot))
            return True

    def heartbeat(self, uid: int, socket: Any) -> bool:
        """Acepta latidos solo desde el socket actual y rearma controles neutrales."""
        with self.lock:
            guest = self.players.get(uid)
            if (not guest or not guest.active or guest.socket is not socket
                    or not guest.heartbeat_enabled or guest.disconnected_at is not None):
                return False
            now = self.clock()
            # Even if an overdue heartbeat arrives before the 0.5s ticker,
            # the old pressed input MUST first be reset.
            if guest.slot:
                self._check_input_watchdog(guest, now)
            guest.last_heartbeat = now
            guest.input_suspended = False
            return True

    def _check_input_watchdog(self, guest: Guest, now: float) -> bool:
        if not guest.heartbeat_enabled or guest.socket is None:
            return False
        if now - guest.last_heartbeat < INPUT_WATCHDOG_SECONDS:
            return guest.input_suspended
        if not guest.input_suspended:
            self._neutralize(guest)
            guest.input_suspended = True
            guest.tell({"type": "controls_reset"})
            self.events.append(("input_timeout", guest.name, guest.slot))
        return True

    def watchdog(self) -> None:
        """Detecta enlaces medio abiertos aunque websocket no haya cerrado aun."""
        with self.lock:
            now = self.clock()
            for guest in self.players.values():
                if guest.active and guest.slot and guest.socket is not None:
                    self._check_input_watchdog(guest, now)

    def _expire_disconnect(self, uid: int, token: str, disconnected_at: float) -> None:
        with self.lock:
            guest = self.players.get(uid)
            if (guest and guest.disconnected_at == disconnected_at
                    and hmac.compare_digest(guest.resume_token, token)):
                self.remove(uid)

    def queue_keep_waiting(self, uid: int) -> bool:
        """Respuesta opcional de web; SOLO web calcula los cinco minutos."""
        with self.lock:
            self._advance(self.clock())
            g = self.players.get(uid)
            if not g or not g.active or not g.queued or g.slot != 0:
                return False
            self.events.append(('queue_kept', g.name, 0))
            return True

    def queue_yield(self, uid: int) -> Guest | None:
        """Salir voluntariamente de la cola sin reservar el nombre durante 35s."""
        with self.lock:
            self._advance(self.clock())
            g = self.players.get(uid)
            if not g or not g.active or not g.queued or g.slot != 0:
                return None
            return self.remove(uid)

    def remove(self, uid: int) -> Guest | None:
        with self.lock:
            now = self.clock()
            self._advance(now)
            g = self.players.pop(uid, None)
            if g is None:
                return None
            if g.disconnect_timer:
                g.disconnect_timer.cancel()
                g.disconnect_timer = None
            old_slot = self._deactivate(g)
            self.waiting = collections.deque(u for u in self.waiting if u != uid)
            g.active = False
            g.wake.set()
            self.events.append(("left", g.name, old_slot))
            self._vacancy(now)
            return g

    def set_slot_mode(self, slot: int, mode: str) -> Guest | None:
        """Reserva un VJOY fisico o habilita uno remoto con reasignacion FIFO.

        Al pasar a CONTROLADO, expulsa al visitante que ocupaba ese VJOY,
        liberando todos sus botones ANTES de activar el mando fisico.
        El llamador cierra luego su WebSocket.
        """
        if slot not in self.slots or mode not in ('REMOTO', 'CONTROLADO'):
            raise ValueError('Puesto o modo invalido')
        with self.lock:
            now = self.clock()
            self._advance(now)
            if self.slot_modes[slot] == mode:
                return None
            self.slot_modes[slot] = mode
            self.remote_slots = tuple(s for s in self.slots if self.slot_modes[s] == 'REMOTO')
            victim = next((g for g in self.players.values() if g.slot == slot), None)
            if victim and mode == 'CONTROLADO':
                self.remove(victim.uid)
                self.events.append(('local_takeover', victim.name, slot))
            self.device.release_slot(slot)
            if mode == 'CONTROLADO':
                self.device.set_mode(slot, 'analog')
            else:
                self.device.set_mode(slot, 'dpad')
                self._vacancy(now)
            return victim if mode == 'CONTROLADO' else None

    def resize_capacity(self, count: int,
                        extra_modes: dict[int, str] | None = None) -> dict:
        """Cambia el numero de jugadores EN VIVO, sin cerrar WebSocket ni sala.

        - Crece: crea solo mandos adicionales, sirve la cola FIFO existente.
        - Reduce: suelta botones y stick de los puestos sobrantes, pone a
          sus ocupantes al final de la cola (sin adelantar a los que esperaban)
          y conserva para ellos los segundos restantes de juego.
        - P1..P<count> no se reinician ni pierden sus turnos.
        - Los modos CONTROLADO/REMOTO de los puestos conservados se respetan.
        """
        if type(count) is not int or not 1 <= count <= MAX_PLAYERS:
            raise ValueError("Solo se admiten entre 1 y 8 jugadores")
        with self.lock:
            now = self.clock()
            self._advance(now)
            previous = self.slot_count
            if count == previous:
                return {'previous': previous, 'current': count,
                        'displaced': [], 'queue': len(self.waiting)}
            new_modes = extra_modes or {}
            for n in range(previous + 1, count + 1):
                if new_modes.get(n, 'REMOTO') not in ('REMOTO', 'CONTROLADO'):
                    raise ValueError(f"Modo de FUTUREO_VJOY{n} invalido")

            displaced: list[tuple[Guest, int, float]] = []
            if count < previous:
                victims = sorted(
                    (g for g in self.players.values() if g.slot > count),
                    key=lambda g: g.slot)
                for g in victims:
                    original_slot = g.slot
                    remaining = max(1.0, g.remaining)
                    self._deactivate(g)
                    g.queued = True
                    g.turn_credit = remaining
                    # Mantiene delante a quienes ya formaban la cola.
                    self.waiting.append(g.uid)
                    g.tell({'type': 'controls_reset'})
                    self.events.append(('capacity_queued', g.name, original_slot))
                    displaced.append((g, original_slot, remaining))

            try:
                # El cambio de dispositivos solo lo realiza FUTUREO, no Python.
                self.device.resize(count)
            except Exception:
                # Si no pudo reducir FUTUREO, devolver el turno a los mismos
                # puestos originales sin desconectar a nadie.
                for g, original_slot, remaining in displaced:
                    self.waiting = collections.deque(
                        uid for uid in self.waiting if uid != g.uid)
                    g.turn_credit = remaining
                    self._activate(g, original_slot, now)
                raise

            if count > previous:
                for slot in range(previous + 1, count + 1):
                    mode = new_modes.get(slot, 'REMOTO')
                    self.slot_modes[slot] = mode
                    self.device.set_mode(slot, 'analog' if mode == 'CONTROLADO' else 'dpad')
            else:
                for slot in range(count + 1, previous + 1):
                    self.slot_modes.pop(slot, None)

            self.slot_count = count
            self.slots = tuple(range(1, count + 1))
            self.remote_slots = tuple(
                slot for slot in self.slots if self.slot_modes[slot] == 'REMOTO')
            self._vacancy(now)
            self.events.append(('capacity_changed', f'{previous}->{count}', count))
            return {
                'previous': previous, 'current': count,
                'displaced': [g.name for g, _, _ in displaced],
                'queue': len(self.waiting)
            }

    def identify_slot(self, slot: int) -> bool:
        """Diagnostico local sin que un cliente remoto pueda enviar el comando."""
        with self.lock:
            if slot not in self.slots:
                return False
            self._advance(self.clock())
            for guest in self.players.values():
                if guest.slot == slot:
                    self._neutralize(guest)
                    # La prueba no debe reactivar el teclado antiguo del navegador.
                    guest.input_suspended = False
                    guest.tell({'type': 'controls_reset'})
            return self.device.identify(slot)

    def rotate_slot(self, slot: int) -> bool:
        """Solo la GUI local puede hacer avanzar una cola antes del limite."""
        with self.lock:
            now = self.clock()
            self._advance(now)
            g = next((g for g in self.players.values() if g.slot == slot), None)
            return bool(g and self._rotate(g, now, "manual_turn"))

    def set_direction_mode(self, uid: int, mode: str) -> bool:
        """Un cliente cambia SOLO su propio dispositivo; el puesto lo decide Python."""
        if mode not in ('analog', 'dpad'):
            return False
        with self.lock:
            now = self.clock()
            self._advance(now)
            guest = self.players.get(uid)
            if not guest or not guest.active:
                return False
            if guest.direction_mode == mode:
                return True
            if guest.slot and not self.device.set_mode(guest.slot, mode):
                return False
            guest.direction_mode = mode
            guest.held.difference_update(DIRECTIONS)
            return True

    def analog(self, uid: int, x: int, y: int) -> bool:
        """Ejes analogicos de 8 bits, permitidos solo al jugador actual en modo analogico."""
        if type(x) is not int or type(y) is not int or not (-127 <= x <= 127 and -127 <= y <= 127):
            return False
        with self.lock:
            now = self.clock()
            self._advance(now)
            guest = self.players.get(uid)
            if (not guest or not guest.active or not guest.slot or
                    guest.countdown_deadline is not None or guest.direction_mode != 'analog'):
                return False
            if self._check_input_watchdog(guest, now):
                return False
            while guest.input_times and guest.input_times[0] < now - 1.0:
                guest.input_times.popleft()
            if len(guest.input_times) >= MAX_MESSAGES_PER_SECOND:
                return False
            guest.input_times.append(now)
            accepted = self.device.analog(guest.slot, x, y)
            # Ignorar el ruido de un joystick ligeramente descentrado.
            if accepted and max(abs(x), abs(y)) >= 18:
                self._confirm_first_input(guest, now)
            return accepted

    def input(self, uid: int, action: str, down: bool) -> bool:
        with self.lock:
            now = self.clock()
            self._advance(now)
            g = self.players.get(uid)
            if (not g or not g.active or not g.slot or
                    g.countdown_deadline is not None or action not in ACTIONS
                    or type(down) is not bool):
                return False
            if self._check_input_watchdog(g, now):
                return False
            while g.input_times and g.input_times[0] < now - 1.0:
                g.input_times.popleft()
            if len(g.input_times) >= MAX_MESSAGES_PER_SECOND:
                return False
            g.input_times.append(now)
            if (action in g.held) == down:
                return True
            if not self.device.apply(g.slot, action, down):
                return False
            if down:
                g.held.add(action)
                self._confirm_first_input(g, now)
            else:
                g.held.discard(action)
            return True

    def tick(self) -> list[tuple[str, str, int]]:
        with self.lock:
            self._advance(self.clock())
            events = list(self.events)
            self.events.clear()
            return events

    def snapshot(self) -> dict:
        with self.lock:
            self._advance(self.clock())
            running = bool(self.waiting)
            people = {}
            for slot in self.slots:
                g = next((p for p in self.players.values() if p.slot == slot), None)
                people[str(slot)] = {
                    "id": g.uid, "name": g.name,
                    "remaining_seconds": max(0, math.ceil(g.remaining)),
                    "timer_remaining": max(0, math.ceil(g.remaining)),
                    "timer_running": running and g.activation_deadline is None and g.countdown_deadline is None,
                    "countdown_seconds": max(0, math.ceil(g.countdown_deadline - self.clock()))
                                         if g.countdown_deadline is not None else 0,
                    "activation_pending": g.activation_deadline is not None,
                    "activation_seconds": max(0, math.ceil(g.activation_deadline - self.clock()))
                                          if g.activation_deadline is not None else 0,
                } if g else None
            return {
                "players": people,
                "queue": [{"id": uid, "name": self.players[uid].name}
                          for uid in self.waiting if uid in self.players],
                "queue_length": len(self.waiting),
                "total": len(self.players),
                "slot_count": self.slot_count,
                "remote_count": len(self.remote_slots),
                "slot_modes": {str(slot): self.slot_modes[slot] for slot in self.slots},
                "turn_duration": self.seconds,
                "room_id": self.session_id,
            }

    def individualized(self) -> list[tuple[Guest, dict]]:
        with self.lock:
            data = self.snapshot()
            waiting_ids = list(self.waiting)
            result = []
            for g in self.players.values():
                timer = max(0, math.ceil(g.remaining)) if g.slot else None
                state = {
                    "type": "state", "you": g.uid,
                    "slot": g.slot,
                    "waiting_position": waiting_ids.index(g.uid) + 1 if g.queued and g.uid in waiting_ids else 0,
                    "remaining_seconds": timer,
                    "timer_remaining": timer,
                    "timer_running": bool(self.waiting) and bool(g.slot)
                                     and g.activation_deadline is None and g.countdown_deadline is None,
                    "countdown_seconds": max(0, math.ceil(g.countdown_deadline - self.clock()))
                                         if g.countdown_deadline is not None else 0,
                    "activation_seconds": max(0, math.ceil(g.activation_deadline - self.clock()))
                                          if g.activation_deadline is not None else 0,
                    **data,
                }
                result.append((g, state))
            return result

    def compact_states(self) -> list[tuple[Guest, list[int]]]:
        """Seis enteros de estado PERSONALIZADO, sin roster ni nombres.

        [slot, waiting_position, queue_length, remaining_seconds, activation_seconds, countdown_seconds]
        - slot 0=cola, 1..8=P1..P8.
        - el reloj corre si slot entre 1 y N y queue_length > 0.
        - el tiempo 0 en espera no significa que el jugador perdio su turno.
        """
        with self.lock:
            self._advance(self.clock())
            positions = {uid: i + 1 for i, uid in enumerate(self.waiting)}
            queue_length = len(self.waiting)
            return [
                (g, [
                    g.slot,
                    positions.get(g.uid, 0),
                    queue_length,
                    max(0, math.ceil(g.remaining)) if g.slot else 0,
                    max(0, math.ceil(g.activation_deadline - self.clock()))
                    if g.slot and g.activation_deadline is not None else 0,
                    max(0, math.ceil(g.countdown_deadline - self.clock()))
                    if g.slot and g.countdown_deadline is not None else 0,
                ])
                for g in self.players.values() if g.active and g.socket is not None
            ]

    def close(self) -> None:
        with self.lock:
            for g in self.players.values():
                if g.disconnect_timer:
                    g.disconnect_timer.cancel()
                g.active = False
                g.wake.set()
            self.players.clear()
            self.waiting.clear()
            self.device.close()


def websocket_channel(raw_path: str | None) -> str:
    """Solo '/stream' y '/stream/' son espectadores (con o sin query).

    El controlador v2.0 aceptaba cualquier ruta WS y verificaba el
    primer mensaje hello. Mantener ese comportamiento evita romper
    clientes anteriores que agregan rutas o parametros de conexion.
    """
    route = urlsplit(raw_path or "/").path.rstrip("/")
    return "stream" if route == "/stream" else "controller"


class MultimandoServer:
    def __init__(self, port: int, device: Any, on_event: Callable[[str, Any], None],
                 seconds: float = DEFAULT_SECONDS, bind_lan: bool = False,
                 slot_modes: dict[int, str] | None = None):
        self.port = port
        self.room = Room(device, seconds=seconds, slot_modes=slot_modes)
        self.on_event = on_event
        self.bind_lan = bind_lan
        self.stop_event = threading.Event()
        self.server = None
        self.worker: threading.Thread | None = None
        self.ticker: threading.Thread | None = None
        # No enviar el roster de todos los usuarios cada 0.5 s a cada cliente.
        # Estado [slot, posicion, cola, restante, activacion, cuenta_atras].
        self._state_lock = threading.RLock()
        self._last_state: dict[int, tuple[tuple[int, int, int], float]] = {}
        self._last_roster_at = 0.0
        self._last_device_heartbeat_error = 0.0
        self.stream_hub = FrameHub()

    def start(self) -> None:
        try:
            from websockets.sync.server import serve
        except ImportError as exc:
            raise RuntimeError("Instala: py -m pip install websockets pygame") from exc
        bind = "0.0.0.0" if self.bind_lan else "127.0.0.1"
        self.server = serve(self._handle, bind, self.port, max_size=4096,
                            compression=None, ping_interval=5, ping_timeout=5,
                            open_timeout=10, close_timeout=3)
        # Puerto elegido por el SO cuando el usuario pasa 0 (solo pruebas).
        self.port = self.server.socket.getsockname()[1]
        self.worker = threading.Thread(target=self.server.serve_forever,
                                       daemon=True, name="MULTIMANDO-WebSocket")
        self.worker.start()
        self.ticker = threading.Thread(target=self._ticker, daemon=True,
                                       name="MULTIMANDO-Turnos")
        self.ticker.start()
        self.on_event("log", f"Sala abierta en {bind}:{self.port}; ID {self.room.session_id}")

    def _sender(self, guest: Guest, websocket: Any, outbound: queue.Queue, wake: threading.Event) -> None:
        try:
            while guest.active and guest.socket is websocket and not self.stop_event.is_set():
                wake.wait(1.0)
                wake.clear()
                while guest.active and guest.socket is websocket:
                    try:
                        payload = outbound.get_nowait()
                    except queue.Empty:
                        break
                    websocket.send(payload)
        except Exception:
            try: websocket.close()
            except Exception: pass

    def _state(self) -> None:
        """Notificar SOLO cambios de asignacion/cola y sincronizar reloj.

        El calculo de tiempo es autoritativo en Room (Python). La palanca
        muestra la cuenta localmente entre sincronizaciones de 10 segundos.
        La GUI sigue viendo snapshot completo pero NUNCA lo envia a Internet.
        """
        with self._state_lock:
            now = time.monotonic()
            states = self.room.compact_states()
            live_uids = set()
            for guest, packet in states:
                live_uids.add(guest.uid)
                # El estado solo contiene seis enteros. Nunca transmitir
                # el roster por WebSocket, aun cuando haya muchos conectados.
                fingerprint = (packet[0], packet[1], packet[2], packet[4], packet[5])
                previous = self._last_state.get(guest.uid)
                running = packet[0] in self.room.slots and packet[2] > 0
                cadence = (1.0 if packet[4] > 0 or packet[5] > 0 else
                           STATE_RESYNC_ACTIVE if running else STATE_RESYNC_PAUSED)
                if previous is None or fingerprint != previous[0] or now - previous[1] >= cadence:
                    guest.tell(packet)
                    self._last_state[guest.uid] = (fingerprint, now)
            for departed_uid in self._last_state.keys() - live_uids:
                del self._last_state[departed_uid]
            # Solo para la ventana local: no se transmite por WebSocket.
            if now - self._last_roster_at >= 1.0:
                self.on_event("roster", self.room.snapshot())
                self._last_roster_at = now

    def _handle(self, websocket: Any) -> None:
        # Solo /stream es publico y de lectura. RESTO de rutas siguen usando
        # el protocolo historico del mando, incluido /?token=... o /ws.
        # Nunca rechazar un mando por su ruta: el primer paquete "hello"
        # conserva la validacion de identidad, sesiones y turnos.
        path = getattr(getattr(websocket, "request", None), "path", "/")
        if websocket_channel(path) == "stream":
            self.stream_hub.spectator(websocket, self.stop_event)
            return
        guest = None
        try:
            raw = websocket.recv(timeout=12)
            if not isinstance(raw, str) or len(raw) > 4096:
                websocket.send(compact({"type": "error", "message": "Mensaje inicial invalido"}))
                return
            try:
                hello = json.loads(raw)
            except (ValueError, TypeError):
                websocket.send(compact({"type": "error", "message": "JSON invalido"}))
                return
            if not isinstance(hello, dict) or hello.get("type") != "hello":
                websocket.send(compact({"type": "error", "message": "Primero envia hello"}))
                return
            name = hello.get("name", "")
            resume_token = hello.get("resume_token")
            heartbeat_enabled = hello.get("heartbeat") is True
            recovered = False
            previous_socket = None
            if isinstance(resume_token, str):
                found = self.room.resume(name, resume_token, websocket, heartbeat=heartbeat_enabled)
                if found:
                    guest, previous_socket = found
                    recovered = True
            if not recovered:
                try:
                    guest = self.room.register(name, websocket, heartbeat=heartbeat_enabled)
                except ValueError as exc:
                    websocket.send(compact({"type": "error", "message": str(exc)}))
                    return
            websocket.send(compact({"type": "welcome", "you": guest.uid,
                                    "room_id": self.room.session_id,
                                    "resume_token": guest.resume_token,
                                    "resumed": recovered, "heartbeat": heartbeat_enabled,
                                    "version": VERSION, "turn_duration": self.room.seconds}))
            if previous_socket is not None and previous_socket is not websocket:
                try: previous_socket.close(code=1000, reason="Sesion recuperada")
                except Exception: pass
            threading.Thread(target=self._sender, args=(guest, websocket, guest.outbound, guest.wake), daemon=True,
                             name=f"MULTIMANDO-Send-{guest.uid}").start()
            with self._state_lock:
                self._last_state.pop(guest.uid, None)
            self._state()
            self.on_event("log", f"{guest.name} {'reconectado' if recovered else 'conectado'}: " + (f"P{guest.slot}" if guest.slot else "cola"))
            for raw in websocket:
                if self.stop_event.is_set():
                    break
                # La identidad de la conexion debe verificarse BAJO el bloqueo:
                # un socket antiguo no puede reactivar teclas ni expulsar al
                # jugador despues de una recuperacion simultanea.
                with self.room.lock:
                    if not guest.active or guest.socket is not websocket:
                        break
                    if raw == 'bye':
                        self.room.remove(guest.uid)
                        break
                    if raw == 'q1':
                        if self.room.queue_keep_waiting(guest.uid):
                            guest.tell({'type': 'queue_kept'})
                        continue
                    if raw == 'q0':
                        if self.room.queue_yield(guest.uid) is not None:
                            try:
                                websocket.send(compact({'type': 'queue_left'}))
                            except Exception:
                                pass
                            self.on_event('log', f'{guest.name} cedio voluntariamente su lugar en la cola')
                            break
                        else:
                            guest.tell({'type': 'queue_cannot_yield',
                                        'message': 'Ya tienes un mando asignado; no se ha cedido tu turno.'})
                        continue
                    if raw == 'h':
                        if self.room.heartbeat(guest.uid, websocket):
                            guest.tell_raw('h')
                        continue
                if isinstance(raw, bytes):
                    # Paquete binario EXACTO de 3 bytes: A1, int8 X, int8 Y.
                    if len(raw) != 3 or raw[0] != 0xA1:
                        continue
                    x = int.from_bytes(raw[1:2], 'big', signed=True)
                    y = int.from_bytes(raw[2:3], 'big', signed=True)
                    with self.room.lock:
                        if not guest.active or guest.socket is not websocket:
                            break
                        before_slot = guest.slot
                        before = self.room.device.analog_axes.get(before_slot, (0, 0))
                        accepted = self.room.analog(guest.uid, x, y)
                        is_current = guest.slot == before_slot and before_slot in self.room.slots
                    if accepted and is_current:
                        was_active = before != (0, 0)
                        is_active = (x, y) != (0, 0)
                        if was_active != is_active:
                            word = f'MOVIMIENTO ({x}, {y})' if is_active else 'CENTRADO (0, 0)'
                            self.on_event('log', f'CONTROL P{before_slot} | {guest.name} | ANALOGICO | {word}')
                    continue
                if not isinstance(raw, str) or len(raw) > 4096:
                    continue
                if raw in ('m0', 'm1'):
                    mode = 'analog' if raw == 'm1' else 'dpad'
                    with self.room.lock:
                        if not guest.active or guest.socket is not websocket:
                            break
                        accepted = self.room.set_direction_mode(guest.uid, mode)
                        slot = guest.slot
                    if accepted:
                        self.on_event('log', f'{guest.name} | {"P"+str(slot) if slot else "COLA"} | MODO {mode.upper()}')
                    continue
                decoded = decode_input(raw)
                if decoded is None:
                    continue
                action, down = decoded
                # Una pulsacion no puede atribuirse a un puesto antiguo si
                # el temporizador lo hizo rotar justo en este instante.
                with self.room.lock:
                    if not guest.active or guest.socket is not websocket:
                        break
                    slot_before = guest.slot
                    held_before = action in guest.held
                    accepted = self.room.input(guest.uid, action, down)
                    real_transition = (
                        accepted and slot_before in self.room.slots
                        and guest.slot == slot_before and guest.active
                        and held_before != down and (action in guest.held) == down
                    )
                if real_transition:
                    button = INPUT_NAMES.get(action, action.upper())
                    code = next((k for k, a in WIRE_CODES.items() if a == action), "?")
                    self.on_event("log", (
                        f"CONTROL P{slot_before} | {guest.name} | "
                        f"{button} ({code}{'1' if down else '0'}) | "
                        + ("PRESIONADO" if down else "SOLTADO")
                    ))
                if accepted and down and action in ("start", "select"):
                    guest.tell({"type": "input_ack", "action": action, "slot": guest.slot})
                if not accepted and down:
                    guest.tell({"type": "notice", "level": "warning",
                                "message": "Sin turno o entrada no admitida"})
                # La web no puede alterar turnos, posiciones ni temporizadores.
        except Exception as exc:
            if guest is None:
                self.on_event("log", "Conexion sin identificar: " + type(exc).__name__)
        finally:
            if guest is not None:
                reserved = self.room.disconnect(guest.uid, websocket)
                self._state()
                if reserved:
                    self.on_event("log", f"{guest.name}: conexion perdida, 35s para recuperar el mando")
            try:
                websocket.close()
            except Exception:
                pass

    def _ticker(self) -> None:
        while not self.stop_event.is_set():
            self.room.watchdog()
            heartbeat = getattr(self.room.device, 'heartbeat', None)
            if callable(heartbeat):
                try:
                    with self.room.lock:
                        heartbeat()
                except Exception as exc:
                    if time.monotonic() - self._last_device_heartbeat_error > 8:
                        self.on_event("log",
                            "FUTUREO: sin latido del puente local: " + str(exc)[:160])
                        self._last_device_heartbeat_error = time.monotonic()
            events = self.room.tick()
            for kind, name, slot in events:
                if kind == 'queue_kept':
                    self.on_event('log', f'{name} confirmo que continua en la cola')
                    continue
                if kind in ("turn_finished", "manual_turn", "activation_timeout"):
                    reasons = {
                        "turn_finished": "Turno de 10 min agotado",
                        "manual_turn": "Cambio manual del anfitrion",
                        "activation_timeout": "No pulso ninguna tecla en 10 segundos",
                    }
                    self.on_event("log", f"{reasons[kind]}: {name} deja VJOY{slot} y pasa al final de la cola")
                    with self.room.lock:
                        g = next((g for g in self.room.players.values() if g.name == name), None)
                        if g:
                            message = ("No activaste el mando en 10 segundos. Pasaste al final de la cola."
                                       if kind == "activation_timeout" else
                                       "Turno finalizado. Pasaste al final de la cola.")
                            g.tell({"type": "notice", "level": "warning" if kind == "activation_timeout" else "info",
                                    "message": message})
                elif kind == "assigned":
                    self.on_event("log", f"VJOY{slot}: {name} recibio turno (3, 2, 1 y luego 10s para activar)")
                    with self.room.lock:
                        g = next((g for g in self.room.players.values() if g.name == name), None)
                        if g:
                            g.tell({"type": "notice", "level": "warning",
                                    "message": "Tu turno empieza en 3, 2, 1; despues pulsa una tecla en 10 segundos."})
                elif kind == "activation_ready":
                    self.on_event("log", f"VJOY{slot}: {name}, activacion de 10 segundos iniciada")
                elif kind == "activated":
                    self.on_event("log", f"VJOY{slot}: {name} activo su turno de 10 minutos")
                elif kind == "capacity_queued":
                    self.on_event("log",
                        f"CAPACIDAD: {name} pasa de P{slot} a cola FIFO; tiempo restante conservado")
                elif kind == "capacity_changed":
                    self.on_event("log", f"FUTUREO: capacidad activa {name} mandos")
                elif kind == "input_timeout":
                    self.on_event("log", f"CONTROL P{slot} | {name} | SIN LATIDO: todos los botones liberados")
                elif kind == "last_minute":
                    self.on_event("log", f"Ultimo minuto para {name} P{slot} (si sigue la cola)")
                    with self.room.lock:
                        g = next((g for g in self.room.players.values() if g.name == name), None)
                        if g:
                            g.tell({"type": "notice", "level": "warning",
                                    "message": "Te queda menos de un minuto mientras haya cola."})
            self._state()
            self.stop_event.wait(0.5)

    def change_capacity(self, count: int, extra_modes: dict[int, str] | None = None) -> dict:
        """Solo la GUI puede cambiar la capacidad en vivo, no los visitantes."""
        report = self.room.resize_capacity(count, extra_modes)
        with self._state_lock:
            self._last_state.clear()
            self._last_roster_at = 0.0
        self._state()
        self.on_event('log',
            f"Capacidad en vivo {report['previous']} -> {report['current']}; "
            + f"cola {report['queue']} (sala {self.room.session_id} intacta)")
        return report

    def change_slot_mode(self, slot: int, mode: str) -> bool:
        """Cambio directo desde la GUI, no expuesto a clientes remotos."""
        with self.room.lock:
            victim = self.room.set_slot_mode(slot, mode)
            if victim and victim.socket is not None:
                victim.tell({'type': 'notice', 'level': 'warning',
                             'message': f'El anfitrion reservo VJOY{slot} para mando fisico.'})
            socket = victim.socket if victim else None
        if socket is not None:
            try: socket.close(code=1000, reason=f'VJOY{slot} reservado por anfitrion')
            except Exception: pass
        self._state()
        self.on_event('log', f'VJOY{slot}: modo {mode}' +
                      (f'; visitante {victim.name} desconectado por el anfitrion' if victim else ''))
        return True

    def kick(self, uid: int) -> bool:
        with self.room.lock:
            g = self.room.players.get(uid)
            if g is None:
                return False
            socket = g.socket
            self.room.remove(uid)
        try:
            if socket is not None:
                socket.close(code=1000, reason="Expulsado por el anfitrion")
            return True
        except Exception:
            return False

    def stop(self) -> None:
        self.stream_hub.set_active(False)
        with self.stream_hub.cv:
            self.stream_hub.cv.notify_all()
        self.stop_event.set()
        if self.server:
            try: self.server.shutdown()
            except Exception: pass
        with self.room.lock:
            sockets = [g.socket for g in self.room.players.values() if g.socket is not None]
        for ws in sockets:
            try: ws.close(code=1001, reason="Sala cerrada")
            except Exception: pass
        for thread in (self.worker, self.ticker):
            if thread and thread.is_alive():
                thread.join(timeout=2)
        self.room.close()
        self.on_event("log", "Sala detenida; controles virtuales liberados")


class MultimandoGUI:
    """Administracion EXCLUSIVA en Python/Tkinter; PHP es solo controlador."""
    def __init__(self):
        if sys.platform != "win32":
            raise RuntimeError("La GUI y los joysticks vJoy requieren Windows")
        import tkinter as tk
        from tkinter import ttk, messagebox
        self.tk, self.ttk, self.messagebox = tk, ttk, messagebox
        self.root = tk.Tk()
        self.root.title("MULTIMANDO | ANFITRION v" + VERSION)
        self.root.geometry("1190x900")
        self.root.minsize(850, 680)
        self.root.configure(bg="#0b1424")
        self.events: queue.Queue[tuple[str, Any]] = queue.Queue(maxsize=250)
        self.api_jobs: queue.Queue[str | None] = queue.Queue()
        self.api_thread = threading.Thread(target=self._api_loop, daemon=True, name="MULTIMANDO-API")
        self.api_thread.start()
        self.server: MultimandoServer | None = None
        self.streamer: ScreenBroadcaster | None = None
        self.stream_sources: dict[str, tuple[str, int]] = {}
        self._stream_photo = None
        self.tunnel: subprocess.Popen | None = None
        self.public_address = ""
        self.api_published = ""
        self.member_rows: dict[str, int] = {}
        self.settings = load_local_settings()
        raw_slots = self.settings.get('slots', {})
        if not isinstance(raw_slots, dict):
            raw_slots = {}
        self.slot_configs: dict[int, dict] = {}
        for number in range(1, MAX_PLAYERS + 1):
            raw = raw_slots.get(str(number), {})
            if not isinstance(raw, dict):
                raw = {}
            self.slot_configs[number] = {
                'mode': raw.get('mode') if raw.get('mode') in ('REMOTO', 'CONTROLADO') else 'REMOTO',
                'device': str(raw.get('device') or ''),
                'mapping': raw.get('mapping') if isinstance(raw.get('mapping'), dict) else {},
            }
        self.local_bridge = LocalControllerBridge(self.notify)
        self._last_local_error = 0.0
        self._last_device_scan = 0.0
        self._closing = False
        self._installing_cloudflared = False
        self._capacity_busy = False
        self._theme()
        self._build()
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self.root.after(120, self._drain)
        self.root.after(800, self._refresh)
        self.root.after(30, self._poll_locals)

    def _theme(self) -> None:
        style = self.ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TFrame", background="#0b1424")
        style.configure("TLabel", background="#0b1424", foreground="#eaf2ff",
                        font=("Segoe UI", 10))
        style.configure("Title.TLabel", background="#0b1424", foreground="#ffffff",
                        font=("Segoe UI Semibold", 17))
        style.configure("Muted.TLabel", background="#0b1424", foreground="#9ab4d1",
                        font=("Segoe UI", 9))
        style.configure("TButton", font=("Segoe UI Semibold", 10), padding=(10, 6))
        style.configure("TEntry", padding=6)
        style.configure("Treeview", background="#152c48", fieldbackground="#152c48",
                        foreground="#ecf7ff", rowheight=27, borderwidth=0)
        style.configure("Treeview.Heading", background="#244364", foreground="#ffffff",
                        font=("Segoe UI Semibold", 10))
        style.map("Treeview", background=[("selected", "#3667a4")])

    def _build(self) -> None:
        tk, ttk = self.tk, self.ttk
        self.port_var = tk.StringVar(value=str(DEFAULT_PORT))
        self.status_var = tk.StringVar(value="Servidor cerrado")
        self.url_var = tk.StringVar(value="SIN PUBLICAR")
        self.api_var = tk.StringVar(value="API: no publicada")
        self.room_var = tk.StringVar(value="SALA --")
        self.counter_var = tk.StringVar(value="0 conectados | 0 jugando | cola 0")
        self.player_count_var = tk.StringVar(value=str(DEFAULT_PLAYERS))
        self.pad_var = tk.StringVar(value="Mandos virtuales: sin iniciar")
        self.lan_var = tk.BooleanVar(value=False)
        body = ttk.Frame(self.root)
        body.pack(fill="both", expand=True, padx=14, pady=10)
        head = ttk.Frame(body)
        head.pack(fill="x", pady=(0, 10))
        ttk.Label(head, text="MULTIMANDO", style="Title.TLabel").pack(side="left")
        ttk.Label(head, text="ANFITRION v" + VERSION + "  |  1-8 FUTUREO_VJOY / 10 min con cola",
                  style="Muted.TLabel").pack(side="left", padx=16, pady=7)
        ttk.Label(head, textvariable=self.room_var, style="Muted.TLabel").pack(side="right")

        main_buttons = ttk.Frame(body)
        main_buttons.pack(fill="x", pady=3)
        ttk.Label(main_buttons, text="Puerto:", style="Muted.TLabel").pack(side="left", padx=(0, 4))
        self.port_input = ttk.Entry(main_buttons, textvariable=self.port_var, width=8)
        self.port_input.pack(side="left", padx=(0, 8))
        ttk.Label(main_buttons, text="Jugadores:", style="Muted.TLabel").pack(side="left", padx=(0, 5))
        self.player_select = ttk.Combobox(main_buttons, textvariable=self.player_count_var,
                                          values=tuple(str(n) for n in range(1, MAX_PLAYERS + 1)),
                                          width=3, state="readonly")
        self.player_select.pack(side="left", padx=(0, 4))
        self.capacity_apply_button = ttk.Button(main_buttons, text="APLICAR EN VIVO",
                command=self._apply_capacity, state="disabled")
        self.capacity_apply_button.pack(side="left", padx=(0, 8))
        self.config_vjoy_btn = ttk.Button(main_buttons, text="CONFIGURAR FUTUREO",
                                          command=self._configure_joysticks)
        self.config_vjoy_btn.pack(side="left", padx=(0, 8))
        ttk.Checkbutton(main_buttons, text="Red local", variable=self.lan_var).pack(side="left", padx=(0, 10))
        ttk.Button(main_buttons, text="1. ABRIR SALA", command=self._start_server).pack(side="left", padx=4)
        ttk.Button(main_buttons, text="2. PUBLICAR INTERNET", command=self._start_tunnel).pack(side="left", padx=4)
        ttk.Button(main_buttons, text="CERRAR SALA", command=self._stop_server).pack(side="left", padx=4)

        info = ttk.Frame(body)
        info.pack(fill="x", pady=7)
        ttk.Label(info, textvariable=self.status_var).pack(anchor="w")
        ttk.Label(info, textvariable=self.pad_var, style="Muted.TLabel").pack(anchor="w", pady=2)
        ttk.Label(info, textvariable=self.url_var, style="Muted.TLabel").pack(anchor="w", pady=2)
        ttk.Label(info, textvariable=self.api_var, style="Muted.TLabel").pack(anchor="w", pady=2)
        right_actions = ttk.Frame(body)
        right_actions.pack(fill="x", pady=5)
        ttk.Label(right_actions, textvariable=self.counter_var).pack(side="left")
        ttk.Button(right_actions, text="COPIAR ENLACE", command=self._copy).pack(side="right", padx=3)
        ttk.Button(right_actions, text="REENVIAR API", command=self._resend).pack(side="right", padx=3)
        self._build_stream_panel(body)

        panel = ttk.Frame(body)
        panel.pack(fill="both", expand=True, pady=(4, 7))
        columns = ("slot", "username", "id", "seconds", "condition")
        self.table = ttk.Treeview(panel, columns=columns, show="headings", selectmode="browse")
        for key, label, width in (("slot", "Mando vJoy", 155), ("username", "Jugador", 260),
                                   ("id", "ID", 60), ("seconds", "Tiempo", 135),
                                   ("condition", "Reloj", 160)):
            self.table.heading(key, text=label)
            self.table.column(key, width=width, minwidth=50, stretch=True,
                              anchor="w" if key == "username" else "center")
        self.table.pack(side="left", fill="both", expand=True)
        scroller = ttk.Scrollbar(panel, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scroller.set)
        scroller.pack(side="right", fill="y")
        actions = ttk.Frame(body)
        actions.pack(fill="x", pady=4)
        ttk.Label(actions, text="Pasar turno:", style="Muted.TLabel").pack(side="left")
        self.rotate_buttons = {}
        for slot in range(1, MAX_PLAYERS + 1):
            button = ttk.Button(actions, text=f"P{slot}", command=lambda n=slot: self._rotate(n))
            button.pack(side="left", padx=2)
            self.rotate_buttons[slot] = button
        utility = ttk.Frame(body)
        utility.pack(fill='x', pady=(4, 3))
        ttk.Button(utility, text="EXPULSAR JUGADOR SELECCIONADO", command=self._kick).pack(side='left', padx=(0, 16))
        ttk.Label(utility, text="Identificar joystick:", style="Muted.TLabel").pack(side='left', padx=(0, 5))
        self.identify_var = tk.StringVar(value='FUTUREO_VJOY1')
        self.identify_select = ttk.Combobox(utility, textvariable=self.identify_var,
              state='readonly', width=17, values=['FUTUREO_VJOY1', 'FUTUREO_VJOY2'])
        self.identify_select.pack(side='left', padx=(0, 6))
        self.identify_button = ttk.Button(utility, text="IDENTIFICAR (boton 8)", command=self._identify)
        self.identify_button.pack(side='left', padx=3)
        ttk.Label(utility, text='Usar al configurar controles del juego', style='Muted.TLabel').pack(side='left', padx=10)
        self.player_select.bind('<<ComboboxSelected>>', lambda _e: self._refresh_rotate_buttons())
        self._refresh_rotate_buttons()
        ttk.Label(body, text="REGISTRO DE EVENTOS", style="Muted.TLabel").pack(anchor="w", pady=(5, 2))
        self.log = tk.Text(body, height=6, wrap="word", bg="#09172b", fg="#bde4ff",
                           insertbackground="white", relief="flat", font=("Consolas", 9), state="disabled")
        self.log.pack(fill="x")
        self._log("Los visitantes usan solo la palanca PHP; los turnos se controlan aqui.")
        self._log("Acciones: ar/ab/iz/de + button_a/button_b/button_x/button_y/button_lb/button_rb + start/select.")
        self._log("Requiere FUTUREO VJOY v0.8.4 abierto e iniciado y Python websockets/pygame.")
        self._log("Selecciona 1-8 jugadores y pulsa APLICAR EN VIVO incluso con sala abierta.")
        self._log("CONFIGURAR FUTUREO: REMOTO o CONTROLADO + mando fisico por puesto.")

    def _build_stream_panel(self, parent: Any) -> None:
        tk, ttk = self.tk, self.ttk
        frame = ttk.LabelFrame(parent, text="TRANSMISION PUBLICA - visible sin conectarse y tambien en cola")
        frame.pack(fill="x", pady=(5, 6))
        left = ttk.Frame(frame)
        left.pack(side="left", fill="both", expand=True, padx=8, pady=6)
        self.stream_source_var = tk.StringVar(value="Selecciona una fuente")
        self.stream_size_var = tk.StringVar(value="480x270")
        self.stream_fps_var = tk.StringVar(value="10")
        self.stream_quality_var = tk.StringVar(value="50")
        self.stream_status_var = tk.StringVar(value="Sin transmitir; espectadores reciben imagen automaticamente.")
        source_row = ttk.Frame(left)
        source_row.pack(fill="x", pady=2)
        ttk.Label(source_row, text="Ventana o pantalla:").pack(side="left", padx=(0, 5))
        self.stream_source_select = ttk.Combobox(
            source_row, textvariable=self.stream_source_var, width=49, state="readonly")
        self.stream_source_select.pack(side="left", fill="x", expand=True)
        ttk.Button(source_row, text="BUSCAR", command=self._stream_refresh_sources).pack(side="left", padx=5)
        options = ttk.Frame(left)
        options.pack(fill="x", pady=4)
        for label, var, choices in (
            ("Tamano", self.stream_size_var, ("320x180", "480x270", "640x360")),
            ("FPS", self.stream_fps_var, ("1", "2", "5", "10", "15", "20")),
            ("Calidad JPEG", self.stream_quality_var, ("30", "40", "55", "70", "80"))):
            ttk.Label(options, text=label + ":").pack(side="left", padx=(5, 4))
            ttk.Combobox(options, textvariable=var, values=choices,
                         state="readonly", width=9 if label == "Tamano" else 4).pack(side="left")
        buttons = ttk.Frame(left)
        buttons.pack(fill="x", pady=3)
        ttk.Button(buttons, text="MODO RAPIDO", command=self._stream_fast_preset).pack(side="left", padx=4)
        ttk.Button(buttons, text="INICIAR TRANSMISION", command=self._stream_start).pack(side="left", padx=4)
        ttk.Button(buttons, text="DETENER", command=self._stream_stop).pack(side="left", padx=4)
        ttk.Label(buttons, textvariable=self.stream_status_var, style="Muted.TLabel").pack(side="left", padx=8)
        self.stream_preview_label = tk.Label(
            frame, text="VISTA PREVIA\\nSin imagen", width=31, height=7,
            bg="#122745", fg="#d1ecff", relief="groove")
        self.stream_preview_label.pack(side="right", padx=8, pady=6)
        try:
            self._stream_refresh_sources()
        except Exception as exc:
            self.stream_status_var.set("Error al enumerar fuentes: " + str(exc)[:90])

    def _stream_refresh_sources(self) -> None:
        sources = list_sources()
        self.stream_sources = {}
        labels = []
        for label, kind, value in sources:
            name = label
            suffix = 2
            while name in self.stream_sources:
                name = f"{label} ({suffix})"
                suffix += 1
            self.stream_sources[name] = (kind, value)
            labels.append(name)
        self.stream_source_select.configure(values=labels)
        if self.stream_source_var.get() not in self.stream_sources:
            self.stream_source_var.set(labels[0] if labels else "No hay ventanas visibles")

    def _stream_fast_preset(self) -> None:
        """Baja latencia con poco ancho de banda; aplicar al reiniciar el stream."""
        if self.streamer and self.streamer.running:
            self.messagebox.showinfo("BAJA LATENCIA",
                "Deten la transmision para cambiar de perfil y vuelve a INICIAR.")
            return
        self.stream_size_var.set("320x180")
        self.stream_fps_var.set("15")
        self.stream_quality_var.set("40")
        self.stream_status_var.set("Perfil rapido: 320x180 | 15 FPS | JPEG 40")

    def _stream_start(self) -> None:
        if self.server is None:
            self.messagebox.showwarning("TRANSMISION", "Primero pulsa ABRIR SALA.")
            return
        source = self.stream_sources.get(self.stream_source_var.get())
        if not source:
            self.messagebox.showwarning("TRANSMISION", "Selecciona una ventana o pantalla.")
            return
        try:
            width, height = map(int, self.stream_size_var.get().split("x"))
            fps, quality = int(self.stream_fps_var.get()), int(self.stream_quality_var.get())
            if self.streamer and self.streamer.running:
                self.messagebox.showinfo("TRANSMISION", "Deten la transmision antes de cambiar.")
                return
            self.streamer = ScreenBroadcaster(
                self.server.stream_hub,
                preview=lambda jpeg: self.notify("stream_preview", jpeg),
                notice=lambda message: self.notify("stream_notice", message),
                telemetry=lambda data: self.notify("stream_metrics", data))
            self.streamer.start(source[0], source[1], (width, height), fps, quality)
            self.stream_status_var.set(f"EN VIVO | {width}x{height} | {fps} FPS | JPEG {quality}")
            self._log("Transmision v2.2 publica sin cola: JPEG actualizado y frames antiguos descartados")
        except Exception as exc:
            self.messagebox.showerror("No se pudo capturar", str(exc))

    def _stream_stop(self) -> None:
        if self.streamer:
            self.streamer.stop()
        self.stream_status_var.set("Transmision detenida")
        self.stream_preview_label.configure(image="", text="VISTA PREVIA\\nSin imagen")
        self._stream_photo = None

    def _log(self, message: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", "[" + time.strftime("%H:%M:%S") + "] " + message + "\n")
        if int(self.log.index("end-1c").split(".")[0]) > 750:
            self.log.delete("1.0", "151.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    def notify(self, kind: str, data: Any) -> None:
        try: self.events.put_nowait((kind, data))
        except queue.Full: pass

    def _refresh_rotate_buttons(self) -> None:
        count = self.server.room.slot_count if self.server else int(self.player_count_var.get())
        for slot, button in self.rotate_buttons.items():
            mode = self.server.room.slot_modes[slot] if self.server and slot <= count else self.slot_configs[slot]['mode']
            button.configure(state='normal' if self.server and slot <= count and mode == 'REMOTO' else 'disabled')
        available = [f'FUTUREO_VJOY{n}' for n in range(1, count + 1)]
        self.identify_select.configure(values=available)
        if self.identify_var.get() not in available:
            self.identify_var.set(available[0])
        self.identify_button.configure(state='normal' if self.server else 'disabled')

    def _poll_locals(self) -> None:
        """Leer mandos fisicos a ~33 Hz; no bloquear WebSockets ni cola FIFO."""
        if self._closing:
            return
        try:
            host = self.server
            if host and any(m == 'CONTROLADO' for m in host.room.slot_modes.values()):
                if time.monotonic() - self._last_device_scan > 6.0:
                    self._last_device_scan = time.monotonic()
                    self.local_bridge.scan()
                self.local_bridge.poll(host.room, self.slot_configs)
        except Exception as exc:
            if time.monotonic() - self._last_local_error > 8.0:
                self._log('Control local: ' + str(exc)[:120])
                self._last_local_error = time.monotonic()
        finally:
            if not self._closing:
                self.root.after(30, self._poll_locals)

    def _configure_joysticks(self) -> None:
        """Pantalla por puesto: REMOTO (cola) o CONTROLADO (mando USB/Wi-Fi)."""
        tk, ttk = self.tk, self.ttk
        count = self.server.room.slot_count if self.server else int(self.player_count_var.get())
        try:
            devices = self.local_bridge.scan()
            discovery_error = ''
        except Exception as exc:
            devices = []
            discovery_error = str(exc)
        draft = {slot: {
            'mode': self.slot_configs[slot]['mode'],
            'device': self.slot_configs[slot]['device'],
            'mapping': dict(self.slot_configs[slot]['mapping'])
        } for slot in range(1, count + 1)}
        window = tk.Toplevel(self.root)
        window.title('MULTIMANDO - Configurar dispositivos VJOY')
        window.geometry('865x620')
        window.minsize(760, 470)
        window.transient(self.root)
        window.configure(bg='#0b1424')
        window.grab_set()
        head = ttk.Frame(window)
        head.pack(fill='x', padx=15, pady=(14, 7))
        ttk.Label(head, text=f'CONFIGURAR {count} JOYSTICKS VJOY', style='Title.TLabel').pack(anchor='w')
        ttk.Label(head, text='REMOTO = asignado al jugador P del mismo numero; CONTROLADO = mando USB/Wi-Fi local.',
                  style='Muted.TLabel').pack(anchor='w')
        if discovery_error:
            ttk.Label(head, text='Aviso: ' + discovery_error[:125], style='Muted.TLabel').pack(anchor='w')
        ttk.Label(head, text='Puedes cambiar un VJOY con la sala abierta: si era REMOTO, el anfitrion expulsara a su usuario.',
                  style='Muted.TLabel').pack(anchor='w')
        controls = ttk.Frame(window)
        controls.pack(fill='both', expand=True, padx=15, pady=6)
        ttk.Label(controls, text='MANDO').grid(row=0, column=0, sticky='w', padx=5)
        ttk.Label(controls, text='MODO').grid(row=0, column=1, sticky='w', padx=5)
        ttk.Label(controls, text='DISPOSITIVO FISICO').grid(row=0, column=2, sticky='w', padx=5)
        mode_vars = {}
        device_vars = {}
        for slot in draft:
            mode_var = tk.StringVar(value=draft[slot]['mode'])
            device_var = tk.StringVar(value=draft[slot]['device'])
            mode_vars[slot] = mode_var
            device_vars[slot] = device_var
            ttk.Label(controls, text=f'P{slot} = VJOY{slot}').grid(row=slot, column=0, sticky='w', padx=5, pady=7)
            mode_box = ttk.Combobox(controls, textvariable=mode_var, values=('REMOTO', 'CONTROLADO'),
                                    width=13, state='readonly')
            mode_box.grid(row=slot, column=1, sticky='w', padx=5, pady=7)
            options = list(devices)
            if device_var.get() and device_var.get() not in options:
                options.insert(0, device_var.get())
            device_box = ttk.Combobox(controls, textvariable=device_var, values=options,
                                      state='readonly', width=45)
            device_box.grid(row=slot, column=2, sticky='ew', padx=5, pady=7)
            map_button = ttk.Button(controls, text='MAPEAR BOTONES',
                                    command=lambda n=slot: self._edit_local_mapping(window, n, draft[n], device_vars[n].get()))
            map_button.grid(row=slot, column=3, sticky='e', padx=5, pady=7)
            def sync(_event=None, *, n=slot, field=device_box, mapping=map_button):
                enabled = mode_vars[n].get() == 'CONTROLADO'
                field.configure(state='readonly' if enabled else 'disabled')
                mapping.configure(state='normal' if enabled else 'disabled')
            mode_box.bind('<<ComboboxSelected>>', sync)
            sync()
        controls.columnconfigure(2, weight=1)
        foot = ttk.Frame(window)
        foot.pack(fill='x', padx=16, pady=15)
        ttk.Label(foot, text='La seleccion se guarda en multimando_config.json, junto al anfitrion.',
                  style='Muted.TLabel').pack(side='left')
        ttk.Button(foot, text='CANCELAR', command=window.destroy).pack(side='right', padx=5)
        def save():
            selected = []
            for slot in draft:
                draft[slot]['mode'] = mode_vars[slot].get()
                draft[slot]['device'] = device_vars[slot].get().strip()
                if draft[slot]['mode'] == 'CONTROLADO':
                    if not draft[slot]['device'] or draft[slot]['device'] not in devices:
                        self.messagebox.showwarning('Mando fisico requerido',
                            f'VJOY{slot}: conecta y selecciona un mando fisico detectado.', parent=window)
                        return
                    selected.append(draft[slot]['device'])
            if len(selected) != len(set(selected)):
                self.messagebox.showwarning('Mando duplicado',
                    'No asignes un mismo mando fisico a dos puestos.', parent=window)
                return
            for slot, cfg in draft.items():
                old_mode = (self.server.room.slot_modes[slot] if self.server else
                            self.slot_configs[slot]['mode'])
                self.slot_configs[slot] = cfg
                self.local_bridge.reset_slot(slot)
                if self.server and cfg['mode'] != old_mode:
                    self.server.change_slot_mode(slot, cfg['mode'])
            try:
                save_local_settings({'slots': {str(n): self.slot_configs[n]
                                               for n in range(1, MAX_PLAYERS + 1)}})
            except OSError as exc:
                self.messagebox.showwarning('No se guardo el perfil', str(exc), parent=window)
            window.destroy()
            self._refresh_rotate_buttons()
            if self.server:
                self._roster(self.server.room.snapshot())
            self._log('Configuracion de mandos VJOY actualizada')
        ttk.Button(foot, text='GUARDAR Y APLICAR', command=save).pack(side='right', padx=5)
        window.wait_window()

    def _edit_local_mapping(self, parent: Any, slot: int, cfg: dict, device: str) -> None:
        """Asigna cada boton fisico a la accion VJOY, con aprendizaje por pulsacion."""
        tk, ttk = self.tk, self.ttk
        if not device or device not in self.local_bridge.physical:
            self.messagebox.showwarning('Selecciona un mando',
                                        'Elige primero un mando USB o Wi-Fi conectado.', parent=parent)
            return
        try:
            initial = self.local_bridge.mapping_for(cfg)
        except (ValueError, TypeError):
            initial = self.local_bridge.mapping_for({})
        dlg = tk.Toplevel(parent)
        dlg.title(f'MAPEAR MANDO LOCAL VJOY{slot}')
        dlg.geometry('490x640')
        dlg.transient(parent)
        dlg.grab_set()
        frame = ttk.Frame(dlg)
        frame.pack(fill='both', expand=True, padx=16, pady=12)
        ttk.Label(frame, text=f'VJOY{slot} ← {device[:44]}', style='Title.TLabel').pack(anchor='w', pady=(0, 8))
        ttk.Label(frame, text='Numeros de boton desde 0. APRENDER detecta la siguiente pulsacion.',
                  style='Muted.TLabel').pack(anchor='w', pady=(0, 10))
        names = {'button_a': 'A', 'button_b': 'B', 'button_x': 'X', 'button_y': 'Y',
                 'button_lb': 'LB', 'button_rb': 'RB', 'start': 'START', 'select': 'SELECT'}
        area = ttk.Frame(frame)
        area.pack(fill='x')
        vars_buttons = {}
        message = tk.StringVar(value='Selecciona APRENDER y pulsa un boton fisico.')
        learning = {'token': 0}
        for row, (action, title) in enumerate(names.items()):
            v = tk.StringVar(value=str(initial['buttons'].get(action, -1)))
            vars_buttons[action] = v
            ttk.Label(area, text=title).grid(row=row, column=0, sticky='w', pady=4)
            ttk.Combobox(area, textvariable=v, state='readonly', width=8,
                         values=tuple(str(i) for i in range(-1, 64))).grid(row=row, column=1, pady=4, padx=(8, 16))
            def learn(key=action, var=v):
                learning['token'] += 1
                token = learning['token']
                joy = self.local_bridge.physical[device]['joy']
                try:
                    self.local_bridge.pygame.event.pump()
                    held_at_start = {i for i in range(joy.get_numbuttons()) if joy.get_button(i)}
                except Exception:
                    message.set('No se pudo leer el mando fisico.')
                    return
                message.set(f'Pulsa un boton nuevo para {names[key]}... (10 s)')
                expires = time.monotonic() + 10.0
                def poll_learn():
                    nonlocal held_at_start
                    if token != learning['token'] or not dlg.winfo_exists():
                        return
                    if time.monotonic() > expires:
                        message.set('Tiempo agotado. Reintenta APRENDER.')
                        return
                    try:
                        self.local_bridge.pygame.event.pump()
                        active = {i for i in range(joy.get_numbuttons()) if joy.get_button(i)}
                        newly_pressed = sorted(active - held_at_start)
                        if newly_pressed:
                            var.set(str(newly_pressed[0])); learning['token'] += 1
                            message.set(f'{names[key]} asignado a boton {newly_pressed[0]}.')
                            return
                        held_at_start = active
                    except Exception:
                        message.set('Error leyendo el mando.')
                        return
                    dlg.after(65, poll_learn)
                dlg.after(65, poll_learn)
            ttk.Button(area, text='APRENDER', command=learn).grid(row=row, column=2, pady=4)
        message_label = ttk.Label(frame, textvariable=message, style='Muted.TLabel')
        message_label.pack(anchor='w', pady=8)
        extra = ttk.Frame(frame)
        extra.pack(fill='x', pady=5)
        axis_x = tk.StringVar(value=str(initial['axis_x']))
        axis_y = tk.StringVar(value=str(initial['axis_y']))
        ttk.Label(extra, text='Eje X').grid(row=0, column=0, sticky='w', padx=3)
        ttk.Combobox(extra, textvariable=axis_x, state='readonly', width=5,
                     values=tuple(str(i) for i in range(-1, 16))).grid(row=0, column=1, padx=5)
        ttk.Label(extra, text='Eje Y').grid(row=0, column=2, sticky='w', padx=5)
        ttk.Combobox(extra, textvariable=axis_y, state='readonly', width=5,
                     values=tuple(str(i) for i in range(-1, 16))).grid(row=0, column=3, padx=3)
        use_hat = tk.BooleanVar(value=initial['hat'])
        invert_y = tk.BooleanVar(value=initial['invert_y'])
        ttk.Checkbutton(extra, text='Cruceta fisica (HAT)', variable=use_hat).grid(row=1, column=0, columnspan=2, sticky='w', pady=8)
        ttk.Checkbutton(extra, text='Invertir eje Y', variable=invert_y).grid(row=1, column=2, columnspan=2, sticky='w')
        deadzone = tk.IntVar(value=round(initial['deadzone'] * 100))
        ttk.Label(extra, text='Zona muerta %').grid(row=2, column=0, sticky='w')
        ttk.Spinbox(extra, from_=5, to=45, increment=1, textvariable=deadzone, width=6).grid(row=2, column=1, sticky='w')
        buttons_row = ttk.Frame(frame)
        buttons_row.pack(fill='x', pady=8)
        def save():
            learning['token'] += 1
            cfg['mapping'] = {
                'buttons': {k: int(var.get()) for k, var in vars_buttons.items()},
                'axis_x': int(axis_x.get()), 'axis_y': int(axis_y.get()),
                'hat': use_hat.get(), 'invert_y': invert_y.get(),
                'deadzone': max(.05, min(.45, deadzone.get() / 100)),
            }
            dlg.destroy()
        ttk.Button(buttons_row, text='CANCELAR', command=dlg.destroy).pack(side='left')
        ttk.Button(buttons_row, text='GUARDAR MAPEO', command=save).pack(side='right')
        dlg.wait_window()


    def _apply_capacity(self) -> None:
        """Cambia cantidad de P1..P8 sin desconectar sala, web o tunel."""
        host = self.server
        if host is None or self._capacity_busy:
            return
        try:
            target = int(self.player_count_var.get())
        except ValueError:
            self.messagebox.showwarning("FUTUREO", "Selecciona 1 a 8 jugadores.")
            return
        if not 1 <= target <= MAX_PLAYERS:
            self.messagebox.showwarning("FUTUREO", "La capacidad debe ser entre 1 y 8.")
            return
        previous = host.room.slot_count
        if previous == target:
            self._log(f"Capacidad ya establecida en {target} jugadores.")
            return

        modes = {
            slot: self.slot_configs[slot]['mode']
            for slot in range(previous + 1, target + 1)
        }
        if target > previous:
            local = [
                self.slot_configs[slot]['device']
                for slot in range(previous + 1, target + 1)
                if modes[slot] == 'CONTROLADO'
            ]
            existing = [
                self.slot_configs[slot]['device'] for slot in host.room.slots
                if host.room.slot_modes.get(slot) == 'CONTROLADO'
            ]
            if local:
                try:
                    found = set(self.local_bridge.scan())
                except Exception as exc:
                    self.messagebox.showerror("Mando fisico", str(exc))
                    return
                if any(not name or name not in found for name in local):
                    self.messagebox.showerror("Mando fisico",
                        "Selecciona y conecta un mando USB/Wi-Fi para cada nuevo CONTROLADO.")
                    return
                if len(local + existing) != len(set(local + existing)):
                    self.messagebox.showerror("Mando fisico",
                        "No se puede asignar el mismo mando a dos puestos.")
                    return
        else:
            # Users on slots > target are queued without disconnecting.
            with host.room.lock:
                displaced = sorted(
                    (p.name for p in host.room.players.values() if p.slot > target))
            if displaced:
                names = ", ".join(displaced[:5])
                if len(displaced) > 5:
                    names += f" y {len(displaced) - 5} mas"
                if not self.messagebox.askyesno(
                        "Reducir capacidad sin cerrar sala",
                        f"La sala pasara de {previous} a {target} jugadores.\n"
                        f"Estos jugadores pasaran a la cola: {names}.\n"
                        "Conservaran sus segundos restantes y no se cerraran sus conexiones.\n"
                        "Los jugadores de los puestos que permanecen seguiran jugando.\n\n"
                        "¿Aplicar el cambio?"):
                    self.player_count_var.set(str(previous))
                    return

        self._capacity_busy = True
        self.player_select.configure(state='disabled')
        self.capacity_apply_button.configure(state='disabled')
        self.status_var.set(f"Actualizando capacidad {previous} -> {target}, sala sigue abierta...")
        self._log(f"Solicitando capacidad EN VIVO: {previous} -> {target} FUTUREO_VJOY.")
        def worker():
            try:
                result = host.change_capacity(target, modes)
                self.notify('capacity_done', (host, target, result, None))
            except Exception as exc:
                self.notify('capacity_done', (host, target, None, str(exc)))
        threading.Thread(target=worker, daemon=True,
                         name="MULTIMANDO-FUTUREO-Resize").start()

    def _start_server(self) -> None:
        if self.server:
            self._log("La sala ya esta abierta")
            return
        try:
            port = int(self.port_var.get())
            if not 1024 <= port <= 65535:
                raise ValueError("Puerto fuera del rango 1024-65535")
            count = int(self.player_count_var.get())
            if not 1 <= count <= MAX_PLAYERS:
                raise ValueError("Selecciona entre 1 y 8 jugadores")
            modes = {slot: self.slot_configs[slot]['mode'] for slot in range(1, count + 1)}
            local_devices = [self.slot_configs[n]['device'] for n in modes if modes[n] == 'CONTROLADO']
            if local_devices:
                discovered = set(self.local_bridge.scan())
                if len(set(local_devices)) != len(local_devices):
                    raise ValueError('No puedes asignar el mismo mando fisico a dos VJOY.')
                missing = [name for name in local_devices if name not in discovered]
                if missing:
                    raise ValueError('Conecta tu mando USB/Wi-Fi y vuelve a configurar: ' + ', '.join(missing))
            device = VirtualFutureoPads(count)
            try:
                host = MultimandoServer(port, device, self.notify, bind_lan=self.lan_var.get(),
                                        slot_modes=modes)
                host.start()
            except Exception:
                device.close()
                raise
            self.server = host
            self.port_input.configure(state="disabled")
            self.player_select.configure(state="readonly")
            self.capacity_apply_button.configure(state="normal")
            self._refresh_rotate_buttons()
            self.status_var.set("Sala abierta - unirse por el enlace publico o por red local")
            self.room_var.set("SALA " + host.room.session_id)
            self.pad_var.set(f"{count} mandos FUTUREO activos: " +
                             ", ".join(f"FUTUREO_VJOY{n}" for n in range(1, count + 1)))
            self.url_var.set(f"LOCAL: ws://127.0.0.1:{port}")
            self.api_var.set("API: abre PUBLICAR INTERNET para registrar la sala")
            self._log(f"{count} dispositivos FUTUREO_VJOY listos; no se usa pyvjoystick ni el driver vJoy clasico.")
        except Exception as exc:
            self.messagebox.showerror("No se pudo abrir la sala", str(exc))

    def _start_tunnel(self) -> None:
        if self.server is None:
            self.messagebox.showwarning("Abre la sala", "Primero pulsa ABRIR SALA")
            return
        if self.tunnel and self.tunnel.poll() is None:
            self._log("El tunel ya esta activo")
            return
        executable = find_cloudflared()
        if not executable:
            if self._installing_cloudflared:
                self._log("La instalacion automatica de Cloudflare continua...")
                return
            self._installing_cloudflared = True
            self.api_var.set("Cloudflare ausente: instalando automaticamente...")
            self._log("Cloudflare no esta instalado; iniciando instalacion automatica")
            threading.Thread(target=self._install_cloudflared_worker, daemon=True,
                             name="MULTIMANDO-Instalador-Cloudflare").start()
            return
        self.public_address = ""
        self.api_var.set("API: esperando enlace Cloudflare...")
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            self.tunnel = subprocess.Popen([
                executable, "tunnel", "--no-autoupdate", "--url",
                f"http://127.0.0.1:{self.server.port}"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                encoding="utf-8", errors="replace", bufsize=1, creationflags=flags)
            threading.Thread(target=self._read_tunnel, args=(self.tunnel,), daemon=True,
                             name="MULTIMANDO-Cloudflare").start()
            self._log("Creando enlace Quick Tunnel...")
        except Exception as exc:
            self.messagebox.showerror("Cloudflare", str(exc))

    def _install_cloudflared_worker(self) -> None:
        """No bloquear Tkinter mientras winget instala o descarga."""
        try:
            executable = ensure_cloudflared(lambda text: self.notify("log", text))
            self.notify("cloudflared_ready", executable)
        except Exception as exc:
            self.notify("cloudflared_failed", str(exc))

    def _read_tunnel(self, process: subprocess.Popen) -> None:
        seen = set()
        try:
            for line in process.stdout or ():
                match = URL_REGEX.search(line)
                if match and match.group(0) not in seen:
                    seen.add(match.group(0))
                    self.notify("public_url", (process, match.group(0)))
                elif " ERR " in line:
                    self.notify("log", "Cloudflare: " + line.strip()[:140])
        except Exception as exc:
            self.notify("log", "Cloudflare: " + str(exc))
        finally:
            self.notify("tunnel_closed", process)

    def _api_loop(self) -> None:
        while True:
            value = self.api_jobs.get()
            if value is None:
                return
            try:
                if value:
                    publish_url(value)
                    confirmed = ""
                    for attempt in range(3):
                        confirmed = get_published_url()
                        if confirmed == valid_public_url(value):
                            break
                        if attempt < 2:
                            time.sleep(0.35)
                    if confirmed != valid_public_url(value):
                        self.notify("api", "API: POST aceptado, pero GET devuelve otra URL")
                        self.notify("log", "Revisa si las rutas Laravel leen amo_multimando.url")
                    else:
                        self.api_published = valid_public_url(value)
                        self.notify("api", "API: POST/GET verificados, AUTO disponible")
                else:
                    # No borrar el enlace de otro anfitrion o uno actualizado por un tercero.
                    current = get_published_url()
                    if self.api_published and current == self.api_published:
                        publish_url("")
                        self.api_published = ""
                        self.notify("api", "API: enlace retirado")
                    else:
                        self.notify("log", "La API usa otro enlace o estaba vacia; no se borro")
            except (HTTPError, URLError, ValueError, RuntimeError, OSError) as exc:
                self.notify("api", "API: error " + str(exc)[:110])
                self.notify("log", "Error de API MULTIMANDO: " + str(exc)[:130])

    def _resend(self) -> None:
        if self.public_address:
            self.api_jobs.put(self.public_address)
            self._log("Reenviando URL a la API...")
        else:
            self.messagebox.showinfo("Falta URL", "Publica primero el enlace Cloudflare")

    def _copy(self) -> None:
        if not self.public_address:
            self.messagebox.showinfo("Falta URL", "Publica primero con Cloudflare")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(self.public_address)
        self.root.update()
        self._log("Enlace copiado al portapapeles")

    def _rotate(self, slot: int) -> None:
        if not self.server:
            return
        if self.server.room.rotate_slot(slot):
            self.server._state()
            self._log(f"Cambio manual VJOY{slot} (P{slot}): nuevo jugador por FIFO")
        else:
            self._log(f"VJOY{slot}: no hay cola para ceder el mando")

    def _identify(self) -> None:
        server = self.server
        if not server:
            return
        try:
            slot = int(self.identify_var.get().removeprefix('FUTUREO_VJOY'))
        except ValueError:
            return
        if slot not in server.room.slots:
            return
        if any(g.slot == slot for g in server.room.players.values()):
            if not self.messagebox.askyesno('Prueba de joystick',
                 f'VJOY{slot} esta ocupado. La prueba liberara sus teclas y presionara '
                 'SELECT (boton 8) durante un instante. ¿Continuar?'):
                return
        self.identify_button.configure(state='disabled')
        def run_identify():
            try:
                ok = server.room.identify_slot(slot)
                message = (f'VJOY{slot}: boton 8 pulsado y liberado. '
                           'Identificalo en la pantalla de asignacion del juego.' if ok
                           else f'VJOY{slot}: identificacion no disponible')
            except Exception as exc:
                message = f'VJOY{slot}: fallo de prueba: {exc}'
            self.notify('log', message)
            self.notify('identify_complete', True)
        threading.Thread(target=run_identify, daemon=True,
                         name=f'MULTIMANDO-Identify-VJOY{slot}').start()

    def _kick(self) -> None:
        if not self.server:
            return
        selection = self.table.selection()
        uid = self.member_rows.get(selection[0]) if selection else None
        if uid and self.server.kick(uid):
            self._log(f"Expulsando usuario ID {uid}")

    def _refresh(self) -> None:
        try:
            if self.server:
                self._roster(self.server.room.snapshot())
        except Exception as exc:
            self._log("Error al refrescar lista: " + str(exc)[:85])
        if not self._closing:
            self.root.after(800, self._refresh)

    def _roster(self, data: dict) -> None:
        current = self.table.selection()
        selected_uid = self.member_rows.get(current[0]) if current else None
        view = self.table.yview()
        for row in self.table.get_children():
            self.table.delete(row)
        self.member_rows.clear()
        players = data.get("players", {})
        waiting = data.get("queue", [])
        count = int(data.get('slot_count') or int(self.player_count_var.get()))
        playing = sum(players.get(str(n)) is not None for n in range(1, count + 1))
        remote_count = int(data.get('remote_count', count))
        local_count = count - remote_count
        self.counter_var.set(f"{data.get('total', 0)} conectados | "
                             f"Remotos: {playing}/{remote_count} | Locales: {local_count} | Cola: {len(waiting)}")
        for slot in range(1, count + 1):
            g = players.get(str(slot))
            position = f"P{slot} / FUTUREO_VJOY{slot}"
            if data.get('slot_modes', {}).get(str(slot), self.slot_configs[slot]['mode']) == 'CONTROLADO':
                local_name = self.slot_configs[slot]['device'] or 'SIN ASIGNAR'
                self.table.insert('', 'end', values=(position, local_name[:32], 'LOCAL', '---', 'CONTROLADO USB/WI-FI'))
                continue
            if g:
                remaining = int(g["remaining_seconds"])
                mm, ss = divmod(remaining, 60)
                if g.get("countdown_seconds", 0) > 0:
                    status = "INICIA EN 3, 2, 1"
                    remaining = int(g.get("countdown_seconds", 0))
                    mm, ss = divmod(remaining, 60)
                elif g.get("activation_pending"):
                    status = "ACTIVAR EN 10 S"
                    remaining = int(g.get("activation_seconds", 0))
                    mm, ss = divmod(remaining, 60)
                else:
                    status = "CONTANDO" if g.get("timer_running") else "PAUSADO (sin cola)"
                item = self.table.insert("", "end", values=(
                    position, g["name"], g["id"], f"{mm:02d}:{ss:02d}", status))
                self.member_rows[item] = g["id"]
            else:
                self.table.insert("", "end", values=(position, "LIBRE", "—", "—", "DISPONIBLE"))
        for order, g in enumerate(waiting, 1):
            item = self.table.insert("", "end", values=(
                f"COLA #{order}", g["name"], g["id"], "10:00 al entrar", "ESPERANDO"))
            self.member_rows[item] = g["id"]
        for row, uid in self.member_rows.items():
            if uid == selected_uid:
                self.table.selection_set(row)
                self.table.focus(row)
                break
        if view:
            self.table.yview_moveto(view[0])

    def _drain(self) -> None:
        for _ in range(100):
            try:
                kind, payload = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "log":
                self._log(str(payload))
            elif kind == "roster":
                self._roster(payload)
            elif kind == "stream_metrics":
                if self.streamer and self.streamer.running:
                    stats = payload
                    self.stream_status_var.set(
                        f"REAL: {stats['fps']:.1f} FPS | captura {stats['capture_ms']:.1f} ms | "
                        f"{stats['jpeg_kb']:.1f} KB/frame | espectadores {stats['viewers']}")
            elif kind == "stream_notice":
                self.stream_status_var.set(str(payload))
                self._log(str(payload))
            elif kind == "stream_preview":
                try:
                    from PIL import Image, ImageTk
                    import io
                    im = Image.open(io.BytesIO(payload))
                    im.thumbnail((240, 135), Image.Resampling.BILINEAR)
                    self._stream_photo = ImageTk.PhotoImage(im, master=self.root)
                    self.stream_preview_label.configure(image=self._stream_photo, text="")
                except Exception:
                    pass
            elif kind == "api":
                self.api_var.set(str(payload))
            elif kind == 'identify_complete':
                self._refresh_rotate_buttons()
            elif kind == 'capacity_done':
                host, requested, result, error = payload
                self._capacity_busy = False
                self.player_select.configure(state='readonly')
                self.capacity_apply_button.configure(state='normal' if self.server else 'disabled')
                if host is self.server and self.server is not None:
                    actual = host.room.slot_count
                    self.player_count_var.set(str(actual))
                    self._refresh_rotate_buttons()
                    self.pad_var.set(
                        f"{actual} FUTUREO_VJOY activos: "
                        + ", ".join(f"FUTUREO_VJOY{n}" for n in range(1, actual + 1)))
                    self._roster(host.room.snapshot())
                    if error:
                        self.status_var.set(f"Sala abierta - capacidad {actual} (fallo al aplicar)")
                        self._log("ERROR ajustando capacidad: " + error)
                        self.messagebox.showerror("FUTUREO - Capacidad", error)
                    else:
                        for slot in range(actual + 1, MAX_PLAYERS + 1):
                            self.local_bridge.reset_slot(slot)
                        self.status_var.set(
                            f"Sala abierta - {actual} mandos FUTUREO, jugadores/cola conservados")
                        self._log(
                            f"CAPACIDAD ACTUALIZADA {result['previous']} -> {actual}; "
                            f"cola {result['queue']}. "
                            + ("Desplazados a cola: " + ", ".join(result['displaced'])
                               if result['displaced'] else "Sin usuarios desplazados."))
            elif kind == "cloudflared_ready":
                self._installing_cloudflared = False
                self._log("Cloudflare listo: " + str(payload))
                if not self._closing and self.server is not None:
                    self._start_tunnel()
            elif kind == "cloudflared_failed":
                self._installing_cloudflared = False
                self.api_var.set("API: no se pudo instalar Cloudflare")
                self._log("Error al instalar Cloudflare: " + str(payload)[:250])
                if not self._closing:
                    self.messagebox.showerror("Instalacion automatica fallida", str(payload))
            elif kind == "public_url":
                process, url = payload
                if process is self.tunnel and self.server is not None:
                    try:
                        self.public_address = valid_public_url(url)
                        self.url_var.set("PUBLICO: " + self.public_address)
                        self.api_var.set("API: publicando URL...")
                        self.api_jobs.put(self.public_address)
                        self._log("Enlace publico: " + self.public_address)
                    except ValueError as exc:
                        self._log("Cloudflare devolvio una URL invalida: " + str(exc))
            elif kind == "tunnel_closed":
                if payload is self.tunnel:
                    self.tunnel = None
                    self.public_address = ""
                    self.api_jobs.put("")
                    self.url_var.set("Tunel cerrado; publica de nuevo")
                    self.api_var.set("API: despublicando enlace anterior...")
        if not self._closing:
            self.root.after(120, self._drain)

    def _stop_server(self) -> None:
        self._stream_stop()
        if self._capacity_busy:
            self._log("El cambio de capacidad sigue en curso. Espera su finalizacion.")
            return
        if self.tunnel is not None:
            try: self.tunnel.terminate()
            except Exception: pass
            self.tunnel = None
        if self.public_address or self.api_published:
            self.api_jobs.put("")
        self.public_address = ""
        if self.server:
            old, self.server = self.server, None
            old.stop()
        self.port_input.configure(state="normal")
        self.player_select.configure(state="readonly")
        self.capacity_apply_button.configure(state="disabled")
        self._refresh_rotate_buttons()
        self.status_var.set("Servidor cerrado")
        self.room_var.set("SALA --")
        self.url_var.set("SIN PUBLICAR")
        self.pad_var.set("Mandos virtuales: detenidos")
        self._roster({"players": {}, "queue": [], "total": 0,
                      "slot_count": int(self.player_count_var.get())})

    def _close(self) -> None:
        if self._capacity_busy:
            self.messagebox.showwarning("FUTUREO",
                "Cambio de capacidad en curso. Vuelve a cerrar al terminar.")
            return
        self._closing = True
        self._stop_server()
        self.api_jobs.put(None)
        self.local_bridge.close()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()



def selftest_live_capacity() -> None:
    """Pruebas deterministas sin drivers: crecimiento/reduccion con cola FIFO."""
    now = [80.0]
    dummy = DummyPads(4)
    room = Room(dummy, seconds=600, clock=lambda: now[0])
    people = [room.register(f"G{n}") for n in range(1, 7)]
    assert [p.slot for p in people] == [1, 2, 3, 4, 0, 0]
    original_id = room.session_id
    remaining = 276.0
    people[2].remaining = remaining
    dummy.held[3].add('button_a')
    report = room.resize_capacity(2)
    assert report['previous'] == 4 and report['current'] == 2
    assert report['displaced'] == ['G3', 'G4']
    assert room.session_id == original_id
    assert dummy.count == 2 and room.remote_slots == (1, 2)
    assert people[0].slot == 1 and people[1].slot == 2
    assert not people[2].slot and people[2].queued
    assert not people[3].slot and people[3].queued
    assert people[2].turn_credit == remaining
    assert [room.players[uid].name for uid in room.waiting] == ['G5', 'G6', 'G3', 'G4']
    report = room.resize_capacity(6)
    assert report['previous'] == 2 and report['current'] == 6
    assert dummy.count == 6 and room.slot_count == 6
    assert room.session_id == original_id
    assert not room.waiting
    assert [p.slot for p in people] == [1, 2, 5, 6, 3, 4]
    assert people[2].remaining == remaining, "La reduccion no borra tiempo restante"
    assert all(1 <= p.slot <= 6 for p in people)
    assert room.resize_capacity(6)['displaced'] == []
    try:
        room.resize_capacity(9)
    except ValueError:
        pass
    else:
        raise AssertionError("Se permitieron mas de 8 jugadores")
    room.close()

    # Fault injection: reduce capacity fails; players and room survive.
    class FailingDummy(DummyPads):
        def resize(self, count: int) -> bool:
            if count == 1:
                raise RuntimeError("simulated driver failure")
            return super().resize(count)

    broken = Room(FailingDummy(2))
    first, second = broken.register("Uno"), broken.register("Dos")
    try:
        broken.resize_capacity(1)
    except RuntimeError:
        pass
    else:
        raise AssertionError("No se notifico el fallo del driver")
    assert broken.slot_count == 2 and first.slot == 1 and second.slot == 2
    assert broken.session_id and not broken.waiting
    broken.close()

    class FakeFutureo:
        def __init__(self):
            self.count = 2
            self.history = []
        def health(self):
            return {'engine': 'FUTUREO_VJOY', 'slots': [1, 2]}
        def resize(self, count):
            self.count = count
        def input(self, packet):
            assert 1 <= packet['slot'] <= self.count
            assert len(packet['buttons']) == 16
            assert -1 <= packet['axes'][0] <= 1
            assert -1 <= packet['axes'][1] <= 1
            assert packet['session']
            self.history.append(packet)

    fake = FakeFutureo()
    bridge = VirtualFutureoPads(2, transport=fake)
    assert bridge.count == 2
    assert bridge.set_mode(1, 'dpad')
    assert bridge.apply(1, 'ar', True)
    assert bridge.apply(1, 'de', True)
    assert fake.history[-1]['hat'] == 2, "DPad NE debe ser Hat=2"
    assert fake.history[-1]['axes'] == [0., 0.], "El DPad deja stick neutral"
    assert bridge.apply(1, 'button_a', True)
    assert fake.history[-1]['buttons'][3] == 1, "Boton A en indice FUTUREO 3"
    bridge.release_slot(1)
    assert fake.history[-1]['hat'] == 0
    assert bridge.set_mode(1, 'analog')
    assert bridge.analog(1, -127, 127)
    assert fake.history[-1]['axes'] == [-1., -1.], "X izquierda Y arriba"
    assert bridge.resize(8) and bridge.count == 8 and fake.count == 8
    assert bridge.resize(1) and bridge.count == 1 and fake.count == 1
    bridge.close()
    assert all(v == 0 for v in fake.history[-1]['buttons'])
    print("OK: capacidad EN VIVO 4->2->6, cola FIFO, tiempo conservado, rollback, FUTUREO 1..8")


def selftest() -> None:
    """Prueba reproducible sin Windows, Internet, Tk ni vJoy."""
    now = [100.0]
    device = DummyPads()
    room = Room(device, clock=lambda: now[0])
    a, b = room.register("Ana"), room.register("Beto")
    assert (a.slot, b.slot) == (1, 2)
    assert room.snapshot()["players"]["1"]["timer_running"] is False
    now[0] += 900  # 15 minutos SIN COLA: no descontar un solo segundo.
    room.tick()
    assert a.remaining == 600 and b.remaining == 600
    assert room.input(a.uid, 'button_a', True)
    assert room.input(a.uid, 'button_a', False)
    assert room.input(b.uid, 'button_a', True)
    assert room.input(b.uid, 'button_a', False)
    c = room.register("Cata")
    assert c.queued and c.slot == 0
    assert room.snapshot()["queue_length"] == 1
    assert room.snapshot()["players"]["1"]["timer_running"] is True
    now[0] += 210
    room.tick()
    assert round(a.remaining) == 390 and round(b.remaining) == 390
    assert room.input(a.uid, "iz", True)
    assert room.input(a.uid, "ar", True)
    assert (1, "iz", True) in device.events and (1, "ar", True) in device.events
    assert room.set_direction_mode(a.uid, 'analog')
    assert device.mode[1] == 'analog' and not device.held[1].intersection(DIRECTIONS)
    assert room.analog(a.uid, -90, 90) and device.analog_axes[1] == (-90, 90)
    assert not room.analog(c.uid, 100, 0)  # espectador no puede mover un mando.
    assert not room.analog(a.uid, 128, 0)   # datos fuera de rango rechazados.
    assert room.set_direction_mode(a.uid, 'dpad')
    assert device.analog_axes[1] == (0, 0)  # alternar siempre centra el eje.
    assert not room.analog(a.uid, 127, 0)
    assert room.input(a.uid, 'de', True)
    assert 'de' in device.held[1]
    for cmd in ("button_a", "button_b", "button_x", "button_y", "button_lb", "button_rb", "start", "select"):
        assert room.input(b.uid, cmd, True)
        assert room.input(b.uid, cmd, False)
    assert not room.input(c.uid, "button_a", True)
    assert not room.input(a.uid, "INVALID", True)
    assert set(WIRE_CODES.values()) == ACTIONS
    assert len(WIRE_CODES) == len(ACTIONS) == 12
    assert all(decode_input(code + "1") == (action, True)
               and decode_input(code + "0") == (action, False)
               for code, action in WIRE_CODES.items())
    assert decode_input("x1") == ("button_x", True)
    assert decode_input("l0") == ("button_lb", False)
    assert decode_input("t1") == ("start", True)
    assert decode_input("s0") == ("select", False)
    assert decode_input("x2") is None
    assert decode_input("zz") is None
    assert decode_input("x11") is None
    assert decode_input("{") is None
    assert decode_input('{"type":"notice","action":"x","down":true}') is None
    assert decode_input('{"type":"input","action":"bc","down":true}') == ("button_x", True)
    assert decode_input('{"type":"input","action":"button_a","down":false}') == ("button_a", False)
    assert not room.input(a.uid, "ba", True)  # protocolo anterior, no se admite
    assert set(VirtualVJoyPads.BUTTONS) == (ACTIONS - DIRECTIONS)
    assert room.set_direction_mode(c.uid, 'analog') and not room.analog(c.uid, 127, 0)
    assert VirtualVJoyPads.BUTTONS['button_lb'] == 5
    assert VirtualVJoyPads.BUTTONS['button_rb'] == 6
    try:
        room.register("  ANa  ")
    except ValueError:
        pass
    else:
        raise AssertionError("Nombres duplicados no bloqueados")
    room.remove(c.uid)  # Se vacia la cola: congelar exactamente 390s.
    now[0] += 500
    room.tick()
    assert round(a.remaining) == 390 and round(b.remaining) == 390
    d = room.register("Dani")
    assert d.queued
    now[0] += 389
    room.tick()
    assert round(a.remaining) == 1 and round(b.remaining) == 1
    # Una persona esperando: al vencer pasa a jugar con turno completo.
    now[0] += 1
    room.tick()
    assert d.slot in (1, 2)
    assert room.snapshot()["players"][str(d.slot)]["remaining_seconds"] == 600
    assert a.queued or b.queued
    # Los controles de un ocupante desplazado se sueltan siempre.
    assert not device.held[d.slot]
    room.remove(a.uid)
    room.remove(b.uid)
    room.remove(d.uid)
    assert not room.waiting
    assert not room.players
    second_room = Room(DummyPads(), seconds=20, clock=lambda: now[0])
    one, two, three, four = [second_room.register(n) for n in ("One", "Two", "Three", "Four")]
    assert second_room.rotate_slot(1)
    assert three.slot == 1 and one.queued
    assert second_room.rotate_slot(2)
    assert four.slot == 2 and two.queued
    assert [second_room.players[u].name for u in second_room.waiting] == ["One", "Two"]
    assert VirtualVJoyPads.axes({"ar", "iz"}) == (-1, 1)
    assert VirtualVJoyPads.axes({"ab", "de"}) == (1, -1)
    assert valid_public_url("https://abc-1.trycloudflare.com/") == "https://abc-1.trycloudflare.com"
    for unsafe in ("http://abc-1.trycloudflare.com", "https://evil.com",
                   "https://a.trycloudflare.com.attacker.org", "https://x.trycloudflare.com:8443"):
        try: valid_public_url(unsafe)
        except ValueError: pass
        else: raise AssertionError("URL peligrosa aceptada: " + unsafe)
    room.close()
    second_room.close()
    for count in (1, 4, 8):
        fake = DummyPads(count)
        room_n = Room(fake, seconds=20, clock=lambda: now[0])
        people = [room_n.register(f"Jugador{n}") for n in range(1, count + 3)]
        assert [p.slot for p in people[:count]] == list(range(1, count + 1))
        assert [p.slot for p in people[count:]] == [0, 0]
        assert room_n.snapshot()['slot_count'] == count
        assert list(room_n.snapshot()['players']) == [str(i) for i in room_n.slots]
        assert room_n.rotate_slot(count)
        assert people[count].slot == count and people[count - 1].queued
        now[0] += COUNTDOWN_SECONDS
        room_n.tick()
        assert room_n.input(people[count].uid, 'button_a', True)
        assert 'button_a' in fake.held[count]
        fake.analog_axes[count] = (65, -40)
        room_n.disconnect(people[count].uid, socket=None)
        assert fake.held[count] == set() and fake.analog_axes[count] == (0, 0)
        assert room_n.snapshot()['players'][str(count)]['name'] == people[count].name
        assert room_n.identify_slot(count)
        assert (count, 'identify_button_8', True) in fake.events
        assert (count, 'identify_button_8', False) in fake.events
        room_n.close()
    # Confirmacion de 10 s: latidos, modos y liberaciones no cuentan.
    clock = [0.0]
    r = Room(DummyPads(1), clock=lambda: clock[0])
    first = r.register('Primero')
    assert not r.input(first.uid, 'button_a', True)  # El popup 3,2,1 bloquea pulsaciones.
    clock[0] += COUNTDOWN_SECONDS
    r.tick()
    clock[0] += 5
    assert r.input(first.uid, 'button_a', False)
    assert first.activation_deadline is not None
    r.tick()
    assert r.snapshot()['players']['1']['activation_seconds'] == 5
    assert r.snapshot()['players']['1']['timer_remaining'] == 600
    second = r.register('Segundo')
    assert second.queued and first.slot == 1
    clock[0] += 5
    events = r.tick()
    assert ('activation_timeout','Primero',1) in events
    assert second.slot == 1 and first.queued
    assert not r.device.held[1]
    assert not r.input(second.uid, 'button_b', True)  # En popup.
    clock[0] += COUNTDOWN_SECONDS
    r.tick()
    assert r.input(second.uid, 'button_b', True)
    assert r.snapshot()['players']['1']['activation_pending'] is False
    assert r.snapshot()['players']['1']['timer_remaining'] == 600
    clock[0] += 60
    r.tick()
    assert r.snapshot()['players']['1']['timer_remaining'] == 540
    assert second.activation_deadline is None
    r.close()
    mixed = Room(DummyPads(4), clock=lambda: clock[0],
                 slot_modes={1:'CONTROLADO', 2:'REMOTO', 3:'CONTROLADO', 4:'REMOTO'})
    persons = [mixed.register(f'Inv{n}') for n in range(1,4)]
    assert [v.slot for v in persons] == [2,4,0]
    assert mixed.snapshot()['remote_count'] == 2
    visitor = mixed.set_slot_mode(2, 'CONTROLADO')
    assert visitor is persons[0] and not visitor.active and visitor.uid not in mixed.players
    assert mixed.snapshot()['slot_modes']['2'] == 'CONTROLADO'
    assert persons[2].slot == 0 and persons[2].queued
    mixed.set_slot_mode(3, 'REMOTO')
    assert persons[2].slot == 3
    assert mixed.snapshot()['remote_count'] == 2
    mixed.close()
    room_names = Room(DummyPads(1))
    assert room_names.register('1234567890').name == '1234567890'
    try:
        room_names.register('12345678901')
    except ValueError as exc:
        assert '10 caracteres' in str(exc)
    else:
        raise AssertionError('Se aceptaron nombres de 11 caracteres')
    room_names.close()
    # Regresion v2.1/v2.2: ningun mando antiguo puede rechazarse
    # por usar rutas distintas de "/" en su WebSocket.
    for route in (None, "", "/", "/?session=anterior",
                  "/ws", "/ws?room=abc", "/control/", "/streaming"):
        assert websocket_channel(route) == "controller", route
    for route in ("/stream", "/stream/", "/stream?ticket=1",
                  "/stream/?v=2"):
        assert websocket_channel(route) == "stream", route
    selftest_live_capacity()
    stream_selftest()
    print("OK: MULTIMANDO FUTUREO 1-8, 3s cuenta atras, 10s activacion, FIFO y cambios de capacidad")


def main() -> None:
    if "--selftest" in sys.argv:
        selftest()
        return
    if sys.platform != "win32":
        print("MULTIMANDO requiere Windows para crear los joysticks genericos vJoy.")
        print("Para comprobar la logica en otro sistema: --selftest")
        return
    try:
        ensure_python_dependencies()
        from websockets.sync.server import serve  # noqa: F401
    except (ImportError, RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
        message = "No se pudieron preparar las dependencias de MULTIMANDO.\n\n" + str(exc)
        print(message, file=sys.stderr)
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("MULTIMANDO - Instalacion", message, parent=root)
            root.destroy()
        except Exception:
            pass
        return
    MultimandoGUI().run()


if __name__ == "__main__":
    main()
