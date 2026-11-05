"""Pruebas AMBOT: comandos, memoria, API y sustitucion de cache."""
from __future__ import annotations
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
from cerebro_robot import Cerebro, CuerpoSimulado, Memoria
from servidor import estado

class TestCerebro(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.memoria = Memoria(Path(self.tempdir.name) / "memoria.json")
        self.cerebro = Cerebro(CuerpoSimulado(), self.memoria)

    def test_comandos(self):
        for comando in ("estado", "mapa", "plan", "gira derecha", "avanza", "explora", "auto 3"):
            respuesta, salir = self.cerebro.ejecutar(comando)
            self.assertIsInstance(respuesta, str)
            self.assertFalse(salir)

    def test_memoria(self):
        texto, _ = self.cerebro.ejecutar("recuerda nombre = AMBOT")
        self.assertIn("AMBOT", texto)
        texto, _ = self.cerebro.ejecutar("que sabes de nombre")
        self.assertIn("AMBOT", texto)
        texto, _ = self.cerebro.ejecutar("olvida nombre")
        self.assertIn("olvidado", texto.lower())
        texto, _ = self.cerebro.ejecutar("olvida nombre")
        self.assertIn("no encontre", texto.lower())

    def test_api_estado(self):
        state = estado()
        self.assertIn("robot", state)
        self.assertIn("mapa", state)
        self.assertIn("decision", state)

    def test_cache_old_release_is_replaced(self):
        root = Path(self.tempdir.name) / "cache"
        root.mkdir()
        commit = "e" * 40
        (root / "config.json").write_text(json.dumps({
            "release_commit": commit, "version": "0.1.2"
        }), encoding="utf-8")
        for name in app.NECESSARY:
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("contenido anterior", encoding="utf-8")
        (root / ".ambot_release").write_text("a"*40+"\n", encoding="utf-8")
        def fake_download(name, _release):
            return (b"pass\n" if name.endswith(".py") else b"nuevo archivo\n")
        with patch.object(app, "ROOT", root), \
             patch.dict(os.environ, {"AMDEV_MODE":"repo"}), \
             patch.object(app, "_remote_bytes", side_effect=fake_download) as download:
            app.ensure_assets()
            self.assertEqual(download.call_count, len(app.NECESSARY))
            self.assertEqual((root / "cerebro_robot.py").read_text(), "pass\n")
            self.assertEqual((root / ".ambot_release").read_text().strip(), commit)
            app.ensure_assets()
            self.assertEqual(download.call_count, len(app.NECESSARY))

if __name__ == "__main__":
    unittest.main()
