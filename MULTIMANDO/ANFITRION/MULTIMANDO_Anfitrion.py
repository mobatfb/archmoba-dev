#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MULTIMANDO: anfitrion independiente para dos mandos Xbox virtuales.

Compatible con la palanca PHP v5.7: WASD/UIOJKL en el navegador,
comandos WebSocket ar/ab/iz/de, button_a/button_b/button_x/button_y/button_lb/button_rb, start/select.

Regla: 600 segundos de juego POR JUGADOR, consumidos unicamente mientras
exista al menos un jugador en espera. Sin cola, el reloj se pausa sin reset.
Al agotar el turno, el jugador pasa AL FINAL de la cola FIFO y se entrega
su mando al primer jugador que ya estaba esperando. El servidor es la unica
fuente de verdad; el cliente solo envia pulsaciones.

No necesita KOF, MAME, ROMs, cuenta del usuario ni acceso al escritorio.
No transmite pantalla o audio ni ejecuta instrucciones arbitrarias recibidas.
Windows: python -m pip install websockets vgamepad  (+ controlador ViGEmBus).
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

VERSION = "1.2.0"
BASE_DIR = pathlib.Path(__file__).resolve().parent
DEFAULT_PORT = 8766  # No interfiere con el puerto 8765 de KOFMULTI.
DEFAULT_SECONDS = 600
MAX_GUESTS = 64
MAX_MESSAGES_PER_SECOND = 100
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



def compact(obj: dict) -> str:
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
    input_times: collections.deque = field(default_factory=collections.deque)
    outbound: queue.Queue = field(default_factory=lambda: queue.Queue(maxsize=32))
    wake: threading.Event = field(default_factory=threading.Event)
    warned_last_minute: bool = False

    def tell(self, data: dict) -> None:
        payload = compact(data)
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
    def __init__(self):
        self.events: list[tuple[int, str, bool]] = []
        self.held = {1: set(), 2: set()}
        self.xinput_slots = None

    def apply(self, slot: int, action: str, down: bool) -> bool:
        if slot not in (1, 2) or action not in ACTIONS:
            return False
        self.events.append((slot, action, down))
        if down:
            self.held[slot].add(action)
        else:
            self.held[slot].discard(action)
        return True

    def release_slot(self, slot: int) -> None:
        self.held[slot].clear()

    def close(self) -> None:
        for slot in (1, 2):
            self.release_slot(slot)


def xinput_reader() -> Callable[[], dict[int, int]]:
    """Consulta XInput 1-4 y devuelve sus botones, sin enviar teclas Windows."""
    from ctypes import wintypes

    class GAMEPAD(ctypes.Structure):
        _fields_ = [("wButtons", wintypes.WORD), ("bLeftTrigger", wintypes.BYTE),
                    ("bRightTrigger", wintypes.BYTE), ("sThumbLX", ctypes.c_short),
                    ("sThumbLY", ctypes.c_short), ("sThumbRX", ctypes.c_short),
                    ("sThumbRY", ctypes.c_short)]

    class STATE(ctypes.Structure):
        _fields_ = [("dwPacketNumber", wintypes.DWORD), ("Gamepad", GAMEPAD)]

    dll = None
    for name in ("xinput1_4.dll", "xinput1_3.dll", "xinput9_1_0.dll"):
        try:
            dll = ctypes.WinDLL(name)
            break
        except OSError:
            pass
    if dll is None:
        raise RuntimeError("No se encontro XInput en Windows")
    reader = dll.XInputGetState
    reader.argtypes = [wintypes.DWORD, ctypes.POINTER(STATE)]
    reader.restype = wintypes.DWORD

    def poll() -> dict[int, int]:
        result = {}
        for idx in range(4):
            state = STATE()
            if reader(idx, ctypes.byref(state)) == 0:
                result[idx + 1] = int(state.Gamepad.wButtons)
        return result
    return poll


