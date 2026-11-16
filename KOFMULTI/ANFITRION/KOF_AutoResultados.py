# -*- coding: utf-8 -*-
"""KOFMULTI: lectura LOCAL de pantallas de resultados en MAME antiguo.

No envía imágenes, no guarda fotogramas y no modifica el emulador ni las ROM.
El motor OCR necesita Pillow y Tesseract (ejecutable local); sin ellos NO
inventa puntuaciones. Requiere validar los textos del juego real.
"""
from __future__ import annotations

import ctypes
import io
import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

RESULT_PATTERNS = (
    re.compile(r"\b(?:P(?:LAYER)?\s*1|1\s*P)\b\s*(?:WIN|WINS|WINNER|VICTORY)\b"),
    re.compile(r"\b(?:P(?:LAYER)?\s*2|2\s*P)\b\s*(?:WIN|WINS|WINNER|VICTORY)\b"),
)
REVERSED_PATTERNS = (
    re.compile(r"\b(?:WINNER|WINS?|VICTORY)\b\s*(?:P(?:LAYER)?\s*1|1\s*P)\b"),
    re.compile(r"\b(?:WINNER|WINS?|VICTORY)\b\s*(?:P(?:LAYER)?\s*2|2\s*P)\b"),
)
PERFECT_PATTERN = re.compile(r"\bPERFECT\b")


def read_result_text(text: str) -> tuple[int, bool]:
    """Devuelve (P1/P2, perfecto) SOLO ante un ganador inequívoco."""
    normalized = re.sub(r"[^A-Z0-9]+", " ", str(text).upper()).strip()
    hits = set()
    for slot, (direct, reverse) in enumerate(zip(RESULT_PATTERNS, REVERSED_PATTERNS), 1):
        if direct.search(normalized) or reverse.search(normalized):
            hits.add(slot)
    slot = next(iter(hits)) if len(hits) == 1 else 0
    return slot, bool(PERFECT_PATTERN.search(normalized))


class VerifiedOutcome:
    """Debounce de pantalla: no cuenta un mismo resultado varias veces."""

    def __init__(self, cooldown=12.0):
        self.cooldown = cooldown
        self.candidate = 0
        self.candidate_count = 0
        self.pending = None
        self.pending_at = 0.0
        self.perfect_recent_at = float("-inf")
        self.armed = True
        self.last_fired = float("-inf")
        self.last_seen = 0.0

    def feed(self, text: str, identities: tuple[int, int], now: float):
        """Retorna (winner_slot, perfect, ids) o None.

        Una victoria necesita leerse dos veces y mantenerse asociados los mismos
        dos jugadores. El perfecto puede anunciarse antes o después de WINNER.
        """
        winner, perfect = read_result_text(text)
        if perfect:
            self.perfect_recent_at = now
            if self.pending:
                self.pending["perfect"] = True
        if winner:
            self.last_seen = now
            if winner == self.candidate:
                self.candidate_count += 1
            else:
                self.candidate = winner
                self.candidate_count = 1
            if (self.armed and self.pending is None and
                    self.candidate_count >= 2 and now - self.last_fired > self.cooldown and
                    len(identities) == 2 and all(i > 0 for i in identities)):
                self.pending = {
                    "slot": winner,
                    "perfect": now - self.perfect_recent_at < 4.0,
                    "ids": tuple(identities),
                }
                self.pending_at = now
        else:
            self.candidate = 0
            self.candidate_count = 0
            if not self.armed and now - self.last_seen >= 3.5:
                self.armed = True

        if self.pending and tuple(identities) != self.pending["ids"]:
            self.pending = None  # El mando cambió: nunca atribuir a otro jugador.
        if self.pending and now - self.pending_at >= 1.4:
            event = self.pending
            self.pending = None
            self.armed = False
            self.last_fired = now
            return event["slot"], event["perfect"], event["ids"]
        return None


def find_tesseract(base: Path) -> str | None:
    candidates = [
        os.environ.get("KOF_TESSERACT_EXE", ""),
        str(base / "Tesseract-OCR" / "tesseract.exe"),
        shutil.which("tesseract") or "",
        str(Path(os.environ.get("ProgramFiles", "C:/Program Files")) /
            "Tesseract-OCR" / "tesseract.exe"),
        str(Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) /
            "Tesseract-OCR" / "tesseract.exe"),
    ]
    return next((p for p in candidates if p and Path(p).is_file()), None)


def find_window_for_pid(pid: int):
    """Busca el rectángulo CLIENTE de MAME (no del escritorio completo)."""
    if os.name != "nt":
        return None
    import ctypes.wintypes as wt

    class POINT(ctypes.Structure):
        _fields_ = [("x", wt.LONG), ("y", wt.LONG)]

    class RECT(ctypes.Structure):
        _fields_ = [("left", wt.LONG), ("top", wt.LONG),
                    ("right", wt.LONG), ("bottom", wt.LONG)]

    user = ctypes.windll.user32
    CALLBACK = ctypes.WINFUNCTYPE(ctypes.c_int, wt.HWND, wt.LPARAM)
    rectangles = []

    def visit(hwnd, _param):
        found_pid = wt.DWORD()
        user.GetWindowThreadProcessId(hwnd, ctypes.byref(found_pid))
        if found_pid.value != pid or not user.IsWindowVisible(hwnd):
            return 1
        rect = RECT()
        if not user.GetClientRect(hwnd, ctypes.byref(rect)):
            return 1
        p = POINT(0, 0)
        if not user.ClientToScreen(hwnd, ctypes.byref(p)):
            return 1
        width = rect.right - rect.left
        height = rect.bottom - rect.top
        if width >= 250 and height >= 180:
            rectangles.append((width * height, (p.x, p.y, p.x + width, p.y + height)))
        return 1

    callback = CALLBACK(visit)
    user.EnumWindows(callback, 0)
    return max(rectangles)[1] if rectangles else None


