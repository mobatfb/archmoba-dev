# -*- coding: utf-8 -*-
"""KOFMULTI | Diagnostico KO, final de equipo y tiempo para MAME 0.289.

Lanza kf2k2mp2 con KOF_Diagnostico_Combate.lua y registra los instantes
exactos (fotogramas emulados) en que cambian vida, KO=254, tiempo y rondas.
Los botones de la interfaz permiten etiquetar un KO o final de equipo.
SOLO LECTURA: NO modifica MAME y NO concede victorias/puntos.

Windows, Python 3.10+, tkinter. Sin librerias externas.
  py -B KOF_Diagnostico_Combate.py
  py -B KOF_Diagnostico_Combate.py --selftest
"""
from __future__ import annotations

import csv
import dataclasses
import datetime as dt
import os
import pathlib
import re
import subprocess
import sys
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Optional

VERSION = "1.1"
HERE = pathlib.Path(__file__).resolve().parent
LUA_FILE = HERE / "KOF_Diagnostico_Combate.lua"
SESSION_DIR = HERE / "KOF_DIAG_SESIONES"
HP_SENTINEL = 254
TIMER_ADDRESS = 0x10A7D2

MARKS = (
    ("Inicio de combate", "INICIO_COMBATE"),
    ("KO P1 confirmado", "KO_P1_CONFIRMADO"),
    ("KO P2 confirmado", "KO_P2_CONFIRMADO"),
    ("Entró otro P1", "CAMBIO_PERSONAJE_P1"),
    ("Entró otro P2", "CAMBIO_PERSONAJE_P2"),
    ("Equipo P1 eliminado", "FIN_EQUIPO_P1"),
    ("Equipo P2 eliminado", "FIN_EQUIPO_P2"),
    ("Se agotó el tiempo", "TIEMPO_AGOTADO_CONFIRMADO"),
    ("Fin de combate", "FIN_COMBATE"),
    ("Observación", "OBSERVACION"),
)


def byte_label(value: int) -> str:
    if value == HP_SENTINEL:
        return "254 (KO observado)"
    if value == 255:
        return "255 (KO posible)"
    if 0 <= value <= 102:
        return f"{value} / 102"
    return f"{value} (estado especial)"


def timer_label(value: int) -> str:
    """En esta captura, 0x60, 0x59 ... 0x00 concuerda con BCD 60..0."""
    hi, lo = value >> 4, value & 0xF
    if hi <= 9 and lo <= 9:
        return f"{hi * 10 + lo:02d} (BCD observado, 0x{value:02X})"
    return f"0x{value:02X} ({value} decimal)"


@dataclasses.dataclass(frozen=True)
class Reading:
    frame: int
    hp1: int
    hp2: int
    lost1: int
    lost2: int
    timer: int
    timer_aux: int
    ko1: int
    ko2: int


@dataclasses.dataclass(frozen=True)
class GameEvent:
    reading: Reading
    kind: str
    contexts: tuple[str, ...]  # Cinco volcados de 32 bytes cada uno.


def parse_numbers(parts: list[str]) -> Optional[Reading]:
    if len(parts) != 9:
        return None
    try:
        values = tuple(int(p, 10) for p in parts)
    except ValueError:
        return None
    frame, hp1, hp2, lost1, lost2, timer, aux, ko1, ko2 = values
    if not (0 <= frame <= 10**12 and 0 <= ko1 <= 10**9 and 0 <= ko2 <= 10**9):
        return None
    if any(not 0 <= v <= 255 for v in (hp1, hp2, lost1, lost2, timer, aux)):
        return None
    return Reading(*values)


def parse_state(line: str) -> Optional[tuple[int, Reading]]:
    parts = line.rstrip("\r\n").split("\t")
    if len(parts) != 11 or parts[0] != "KOF_DIAG_STATE1":
        return None
    try:
        seq = int(parts[1], 10)
    except ValueError:
        return None
    reading = parse_numbers(parts[2:11])
    if not 1 <= seq <= 10**12 or reading is None:
        return None
    return seq, reading


