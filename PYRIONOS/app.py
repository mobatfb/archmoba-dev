#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PYRION OS Desktop v0.1.0

Escritorio experimental para Windows/Linux, construido con PySide6.
Los datos persistentes se guardan en una carpeta 'pyrionos' situada en
un disco montado y accesible. La ubicación se busca en cada inicio.

Instalacion: python -m pip install PySide6
Ejecucion:   python PYRION_OS.py

NOTA: esto es una interfaz de escritorio, no un reemplazo del kernel ni
un compositor Wayland. El generador automatico de apps mediante IA es
una funcionalidad futura; las herramientas integradas si son reales.
"""

from __future__ import annotations

import ast
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unicodedata
import uuid
from typing import Any

APP_NAME = "PYRION OS"
APP_VERSION = "0.1.0"
DIR_NAME = "pyrionos"
SUBFOLDERS = ("apps", "config", "data", "cache", "logs", "downloads")


class StorageError(RuntimeError):
    """El almacenamiento persistente no esta disponible o es inseguro."""


def write_json_atomic(path: Path, obj: Any) -> None:
    """Guardar un JSON sin reemplazar el archivo previo a medio escribir."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=str(path.parent),
            prefix=".pyrion-", suffix=".tmp", delete=False
        ) as handle:
            temporary = Path(handle.name)
            json.dump(obj, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(temporary), str(path))
    finally:
        if temporary and temporary.exists():
            temporary.unlink(missing_ok=True)


def read_json_strict(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise StorageError(f"No se pudo leer {path}: {exc}") from exc


def mounted_volumes() -> list[Path]:
    """Obtiene discos/volumenes montados sin pedir privilegios de administrador."""
    volumes: list[Path] = []
    if os.name == "nt":
        # Win32 GetDriveTypeW: 3 = unidad fija. Evita pendrives y red por defecto.
        import ctypes
        get_drives = ctypes.windll.kernel32.GetLogicalDrives
        get_type = ctypes.windll.kernel32.GetDriveTypeW
        bits = get_drives()
        for index in range(26):
            if (bits >> index) & 1:
                root = Path(chr(65 + index) + ":\\")
                if get_type(str(root)) == 3:
                    volumes.append(root)
    else:
        # psutil es opcional. Si no esta, usamos los montajes de Linux.
        try:
            import psutil
            for part in psutil.disk_partitions(all=False):
                if part.fstype.lower() in {
                    "proc", "sysfs", "devtmpfs", "tmpfs", "squashfs",
                    "cgroup", "cgroup2", "autofs", "devpts", "overlay"
                }:
                    continue
                volumes.append(Path(part.mountpoint))
        except ImportError:
            if sys.platform.startswith("linux") and Path("/proc/mounts").exists():
                ignored = {
                    "proc", "sysfs", "devtmpfs", "tmpfs", "squashfs",
                    "cgroup", "cgroup2", "autofs", "devpts", "overlay"
                }
                for line in Path("/proc/mounts").read_text(errors="replace").splitlines():
                    fields = line.split()
                    if len(fields) >= 3 and fields[2] not in ignored:
                        volumes.append(Path(fields[1].replace("\\040", " ")))
        volumes.append(Path("/"))

    # Siempre incluir el disco donde se encuentra el directorio personal.
    home = Path.home()
    result = [home]
    result.extend(volumes)
    unique: list[Path] = []
    seen = set()
    for path in result:
        try:
            canonical = path.resolve(strict=True)
        except OSError:
            continue
        key = os.path.normcase(str(canonical))
        if key not in seen and canonical.is_dir():
            seen.add(key)
            unique.append(canonical)
    return unique


class PersistentStore:
    """Descubre o crea UN almacenamiento estable y recuerda su ubicacion."""

    def __init__(self, preferred_parent: Path | None = None):
        if os.name == "nt":
            config_base = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
        else:
            config_base = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config"))
        # Este archivo contiene solamente una referencia: los datos estan en el disco.
        self.pointer = config_base / "pyrionos" / "ubicacion.json"
        self.root = self._discover(preferred_parent)
        self._prepare()

    @staticmethod
    def _is_installation(path: Path) -> bool:
        if not path.is_dir() or path.is_symlink():
            return False
        marker = path / "config" / "instalacion.json"
        if not marker.is_file():
            return False
        try:
            data = read_json_strict(marker, {})
            return isinstance(data, dict) and data.get("producto") == "pyrionos"
        except StorageError:
            return False

    @staticmethod
    def _is_empty(path: Path) -> bool:
        return path.is_dir() and not any(path.iterdir())

    def _candidate_paths(self) -> list[Path]:
        result: list[Path] = []
        for volume in mounted_volumes():
            result.append(volume / DIR_NAME)
        result.append(Path.home() / DIR_NAME)
        # Duplicados preservando orden.
        return list(dict.fromkeys(result))

    def _discover(self, preferred_parent: Path | None) -> Path:
        # Ruta explicita util para instalar en un disco elegido por el usuario.
        env_dir = os.environ.get("PYRIONOS_DATA_DIR", "").strip()
        if env_dir and preferred_parent is None:
            preferred_parent = Path(env_dir).expanduser()

        if preferred_parent is not None:
            selected = Path(preferred_parent).expanduser().resolve()
            target = selected if selected.name.lower() == DIR_NAME else selected / DIR_NAME
            if target.is_symlink():
                raise StorageError("La ruta seleccionada es un enlace simbolico no permitido.")
            if target.exists() and not (self._is_installation(target) or self._is_empty(target)):
                raise StorageError(f"La carpeta ya contiene datos ajenos a PYRION: {target}")
            return target

        recorded = read_json_strict(self.pointer, {})
        recorded_path = recorded.get("ruta") if isinstance(recorded, dict) else None
        recorded_id = recorded.get("id") if isinstance(recorded, dict) else None
        if recorded_path:
            target = Path(recorded_path).expanduser()
            if self._is_installation(target):
                if recorded_id:
                    identity = read_json_strict(target / "config" / "instalacion.json", {})
                    if identity.get("id") != recorded_id:
                        raise StorageError("La carpeta encontrada no coincide con la instalacion anterior.")
                return target

        # Escanear todos los discos en cada arranque para encontrar un PYRION existente.
        candidates = self._candidate_paths()
        installations = [p for p in candidates if self._is_installation(p)]
        if recorded_id:
            for p in installations:
                meta = read_json_strict(p / "config" / "instalacion.json", {})
                if meta.get("id") == recorded_id:
                    return p
            raise StorageError(
                "No se encontro el disco que contiene tus datos de PYRION. "
                "Conecta el disco original y vuelve a iniciar, o selecciona "
                "manualmente una ubicacion. No se creara una instalacion vacia."
            )
        if recorded_path:
            raise StorageError(
                "No se encontro la carpeta persistente de PYRION. "
                "No se creara otra para evitar aparentar que se perdieron tus datos."
            )
        if installations:
            # Preferir la del disco personal, si existe.
            return installations[0]

        # Primer arranque: crear en el disco de usuario. En Windows probar la raiz
        # de la unidad fija personal; si no tenemos permisos, usar la carpeta HOME.
        preferred: list[Path] = []
        if os.name == "nt":
            preferred.append(Path(Path.home().anchor) / DIR_NAME)
        preferred.append(Path.home() / DIR_NAME)
        for path in preferred:
            if path.exists() and not self._is_empty(path):
                continue
            try:
                path.mkdir(parents=True, exist_ok=True)
                # Verificar escritura real en lugar de confiar solo en os.access().
                probe = path / (".escritura-" + uuid.uuid4().hex)
                probe.write_text("ok", encoding="utf-8")
                probe.unlink()
                return path
            except OSError:
                continue
        raise StorageError("No se encontro un disco local escribible para crear 'pyrionos'.")

    def _prepare(self) -> None:
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            for name in SUBFOLDERS:
                (self.root / name).mkdir(parents=True, exist_ok=True)
            marker = self.root / "config" / "instalacion.json"
            existing = read_json_strict(marker, {})
            if not existing:
                existing = {
                    "producto": "pyrionos",
                    "id": str(uuid.uuid4()),
                    "creado": datetime.now(timezone.utc).isoformat(),
                    "version_inicial": APP_VERSION,
                }
                write_json_atomic(marker, existing)
            if existing.get("producto") != "pyrionos":
                raise StorageError("La carpeta de datos no pertenece a PYRION.")
            self.installation_id = existing["id"]
            # Archivos vacios de datos: nunca reemplazar si ya existen.
            for filename in ("historial.json", "solicitudes.json"):
                path = self.root / "data" / filename
                if not path.exists():
                    write_json_atomic(path, [])
            if not (self.root / "config" / "preferencias.json").exists():
                write_json_atomic(self.root / "config" / "preferencias.json", {"tema": "oscuro"})
            write_json_atomic(self.pointer, {
                "ruta": str(self.root.resolve()),
                "id": self.installation_id,
            })
        except (OSError, KeyError) as exc:
            raise StorageError(f"No fue posible preparar el almacenamiento: {exc}") from exc

    def load_list(self, name: str) -> list:
        if name not in ("historial", "solicitudes"):
            raise ValueError("Nombre de coleccion no permitido")
        data = read_json_strict(self.root / "data" / f"{name}.json", [])
        if not isinstance(data, list):
            raise StorageError(f"El archivo {name}.json no contiene una lista valida.")
        return data

    def append(self, name: str, entry: dict) -> None:
        events = self.load_list(name)
        events.insert(0, entry)
        # Historial acotado para evitar crecer indefinidamente.
        write_json_atomic(self.root / "data" / f"{name}.json", events[:2000])

    def record(self, title: str, status: str) -> None:
        self.append("historial", {
            "fecha": datetime.now().astimezone().isoformat(timespec="seconds"),
            "accion": title,
            "estado": status,
        })

    def check(self) -> tuple[bool, str]:
        try:
            if not self._is_installation(self.root):
                return False, "No se reconoce la instalacion."
            for name in ("historial", "solicitudes"):
                self.load_list(name)
            probe = self.root / "cache" / (".prueba-" + uuid.uuid4().hex)
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return True, "Carpeta localizada, datos legibles y disco escribible."
        except (OSError, StorageError) as exc:
            return False, str(exc)


def normalized(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c))


