import unittest
import xml.etree.ElementTree as ET

from modules.parsing import keyboard
from modules.rules import hypr, niri

REGISTRY = ET.fromstring("""
<xkbConfigRegistry><layoutList>
  <layout><configItem><name>us</name><shortDescription>en</shortDescription><description>English (US)</description>
  </configItem><variantList><variant><configItem><name>intl</name>
  <description>English (US, intl., with dead keys)</description></configItem></variant></variantList></layout>
  <layout><configItem><name>ru</name><shortDescription>ru</shortDescription><description>Russian</description>
  </configItem></layout>
</layoutList></xkbConfigRegistry>
""")


class ShortNameTest(unittest.TestCase):
    def setUp(self):
        self.names = keyboard.parse_registry(REGISTRY)

    def test_layout_and_variant(self):
        self.assertEqual(keyboard.short_name("English (US)", self.names), "en")
        self.assertEqual(keyboard.short_name("English (US, intl., with dead keys)", self.names), "en")
        self.assertEqual(keyboard.short_name("Russian", self.names), "ru")

    def test_unknown_and_empty(self):
        self.assertEqual(keyboard.short_name("Klingon", self.names), "kl")
        self.assertEqual(keyboard.short_name("", self.names), "")


class NiriLayoutTest(unittest.TestCase):
    def test_changed_and_switched(self):
        tracker = niri.WindowTracker()
        self.assertEqual(tracker.layout, "")
        self.assertTrue(tracker.needs_refresh(
            {"KeyboardLayoutsChanged": {"keyboard_layouts": {"names": ["English (US)", "Russian"], "current_idx": 1}}}))
        self.assertEqual(tracker.layout, "ru")
        self.assertTrue(tracker.needs_refresh({"KeyboardLayoutSwitched": {"idx": 0}}))
        self.assertEqual(tracker.layout, "en")
        self.assertTrue(tracker.needs_refresh({"KeyboardLayoutSwitched": {"idx": 5}}))
        self.assertEqual(tracker.layout, "")


class HyprLayoutTest(unittest.TestCase):
    def test_event(self):
        self.assertEqual(hypr.event_layout("activelayout>>at-translated-set-2-keyboard,Russian\n"), "ru")
        self.assertEqual(hypr.event_layout("activelayout>>kb,English (US, intl., with dead keys)"), "en")

    def test_devices(self):
        devices = {"keyboards": [{"name": "virtual", "main": False, "active_keymap": "Russian"},
                                 {"name": "kb", "main": True, "active_keymap": "English (US)"}]}
        self.assertEqual(hypr.main_layout(devices), "en")
        self.assertEqual(hypr.main_layout({}), "")


if __name__ == "__main__":
    unittest.main()


class CapsLockTest(unittest.TestCase):
    def _leds(self, root, values):
        import pathlib
        for name, value in values.items():
            led = pathlib.Path(root) / name
            led.mkdir()
            (led / "brightness").write_text(f"{value}\n")
        return keyboard.caps_lock_leds(pathlib.Path(root))

    def test_finds_only_capslock_leds(self):
        import tempfile
        with tempfile.TemporaryDirectory() as root:
            paths = self._leds(root, {"input3::capslock": 0, "input3::numlock": 1, "input9::capslock": 0})
            self.assertEqual([p.parent.name for p in paths], ["input3::capslock", "input9::capslock"])

    def test_on_if_any_keyboard_lit(self):
        import tempfile
        with tempfile.TemporaryDirectory() as root:
            self.assertFalse(keyboard.caps_lock_on(self._leds(root, {"input3::capslock": 0})))
        with tempfile.TemporaryDirectory() as root:
            self.assertTrue(keyboard.caps_lock_on(self._leds(root, {"input3::capslock": 0, "input9::capslock": 1})))

    def test_missing_or_broken_files_are_off(self):
        import pathlib
        self.assertFalse(keyboard.caps_lock_on([pathlib.Path("/nonexistent/brightness")]))
        self.assertFalse(keyboard.caps_lock_on([]))

    def test_layout_text(self):
        self.assertEqual(keyboard.layout_text("en", False), "en")
        self.assertEqual(keyboard.layout_text("en", True), "EN")
        self.assertEqual(keyboard.layout_text("", True), "")
