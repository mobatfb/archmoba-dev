#!/usr/bin/python3
"""Compatibilidad de arranque: PYRIONOS es el nuevo escritorio."""
import runpy
import sys
from pathlib import Path

if __name__ == '__main__':
    target = Path('/opt/pyrionos/app.py')
    sys.argv[0] = str(target)
    runpy.run_path(str(target), run_name='__main__')
