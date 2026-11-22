#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Motor FUTUREO VJOY para MULTIMANDO (integracion futura, optativa).

No modifica MULTIMANDO existente. Requiere FutJoy.sys firmado e instalado.
Compatible con interfaz VirtualVJoyPads: apply, analog, set_mode,
release_slot, identify, close. Se prueban los estados con un driver simulado.
"""
from __future__ import annotations

import threading
import time
from typing import Callable

from futureo_vjoy import FutJoy

DIRECTIONS = frozenset(("ar", "ab", "iz", "de"))
BUTTONS = {
    "button_a": 0, "button_b": 1, "button_x": 2, "button_y": 3,
    "button_lb": 4, "button_rb": 5, "start": 6, "select": 7,
}
ACTIONS = DIRECTIONS | frozenset(BUTTONS)


class FutureoPads:
    """Administra los puestos P1...P8. El turno lo decide Room, no este driver."""

    MIN_TAP_SECONDS = 0.095

    def __init__(self, count: int = 2, factory: Callable = FutJoy):
        if type(count) is not int or not 1 <= count <= 8:
            raise ValueError("Elige entre 1 y 8 joysticks")
        self.count = count
        self.lock = threading.RLock()
        self.pads = []
        self.held = {slot: set() for slot in range(1, count + 1)}
        self.mode = {slot: "legacy" for slot in range(1, count + 1)}
        self.analog_axes = {slot: (0, 0) for slot in range(1, count + 1)}
        self.pressed_at = {}
        self.release_timers = {}
        self.xinput_slots = None  # HID/DirectInput, no XInput.
        try:
            for slot in range(1, count + 1):
                pad = factory(slot)
                self.pads.append(pad)
                pad.neutral()
        except BaseException:
            self.close()
            raise

    @staticmethod
    def axes(actions: set[str]) -> tuple[int, int]:
        return (int("de" in actions) - int("iz" in actions),
                int("ar" in actions) - int("ab" in actions))

    @staticmethod
    def scale8(value: int) -> int:
        return max(-32767, min(32767, round(value * 32767 / 127)))

    def _send(self, slot: int) -> None:
        active = set(self.held[slot])
        for left, right in (("ar", "ab"), ("iz", "de")):
            if left in active and right in active:
                active.difference_update((left, right))
        if self.mode[slot] == "analog":
            ax, ay = self.analog_axes[slot]
            x, y = self.scale8(ax), -self.scale8(ay)
        else:
            dx, dy = self.axes(active)
            x, y = 32767 * dx, -32767 * dy
        mask = sum(1 << bit for action, bit in BUTTONS.items()
                   if action in active)
        self.pads[slot - 1].state(x=x, y=y, buttons=mask)

    def _cancel(self, key: tuple[int, str]) -> None:
        timer = self.release_timers.pop(key, None)
        if timer:
            timer.cancel()

    def set_mode(self, slot: int, mode: str) -> bool:
        if slot not in self.held or mode not in ("analog", "dpad", "legacy"):
            return False
        with self.lock:
            for key in list(self.release_timers):
                if key[0] == slot and key[1] in DIRECTIONS:
                    self._cancel(key)
            for key in list(self.pressed_at):
                if key[0] == slot and key[1] in DIRECTIONS:
                    self.pressed_at.pop(key, None)
            self.held[slot].difference_update(DIRECTIONS)
            self.analog_axes[slot] = (0, 0)
            self.mode[slot] = mode
            self._send(slot)
            return True

    def analog(self, slot: int, x: int, y: int) -> bool:
        if (slot not in self.held or type(x) is not int or type(y) is not int or
                not -127 <= x <= 127 or not -127 <= y <= 127):
            return False
        with self.lock:
            if self.mode[slot] != "analog":
                return False
            if self.analog_axes[slot] == (x, y):
                return True
            old = self.analog_axes[slot]
            self.analog_axes[slot] = (x, y)
            try:
                self._send(slot)
            except Exception:
                self.analog_axes[slot] = old
                return False
            return True

    def _release_now(self, slot: int, action: str) -> None:
        key = slot, action
        self._cancel(key)
        self.pressed_at.pop(key, None)
        if action in self.held[slot]:
            self.held[slot].discard(action)
            self._send(slot)

    def _release_delayed(self, slot: int, action: str) -> None:
        with self.lock:
            self._release_now(slot, action)

    def apply(self, slot: int, action: str, down: bool) -> bool:
        if slot not in self.held or action not in ACTIONS or type(down) is not bool:
            return False
        with self.lock:
            key = slot, action
            if down:
                self._cancel(key)
                if action in self.held[slot]:
                    return True
                self.held[slot].add(action)
                try:
                    self._send(slot)
                except Exception:
                    self.held[slot].discard(action)
                    return False
                self.pressed_at[key] = time.monotonic()
                return True
            if action not in self.held[slot]:
                return True
            delay = self.MIN_TAP_SECONDS - (time.monotonic() - self.pressed_at.get(key, 0))
            if delay > 0:
                self._cancel(key)
                timer = threading.Timer(delay, self._release_delayed, args=(slot, action))
                timer.daemon = True
                self.release_timers[key] = timer
                timer.start()
            else:
                self._release_now(slot, action)
            return True

    def release_slot(self, slot: int) -> None:
        if slot not in self.held:
            return
        with self.lock:
            for key in list(self.release_timers):
                if key[0] == slot:
                    self._cancel(key)
            for key in list(self.pressed_at):
                if key[0] == slot:
                    self.pressed_at.pop(key, None)
            self.held[slot].clear()
            self.analog_axes[slot] = (0, 0)
            if slot <= len(self.pads):
                self.pads[slot - 1].neutral()

    def identify(self, slot: int, duration: float = 0.28) -> bool:
        if slot not in self.held:
            return False
        with self.lock:
            self.release_slot(slot)
            try:
                self.pads[slot - 1].state(buttons=1 << BUTTONS["select"])
                time.sleep(max(0.12, min(0.55, duration)))
            finally:
                self.release_slot(slot)
            return True

    def close(self) -> None:
        with self.lock:
            for slot in range(1, len(self.pads) + 1):
                try:
                    self.release_slot(slot)
                except Exception:
                    pass
            for pad in self.pads:
                try:
                    pad.close()
                except Exception:
                    pass
            self.pads.clear()


if __name__ == "__main__":
    print("Adaptador FUTUREO VJOY. No es un ejecutable autonomo.")
    print("Ejecuta: py -m unittest discover -s tests -v")
