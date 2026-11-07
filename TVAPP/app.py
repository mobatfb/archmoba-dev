"""TVAPP: lanzador con actualizaciones desde GitHub y dependencias automaticas."""

from __future__ import annotations

import ast
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
import time
from urllib.request import Request, urlopen

if sys.version_info < (3, 10):
    raise SystemExit("Se requiere Python 3.10 o superior. En Windows ejecuta iniciar.bat.")

try:
    import tkinter as tk
    from tkinter import messagebox
except ImportError as exc:
    raise SystemExit(
        "Falta tkinter. En Windows instala Python desde python.org con Tcl/Tk; "
        "en Debian/Ubuntu instala python3-tk."
    ) from exc


APP_VERSION = "1.0.9"
WINDOW_WIDTH = 380
WINDOW_HEIGHT = 650
REPOSITORY = "mobatfb/archmoba-dev"
BRANCH = "main"
COMMITS_URL = (
    f"https://api.github.com/repos/{REPOSITORY}/commits"
    "?path=TVAPP%2Ftvapp.py&per_page=1"
)
BASE_DIR = Path(__file__).resolve().parent
TVAPP_PATH = BASE_DIR / "tvapp.py"
STATE_PATH = BASE_DIR / ".tvapp_update.json"

# Algunos nombres de importacion difieren del nombre del paquete en PyPI.
PIP_NAMES = {
    "PIL": "Pillow",
    "cv2": "opencv-python",
    "yaml": "PyYAML",
    "bs4": "beautifulsoup4",
    "serial": "pyserial",
    "sklearn": "scikit-learn",
    "dotenv": "python-dotenv",
    "fitz": "PyMuPDF",
    "Crypto": "pycryptodome",
}


def version_from_source(source: str) -> str:
    """Lee VERSION (o __version__) sin ejecutar codigo remoto."""
    tree = ast.parse(source, filename="tvapp.py")
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names = [target.id for target in node.targets if isinstance(target, ast.Name)]
            value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names = [node.target.id]
            value = node.value
        else:
            continue
        if ("VERSION" in names or "__version__" in names) and isinstance(value, ast.Constant):
            if isinstance(value.value, str) and re.fullmatch(r"\d+(?:\.\d+)*", value.value):
                return value.value
    raise ValueError("tvapp.py debe declarar VERSION = '1.0.0' (version numerica).")


def version_numbers(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def missing_packages(source: str) -> list[tuple[str, str]]:
    """Detecta imports externos que no estan instalados, sin importar tvapp.py."""
    tree = ast.parse(source, filename="tvapp.py")
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])

    missing: list[tuple[str, str]] = []
    for name in sorted(roots):
        if name in sys.stdlib_module_names or name == "__future__":
            continue
        if (BASE_DIR / f"{name}.py").exists() or (BASE_DIR / name / "__init__.py").exists():
            continue
        try:
            present = importlib.util.find_spec(name) is not None
        except (ImportError, AttributeError, ValueError):
            present = False
        if not present:
            missing.append((name, PIP_NAMES.get(name, name)))
    return missing


def run_command(args: list[str]) -> tuple[int, str]:
    """Ejecuta pip sin abrir una consola adicional en Windows."""
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    completed = subprocess.run(
        args,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace",
        creationflags=flags,
        timeout=360,
        check=False,
    )
    return completed.returncode, completed.stdout[-3000:]


