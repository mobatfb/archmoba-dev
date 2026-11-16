# -*- coding: utf-8 -*-
"""
KOFMULTI - CONTROL v.0.0.1
Ventana fija de 520 x 240. Usa los SVG de ./assets.
Este primer prototipo es LOCAL: todavia no se conecta al anfitrion.
No crea cache, archivos de configuracion ni registros en disco.
Instalacion de interfaz: py -m pip install --no-cache-dir PySide6
"""
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import (
    QColor, QFont, QLinearGradient, QPainter, QPen
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QWidget, QPushButton

VERSION = "v.0.0.1"
WINDOW_WIDTH = 520
WINDOW_HEIGHT = 240
ASSETS = Path(__file__).resolve().parent / "assets"

# Teclado identico para todos, independientemente de P1/P2.
KEYS = {
    Qt.Key_Up: "UP",
    Qt.Key_Down: "DOWN",
    Qt.Key_Left: "LEFT",
    Qt.Key_Right: "RIGHT",
    Qt.Key_A: "A",
    Qt.Key_S: "S",
    Qt.Key_Z: "Z",
    Qt.Key_X: "X",
    Qt.Key_Return: "START",
    Qt.Key_Enter: "START",
    Qt.Key_5: "COIN",
}


class ControlButton(QWidget):
    """Boton SVG transparente; emite pulsar/soltar y no guarda archivos."""

    def __init__(self, parent, action, filename, fallback, x, y, w, h):
        super().__init__(parent)
        self.action = action
        self.fallback = fallback
        self.is_down = False
        self.renderer = QSvgRenderer(str(ASSETS / filename), self)
        self.setGeometry(x, y, w, h)
        self.setFocusPolicy(Qt.NoFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def set_pressed(self, down):
        if self.is_down == down:
            return
        self.is_down = down
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.parent().action_event(self.action, True, "tactil")
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.parent().action_event(self.action, False, "tactil")
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def leaveEvent(self, event):
        # Evita dejar un boton mantenido si el puntero sale de el.
        if self.is_down:
            self.parent().action_event(self.action, False, "tactil")
        super().leaveEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(0, 0, self.width(), self.height())
        if self.renderer.isValid():
            self.renderer.render(p, rect)
        else:
            # La ventana tambien abre si se descargo solamente el .py.
            grad = QLinearGradient(0, 0, 0, self.height())
            grad.setColorAt(0, QColor("#283c58"))
            grad.setColorAt(1, QColor("#081325"))
            p.setBrush(grad)
            p.setPen(QPen(QColor("#25b7ff"), 1.5))
            p.drawRoundedRect(rect.adjusted(2, 2, -2, -2), 8, 8)
            p.setPen(QColor("#eefaff"))
            p.setFont(QFont("Arial", max(9, self.height() // 3), QFont.Bold))
            p.drawText(rect, Qt.AlignCenter, self.fallback)
        if self.is_down:
            p.setBrush(QColor(0, 221, 255, 60))
            p.setPen(QPen(QColor("#86f4ff"), 2))
            p.drawRoundedRect(rect.adjusted(1.5, 1.5, -1.5, -1.5), 8, 8)
        p.end()


class KofControl(QWidget):
    """Solo interfaz y diagnostico local. Sin red ni persistencia."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("KOFMULTI CONTROL " + VERSION)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setFocusPolicy(Qt.StrongFocus)
        self.drag_origin = None
        self.buttons = {}
        self.held = set()
        self.events = [
            ("[SISTEMA] Control iniciado.", "#9df9ad"),
            ("[ESTADO] Modo local, sin servidor.", "#a1bbd2"),
            ("[LISTO] Prueba flechas, ASZX y START.", "#8de9fa"),
        ]

        # Barra propia para conservar exactamente 520 x 240 pixeles.
        self.min_button = QPushButton("–", self)
        self.min_button.setGeometry(470, 3, 19, 19)
        self.min_button.setFocusPolicy(Qt.NoFocus)
        self.min_button.setCursor(Qt.PointingHandCursor)
        self.min_button.clicked.connect(self.showMinimized)
        self.close_button = QPushButton("×", self)
        self.close_button.setGeometry(492, 3, 19, 19)
        self.close_button.setFocusPolicy(Qt.NoFocus)
        self.close_button.setCursor(Qt.PointingHandCursor)
        self.close_button.clicked.connect(self.close)
        for button in (self.min_button, self.close_button):
            button.setStyleSheet(
                "QPushButton {background:#132337;color:#95d9ff;border:1px solid #2c5778;"
                "border-radius:5px;font-weight:bold;padding:0}"
                "QPushButton:hover {background:#205075;color:white}"
            )

        # Cruceta: cinco piezas independientes (el centro es decorativo).
        self.add_button("UP", "dpad_up.svg", "↑", 72, 124, 34, 34)
        self.add_button("LEFT", "dpad_left.svg", "←", 38, 158, 34, 34)
        self.add_button("RIGHT", "dpad_right.svg", "→", 106, 158, 34, 34)
        self.add_button("DOWN", "dpad_down.svg", "↓", 72, 192, 34, 34)

        # Centro de cruceta sin evento ni accion.
        center = ControlButton(self, "", "dpad_center.svg", "•", 72, 158, 34, 34)
        center.setCursor(Qt.ArrowCursor)
        center.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self.add_button("START", "btn_start.svg", "START", 205, 164, 115, 38)

        # Bloque solicitado: A S / Z X.
        self.add_button("A", "btn_a.svg", "A", 404, 128, 43, 43)
        self.add_button("S", "btn_s.svg", "S", 451, 128, 43, 43)
        self.add_button("Z", "btn_z.svg", "Z", 404, 175, 43, 43)
        self.add_button("X", "btn_x.svg", "X", 451, 175, 43, 43)

        self.setFocus()

    def add_button(self, action, filename, label, x, y, w, h):
        button = ControlButton(self, action, filename, label, x, y, w, h)
        self.buttons[action] = button

    def action_event(self, action, down, source):
        if not action:
            return
        was_down = action in self.held
        if down and not was_down:
            self.held.add(action)
            self.events.append((f"[INPUT] {action} pulsado ({source})", "#61e9ff"))
            self.events = self.events[-3:]
        elif not down and was_down:
            self.held.remove(action)
        for name, button in self.buttons.items():
            if name == action:
                button.set_pressed(action in self.held)
        self.update()
        # En versiones futuras aqui se enviaran las acciones al anfitrion.
        # Esta version no hace peticiones HTTP ni abre WebSockets.

    def keyPressEvent(self, event):
        action = KEYS.get(event.key())
        if action:
            if not event.isAutoRepeat():
                self.action_event(action, True, "teclado")
            event.accept()
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        action = KEYS.get(event.key())
        if action:
            if not event.isAutoRepeat():
                self.action_event(action, False, "teclado")
            event.accept()
        else:
            super().keyReleaseEvent(event)

    def focusOutEvent(self, event):
        # Liberar todo al perder foco: no deben quedarse botones activos.
        for action in tuple(self.held):
            self.action_event(action, False, "sistema")
        super().focusOutEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.position().y() <= 25:
            self.drag_origin = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drag_origin is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_origin)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.drag_origin = None
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        gradient = QLinearGradient(0, 0, 0, WINDOW_HEIGHT)
        gradient.setColorAt(0, QColor("#121e31"))
        gradient.setColorAt(1, QColor("#060c18"))
        p.fillRect(self.rect(), gradient)

        p.setBrush(QColor("#10223a"))
        p.setPen(QPen(QColor("#2499ef"), 1))
        p.drawRoundedRect(QRectF(1, 1, 518, 238), 9, 9)
        p.setBrush(QColor("#0a1426"))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(4, 4, 512, 22), 6, 6)
        p.setFont(QFont("Arial", 9, QFont.Bold))
        p.setPen(QColor("#57daff"))
        p.drawText(14, 19, "KOFMULTI")
        p.setFont(QFont("Arial", 8))
        p.setPen(QColor("#93a8c1"))
        p.drawText(119, 19, "CONTROL REMOTO")
        p.setPen(QColor("#59e8ff"))
        p.drawText(296, 19, VERSION)

        # Consola: la version es SIEMPRE el primer mensaje visible.
        p.setBrush(QColor("#050c17"))
        p.setPen(QPen(QColor("#185a91"), 1))
        p.drawRoundedRect(QRectF(10, 29, 500, 83), 8, 8)
        p.setFont(QFont("Consolas", 9, QFont.Bold))
        p.setPen(QColor("#46daff"))
        p.drawText(21, 45, VERSION)
        p.setFont(QFont("Consolas", 8))
        for i, (message, color) in enumerate(self.events[-3:]):
            p.setPen(QColor(color))
            p.drawText(21, 64 + i * 14, message)

        # Superficie del mando.
        p.setBrush(QColor("#0e1b30"))
        p.setPen(QPen(QColor("#1b689d"), 1))
        p.drawRoundedRect(QRectF(10, 119, 500, 112), 12, 12)
        p.setFont(QFont("Arial", 11, QFont.Bold))
        p.setPen(QColor("#2dbdff"))
        p.drawText(185, 146, "/// KOFMULTI ///")
        p.setFont(QFont("Consolas", 8))
        p.setPen(QColor("#7c9bb9"))
        p.drawText(217, 225, "SIN ASIGNAR")
        p.end()


def main():
    # Sin QSettings, sqlite, config JSON, logs, cache local ni telemetria.
    app = QApplication(sys.argv)
    app.setApplicationName("KOFMULTI CONTROL")
    window = KofControl()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
