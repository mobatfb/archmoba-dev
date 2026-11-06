# ARGUMENTOS: audio cutter recortar cortar audio mp3 wav m4a flac ogg fragmento inicio fin vista previa exportar
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Audio Cutter para PTM. Interfaz integrada; FFmpeg para formatos comprimidos."""
import os
import re
import shutil
import subprocess
import threading
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
    """Mutagen lee los metadatos sin requerir ffprobe ni un FFmpeg instalado."""
    try:
        from mutagen import File as AudioFile
        audio = AudioFile(str(path))
        if audio is not None and audio.info is not None:
            value = float(audio.info.length)
            if 0 < value < float("inf"):
                return value
    except (ImportError, ValueError, OSError, AttributeError):
        pass
    if path.suffix.lower() == ".wav":
        try:
            with wave.open(str(path), "rb") as source:
                return source.getnframes() / source.getframerate()
        except (wave.Error, EOFError, OSError):
            pass
    probe = shutil.which("ffprobe")
    if probe:
        command = [probe, "-v", "error", "-show_entries", "format=duration",
                   "-of", "default=noprint_wrappers=1:nokey=1", str(path)]
        result = subprocess.run(command, capture_output=True, text=True,
                                timeout=35, **hidden_kwargs())
        if result.returncode == 0:
            try:
                value = float(result.stdout.strip())
                if 0 < value < float("inf"):
                    return value
            except ValueError:
                pass
    raise RuntimeError("No se pudo obtener la duración del audio. Comprueba que el archivo sea válido.")


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
        self.timeline = tk.Canvas(settings, height=46, bg="#0d182b",
                                  highlightthickness=0, cursor="crosshair")
        self.timeline.pack(fill="x", pady=(9, 3))
        self.timeline.bind("<Button-1>", self._timeline_click)
        self.timeline.bind("<Configure>", lambda _event: self._draw_timeline())
        self.start_var.trace_add("write", lambda *_: self._draw_timeline())
        self.end_var.trace_add("write", lambda *_: self._draw_timeline())
        self._label(settings, "Clic izquierdo: fija inicio. Mayús + clic: fija fin.", fg=MUTED, size=9).pack(anchor="w")
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
        self.start_var.set("00:00.00")
        self.end_var.set(format_time(self.duration))
        self._draw_timeline()

    def _draw_timeline(self):
        if not hasattr(self, "timeline"):
            return
        c = self.timeline
        c.delete("all")
        width = max(2, c.winfo_width())
        c.create_rectangle(5, 13, width - 5, 33, fill="#293e5a", outline="")
        if not self.duration:
            return
        try:
            start = max(0, min(self.duration, parse_time(self.start_var.get())))
            end = max(0, min(self.duration, parse_time(self.end_var.get())))
        except ValueError:
            return
        left = 5 + (width - 10) * start / self.duration
        right = 5 + (width - 10) * end / self.duration
        c.create_rectangle(left, 13, right, 33, fill=ACCENT, outline="")
        for x in (left, right):
            c.create_line(x, 7, x, 39, fill="#ffffff", width=2)

    def _timeline_click(self, event):
        if self.duration <= 0:
            return
        ratio = max(0, min(1, (event.x - 5) / max(1, self.timeline.winfo_width() - 10)))
        current = format_time(self.duration * ratio)
        if event.state & 0x0001:
            self.end_var.set(current)
        else:
            self.start_var.set(current)

    def stop_preview(self):
        process = self.preview_process
        self.preview_process = None
        if process and process.poll() is None:
            process.terminate()
        self.status_var.set("Vista previa detenida.")

    def preview(self):
        try:
            start, end = self._selection()
        except ValueError as exc:
            messagebox.showwarning("Intervalo", str(exc), parent=self)
            return
        player = shutil.which("ffplay")
        if not player:
            messagebox.showinfo("Vista previa", "Para reproducir instala FFmpeg con ffplay.", parent=self)
            return
        self.stop_preview()
        try:
            command = [player, "-autoexit", "-nodisp", "-loglevel", "error",
                       "-ss", str(start), "-t", str(end - start), str(self.source)]
            self.preview_process = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                                                    stdout=subprocess.DEVNULL,
                                                    stderr=subprocess.DEVNULL, **hidden_kwargs())
            self.status_var.set(f"Reproduciendo {format_time(start)} - {format_time(end)}")
        except OSError as exc:
            messagebox.showerror("Vista previa", str(exc), parent=self)

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
