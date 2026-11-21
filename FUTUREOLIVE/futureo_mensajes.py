#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FUTUREO Mensajes 1.2.7 — una ventana, 10 transiciones y banco remoto.

Ejecución: python futureo_mensajes.py
Requiere Python 3.9 o posterior con Tkinter. No usa paquetes externos,
imágenes auxiliares, claves ni instalaciones automáticas.

Al abrirse, descarga mensajes.json una sola vez desde el repositorio.
El banco se conserva únicamente en RAM: no se escribe en disco ni caché.
Si falla la descarga, el envío manual sigue disponible; vuelve a abrir
la aplicación para reintentar. Auto se habilita cuando hay frases remotas
que caben en el límite establecido. No incluye un banco local alternativo.

Arriba: únicamente el mensaje publicado en un banner azul de estilo neón.
La ventana permanece siempre visible sobre las otras ventanas normales.
Abajo: editor, límite de caracteres, intervalo en segundos, Auto y Enviar.
Enter envía desde el editor. El intervalo predeterminado es de 10 segundos.
El límite y el intervalo se guardan en la caché del usuario.
Auto no borra el borrador. Un envío manual reinicia el intervalo elegido.
"""

"""Núcleo sin GUI para FUTUREO Mensajes. Solo usa la biblioteca estándar."""

import json
import os
import random
import sys
import tempfile
import unicodedata
from pathlib import Path


DEFAULT_LIMIT = 80
MIN_LIMIT = 1
MAX_LIMIT = 9999
DEFAULT_INTERVAL_SECONDS = 10
MIN_INTERVAL_SECONDS = 1
MAX_INTERVAL_SECONDS = 9999


def normalize_text(value: str) -> str:
    """Normaliza NFC y espacios sin cambiar mayúsculas ni minúsculas.

    Conserva un solo espacio en cada extremo para no impedir escribir una
    palabra nueva en el Entry. Al publicar se puede aplicar ``.strip()``.
    """
    if value is None:
        return ""
    text = unicodedata.normalize("NFC", str(value))
    result = []
    previous_space = False
    for character in text:
        is_space = character.isspace()
        if is_space:
            if not previous_space:
                result.append(" ")
        else:
            result.append(character)
        previous_space = is_space
    return "".join(result)


def _integer_value(value):
    """Devuelve un entero inequívoco, o None; bool no es un ajuste válido."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value.strip(), 10)
        except (ValueError, TypeError, OverflowError):
            return None
    if isinstance(value, float) and value.is_integer():
        try:
            return int(value)
        except (ValueError, OverflowError):
            return None
    return None


def clamp_limit(value, default=DEFAULT_LIMIT) -> int:
    """Convierte y acota un límite; entradas inválidas usan un valor seguro."""
    fallback = _integer_value(default)
    if fallback is None:
        fallback = DEFAULT_LIMIT
    parsed = _integer_value(value)
    if parsed is None:
        parsed = fallback
    return max(MIN_LIMIT, min(MAX_LIMIT, parsed))


def clamp_interval(value, default=DEFAULT_INTERVAL_SECONDS) -> int:
    """Convierte y acota el intervalo de Auto, expresado en segundos."""
    fallback = _integer_value(default)
    if fallback is None:
        fallback = DEFAULT_INTERVAL_SECONDS
    parsed = _integer_value(value)
    if parsed is None:
        parsed = fallback
    return max(MIN_INTERVAL_SECONDS, min(MAX_INTERVAL_SECONDS, parsed))