def identify_tool(request: str) -> str | None:
    query = normalized(request)
    if "pdf" in query and ("word" in query or "docx" in query):
        return "pdf_word"
    if "pdf" in query and any(t in query for t in ("imagen", "foto", "jpg", "png")):
        return "image_pdf"
    if "csv" in query or "hoja de datos" in query:
        return "csv"
    if any(t in query for t in ("calculadora", "calcular", "operacion matematica")):
        return "calc"
    return None


# Solo el escritorio necesita PySide6. El almacenamiento anterior usa Python puro.
try:
    from PySide6.QtCore import Qt, QThread, QObject, Signal, Slot, QTimer, QUrl, QSize, QRectF
    from PySide6.QtGui import QColor, QDesktopServices, QFont, QPainter, QPdfWriter, QPageSize, QImage
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QDialog, QFrame, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QLineEdit, QTextEdit, QStackedWidget, QFileDialog,
        QMessageBox, QScrollArea, QGridLayout, QTableWidget, QTableWidgetItem,
        QHeaderView, QSizePolicy, QAbstractItemView,
    )
    QT_READY = True
except ImportError:
    QT_READY = False


if QT_READY:
    PALETTE = """
    QWidget { background-color: #0D1423; color: #EAF1FB; font-family: 'Segoe UI', 'Noto Sans', sans-serif; font-size: 13px; }
    QMainWindow, QWidget#DesktopRoot { background-color: #0B1220; }
    QFrame#TopBar { background-color: #101B2C; border-bottom: 1px solid #263B55; }
    QFrame#Sidebar { background-color: #0D182A; border-right: 1px solid #24344C; }
    QFrame#Panel, QFrame#ToolCard { background-color: #142238; border: 1px solid #2C4563; border-radius: 15px; }
    QFrame#Hero { background-color: #10243B; border: 1px solid #284F6C; border-radius: 20px; }
    QLabel#Brand { font-size: 19px; font-weight: 800; color: #66D8FA; letter-spacing: 2px; }
    QLabel#Title { font-size: 29px; font-weight: 750; color: #F0F7FF; }
    QLabel#SectionTitle { font-size: 21px; font-weight: 700; color: #F0F7FF; }
    QLabel#SmallTitle { font-size: 15px; font-weight: 700; color: #E9F4FF; }
    QLabel#Muted { color: #91A9C1; font-size: 12px; }
    QLabel#Tiny { color: #7892AE; font-size: 11px; }
    QLabel#Orb { background-color: #1D6096; color: #F4FCFF; border: 2px solid #4DCAFC; border-radius: 35px; font-size: 32px; font-weight: bold; }
    QLineEdit, QTextEdit { background-color: #192B43; border: 1px solid #405E80; border-radius: 10px; padding: 10px 12px; selection-background-color: #329EEA; }
    QLineEdit:focus, QTextEdit:focus { border: 1px solid #63C9F8; }
    QPushButton { color: #C8DDF1; background-color: #243A54; border: 1px solid #38526E; border-radius: 9px; padding: 9px 12px; }
    QPushButton:hover { background-color: #314F72; border-color: #6DBDFA; }
    QPushButton:pressed { background-color: #18314C; }
    QPushButton:disabled { color: #74849C; background-color: #152539; }
    QPushButton[role="primary"] { background-color: #3DADF5; color: #071A2B; border: none; font-weight: 750; }
    QPushButton[role="primary"]:hover { background-color: #77CEFF; }
    QPushButton[role="nav"] { background-color: transparent; border: none; text-align: left; padding: 12px 15px; color: #A5BDD6; }
    QPushButton[role="nav"]:hover { background-color: #1B304B; }
    QPushButton[role="selected"] { background-color: #244464; border: 1px solid #365E82; text-align: left; padding: 12px 15px; color: #E7F7FF; font-weight: bold; }
    QScrollArea { border: none; background: transparent; }
    QScrollBar:vertical { background: #101C2D; width: 9px; }
    QScrollBar::handle:vertical { background: #35516F; border-radius: 4px; }
    QTableWidget { background-color: #132238; gridline-color: #38506B; alternate-background-color: #1B3046; }
    QHeaderView::section { background-color: #284465; border: 1px solid #3B5773; padding: 6px; font-weight: bold; }
    """

    TOOLS = [
        ("pdf_word", "PDF a Word", "Convierte PDF en un documento DOCX.", "▤"),
        ("image_pdf", "Imágenes a PDF", "Combina imágenes en un PDF multipágina.", "▧"),
        ("csv", "Editor CSV", "Abre, modifica y guarda archivos CSV.", "▦"),
        ("calc", "Calculadora", "Operaciones matemáticas básicas.", "＋"),
    ]

    def label(text: str, style: str = "Muted", wrap: bool = False) -> QLabel:
        widget = QLabel(text)
        widget.setObjectName(style)
        widget.setWordWrap(wrap)
        return widget

    def button(text: str, callback=None, role: str | None = None) -> QPushButton:
        widget = QPushButton(text)
        if role:
            widget.setProperty("role", role)
        if callback:
            widget.clicked.connect(callback)
        widget.setCursor(Qt.CursorShape.PointingHandCursor)
        return widget

    def row(*widgets, spacing: int = 10) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(spacing)
        for child in widgets:
            if isinstance(child, (QHBoxLayout, QVBoxLayout)):
                layout.addLayout(child)
            else:
                layout.addWidget(child)
        return layout

    def clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
            elif item.layout():
                clear_layout(item.layout())

    class PdfWorker(QObject):
        finished = Signal(bool, str)

        def __init__(self, source: str, destination: str):
            super().__init__()
            self.source = source
            self.destination = destination

        @Slot()
        def run(self):
            try:
                from pdf2docx import Converter
            except ImportError:
                self.finished.emit(False, "Falta pdf2docx. Instálalo con: python -m pip install pdf2docx")
                return
            converter = None
            destination = Path(self.destination)
            temporary = destination.with_name(".pyrion-" + uuid.uuid4().hex + ".docx")
            try:
                destination.parent.mkdir(parents=True, exist_ok=True)
                converter = Converter(self.source)
                converter.convert(str(temporary))
                converter.close()
                converter = None
                os.replace(temporary, destination)
                self.finished.emit(True, f"Documento creado: {self.destination}")
            except Exception as exc:
                self.finished.emit(False, f"Error de conversión: {exc}")
            finally:
                if converter is not None:
                    try:
                        converter.close()
                    except Exception:
                        pass
                temporary.unlink(missing_ok=True)

    class PdfToWordDialog(QDialog):
        def __init__(self, store: PersistentStore, parent=None):
            super().__init__(parent)
            self.store = store
            self.setWindowTitle("PYRION · PDF a Word")
            self.resize(610, 275)
            self.worker_thread = None
            root = QVBoxLayout(self)
            root.setContentsMargins(22, 22, 22, 22)
            root.setSpacing(14)
            root.addWidget(label("Convertir PDF a Word", "SectionTitle"))
            root.addWidget(label("Selecciona un PDF y el destino DOCX. La conversión requiere pdf2docx.", wrap=True))
            self.source = QLineEdit()
            self.source.setPlaceholderText("Archivo PDF de origen")
            root.addLayout(row(self.source, button("Examinar", self.choose_source)))
            self.destination = QLineEdit()
            self.destination.setPlaceholderText("Archivo DOCX de destino")
            root.addLayout(row(self.destination, button("Guardar como", self.choose_destination)))
            self.message = label("Preparado para convertir.")
            root.addWidget(self.message)
            self.convert_btn = button("Convertir", self.convert, "primary")
            root.addWidget(self.convert_btn)

        def choose_source(self):
            file, _ = QFileDialog.getOpenFileName(self, "Seleccionar PDF", str(Path.home()), "PDF (*.pdf)")
            if file:
                self.source.setText(file)
                self.destination.setText(str(Path(file).with_suffix(".docx")))

        def choose_destination(self):
            suggestion = self.destination.text() or str(self.store.root / "downloads" / "convertido.docx")
            file, _ = QFileDialog.getSaveFileName(self, "Guardar DOCX", suggestion, "Word (*.docx)")
            if file:
                if not file.lower().endswith(".docx"):
                    file += ".docx"
                self.destination.setText(file)

        def convert(self):
            source = Path(self.source.text().strip())
            destination_text = self.destination.text().strip()
            if not source.is_file() or source.suffix.lower() != ".pdf":
                QMessageBox.warning(self, "PDF requerido", "Selecciona un archivo PDF válido.")
                return
            if not destination_text:
                QMessageBox.warning(self, "Destino requerido", "Selecciona dónde guardar el DOCX.")
                return
            destination = Path(destination_text)
            if source.resolve() == destination.resolve():
                QMessageBox.warning(self, "Ruta inválida", "El archivo de salida debe ser diferente.")
                return
            if destination.exists() and QMessageBox.question(
                self, "Sobrescribir archivo", "El DOCX ya existe. ¿Deseas reemplazarlo?"
            ) != QMessageBox.StandardButton.Yes:
                return
            self.convert_btn.setEnabled(False)
            self.message.setText("Convirtiendo... el tiempo depende del tamaño del PDF.")
            self.worker_thread = QThread(self)
            worker = PdfWorker(str(source), str(destination))
            self.worker = worker
            worker.moveToThread(self.worker_thread)
            self.worker_thread.started.connect(worker.run)
            worker.finished.connect(self.worker_thread.quit)
            worker.finished.connect(self.conversion_finished)
            worker.finished.connect(worker.deleteLater)
            self.worker_thread.finished.connect(self._worker_cleanup)
            self.worker_thread.finished.connect(self.worker_thread.deleteLater)
            self.worker_thread.start()

        def _worker_cleanup(self):
            self.worker_thread = None
            self.worker = None

        def conversion_finished(self, success: bool, message: str):
            self.convert_btn.setEnabled(True)
            self.message.setText(message)
            self.store.record("PDF a Word", "completado" if success else "error")
            if success:
                QMessageBox.information(self, "Conversión realizada", message)
            else:
                QMessageBox.warning(self, "No se pudo convertir", message)

        def reject(self):
            if self.worker_thread and self.worker_thread.isRunning():
                QMessageBox.information(self, "Conversión en curso", "Deja finalizar la conversión antes de cerrar.")
                return
            super().reject()

    class ImagesToPdfDialog(QDialog):
        def __init__(self, store: PersistentStore, parent=None):
            super().__init__(parent)
            self.store = store
            self.images: list[str] = []
            self.setWindowTitle("PYRION · Imágenes a PDF")
            self.resize(600, 310)
            root = QVBoxLayout(self)
            root.setContentsMargins(22, 22, 22, 22)
            root.setSpacing(13)
            root.addWidget(label("Imágenes a PDF", "SectionTitle"))
            root.addWidget(label("Las imágenes se colocan en páginas A4, en el orden seleccionado.", wrap=True))
            self.selected = label("Ninguna imagen seleccionada.", wrap=True)
            root.addWidget(self.selected)
            root.addWidget(button("Seleccionar imágenes", self.choose_images))
            self.destination = QLineEdit(str(store.root / "downloads" / "imagenes.pdf"))
            root.addLayout(row(self.destination, button("Guardar como", self.choose_destination)))
            root.addStretch()
            root.addWidget(button("Crear PDF", self.convert, "primary"))

        def choose_images(self):
            items, _ = QFileDialog.getOpenFileNames(
                self, "Seleccionar imágenes", str(Path.home()),
                "Imágenes (*.png *.jpg *.jpeg *.bmp *.webp)"
            )
            if items:
                self.images = items
                self.selected.setText(f"{len(items)} imagen(es): " + ", ".join(Path(x).name for x in items[:4]))

        def choose_destination(self):
            file, _ = QFileDialog.getSaveFileName(self, "Guardar PDF", self.destination.text(), "PDF (*.pdf)")
            if file:
                self.destination.setText(file if file.lower().endswith(".pdf") else file + ".pdf")

        def convert(self):
            if not self.images:
                QMessageBox.warning(self, "Sin imágenes", "Selecciona al menos una imagen.")
                return
            dest = Path(self.destination.text().strip())
            if dest.suffix.lower() != ".pdf":
                QMessageBox.warning(self, "Destino inválido", "El destino debe terminar en .pdf")
                return
            pictures = [QImage(f) for f in self.images]
            if any(im.isNull() for im in pictures):
                QMessageBox.warning(self, "Imagen inválida", "No se pudo abrir alguna de las imágenes.")
                return
            if dest.exists() and QMessageBox.question(
                self, "Sobrescribir", "El PDF ya existe. ¿Deseas reemplazarlo?"
            ) != QMessageBox.StandardButton.Yes:
                return
            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                # Usar un PDF temporal evita sobrescribir el anterior si algo falla.
                tmp = dest.with_name(".pyrion-" + uuid.uuid4().hex + ".pdf")
                try:
                    pdf = QPdfWriter(str(tmp))
                    pdf.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
                    pdf.setResolution(150)
                    painter = QPainter(pdf)
                    if not painter.isActive():
                        raise OSError("No se pudo crear el PDF.")
                    try:
                        for index, picture in enumerate(pictures):
                            if index:
                                pdf.newPage()
                            page = QRectF(painter.viewport())
                            margin = 40.0
                            usable_w = page.width() - 2 * margin
                            usable_h = page.height() - 2 * margin
                            ratio = min(usable_w / picture.width(), usable_h / picture.height())
                            w, h = picture.width() * ratio, picture.height() * ratio
                            target = QRectF((page.width() - w) / 2, (page.height() - h) / 2, w, h)
                            painter.drawImage(target, picture)
                    finally:
                        painter.end()
                    os.replace(tmp, dest)
                finally:
                    tmp.unlink(missing_ok=True)
                self.store.record("Imágenes a PDF", "completado")
                QMessageBox.information(self, "PDF creado", f"Archivo creado:\n{dest}")
            except (OSError, ValueError) as exc:
                self.store.record("Imágenes a PDF", "error")
                QMessageBox.critical(self, "Error", str(exc))

    class CsvEditorDialog(QDialog):
        def __init__(self, store: PersistentStore, parent=None):
            super().__init__(parent)
            self.store = store
            self.current: Path | None = None
            self.delimiter = ";"
            self.setWindowTitle("PYRION · Editor CSV")
            self.resize(800, 550)
            root = QVBoxLayout(self)
            root.setContentsMargins(16, 16, 16, 16)
            root.addWidget(label("Editor de archivos CSV", "SectionTitle"))
            root.addLayout(row(
                button("Abrir CSV", self.open_csv),
                button("Guardar", self.save_csv),
                button("Guardar como", lambda: self.save_csv(True)),
                button("+ Fila", self.add_row),
                button("+ Columna", self.add_column),
            ))
            self.table = QTableWidget(0, 3)
            self.table.setAlternatingRowColors(True)
            self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            self.table.setHorizontalHeaderLabels(["Columna 1", "Columna 2", "Columna 3"])
            root.addWidget(self.table)
            self.note = label("Separador inicial: ; · Los cambios se guardan solo al pulsar Guardar.")
            root.addWidget(self.note)

        def add_row(self):
            self.table.insertRow(self.table.rowCount())

        def add_column(self):
            col = self.table.columnCount()
            self.table.insertColumn(col)
            self.table.setHorizontalHeaderItem(col, QTableWidgetItem(f"Columna {col + 1}"))

        def open_csv(self):
            file, _ = QFileDialog.getOpenFileName(self, "Abrir CSV", str(Path.home()), "CSV (*.csv);;Todos (*)")
            if not file:
                return
            try:
                with open(file, "r", encoding="utf-8-sig", newline="") as handle:
                    sample = handle.read(4096)
                    handle.seek(0)
                    try:
                        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t|")
                        delimiter = dialect.delimiter
                    except csv.Error:
                        delimiter = ";"
                    records = list(csv.reader(handle, delimiter=delimiter))
                if len(records) > 5000:
                    QMessageBox.warning(self, "Archivo grande", "Esta versión admite hasta 5000 filas para evitar bloquear la interfaz.")
                    return
                columns = max([len(r) for r in records] + [1])
                if columns > 100:
                    QMessageBox.warning(self, "Demasiadas columnas", "Esta versión admite hasta 100 columnas.")
                    return
                self.table.setRowCount(len(records))
                self.table.setColumnCount(columns)
                self.table.setHorizontalHeaderLabels([f"Columna {i+1}" for i in range(columns)])
                for r, record in enumerate(records):
                    for c, value in enumerate(record):
                        self.table.setItem(r, c, QTableWidgetItem(value))
                self.current = Path(file)
                self.delimiter = delimiter
                self.note.setText(f"Abierto: {file} · {len(records)} filas · separador: {repr(delimiter)}")
                self.store.record("Abrir CSV", "completado")
            except (OSError, UnicodeError, csv.Error) as exc:
                QMessageBox.critical(self, "Error CSV", str(exc))

        def save_csv(self, save_as=False):
            destination = self.current
            if destination is None or save_as:
                default = str(destination or (self.store.root / "downloads" / "tabla.csv"))
                file, _ = QFileDialog.getSaveFileName(self, "Guardar CSV", default, "CSV (*.csv)")
                if not file:
                    return
                destination = Path(file if file.lower().endswith(".csv") else file + ".csv")
            if destination.exists() and (save_as or self.current != destination):
                if QMessageBox.question(self, "Sobrescribir", "El archivo ya existe. ¿Reemplazarlo?") != QMessageBox.StandardButton.Yes:
                    return
            try:
                destination.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8-sig", newline="", dir=destination.parent,
                    prefix=".pyrion-csv-", suffix=".tmp", delete=False
                ) as handle:
                    tmp = Path(handle.name)
                    writer = csv.writer(handle, delimiter=self.delimiter)
                    for r in range(self.table.rowCount()):
                        writer.writerow([
                            self.table.item(r, c).text() if self.table.item(r, c) else ""
                            for c in range(self.table.columnCount())
                        ])
                try:
                    os.replace(tmp, destination)
                finally:
                    tmp.unlink(missing_ok=True)
                self.current = destination
                self.note.setText(f"Guardado: {destination}")
                self.store.record("Guardar CSV", "completado")
            except OSError as exc:
                QMessageBox.critical(self, "Error al guardar", str(exc))

    def safe_calculate(expression: str) -> float:
        allowed = {
            ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b,
            ast.Mult: lambda a, b: a * b, ast.Div: lambda a, b: a / b,
            ast.Mod: lambda a, b: a % b, ast.Pow: lambda a, b: a ** b,
            ast.USub: lambda x: -x, ast.UAdd: lambda x: x,
        }
        def evaluate(node, depth=0):
            if depth > 20:
                raise ValueError("Operación demasiado compleja")
            if isinstance(node, ast.Expression):
                return evaluate(node.body, depth + 1)
            if isinstance(node, ast.Constant) and type(node.value) in (int, float):
                if abs(node.value) > 1e12:
                    raise ValueError("Número demasiado grande")
                return node.value
            if isinstance(node, ast.UnaryOp) and type(node.op) in allowed:
                return allowed[type(node.op)](evaluate(node.operand, depth + 1))
            if isinstance(node, ast.BinOp) and type(node.op) in allowed:
                a = evaluate(node.left, depth + 1)
                b = evaluate(node.right, depth + 1)
                if isinstance(node.op, ast.Pow) and (abs(b) > 12 or abs(a) > 1e6):
                    raise ValueError("Potencia demasiado grande")
                result = allowed[type(node.op)](a, b)
                if isinstance(result, complex) or abs(result) > 1e15:
                    raise ValueError("Resultado fuera de rango")
                return result
            raise ValueError("Expresión no permitida")
        if len(expression) > 120:
            raise ValueError("Expresión demasiado larga")
        return evaluate(ast.parse(expression, mode="eval"))

    class CalculatorDialog(QDialog):
        def __init__(self, store: PersistentStore, parent=None):
            super().__init__(parent)
            self.store = store
            self.setWindowTitle("PYRION · Calculadora")
            self.resize(380, 385)
            root = QVBoxLayout(self)
            root.setContentsMargins(20, 20, 20, 20)
            root.addWidget(label("Calculadora", "SectionTitle"))
            self.display = QLineEdit()
            self.display.setPlaceholderText("2 + 2 * 3")
            self.display.returnPressed.connect(self.solve)
            root.addWidget(self.display)
            grid = QGridLayout()
            matrix = ["7", "8", "9", "/", "4", "5", "6", "*", "1", "2", "3", "-", "C", "0", ".", "+", "(", ")", "**", "="]
            for i, value in enumerate(matrix):
                control = button(value, lambda checked=False, key=value: self.press(key), "primary" if value == "=" else None)
                grid.addWidget(control, i // 4, i % 4)
            root.addLayout(grid)

        def press(self, key):
            if key == "C":
                self.display.clear()
            elif key == "=":
                self.solve()
            else:
                self.display.insert(key)

        def solve(self):
            try:
                result = safe_calculate(self.display.text())
                self.display.setText(str(result))
                self.store.record("Calculadora", "completado")
            except (SyntaxError, ValueError, ZeroDivisionError, OverflowError) as exc:
                QMessageBox.warning(self, "Operación inválida", str(exc))

    class PyrionDesktop(QMainWindow):
        def __init__(self, store: PersistentStore):
            super().__init__()
            self.store = store
            self.setWindowTitle(f"{APP_NAME} | Desktop {APP_VERSION}")
            self.resize(1180, 740)
            self.setMinimumSize(850, 590)
            self.setStyleSheet(PALETTE)
            self.nav = {}
            self.pages = {}
            self.main_root = QWidget()
            self.main_root.setObjectName("DesktopRoot")
            self.setCentralWidget(self.main_root)
            shell = QVBoxLayout(self.main_root)
            shell.setContentsMargins(0, 0, 0, 0)
            shell.setSpacing(0)
            self._build_topbar(shell)
            body = QHBoxLayout()
            body.setSpacing(0)
            shell.addLayout(body, 1)
            self._build_sidebar(body)
            self.stack = QStackedWidget()
            body.addWidget(self.stack, 1)
            self._build_home()
            self._build_tools()
            self._build_history()
            self._build_files()
            self._build_settings()
            self.goto("home")
            self.clock_timer = QTimer(self)
            self.clock_timer.timeout.connect(self._update_clock)
            self.clock_timer.start(30_000)
            self._update_clock()

        def _build_topbar(self, shell):
            top = QFrame()
            top.setObjectName("TopBar")
            top.setFixedHeight(63)
            layout = QHBoxLayout(top)
            layout.setContentsMargins(23, 0, 23, 0)
            layout.addWidget(label("◈  PYRION", "Brand"))
            layout.addWidget(label("OS  /  PYTHON DESKTOP", "Tiny"))
            layout.addStretch()
            self.disk_indicator = label("● Datos persistentes", "Muted")
            self.disk_indicator.setStyleSheet("color: #69D9AC")
            self.disk_indicator.setToolTip(str(self.store.root))
            layout.addWidget(self.disk_indicator)
            layout.addSpacing(25)
            self.clock = label("", "Muted")
            layout.addWidget(self.clock)
            shell.addWidget(top)

        def _update_clock(self):
            self.clock.setText(datetime.now().strftime("%d/%m/%Y   %H:%M"))

        def _build_sidebar(self, body):
            side = QFrame()
            side.setObjectName("Sidebar")
            side.setFixedWidth(228)
            layout = QVBoxLayout(side)
            layout.setContentsMargins(15, 23, 15, 18)
            layout.setSpacing(7)
            layout.addWidget(label("ESPACIO DE TRABAJO", "Tiny"))
            items = [
                ("home", "⌂   Inicio"),
                ("tools", "▦   Mis herramientas"),
                ("history", "◷   Historial"),
                ("files", "▤   Archivos"),
            ]
            for key, text in items:
                b = button(text, lambda checked=False, page=key: self.goto(page), "nav")
                self.nav[key] = b
                layout.addWidget(b)
            layout.addSpacing(12)
            layout.addWidget(label("SISTEMA", "Tiny"))
            b = button("⚙   Configuración", lambda: self.goto("settings"), "nav")
            self.nav["settings"] = b
            layout.addWidget(b)
            layout.addStretch()
            disk_card = QFrame()
            disk_card.setObjectName("Panel")
            card_lay = QVBoxLayout(disk_card)
            card_lay.setContentsMargins(12, 12, 12, 12)
            card_lay.addWidget(label("●  ALMACENAMIENTO", "Tiny"))
            location = label(str(self.store.root), "Muted", wrap=True)
            location.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            card_lay.addWidget(location)
            card_lay.addWidget(label("Python Engine · v" + APP_VERSION, "Tiny"))
            layout.addWidget(disk_card)
            body.addWidget(side)

        def _base_page(self) -> tuple[QWidget, QVBoxLayout]:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            page = QWidget()
            outer = QVBoxLayout(page)
            outer.setContentsMargins(31, 24, 31, 31)
            outer.setSpacing(18)
            scroll.setWidget(page)
            self.stack.addWidget(scroll)
            return scroll, outer

        def _build_home(self):
            page, outer = self._base_page()
            self.pages["home"] = page
            hero = QFrame()
            hero.setObjectName("Hero")
            layout = QVBoxLayout(hero)
            layout.setSpacing(11)
            layout.setContentsMargins(26, 30, 26, 27)
            layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            orb = label("✧", "Orb")
            orb.setFixedSize(70, 70)
            orb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(orb, 0, Qt.AlignmentFlag.AlignHCenter)
            title = label("¿Qué quieres hacer hoy?", "Title")
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(title)
            subtitle = label(
                "Describe tu tarea. PYRION abrirá una herramienta existente o guardará tu solicitud para el futuro motor de IA.",
                "Muted", wrap=True
            )
            subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
            subtitle.setMaximumWidth(600)
            layout.addWidget(subtitle)
            search_row = QHBoxLayout()
            self.search_box = QLineEdit()
            self.search_box.setMinimumHeight(47)
            self.search_box.setPlaceholderText("Ej.: PDF a Word, editar CSV, calculadora...")
            self.search_box.returnPressed.connect(self.search)
            search_row.addWidget(self.search_box, 1)
            search_row.addWidget(button("Ejecutar  ↗", self.search, "primary"))
            layout.addLayout(search_row)
            chips = QHBoxLayout()
            chips.addStretch()
            for text in ("PDF a Word", "Imágenes a PDF", "Editor CSV", "Calculadora"):
                chips.addWidget(button(text, lambda checked=False, value=text: self.select_example(value)))
            chips.addStretch()
            layout.addLayout(chips)
            outer.addWidget(hero)
            panel = QFrame()
            panel.setObjectName("Panel")
            panel_lay = QVBoxLayout(panel)
            panel_lay.setContentsMargins(21, 18, 21, 18)
            panel_lay.setSpacing(8)
            panel_lay.addWidget(label("CENTRO DE EJECUCIÓN", "Tiny"))
            self.result_title = label("Sistema listo", "SmallTitle")
            panel_lay.addWidget(self.result_title)
            self.result_desc = label(
                "El escritorio está funcionando. Las herramientas incluidas se pueden abrir ahora. "
                "La creación automática de nuevas aplicaciones mediante IA todavía no está implementada.",
                "Muted", wrap=True
            )
            panel_lay.addWidget(self.result_desc)
            self.result_actions = QHBoxLayout()
            panel_lay.addLayout(self.result_actions)
            outer.addWidget(panel)
            outer.addWidget(label("HERRAMIENTAS DISPONIBLES", "Tiny"))
            grid = QGridLayout()
            grid.setSpacing(13)
            for index, (key, name, desc, symbol) in enumerate(TOOLS):
                card = QFrame()
                card.setObjectName("ToolCard")
                lay = QVBoxLayout(card)
                lay.setContentsMargins(15, 13, 15, 13)
                lay.addWidget(label(f"{symbol}   {name}", "SmallTitle"))
                lay.addWidget(label(desc, "Muted", wrap=True))
                lay.addWidget(button("Abrir", lambda checked=False, tool=key: self.launch(tool)))
                grid.addWidget(card, index // 2, index % 2)
            outer.addLayout(grid)
            outer.addStretch()

        def _build_tools(self):
            page, outer = self._base_page()
            self.pages["tools"] = page
            outer.addWidget(label("Mis herramientas", "SectionTitle"))
            outer.addWidget(label("Estas aplicaciones están incorporadas; no necesitan un generador de IA.", "Muted"))
            for key, name, desc, symbol in TOOLS:
                card = QFrame()
                card.setObjectName("ToolCard")
                lay = QHBoxLayout(card)
                lay.setContentsMargins(20, 18, 20, 18)
                t = QVBoxLayout()
                t.addWidget(label(f"{symbol}   {name}", "SmallTitle"))
                t.addWidget(label(desc, "Muted", wrap=True))
                lay.addLayout(t, 1)
                lay.addWidget(button("Abrir", lambda checked=False, tool=key: self.launch(tool), "primary"))
                outer.addWidget(card)
            outer.addStretch()

        def _build_history(self):
            page, outer = self._base_page()
            self.pages["history"] = page
            outer.addWidget(label("Historial", "SectionTitle"))
            outer.addWidget(label("Acciones registradas en el disco persistente.", "Muted"))
            self.history_list = QVBoxLayout()
            self.history_list.setSpacing(10)
            outer.addLayout(self.history_list)
            outer.addStretch()

        def _build_files(self):
            page, outer = self._base_page()
            self.pages["files"] = page
            outer.addWidget(label("Explorador de archivos", "SectionTitle"))
            pane = QFrame()
            pane.setObjectName("Panel")
            lay = QVBoxLayout(pane)
            lay.setContentsMargins(24, 28, 24, 28)
            lay.addWidget(label("▤   Módulo reservado", "SmallTitle"))
            lay.addWidget(label(
                "El botón Archivos ya forma parte del escritorio, pero el explorador "
                "y sus operaciones se desarrollarán en una siguiente versión.",
                "Muted", wrap=True
            ))
            outer.addWidget(pane)
            outer.addStretch()

        def _build_settings(self):
            page, outer = self._base_page()
            self.pages["settings"] = page
            outer.addWidget(label("Configuración", "SectionTitle"))
            outer.addWidget(label("Datos persistentes y estado de la instalación.", "Muted"))
            pane = QFrame()
            pane.setObjectName("Panel")
            lay = QVBoxLayout(pane)
            lay.setContentsMargins(22, 22, 22, 22)
            lay.setSpacing(13)
            lay.addWidget(label("Carpeta de datos", "SmallTitle"))
            self.path_label = label(str(self.store.root), "Muted", wrap=True)
            self.path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            lay.addWidget(self.path_label)
            lay.addWidget(label(f"Identificador: {self.store.installation_id}", "Tiny"))
            try:
                space = shutil.disk_usage(self.store.root)
                lay.addWidget(label(f"Espacio libre del disco: {space.free / 1024**3:.2f} GB", "Muted"))
            except OSError:
                lay.addWidget(label("No se pudo consultar el espacio disponible.", "Muted"))
            lay.addLayout(row(
                button("Abrir carpeta de datos", self.open_data_folder),
                button("Verificar almacenamiento", self.test_storage),
            ))
            outer.addWidget(pane)
            note = QFrame()
            note.setObjectName("Panel")
            note_lay = QVBoxLayout(note)
            note_lay.setContentsMargins(22, 18, 22, 18)
            note_lay.addWidget(label("Modelo de inteligencia artificial", "SmallTitle"))
            note_lay.addWidget(label(
                "Aún no conectado. PYRION puede abrir herramientas incorporadas "
                "y almacenar solicitudes pendientes; no genera ni ejecuta código desconocido.",
                "Muted", wrap=True
            ))
            outer.addWidget(note)
            outer.addStretch()

        def goto(self, key: str):
            self.stack.setCurrentWidget(self.pages[key])
            for name, widget in self.nav.items():
                widget.setProperty("role", "selected" if name == key else "nav")
                widget.style().unpolish(widget)
                widget.style().polish(widget)
            if key == "history":
                self.refresh_history()

        def select_example(self, text: str):
            self.search_box.setText(text)
            self.search()

        def _result(self, title: str, explanation: str, action=None, action_text="Abrir"):
            self.result_title.setText(title)
            self.result_desc.setText(explanation)
            clear_layout(self.result_actions)
            if action:
                self.result_actions.addWidget(button(action_text, action, "primary"))
            self.result_actions.addStretch()

        def search(self):
            query = self.search_box.text().strip()
            if not query:
                self._result("Escribe una tarea", "Indica lo que necesitas hacer.")
                return
            tool_id = identify_tool(query)
            if tool_id:
                name = next(name for key, name, _, _ in TOOLS if key == tool_id)
                self.store.record(f"Buscar: {query}", "herramienta encontrada")
                self._result(
                    f"Herramienta disponible: {name}",
                    "Esta función ya existe en el escritorio y puede utilizarse ahora.",
                    lambda: self.launch(tool_id), "Abrir herramienta"
                )
                self.launch(tool_id)
            else:
                try:
                    self.store.append("solicitudes", {
                        "fecha": datetime.now().astimezone().isoformat(timespec="seconds"),
                        "solicitud": query,
                        "estado": "pendiente_ia",
                    })
                    self.store.record(f"Solicitar: {query}", "pendiente de IA")
                except (OSError, StorageError) as exc:
                    QMessageBox.critical(self, "No se pudo guardar", str(exc))
                    return
                self._result(
                    "Solicitud guardada", f"«{query}» se ha guardado en el disco. "
                    "Todavía no hay un modelo de IA conectado, así que no se ha generado "
                    "ni ejecutado ninguna aplicación.",
                    lambda: self.goto("history"), "Ver historial"
                )

        def launch(self, tool_id: str):
            types = {
                "pdf_word": PdfToWordDialog,
                "image_pdf": ImagesToPdfDialog,
                "csv": CsvEditorDialog,
                "calc": CalculatorDialog,
            }
            dialog_type = types.get(tool_id)
            if dialog_type is None:
                QMessageBox.warning(self, "Herramienta no disponible", "No existe esta herramienta.")
                return
            try:
                self.store.record(f"Abrir: {tool_id}", "iniciado")
            except (StorageError, OSError) as exc:
                QMessageBox.warning(self, "Aviso de almacenamiento", str(exc))
            dialog = dialog_type(self.store, self)
            dialog.setStyleSheet(PALETTE)
            dialog.exec()

        def refresh_history(self):
            clear_layout(self.history_list)
            try:
                entries = self.store.load_list("historial")
            except StorageError as exc:
                self.history_list.addWidget(label(f"Error: {exc}", "Muted"))
                return
            if not entries:
                self.history_list.addWidget(label("Todavía no hay actividades registradas.", "Muted"))
                return
            for entry in entries[:70]:
                card = QFrame()
                card.setObjectName("ToolCard")
                lay = QHBoxLayout(card)
                lay.setContentsMargins(15, 12, 15, 12)
                text = QVBoxLayout()
                text.addWidget(label(str(entry.get("accion", "Actividad")), "SmallTitle", wrap=True))
                text.addWidget(label(str(entry.get("fecha", "")), "Tiny"))
                lay.addLayout(text, 1)
                lay.addWidget(label(str(entry.get("estado", "")), "Muted"))
                self.history_list.addWidget(card)

        def open_data_folder(self):
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.store.root))):
                QMessageBox.warning(self, "No se pudo abrir", str(self.store.root))

        def test_storage(self):
            ok, result = self.store.check()
            if ok:
                QMessageBox.information(self, "Almacenamiento correcto", result)
            else:
                QMessageBox.critical(self, "Problema de almacenamiento", result)


def main() -> int:
    if not QT_READY:
        print("PYRION OS necesita PySide6.\nInstala con: python -m pip install PySide6", file=sys.stderr)
        return 2
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    try:
        storage = PersistentStore()
    except StorageError as exc:
        QMessageBox.warning(
            None, "PYRION · almacenamiento no disponible",
            f"{exc}\n\nPuedes seleccionar una carpeta o disco para los datos de PYRION. "
            "Si los datos estaban en un disco desconectado, es preferible reconectarlo y reiniciar.",
        )
        selected = QFileDialog.getExistingDirectory(None, "Seleccionar disco o carpeta para pyrionos", str(Path.home()))
        if not selected:
            return 1
        try:
            storage = PersistentStore(preferred_parent=Path(selected))
        except StorageError as second_exc:
            QMessageBox.critical(None, "No fue posible iniciar PYRION", str(second_exc))
            return 1
    window = PyrionDesktop(storage)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
