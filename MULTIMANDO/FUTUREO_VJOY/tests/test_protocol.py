import importlib.util
import pathlib
import unittest

PROJECT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("futjoy",PROJECT/"python"/"futureo_vjoy.py")
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class ProtocolTests(unittest.TestCase):
    def test_report(self):
        self.assertEqual(len(module.make_report()),6)
        self.assertEqual(module.make_report(-1,1,1),b"\xff\xff\x01\x00\x01\x00")

    def test_16_buttons(self):
        self.assertEqual(len(module.BUTTONS),16)
        self.assertEqual(len(set(module.BUTTONS.values())),16)

    def test_ioctls(self):
        self.assertEqual(module.IOCTL_SET_STATE,0x22A004)
        self.assertEqual(module.IOCTL_NEUTRAL,0x22A008)

    def test_validation(self):
        for values in [(-32769,0,0),(0,32768,0),(0,0,65536)]:
            with self.assertRaises(ValueError):
                module.make_report(*values)

    def test_eight_independent_pnp_ids(self):
        data=(PROJECT/"driver"/"FutJoy.inf").read_text(encoding="utf-8")
        for n in range(1,9):
            self.assertIn(f"ROOT\\FUTJOY{n:02d}",data)
            self.assertIn(f"Pad{n}=",data)
            self.assertIn(f"FUTUREO VJOY{n} - PLAYER {n}",data)

if __name__=="__main__":
    unittest.main()
