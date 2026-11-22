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

class DriverInstallationContractTests(unittest.TestCase):
    def test_vhf_lower_filter_is_declared(self):
        inf=(PROJECT/"driver"/"FutJoy.inf").read_text(encoding="utf-8")
        self.assertIn("[FutJoyInstall.NT.HW]",inf)
        self.assertIn('HKR,,"LowerFilters",0x00010000,"vhf"',inf)

    def test_driver_releases_buttons_when_handle_closes(self):
        source=(PROJECT/"driver"/"FutJoy.c").read_text(encoding="utf-8")
        self.assertIn("FutJoyFileCleanup",source)
        self.assertIn("WdfDeviceInitSetFileObjectConfig",source)
        self.assertIn("SendState(ctx,&neutral)",source)

    def test_only_one_writer_per_virtual_gamepad(self):
        driver=(PROJECT/"driver"/"FutJoy.c").read_text(encoding="utf-8")
        bridge=(PROJECT/"python"/"futureo_vjoy.py").read_text(encoding="utf-8")
        self.assertIn("WdfDeviceInitSetExclusive(init, TRUE);", driver)
        self.assertIn("self.path, GENERIC_WRITE, 0,", bridge)
        self.assertIn("FutJoyFileCleanup", driver)

    def test_unique_product_ids(self):
        source=(PROJECT/"driver"/"FutJoy.c").read_text(encoding="utf-8")
        self.assertIn("FUTJOY_PRODUCT_BASE+ctx->Slot",source)
        self.assertIn("config.ProductID",source.replace("vhf.ProductID","config.ProductID"))

class DirectInputNamesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec=importlib.util.spec_from_file_location(
            "names",PROJECT/"python"/"nombres_windows.py")
        cls.names=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.names)

    def test_eight_distinct_oem_names(self):
        keys=set()
        for slot in range(1,9):
            value=self.names.product_key(slot)
            keys.add(value)
            plan=self.names.changes_for_slot(slot)
            self.assertEqual(len(plan),3)
            self.assertEqual({p["value"] for p in plan},{f"FUTUREO VJOY{slot}"})
            self.assertEqual(sum("OEMName"==p["name"] for p in plan),2)
        self.assertEqual(len(keys),8)

    def test_rejects_wrong_slot(self):
        for slot in (-1,0,9,True,"2"):
            with self.assertRaises(ValueError):
                self.names.product_key(slot)


if __name__=="__main__":
    unittest.main()