def detect_pad_positions(pads: list[Any], vg_buttons: Any,
                         read: Callable[[], dict[int, int]] | None = None
                         ) -> tuple[int, int]:
    """Identifica las posiciones XInput reales de los mandos creados."""
    if len(pads) != 2:
        raise ValueError("Se necesitan exactamente dos mandos")
    poll = read or xinput_reader()
    positions = []
    mask = 0x1000 | 0x2000  # A y B simultaneos en XInput.
    for pad in pads:
        prior = poll()
        found = None
        try:
            pad.press_button(button=vg_buttons.XUSB_GAMEPAD_A)
            pad.press_button(button=vg_buttons.XUSB_GAMEPAD_B)
            pad.update()
            for _ in range(20):
                active = poll()
                choices = [idx for idx, bits in active.items()
                           if bits & mask == mask and prior.get(idx, 0) & mask != mask
                           and idx not in positions]
                if len(choices) == 1:
                    found = choices[0]
                    break
                time.sleep(0.05)
        finally:
            pad.reset()
            pad.update()
        if found is None:
            raise RuntimeError("No se pudo identificar un joystick virtual en XInput")
        positions.append(found)
    if len(set(positions)) != 2:
        raise RuntimeError("Los dos mandos virtuales comparten la misma posicion XInput")
    return positions[0], positions[1]


class VirtualXboxPads:
    """2 mandos Xbox360 por ViGEmBus; 6 botones A,B,X,Y,LB,RB."""
    BUTTONS = {
        "ar": "XUSB_GAMEPAD_DPAD_UP", "ab": "XUSB_GAMEPAD_DPAD_DOWN",
        "iz": "XUSB_GAMEPAD_DPAD_LEFT", "de": "XUSB_GAMEPAD_DPAD_RIGHT",
        "button_a": "XUSB_GAMEPAD_A", "button_b": "XUSB_GAMEPAD_B",
        "button_x": "XUSB_GAMEPAD_X", "button_y": "XUSB_GAMEPAD_Y",
        "button_lb": "XUSB_GAMEPAD_LEFT_SHOULDER", "button_rb": "XUSB_GAMEPAD_RIGHT_SHOULDER",
        "start": "XUSB_GAMEPAD_START", "select": "XUSB_GAMEPAD_BACK",
    }
    MIN_TAP_SECONDS = 0.095

    @staticmethod
    def axes(actions: set[str]) -> tuple[int, int]:
        horizontal = int("de" in actions) - int("iz" in actions)
        vertical = int("ar" in actions) - int("ab" in actions)
        return horizontal * 32767, vertical * 32767

    def __init__(self):
        if sys.platform != "win32":
            raise RuntimeError("Los mandos Xbox virtuales requieren Windows")
        try:
            import vgamepad as vg
        except ImportError as exc:
            raise RuntimeError("Instala: py -m pip install websockets vgamepad, y ViGEmBus") from exc
        self.vg = vg
        self.lock = threading.RLock()
        self.pads = []
        try:
            self.pads = [vg.VX360Gamepad(), vg.VX360Gamepad()]
            for pad in self.pads:
                pad.reset(); pad.update()
        except Exception as exc:
            self.close()
            raise RuntimeError("No se pudieron abrir los 2 mandos. Instala ViGEmBus: " + str(exc)) from exc
        self.held: dict[int, set[str]] = {1: set(), 2: set()}
        self.pressed_at: dict[tuple[int, str], float] = {}
        self.release_timers: dict[tuple[int, str], threading.Timer] = {}
        self.xinput_slots: tuple[int, int] | None = None
        self.xinput_warning = ""
        try:
            self.xinput_slots = detect_pad_positions(self.pads, vg.XUSB_BUTTON)
        except (RuntimeError, ValueError, OSError) as exc:
            self.xinput_warning = str(exc)

    def _cancel_timer(self, key: tuple[int, str]) -> None:
        timer = self.release_timers.pop(key, None)
        if timer:
            timer.cancel()

    def _update(self, slot: int) -> None:
        current = self.held[slot]
        pad = self.pads[slot - 1]
        pad.reset()
        # XInput D-pad no admite opuestos, pero si diagonales.
        current_buttons = set(current)
        for a, b in (("ar", "ab"), ("iz", "de")):
            if a in current_buttons and b in current_buttons:
                current_buttons.discard(a)
                current_buttons.discard(b)
        for action in sorted(current_buttons):
            pad.press_button(button=getattr(self.vg.XUSB_BUTTON, self.BUTTONS[action]))
        x, y = self.axes(current_buttons)
        pad.left_joystick(x_value=x, y_value=y)
        pad.update()

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
        if slot not in (1, 2) or action not in ACTIONS or not isinstance(down, bool):
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
            wait = self.MIN_TAP_SECONDS - (time.monotonic() - self.pressed_at.get(key, 0))
            if wait > 0:
                self._cancel_timer(key)
                t = threading.Timer(wait, self._timer_release, args=(slot, action))
                t.daemon = True
                self.release_timers[key] = t
                t.start()
            else:
                self._release_now(slot, action)
            return True

    def release_slot(self, slot: int) -> None:
        if slot not in (1, 2):
            return
        with self.lock:
            for key in tuple(self.release_timers):
                if key[0] == slot:
                    self._cancel_timer(key)
            for key in tuple(self.pressed_at):
                if key[0] == slot:
                    self.pressed_at.pop(key, None)
            self.held[slot].clear()
            if slot <= len(self.pads):
                self._update(slot)

    def close(self) -> None:
        if not hasattr(self, "held"):
            for p in getattr(self, "pads", []):
                try: p.reset(); p.update()
                except Exception: pass
            return
        for slot in (1, 2):
            try: self.release_slot(slot)
            except Exception: pass
        self.pads.clear()


