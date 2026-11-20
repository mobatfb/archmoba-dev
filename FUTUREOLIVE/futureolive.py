#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FUTUREO LIVE - Boceto funcional de escena para streaming.
Pantalla/monitor en el centro + foto real o avatar a la derecha.

Instalacion minima:
    python -m pip install pillow
Captura mas rapida y seleccion de monitor (recomendado):
    python -m pip install mss
Ejecucion:
    python FUTUREO_LIVE.py

IMPORTANTE: Este programa muestra una PREVISUALIZACION, no transmite ni graba.
Para publicar en YouTube, captura la ventana de FUTUREO LIVE en OBS Studio.
Si ves un efecto de pantallas infinitas, captura un monitor distinto del que
contiene esta aplicacion (lo mas conveniente son dos pantallas), o monta la
escena con captura de juego + imagen en OBS.
"""

from __future__ import annotations

import json
import os
import queue
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

try:
    from PIL import Image, ImageGrab, ImageOps, ImageTk
except ImportError as exc:
    raise SystemExit("Falta Pillow. Instala con: python -m pip install pillow mss") from exc

try:
    import mss
except ImportError:
    mss = None  # Pillow ImageGrab funciona como alternativa sin mss.


VERSION = "1.0.0"
BASE = Path(__file__).resolve().parent
CONFIG_FILE = BASE / "futureo_config.json"
DEFAULT_FOTO = BASE / "futureo_foto.jpg"
DEFAULT_AVATAR = BASE / "avatar_futureo.png"

COL = {
    "bg": "#08111E",
    "panel": "#0D1A2B",
    "panel_alt": "#101F33",
    "canvas": "#06101B",
    "line": "#1C3853",
    "cyan": "#45DFFF",
    "cyan_dark": "#126D9A",
    "white": "#F5FAFF",
    "muted": "#A9C2D8",
    "yellow": "#FFC85C",
    "green": "#67E8A4",
    "danger": "#FF737E",
}


def load_settings() -> dict:
    try:
        if CONFIG_FILE.is_file():
            value = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                return value
    except (OSError, ValueError):
        pass
    return {}


def save_settings(settings: dict) -> None:
    try:
        CONFIG_FILE.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        # En carpetas solo lectura la app sigue funcionando sin persistir opciones.
        pass


def crop_photo(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    return ImageOps.fit(image, size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.45))


class LiveCapture:
    """Captura del monitor en un hilo, sin tocar widgets Tk."""

    def __init__(self, frames: queue.Queue) -> None:
        self.frames = frames
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.monitor_index = 1
        self.fps = 12
        self.error: str | None = None
        self.latest_fps = 0.0

    def start(self) -> None:
        if self.thread is not None and self.thread.is_alive():
            self.pause_event.clear()
            return
        self.stop_event.clear()
        self.pause_event.clear()
        self.error = None
        self.thread = threading.Thread(target=self._run, name="futureo-capture", daemon=True)
        self.thread.start()

    def pause(self) -> None:
        self.pause_event.set()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.3)

    def _run(self) -> None:
        try:
            if mss is not None:
                with mss.mss() as grabber:
                    self._capture_loop(grabber)
            else:
                self._capture_loop(None)
        except Exception as exc:
            self.error = f"No fue posible capturar la pantalla: {exc}"

    def _capture_loop(self, grabber) -> None:
        frame_counter = 0
        measured_at = time.monotonic()
        while not self.stop_event.is_set():
            if self.pause_event.is_set():
                time.sleep(0.075)
                continue
            started = time.monotonic()
            if grabber is not None:
                available = len(grabber.monitors) - 1
                if available < 1:
                    self.error = "No se encontraron pantallas para capturar."
                    return
                selected = min(max(1, self.monitor_index), available)
                raw = grabber.grab(grabber.monitors[selected])
                image = Image.frombytes("RGB", raw.size, raw.rgb)
            else:
                # Alternativa nativa de Pillow cuando mss no esta instalado.
                image = ImageGrab.grab(all_screens=(sys.platform == "win32")).convert("RGB")
            image.thumbnail((1560, 880), Image.Resampling.LANCZOS)
            while True:
                try:
                    self.frames.get_nowait()
                except queue.Empty:
                    break
            try:
                self.frames.put_nowait(image)
            except queue.Full:
                pass
            frame_counter += 1
            if started - measured_at >= 1.0:
                self.latest_fps = frame_counter / max(0.001, started - measured_at)
                frame_counter = 0
                measured_at = started
            elapsed = time.monotonic() - started
            time.sleep(max(0.008, 1 / self.fps - elapsed))


class FutureoLive:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.configure(bg=COL["bg"])

        try:
            self.root.iconbitmap(BASE / "futureo.ico")
        except Exception:
            pass

        self.settings = load_settings()
        self.photo_path = Path(self.settings.get("foto", str(DEFAULT_FOTO)))
        if not self.photo_path.is_file():
            self.photo_path = DEFAULT_FOTO if DEFAULT_FOTO.is_file() else DEFAULT_AVATAR
        self.photo_source: Image.Image | None = None
        self.photo_ref = None
        self.screen_ref = None
        self.last_frame: Image.Image | None = None
        self.running = False
        self.scene_mode = False
        self.last_error: str | None = None

        self.monitor_choices: dict[str, int] = {}
        self.frame_queue: queue.Queue = queue.Queue(maxsize=1)
        self.capture = LiveCapture(self.frame_queue)
        self.monitor_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Preparando vista previa ...")
        self.challenge_var = tk.StringVar(value=self.settings.get("reto", "¡El futuro se juega entre amigos!"))
        self.build_ui()
        self.read_photo()
        self.list_monitors()
        self.root.after(250, self.start_capture)
        self.root.after(50, self.poll_frames)
        self.root.winfo_toplevel().bind("<F11>", lambda _event: self.toggle_scene())
        self.root.winfo_toplevel().bind("<Escape>", lambda _event: self.exit_scene())

    def style_button(self, parent, text, command, primary=False) -> tk.Button:
        bg = COL["cyan"] if primary else COL["panel_alt"]
        fg = COL["bg"] if primary else COL["white"]
        button = tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground="#8CEFFF" if primary else COL["line"],
            activeforeground=COL["bg"] if primary else COL["white"],
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            bd=0,
            padx=16,
            pady=10,
            cursor="hand2",
        )
        return button

    def build_ui(self) -> None:
        self.header = tk.Frame(self.root, bg=COL["bg"], height=86)
        self.header.pack(side="top", fill="x")
        self.header.pack_propagate(False)

        brand = tk.Frame(self.header, bg=COL["bg"])
        brand.pack(side="left", padx=(26, 12), pady=13)
        tk.Label(
            brand, text="F", fg=COL["cyan"], bg=COL["bg"],
            font=("Segoe UI", 34, "bold"),
        ).pack(side="left", padx=(0, 12))
        name_group = tk.Frame(brand, bg=COL["bg"])
        name_group.pack(side="left", pady=4)
        tk.Label(
            name_group, text="FUTUREO", fg=COL["white"], bg=COL["bg"],
            font=("Segoe UI", 21, "bold"),
        ).pack(anchor="w")
        tk.Label(
            name_group, text="EL FUTURO SE JUEGA ENTRE AMIGOS", fg=COL["cyan"],
            bg=COL["bg"], font=("Segoe UI", 8, "bold"),
        ).pack(anchor="w")

        tk.Label(
            self.header, text="●  PREVISUALIZACIÓN DE STREAM", fg=COL["green"],
            bg=COL["bg"], font=("Segoe UI", 10, "bold"),
        ).pack(side="right", padx=28)

        thin_line = tk.Frame(self.root, height=2, bg=COL["line"])
        thin_line.pack(side="top", fill="x")

        self.footer = tk.Frame(self.root, bg=COL["panel"], height=75)
        self.footer.pack(side="bottom", fill="x")
        self.footer.pack_propagate(False)

        self.status_label = tk.Label(
            self.footer, textvariable=self.status_var, bg=COL["panel"],
            fg=COL["muted"], font=("Segoe UI", 9), anchor="w",
        )
        self.status_label.pack(side="bottom", fill="x", padx=23, pady=(0, 7))
        footer_controls = tk.Frame(self.footer, bg=COL["panel"])
        footer_controls.pack(side="top", fill="x", padx=18, pady=(10, 2))
        self.play_button = self.style_button(footer_controls, "⏸  Pausar", self.toggle_capture)
        self.play_button.pack(side="left", padx=(0, 8))
        self.style_button(footer_controls, "📷  Cambiar foto", self.choose_photo).pack(side="left", padx=(0, 8))
        self.style_button(footer_controls, "🖼  Avatar gamer", self.use_avatar).pack(side="left", padx=(0, 8))
        self.style_button(footer_controls, "⛶  Modo escena (F11)", self.toggle_scene).pack(side="right", padx=(8, 0))

        chooser = tk.Frame(footer_controls, bg=COL["panel"])
        chooser.pack(side="right", padx=12)
        tk.Label(
            chooser, text="CAPTURAR:", fg=COL["muted"], bg=COL["panel"],
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left", padx=(0, 10))
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "Futureo.TCombobox", fieldbackground=COL["panel_alt"],
            foreground=COL["white"], background=COL["panel_alt"],
            bordercolor=COL["line"], arrowcolor=COL["cyan"],
        )
        self.monitor_combo = ttk.Combobox(
            chooser, textvariable=self.monitor_var, width=20,
            state="readonly", style="Futureo.TCombobox",
        )
        self.monitor_combo.pack(side="left")
        self.monitor_combo.bind("<<ComboboxSelected>>", self.monitor_selected)

        self.body = tk.Frame(self.root, bg=COL["bg"])
        self.body.pack(fill="both", expand=True, padx=18, pady=15)
        self.body.grid_columnconfigure(0, weight=1)
        self.body.grid_columnconfigure(1, weight=0, minsize=305)
        self.body.grid_rowconfigure(0, weight=1)

        main = tk.Frame(self.body, bg=COL["panel"], highlightbackground=COL["line"], highlightthickness=1)
        main.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        tk.Label(
            main, text="◉  PANTALLA / GAMEPLAY", fg=COL["white"], bg=COL["panel"],
            font=("Segoe UI", 11, "bold"), anchor="w", pady=12, padx=16,
        ).pack(fill="x")
        self.screen_canvas = tk.Canvas(main, bg=COL["canvas"], bd=0, highlightthickness=0)
        self.screen_canvas.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.screen_canvas.bind("<Configure>", lambda _event: self.draw_screen())

        side = tk.Frame(self.body, width=310, bg=COL["panel"], highlightbackground=COL["line"], highlightthickness=1)
        side.grid(row=0, column=1, sticky="nsew")
        side.grid_propagate(False)
        tk.Label(
            side, text="★  TU ESPACIO", fg=COL["cyan"], bg=COL["panel"],
            font=("Segoe UI", 11, "bold"), pady=14,
        ).pack()
        self.photo_canvas = tk.Canvas(side, height=365, bg=COL["panel"], bd=0, highlightthickness=0)
        self.photo_canvas.pack(fill="x", padx=16)
        self.photo_canvas.bind("<Configure>", lambda _event: self.draw_photo())
        tk.Label(
            side, text="FUTUREO", bg=COL["panel"], fg=COL["white"],
            font=("Segoe UI", 28, "bold"), pady=7,
        ).pack()
        tk.Label(
            side, text="🎮  GAMING  •  DIRECTOS  •  AMIGOS", bg=COL["panel"],
            fg=COL["cyan"], font=("Segoe UI", 9, "bold"),
        ).pack()
        line = tk.Frame(side, bg=COL["line"], height=1)
        line.pack(fill="x", padx=21, pady=16)
        tk.Label(
            side, text="RETO DE LA COMUNIDAD", fg=COL["yellow"], bg=COL["panel"],
            font=("Segoe UI", 10, "bold"),
        ).pack(padx=17, anchor="w")
        self.challenge_text = tk.Label(
            side, textvariable=self.challenge_var, fg=COL["white"], bg=COL["panel"],
            font=("Segoe UI", 11), justify="left", wraplength=267,
        )
        self.challenge_text.pack(padx=18, pady=(5, 11), anchor="w")
        self.style_button(side, "✎  Editar reto", self.edit_challenge).pack(anchor="w", padx=18)
        tk.Label(
            side, text="Diseñado para mostrar tu pantalla y tu foto.\nNo inicia emisiones ni transmite audio.",
            fg=COL["muted"], bg=COL["panel"], font=("Segoe UI", 8),
            justify="center", pady=10,
        ).pack(side="bottom", fill="x", padx=10)

    def list_monitors(self) -> None:
        try:
            if mss is not None:
                with mss.mss() as screen:
                    monitors = screen.monitors[1:]
                self.monitor_choices = {
                    f"Pantalla {i + 1}  ({m['width']}×{m['height']})": i + 1
                    for i, m in enumerate(monitors)
                }
            else:
                self.monitor_choices = {"Escritorio completo (Pillow)": 1}
            self.monitor_combo["values"] = list(self.monitor_choices)
            selected = int(self.settings.get("monitor", 1))
            selected = min(max(1, selected), max(1, len(self.monitor_choices)))
            for name, idx in self.monitor_choices.items():
                if idx == selected:
                    self.monitor_var.set(name)
                    break
            self.capture.monitor_index = selected
        except Exception as exc:
            self.status_var.set(f"No pude detectar pantallas: {exc}")

    def monitor_selected(self, _event=None) -> None:
        selected = self.monitor_choices.get(self.monitor_var.get(), 1)
        self.capture.monitor_index = selected
        self.settings["monitor"] = selected
        save_settings(self.settings)
        self.status_var.set(f"Ahora se captura la pantalla {selected}.")

    def read_photo(self) -> None:
        try:
            with Image.open(self.photo_path) as photo:
                self.photo_source = ImageOps.exif_transpose(photo).convert("RGB")
            self.status_var.set(f"Foto cargada: {self.photo_path.name}")
        except Exception:
            self.photo_source = None
            self.status_var.set("No hay foto; pulsa Cambiar foto para agregar una.")
        self.draw_photo()

    def choose_photo(self) -> None:
        filename = filedialog.askopenfilename(
            title="Selecciona una foto para FUTUREO",
            filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.webp *.bmp"), ("Todos los archivos", "*.*")],
        )
        if not filename:
            return
        self.photo_path = Path(filename)
        self.settings["foto"] = str(self.photo_path)
        save_settings(self.settings)
        self.read_photo()

    def use_avatar(self) -> None:
        if not DEFAULT_AVATAR.is_file():
            messagebox.showinfo("Avatar", "No se encontró avatar_futureo.png al lado del programa.")
            return
        self.photo_path = DEFAULT_AVATAR
        self.settings["foto"] = str(self.photo_path)
        save_settings(self.settings)
        self.read_photo()

    def draw_photo(self) -> None:
        canvas = self.photo_canvas
        width = max(30, canvas.winfo_width())
        height = max(30, canvas.winfo_height())
        canvas.delete("all")
        if self.photo_source is None:
            canvas.create_rectangle(5, 5, width - 5, height - 5, outline=COL["cyan_dark"], width=2)
            canvas.create_text(
                width / 2, height / 2, text="TU FOTO\nVA AQUÍ",
                fill=COL["cyan"], justify="center", font=("Segoe UI", 17, "bold"),
            )
            return
        image_width, image_height = max(24, width - 22), max(24, height - 14)
        rendered = crop_photo(self.photo_source, (image_width, image_height))
        self.photo_ref = ImageTk.PhotoImage(rendered)
        canvas.create_rectangle(
            3, 3, width - 3, height - 3, outline=COL["cyan_dark"], width=4,
        )
        canvas.create_image(width // 2, height // 2, image=self.photo_ref, anchor="center")
        canvas.create_rectangle(
            9, 7, width - 9, height - 7, outline=COL["cyan"], width=2,
        )

    def draw_screen(self) -> None:
        canvas = self.screen_canvas
        width = max(50, canvas.winfo_width())
        height = max(50, canvas.winfo_height())
        canvas.delete("all")
        if self.last_frame is None:
            canvas.create_text(
                width / 2, height / 2 - 18,
                text="FUTUREO LIVE", fill=COL["white"],
                font=("Segoe UI", 30, "bold"),
            )
            canvas.create_text(
                width / 2, height / 2 + 30,
                text="Aquí aparecerá tu pantalla en vivo",
                fill=COL["muted"], font=("Segoe UI", 14),
            )
        else:
            rendered = ImageOps.contain(
                self.last_frame, (max(1, width - 16), max(1, height - 16)),
                method=Image.Resampling.LANCZOS,
            )
            self.screen_ref = ImageTk.PhotoImage(rendered)
            canvas.create_image(width / 2, height / 2, image=self.screen_ref, anchor="center")
        # HUD de preview para que el resultado parezca una escena real.
        canvas.create_rectangle(13, 13, 213, 50, fill=COL["bg"], outline=COL["cyan_dark"], width=1)
        canvas.create_text(
            28, 31, text="●  CAPTURA EN VIVO", fill=COL["green"],
            anchor="w", font=("Segoe UI", 10, "bold"),
        )
        canvas.create_rectangle(13, height - 57, 235, height - 14, fill=COL["bg"], outline=COL["cyan_dark"])
        canvas.create_text(
            25, height - 36, text="FUTUREO   |   @SoyFutureo",
            fill=COL["cyan"], anchor="w", font=("Segoe UI", 10, "bold"),
        )

    def start_capture(self) -> None:
        self.capture.start()
        self.running = True
        self.play_button.configure(text="⏸  Pausar")
        self.status_var.set(
            "Vista previa activa. Si ves efecto espejo, captura otro monitor o usa OBS con captura de juego."
        )

    def toggle_capture(self) -> None:
        if self.running:
            self.capture.pause()
            self.running = False
            self.play_button.configure(text="▶  Reanudar")
            self.status_var.set("Vista previa pausada.")
        else:
            self.start_capture()

    def poll_frames(self) -> None:
        try:
            image = self.frame_queue.get_nowait()
        except queue.Empty:
            image = None
        if image is not None:
            self.last_frame = image
            self.draw_screen()
        if self.capture.error and self.capture.error != self.last_error:
            self.last_error = self.capture.error
            self.status_var.set(self.capture.error)
            messagebox.showwarning("Captura de pantalla", self.capture.error)
        if self.root.winfo_exists():
            self.root.after(50, self.poll_frames)

    def edit_challenge(self) -> None:
        editor = tk.Toplevel(self.root)
        editor.title("Reto de la comunidad")
        editor.configure(bg=COL["panel"])
        editor.geometry("440x230")
        editor.transient(self.root)
        editor.grab_set()
        tk.Label(
            editor, text="¿Qué reto mostrarás en el directo?", fg=COL["white"],
            bg=COL["panel"], font=("Segoe UI", 13, "bold"),
        ).pack(padx=20, pady=(20, 15))
        text_box = tk.Text(
            editor, height=3, wrap="word", fg=COL["white"],
            bg=COL["panel_alt"], relief="flat", font=("Segoe UI", 11),
            insertbackground=COL["white"],
        )
        text_box.pack(fill="both", expand=True, padx=20)
        text_box.insert("1.0", self.challenge_var.get())

        def commit() -> None:
            value = text_box.get("1.0", "end").strip()
            if value:
                self.challenge_var.set(value[:160])
                self.settings["reto"] = value[:160]
                save_settings(self.settings)
            editor.destroy()

        self.style_button(editor, "Guardar reto", commit, primary=True).pack(pady=14)
        editor.bind("<Control-Return>", lambda _event: commit())

    def toggle_scene(self) -> None:
        self.scene_mode = not self.scene_mode
        if self.scene_mode:
            self.header.pack_forget()
            self.footer.pack_forget()
            self.root.winfo_toplevel().attributes("-fullscreen", True)
        else:
            self.exit_scene()

    def exit_scene(self) -> None:
        if not self.scene_mode:
            return
        self.scene_mode = False
        self.root.winfo_toplevel().attributes("-fullscreen", False)
        # Como la zona central se empacó después del pie,
        # before permite restaurar la jerarquía de la disposición.
        self.header.pack(side="top", fill="x", before=self.body)
        self.footer.pack(side="bottom", fill="x", before=self.body)
        self.root.after(100, self.draw_screen)

    def quit(self) -> None:
        self.settings["foto"] = str(self.photo_path)
        save_settings(self.settings)
        self.capture.stop()
        self.root.destroy()


def render(parent):
    """Interfaz embebida para app.py, con limpieza al actualizar."""
    frame = tk.Frame(parent, bg=COL["bg"])
    controller = FutureoLive(frame)
    frame.futureo_controller = controller

    def cleanup(event):
        if event.widget is frame:
            controller.capture.stop()

    frame.bind("<Destroy>", cleanup, add="+")
    return frame


def main() -> None:
    root = tk.Tk()
    root.title("FUTUREO LIVE")
    root.geometry("1440x860")
    root.minsize(1030, 690)
    widget = render(root)
    widget.pack(fill="both", expand=True)
    root.mainloop()


if __name__ == "__main__":
    main()