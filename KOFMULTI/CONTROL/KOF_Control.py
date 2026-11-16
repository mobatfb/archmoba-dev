# -*- coding: utf-8 -*-
"""
KOFMULTI - CONTROL v.0.0.5
Ventana fija de 520 x 240. Usa los SVG de ./assets.
Conexion real al anfitrion mediante API GET y WebSocket, sin contraseña.
Solo guarda el nombre del jugador en cache local; no guarda otros datos.
Instalacion de interfaz: py -m pip install --no-cache-dir PySide6
"""
import sys
import json
from pathlib import Path
from urllib.parse import urlsplit

from PySide6.QtCore import Qt, QRectF, QUrl, QTimer, QStandardPaths
from PySide6.QtGui import (
    QColor, QFont, QLinearGradient, QPainter, QPen
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QLineEdit
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PySide6.QtWebSockets import QWebSocket

VERSION = "v.0.0.5"
WINDOW_WIDTH = 520
WINDOW_HEIGHT = 240
ASSETS = Path(__file__).resolve().parent / "assets"
API_GET_URL = "https://api.isupol.edu.ec/api/geturlkof"
ACTION_MAP = {"UP": "UP", "DOWN": "DOWN", "LEFT": "LEFT", "RIGHT": "RIGHT",
              "A": "A", "S": "C", "Z": "B", "X": "D", "COIN": "COIN", "START": "COIN_START"}

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
        # START cambia visualmente a CONECTAR mientras no haya una sesión validada.
        if self.action == "START" and not self.parent().connected:
            grad = QLinearGradient(0, 0, 0, self.height())
            grad.setColorAt(0, QColor("#086db9"))
            grad.setColorAt(1, QColor("#061f59"))
            p.setBrush(grad)
            p.setPen(QPen(QColor("#27ddff" if not self.is_down else "#f4fbff"), 2))
            p.drawRoundedRect(rect.adjusted(1.5, 1.5, -1.5, -1.5), 12, 12)
            p.setPen(QColor("#ffffff"))
            p.setFont(QFont("Arial", 9 if self.parent().connecting else 10, QFont.Bold))
            p.drawText(rect, Qt.AlignCenter, self.fallback)
            p.end()
            return
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
    """Control remoto: solo conserva el nombre en cache local del usuario."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("KOFMULTI CONTROL " + VERSION)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setFocusPolicy(Qt.StrongFocus)
        self.drag_origin = None
        self.buttons = {}
        self.held = set()
        self.connected = False
        self.connecting = False
        self.slot = 0
        self.waiting_position = 0
        self.events = [
            ("[SISTEMA] Control iniciado.", "#9df9ad"),
            ("[RED] Desconectado del anfitrión.", "#a1bbd2"),
            ("[LISTO] Escribe tu nombre y pulsa CONECTAR.", "#8de9fa"),
        ]
        self.net = QNetworkAccessManager(self)
        self.socket = QWebSocket(parent=self)
        self.socket.connected.connect(self._socket_opened)
        self.socket.disconnected.connect(self._socket_closed)
        self.socket.textMessageReceived.connect(self._socket_message)
        self.socket.errorOccurred.connect(self._socket_error)
        self._connect_serial = 0

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

        # Nombre visible justo encima de START / CONECTAR.
        self.name_edit = QLineEdit(self)
        self.name_edit.setGeometry(221, 129, 129, 25)
        self.name_edit.setMaxLength(24)
        self.name_edit.setPlaceholderText("Tu nombre")
        self.name_edit.setText(self._load_saved_name())
        self.name_edit.setToolTip("Nombre que verán los demás jugadores")
        self.name_edit.setStyleSheet(
            "QLineEdit {background:#071526;color:#f1fbff;border:1px solid #247fbd;"
            "border-radius:6px;padding:2px 6px;font-size:10px;}"
            "QLineEdit:focus {border:1px solid #39d4ff;}"
        )
        self.name_edit.returnPressed.connect(self.begin_connect)
        self.name_edit.editingFinished.connect(self._remember_name)
        self.add_button("START", "btn_start.svg", "CONECTAR", 215, 164, 126, 38)
        self._refresh_start_button()

        # Bloque solicitado: A S / Z X.
        self.add_button("A", "btn_a.svg", "A", 404, 128, 43, 43)
        self.add_button("S", "btn_s.svg", "S", 451, 128, 43, 43)
        self.add_button("Z", "btn_z.svg", "Z", 404, 175, 43, 43)
        self.add_button("X", "btn_x.svg", "X", 451, 175, 43, 43)

        self.setFocus()

    def add_button(self, action, filename, label, x, y, w, h):
        button = ControlButton(self, action, filename, label, x, y, w, h)
        self.buttons[action] = button

    def _refresh_start_button(self):
        """Sincroniza la etiqueta del boton con el estado real de la sesion."""
        button = self.buttons.get("START")
        if button is None:
            return
        if self.connected:
            button.fallback = "START"
            button.setToolTip("COIN + START para el jugador asignado")
        elif self.connecting:
            button.fallback = "CONECTANDO"
            button.setToolTip("Estableciendo conexion con el anfitrion")
        else:
            button.fallback = "CONECTAR"
            button.setToolTip("Conectarse al anfitrion")
        button.update()

    def _write_log(self, text, color="#8de9fa"):
        self.events.append((text, color))
        self.events = self.events[-4:]
        self.update()

    @staticmethod
    def _clean_name(value):
        # El nombre coincide con el formato permitido por el anfitrion.
        return " ".join("".join(ch for ch in str(value) if ch.isprintable()).split())[:24]

    @staticmethod
    def _name_cache_file():
        # Cache privada por perfil de sistema. Nada se guarda junto al programa.
        location = QStandardPaths.writableLocation(QStandardPaths.CacheLocation)
        if not location:
            return None
        return Path(location) / "nombre_jugador.txt"

    def _load_saved_name(self):
        try:
            cache = self._name_cache_file()
            if cache and cache.is_file():
                return self._clean_name(cache.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError):
            pass
        return ""

    def _remember_name(self):
        name = self._clean_name(self.name_edit.text())
        if not name:
            return
        try:
            cache = self._name_cache_file()
            if cache is None:
                return
            # Se escribe solo al cambiar el nombre; no se crea otro cache.
            if cache.is_file() and self._clean_name(cache.read_text(encoding="utf-8")) == name:
                return
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(name, encoding="utf-8")
        except (OSError, UnicodeError, ValueError):
            # Si el perfil no permite escribir, el control igual funciona.
            pass

    def begin_connect(self):
        """El enlace se consulta en la API; el usuario no escribe URL ni clave."""
        if self.connected or self.connecting:
            return
        name = " ".join(self.name_edit.text().split()).strip()
        if not name:
            self._write_log("[AVISO] Escribe tu nombre para conectar.", "#ffd170")
            self.name_edit.setFocus()
            return
        self._remember_name()
        self.connecting = True
        self._connect_serial += 1
        serial = self._connect_serial
        self._refresh_start_button()
        self._write_log("[RED] Consultando dirección de la sala...", "#91dcff")
        request = QNetworkRequest(QUrl(API_GET_URL))
        request.setRawHeader(b"Cache-Control", b"no-store, no-cache, max-age=0")
        request.setAttribute(QNetworkRequest.CacheLoadControlAttribute,
                             QNetworkRequest.CacheLoadControl.AlwaysNetwork)
        request.setAttribute(QNetworkRequest.CacheSaveControlAttribute, False)
        request.setTransferTimeout(10000)
        reply = self.net.get(request)
        reply.finished.connect(lambda: self._api_finished(reply, serial))
        QTimer.singleShot(12000, lambda: self._timeout_connect(serial))

    def _timeout_connect(self, serial):
        if serial != self._connect_serial or not self.connecting:
            return
        self._connect_failed("Tiempo de conexión agotado.")

    def _connect_failed(self, message):
        self._connect_serial += 1
        self.connecting = False
        self.connected = False
        self.slot = 0
        self.waiting_position = 0
        self._refresh_start_button()
        self._write_log("[ERROR] " + message[:100], "#ff8989")

    def _api_finished(self, reply, serial):
        try:
            if serial != self._connect_serial or not self.connecting:
                return
            if reply.error() != QNetworkReply.NetworkError.NoError:
                self._connect_failed("No se pudo consultar la API: " + reply.errorString())
                return
            data = json.loads(bytes(reply.readAll()).decode("utf-8"))
            if not isinstance(data, dict) or data.get("status") != "success":
                self._connect_failed("La API no devolvió una sala válida.")
                return
            # La API puede exponer el campo original amo_users.email,
            # o el alias url, sin que el usuario cambie su configuracion.
            source = data.get("data") if isinstance(data.get("data"), dict) else data
            raw_url = str(source.get("url") or source.get("email") or
                          data.get("url") or data.get("email") or "").strip()
            parsed = urlsplit(raw_url)
            # El anfitrión publica Cloudflare Quick Tunnel. No seguir URL
            # arbitrarias si alguien modifica el POST público de Laravel.
            host = (parsed.hostname or "").lower()
            if parsed.scheme not in ("https", "wss") or not host.endswith(".trycloudflare.com"):
                self._connect_failed("Sala no publicada o URL de Cloudflare no válida.")
                return
            if parsed.username or parsed.password or parsed.port not in (None, 443):
                self._connect_failed("Dirección de sala no permitida.")
                return
            websocket_url = "wss://" + host + (parsed.path or "/")
            self._write_log("[RED] Conectando con el anfitrión...", "#8de9fa")
            self.socket.open(QUrl(websocket_url))
        except (ValueError, TypeError, KeyError, UnicodeError) as exc:
            self._connect_failed("Respuesta de API incorrecta: " + str(exc))
        finally:
            reply.deleteLater()

    def _socket_opened(self):
        if not self.connecting:
            self.socket.close()
            return
        hello = {"type": "hello", "name": self.name_edit.text().strip()[:24]}
        self.socket.sendTextMessage(json.dumps(hello, ensure_ascii=False))

    def _socket_message(self, message):
        try:
            payload = json.loads(message)
        except (TypeError, ValueError):
            return
        if not isinstance(payload, dict):
            return
        kind = payload.get("type")
        if kind == "welcome":
            if not self.connecting:
                return
            self._connect_serial += 1
            self.connecting = False
            self.connected = True
            self.name_edit.setReadOnly(True)
            self.name_edit.setFocusPolicy(Qt.NoFocus)
            self.setFocus()
            self._refresh_start_button()
            self._write_log("[OK] Conectado: botón START habilitado.", "#83f9a1")
        elif kind == "state":
            if not self.connected:
                return
            new_slot = payload.get("slot")
            try:
                new_slot = int(new_slot) if new_slot else 0
            except (TypeError, ValueError):
                new_slot = 0
            if new_slot not in (0, 1, 2):
                new_slot = 0
            pos = payload.get("waiting_position", 0)
            try:
                pos = max(0, int(pos))
            except (ValueError, TypeError):
                pos = 0
            if (new_slot, pos) != (self.slot, self.waiting_position):
                for a in tuple(self.held):
                    self._release_action(a)
                self.slot = new_slot
                self.waiting_position = pos
                status = f"Asignado a P{new_slot}." if new_slot else (
                    f"En espera: posición {pos}." if pos else "Modo espectador.")
                self._write_log("[TURNO] " + status, "#ffdf61")
            self.update()
        elif kind == "notice":
            self._write_log("[AVISO] " + str(payload.get("message", ""))[:80], "#ffd170")
        elif kind == "error":
            self._write_log("[ERROR] " + str(payload.get("message", ""))[:80], "#ff8989")
            self.socket.close()
        elif kind == "input_ack" and payload.get("action") == "COIN_START":
            self._write_log("[JUEGO] COIN + START enviado.", "#7af1aa")

    def _socket_error(self, error):
        msg = self.socket.errorString() or "Error de WebSocket."
        if self.connecting:
            self._connect_failed(msg)
        elif self.connected:
            self._write_log("[RED] " + msg[:90], "#ff8989")

    def _socket_closed(self):
        if self.connecting:
            self._connect_failed("No se completó la conexión.")
        elif self.connected:
            self._write_log("[RED] Desconectado del anfitrión.", "#ffd170")
        self.connected = False
        self.connecting = False
        self.slot = 0
        self.waiting_position = 0
        for a in tuple(self.held):
            self._release_action(a, send=False)
        self.name_edit.setReadOnly(False)
        self.name_edit.setFocusPolicy(Qt.StrongFocus)
        self._refresh_start_button()
        self.update()

    def _send(self, payload):
        if not self.connected:
            return
        self.socket.sendTextMessage(json.dumps(payload, separators=(",", ":")))

    def _release_action(self, action, send=True):
        if action not in self.held:
            return
        self.held.remove(action)
        if action in self.buttons:
            self.buttons[action].set_pressed(False)
        if send and self.connected and self.slot:
            self._send({"type": "input", "action": ACTION_MAP[action], "down": False})

    def action_event(self, action, down, source):
        if not action:
            return
        if action == "START" and not self.connected:
            if down:
                self.begin_connect()
            return
        if down:
            if action in self.held:
                return
            self.held.add(action)
            self.buttons.get(action) and self.buttons[action].set_pressed(True)
            if not self.connected:
                return
            if not self.slot:
                if action == "START" and not self.waiting_position:
                    self._send({"type": "request"})
                    self._write_log("[TURNO] Solicitando un mando...", "#91dcff")
                return
            self._send({"type": "input", "action": ACTION_MAP[action], "down": True})
        else:
            self._release_action(action)
        self.update()

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
        # Al perder foco, soltar direcciones y golpes (no quedan bloqueados).
        for action in tuple(self.held):
            self._release_action(action)
        super().focusOutEvent(event)

    def closeEvent(self, event):
        self._remember_name()
        for action in tuple(self.held):
            self._release_action(action)
        self.socket.close()
        super().closeEvent(event)

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

        # Consola solo para eventos. La versión ya figura en la barra superior.
        p.setBrush(QColor("#050c17"))
        p.setPen(QPen(QColor("#185a91"), 1))
        p.drawRoundedRect(QRectF(10, 29, 500, 83), 8, 8)
        p.setFont(QFont("Consolas", 8))
        for i, (message, color) in enumerate(self.events[-4:]):
            p.setPen(QColor(color))
            p.drawText(21, 46 + i * 18, message[:78])

        # Superficie del mando.
        p.setBrush(QColor("#0e1b30"))
        p.setPen(QPen(QColor("#1b689d"), 1))
        p.drawRoundedRect(QRectF(10, 119, 500, 112), 12, 12)
        p.setFont(QFont("Arial", 8, QFont.Bold))
        p.setPen(QColor("#56d6ff"))
        p.drawText(167, 146, "NOMBRE")
        p.setFont(QFont("Consolas", 8))
        p.setPen(QColor("#7c9bb9" if not self.connected else "#77f5af"))
        status = ("DESCONECTADO" if not self.connected else
                  f"P{self.slot}" if self.slot else
                  f"ESPERA #{self.waiting_position}" if self.waiting_position else "ESPECTADOR")
        p.drawText(QRectF(179, 209, 170, 21), Qt.AlignCenter, status)
        p.end()


def main():
    # Unicamente se guarda el nombre en cache local; no se persiste nada mas.
    app = QApplication(sys.argv)
    app.setApplicationName("KOFMULTI CONTROL")
    window = KofControl()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