def config_path() -> Path:
    """Ubicación de la caché del usuario, independiente del directorio del .py."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        base = Path(base) if base else Path.home() / "AppData" / "Local"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Caches"
    else:
        base = os.environ.get("XDG_CACHE_HOME")
        base = Path(base) if base else Path.home() / ".cache"
    return base / "FutureoMensajes" / "config.json"


class ConfigStore:
    """Persiste límite e intervalo, con reemplazo atómico y errores no fatales."""

    def __init__(self, path=None):
        self.path = Path(path) if path is not None else config_path()
        self.last_error = None

    def load_settings(self) -> tuple:
        """Lee schema 2; schema 1 conserva su límite y adopta un intervalo de 10 s."""
        self.last_error = None
        defaults = (DEFAULT_LIMIT, DEFAULT_INTERVAL_SECONDS)
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except FileNotFoundError:
            return defaults
        except (OSError, UnicodeError, ValueError) as error:
            self.last_error = str(error)
            return defaults
        if not isinstance(data, dict):
            self.last_error = "La configuración guardada no es válida."
            return defaults
        schema = data.get("schema", 1)
        if isinstance(schema, bool) or schema not in (1, 2):
            self.last_error = "La versión de la configuración no es compatible."
            return defaults
        value = _integer_value(data.get("character_limit"))
        if value is None:
            self.last_error = "El límite guardado no es válido."
            return defaults
        if schema == 1:
            return (clamp_limit(value), DEFAULT_INTERVAL_SECONDS)
        interval = _integer_value(data.get("auto_interval_seconds"))
        if interval is None:
            self.last_error = "El intervalo guardado no es válido."
            return defaults
        return (clamp_limit(value), clamp_interval(interval))

    def load_limit(self) -> int:
        """Compatibilidad: devuelve solo el límite de la configuración completa."""
        return self.load_settings()[0]

    def save_limit(self, limit) -> bool:
        """Compatibilidad: actualiza el límite sin borrar el intervalo existente."""
        _, interval = self.load_settings()
        return self.save_settings(limit, interval)

    def save_settings(self, limit, interval) -> bool:
        """Guarda ambos ajustes en una única escritura atómica de schema 2."""
        self.last_error = None
        temporary_path = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "schema": 2,
                "character_limit": clamp_limit(limit),
                "auto_interval_seconds": clamp_interval(interval),
            }
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=str(self.path.parent),
                prefix=".futureo-",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary_path = Path(handle.name)
                json.dump(data, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, self.path)
            temporary_path = None
            return True
        except (OSError, UnicodeError, ValueError, TypeError) as error:
            self.last_error = str(error)
            return False
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink()
                except OSError:
                    pass


class ShuffleBag:
    """Bolsa aleatoria: todos los valores únicos antes de iniciar otra ronda.

    Con dos o más valores evita también repetir al pasar de una ronda a otra.
    ``next()`` sobre una bolsa vacía lanza LookupError.
    """

    def __init__(self, values, rng=None):
        self._rng = rng if rng is not None else random.Random()
        self._values = []
        self._bag = []
        self._has_last = False
        self._last = None
        self.update(values)

    def update(self, values):
        unique = []
        for value in values:
            if value not in unique:
                unique.append(value)
        self._values = unique
        self._bag = []

    def next(self):
        if not self._values:
            raise LookupError("No hay elementos disponibles en la bolsa aleatoria.")
        if not self._bag:
            self._bag = list(self._values)
            self._rng.shuffle(self._bag)
            if (
                len(self._bag) > 1
                and self._has_last
                and self._bag[-1] == self._last
            ):
                self._bag[-1], self._bag[0] = self._bag[0], self._bag[-1]
        chosen = self._bag.pop()
        self._last = chosen
        self._has_last = True
        return chosen


class AutoMessageBank:
    """Selecciona mensajes completos que caben en el límite actual."""

    def __init__(self, messages):
        unique = []
        seen = set()
        for message in messages:
            if not isinstance(message, str):
                continue
            message = normalize_text(message).strip()
            key = message.casefold()
            if message and key not in seen:
                unique.append(message)
                seen.add(key)
        self._messages = tuple(unique)
        self._eligible = ()
        self._bag = ShuffleBag(())
        self.limit = DEFAULT_LIMIT
        self.set_limit(DEFAULT_LIMIT)

    @property
    def eligible_count(self) -> int:
        return len(self._eligible)

    def set_limit(self, limit):
        self.limit = clamp_limit(limit)
        eligible = tuple(message for message in self._messages if len(message) <= self.limit)
        if eligible != self._eligible:
            self._eligible = eligible
            self._bag.update(eligible)

    def next(self) -> str:
        if self._eligible:
            return self._bag.next()
        raise LookupError("No hay mensajes remotos que quepan en el límite actual.")


"""Descarga única del banco remoto. La respuesta se conserva solamente en RAM."""

import queue
import threading
import urllib.request


REMOTE_MESSAGES_URL = "https://raw.githubusercontent.com/mobatfb/archmoba-dev/main/FUTUREOLIVE/mensajes.json"
REMOTE_TIMEOUT_SECONDS = 8.0
MAX_REMOTE_RESPONSE_BYTES = 256 * 1024
MAX_REMOTE_MESSAGES = 2000


def fetch_remote_messages(url: str) -> tuple:
    """Obtiene y valida un array JSON sin caché, escritura de archivos ni reintentos."""
    if not isinstance(url, str) or not url.startswith("https://"):
        raise ValueError("La dirección del banco de mensajes debe usar HTTPS.")
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Cache-Control": "no-cache, no-store",
            "Pragma": "no-cache",
            "User-Agent": "FutureoMensajes/1.2.7",
        },
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=REMOTE_TIMEOUT_SECONDS) as response:
        declared = response.headers.get("Content-Length")
        if declared is not None:
            try:
                declared = int(declared)
            except (TypeError, ValueError):
                declared = None
            if declared is not None and declared > MAX_REMOTE_RESPONSE_BYTES:
                raise ValueError("El banco remoto supera el tamaño permitido.")
        raw = response.read(MAX_REMOTE_RESPONSE_BYTES + 1)
    if len(raw) > MAX_REMOTE_RESPONSE_BYTES:
        raise ValueError("El banco remoto supera el tamaño permitido.")
    messages = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(messages, list) or not 1 <= len(messages) <= MAX_REMOTE_MESSAGES:
        raise ValueError("El banco remoto debe ser un array JSON de mensajes.")
    seen = set()
    for message in messages:
        if not isinstance(message, str):
            raise ValueError("Todos los mensajes remotos deben ser textos.")
        normalized = normalize_text(message).strip()
        if not normalized or len(message) > MAX_LIMIT or "\x00" in message:
            raise ValueError("El banco remoto contiene un mensaje vacío o no válido.")
        key = normalized.casefold()
        if key in seen:
            raise ValueError("El banco remoto contiene mensajes repetidos.")
        seen.add(key)
    return tuple(messages)


def download_messages_to_queue(result_queue, url):
    """Worker sin Tk: publica un único resultado y finaliza, incluso si falla."""
    try:
        messages = fetch_remote_messages(url)
    except Exception as error:
        result_queue.put(("error", f"{type(error).__name__}: {error}"))
    else:
        result_queue.put(("ok", messages))


import math
import time
import tkinter as tk
import tkinter.font as tkfont

APP_VERSION = "1.2.7"
TRANSITIONS = (
    "Desvanecer", "Deslizar izquierda", "Deslizar derecha", "Subir", "Bajar",
    "Zoom", "Barrido izquierda", "Barrido derecha", "Escritura", "Giro suave",
)


def mix_color(first, second, amount):
    amount = max(0.0, min(1.0, amount))
    a = tuple(int(first[i:i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(second[i:i + 2], 16) for i in (1, 3, 5))
    return "#" + "".join(f"{round(x + (y - x) * amount):02x}" for x, y in zip(a, b))


def ease(value):
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def choose_family(root, candidates):
    available = {name.casefold(): name for name in tkfont.families(root)}
    for name in candidates:
        if name.casefold() in available:
            return available[name.casefold()]
    return tkfont.nametofont("TkDefaultFont", root=root).actual("family")


class MessageBanner(tk.Canvas):
    """A locked navy banner; only its lettering participates in transitions."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg="#060b20", highlightthickness=0, **kwargs)
        self.family = choose_family(self, ("Arial Black", "Arial", "Liberation Sans", "DejaVu Sans", "Helvetica"))
        self.current_message = "VOLVEMOS EN UN MOMENTO"
        self.target_message = self.current_message
        self.old_message = self.current_message
        self.effects = ShuffleBag(TRANSITIONS)
        self.effect = TRANSITIONS[0]
        self.active = False
        self.duration = 0.72
        self.started_at = 0.0
        self._tick_id = None
        self._resize_id = None
        self._closed = False
        self._bg = None
        self._margin_patches = []
        self._frame_patches = []
        self._fonts = {}
        self._layouts = {}
        self.w, self.h = 980, 175
        self.bind("<Configure>", self._on_resize)

    def _on_resize(self, event):
        if self._closed:
            return
        if self._resize_id is not None:
            self.after_cancel(self._resize_id)
        self._resize_id = self.after(40, self._resize)

    def _resize(self):
        self._resize_id = None
        if self._closed:
            return
        self.w, self.h = max(200, self.winfo_width()), max(95, self.winfo_height())
        self._layouts.clear()
        rows = []
        for y in range(self.h):
            t = y / max(1, self.h - 1)
            glow = math.sin(math.pi * t) ** 2
            color = (round(4 + 5 * glow), round(9 + 7 * glow), round(24 + 19 * glow))
            rows.append(bytes(color) * self.w)
        ppm = f"P6\n{self.w} {self.h}\n255\n".encode("ascii") + b"".join(rows)
        self._bg = tk.PhotoImage(master=self, data=ppm, format="PPM")
        left, top, right, bottom = self.content_rect()
        self._margin_patches = []
        for box in ((0, 0, self.w, top), (0, bottom, self.w, self.h),
                    (0, top, left, bottom), (right, top, self.w, bottom)):
            patch = self._crop_background(*box)
            if patch is not None:
                self._margin_patches.append((box[0], box[1], patch))
        self._render(self._progress() if self.active else 1.0)

    def content_rect(self):
        margin_x = min(42, max(22, self.w // 24))
        margin_y = min(16, max(10, self.h // 10))
        return margin_x, margin_y, self.w - margin_x, self.h - margin_y

    def _crop_background(self, x0, y0, x1, y1):
        x0, y0, x1, y1 = [int(round(v)) for v in (x0, y0, x1, y1)]
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(self.w, x1), min(self.h, y1)
        if self._bg is None or x1 <= x0 or y1 <= y0:
            return None
        patch = tk.PhotoImage(master=self, width=x1 - x0, height=y1 - y0)
        self.tk.call(str(patch), "copy", str(self._bg), "-from", x0, y0, x1, y1, "-to", 0, 0)
        return patch

    def _font(self, pixels):
        pixels = max(2, min(240, int(round(pixels))))
        if pixels not in self._fonts:
            self._fonts[pixels] = tkfont.Font(root=self, family=self.family,
                                            size=-pixels, weight="bold", slant="italic")
        return self._fonts[pixels]

    @staticmethod
    def _wrap(text, font, width):
        if font.measure(text) <= width:
            return [text]
        lines, line = [], ""
        for word in text.split():
            candidate = f"{line} {word}" if line else word
            if font.measure(candidate) <= width:
                line = candidate
                continue
            if line:
                lines.append(line)
                line = ""
            # Long unbroken words are split instead of extending outside the panel.
            while word and font.measure(word) > width:
                lo, hi = 1, len(word)
                while lo < hi:
                    mid = (lo + hi + 1) // 2
                    if font.measure(word[:mid]) <= width:
                        lo = mid
                    else:
                        hi = mid - 1
                lines.append(word[:lo])
                word = word[lo:]
            line = word
        if line:
            lines.append(line)
        return lines or [""]

    def _layout(self, text):
        if text in self._layouts:
            return self._layouts[text]
        left, top, right, bottom = self.content_rect()
        available_w = max(40, right - left - 24)
        available_h = max(20, bottom - top - 10)
        lo, hi = 2, min(32, int(available_h * 0.48))
        best = (2, self._wrap(text, self._font(2), available_w))
        while lo <= hi:
            mid = (lo + hi) // 2
            font = self._font(mid)
            lines = self._wrap(text, font, available_w)
            if len(lines) * font.metrics("linespace") <= available_h:
                best = (mid, lines)
                lo = mid + 1
            else:
                hi = mid - 1
        self._layouts[text] = best
        if len(self._layouts) > 10:
            first = next(iter(self._layouts))
            if first != text:
                self._layouts.pop(first)
        return best

    def _draw_text(self, text, opacity=1.0, dx=0.0, dy=0.0, scale=1.0, angle=0.0,
                   visible_chars=None):
        if not text or opacity <= 0.002:
            return
        size, lines = self._layout(text)
        font = self._font(size * scale)
        rendered = "\n".join(lines)
        x, y = self.w / 2 + dx, self.h / 2 + dy
        common = dict(text=rendered, font=font, justify="center", anchor="center", angle=angle)
        # An outline and layered soft glow approximate the supplied bold italic sample.
        colors = ((0, 3, "#020611"), (-2, 1, "#123a86"), (2, 0, "#245594"),
                  (0, 1, "#94b1e7"), (0, 0, "#f6f8ff"))
        if visible_chars is not None:
            # Anchor each revealed prefix at the final full line's left edge.
            # Spaces are not used as placeholders: proportional fonts would wobble.
            remaining = visible_chars
            line_height = font.metrics("linespace")
            for index, line in enumerate(lines):
                prefix = line[:max(0, remaining)]
                remaining -= len(line) + 1
                if not prefix:
                    continue
                lx = x - font.measure(line) / 2
                ly = y + (index - (len(lines) - 1) / 2) * line_height
                for ox, oy, color in colors:
                    self.create_text(lx + ox, ly + oy, text=prefix, font=font,
                                     anchor="w", fill=mix_color("#090f2a", color, opacity))
            return
        for ox, oy, color in colors:
            fill = mix_color("#090f2a", color, opacity)
            self.create_text(x + ox, y + oy, fill=fill, **common)

    def _hide_area(self, x0, y0, x1, y1):
        patch = self._crop_background(x0, y0, x1, y1)
        if patch is not None:
            self._frame_patches.append(patch)
            self.create_image(round(x0), round(y0), image=patch, anchor="nw")

    def _draw_frame(self):
        for x, y, patch in self._margin_patches:
            self.create_image(x, y, image=patch, anchor="nw")
        w, h = self.w, self.h
        bevel = min(30, h * 0.18)
        left = [10, h / 2, 10 + bevel, 12, w * 0.55, 12]
        right = [w * 0.45, h - 12, w - 10 - bevel, h - 12, w - 10, h / 2]
        left_bottom = [10, h / 2, 10 + bevel, h - 12, w * 0.45, h - 12]
        right_top = [w * 0.55, 12, w - 10 - bevel, 12, w - 10, h / 2]
        for points, halo, color in ((left, "#0b2452", "#2ebcff"),
                                     (left_bottom, "#071d45", "#2466b7"),
                                     (right, "#211045", "#b940f6"),
                                     (right_top, "#1a123c", "#6047aa")):
            self.create_line(*points, fill=halo, width=5, joinstyle="round")
            self.create_line(*points, fill=color, width=1.3, joinstyle="round")

    def _progress(self):
        return min(1.0, max(0.0, (time.perf_counter() - self.started_at) / self.duration))

    def _render(self, p):
        if self._bg is None or self._closed:
            return
        self.delete("all")
        self._frame_patches.clear()
        self.create_image(0, 0, image=self._bg, anchor="nw")
        if not self.active or p >= 1:
            self._draw_text(self.target_message)
            self._draw_frame()
            return
        old, new, kind, q = self.old_message, self.target_message, self.effect, ease(p)
        if kind == "Desvanecer":
            if p < 0.5:
                self._draw_text(old, opacity=1 - ease(p * 2))
            else:
                self._draw_text(new, opacity=ease((p - 0.5) * 2))
        elif kind in ("Deslizar izquierda", "Deslizar derecha", "Subir", "Bajar"):
            direction = -1 if kind in ("Deslizar izquierda", "Subir") else 1
            horizontal = kind.startswith("Deslizar")
            travel = self.w + 35 if horizontal else self.h + 15
            old_offset = direction * q * travel
            new_offset = -direction * (1 - q) * travel
            self._draw_text(old, dx=old_offset if horizontal else 0,
                            dy=0 if horizontal else old_offset)
            self._draw_text(new, dx=new_offset if horizontal else 0,
                            dy=0 if horizontal else new_offset)
        elif kind == "Zoom":
            if p < 0.42:
                a = ease(p / 0.42)
                self._draw_text(old, opacity=1 - a, scale=1 + 0.30 * a)
            else:
                a = ease((p - 0.42) / 0.58)
                self._draw_text(new, opacity=a, scale=0.50 + 0.50 * a)
        elif kind in ("Barrido izquierda", "Barrido derecha"):
            left, top, right, bottom = self.content_rect()
            width = right - left
            reverse = kind == "Barrido derecha"
            if p < 0.5:
                a = ease(p * 2)
                self._draw_text(old)
                if reverse:
                    self._hide_area(right - width * a, top, right, bottom)
                else:
                    self._hide_area(left, top, left + width * a, bottom)
            else:
                a = ease((p - 0.5) * 2)
                self._draw_text(new)
                if reverse:
                    self._hide_area(left, top, right - width * a, bottom)
                else:
                    self._hide_area(left + width * a, top, right, bottom)
        elif kind == "Escritura":
            if p < 0.20:
                self._draw_text(old, opacity=1 - p / 0.20)
            else:
                total = len("\n".join(self._layout(new)[1]))
                count = math.ceil(total * min(1, (p - 0.20) / 0.80))
                self._draw_text(new, visible_chars=count)
        elif kind == "Giro suave":
            if p < 0.45:
                a = ease(p / 0.45)
                self._draw_text(old, opacity=1 - a, angle=9 * a, dy=-12 * a)
            else:
                a = ease((p - 0.45) / 0.55)
                self._draw_text(new, opacity=a, angle=-9 * (1 - a), dy=12 * (1 - a))
        self._draw_frame()

    def show_message(self, message, effect=None):
        if self._closed:
            return
        if self._tick_id is not None:
            self.after_cancel(self._tick_id)
            self._tick_id = None
        # A new submission supersedes any pending animation; there is no stale queue.
        self.old_message = self.target_message
        self.target_message = message
        self.current_message = message
        self.effect = effect if effect in TRANSITIONS else self.effects.next()
        self.duration = 1.0 if self.effect == "Escritura" else 0.72
        self._layout(message)
        self.active = True
        self.started_at = time.perf_counter()
        self._tick()

    def _tick(self):
        self._tick_id = None
        if self._closed:
            return
        p = self._progress()
        self._render(p)
        if p >= 1:
            self.active = False
        else:
            self._tick_id = self.after(16, self._tick)

    def close(self):
        self._closed = True
        for handle in (self._tick_id, self._resize_id):
            if handle is not None:
                try:
                    self.after_cancel(handle)
                except tk.TclError:
                    pass
        self._tick_id = self._resize_id = None


class FutureoMessagesApp:
    def __init__(self, root, store=None):
        self.root = root
        self.store = store or ConfigStore()
        self.limit, self.interval_seconds = self.store.load_settings()
        self.message_bank = AutoMessageBank(())
        self.message_bank.set_limit(self.limit)
        self._editing = False
        self._editing_limit = False
        self._editing_interval = False
        self._closed = False
        self._save_job = None
        self._auto_job = None
        self._auto_generation = 0
        self._cache_failed = False
        self._messages_state = "loading"
        self._messages_count = 0
        self._remote_error = ""
        self._remote_load_started = False
        self._remote_results = queue.Queue(maxsize=1)
        self._remote_poll_job = None
        self._remote_thread = None
        self.last_origin = "initial"
        self.sent_count = 0
        root.title(f"FUTUREO · Mensajes {APP_VERSION}")
        root.geometry("390x300")
        root.minsize(390, 290)
        root.configure(bg="#070c1c")
        root.attributes("-topmost", True)  # Mantener esta ventana delante de las demás.
        root.rowconfigure(0, weight=1, minsize=95)
        root.columnconfigure(0, weight=1)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.ui_family = choose_family(root, ("Segoe UI", "Arial", "Liberation Sans", "DejaVu Sans"))
        self.input_var = tk.StringVar(root)
        self.limit_var = tk.StringVar(root, value=str(self.limit))
        self.interval_var = tk.StringVar(root, value=str(self.interval_seconds))
        self.auto_var = tk.BooleanVar(root, value=False)
        self.banner = MessageBanner(root, height=106)
        self.banner.grid(row=0, column=0, sticky="nsew", padx=8, pady=(8, 5))
        self._build_controls()
        self.input_var.trace_add("write", self._input_changed)
        self.limit_var.trace_add("write", self._limit_changed)
        self.interval_var.trace_add("write", self._interval_changed)
        self._update_counter()
        self._update_status()
        root.after_idle(self.entry.focus_set)
        self._start_message_load()

    def _build_controls(self):
        panel = tk.Frame(self.root, bg="#0c1428", padx=10, pady=7)
        panel.grid(row=1, column=0, sticky="ew")
        panel.columnconfigure(0, weight=1)
        panel.columnconfigure(1, weight=1)
        panel.columnconfigure(2, weight=1)
        panel.columnconfigure(3, weight=1)
        label_options = dict(bg="#0c1428", fg="#9daecd", font=(self.ui_family, 8))
        tk.Label(panel, text="MENSAJE", **label_options).grid(row=0, column=0, sticky="w", pady=(0, 5))
        tk.Label(panel, text="LÍMITE", **label_options).grid(row=3, column=0, sticky="w", pady=(6, 3))
        tk.Label(panel, text="SEGUNDOS", **label_options).grid(row=3, column=1, sticky="w", pady=(6, 3))
        self.entry = tk.Entry(panel, textvariable=self.input_var, bg="#071023", fg="#f5f8ff",
                              insertbackground="#38c9ff", selectbackground="#244e7d",
                              selectforeground="#ffffff", relief="flat", highlightthickness=1,
                              highlightbackground="#233754", highlightcolor="#37bfff",
                              font=(self.ui_family, 10))
        self.entry.grid(row=1, column=0, columnspan=4, sticky="ew", ipady=5)
        self.entry.bind("<Return>", self.send_manual)
        self.entry.bind("<KP_Enter>", self.send_manual)
        self.entry.bind("<Control-a>", self._select_all)
        self.entry.bind("<Control-A>", self._select_all)
        valid_number = (self.root.register(lambda value: value == "" or (value.isdecimal() and len(value) <= 4)), "%P")
        self.limit_spin = tk.Spinbox(panel, from_=MIN_LIMIT, to=MAX_LIMIT, textvariable=self.limit_var,
                                    command=self._commit_limit, width=5, justify="center",
                                    validate="key", validatecommand=valid_number,
                                    bg="#101d36", fg="#e7f3ff", buttonbackground="#253a58",
                                    insertbackground="#ffffff", relief="flat", highlightthickness=1,
                                    highlightbackground="#233754", highlightcolor="#37bfff",
                                    font=(self.ui_family, 10, "bold"))
        self.limit_spin.grid(row=4, column=0, sticky="ew", padx=(0, 5), ipady=3)
        self.limit_spin.bind("<FocusOut>", self._commit_limit)
        self.limit_spin.bind("<Return>", self._commit_limit)
        self.limit_spin.bind("<KP_Enter>", self._commit_limit)
        self.limit_spin.bind("<Control-a>", self._select_all)
        self.limit_spin.bind("<Control-A>", self._select_all)
        self.interval_spin = tk.Spinbox(panel, from_=MIN_INTERVAL_SECONDS, to=MAX_INTERVAL_SECONDS,
                                       textvariable=self.interval_var, command=self._commit_interval,
                                       width=5, justify="center", validate="key", validatecommand=valid_number,
                                       bg="#101d36", fg="#e7f3ff", buttonbackground="#253a58",
                                       insertbackground="#ffffff", relief="flat", highlightthickness=1,
                                       highlightbackground="#233754", highlightcolor="#37bfff",
                                       font=(self.ui_family, 10, "bold"))
        self.interval_spin.grid(row=4, column=1, sticky="ew", padx=(0, 5), ipady=3)
        self.interval_spin.bind("<FocusOut>", self._commit_interval)
        self.interval_spin.bind("<Return>", self._commit_interval)
        self.interval_spin.bind("<KP_Enter>", self._commit_interval)
        self.interval_spin.bind("<Control-a>", self._select_all)
        self.interval_spin.bind("<Control-A>", self._select_all)
        self.auto_check = tk.Checkbutton(panel, text="Auto", variable=self.auto_var,
                                        command=self._toggle_auto, bg="#0c1428", fg="#dbe8ff",
                                        activebackground="#0c1428", activeforeground="#47d3ff",
                                        selectcolor="#173153", highlightthickness=0,
                                        font=(self.ui_family, 10), cursor="hand2", state="disabled")
        self.auto_check.grid(row=4, column=2, sticky="ew", padx=(0, 3))
        self.send_button = tk.Button(panel, text="ENVIAR  ↵", command=self.send_manual,
                                     bg="#24bfff", fg="#041526", activebackground="#58d1ff",
                                     activeforeground="#041526", relief="flat", borderwidth=0,
                                     font=(self.ui_family, 10, "bold"), padx=10, pady=6,
                                     cursor="hand2")
        self.send_button.grid(row=4, column=3, sticky="ew")
        self.counter = tk.Label(panel, text="", **label_options)
        self.counter.grid(row=2, column=0, columnspan=4, sticky="w", pady=(3, 0))
        self.status = tk.Label(panel, text="", **label_options)
        self.status.grid(row=5, column=0, columnspan=4, sticky="w", pady=(5, 0))

    def _select_all(self, event=None):
        widget = event.widget if event is not None else self.entry
        widget.selection_range(0, "end")
        widget.icursor("end")
        return "break"

    def _input_changed(self, *args):
        if self._editing or self._closed:
            return
        raw = self.input_var.get()
        cleaned = normalize_text(raw)[:self.limit]
        if cleaned != raw:
            self._editing = True
            self.input_var.set(cleaned)
            self._editing = False
        self._update_counter()

    def _update_counter(self):
        count = len(self.input_var.get())
        self.counter.configure(text=f"{count} / {self.limit} caracteres",
                               fg="#ffc773" if count >= self.limit else "#9daecd")

    def _update_status(self):
        if self._messages_state == "loading":
            text, color = "Cargando mensajes para Auto…", "#9daecd"
        elif self._messages_state == "error":
            text, color = "Auto no disponible: reabre para reintentar", "#ffc773"
        elif self.message_bank.eligible_count == 0:
            text, color = "Aumenta el límite para usar Auto", "#ffc773"
        elif self._cache_failed:
            text, color = "No se pudieron guardar los ajustes", "#ffc773"
        elif self.auto_var.get():
            count = self.message_bank.eligible_count
            text = f"Auto cada {self.interval_seconds} s · {count} frases disponibles"
            color = "#54cfff"
        else:
            text, color = f"Enter para enviar · {self._messages_count} mensajes en Auto", "#9daecd"
        self.status.configure(text=text, fg=color)

    def _can_auto(self):
        return self._messages_state == "ready" and self.message_bank.eligible_count > 0

    def _sync_auto_availability(self):
        available = self._can_auto()
        self.auto_check.configure(state="normal" if available else "disabled")
        if not available:
            self.auto_var.set(False)
            self._cancel_auto()

    def _start_message_load(self):
        # This guard lasts for the complete lifetime of this window. Neither controls
        # nor failures reset it: reopening the application is the only retry path.
        if self._closed or self._remote_load_started:
            return
        self._remote_load_started = True
        self._messages_state = "loading"
        self._sync_auto_availability()
        self._update_status()
        self._remote_thread = threading.Thread(
            target=download_messages_to_queue,
            args=(self._remote_results, REMOTE_MESSAGES_URL),
            daemon=True,
            name="FutureoMensajesRemote",
        )
        try:
            self._remote_thread.start()
        except RuntimeError as error:
            self._messages_state = "error"
            self._remote_error = str(error)
            self._sync_auto_availability()
            self._update_status()
            return
        self._remote_poll_job = self.root.after(75, self._poll_message_load)

    def _poll_message_load(self):
        self._remote_poll_job = None
        if self._closed:
            return
        try:
            outcome, payload = self._remote_results.get_nowait()
        except queue.Empty:
            self._remote_poll_job = self.root.after(75, self._poll_message_load)
            return
        if outcome == "ok":
            self.message_bank = AutoMessageBank(payload)
            self.message_bank.set_limit(self.limit)
            self._messages_count = len(payload)
            self._messages_state = "ready"
        else:
            self._messages_state = "error"
            self._remote_error = str(payload)
        self._sync_auto_availability()
        self._update_status()

    def _limit_changed(self, *args):
        if self._editing_limit or self._closed:
            return
        raw = self.limit_var.get()
        if not raw.isdecimal() or not MIN_LIMIT <= int(raw) <= MAX_LIMIT:
            self.limit_spin.configure(highlightbackground="#d19d56")
            return
        self.limit_spin.configure(highlightbackground="#233754")
        # Do not apply intermediate digits: changing 80 to 120 passes through "1".
        # Commit on Enter, leaving the field, or clicking a Spinbox arrow.

    def _commit_limit(self, event=None):
        raw = self.limit_var.get()
        value = int(raw) if raw.isdecimal() and MIN_LIMIT <= int(raw) <= MAX_LIMIT else self.limit
        self._editing_limit = True
        self.limit_var.set(str(value))
        self._editing_limit = False
        self.limit_spin.configure(highlightbackground="#233754")
        if value != self.limit:
            self.limit = value
            self.message_bank.set_limit(value)
            self._sync_auto_availability()
            self._input_changed()
            self._schedule_settings_save()
        self._update_counter()
        self._update_status()
        if event is not None and event.type == tk.EventType.KeyPress:
            self.entry.focus_set()
        return "break" if event is not None and event.type == tk.EventType.KeyPress else None

    def _interval_changed(self, *args):
        if self._editing_interval or self._closed:
            return
        raw = self.interval_var.get()
        valid = raw.isdecimal() and MIN_INTERVAL_SECONDS <= int(raw) <= MAX_INTERVAL_SECONDS
        self.interval_spin.configure(highlightbackground="#233754" if valid else "#d19d56")

    def _commit_interval(self, event=None):
        raw = self.interval_var.get()
        value = (int(raw) if raw.isdecimal() and MIN_INTERVAL_SECONDS <= int(raw) <= MAX_INTERVAL_SECONDS
                 else self.interval_seconds)
        self._editing_interval = True
        self.interval_var.set(str(value))
        self._editing_interval = False
        self.interval_spin.configure(highlightbackground="#233754")
        if value != self.interval_seconds:
            self.interval_seconds = value
            self._schedule_settings_save()
            if self.auto_var.get():
                self._restart_auto()
        self._update_status()
        if event is not None and event.type == tk.EventType.KeyPress:
            self.entry.focus_set()
        return "break" if event is not None and event.type == tk.EventType.KeyPress else None

    def _schedule_settings_save(self):
        if self._save_job is not None:
            self.root.after_cancel(self._save_job)
        self._save_job = self.root.after(250, self._save_settings)

    def _save_settings(self):
        self._save_job = None
        if self._closed:
            return
        self._cache_failed = not self.store.save_settings(self.limit, self.interval_seconds)
        self._update_status()

    def send_manual(self, event=None):
        if self._closed:
            return "break"
        self._commit_limit()
        self._commit_interval()
        message = normalize_text(self.input_var.get()).strip()[:self.limit]
        if not message:
            self.entry.focus_set()
            return "break"
        self.banner.show_message(message)
        self.last_origin = "manual"
        self.sent_count += 1
        self.input_var.set("")
        self.entry.focus_set()
        if self.auto_var.get():
            self._restart_auto()
        return "break"

    def _cancel_auto(self):
        self._auto_generation += 1
        if self._auto_job is not None:
            try:
                self.root.after_cancel(self._auto_job)
            except tk.TclError:
                pass
        self._auto_job = None

    def _restart_auto(self):
        self._cancel_auto()
        if not self._closed and self.auto_var.get() and self._can_auto():
            token = self._auto_generation
            self._auto_job = self.root.after(self.interval_seconds * 1000, lambda: self._auto_tick(token))

    def _toggle_auto(self):
        self._commit_interval()
        if not self._can_auto():
            self.auto_var.set(False)
        self._restart_auto()
        self._update_status()

    def _auto_tick(self, token):
        if (self._closed or token != self._auto_generation or not self.auto_var.get()
                or not self._can_auto()):
            return
        self._auto_job = None
        message = self.message_bank.next()
        self.banner.show_message(message)
        self.last_origin = "auto"
        self.sent_count += 1
        # Leave both the draft and keyboard focus untouched during automatic sending.
        self._auto_job = self.root.after(self.interval_seconds * 1000, lambda: self._auto_tick(token))

    def close(self):
        if self._closed:
            return
        self._commit_limit()
        self._commit_interval()
        self.store.save_settings(self.limit, self.interval_seconds)
        self._closed = True
        self._cancel_auto()
        if self._remote_poll_job is not None:
            try:
                self.root.after_cancel(self._remote_poll_job)
            except tk.TclError:
                pass
            self._remote_poll_job = None
        if self._save_job is not None:
            try:
                self.root.after_cancel(self._save_job)
            except tk.TclError:
                pass
        self.banner.close()
        self.root.destroy()


def hide_windows_console():
    """Oculta la consola creada al abrir este .py con Python en Windows.

    No intenta cerrar una consola compartida con otros procesos; en ese caso
    la deja intacta para no ocultar el terminal del usuario.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        hwnd = kernel32.GetConsoleWindow()
        if not hwnd:
            return
        members = (ctypes.c_ulong * 16)()
        number = kernel32.GetConsoleProcessList(members, len(members))
        if number == 1:
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE
    except (OSError, AttributeError, ValueError):
        pass


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Panel FUTUREO de mensajes con 10 transiciones y 500 frases automáticas.")
    parser.add_argument("--config", type=Path, default=None,
                        help="Ruta opcional del archivo de configuración (normalmente no hace falta).")
    args = parser.parse_args()
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
    hide_windows_console()
    root = tk.Tk()
    FutureoMessagesApp(root, store=ConfigStore(args.config))
    root.mainloop()


if __name__ == "__main__":
    main()
