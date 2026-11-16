# -*- coding: utf-8 -*-
"""KOF ARENA | receptor local de telemetria MAME Lua (sin puntuar partidas).

Lee un archivo corto que escribe KOF_Salud_MAME289.lua.
No usa direcciones de memoria de Windows; no escribe en MAME.
Compatible con Python 3.10+; sin librerias externas.
"""
from __future__ import annotations

import dataclasses
import pathlib
import re
import threading
import time
from typing import Callable, Optional

STATE_FILE_NAME = "KOF_ARENA_LUA_ESTADO.txt"
LINE = re.compile(r"^KOF_LUA_V1\t([0-9]{1,12})\t([0-9]{1,3})\t([0-9]{1,3})"
                  r"\t([0-9]{1,3})\t([0-9]{1,3})\s*$")


@dataclasses.dataclass(frozen=True)
class HealthState:
    seq: int
    p1: int
    p2: int
    rounds_lost_p1: int
    rounds_lost_p2: int

    @property
    def values(self) -> tuple[int, int, int, int]:
        return self.p1, self.p2, self.rounds_lost_p1, self.rounds_lost_p2


def parse_health_line(raw: str) -> Optional[HealthState]:
    """Admite solo el formato de la version 1 y valores Byte validos."""
    match = LINE.fullmatch(raw)
    if match is None:
        return None
    seq, p1, p2, l1, l2 = map(int, match.groups())
    if seq == 0 or any(value > 255 for value in (p1, p2, l1, l2)):
        return None
    return HealthState(seq, p1, p2, l1, l2)


class LuaHealthMonitor:
    """Vigila el archivo del emulador y publica notificaciones al GUI."""

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
                # Puede coincidir con un archivo truncado a mitad de escritura.
                state = None

            if state is not None and state.seq > last_seq:
                last_seq = state.seq
                last_data_at = time.monotonic()
                status("Lua conectado: leyendo RAM de Neo Geo (solo lectura).")
                if last_values != state.values:
                    last_values = state.values
                    self.notify("lua_health", state)
            elif time.monotonic() - last_data_at > 5:
                status("Lua sin cambios recientes: pausa, emulacion detenida "
                       "o script sin cargar. Revisa la ventana de MAME.")
            self._stop.wait(0.2)


def run_selftest():
    from tempfile import TemporaryDirectory

    assert parse_health_line("KOF_LUA_V1\t1\t102\t102\t0\t0\n") == HealthState(
        1, 102, 102, 0, 0)
    assert parse_health_line("KOF_LUA_V1\t2\t99\t102\t0\t0\n").p1 == 99
    assert parse_health_line("KOF_LUA_V1\t3\t102\t0\t0\t2\n").p2 == 0
    assert parse_health_line("KOF_LUA_V1\t1\t300\t0\t0\t0") is None
    assert parse_health_line("KOF_LUA_V1\t0\t102\t102\t0\t0") is None
    assert parse_health_line("KOF_LUA_V1\t1\t0\t0") is None
    assert parse_health_line("anything\t1\t102\t102\t0\t0") is None
    with TemporaryDirectory() as directory:
        path = pathlib.Path(directory) / STATE_FILE_NAME
        path.write_text("KOF_LUA_V1\t15\t76\t53\t1\t0\n", encoding="ascii")
        assert parse_health_line(path.read_text(encoding="ascii")).values == (
            76, 53, 1, 0)
    print("OK: protocolo Lua V1, Byte P1/P2, rangos y entradas invalidas.")


if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv:
        run_selftest()
    else:
        print("Importa LuaHealthMonitor desde KOF_Anfitrion.py.")
