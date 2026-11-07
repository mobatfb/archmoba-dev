# ARGUMENTOS: audio cutter recortar cortar audio mp3 wav m4a flac ogg fragmento inicio fin vista previa exportar
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Audio Cutter v1.0.5: límites arrastrables y aguja de reproducción."""
import os
import re
import shutil
import subprocess
import threading
import tempfile
import time
import wave
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

TOOL_NAME = "Audio Cutter"
TOOL_DESCRIPTION = "Recorta fragmentos de audio con controles de inicio y fin, vista previa y exportación."
INPUT_TYPES = [("Audio", "*.mp3 *.wav *.flac *.m4a *.aac *.ogg *.opus *.wma"), ("Todos", "*.*")]
EXPORT_TYPES = ("mp3", "wav", "flac", "m4a", "ogg")
BG = "#0c1425"
PANEL = "#17243a"
FG = "#edf4ff"
MUTED = "#a4bad4"
ACCENT = "#37ddd0"


def parse_time(value):
    """Acepta segundos, MM:SS o HH:MM:SS (con decimales)."""
    parts = value.strip().replace(",", ".").split(":")
    if not 1 <= len(parts) <= 3:
        raise ValueError("Usa segundos, MM:SS o HH:MM:SS.")
    try:
        numbers = [float(p) for p in parts]
    except ValueError as exc:
        raise ValueError("El tiempo contiene caracteres inválidos.") from exc
    if any(n < 0 or not n < float("inf") for n in numbers):
        raise ValueError("Los tiempos deben ser finitos y positivos.")
    if len(numbers) > 1 and any(n >= 60 for n in numbers[1:]):
        raise ValueError("Segundos y minutos secundarios deben ser menores que 60.")
    seconds = 0.0
    for n in numbers:
        seconds = seconds * 60 + n
    return seconds


def format_time(seconds):
    seconds = max(0, float(seconds))
    hours = int(seconds // 3600)
    minutes = int(seconds // 60) % 60
    sec = seconds % 60
    return (f"{hours:02d}:" if hours else "") + f"{minutes:02d}:{sec:05.2f}"


def hidden_kwargs():
    if os.name == "nt":
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    return {}


def get_ffmpeg():
    """Prioriza FFmpeg del sistema y utiliza el binario portable de imageio-ffmpeg."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        binary = imageio_ffmpeg.get_ffmpeg_exe()
        if binary and Path(binary).is_file():
            return binary
    except (ImportError, RuntimeError, OSError):
        pass
    return None


def audio_duration(path):
    """Lee duración con Mutagen o el motor portable FFmpeg de PTM."""
    errors = []
    try:
        from mutagen import File as AudioFile
        audio = AudioFile(str(path))
        if audio is not None and audio.info is not None:
            value = float(audio.info.length)
            if 0 < value < float("inf"):
                return value
        errors.append("Mutagen no reconoció el audio")
    except Exception as exc:
        errors.append(f"Mutagen: {exc}")
    if path.suffix.lower() == ".wav":
        try:
            with wave.open(str(path), "rb") as source:
                return source.getnframes() / source.getframerate()
        except (wave.Error, EOFError, OSError) as exc:
            errors.append(f"WAV: {exc}")
    probe = shutil.which("ffprobe")
    if probe:
        try:
            command = [probe, "-v", "error", "-show_entries", "format=duration",
                       "-of", "default=noprint_wrappers=1:nokey=1", str(path)]
            result = subprocess.run(command, capture_output=True, text=True,
                                    timeout=35, **hidden_kwargs())
            if result.returncode == 0:
                value = float(result.stdout.strip())
                if 0 < value < float("inf"):
                    return value
        except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
            errors.append(f"FFprobe: {exc}")
    ffmpeg = get_ffmpeg()
    if ffmpeg:
        try:
            result = subprocess.run(
                [ffmpeg, "-hide_banner", "-i", str(path)],
                stdin=subprocess.DEVNULL, capture_output=True, text=True,
                timeout=35, **hidden_kwargs(),
            )
            match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", result.stderr)
            if match:
                hours, minutes, seconds = match.groups()
                value = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
                if value > 0:
                    return value
            errors.append("FFmpeg no pudo identificar la duración")
        except (OSError, subprocess.TimeoutExpired) as exc:
            errors.append(f"FFmpeg: {exc}")
    raise RuntimeError(
        "No se pudo analizar el audio. Comprueba el MP3 o las dependencias de PTM. "
        + " | ".join(errors)[:300]
    )