class Room:
    """Arbitro de turnos P1/P2 con cola FIFO y reloj monotonic del anfitrion."""
    def __init__(self, device: Any, seconds: float = DEFAULT_SECONDS,
                 clock: Callable[[], float] = time.monotonic,
                 max_guests: int = MAX_GUESTS):
        if seconds <= 0 or not math.isfinite(seconds):
            raise ValueError("Tiempo de turno invalido")
        self.device = device
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
        guest.remaining = self.seconds
        guest.last_tick = now
        guest.warned_last_minute = False
        self.events.append(("assigned", guest.name, slot))

    def _vacancy(self, now: float) -> None:
        while self.waiting:
            occupied = {g.slot for g in self.players.values() if g.slot in (1, 2)}
            slot = next((n for n in (1, 2) if n not in occupied), None)
            if slot is None:
                return
            uid = self.waiting.popleft()
            guest = self.players.get(uid)
            if guest is not None and guest.queued and guest.active:
                self._activate(guest, slot, now)

    def _deactivate(self, guest: Guest) -> int:
        slot = guest.slot
        if slot:
            self.device.release_slot(slot)
        guest.held.clear()
        guest.input_times.clear()
        guest.slot = 0
        guest.queued = False
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
        """Descontar tiempo ANTES de modificar la cola; evita descuentos sin cola."""
        has_queue = bool(self.waiting)
        active = tuple(g for g in self.players.values() if g.slot in (1, 2))
        for g in active:
            elapsed = max(0.0, now - g.last_tick)
            if has_queue:
                g.remaining = max(0.0, g.remaining - elapsed)
            g.last_tick = now
        # El primero en vencer rota primero; las nuevas asignaciones no pierden
        # segundos de un tick anterior. Si la cola se vacia no hay expiracion.
        for g in sorted(active, key=lambda x: x.slot):
            if g.slot and g.remaining <= 0.000001 and self.waiting:
                self._rotate(g, now, "turn_finished")
        if self.waiting:
            for g in self.players.values():
                if g.slot and g.remaining <= 60 and not g.warned_last_minute:
                    g.warned_last_minute = True
                    self.events.append(("last_minute", g.name, g.slot))

    def register(self, name: str, socket: Any = None) -> Guest:
        with self.lock:
            now = self.clock()
            self._advance(now)
            if len(self.players) >= self.max_guests:
                raise ValueError("Sala llena; vuelve a intentarlo mas tarde")
            clean = " ".join("".join(c for c in str(name) if c.isprintable()).split())[:24]
            if not clean:
                raise ValueError("Escribe un nombre valido")
            normalized = canonical_name(clean)
            if any(canonical_name(g.name) == normalized for g in self.players.values()):
                raise ValueError("El nombre '" + clean + "' ya esta en uso en esta sala")
            g = Guest(self.uid, clean, socket, remaining=self.seconds)
            self.uid += 1
            self.players[g.uid] = g
            self._vacancy(now)
            vacant = next((s for s in (1, 2) if not any(p.slot == s for p in self.players.values())), None)
            if vacant is not None and not self.waiting:
                self._activate(g, vacant, now)
            else:
                g.slot = 0
                g.queued = True
                self.waiting.append(g.uid)
                self.events.append(("waiting", g.name, len(self.waiting)))
            return g

    def remove(self, uid: int) -> Guest | None:
        with self.lock:
            now = self.clock()
            self._advance(now)
            g = self.players.pop(uid, None)
            if g is None:
                return None
            old_slot = self._deactivate(g)
            self.waiting = collections.deque(u for u in self.waiting if u != uid)
            g.active = False
            g.wake.set()
            self.events.append(("left", g.name, old_slot))
            self._vacancy(now)
            return g

    def rotate_slot(self, slot: int) -> bool:
        """Solo la GUI local puede hacer avanzar una cola antes del limite."""
        with self.lock:
            now = self.clock()
            self._advance(now)
            g = next((g for g in self.players.values() if g.slot == slot), None)
            return bool(g and self._rotate(g, now, "manual_turn"))

    def input(self, uid: int, action: str, down: bool) -> bool:
        with self.lock:
            now = self.clock()
            self._advance(now)
            g = self.players.get(uid)
            if (not g or not g.active or not g.slot or action not in ACTIONS
                    or type(down) is not bool):
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
            for slot in (1, 2):
                g = next((p for p in self.players.values() if p.slot == slot), None)
                people[str(slot)] = {
                    "id": g.uid, "name": g.name,
                    "remaining_seconds": max(0, math.ceil(g.remaining)),
                    "timer_remaining": max(0, math.ceil(g.remaining)),
                    "timer_running": running,
                } if g else None
            return {
                "players": people,
                "queue": [{"id": uid, "name": self.players[uid].name}
                          for uid in self.waiting if uid in self.players],
                "queue_length": len(self.waiting),
                "total": len(self.players),
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
                    "timer_running": bool(self.waiting) and bool(g.slot),
                    **data,
                }
                result.append((g, state))
            return result

    def close(self) -> None:
        with self.lock:
            for g in self.players.values():
                g.active = False
                g.wake.set()
            self.players.clear()
            self.waiting.clear()
            self.device.close()


