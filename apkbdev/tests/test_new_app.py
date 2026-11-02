"""Pruebas del generador sin dependencias externas."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from new_app import generate


class TemplateTests(unittest.TestCase):
    def test_create_native_java_app(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = generate("App de prueba", "app-test",
                                   "com.archmoba.apptest",
                                   projects_dir=directory)
            self.assertTrue((destination / "app/build.gradle").exists())
            manifest = (destination / "app/src/main/AndroidManifest.xml").read_text(encoding="utf-8")
            self.assertIn("App de prueba", manifest)
            java = (destination / "app/src/main/java/com/archmoba/apptest/MainActivity.java").read_text(encoding="utf-8")
            self.assertIn("package com.archmoba.apptest;", java)
            self.assertNotIn("__APPLICATION_ID__", java)
            self.assertIn("compileSdk 35", (destination / "app/build.gradle").read_text())
            with self.assertRaises(FileExistsError):
                generate("Duplicada", "app-test", "com.archmoba.apptest", projects_dir=directory)

    def test_reject_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            for slug in ("../escape", "App!", "", "-hidden", "dot.name"):
                with self.assertRaises(ValueError):
                    generate("X", slug, "com.archmoba.example", projects_dir=directory)
            for package in ("single", "../escape", "com.bad-pkg"):
                with self.assertRaises(ValueError):
                    generate("X", "goodname", package, projects_dir=directory)

    def test_quotes_in_app_name(self):
        with tempfile.TemporaryDirectory() as directory:
            d = generate('A "B" & C', "quoted", "com.archmoba.quoted", projects_dir=directory)
            manifest = (d / "app/src/main/AndroidManifest.xml").read_text(encoding="utf-8")
            self.assertIn("&quot;B&quot;", manifest)
            self.assertIn("&amp;", manifest)


if __name__ == "__main__":
    unittest.main()
