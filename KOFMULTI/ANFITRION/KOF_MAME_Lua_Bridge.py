# -*- coding: utf-8 -*-
"""KOFMULTI | receptor de salud Lua MAME 0.289, lectura sin puntuacion.

V3 incorpora timer y contador PERFECT por KO/tiempo con 102 HP.
Soporta V1/V2 por compatibilidad y no puntua ninguna partida.
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
LINE_V3 = re.compile(
    r"^KOF_LUA_V3\t([0-9]{1,12})\t([0-9]{1,3})\t([0-9]{1,3})"
    r"\t([0-9]{1,3})\t([0-9]{1,3})\t([0-9]{1,6})\t([0-9]{1,6})"
    r"\t([0-9]{1,3})\t([0-9]{1,6})\t([0-9]{1,6})\s*$")


def display_health(value: int) -> str:
    """Un 254 observado en KO es un estado, no 254 puntos de vida."""
    if 128 <= value <= 255:
        return f"{value} (HP con signo {value - 256})"
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
    timer: Optional[int] = None
    perfect_p1: int = 0
    perfect_p2: int = 0

    @property
    def p1_display(self) -> str:
        return display_health(self.p1)

    @property
    def p2_display(self) -> str:
        return display_health(self.p2)

    @property
    def values(self) -> tuple:
        return (self.p1, self.p2, self.rounds_lost_p1, self.rounds_lost_p2,
                self.ko_events_p1, self.ko_events_p2, self.timer,
                self.perfect_p1, self.perfect_p2)

    @property
    def ko_counts(self) -> tuple[int, int]:
        return self.ko_events_p1, self.ko_events_p2

    @property
    def perfect_counts(self) -> tuple[int, int]:
        return self.perfect_p1, self.perfect_p2

    @property
    def timer_display(self) -> str:
        if self.timer is None:
            return "--"
        high, low = self.timer >> 4, self.timer & 15
        if high <= 9 and low <= 9:
            return f"{high * 10 + low:02d}"
        return f"0x{self.timer:02X}"


def parse_health_line(raw: str) -> Optional[HealthState]:
    """Valida y acepta V1, V2 y V3 sin confiar en muestras incompletas."""
    match = LINE_V3.fullmatch(raw)
    version = 3
    if match is None:
        match = LINE_V2.fullmatch(raw)
        version = 2
    if match is None:
        match = LINE_V1.fullmatch(raw)
        version = 1
    if match is None:
        return None
    parts = tuple(map(int, match.groups()))
    seq, p1, p2, l1, l2 = parts[:5]
    if seq == 0 or any(value > 255 for value in (p1, p2, l1, l2)):
        return None
    ko1, ko2 = (parts[5], parts[6]) if version >= 2 else (0, 0)
    timer, perfect1, perfect2 = (parts[7], parts[8], parts[9]) if version == 3 \
        else (None, 0, 0)
    if any(value > 999999 for value in (ko1, ko2, perfect1, perfect2)):
        return None
    if timer is not None and timer > 255:
        return None
    return HealthState(seq, p1, p2, l1, l2, ko1, ko2,
                       timer, perfect1, perfect2)


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
        last_perfect_counts = None
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
                if (last_perfect_counts is not None and
                        any(now > old for now, old
                            in zip(state.perfect_counts, last_perfect_counts))):
                    self.notify("lua_perfect", state)
                last_perfect_counts = state.perfect_counts
            elif time.monotonic() - last_data_at > 5:
                status("Lua sin cambios recientes: pausa, emulacion detenida "
                       "o script sin cargar. Revisa la ventana de MAME.")
            self._stop.wait(0.2)


def run_selftest():
    from tempfile import TemporaryDirectory

    v1 = parse_health_line("KOF_LUA_V1\t1\t102\t102\t0\t0\n")
    assert v1 == HealthState(1, 102, 102, 0, 0)
    assert v1.perfect_counts == (0, 0) and v1.timer_display == "--"

    v2 = parse_health_line("KOF_LUA_V2\t2\t102\t254\t0\t1\t0\t1\n")
    assert v2 == HealthState(2, 102, 254, 0, 1, 0, 1)
    assert v2.p2_display == "254 (HP con signo -2)"
    assert v2.ko_counts == (0, 1)

    # Primera partida: P1 obtiene 2 PERFECT por KO y 1 por tiempo.
    first = parse_health_line(
        "KOF_LUA_V3\t10\t102\t255\t0\t1\t0\t1\t56\t1\t0\n")
    timeout = parse_health_line(
        "KOF_LUA_V3\t20\t102\t35\t0\t2\t0\t1\t0\t2\t0\n")
    finale = parse_health_line(
        "KOF_LUA_V3\t30\t102\t254\t0\t3\t0\t2\t65\t3\t0\n")
    assert first is not None and first.perfect_counts == (1, 0)
    assert timeout is not None and timeout.perfect_counts == (2, 0)
    assert finale is not None and finale.perfect_counts == (3, 0)
    assert timeout.timer_display == "00"
    assert finale.timer_display == "41"
    # Segunda partida: P2 tuvo vida entera en el primer KO de P1.
    second = parse_health_line(
        "KOF_LUA_V3\t13\t252\t102\t1\t0\t1\t0\t54\t0\t1\n")
    assert second is not None and second.perfect_counts == (0, 1)
    assert display_health(255) == "255 (HP con signo -1)"
    assert parse_health_line("KOF_LUA_V3\t1\t300\t0\t0\t0\t0\t0\t0\t0\t0") is None
    assert parse_health_line("KOF_LUA_V3\t1\t102\t102\t0\t0\t0\t0\t300\t0\t0") is None
    assert parse_health_line("KOF_LUA_V3\t1\t102\t102\t0\t0\t0\t0\t0\t1000000\t0") is None
    assert parse_health_line("KOF_LUA_V2\t3\t300\t0\t0\t0\t0\t0") is None
    assert parse_health_line("KOF_LUA_V1\t0\t102\t102\t0\t0") is None
    assert parse_health_line("anything\t1\t102\t102\t0\t0") is None
    with TemporaryDirectory() as directory:
        path = pathlib.Path(directory) / STATE_FILE_NAME
        path.write_text(
            "KOF_LUA_V3\t15\t76\t53\t1\t0\t1\t2\t48\t1\t0\n",
            encoding="ascii")
        parsed = parse_health_line(path.read_text(encoding="ascii"))
        assert parsed and parsed.values == (76, 53, 1, 0, 1, 2, 48, 1, 0)
    print("OK: V1/V2/V3, PERFECT por KO o tiempo, BCD y validacion Byte.")


if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv:
        run_selftest()
    else:
        print("Importa LuaHealthMonitor desde KOF_Anfitrion.py.")