def atomic_write(path: Path, source: str) -> None:
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_text(source, encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def lock_mobile_window(window):
    """Impide maximizar, ajustar o cambiar las dimensiones de la ventana."""
    if getattr(window, "_archmoba_mobile_size_locked", False):
        return
    window._archmoba_mobile_size_locked = True
    window.resizable(False, False)
    window.minsize(WINDOW_WIDTH, WINDOW_HEIGHT)
    window.maxsize(WINDOW_WIDTH, WINDOW_HEIGHT)

    def restore_size():
        try:
            state = window.state()
            if state == "zoomed":
                window.state("normal")
            if window.state() == "normal" and (
                window.winfo_width() != WINDOW_WIDTH
                or window.winfo_height() != WINDOW_HEIGHT
            ):
                window.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        except tk.TclError:
            pass

    def on_resize(event):
        if event.widget is window:
            window.after_idle(restore_size)

    window.bind("<Configure>", on_resize, add="+")
    window.after_idle(restore_size)

    if os.name == "nt":
        def disable_maximize():
            """Quita el boton maximizar y el ajuste Snap en Windows."""
            try:
                import ctypes
                from ctypes import wintypes

                user32 = ctypes.WinDLL("user32", use_last_error=True)
                user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
                user32.GetAncestor.restype = wintypes.HWND
                user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
                user32.GetWindowLongW.restype = ctypes.c_long
                user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
                user32.SetWindowLongW.restype = ctypes.c_long
                user32.SetWindowPos.argtypes = [
                    wintypes.HWND, wintypes.HWND,
                    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                    wintypes.UINT,
                ]
                user32.SetWindowPos.restype = wintypes.BOOL

                hwnd = user32.GetAncestor(wintypes.HWND(window.winfo_id()), 2)
                if hwnd:
                    style = user32.GetWindowLongW(hwnd, -16)
                    # WS_MAXIMIZEBOX | WS_THICKFRAME
                    fixed_style = style & ~0x00050000
                    if fixed_style != style:
                        user32.SetWindowLongW(hwnd, -16, fixed_style)
                        # SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_FRAMECHANGED
                        user32.SetWindowPos(hwnd, wintypes.HWND(0), 0, 0, 0, 0, 0x27)
            except (OSError, AttributeError, ValueError):
                pass

        window.after_idle(disable_maximize)


class TVAppManager:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"ARCHMOBA | TVAPP - APP v{APP_VERSION}")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.update_idletasks()
        pos_x = max(0, (self.root.winfo_screenwidth() - WINDOW_WIDTH) // 2)
        pos_y = max(0, (self.root.winfo_screenheight() - WINDOW_HEIGHT) // 2)
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{pos_x}+{pos_y}")
        lock_mobile_window(self.root)
        self.root.configure(bg="#ffffff")
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.busy = False

        header = tk.Frame(root, bg="#ffffff", height=66)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header, text="TVAPP", bg="#ffffff", fg="#111827",
            font=("Segoe UI", 17, "bold")
        ).pack(side="left", padx=(22, 18))
        self.version_label = tk.Label(
            header, text="Version: --", bg="#ffffff", fg="#475467",
            font=("Segoe UI", 11)
        )
        self.version_label.pack(side="left")
        self.update_button = tk.Button(
            header, text="Actualizar", command=self.check_for_updates,
            bg="#14b8a6", fg="#082f2b", activebackground="#5eead4",
            font=("Segoe UI", 10, "bold"), relief="flat",
            cursor="hand2", padx=20, pady=8
        )
        self.update_button.pack(side="right", padx=20)

        self.body = tk.Frame(root, bg="white")
        self.body.pack(fill="both", expand=True, padx=12, pady=(12, 0))
        tk.Label(
            self.body, text="Cargando TVAPP...", bg="white",
            fg="#667085", font=("Segoe UI", 15)
        ).place(relx=0.5, rely=0.5, anchor="center")

        self.status_var = tk.StringVar(value="Comprobando dependencias locales...")
        tk.Label(
            root, textvariable=self.status_var, anchor="w",
            bg="#ffffff", fg="#475467", font=("Segoe UI", 9),
            padx=14, pady=9
        ).pack(fill="x")

        if TVAPP_PATH.exists():
            try:
                self.version_label.config(
                    text=f"Version: {version_from_source(TVAPP_PATH.read_text(encoding='utf-8'))}"
                )
            except (OSError, ValueError, SyntaxError):
                pass
        self.root.after(100, self._process_events)
        self._start("startup")

    def _tell(self, kind: str, value: object) -> None:
        self.events.put((kind, value))

    def _start(self, action: str) -> None:
        if self.busy:
            return
        self.busy = True
        self.update_button.config(state="disabled", text="Procesando...")
        threading.Thread(target=self._worker, args=(action,), daemon=True).start()

    def check_for_updates(self) -> None:
        self._start("update")

    def _ensure_dependencies(self, source: str) -> None:
        packages = missing_packages(source)
        if not packages:
            return

        self._tell("status", "Preparando instalacion de dependencias...")
        code, output = run_command([sys.executable, "-m", "pip", "--version"])
        if code != 0:
            code, output = run_command([sys.executable, "-m", "ensurepip", "--upgrade"])
            if code != 0:
                raise RuntimeError("No se pudo activar pip: " + output[-400:])

        for module, package in packages:
            self._tell("status", f"Instalando {package} en segundo plano...")
            code, output = run_command([
                sys.executable, "-m", "pip", "install",
                "--disable-pip-version-check", "--no-input", package
            ])
            if code != 0:
                raise RuntimeError(f"No se pudo instalar {package}: {output[-600:]}")
            importlib.invalidate_caches()
            try:
                installed = importlib.util.find_spec(module) is not None
            except (ImportError, AttributeError, ValueError):
                installed = False
            if not installed:
                raise RuntimeError(
                    f"Se instalo {package}, pero no se encontro el import {module}. "
                    "Comprueba el nombre del paquete."
                )

    @staticmethod
    def _get_text(url: str, max_bytes: int = 1024 * 1024) -> str:
        """Solicita contenido fresco a GitHub (con timeout) sin bloquear Tkinter."""
        request = Request(
            url,
            headers={
                "User-Agent": "ARCHMOBA-TVAPP/1.1",
                "Accept": "application/vnd.github+json",
                "Cache-Control": "no-cache, no-store, max-age=0",
                "Pragma": "no-cache",
            },
        )
        with urlopen(request, timeout=10) as response:
            data = response.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ValueError("El archivo remoto excede el tamano permitido.")
        return data.decode("utf-8-sig")

    def _latest_tvapp_commit(self) -> str:
        """Lee el commit mas reciente que modifico TVAPP/tvapp.py."""
        url = f"{COMMITS_URL}&cache_bust={time.time_ns()}"
        items = json.loads(self._get_text(url, max_bytes=256 * 1024))
        if not isinstance(items, list) or not items:
            raise ValueError("GitHub no devolvio commits para tvapp.py.")
        sha = items[0].get("sha", "")
        if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise ValueError("GitHub devolvio un commit no valido.")
        return sha

    @staticmethod
    def _file_hash(source: str) -> str:
        return hashlib.sha256(source.encode("utf-8")).hexdigest()

    @staticmethod
    def _read_state() -> dict:
        try:
            state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            return state if isinstance(state, dict) else {}
        except (OSError, ValueError, TypeError):
            return {}

    @staticmethod
    def _save_state(commit: str, source: str) -> None:
        data = {
            "commit": commit,
            "sha256": TVAppManager._file_hash(source),
            "version": version_from_source(source),
        }
        atomic_write(STATE_PATH, json.dumps(data, indent=2))

    def _download_commit(self, commit: str) -> str:
        """Descarga el archivo inmutable asociado a ese commit."""
        url = (
            f"https://raw.githubusercontent.com/{REPOSITORY}/"
            f"{commit}/TVAPP/tvapp.py"
        )
        return self._get_text(url)

    def _worker(self, action: str) -> None:
        local_loaded = False
        try:
            if action == "startup" and TVAPP_PATH.exists():
                try:
                    local = TVAPP_PATH.read_text(encoding="utf-8")
                    version_from_source(local)
                    self._ensure_dependencies(local)
                    self._tell("show", (local, "Version local cargada. Comprobando GitHub..."))
                    local_loaded = True
                except Exception as exc:
                    self._tell("status", f"Se recuperara la version local: {exc}")

            self._tell("status", "Consultando ultimo commit de tvapp.py en GitHub...")
            remote = None
            try:
                commit = self._latest_tvapp_commit()
                self._tell("status", f"Commit {commit[:8]} encontrado. Comprobando cambios...")
            except Exception:
                # Respaldo si la API esta limitada o bloqueada.
                self._tell(
                    "status",
                    "API de commits no disponible. Descargando archivo sin cache...",
                )
                direct_url = (
                    f"https://raw.githubusercontent.com/{REPOSITORY}/{BRANCH}"
                    f"/TVAPP/tvapp.py?cache_bust={time.time_ns()}"
                )
                remote = self._get_text(direct_url)
                commit = "direct-" + self._file_hash(remote)

            local = TVAPP_PATH.read_text(encoding="utf-8") if TVAPP_PATH.exists() else None
            state = self._read_state()

            if (
                local is not None
                and remote is None
                and state.get("commit") == commit
                and state.get("sha256") == self._file_hash(local)
            ):
                version = version_from_source(local)
                self._tell("show", (
                    local,
                    f"Sin cambios: v{version}, commit {commit[:8]}.",
                ))
                return

            if remote is None:
                self._tell("status", f"Descargando tvapp.py del commit {commit[:8]}...")
                remote = self._download_commit(commit)
            version = version_from_source(remote)
            compile(remote, str(TVAPP_PATH), "exec")

            if local != remote:
                self._ensure_dependencies(remote)
                self._tell("apply", (remote, version, commit))
            else:
                self._tell("same", (remote, version, commit))
        except Exception as exc:
            # Cuando hay copia local funcional, el inicio puede continuar sin red.
            if action == "startup" and local_loaded:
                self._tell("warning", f"Sin actualizacion: {exc}")
            else:
                self._tell("error", f"No se pudo comprobar GitHub: {exc}")
        finally:
            self._tell("done", None)

    def _show_source(self, source: str) -> None:
        """Carga el codigo actualizado y muestra su widget dentro de la ventana."""
        namespace: dict[str, object] = {
            "__name__": "tvapp_embedded",
            "__file__": str(TVAPP_PATH),
        }
        old_widgets = set(self.body.winfo_children())
        try:
            exec(compile(source, str(TVAPP_PATH), "exec"), namespace)
            render = namespace.get("render")
            if not callable(render):
                raise ValueError("tvapp.py debe incluir una funcion render(parent).")
            widget = render(self.body)
            if not isinstance(widget, tk.Widget) or widget.master is not self.body:
                raise TypeError("render(parent) debe devolver un widget hijo de parent.")
        except Exception:
            for child in self.body.winfo_children():
                if child not in old_widgets:
                    child.destroy()
            raise

        for old in old_widgets:
            old.destroy()
        widget.pack(fill="both", expand=True)
        self.version_label.config(text=f"Version: {version_from_source(source)}")

    def _apply(self, remote: str, version: str, commit: str) -> None:
        previous = TVAPP_PATH.read_text(encoding="utf-8") if TVAPP_PATH.exists() else None
        try:
            atomic_write(TVAPP_PATH, remote)
            self._show_source(remote)
        except Exception:
            if previous is None:
                TVAPP_PATH.unlink(missing_ok=True)
            else:
                atomic_write(TVAPP_PATH, previous)
            raise
        self._save_state(commit, remote)
        self.status_var.set(
            f"Actualizado a v{version} desde commit {commit[:8]}. Interfaz recargada."
        )

    def _process_events(self) -> None:
        try:
            while True:
                kind, value = self.events.get_nowait()
                try:
                    if kind == "status":
                        self.status_var.set(str(value))
                    elif kind == "show":
                        source, status = value
                        self._show_source(source)
                        self.status_var.set(str(status))
                    elif kind == "apply":
                        source, version, commit = value
                        self._apply(source, version, commit)
                    elif kind == "same":
                        source, version, commit = value
                        self._show_source(source)
                        self._save_state(commit, source)
                        self.status_var.set(
                            f"Sin cambios: v{version}, commit {commit[:8]}. Interfaz recargada."
                        )
                    elif kind == "warning":
                        self.status_var.set(str(value))
                    elif kind == "error":
                        self.status_var.set("Error: " + str(value))
                        messagebox.showerror("TVAPP", str(value), parent=self.root)
                    elif kind == "done":
                        self.busy = False
                        self.update_button.config(state="normal", text="Actualizar")
                except Exception as exc:
                    self.status_var.set("Error: " + str(exc))
                    messagebox.showerror("TVAPP", str(exc), parent=self.root)
        except queue.Empty:
            pass
        self.root.after(100, self._process_events)


def main() -> None:
    root = tk.Tk()
    TVAppManager(root)
    root.mainloop()


if __name__ == "__main__":
    main()
