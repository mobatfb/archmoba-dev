#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FUTUREO VJOY Manager - interfaz experimental, solo para laboratorio Windows.
No puede instalar ni crear dispositivos hasta compilar, firmar e instalar FutJoy.sys.
"""
from __future__ import annotations
import ctypes
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from futureo_vjoy import FutJoy

BASE = Path(__file__).resolve().parents[1]
INF = BASE / "driver" / "FutJoy.inf"

def administrator() -> bool:
    if os.name != "nt":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (OSError, AttributeError):
        return False

def missing(exe: Path) -> list[str]:
    reasons = []
    if os.name != "nt":
        reasons.append("Requiere Windows")
    if not administrator():
        reasons.append("Ejecutar como administrador")
    for file in (INF, INF.parent / "FutJoy.sys", INF.parent / "FutJoy.cat", exe):
        if not file.is_file():
            reasons.append(f"Falta: {file}")
    return reasons

class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("FUTUREO VJOY - ADMINISTRADOR (EXPERIMENTAL)")
        self.root.geometry("750x635")
        self.root.minsize(630, 550)
        self.root.configure(bg="#0d1b30")
        self.count = tk.IntVar(value=2)
        self.slot = tk.IntVar(value=1)
        self.devcon = tk.StringVar(value=shutil.which("devcon.exe") or str(BASE / "driver" / "devcon.exe"))
        self.status = tk.StringVar(value="Prototipo: requiere driver KMDF compilado y firmado")
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
        tk.Label(tool,text="DevCon:",fg="white",bg="#0d1b30").pack(side="left")
        ttk.Entry(tool,textvariable=self.devcon).pack(side="left",fill="x",expand=True,padx=8)
        ttk.Button(tool,text="Buscar",command=self.browse).pack(side="left")
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
        namebar=tk.Frame(self.root,bg="#0d1b30")
        namebar.pack(pady=3)
        ttk.Button(namebar,text="ETIQUETAR EN WINDOWS",command=self.labels_apply).pack(side="left",padx=8)
        ttk.Button(namebar,text="RESTAURAR NOMBRES",command=self.labels_restore).pack(side="left",padx=8)
        tk.Label(self.root,textvariable=self.status,wraplength=700,
                 fg="#8fe8ef",bg="#0d1b30").pack(padx=16,pady=(6,18))

    def labels_apply(self):
        if not administrator():
            messagebox.showwarning("Permisos","Abre FUTUREO VJOY Manager como administrador.")
            return
        if not messagebox.askyesno("Nombres joy.cpl/DirectInput",
            "Crear alias FUTUREO VJOY1...VJOY" + str(self.count.get()) +
            " en el Registro de Windows? Se guardaran los valores originales y"
            " se podran restaurar. No cambia las cadenas HID internas."):
            return
        self._run_labels(["--apply", "--count", str(self.count.get())])

    def labels_restore(self):
        if not administrator():
            messagebox.showwarning("Permisos","Abre FUTUREO VJOY Manager como administrador.")
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
            self.results.put(("info",result.stdout.strip()[-300:]))
        self.background(worker)

    def browse(self):
        chosen=filedialog.askopenfilename(filetypes=[("Ejecutable Windows","*.exe")])
        if chosen: self.devcon.set(chosen)

    def poll(self):
        try:
            while True:
                kind,msg=self.results.get_nowait()
                if kind=="done": self.busy=False
                if msg: self.status.set(msg)
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

    def command(self,verb,slot):
        if not 1<=slot<=8: raise ValueError("Puesto invalido")
        ident=rf"ROOT\FUTJOY{slot:02d}"
        exe=Path(self.devcon.get())
        argv=[str(exe),"install",str(INF),ident] if verb=="install" else [str(exe),"remove",ident]
        result=subprocess.run(argv,capture_output=True,text=True,errors="replace",
                              timeout=40,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        self.results.put(("info",f"{verb} {ident}: codigo {result.returncode}: "
                         +(result.stdout+result.stderr).strip()[-180:]))
        if result.returncode: raise RuntimeError(f"DevCon fallo en {ident}")

    def install(self):
        problems=missing(Path(self.devcon.get()))
        if problems:
            messagebox.showwarning("Faltan requisitos","\n".join(problems))
            return
        quantity=self.count.get()
        if not messagebox.askyesno("ATENCION - DRIVER KERNEL EXPERIMENTAL",
           f"Instalar {quantity} dispositivos en este equipo? "
           "Recomendado UNICAMENTE en una maquina virtual de pruebas."):
            return
        self.background(lambda: [self.command("install",i) for i in range(1,quantity+1)])

    def remove(self):
        exe=Path(self.devcon.get())
        if os.name!="nt" or not administrator() or not exe.is_file():
            messagebox.showwarning("Requisitos","Necesita Windows, administrador y DevCon")
            return
        n=self.slot.get()
        if messagebox.askyesno("Confirmar",f"Eliminar ROOT\\FUTJOY{n:02d}?"):
            self.background(lambda: self.command("remove",n))

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
