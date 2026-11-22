import pathlib
import sys
import time
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
from adapter_multimando import FutureoPads, BUTTONS


class DummyFutJoy:
    def __init__(self, slot):
        self.slot = slot
        self.events = []
        self.closed = False

    def state(self, x=0, y=0, buttons=0):
        self.events.append(("state", x, y, buttons))

    def neutral(self):
        self.events.append(("neutral", 0, 0, 0))

    def close(self):
        self.closed = True


class AdapterTests(unittest.TestCase):
    def make(self, count=2):
        created = []
        def factory(slot):
            pad = DummyFutJoy(slot)
            created.append(pad)
            return pad
        return FutureoPads(count=count, factory=factory), created

    def test_eight_separate_slots(self):
        host, pads = self.make(8)
        self.assertEqual([p.slot for p in pads], list(range(1, 9)))
        self.assertTrue(host.apply(3, "button_a", True))
        self.assertEqual(pads[2].events[-1][-1], 1)
        self.assertEqual(pads[0].events[-1][-1], 0)
        host.release_slot(3)
        self.assertEqual(pads[2].events[-1], ("neutral", 0, 0, 0))
        host.close()
        self.assertTrue(all(p.closed for p in pads))

    def test_directional_axes(self):
        host, pads = self.make()
        self.assertTrue(host.apply(1, "ar", True))
        self.assertEqual(pads[0].events[-1][1:3], (0, -32767))
        self.assertTrue(host.apply(1, "de", True))
        self.assertEqual(pads[0].events[-1][1:3], (32767, -32767))
        host.release_slot(1)
        self.assertEqual(pads[0].events[-1], ("neutral", 0, 0, 0))
        host.close()

    def test_analog_mode_and_validation(self):
        host, pads = self.make()
        self.assertTrue(host.set_mode(2, "analog"))
        self.assertTrue(host.analog(2, -127, 127))
        self.assertEqual(pads[1].events[-1][1:3], (-32767, -32767))
        self.assertFalse(host.analog(2, 128, 0))
        self.assertFalse(host.analog(9, 0, 0))
        self.assertTrue(host.set_mode(2, "dpad"))
        self.assertEqual(pads[1].events[-1][1:3], (0, 0))
        host.close()

    def test_all_eight_buttons(self):
        host, pads = self.make()
        for action in BUTTONS:
            self.assertTrue(host.apply(1, action, True))
        self.assertEqual(pads[0].events[-1][-1], 255)
        host.release_slot(1)
        self.assertEqual(pads[0].events[-1], ("neutral", 0, 0, 0))
        host.close()

    def test_identify_never_leaves_button_down(self):
        host, pads = self.make()
        self.assertTrue(host.identify(1, duration=.12))
        self.assertEqual(pads[0].events[-2][3], 128)
        self.assertEqual(pads[0].events[-1], ("neutral", 0, 0, 0))
        host.close()

    def test_invalid_counts(self):
        for count in (0, 9, True, "2"):
            with self.assertRaises(ValueError):
                FutureoPads(count=count, factory=DummyFutJoy)

    def test_short_tap_is_released(self):
        host, pads = self.make()
        self.assertTrue(host.apply(1, "button_b", True))
        self.assertTrue(host.apply(1, "button_b", False))
        time.sleep(.16)
        self.assertEqual(pads[0].events[-1][-1], 0)
        host.close()


if __name__ == "__main__":
    unittest.main()
