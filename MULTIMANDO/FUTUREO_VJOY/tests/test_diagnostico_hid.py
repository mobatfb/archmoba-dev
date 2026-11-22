"""Solo datos simulados: no pretende comprobar HID de Windows."""
import pathlib
import sys
import unittest

PROJECT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "python"))
from diagnostico_hid import LAB_VENDOR_ID, PID_BASE, summarize, text_report


def fake_device(slot: int, name: str) -> dict:
    return {
        "slot": slot, "vid": f"{LAB_VENDOR_ID:04X}",
        "pid": f"{PID_BASE + slot:04X}",
        "product_string": name, "version": "0100",
    }


class HidDiagnoseTests(unittest.TestCase):
    def test_eight_distinct_names(self):
        fake = [fake_device(n, f"FUTUREO VJOY{n}") for n in range(1, 9)]
        report = summarize(fake, 8)
        self.assertEqual(report["puestos_detectados"], 8)
        self.assertTrue(report["product_strings_diferentes"])
        self.assertEqual(len(report["puestos"]), 8)
        self.assertIn("CONFIRMADOS", text_report(report))

    def test_identical_names_are_not_unique(self):
        fake = [fake_device(n, "Virtual HID Gamepad") for n in range(1, 9)]
        report = summarize(fake, 8)
        self.assertFalse(report["product_strings_diferentes"])
        self.assertTrue(any("nombres iguales" in msg
                            for msg in report["advertencias"]))

    def test_empty_product_string_is_not_a_unique_name(self):
        fake = [fake_device(n, "") for n in range(1, 9)]
        report = summarize(fake, 8)
        self.assertFalse(report["product_strings_diferentes"])
        self.assertEqual(report["puestos"][0]["product_strings"], [])

    def test_missing_devices(self):
        fake = [fake_device(2, "FUTUREO VJOY2")]
        report = summarize(fake, 4)
        self.assertEqual(report["puestos_detectados"], 1)
        self.assertFalse(report["product_strings_diferentes"])
        self.assertIn("P1", " ".join(report["advertencias"]))
        self.assertIn("NO DETECTADO", text_report(report))

    def test_multiple_collections_same_device(self):
        fake = [fake_device(1, "FUTUREO VJOY1"),
                fake_device(1, "FUTUREO VJOY1")]
        report = summarize(fake, 1)
        self.assertEqual(report["puestos"][0]["colecciones_hid"], 2)
        self.assertFalse(report["product_strings_diferentes"])

    def test_real_report_one_of_eight_is_valid_pending_work(self):
        # Situacion de laboratorio: P1 esta instalado y P2-P8 aun no.
        report = summarize([fake_device(1, "HID VHF Driver")], 8)
        self.assertEqual(report["puestos_detectados"], 1)
        self.assertEqual(report["puestos"][0]["vid_pid"], "F7A0:2101")
        self.assertFalse(report["product_strings_diferentes"])
        self.assertIn("un solo mando", " ".join(report["advertencias"]))
        self.assertNotIn("No se ha instalado ni firmado",
                         report["nota"])
        self.assertIn("HID VHF Driver", text_report(report))

    def test_conflicting_product_strings_in_one_slot(self):
        fake = [fake_device(1, "FUTUREO VJOY1"),
                fake_device(1, "Virtual Gamepad")]
        self.assertFalse(summarize(fake, 1)["product_strings_diferentes"])

    def test_reject_invalid_counts(self):
        for val in (-2, 0, 9, True, "8"):
            with self.assertRaises(ValueError):
                summarize([], val)

    def test_readonly_contract(self):
        source = (PROJECT / "python" / "diagnostico_hid.py").read_text(
            encoding="utf-8")
        self.assertIn("SetupDiGetClassDevsW", source)
        self.assertIn("HidD_GetProductString", source)
        self.assertIn("HidD_GetAttributes", source)
        self.assertNotIn("winreg.SetValue", source)
        self.assertNotIn("DeviceIoControl", source)
        self.assertIn("--json", source)


if __name__ == "__main__":
    unittest.main()