class MultimandoServer:
    def __init__(self, port: int, device: Any, on_event: Callable[[str, Any], None],
                 seconds: float = DEFAULT_SECONDS, bind_lan: bool = False):
        self.port = port
        self.room = Room(device, seconds=seconds)
        self.on_event = on_event
        self.bind_lan = bind_lan
        self.stop_event = threading.Event()
        self.server = None
        self.worker: threading.Thread | None = None
        self.ticker: threading.Thread | None = None

    def start(self) -> None:
        try:
            from websockets.sync.server import serve
        except ImportError as exc:
            raise RuntimeError("Instala: py -m pip install websockets vgamepad") from exc
        bind = "0.0.0.0" if self.bind_lan else "127.0.0.1"
        self.server = serve(self._handle, bind, self.port, max_size=4096,
                            compression=None, ping_interval=15, ping_timeout=15,
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

    def _sender(self, guest: Guest) -> None:
        try:
            while guest.active and not self.stop_event.is_set():
                guest.wake.wait(1.0)
                guest.wake.clear()
                while guest.active:
                    try:
                        payload = guest.outbound.get_nowait()
                    except queue.Empty:
                        break
                    guest.socket.send(payload)
        except Exception:
            guest.active = False
            try: guest.socket.close()
            except Exception: pass

    def _state(self) -> None:
        for guest, state in self.room.individualized():
            guest.tell(state)
        self.on_event("roster", self.room.snapshot())

    def _handle(self, websocket: Any) -> None:
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
            try:
                guest = self.room.register(str(hello.get("name", "")), websocket)
            except ValueError as exc:
                websocket.send(compact({"type": "error", "message": str(exc)}))
                return
            websocket.send(compact({"type": "welcome", "you": guest.uid,
                                    "room_id": self.room.session_id,
                                    "version": VERSION, "turn_duration": self.room.seconds}))
            threading.Thread(target=self._sender, args=(guest,), daemon=True,
                             name=f"MULTIMANDO-Send-{guest.uid}").start()
            self._state()
            self.on_event("log", f"{guest.name} conectado: " + (f"P{guest.slot}" if guest.slot else "cola"))
            for raw in websocket:
                if not guest.active or self.stop_event.is_set():
                    break
                if not isinstance(raw, str) or len(raw) > 4096:
                    continue
                decoded = decode_input(raw)
                if decoded is None:
                    continue
                action, down = decoded
                # Una pulsacion no puede atribuirse a un puesto antiguo si
                # el temporizador lo hizo rotar justo en este instante.
                with self.room.lock:
                    slot_before = guest.slot
                    held_before = action in guest.held
                    accepted = self.room.input(guest.uid, action, down)
                    real_transition = (
                        accepted and slot_before in (1, 2)
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
                self.room.remove(guest.uid)
                self._state()
                self.on_event("log", f"{guest.name} desconectado")
            try:
                websocket.close()
            except Exception:
                pass

    def _ticker(self) -> None:
        while not self.stop_event.is_set():
            events = self.room.tick()
            for kind, name, slot in events:
                if kind in ("turn_finished", "manual_turn"):
                    text = "Turno de 10 min agotado" if kind == "turn_finished" else "Cambio manual del anfitrion"
                    self.on_event("log", f"{text}: {name} sale de P{slot} y pasa a la cola")
                    with self.room.lock:
                        g = next((g for g in self.room.players.values() if g.name == name), None)
                        if g:
                            g.tell({"type": "notice", "level": "info",
                                    "message": "Turno finalizado. Pasaste al final de la cola."})
                elif kind == "last_minute":
                    self.on_event("log", f"Ultimo minuto para {name} P{slot} (si sigue la cola)")
                    with self.room.lock:
                        g = next((g for g in self.room.players.values() if g.name == name), None)
                        if g:
                            g.tell({"type": "notice", "level": "warning",
                                    "message": "Te queda menos de un minuto mientras haya cola."})
            self._state()
            self.stop_event.wait(0.5)

    def kick(self, uid: int) -> bool:
        with self.room.lock:
            g = self.room.players.get(uid)
            if g is None:
                return False
            socket = g.socket
        try:
            socket.close(code=1000, reason="Expulsado por el anfitrion")
            return True
        except Exception:
            return False

    def stop(self) -> None:
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
            raise RuntimeError("La GUI y los mandos Xbox virtuales requieren Windows")
        import tkinter as tk
        from tkinter import ttk, messagebox
        self.tk, self.ttk, self.messagebox = tk, ttk, messagebox
        self.root = tk.Tk()
        self.root.title("MULTIMANDO | ANFITRION v" + VERSION)
        self.root.geometry("1000x700")
        self.root.minsize(790, 560)
        self.root.configure(bg="#0b1424")
        self.events: queue.Queue[tuple[str, Any]] = queue.Queue(maxsize=250)
        self.api_jobs: queue.Queue[str | None] = queue.Queue()
        self.api_thread = threading.Thread(target=self._api_loop, daemon=True, name="MULTIMANDO-API")
        self.api_thread.start()
        self.server: MultimandoServer | None = None
        self.tunnel: subprocess.Popen | None = None
        self.public_address = ""
        self.api_published = ""
        self.member_rows: dict[str, int] = {}
        self._closing = False
        self._theme()
        self._build()
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self.root.after(120, self._drain)
        self.root.after(800, self._refresh)

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
        self.counter_var = tk.StringVar(value="0 conectados | P1 libre | P2 libre | cola 0")
        self.pad_var = tk.StringVar(value="Mandos virtuales: sin iniciar")
        self.lan_var = tk.BooleanVar(value=False)
        body = ttk.Frame(self.root)
        body.pack(fill="both", expand=True, padx=14, pady=10)
        head = ttk.Frame(body)
        head.pack(fill="x", pady=(0, 10))
        ttk.Label(head, text="MULTIMANDO", style="Title.TLabel").pack(side="left")
        ttk.Label(head, text="ANFITRION v" + VERSION + "  |  2 mandos virtuales / 10 minutos con cola",
                  style="Muted.TLabel").pack(side="left", padx=16, pady=7)
        ttk.Label(head, textvariable=self.room_var, style="Muted.TLabel").pack(side="right")

        main_buttons = ttk.Frame(body)
        main_buttons.pack(fill="x", pady=3)
        ttk.Label(main_buttons, text="Puerto:", style="Muted.TLabel").pack(side="left", padx=(0, 4))
        self.port_input = ttk.Entry(main_buttons, textvariable=self.port_var, width=8)
        self.port_input.pack(side="left", padx=(0, 8))
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

        panel = ttk.Frame(body)
        panel.pack(fill="both", expand=True, pady=(4, 7))
        columns = ("slot", "username", "id", "seconds", "condition")
        self.table = ttk.Treeview(panel, columns=columns, show="headings", selectmode="browse")
        for key, label, width in (("slot", "Puesto", 135), ("username", "Jugador", 260),
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
        ttk.Button(actions, text="SIGUIENTE P1", command=lambda: self._rotate(1)).pack(side="left", padx=3)
        ttk.Button(actions, text="SIGUIENTE P2", command=lambda: self._rotate(2)).pack(side="left", padx=3)
        ttk.Button(actions, text="EXPULSAR SELECCIONADO", command=self._kick).pack(side="left", padx=3)
        ttk.Label(actions, text="Sin cola: contador en pausa; con cola: 10 min por turno.",
                  style="Muted.TLabel").pack(side="right", padx=7)
        ttk.Label(body, text="REGISTRO DE EVENTOS", style="Muted.TLabel").pack(anchor="w", pady=(5, 2))
        self.log = tk.Text(body, height=6, wrap="word", bg="#09172b", fg="#bde4ff",
                           insertbackground="white", relief="flat", font=("Consolas", 9), state="disabled")
        self.log.pack(fill="x")
        self._log("Los visitantes usan solo la palanca PHP; los turnos se controlan aqui.")
        self._log("Acciones: ar/ab/iz/de + button_a/button_b/button_x/button_y/button_lb/button_rb + start/select.")
        self._log("Requiere Windows, websockets, vgamepad y ViGEmBus; no necesita KOF.")

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

    def _start_server(self) -> None:
        if self.server:
            self._log("La sala ya esta abierta")
            return
        try:
            port = int(self.port_var.get())
            if not 1024 <= port <= 65535:
                raise ValueError("Puerto fuera del rango 1024-65535")
            device = VirtualXboxPads()
            try:
                host = MultimandoServer(port, device, self.notify, bind_lan=self.lan_var.get())
                host.start()
            except Exception:
                device.close()
                raise
            self.server = host
            self.port_input.configure(state="disabled")
            self.status_var.set("Sala abierta - unirse por el enlace publico o por red local")
            self.room_var.set("SALA " + host.room.session_id)
            if device.xinput_slots:
                self.pad_var.set(f"Xbox virtual P1 = XInput {device.xinput_slots[0]}"
                                 f" | P2 = XInput {device.xinput_slots[1]}")
            else:
                self.pad_var.set("2 mandos Xbox virtuales creados. XInput sin verificar: "
                                 + device.xinput_warning[:90])
            self.url_var.set(f"LOCAL: ws://127.0.0.1:{port}")
            self.api_var.set("API: abre PUBLICAR INTERNET para registrar la sala")
            self._log("Dos mandos virtuales activos. Configura tu aplicacion para leerlos.")
        except Exception as exc:
            self.messagebox.showerror("No se pudo abrir la sala", str(exc))

    def _start_tunnel(self) -> None:
        if self.server is None:
            self.messagebox.showwarning("Abre la sala", "Primero pulsa ABRIR SALA")
            return
        if self.tunnel and self.tunnel.poll() is None:
            self._log("El tunel ya esta activo")
            return
        executable = shutil.which("cloudflared")
        if not executable:
            possible = BASE_DIR / "cloudflared.exe"
            if possible.is_file():
                executable = str(possible)
        if not executable:
            self.messagebox.showinfo("Falta Cloudflare",
                "Instala Cloudflare Tunnel o coloca cloudflared.exe junto a este .py.\n"
                "Windows: winget install --id Cloudflare.cloudflared\n"
                "https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/")
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
            self._log(f"Cambio manual P{slot}: nuevo jugador asignado por FIFO")
        else:
            self._log(f"P{slot}: no hay cola para ceder el mando")

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
        self.counter_var.set(f"{data.get('total', 0)} conectados | "
                             f"P1 {'ocupado' if players.get('1') else 'libre'} | "
                             f"P2 {'ocupado' if players.get('2') else 'libre'} | "
                             f"En espera: {len(waiting)}")
        for slot in (1, 2):
            g = players.get(str(slot))
            if g:
                remaining = int(g["remaining_seconds"])
                mm, ss = divmod(remaining, 60)
                position = "P" + str(slot)
                status = "CONTANDO" if g.get("timer_running") else "PAUSADO (sin cola)"
                item = self.table.insert("", "end", values=(
                    position, g["name"], g["id"], f"{mm:02d}:{ss:02d}", status))
                self.member_rows[item] = g["id"]
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
            elif kind == "api":
                self.api_var.set(str(payload))
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
        self.status_var.set("Servidor cerrado")
        self.room_var.set("SALA --")
        self.url_var.set("SIN PUBLICAR")
        self.pad_var.set("Mandos virtuales: detenidos")
        self._roster({"players": {"1": None, "2": None}, "queue": [], "total": 0})

    def _close(self) -> None:
        self._closing = True
        self._stop_server()
        self.api_jobs.put(None)
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def selftest() -> None:
    """Prueba reproducible sin Windows, Internet, Tk o vgamepad."""
    now = [100.0]
    device = DummyPads()
    room = Room(device, clock=lambda: now[0])
    a, b = room.register("Ana"), room.register("Beto")
    assert (a.slot, b.slot) == (1, 2)
    assert room.snapshot()["players"]["1"]["timer_running"] is False
    now[0] += 900  # 15 minutos SIN COLA: no descontar un solo segundo.
    room.tick()
    assert a.remaining == 600 and b.remaining == 600
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
    assert set(VirtualXboxPads.BUTTONS) == ACTIONS
    assert (VirtualXboxPads.BUTTONS["button_lb"] == "XUSB_GAMEPAD_LEFT_SHOULDER"
            and VirtualXboxPads.BUTTONS["button_rb"] == "XUSB_GAMEPAD_RIGHT_SHOULDER")
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
    assert VirtualXboxPads.axes({"ar", "iz"}) == (-32767, 32767)
    assert VirtualXboxPads.axes({"ab", "de"}) == (32767, -32767)
    assert valid_public_url("https://abc-1.trycloudflare.com/") == "https://abc-1.trycloudflare.com"
    for unsafe in ("http://abc-1.trycloudflare.com", "https://evil.com",
                   "https://a.trycloudflare.com.attacker.org", "https://x.trycloudflare.com:8443"):
        try: valid_public_url(unsafe)
        except ValueError: pass
        else: raise AssertionError("URL peligrosa aceptada: " + unsafe)
    room.close()
    second_room.close()
    print("OK: MULTIMANDO pruebas FIFO, 10 min solo con cola, pausa, entradas, URLs")


def main() -> None:
    if "--selftest" in sys.argv:
        selftest()
        return
    if sys.platform != "win32":
        print("MULTIMANDO requiere Windows para crear dos mandos Xbox virtuales.")
        print("Para comprobar la logica en otro sistema: --selftest")
        return
    try:
        from websockets.sync.server import serve  # noqa: F401
    except ImportError:
        print("Instala dependencias: py -m pip install websockets vgamepad")
        return
    MultimandoGUI().run()


if __name__ == "__main__":
    main()
