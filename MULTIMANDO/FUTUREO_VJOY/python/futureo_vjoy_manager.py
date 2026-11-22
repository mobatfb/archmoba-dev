#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FUTUREO VJOY Manager - interfaz del laboratorio Windows.
Usa SetupAPI/pnputil desde instalador.ps1; NO necesita DevCon.exe.
El SYS firmado para pruebas ya viene dentro del ZIP de laboratorio.
"""
from __future__ import annotations
import ctypes
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

from futureo_vjoy import FutJoy

BASE = Path(__file__).resolve().parents[1]
INF = BASE / "DRIVER" / "FutJoy.inf"
INSTALLER = BASE / "HERRAMIENTAS" / "instalador.ps1"

def administrator() -> bool:
    if os.name != "nt":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (OSError, AttributeError):
        return False

def missing() -> list[str]:
    """Verificaciones previas; las operaciones con privilegios los solicitan via UAC."""
    reasons = []
    if os.name != "nt":
        reasons.append("Requiere Windows")
    for file in (INSTALLER, INF, INF.parent / "FutJoy.sys",
                 INF.parent / "FutJoy.cat",
                 INF.parent / "FUTUREO_VJOY_PRUEBA.cer",
                 INF.parent / "SHA256SUMS.txt"):
        if not file.is_file():
            reasons.append(f"Falta: {file}")
    return reasons

def ask_elevation_for_labels() -> bool:
    """Eleva SOLO si el usuario decide aplicar un alias OEM reversible."""
    if administrator():
        return True
    if os.name != "nt":
        messagebox.showwarning("Windows requerido", "Los nombres OEM solo se gestionan en Windows.")
        return False
    if not messagebox.askyesno(
        "Permisos para nombre OEM",
        "La etiqueta DirectInput necesita permisos de administrador.\n"
        "Deseas reabrir el administrador con UAC? Despues vuelve a pulsar "
        "ETIQUETAR EN WINDOWS. No se modifica nada hasta tu confirmacion."):
        return False
    args = f'"{Path(__file__).resolve()}"'
    code = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, args, None, 1)
    if code <= 32:
        messagebox.showerror("UAC cancelado", f"No se abrio como administrador (codigo {code}).")
        return False
    messagebox.showinfo("Nueva ventana elevada",
                        "Se abrio el administrador con permisos. "
                        "Utiliza ESA nueva ventana y pulsa ETIQUETAR EN WINDOWS.")
    return False  # No intentar escribir desde la ventana sin elevar.

class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("FUTUREO VJOY - ADMINISTRADOR (EXPERIMENTAL)")
        self.root.geometry("790x630")
        self.root.minsize(630, 550)
        self.root.configure(bg="#0d1b30")
        self.count = tk.IntVar(value=1)
        self.slot = tk.IntVar(value=1)
        self.status = tk.StringVar(value="Driver de laboratorio firmado: instalar 1..8 sin DevCon (SetupAPI)")
        self.results = queue.Queue()
        self.busy = False
        self.build()
        self.root.after(100, self.poll)

    def build(self):
        tk.Label(self.root, text="FUTUREO VJOY", font=("Segoe UI", 20, "bold"),
                 fg="white", bg="#0d1b30").pack(pady=(17, 5))
        tk.Label(self.root, text="1 a 8 gamepads HID independientes | laboratorio Windows",
                 fg="#9bcfe7", bg="#0d1b30").pack(pady=(0, 14))
        top=tk.Frame(self.root,bg="#0d1b30")
        top.pack(fill="x",padx=20,pady=6)
        tk.Label(top,text="Cantidad:",fg="white",bg="#0d1b30").pack(side="left")
        ttk.Combobox(top,values=list(range(1,9)),textvariable=self.count,state="readonly",
                     width=5).pack(side="left",padx=8)
        ttk.Button(top,text="CREAR DISPOSITIVOS",command=self.install).pack(side="left",padx=5)
        ttk.Button(top,text="QUITAR SELECCIONADO",command=self.remove).pack(side="left",padx=5)
        tool=tk.Frame(self.root,bg="#0d1b30")
        tool.pack(fill="x",padx=20,pady=8)
        tk.Label(tool,text="INSTALACION: SetupAPI + pnputil de Windows (sin DevCon.exe)",
                 fg="#80dfbc",bg="#0d1b30").pack(side="left")
        ttk.Button(tool,text="ABRIR JOY.CPL",command=self.open_joy).pack(side="right")
        grid=tk.Frame(self.root,bg="#0d1b30")
        grid.pack(fill="both",expand=True,padx=20,pady=6)
        for n in range(1,9):
            tk.Radiobutton(grid,text=f"FUTUREO VJOY{n}  / P{n}",
                variable=self.slot,value=n,indicatoron=False,
                fg="white",bg="#1c456b",selectcolor="#1676a0",
                activebackground="#2586b3",activeforeground="white",
                font=("Segoe UI",11,"bold"),padx=8,pady=12).grid(
                row=(n-1)//2,column=(n-1)%2,sticky="nsew",padx=5,pady=5)
        for col in range(2): grid.grid_columnconfigure(col,weight=1)
        for row in range(4): grid.grid_rowconfigure(row,weight=1)
        bar=tk.Frame(self.root,bg="#0d1b30")
        bar.pack(pady=8)
        ttk.Button(bar,text="IDENTIFICAR VJOY",command=self.test).pack(side="left",padx=8)
        ttk.Button(bar,text="COMPROBAR INSTALACION",command=self.check).pack(side="left",padx=8)
        ttk.Button(bar,text="VER IDENTIDAD HID",command=self.diagnostico_hid).pack(side="left",padx=8)
        namebar=tk.Frame(self.root,bg="#0d1b30")
        namebar.pack(pady=3)
        ttk.Button(namebar,text="ETIQUETAR EN WINDOWS",command=self.labels_apply).pack(side="left",padx=8)
        ttk.Button(namebar,text="RESTAURAR NOMBRES",command=self.labels_restore).pack(side="left",padx=8)
        tk.Label(self.root,textvariable=self.status,wraplength=700,
                 fg="#8fe8ef",bg="#0d1b30").pack(padx=16,pady=(6,18))

    def labels_apply(self):
        if not ask_elevation_for_labels():
            return
        if not messagebox.askyesno("Nombres joy.cpl/DirectInput",
            "Crear alias FUTUREO VJOY1...VJOY" + str(self.count.get()) +
            " en el Registro de Windows? Se guardaran los valores originales y"
            " se podran restaurar. No cambia las cadenas HID internas."):
            return
        self._run_labels(["--apply", "--count", str(self.count.get())])

    def labels_restore(self):
        if not ask_elevation_for_labels():
            return
        if not messagebox.askyesno("Restaurar Registro",
            "Restaurar los nombres guardados antes de aplicar etiquetas?"):
            return
        self._run_labels(["--restore"])

    def _run_labels(self, args):
        script=Path(__file__).with_name("nombres_windows.py")
        def worker():
            result=subprocess.run([sys.executable,str(script),*args],
                                  capture_output=True,text=True,errors="replace",timeout=60,
                                  creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
            if result.returncode:
                raise RuntimeError((result.stderr or result.stdout).strip()[-350:])
            extra = (
                " Cierra por completo joy.cpl y vuelve a abrirlo para "
                "comprobar la etiqueta. La cadena HID interna puede seguir "
                "siendo 'HID VHF Driver'."
                if "--apply" in args else ""
            )
            self.results.put(("info",result.stdout.strip()[-300:] + extra))
        self.background(worker)

    def diagnostico_hid(self):
        """Consultar identidades de Windows; no instala ni renombra nada."""
        script=Path(__file__).with_name("diagnostico_hid.py")
        def worker():
            result=subprocess.run(
                [sys.executable,str(script),"--count",str(self.count.get())],
                capture_output=True,text=True,errors="replace",timeout=45,
                creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
            message = (result.stdout or result.stderr).strip()
            if result.returncode:
                raise RuntimeError(message[-450:] or "No se pudo consultar el HID")
            self.results.put(("diagnostic",message))
        self.background(worker)

    def show_diagnostic(self, content: str):
        window=tk.Toplevel(self.root)
        window.title("FUTUREO VJOY | Diagnostico HID (solo lectura)")
        window.geometry("780x450")
        view=tk.Text(window,wrap="word",font=("Consolas",10),padx=12,pady=12)
        view.pack(expand=True,fill="both")
        view.insert("1.0",content)
        view.configure(state="disabled")

    def open_joy(self):
        if os.name != "nt":
            messagebox.showwarning("Windows requerido","Este panel solo existe en Windows.")
            return
        try:
            subprocess.Popen(["control.exe", "joy.cpl"])
        except OSError as exc:
            messagebox.showerror("joy.cpl", str(exc))

    def poll(self):
        try:
            while True:
                kind,msg=self.results.get_nowait()
                if kind=="done": self.busy=False
                elif kind=="diagnostic":
                    self.show_diagnostic(msg)
                    self.status.set("Diagnostico HID: comprobacion terminada (solo lectura)")
                elif msg: self.status.set(msg)
        except queue.Empty:
            pass
        self.root.after(100,self.poll)

    def background(self,fn):
        if self.busy: return
        self.busy=True
        def run():
            try: fn()
            except Exception as exc:
                self.results.put(("error",f"{type(exc).__name__}: {exc}"))
            finally: self.results.put(("done",""))
        threading.Thread(target=run,daemon=True).start()

    def command(self, action: str, quantity: int):
        """Ejecutar el instalador probado, con ventana de consola y UAC.
        El mismo PowerShell crea ROOT\FUTJOY01..08 mediante SetupAPI.
        No descargar ni buscar devcon.exe en ninguna ruta.
        """
        if action not in ("InstalarN", "QuitarN") or not 1 <= quantity <= 8:
            raise ValueError("Accion o cantidad no permitida")
        problems = missing()
        if problems:
            raise RuntimeError("\n".join(problems))
        cmdline = subprocess.list2cmdline([
            "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", str(INSTALLER), "-Accion", action, "-Cantidad", str(quantity)])
        # cmd crea consola interactiva (Read-Host necesita entrada del usuario).
        # Preservar el codigo de error ANTES del pause para no falsear exito.
        command = (
            cmdline + ' & set "futureo_rc=!errorlevel!"'
            + ' & echo. & echo Pulsa una tecla para volver al GUI FUTUREO.'
            + ' & pause >nul & exit /b !futureo_rc!'
        )
        self.results.put(("info",
                          f"{action} P1..P{quantity}: confirma en la consola abierta; "
                          "Windows solicitara UAC si es necesario."))
        flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
        result = subprocess.run(["cmd.exe", "/d", "/v:on", "/c", command],
                                timeout=1200, creationflags=flags, check=False)
        if result.returncode != 0:
            raise RuntimeError(
                f"{action} termino con codigo {result.returncode}. "
                "Consulta los detalles de la consola y el diagnostico de Windows.")
        self.results.put(("info",
                          f"Accion {action} finalizada. Verifica el mando en joy.cpl "
                          "y con VER IDENTIDAD HID."))

    def install(self):
        problems=missing()
        if problems:
            messagebox.showwarning("Falta paquete firmado",
                "\n".join(problems) +
                "\n\nDescarga y descomprime el ZIP completo del laboratorio.")
            return
        quantity=self.count.get()
        if not messagebox.askyesno("ATENCION - DRIVER KERNEL EXPERIMENTAL",
           f"Instalar HASTA {quantity} mando(s) en el equipo secundario?\n"
           "Se conservaran los puestos ya existentes. El instalador "
           "pedira confirmacion y UAC.\n\n"
           "No es necesario DevCon.exe."):
            return
        self.background(lambda: self.command("InstalarN",quantity))

    def remove(self):
        if os.name!="nt" or not INSTALLER.is_file():
            messagebox.showwarning("Requisitos",
                "Requiere Windows y el instalador.ps1 incluido en el ZIP.")
            return
        n=self.slot.get()
        if messagebox.askyesno("Confirmar retirada individual",
           f"Eliminar SOLO ROOT\\FUTJOY{n:02d}?\n"
           "Los otros mandos, el driver y el certificado se conservaran."):
            self.background(lambda: self.command("QuitarN",n))

    def check(self):
        n=self.slot.get()
        try:
            with FutJoy(n): self.status.set(f"FUTUREO VJOY{n}: conectado")
        except Exception as exc:
            self.status.set(f"FUTUREO VJOY{n}: no accesible - {exc}")

    def test(self):
        n=self.slot.get()
        def work():
            with FutJoy(n) as dev:
                for second in range(5,0,-1):
                    self.results.put(("info",f"VJOY{n}: cambia a joy.cpl en {second}..."))
                    time.sleep(1)
                for _ in range(3):
                    dev.state(x=26000,buttons=1)
                    time.sleep(0.3)
                    dev.neutral()
                    time.sleep(0.3)
                self.results.put(("info",f"VJOY{n}: listo, controles liberados"))
        self.background(work)

if __name__=="__main__":
    App().root.mainloop()
