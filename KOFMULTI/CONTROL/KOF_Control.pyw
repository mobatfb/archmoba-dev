# -*- coding: utf-8 -*-
"""
KOFMULTI CONTROL v.0.0.2 — lanzador de interfaz sin consola.
Doble clic en este archivo para abrir solamente la GUI.
No escribe archivos ni cache local.
"""
import os
import sys
from pathlib import Path
import runpy

os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.dont_write_bytecode = True

def main():
    script = Path(__file__).resolve().with_name("KOF_Control.py")
    try:
        runpy.run_path(str(script), run_name="__main__")
    except Exception as exc:
        # pythonw no tiene consola: mostrar los errores en una ventana.
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                None,
                "No se pudo abrir KOFMULTI CONTROL.\n\n"
                + type(exc).__name__ + ": " + str(exc)
                + "\n\nInstala la dependencia con: py -m pip install --no-cache-dir PySide6",
                "KOFMULTI CONTROL v.0.0.2",
                0x10,
            )
        except Exception:
            # No registrar errores en disco.
            pass

if __name__ == "__main__":
    main()