def parse_event(line: str) -> Optional[GameEvent]:
    parts = line.rstrip("\r\n").split("\t")
    if len(parts) != 16 or parts[0] != "KOF_DIAG_EVT1":
        return None
    reading = parse_numbers(parts[1:10])
    kind = parts[10]
    contexts = tuple(parts[11:16])
    if reading is None or re.fullmatch(r"[A-Z0-9_ÁÉÍÓÚÑ]+", kind) is None:
        return None
    if any(re.fullmatch(r"[0-9A-F?]{64}", item) is None for item in contexts):
        return None
    return GameEvent(reading, kind, contexts)


class DiagnosticsApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"KOFMULTI | Diagnóstico KO y tiempo v{VERSION}")
        self.root.geometry("1130x750")
        self.root.minsize(870, 620)

        st = ttk.Style()
        st.theme_use("clam")
        st.configure("TFrame", background="#111e30")
        st.configure("TLabel", background="#111e30", foreground="#e8f0ff",
                     font=("Segoe UI", 10))
        st.configure("TButton", font=("Segoe UI", 9), padding=5)
        st.configure("Header.TLabel", background="#111e30", foreground="#ffffff",
                     font=("Segoe UI", 13, "bold"))
        st.configure("Status.TLabel", background="#111e30", foreground="#8de5c5",
                     font=("Segoe UI", 10, "bold"))
        st.configure("Treeview", background="#182a40", foreground="#eff7ff",
                     fieldbackground="#182a40", rowheight=24)
        st.configure("Treeview.Heading", background="#285174",
                     foreground="#ffffff")
        self.root.configure(bg="#111e30")

        self.exe = tk.StringVar(value="")
        self.rom_folder = tk.StringVar(value="")
        self.rom_name = tk.StringVar(value="kf2k2mp2")
        self.status = tk.StringVar(value="Sin iniciar. Abre MAME 0.289 desde este programa.")
        self.p1_text = tk.StringVar(value="P1: --")
        self.p2_text = tk.StringVar(value="P2: --")
        self.timer_text = tk.StringVar(value="TIEMPO DEL JUEGO: --")
        self.counters_text = tk.StringVar(value="Contadores P1/P2: -- / --")
        self.team_status = tk.StringVar(
            value="EQUIPOS: pendiente | observar cambios de contador 0 a 3")
        self.frame_text = tk.StringVar(value="Fotograma emulado: --")
        self.watch_text = tk.StringVar(value="Cronómetro local: 00:00.0")

        self.proc: Optional[subprocess.Popen] = None
        self.session: Optional[pathlib.Path] = None
        self.state_path: Optional[pathlib.Path] = None
        self.events_path: Optional[pathlib.Path] = None
        self.clips_path: Optional[pathlib.Path] = None
        self.commands_path: Optional[pathlib.Path] = None
        self.seq = 0
        self.last_frame = -1
        self.last_read_at = 0.0
        self.event_offset = 0
        self.pending_event_bytes = b""
        self.event_rows: list[GameEvent] = []
        self.event_items: dict[str, GameEvent] = {}
        self.command_id = 0
        self.game_closed_reported = False
        self.watch_running = False
        self.watch_elapsed = 0.0
        self.watch_start = 0.0
        self._build()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(110, self.poll)

    def _build(self):
        frame = ttk.Frame(self.root, padding=12)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="DIAGNÓSTICO KOF 2002 | KO • EQUIPOS • TIEMPO",
                  style="Header.TLabel").pack(anchor="w", pady=(0, 7))

        pathrow = ttk.Frame(frame)
        pathrow.pack(fill="x", pady=2)
        ttk.Label(pathrow, text="MAME 0.289:").pack(side="left")
        ttk.Entry(pathrow, textvariable=self.exe).pack(
            side="left", fill="x", expand=True, padx=6)
        ttk.Button(pathrow, text="Examinar...", command=self.pick_exe).pack(side="left")

        romrow = ttk.Frame(frame)
        romrow.pack(fill="x", pady=2)
        ttk.Label(romrow, text="Carpeta ROM:").pack(side="left")
        ttk.Entry(romrow, textvariable=self.rom_folder).pack(
            side="left", fill="x", expand=True, padx=6)
        ttk.Button(romrow, text="Examinar...", command=self.pick_rom_folder).pack(side="left")
        ttk.Label(romrow, text="Juego:").pack(side="left", padx=(12, 3))
        ttk.Entry(romrow, textvariable=self.rom_name, width=13).pack(side="left")

        actions = ttk.Frame(frame)
        actions.pack(fill="x", pady=(8, 5))
        ttk.Button(actions, text="INICIAR MAME CON DIAGNÓSTICO",
                   command=self.launch_mame).pack(side="left", padx=(0, 7))
        ttk.Button(actions, text="ABRIR CARPETA DE CAPTURAS",
                   command=self.open_session_folder).pack(side="left", padx=(0, 7))
        ttk.Button(actions, text="EXPORTAR EVENTOS CSV",
                   command=self.export_csv).pack(side="left")
        ttk.Label(frame, textvariable=self.status,
                  style="Status.TLabel").pack(anchor="w", pady=(2, 9))

        vital = ttk.Frame(frame)
        vital.pack(fill="x", pady=(0, 5))
        ttk.Label(vital, textvariable=self.p1_text,
                  style="Header.TLabel").pack(side="left", padx=(0, 40))
        ttk.Label(vital, textvariable=self.p2_text,
                  style="Header.TLabel").pack(side="left")
        ttk.Label(frame, textvariable=self.team_status,
                  style="Status.TLabel").pack(anchor="w", pady=(1, 3))
        for variable in (self.timer_text, self.counters_text, self.frame_text):
            ttk.Label(frame, textvariable=variable).pack(anchor="w", pady=1)

        watch = ttk.Frame(frame)
        watch.pack(fill="x", pady=(8, 6))
        ttk.Label(watch, textvariable=self.watch_text,
                  style="Status.TLabel").pack(side="left", padx=(0, 10))
        ttk.Button(watch, text="Iniciar / Reanudar cronómetro",
                   command=self.resume_watch).pack(side="left", padx=(0, 5))
        ttk.Button(watch, text="Pausar",
                   command=self.pause_watch).pack(side="left", padx=(0, 5))
        ttk.Button(watch, text="Reiniciar",
                   command=self.reset_watch).pack(side="left")

        ttk.Label(frame, text="MARCAR LO QUE VES EN LA PARTIDA "
                  "(se registra en el fotograma siguiente):").pack(
                      anchor="w", pady=(8, 3))
        marksbox = ttk.Frame(frame)
        marksbox.pack(fill="x", pady=(0, 7))
        for index, (label, event_name) in enumerate(MARKS):
            col = index % 5
            row = index // 5
            widget = ttk.Button(
                marksbox, text=label,
                command=lambda name=event_name: self.mark_event(name))
            widget.grid(row=row, column=col, padx=3, pady=3, sticky="ew")
        for i in range(5):
            marksbox.grid_columnconfigure(i, weight=1)

        ttk.Label(frame, text="EVENTOS CAPTURADOS (fotograma exacto de MAME):",
                  style="Header.TLabel").pack(anchor="w", pady=(6, 4))
        holder = ttk.Frame(frame)
        holder.pack(fill="both", expand=True)
        columns = ("frame", "event", "p1", "p2", "counter", "timer")
        self.tree = ttk.Treeview(holder, columns=columns,
                                 show="headings", selectmode="browse")
        definitions = [
            ("frame", "Fotograma", 105), ("event", "Evento", 330),
            ("p1", "Vida P1", 100), ("p2", "Vida P2", 100),
            ("counter", "Contadores P1/P2", 145),
            ("timer", "Tiempo", 130)
        ]
        for key, title, width in definitions:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, anchor="center", minwidth=70)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(holder, command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind("<<TreeviewSelect>>", self.show_event_details)

        ttk.Label(frame, text="MEMORIA CERCANA AL EVENTO "
                  "(selecciona una fila para verla):").pack(anchor="w", pady=(7, 3))
        self.details = tk.Text(frame, height=4, bg="#172a40", fg="#c8e7fd",
                               font=("Consolas", 9), wrap="word")
        self.details.pack(fill="x")
        self.details.insert("1.0", "Esperando eventos. "
                            "Al ocurrir un KO se guardan hasta 180 fotogramas "
                            "anteriores y 120 posteriores.")

    def pick_exe(self):
        selected = filedialog.askopenfilename(
            title="Selecciona MAME 0.289 (mame.exe)",
            filetypes=[("Ejecutables", "*.exe"), ("Todos", "*.*")])
        if selected:
            self.exe.set(selected)
            if not self.rom_folder.get():
                self.rom_folder.set(str(pathlib.Path(selected).parent))

    def pick_rom_folder(self):
        selected = filedialog.askdirectory(title="Directorio donde están las ROM")
        if selected:
            self.rom_folder.set(selected)

    def launch_mame(self):
        if sys.platform != "win32":
            messagebox.showerror("Windows necesario", "MAME necesita Windows en este proyecto.")
            return
        if self.proc is not None and self.proc.poll() is None:
            messagebox.showinfo("Partida abierta",
                                "Cierra esa instancia de MAME antes de iniciar otra.")
            return
        exe = pathlib.Path(self.exe.get().strip())
        if not exe.is_file():
            messagebox.showerror("MAME", "Selecciona el ejecutable mame.exe válido.")
            return
        if not LUA_FILE.is_file():
            messagebox.showerror("Script faltante",
                                 "Coloca KOF_Diagnostico_Combate.lua junto al .py.")
            return
        shortname = self.rom_name.get().strip()
        if re.fullmatch(r"[a-z0-9_]{1,32}", shortname) is None:
            messagebox.showerror("ROM", "Nombre de ROM incorrecto.")
            return
        try:
            version = subprocess.run(
                [str(exe.resolve()), "-version"], cwd=str(exe.resolve().parent),
                capture_output=True, text=True, timeout=8, errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            text = version.stdout + version.stderr
            if version.returncode != 0 or not re.search(r"\b0\.289\b", text):
                raise RuntimeError("Este ejecutable no informa versión MAME 0.289: "
                                   + text[:160])
            session = SESSION_DIR / dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            if session.exists():
                session = SESSION_DIR / (session.name + "_" + str(time.time_ns() % 10000))
            session.mkdir(parents=True, exist_ok=False)
            self.session = session
            self.state_path = session / "KOF_DIAG_ESTADO.tsv"
            self.events_path = session / "KOF_DIAG_EVENTOS.tsv"
            self.clips_path = session / "KOF_DIAG_CLIPS.tsv"
            self.commands_path = session / "KOF_DIAG_COMANDO.tsv"
            self.event_offset = 0
            self.pending_event_bytes = b""
            self.event_rows.clear()
            self.event_items.clear()
            for item in self.tree.get_children():
                self.tree.delete(item)
            self.seq = 0
            self.last_frame = -1
            self.game_closed_reported = False
            self.command_id = 0
            self.team_status.set("EQUIPOS: esperando datos de MAME...")
            self.reset_watch()

            rom_dir = pathlib.Path(self.rom_folder.get().strip() or str(exe.parent))
            paths = list(dict.fromkeys([
                str(rom_dir), str(rom_dir / "roms"),
                str(exe.resolve().parent), str(exe.resolve().parent / "roms")
            ]))
            env = os.environ.copy()
            for key, file in (
                ("KOF_DIAG_STATE", self.state_path),
                ("KOF_DIAG_EVENTS", self.events_path),
                ("KOF_DIAG_CLIPS", self.clips_path),
                ("KOF_DIAG_COMMAND", self.commands_path),
            ):
                env[key] = str(file)
            command = [str(exe.resolve()), shortname, "-window", "-console",
                       "-rompath", os.pathsep.join(paths),
                       "-autoboot_script", str(LUA_FILE)]
            self.proc = subprocess.Popen(
                command, cwd=str(exe.resolve().parent), env=env)
            (session / "INSTRUCCIONES.txt").write_text(
                "KOFMULTI diagnóstico v" + VERSION +
                "\nROM: " + shortname + "\nMAME: " + str(exe.resolve()) +
                "\nHP P1=0x108239, P2=0x108439, KO candidato=254" +
                "\nTIEMPO=0x10A7D2, AUX=0x10A7D3" +
                "\nEl fin de equipo NO se considera probado hasta revisión humana." +
                "\nNingún dato modifica el marcador.\n", encoding="utf-8")
            self.status.set(f"MAME iniciado PID {self.proc.pid} | "
                            f"carpeta: {session.name}")
            self.resume_watch()
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
            messagebox.showerror("Error al abrir MAME", str(exc))
            self.status.set("Error al iniciar diagnóstico: " + str(exc)[:140])

    def update_state(self):
        if self.state_path is None or not self.state_path.is_file():
            return
        try:
            if self.state_path.stat().st_size > 512:
                return
            parsed = parse_state(self.state_path.read_text(encoding="ascii"))
        except (OSError, UnicodeError):
            return
        if not parsed:
            return
        seq, state = parsed
        if seq <= self.seq:
            return
        self.seq, self.last_frame = seq, state.frame
        self.last_read_at = time.monotonic()
        self.p1_text.set("P1: " + byte_label(state.hp1))
        self.p2_text.set("P2: " + byte_label(state.hp2))
        self.timer_text.set("TIEMPO DEL JUEGO: " + timer_label(state.timer)
                            + f" | estado 0x{state.timer_aux:02X}")
        self.counters_text.set(
            f"Contadores ('Rounds Lost'): P1={state.lost1} / P2={state.lost2} "
            f"| transiciones 254/255: P1={state.ko1} / P2={state.ko2}")
        if state.lost1 == 3 and state.lost2 < 3:
            self.team_status.set(
                f"POSIBLE FIN EQUIPO P1 (3/3): fotograma {state.frame}; "
                "pendiente confirmar pantalla de victoria")
        elif state.lost2 == 3 and state.lost1 < 3:
            self.team_status.set(
                f"POSIBLE FIN EQUIPO P2 (3/3): fotograma {state.frame}; "
                "pendiente confirmar pantalla de victoria")
        elif state.lost1 <= 3 and state.lost2 <= 3:
            self.team_status.set(
                f"PERSONAJES/RONDAS PERDIDAS: P1 {state.lost1}/3, "
                f"P2 {state.lost2}/3 (observación)")
        else:
            self.team_status.set("EQUIPOS: datos fuera de rango; esperar combate")
        self.frame_text.set(f"Fotograma emulado: {state.frame} | "
                            "0x10A7D2 tiempo, 0x10A7D3 estado")
        self.status.set(f"Telemetría activa (solo lectura) | sesión {self.session.name}")

    def update_events(self):
        if self.events_path is None or not self.events_path.exists():
            return
        try:
            size = self.events_path.stat().st_size
            if size < self.event_offset:
                self.event_offset, self.pending_event_bytes = 0, b""
            with self.events_path.open("rb") as file:
                file.seek(self.event_offset)
                data = file.read(128 * 1024)
                self.event_offset = file.tell()
            if not data:
                return
            combined = self.pending_event_bytes + data
            lines = combined.split(b"\n")
            self.pending_event_bytes = lines.pop()
            for raw in lines:
                event = parse_event(raw.decode("ascii", errors="replace"))
                if event:
                    self.add_event(event)
        except OSError:
            return

    def add_event(self, event: GameEvent):
        s = event.reading
        self.event_rows.append(event)
        row = self.tree.insert("", "end", values=(
            s.frame, event.kind, byte_label(s.hp1), byte_label(s.hp2),
            f"{s.lost1} / {s.lost2}", timer_label(s.timer)))
        self.event_items[row] = event
        if event.kind.startswith("MARCA_"):
            self.status.set("Marca del usuario registrada: " + event.kind)
        if event.kind in (
            "POSIBLE_FIN_EQUIPO_P1", "POSIBLE_FIN_EQUIPO_P2"):
            self.team_status.set("ATENCIÓN: " + event.kind.replace("_", " ") +
                                 f" | fotograma {s.frame}")
        if len(self.event_items) > 750:
            oldest = next(iter(self.event_items))
            self.tree.delete(oldest)
            self.event_items.pop(oldest, None)
        self.tree.see(row)

    def mark_event(self, mark: str):
        if mark not in dict((code, label) for label, code in MARKS):
            return
        if self.commands_path is None or self.proc is None or self.proc.poll() is not None:
            messagebox.showwarning("MAME cerrado",
                                   "Primero inicia la partida desde esta ventana.")
            return
        # Microsegundos epoch: número exacto representable por Lua (double).
        self.command_id = max(self.command_id + 1, time.time_ns() // 1000)
        text = f"KOF_DIAG_CMD1\t{self.command_id}\t{mark}\n"
        try:
            self.commands_path.write_text(text, encoding="ascii")
            self.status.set("Marcador solicitado: " + mark +
                            " | Lua lo guardará en el siguiente fotograma leído.")
        except OSError as exc:
            messagebox.showerror("Error al registrar", str(exc))

    def show_event_details(self, _event=None):
        selected = self.tree.selection()
        if not selected or selected[0] not in self.event_items:
            return
        data = self.event_items[selected[0]]
        s = data.reading
        labels = ("P1 0x108239", "P2 0x108439", "Rondas P1 0x10A7E5",
                  "Rondas P2 0x10A80B", "Tiempo 0x10A7D2")
        out = (f"EVENTO: {data.kind} | FOTOGRAMA {s.frame}\n"
               f"Vida P1={s.hp1} / Vida P2={s.hp2} | "
               f"Contadores={s.lost1},{s.lost2} | "
               f"Tiempo=0x{s.timer:02X}, AUX=0x{s.timer_aux:02X}\n")
        out += "\n".join(
            f"{label}: {context}"
            for label, context in zip(labels, data.contexts))
        self.details.delete("1.0", "end")
        self.details.insert("1.0", out)

    def resume_watch(self):
        if not self.watch_running:
            self.watch_start = time.monotonic()
            self.watch_running = True

    def pause_watch(self):
        if self.watch_running:
            self.watch_elapsed += time.monotonic() - self.watch_start
            self.watch_running = False

    def reset_watch(self):
        self.watch_elapsed = 0.0
        self.watch_start = time.monotonic()

    def update_watch(self):
        elapsed = self.watch_elapsed
        if self.watch_running:
            elapsed += time.monotonic() - self.watch_start
        minutes, seconds = divmod(max(0.0, elapsed), 60.0)
        self.watch_text.set(
            f"Cronómetro local: {int(minutes):02d}:{seconds:04.1f} "
            "| no modifica el tiempo de MAME")

    def open_session_folder(self):
        if self.session is None:
            messagebox.showinfo("Aún no hay capturas", "Inicia una sesión primero.")
            return
        try:
            if sys.platform == "win32":
                os.startfile(str(self.session))
            else:
                self.status.set("Carpeta: " + str(self.session))
        except OSError as exc:
            messagebox.showerror("Carpeta", str(exc))

    def export_csv(self):
        if not self.event_rows:
            messagebox.showinfo("Sin eventos", "Todavía no hay cambios registrados.")
            return
        default = "KOF_DIAGNOSTICO_EVENTOS.csv"
        selected = filedialog.asksaveasfilename(
            title="Exportar eventos", defaultextension=".csv",
            initialfile=default, filetypes=[("CSV", "*.csv")])
        if not selected:
            return
        try:
            with open(selected, "w", encoding="utf-8-sig", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(["frame", "evento", "vida_p1", "vida_p2",
                                 "contador_p1", "contador_p2", "tiempo_raw",
                                 "tiempo_aux", "254_p1", "254_p2",
                                 "memoria_hp1", "memoria_hp2", "memoria_contador_p1",
                                 "memoria_contador_p2", "memoria_tiempo"])
                for event in self.event_rows:
                    s = event.reading
                    writer.writerow([s.frame, event.kind, s.hp1, s.hp2,
                                     s.lost1, s.lost2, s.timer, s.timer_aux,
                                     s.ko1, s.ko2, *event.contexts])
            self.status.set("CSV exportado: " + str(selected))
        except OSError as exc:
            messagebox.showerror("Exportar", str(exc))

    def poll(self):
        self.update_state()
        self.update_events()
        self.update_watch()
        if (self.proc is not None and self.proc.poll() is not None and
                not self.game_closed_reported):
            self.game_closed_reported = True
            self.pause_watch()
            self.status.set("MAME terminó. Los datos quedaron en " +
                            str(self.session))
        if (self.proc is not None and self.proc.poll() is None and
                self.last_read_at and time.monotonic() - self.last_read_at > 6):
            self.status.set(
                "Sin telemetría reciente: verifica que la ROM y Lua estén funcionando.")
        self.root.after(110, self.poll)

    def close(self):
        # No cerrar/terminar MAME inesperadamente: el usuario puede seguir
        # jugando. Al salir del diagnóstico, MAME ya no tendrá visor Python.
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def selftest():
    assert byte_label(254).startswith("254 (KO")
    assert byte_label(255).startswith("255 (KO")
    assert byte_label(102) == "102 / 102"
    assert timer_label(0x99).startswith("99")
    assert timer_label(0x60).startswith("60")
    assert timer_label(0x41).startswith("41")
    assert timer_label(0xAB).startswith("0xAB")
    good = ("KOF_DIAG_STATE1\t3\t842\t102\t254\t0\t2"
            "\t153\t1\t0\t1\n")
    result = parse_state(good)
    assert result and result[0] == 3
    assert result[1] == Reading(842, 102, 254, 0, 2, 153, 1, 0, 1)
    assert parse_state("KOF_DIAG_STATE1\t3\t842\t102\t999\t0\t2\t153\t1\t0\t1") is None
    assert parse_state("KOF_DIAG_STATE1\t3\t842\t102\t254") is None
    ctx = "\t".join(["00" * 32] * 5)
    good_evt = "KOF_DIAG_EVT1\t842\t102\t254\t0\t2\t153\t1\t0\t1\tP2_ENTRO_254\t" + ctx
    event = parse_event(good_evt)
    assert event is not None and event.kind == "P2_ENTRO_254"
    assert event.reading.frame == 842 and len(event.contexts) == 5
    assert parse_event(good_evt.replace("00" * 32, "ZZ" * 32)) is None
    assert parse_event("KOF_DIAG_EVT1\t1\t1\t1") is None
    # Fotogramas que constan en el registro real del usuario:
    first = Reading(4323, 102, 255, 0, 1, 0x38, 35, 0, 0)
    timeout = Reading(8373, 102, 35, 0, 2, 0, 0, 0, 0)
    last = Reading(9733, 102, 254, 0, 3, 0x41, 3, 0, 1)
    assert first.hp2 == 255 and first.lost2 == 1
    assert timeout.lost2 == 2 and timeout.timer == 0
    assert last.hp2 == 254 and last.lost2 == 3
    print("OK: 254/255, BCD, primera muerte, tiempo agotado y ultimo personaje.")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        DiagnosticsApp().run()
