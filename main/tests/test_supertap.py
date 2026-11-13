import unittest

from modules.parsing.supertap import EV_KEY, EV_REL, REL_WHEEL, TapDetector, key_devices

SUPER = 125
LETTER = 30
BUTTON = 272

DEVICES = """I: Bus=0011 Vendor=0001 Product=0001 Version=ab83
N: Name="AT Translated Set 2 keyboard"
H: Handlers=sysrq kbd leds event3
B: EV=120013

I: Bus=0019 Vendor=0000 Product=0000 Version=0000
N: Name="Accelerometer"
H: Handlers=event9
B: EV=9

I: Bus=0018 Vendor=06cb Product=ce26 Version=0100
N: Name="Touchpad"
H: Handlers=mouse0 event12
B: EV=b
"""


def run(events):
    detector = TapDetector()
    return [detector.feed(*event) for event in events]


class TapTest(unittest.TestCase):
    def test_lone_tap(self):
        self.assertEqual(run([(EV_KEY, SUPER, 1, 0.0), (EV_KEY, SUPER, 0, 0.2)]), [False, True])

    def test_repeat_ignored(self):
        self.assertTrue(run([(EV_KEY, SUPER, 1, 0.0), (EV_KEY, SUPER, 2, 0.3), (EV_KEY, SUPER, 0, 0.4)])[-1])

    def test_combo_is_not_tap(self):
        events = [(EV_KEY, SUPER, 1, 0.0), (EV_KEY, LETTER, 1, 0.1), (EV_KEY, LETTER, 0, 0.15),
                  (EV_KEY, SUPER, 0, 0.2)]
        self.assertFalse(any(run(events)))

    def test_mouse_button_and_scroll_cancel(self):
        self.assertFalse(any(run([(EV_KEY, SUPER, 1, 0.0), (EV_KEY, BUTTON, 1, 0.1), (EV_KEY, BUTTON, 0, 0.2),
                                  (EV_KEY, SUPER, 0, 0.3)])))
        self.assertFalse(any(run([(EV_KEY, SUPER, 1, 0.0), (EV_REL, REL_WHEEL, 1, 0.1), (EV_KEY, SUPER, 0, 0.2)])))

    def test_long_hold_is_not_tap(self):
        self.assertFalse(run([(EV_KEY, SUPER, 1, 0.0), (EV_KEY, SUPER, 0, 0.8)])[-1])

    def test_super_after_held_key(self):
        events = [(EV_KEY, LETTER, 1, 0.0), (EV_KEY, SUPER, 1, 0.1), (EV_KEY, SUPER, 0, 0.2)]
        self.assertFalse(any(run(events)))

    def test_tap_after_combo(self):
        events = [(EV_KEY, SUPER, 1, 0.0), (EV_KEY, LETTER, 1, 0.1), (EV_KEY, LETTER, 0, 0.15),
                  (EV_KEY, SUPER, 0, 0.2), (EV_KEY, SUPER, 1, 1.0), (EV_KEY, SUPER, 0, 1.1)]
        self.assertEqual(run(events)[-1], True)


class DevicesTest(unittest.TestCase):
    def test_only_key_devices(self):
        self.assertEqual(key_devices(DEVICES), ["/dev/input/event3", "/dev/input/event12"])


if __name__ == "__main__":
    unittest.main()
