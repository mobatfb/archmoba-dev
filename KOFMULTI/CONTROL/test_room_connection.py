#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CONTROL: pruebas de selección de sala (sin llamadas a la API)."""
import unittest
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ANFITRION"))
from KOF_Anfitrion import HostServer, NullInput
from PySide6.QtWidgets import QApplication
from KOF_Control import KofControl, VERSION, parse_direct_room_url


class ControlRoomTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_paste_host_invitation(self):
        text = ("KOF ARENA - ENLACE DE SALA\n"
                "Enlace: https://ejemplo-sala-123.trycloudflare.com\n"
                "Abre el control remoto.")
        self.assertEqual(parse_direct_room_url(text),
                         "wss://ejemplo-sala-123.trycloudflare.com/")

    def test_url_and_empty(self):
        self.assertEqual(
            parse_direct_room_url("https://test-kof.trycloudflare.com/"),
            "wss://test-kof.trycloudflare.com/")
        self.assertIsNone(parse_direct_room_url(""))

    def test_reject_other_sites(self):
        for value in ("https://example.org", "http://test.trycloudflare.com",
                      "https://test.trycloudflare.com.evil.org"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_direct_room_url(value)

    def test_qt_websocket_connects_to_this_host(self):
        """La ventana REAL Qt conecta y su sesión coincide con la del host."""
        device = NullInput()
        host = HostServer(
            port=0, ui_notify=lambda *args: None,
            device=device, restore_state=False, process_provider=lambda: None)
        host.start()
        widget = KofControl()
        try:
            widget.name_edit.setText("Prueba Qt")
            widget.direct_url = f"ws://127.0.0.1:{host.server.socket.getsockname()[1]}"
            widget.begin_connect()
            deadline = time.monotonic() + 8
            while not (widget.connected and widget.slot == 1):
                self.app.processEvents()
                self.assertLess(time.monotonic(), deadline, "Qt no recibió P1")
                time.sleep(0.01)
            self.assertEqual(widget.room_id, host.room_id)
            self.assertEqual(host.room.snapshot()["total"], 1)
            widget.action_event("A", True, "tactil")
            deadline = time.monotonic() + 3
            while (1, "A", True) not in device.events:
                self.app.processEvents()
                self.assertLess(time.monotonic(), deadline, "La tecla A no llegó al host")
                time.sleep(0.01)
            widget.action_event("A", False, "tactil")
            self.assertEqual(host.room.snapshot()["players"]["1"]["name"], "Prueba Qt")
        finally:
            widget.close()
            host.stop()
            self.app.processEvents()

    def test_gui_starts_with_auto_and_room_button(self):
        widget = KofControl()
        try:
            self.assertEqual(VERSION, "v.0.0.6")
            self.assertIsNone(widget.direct_url)
            self.assertEqual(widget.room_button.text(), "SALA")
            self.assertFalse(widget.connected)
            self.assertEqual(widget.room_id, "")
        finally:
            widget.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
