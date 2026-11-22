"""Pruebas de nombres PnP sin instalar ni modificar dispositivos Windows."""
import pathlib
import sys
import unittest

PROJECT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "python"))

import nombres_pnp as pnp


class PnPNamingTests(unittest.TestCase):
    def test_slot_id_is_strictly_hid_and_lab_vid_pid(self):
        for slot in range(1, 9):
            instance_id = rf"HID\VID_F7A0&PID_{0x2100+slot:04X}&COL01\A123"
            self.assertEqual(pnp.slot_from_id(instance_id), slot)
            self.assertEqual(pnp.slot_from_id(instance_id.lower()), slot)
        for ident in (
            r"USB\VID_F7A0&PID_2101\A123",
            r"ROOT\FUTJOY01\0000",
            r"HID\VID_F7A0&PID_2100\A123",
            r"HID\VID_F7A0&PID_2109\A123",
            r"HID\VID_F7A0&PID_21010\A123",
            r"HID\VID_0000&PID_2101\A123",
            r"HID\VID_F7A0&PID_2101_FAKE\A123",
        ):
            self.assertIsNone(pnp.slot_from_id(ident))

    def test_correct_names_one_to_eight(self):
        for n in range(1, 9):
            self.assertEqual(pnp.label_for_slot(n),
                             f"FUTUREO VJOY{n} - PLAYER {n}")
        for wrong in (0, 9, -1, True, "1"):
            with self.assertRaises(ValueError):
                pnp.label_for_slot(wrong)

    def test_backups_restricted_to_matching_futjoy_devices(self):
        valid = [{
            "instance_id": r"HID\VID_F7A0&PID_2101&COL01\A",
            "previous": {"exists": False, "value": None},
            "intended": "FUTUREO VJOY1 - PLAYER 1",
        }]
        self.assertEqual(pnp.safe_backup_records(valid), valid)
        for unsafe in (
            [{**valid[0], "instance_id": r"USB\VID_F7A0&PID_2101\A"}],
            [{**valid[0], "intended": "INJECTED"}],
            [{**valid[0], "previous": {"exists": "yes"}}],
            valid + valid,
            {"entries": valid},
        ):
            with self.assertRaises(ValueError):
                pnp.safe_backup_records(unsafe)

    def test_readonly_is_default_and_uses_setupapi(self):
        code = (PROJECT / "python" / "nombres_pnp.py").read_text(
            encoding="utf-8")
        self.assertIn("DIGCF_PRESENT | DIGCF_ALLCLASSES", code)
        self.assertIn("SetupDiSetDeviceRegistryPropertyW", code)
        self.assertIn("SPDRP_FRIENDLYNAME", code)
        self.assertIn("root_ancestor", code)
        self.assertIn("save_backup(backup + pending)", code)
        self.assertIn("status(args.count)", code)
        self.assertNotIn("bcdedit.exe", code)
        self.assertNotIn("pnputil.exe", code)
        self.assertNotIn("devcon.exe", code)


if __name__ == "__main__":
    unittest.main()
