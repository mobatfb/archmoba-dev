# -*- coding: utf-8 -*-
"""KOFMULTI: abrir el analizador de salud sin consola negra."""
import os
import sys
import runpy
from pathlib import Path

os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.dont_write_bytecode = True

if __name__ == "__main__":
    try:
        runpy.run_path(str(Path(__file__).resolve().with_name(
            "KOF_Analizador_Salud.py")), run_name="__main__")
    except Exception as exc:
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                None,
                f"No se pudo iniciar el analizador de salud.\n\n"
                f"{type(exc).__name__}: {exc}",
                "KOFMULTI - Analizador", 0x10)
        except Exception:
            pass
