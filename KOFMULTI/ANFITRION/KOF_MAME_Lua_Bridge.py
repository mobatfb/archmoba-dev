# -*- coding: utf-8 -*-
"""KOFMULTI | receptor de salud Lua MAME 0.289, lectura sin puntuacion.

V2 conserva transiciones compatibles con KO incluso cuando 254 dura
menos que el intervalo de lectura de Python. Soporta V1 por compatibilidad.
No escribe memoria de MAME y no determina resultados de un equipo.
"""
from __future__ import annotations

import dataclasses
import pathlib
import re
import threading
import time
from typing import Callable, Optional

STATE_FILE_NAME = "KOF_ARENA_LUA_ESTADO.txt"
KO_SENTINEL = 254
LINE_V1 = re.compile(
    r"^KOF_LUA_V1\t([0-9]{1,12})\t([0-9]{1,3})\t([0-9]{1,3})"
    r"\t([0-9]{1,3})\t([0-9]{1,3})\s*$")
LINE_V2 = re.compile(
    r"^KOF_LUA_V2\t([0-9]{1,12})\t([0-9]{1,3})\t([0-9]{1,3})"
    r"\t([0-9]{1,3})\t([0-9]{1,3})\t([0-9]{1,6})\t([0-9]{1,6})\s*$")


def display_health(value: int) -> str:
    """Un 254 observado en KO es un estado, no 254 puntos de vida."""
    if value == KO_SENTINEL:
        return "KO (254)"
    if 0 <= value <= 102:
        return str(value)
    return f"{value} (estado)"


@dataclasses.dataclass(frozen=True)
class HealthState:
    seq: int
    p1: int
    p2: int
    rounds_lost_p1: int
    rounds_lost_p2: int
    ko_events_p1: int = 0
    ko_events_p2: int = 0

    @property
    def p1_display(self) -> str:
        return display_health(self.p1)

    @property
    def p2_display(self) -> str:
        return display_health(self.p2)

    @property
    def values(self) -> tuple[int, int, int, int, int, int]:
        return (self.p1, self.p2, self.rounds_lost_p1,
                self.rounds_lost_p2, self.ko_events_p1, self.ko_events_p2)

    @property
    def ko_counts(self) -> tuple[int, int]:
        return self.ko_events_p1, self.ko_events_p2


def parse_health_line(raw: str) -> Optional[HealthState]:
    """Valida un mensaje completo V2 (o V1) antes de usarlo en el GUI."""
    version = 2
    match = LINE_V2.fullmatch(raw)
    if match is None:
        version = 1
        match = LINE_V1.fullmatch(raw)
    if match is None:
        return None
    numbers = tuple(map(int, match.groups()))
    seq, p1, p2, l1, l2 = numbers[:5]
    if seq == 0 or any(value > 255 for value in (p1, p2, l1, l2)):
        return None
    if version == 2:
        ko1, ko2 = numbers[5:]
        if ko1 > 999999 or ko2 > 999999:
            return None
    else:
        ko1, ko2 = 0, 0
    return HealthState(seq, p1, p2, l1, l2, ko1, ko2)


class LuaHealthMonitor:
    """Observa telemetria, avisa cambios y conserva cuentas de KO en V2."""

    def __init__(self, process, file_path: pathlib.Path,
                 notify: Callable[[str, object], None]):
        self.process = process
        self.path = pathlib.Path(file_path)
        self.notify = notify
        self._stop = threading.Event()
        self.thread = threading.Thread(
            target=self._loop, name="KOF-Lua-Health", daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        self._stop.set()

    def _loop(self):
        last_seq = 0
        last_values = None
        last_ko_counts = None
        last_data_at = time.monotonic()
        last_status = None

        def status(message):
            nonlocal last_status
            if last_status != message:
                last_status = message
                self.notify("lua_status", message)

        status("Lua: esperando datos desde MAME 0.289...")
        while not self._stop.is_set():
            if self.process.poll() is not None:
                status("Lua: MAME se cerró; no se registraron resultados.")
                break
            try:
                if self.path.is_file() and self.path.stat().st_size <= 256:
                    raw = self.path.read_text(encoding="ascii")
                    state = parse_health_line(raw)
                else:
                    state = None
            except (OSError, UnicodeError):
                # Puede coincidir con el truncado intermedio de una escritura.
                state = None

            if state is not None and state.seq > last_seq:
                last_seq = state.seq
                last_data_at = time.monotonic()
                status("Lua conectado: leyendo RAM de Neo Geo (solo lectura).")
                if last_values != state.values:
                    last_values = state.values
                    self.notify("lua_health", state)
                # Los contadores V2 sobreviven a una animacion 254 muy corta.
                if (last_ko_counts is not None and
                        any(now > old for now, old
                            in zip(state.ko_counts, last_ko_counts))):
                    self.notify("lua_ko", state)
                last_ko_counts = state.ko_counts
            elif time.monotonic() - last_data_at > 5:
                status("Lua sin cambios recientes: pausa, emulacion detenida "
                       "o script sin cargar. Revisa la ventana de MAME.")
            self._stop.wait(0.2)


def run_selftest():
    from tempfile import TemporaryDirectory

    old = parse_health_line("KOF_LUA_V1\t1\t102\t102\t0\t0\n")
    assert old == HealthState(1, 102, 102, 0, 0)
    assert old.ko_counts == (0, 0)

    new = parse_health_line("KOF_LUA_V2\t2\t102\t254\t0\t1\t0\t1\n")
    assert new == HealthState(2, 102, 254, 0, 1, 0, 1)
    assert new.p2_display == "KO (254)" and new.p1_display == "102"
    assert new.values == (102, 254, 0, 1, 0, 1)
    next_fighter = parse_health_line("KOF_LUA_V2\t3\t90\t102\t0\t1\t0\t1\n")
    assert next_fighter.ko_counts == (0, 1)
    assert display_health(255) == "255 (estado)"
    assert parse_health_line("KOF_LUA_V2\t3\t300\t0\t0\t0\t0\t0") is None
    assert parse_health_line("KOF_LUA_V2\t3\t0\t0\t0\t0\t1000000\t0") is None
    assert parse_health_line("KOF_LUA_V1\t0\t102\t102\t0\t0") is None
    assert parse_health_line("KOF_LUA_V2\t1\t0\t0") is None
    assert parse_health_line("anything\t1\t102\t102\t0\t0") is None
    with TemporaryDirectory() as directory:
        path = pathlib.Path(directory) / STATE_FILE_NAME
        path.write_text(
            "KOF_LUA_V2\t15\t76\t53\t1\t0\t1\t2\n", encoding="ascii")
        assert parse_health_line(path.read_text(encoding="ascii")).values == (
            76, 53, 1, 0, 1, 2)
    print("OK: Lua V1/V2, KO=254, contadores persistentes, rangos y formato.")


if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv:
        run_selftest()
    else:
        print("Importa LuaHealthMonitor desde KOF_Anfitrion.py.")
