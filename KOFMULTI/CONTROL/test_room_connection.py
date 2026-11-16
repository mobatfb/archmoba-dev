#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CONTROL: pruebas de selección de sala (sin llamadas a la API)."""
import unittest

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