def ocr_mame_frame(bbox, executable: str):
    """Captura y OCR en RAM del PC anfitrión; no crea imágenes ni archivos."""
    from PIL import Image, ImageGrab, ImageOps
    frame = ImageGrab.grab(bbox=bbox, all_screens=True)
    # Evitar intentar puntuar si DirectDraw devuelve una pantalla negra.
    extrema = ImageOps.grayscale(frame).getextrema()
    if extrema[1] - extrema[0] < 18:
        return "", False
    image = ImageOps.autocontrast(ImageOps.grayscale(frame))
    if image.width < 800:
        image = image.resize((image.width * 2, image.height * 2),
                             resample=Image.Resampling.BICUBIC)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    # Proceso OCR en segundo plano y prioridad baja: los mandos siempre tienen
    # preferencia sobre el análisis visual. CREATE_NO_WINDOW evita flashes CMD.
    flags = (getattr(subprocess, "CREATE_NO_WINDOW", 0) |
             getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0))
    result = subprocess.run(
        [executable, "stdin", "stdout", "--psm", "11", "-l", "eng"],
        input=buffer.getvalue(), stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, timeout=3.5, check=False,
        creationflags=flags)
    return result.stdout.decode("utf-8", "replace"), True


class AutoResultMonitor:
    """Encuentra MAME por PID y analiza solo su ventana en un hilo aparte."""

    def __init__(self, process, server, notify, base_dir, interval=0.55):
        self.process = process
        self.server = server
        self.notify = notify
        self.base_dir = Path(base_dir)
        self.interval = interval
        self.stop_event = threading.Event()
        self.thread = None

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        if os.name != "nt":
            self.notify("log", "AUTO MARCADOR: requiere Windows.")
            return
        if find_tesseract(self.base_dir) is None:
            self.notify("log", "AUTO MARCADOR NO ACTIVO: falta Tesseract OCR; no se inventarán resultados.")
            return
        try:
            from PIL import ImageGrab  # noqa: F401
        except ImportError:
            self.notify("log", "AUTO MARCADOR NO ACTIVO: instala Pillow con py -m pip install --no-cache-dir Pillow.")
            return
        self.stop_event.clear()
        self.thread = threading.Thread(
            target=self._work, name="KOF-Resultado-Local", daemon=True)
        self.thread.start()
        self.notify("log", "AUTO MARCADOR: lectura local de MAME activa; sin transmisión de imágenes.")

    def stop(self):
        self.stop_event.set()

    def _work(self):
        executable = find_tesseract(self.base_dir)
        engine = VerifiedOutcome()
        last_status = 0.0
        while not self.stop_event.is_set():
            if self.process.poll() is not None or self.server.stop_event.is_set():
                break
            bbox = find_window_for_pid(self.process.pid)
            if bbox is None:
                self.stop_event.wait(1.0)
                continue
            with self.server.room.lock:
                occupants = [
                    next((g.uid for g in self.server.room.guests.values()
                          if g.slot == slot and g.start_pressed), 0)
                    for slot in (1, 2)
                ]
            try:
                text, available = ocr_mame_frame(bbox, executable)
                if not available and time.monotonic() - last_status > 25:
                    last_status = time.monotonic()
                    self.notify("log", "AUTO MARCADOR: no se ve el contenido de MAME. Revisa modo ventana.")
                event = engine.feed(text, tuple(occupants), time.monotonic())
                if event:
                    slot, perfect, uids = event
                    if self.server.record_game_outcome(slot, perfect, uids):
                        self.notify(
                            "log", f"JUEGO: P{slot} ganador detectado "
                                   f"({'PERFECT' if perfect else 'normal'}) por lectura local.")
            except (OSError, ValueError, subprocess.TimeoutExpired) as ex:
                if time.monotonic() - last_status > 20:
                    last_status = time.monotonic()
                    self.notify("log", f"AUTO MARCADOR: captura/OCR no disponible: {ex}")
            self.stop_event.wait(self.interval)


def run_selftest():
    def feed_lines(lines):
        d = VerifiedOutcome()
        result = []
        for t, line in lines:
            e = d.feed(line, (101, 202), t)
            if e:
                result.append(e)
        return result

    assert read_result_text("P1 WINNER PERFECT") == (1, True)
    assert read_result_text("2P WINS") == (2, False)
    assert read_result_text("WINNER PLAYER 2") == (2, False)
    assert read_result_text("WINNER") == (0, False)
    assert read_result_text("P1 WINNER P2 WINNER") == (0, False)
    events = feed_lines([(1, "1P WINS"), (1.7, "1P WINS"),
                         (2.2, "PERFECT"), (3.2, ""),
                         (8, "1P WINS"), (8.7, "1P WINS"),
                         (9.5, "")])
    assert events == [(1, True, (101, 202))], events
    d = VerifiedOutcome()
    assert d.feed("P1 WIN", (101, 202), 1) is None
    assert d.feed("P1 WIN", (101, 303), 2) is None  # P2 cambió
    assert d.feed("", (101, 303), 4) is None
    assert d.feed("P1 WIN", (0, 303), 30) is None
    assert d.feed("P1 WIN", (0, 303), 31) is None
    print("OK: detección segura de resultados, PERFECT y antirrepetición.")


if __name__ == "__main__":
    run_selftest()