def trim_pcm_wav(source, destination, start, end, cancel):
    """Alternativa sin FFmpeg para archivos WAV PCM."""
    temporary = destination.with_name(destination.name + ".part")
    try:
        with wave.open(str(source), "rb") as reader:
            if reader.getcomptype() != "NONE":
                raise RuntimeError("Este WAV necesita FFmpeg para su conversión.")
            rate = reader.getframerate()
            first = int(start * rate)
            last = min(reader.getnframes(), int(end * rate))
            reader.setpos(first)
            with wave.open(str(temporary), "wb") as writer:
                writer.setparams(reader.getparams())
                remaining = last - first
                while remaining > 0:
                    if cancel.is_set():
                        raise RuntimeError("Corte cancelado.")
                    block = reader.readframes(min(32768, remaining))
                    if not block:
                        break
                    writer.writeframesraw(block)
                    remaining -= min(32768, len(block) // (reader.getsampwidth() * reader.getnchannels()))
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


class AudioCutter(tk.Frame):
    def __init__(self, parent, app=None):
        super().__init__(parent, bg=BG)
        self.app = app
        self.source = None
        self.duration = 0.0
        self.worker_running = False
        self.cancel = threading.Event()
        self.preview_process = None
        self.preview_temp = None
        self.preview_generation = 0
        self.preview_cancel = threading.Event()
        self.preview_alias = None
        self.preview_backend = None
        self.preview_started_at = 0.0
        self.preview_deadline = 0.0
        self.preview_source = None
        self.playhead = 0.0
        self.preview_from = 0.0
        self.drag_target = None
        self.playhead_var = tk.StringVar(value='00:00.00')
        self.start_var = tk.StringVar(value="00:00.00")
        self.end_var = tk.StringVar(value="00:00.00")
        self.format_var = tk.StringVar(value="mp3")
        self.source_var = tk.StringVar(value="Ningún archivo seleccionado")
        self.status_var = tk.StringVar(value="Selecciona un archivo de audio para comenzar.")
        self.detail_var = tk.StringVar(value="Duración: --  |  Selección: --")
        self._make_ui()
        self.bind("<Destroy>", self._on_destroy, add="+")

    def _label(self, parent, text, **kwargs):
        return tk.Label(parent, text=text, fg=kwargs.pop("fg", FG), bg=kwargs.pop("bg", PANEL),
                        font=("Segoe UI", kwargs.pop("size", 10),
                              "bold" if kwargs.pop("bold", False) else "normal"),
                        anchor="w", **kwargs)

    def _button(self, parent, text, command, bright=False):
        return tk.Button(parent, text=text, command=command, bd=0,
                         relief="flat", cursor="hand2", padx=16, pady=8,
                         bg=ACCENT if bright else "#2b405d",
                         fg="#092032" if bright else FG,
                         font=("Segoe UI", 10, "bold"))

    def _make_ui(self):
        header = tk.Frame(self, bg=BG, padx=16, pady=10)
        header.pack(fill="x")
        self._label(header, "AUDIO CUTTER", bg=BG, fg=ACCENT, size=16, bold=True).pack(anchor="w")
        self._label(header, "Recorta audio por intervalo sin modificar el original.", bg=BG, fg=MUTED).pack(anchor="w")
        body = tk.Frame(self, bg=BG, padx=16)
        body.pack(fill="both", expand=True)
        filebox = tk.Frame(body, bg=PANEL, padx=14, pady=12)
        filebox.pack(fill="x", pady=(0, 9))
        self._label(filebox, "1. ARCHIVO DE AUDIO", fg=ACCENT, bold=True).pack(anchor="w")
        line = tk.Frame(filebox, bg=PANEL)
        line.pack(fill="x", pady=(8, 0))
        self._label(line, "", fg=FG, textvariable=self.source_var).pack(side="left", fill="x", expand=True)
        self._button(line, "Seleccionar audio", self.choose_file).pack(side="right")
        settings = tk.Frame(body, bg=PANEL, padx=14, pady=12)
        settings.pack(fill="x", pady=(0, 9))
        self._label(settings, "2. INTERVALO DE CORTE", fg=ACCENT, bold=True).pack(anchor="w")
        row = tk.Frame(settings, bg=PANEL)
        row.pack(fill="x", pady=(8, 6))
        self._label(row, "Desde").pack(side="left")
        self.start_entry = tk.Entry(row, textvariable=self.start_var, width=12,
                                    font=("Consolas", 11), bg="#f1f6ff", fg="#112039")
        self.start_entry.pack(side="left", padx=(6, 18))
        self._label(row, "Hasta").pack(side="left")
        self.end_entry = tk.Entry(row, textvariable=self.end_var, width=12,
                                  font=("Consolas", 11), bg="#f1f6ff", fg="#112039")
        self.end_entry.pack(side="left", padx=(6, 18))
        self._button(row, "Usar todo", self.full_range).pack(side="left")
        self._label(settings, "", textvariable=self.detail_var, fg=MUTED).pack(anchor="w")
        self.timeline = tk.Canvas(settings, height=62, bg="#0d182b",
                                  highlightthickness=0, cursor="crosshair")
        self.timeline.pack(fill="x", pady=(9, 3))
        self.timeline.bind("<ButtonPress-1>", self._timeline_press)
        self.timeline.bind("<B1-Motion>", self._timeline_drag)
        self.timeline.bind("<ButtonRelease-1>", self._timeline_release)
        self.timeline.bind("<Motion>", self._timeline_hover)
        self.timeline.bind("<Configure>", lambda _event: self._draw_timeline())
        self.start_var.trace_add("write", lambda *_: self._draw_timeline())
        self.end_var.trace_add("write", lambda *_: self._draw_timeline())
        controls = tk.Frame(settings, bg=PANEL)
        controls.pack(fill="x")
        self._label(controls, "Arrastra VERDE: inicio  |  ROJO: fin  |  AMARILLO: reproducir",
                    fg=MUTED, size=9).pack(side="left")
        self._label(controls, "", textvariable=self.playhead_var, fg="#ffd166",
                    size=9, bold=True).pack(side="right")
        output = tk.Frame(body, bg=PANEL, padx=14, pady=12)
        output.pack(fill="x", pady=(0, 9))
        self._label(output, "3. EXPORTAR FRAGMENTO", fg=ACCENT, bold=True).pack(anchor="w")
        actions = tk.Frame(output, bg=PANEL)
        actions.pack(fill="x", pady=(8, 0))
        self._label(actions, "Formato").pack(side="left")
        ttk.Combobox(actions, textvariable=self.format_var, state="readonly",
                     values=EXPORT_TYPES, width=7).pack(side="left", padx=(8, 15))
        self.preview_btn = self._button(actions, "▶ Vista previa", self.preview)
        self.preview_btn.pack(side="left", padx=(0, 6))
        self._button(actions, "■ Detener", self.stop_preview).pack(side="left", padx=(0, 6))
        self.export_btn = self._button(actions, "RECORTAR Y GUARDAR", self.export, bright=True)
        self.export_btn.pack(side="right")
        bottom = tk.Frame(body, bg=PANEL, padx=14, pady=12)
        bottom.pack(fill="x", side="bottom", pady=(0, 8))
        self._label(bottom, "ESTADO", fg=ACCENT, bold=True).pack(anchor="w")
        self.progress = ttk.Progressbar(bottom, mode="indeterminate")
        self.progress.pack(fill="x", pady=(8, 6))
        self._label(bottom, "", textvariable=self.status_var, fg=MUTED).pack(fill="x")

    def _ui(self, callback):
        try:
            if self.winfo_exists():
                self.after(0, callback)
        except tk.TclError:
            pass

    def _busy(self, active):
        self.worker_running = active
        self.export_btn.configure(state="disabled" if active else "normal")
        if active:
            self.progress.start(12)
        else:
            self.progress.stop()

    def choose_file(self):
        if self.worker_running:
            return
        name = filedialog.askopenfilename(parent=self, title="Seleccionar audio", filetypes=INPUT_TYPES)
        if not name:
            return
        path = Path(name)
        self.status_var.set("Analizando duración...")
        self._busy(True)

        def work():
            try:
                duration = audio_duration(path)
                def done():
                    self.source = path
                    self.duration = duration
                    self.source_var.set(path.name)
                    self.stop_preview(update_status=False)
                    self.playhead = 0.0
                    self.start_var.set("00:00.00")
                    self.end_var.set(format_time(duration))
                    self.detail_var.set(f"Duración: {format_time(duration)}")
                    self.status_var.set("Audio listo para recortar.")
                    self._busy(False)
                    self._draw_timeline()
                self._ui(done)
            except Exception as exc:
                self._ui(lambda error=str(exc): (self._busy(False),
                         self.status_var.set(error), messagebox.showerror("Audio Cutter", error, parent=self)))
        threading.Thread(target=work, daemon=True).start()

    def _selection(self):
        if not self.source or self.duration <= 0:
            raise ValueError("Primero selecciona un archivo de audio.")
        start = parse_time(self.start_var.get())
        end = parse_time(self.end_var.get())
        if start >= end:
            raise ValueError("El tiempo final debe ser mayor que el inicial.")
        if end > self.duration + 0.05:
            raise ValueError("El tiempo final supera la duración del archivo.")
        return start, min(end, self.duration)

    def full_range(self):
        self.stop_preview(update_status=False)
        self.playhead = 0.0
        self.start_var.set("00:00.00")
        self.end_var.set(format_time(self.duration))
        self._draw_timeline()

    def _timeline_bounds(self):
        width = max(2, self.timeline.winfo_width())
        return 8.0, max(9.0, float(width - 8))

    def _time_to_x(self, seconds):
        left, right = self._timeline_bounds()
        return left + (right - left) * seconds / max(self.duration, 0.001)

    def _x_to_time(self, x):
        left, right = self._timeline_bounds()
        ratio = max(0.0, min(1.0, (float(x) - left) / (right - left)))
        return self.duration * ratio

    def _timeline_values(self):
        if self.duration <= 0:
            return None
        try:
            start = max(0.0, min(self.duration, parse_time(self.start_var.get())))
            end = max(0.0, min(self.duration, parse_time(self.end_var.get())))
        except ValueError:
            return None
        return (start, end) if start < end else None

    def _draw_timeline(self):
        if not hasattr(self, "timeline"):
            return
        c = self.timeline
        c.delete("all")
        left, right = self._timeline_bounds()
        c.create_rectangle(left, 23, right, 43, fill="#293e5a", outline="")
        values = self._timeline_values()
        if values is None:
            return
        start, end = values
        self.playhead = max(start, min(end, self.playhead))
        first, last = self._time_to_x(start), self._time_to_x(end)
        needle = self._time_to_x(self.playhead)
        c.create_rectangle(first, 23, last, 43, fill="#205d61", outline="")
        c.create_line(first, 19, first, 49, fill="#42e59b", width=3)
        c.create_rectangle(first - 5, 37, first + 5, 53, fill="#42e59b", outline="#0d182b")
        c.create_line(last, 19, last, 49, fill="#ff6673", width=3)
        c.create_rectangle(last - 5, 37, last + 5, 53, fill="#ff6673", outline="#0d182b")
        c.create_line(needle, 9, needle, 55, fill="#ffd166", width=2)
        c.create_polygon(needle - 7, 5, needle + 7, 5, needle, 17,
                         fill="#ffd166", outline="")
        self.playhead_var.set(f"▶ {format_time(self.playhead)}")
        self.detail_var.set(
            f"Duración: {format_time(self.duration)}  |  "
            f"Selección: {format_time(end - start)}"
        )

    def _timeline_press(self, event):
        values = self._timeline_values()
        if values is None:
            return
        start, end = values
        x = event.x
        # Tiradores verde y rojo en la zona inferior; aguja amarilla arriba.
        if event.y >= 19 and abs(x - self._time_to_x(start)) <= 13:
            self.drag_target = "start"
        elif event.y >= 19 and abs(x - self._time_to_x(end)) <= 13:
            self.drag_target = "end"
        else:
            self.drag_target = "head"
        self.stop_preview(update_status=False)
        self._timeline_move(event)

    def _timeline_drag(self, event):
        if self.drag_target:
            self._timeline_move(event)

    def _timeline_release(self, event):
        if self.drag_target:
            self._timeline_move(event)
        self.drag_target = None

    def _timeline_move(self, event):
        values = self._timeline_values()
        if values is None:
            return
        start, end = values
        current = self._x_to_time(event.x)
        gap = min(0.02, self.duration / 2)
        if self.drag_target == "start":
            self.start_var.set(format_time(max(0.0, min(current, end - gap))))
        elif self.drag_target == "end":
            self.end_var.set(format_time(min(self.duration, max(current, start + gap))))
        else:
            self.playhead = min(end, max(start, current))
            self._draw_timeline()

    def _timeline_hover(self, event):
        values = self._timeline_values()
        if values is None:
            return
        start, end = values
        near = event.y >= 19 and (
            abs(event.x - self._time_to_x(start)) <= 13 or
            abs(event.x - self._time_to_x(end)) <= 13
        )
        self.timeline.configure(cursor="sb_h_double_arrow" if near else "crosshair")

    def _mci_command(self, command):
        """MCI integrado en Windows, sin instalar reproductores externos."""
        import ctypes
        winmm = ctypes.WinDLL("winmm")
        send = winmm.mciSendStringW
        send.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p,
                         ctypes.c_uint, ctypes.c_void_p]
        send.restype = ctypes.c_uint
        buffer = ctypes.create_unicode_buffer(256)
        result = send(command, buffer, len(buffer), None)
        if result:
            get_error = winmm.mciGetErrorStringW
            get_error.argtypes = [ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_uint]
            get_error.restype = ctypes.c_bool
            description = ctypes.create_unicode_buffer(256)
            get_error(result, description, len(description))
            raise RuntimeError(description.value or f"Error MCI {result}")
        return buffer.value

    def _preview_with_mci(self, start, end):
        if os.name != "nt":
            raise RuntimeError("MCI solo está disponible en Windows.")
        alias = f"ptmcut{id(self):x}"
        # Los nombres de archivo de Windows no pueden contener comillas dobles.
        filename = str(self.source)
        self._mci_command(f'open "{filename}" alias {alias}')
        try:
            self._mci_command(f"set {alias} time format milliseconds")
            first = round(start * 1000)
            last = round(end * 1000)
            self._mci_command(f"play {alias} from {first} to {last}")
        except Exception:
            try:
                self._mci_command(f"close {alias}")
            except Exception:
                pass
            raise
        self.preview_alias = alias
        self.preview_backend = "mci"

    def _preview_with_pygame(self, start):
        import pygame
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
        pygame.mixer.music.load(str(self.source))
        # SDL_mixer permite posición inicial en MP3 y OGG.
        pygame.mixer.music.play(loops=0, start=float(start))
        self.preview_backend = "pygame"

    def stop_preview(self, update_status=True):
        """Detiene solo la vista previa activa y libera sus recursos."""
        if self.preview_backend and self.preview_started_at:
            self.playhead = min(
                self.duration,
                self.preview_from + max(0.0, time.monotonic() - self.preview_started_at),
            )
            self._draw_timeline()
        self.preview_started_at = 0.0
        self.preview_generation += 1
        self.preview_cancel.set()
        if self.preview_alias:
            try:
                self._mci_command(f"stop {self.preview_alias}")
            except Exception:
                pass
            try:
                self._mci_command(f"close {self.preview_alias}")
            except Exception:
                pass
            self.preview_alias = None
        if self.preview_backend == "pygame":
            try:
                import pygame
                if pygame.mixer.get_init():
                    pygame.mixer.music.stop()
                    pygame.mixer.music.unload()
            except Exception:
                pass
        self.preview_backend = None
        process = self.preview_process
        self.preview_process = None
        if process is not None and process.poll() is None:
            try:
                process.terminate()
            except OSError:
                pass
        if self.preview_temp is not None:
            try:
                self.preview_temp.unlink(missing_ok=True)
            except OSError:
                pass
            self.preview_temp = None
        if hasattr(self, "preview_btn"):
            self.preview_btn.configure(state="normal")
        if update_status:
            self.status_var.set("Vista previa detenida.")

    def _monitor_preview(self, generation):
        if generation != self.preview_generation:
            return
        now = time.monotonic()
        elapsed = max(0.0, now - self.preview_started_at)
        self.playhead = min(self.duration, self.preview_from + elapsed)
        self._draw_timeline()
        finished = now >= self.preview_deadline
        if not finished and now - self.preview_started_at >= 0.5:
            try:
                if self.preview_backend == "pygame":
                    import pygame
                    finished = not pygame.mixer.music.get_busy()
                elif self.preview_backend == "mci" and self.preview_alias:
                    state = self._mci_command(f"status {self.preview_alias} mode")
                    finished = state.strip().lower() != "playing"
            except Exception:
                finished = True
        if finished:
            self.stop_preview(update_status=False)
            self.status_var.set("Vista previa finalizada.")
        else:
            self.after(150, lambda: self._monitor_preview(generation))

    def preview(self):
        """Inicia la reproducción en el instante seleccionado sin transcodificar minutos."""
        if self.worker_running:
            return
        try:
            start, end = self._selection()
        except ValueError as exc:
            messagebox.showwarning("Intervalo", str(exc), parent=self)
            return
        position = min(end, max(start, self.playhead))
        if position >= end - 0.01:
            messagebox.showwarning(
                "Aguja de reproducción",
                "Mueve la aguja amarilla antes del final del fragmento.", parent=self,
            )
            return
        self.stop_preview(update_status=False)
        self.playhead = position
        self._draw_timeline()
        self.preview_cancel.clear()
        errors = []
        try:
            self._preview_with_pygame(position)
        except Exception as exc:
            errors.append(f"Pygame: {exc}")
            try:
                self._preview_with_mci(position, end)
            except Exception as mci_exc:
                errors.append(f"Windows MCI: {mci_exc}")
                self.stop_preview(update_status=False)
                self.status_var.set("Vista previa no disponible.")
                messagebox.showerror(
                    "Vista previa",
                    "No se pudo reproducir el fragmento.\n\n" + "\n".join(errors),
                    parent=self,
                )
                return

        self.preview_from = position
        self.preview_started_at = time.monotonic()
        self.preview_deadline = self.preview_started_at + (end - position)
        current_generation = self.preview_generation
        self.status_var.set(
            f"Reproduciendo {format_time(position)} - {format_time(end)} "
            f"({self.preview_backend.upper()})."
        )
        self.after(150, lambda: self._monitor_preview(current_generation))

    def export(self):
        if self.worker_running:
            return
        try:
            start, end = self._selection()
        except ValueError as exc:
            messagebox.showwarning("Intervalo", str(exc), parent=self)
            return
        extension = self.format_var.get().lower()
        suggested = f"{self.source.stem}_corte_{int(start)}_{int(end)}.{extension}"
        filename = filedialog.asksaveasfilename(parent=self, title="Guardar recorte",
                    initialdir=str(self.source.parent), initialfile=suggested,
                    defaultextension="." + extension,
                    filetypes=[(extension.upper(), "*." + extension)])
        if not filename:
            return
        destination = Path(filename)
        if destination.resolve() == self.source.resolve():
            messagebox.showwarning("Archivo original", "Elige otro nombre para no sobrescribir el original.", parent=self)
            return
        ffmpeg = get_ffmpeg()
        if not ffmpeg and not (self.source.suffix.lower() == ".wav" and extension == "wav"):
            messagebox.showerror("FFmpeg requerido",
                "No se encontró el motor FFmpeg. Vuelve a abrir Audio Cutter para preparar sus dependencias.", parent=self)
            return
        self.cancel.clear()
        self._busy(True)
        self.status_var.set("Exportando fragmento...")
        self.stop_preview()
        # stop_preview actualiza estado: restaurar estado de exportación.
        self.status_var.set("Exportando fragmento...")

        def work():
            try:
                if not ffmpeg:
                    trim_pcm_wav(self.source, destination, start, end, self.cancel)
                else:
                    temporary = destination.with_name(destination.stem + ".ptm-part" + destination.suffix)
                    codecs = {"mp3": ["-c:a", "libmp3lame", "-q:a", "2"],
                              "wav": ["-c:a", "pcm_s16le"],
                              "flac": ["-c:a", "flac"],
                              "m4a": ["-c:a", "aac", "-b:a", "192k"],
                              "ogg": ["-c:a", "libvorbis", "-q:a", "5"]}
                    command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin",
                               "-y", "-ss", str(start), "-i", str(self.source),
                               "-t", str(end - start), "-vn", *codecs[extension], str(temporary)]
                    try:
                        result = subprocess.run(command, capture_output=True, text=True,
                                                timeout=max(120, (end - start) * 5),
                                                **hidden_kwargs())
                        if result.returncode != 0:
                            raise RuntimeError(result.stderr.strip()[-1000:] or "FFmpeg falló.")
                        if self.cancel.is_set():
                            raise RuntimeError("Operación cancelada.")
                        if not temporary.exists() or temporary.stat().st_size == 0:
                            raise RuntimeError("FFmpeg no generó audio.")
                        temporary.replace(destination)
                    finally:
                        temporary.unlink(missing_ok=True)
                self._ui(lambda: (self._busy(False),
                                  self.status_var.set(f"Guardado: {destination}"),
                                  messagebox.showinfo("Audio Cutter", f"Recorte guardado:\n{destination}", parent=self)))
            except Exception as exc:
                self._ui(lambda error=str(exc): (self._busy(False), self.status_var.set(error),
                            messagebox.showerror("Audio Cutter", error, parent=self)))
        threading.Thread(target=work, daemon=True).start()

    def _on_destroy(self, event):
        if event.widget is self:
            self.on_close()

    def on_close(self):
        self.cancel.set()
        self.stop_preview()


App = AudioCutter


def main():
    root = tk.Tk()
    root.title(TOOL_NAME)
    root.geometry("920x590")
    panel = App(root)
    panel.pack(fill="both", expand=True)
    root.protocol("WM_DELETE_WINDOW", lambda: (panel.on_close(), root.destroy()))
    root.mainloop()


if __name__ == "__main__":
    main()
