"""Pruebas de alias OEM sin escribir en el Registro ni instalar controladores."""
import json
import pathlib
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

PROJECT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "python"))

import nombres_windows as names


class NamesIncrementalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.backup = pathlib.Path(self.temp.name) / "backup.json"
        self.values = {}

        def read(change):
            result = self.values.get(names._identity(change))
            return {"exists": True, "value": result} if result is not None else {
                "exists": False, "value": None
            }

        def put(change, value):
            self.values[names._identity(change)] = value

        def delete(change):
            self.values.pop(names._identity(change), None)

        patches = [
            patch.object(names, "BACKUP", self.backup),
            patch.object(names, "winreg", types.SimpleNamespace()),
            patch.object(names, "is_admin", return_value=True),
            patch.object(names, "installed_slots", return_value={1, 2, 3, 4}),
            patch.object(names, "read_value", side_effect=read),
            patch.object(names, "put_value", side_effect=put),
            patch.object(names, "delete_value", side_effect=delete),
        ]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)

    def test_apply_two_then_expand_four_preserves_original_backup(self):
        names.apply(2)
        original = json.loads(self.backup.read_text(encoding="utf-8"))
        self.assertEqual(len(original), 6)
        names.apply(4)
        extended = json.loads(self.backup.read_text(encoding="utf-8"))
        self.assertEqual(len(extended), 12)
        self.assertEqual(extended[:6], original)
        self.assertEqual(len(self.values), 12)
        names.restore()
        self.assertFalse(self.backup.exists())
        self.assertFalse(self.values)

    def test_same_names_can_be_applied_twice_without_conflict(self):
        names.apply(2)
        names.apply(2)
        self.assertEqual(len(json.loads(self.backup.read_text(encoding="utf-8"))), 6)

    def test_external_modification_is_not_overwritten(self):
        names.apply(2)
        target = names.changes_for_slot(1)[0]
        self.values[names._identity(target)] = "ETIQUETA EXTERNA"
        with self.assertRaisesRegex(RuntimeError, "Otra aplicacion"):
            names.apply(4)
        self.assertEqual(self.values[names._identity(target)], "ETIQUETA EXTERNA")
        self.assertEqual(len(json.loads(self.backup.read_text(encoding="utf-8"))), 6)

    def test_backup_cannot_redirect_registry_writes(self):
        target = names.changes_for_slot(1)[0].copy()
        target["path"] = r"SOFTWARE\\OtraAplicacion"
        self.backup.write_text(json.dumps([{
            "target": target, "previous": {"exists": False, "value": None}
        }]), encoding="utf-8")
        with self.assertRaises(ValueError):
            names.apply(2)
        self.assertFalse(self.values)

    def test_cannot_label_missing_slot(self):
        with self.assertRaisesRegex(RuntimeError, "faltan 5"):
            names.apply(5)
        self.assertFalse(self.backup.exists())


if __name__ == "__main__":
    unittest.main()
