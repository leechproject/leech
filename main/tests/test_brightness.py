import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from modules.parsing import brightness
from modules.cc import controls


class CurveTest(unittest.TestCase):
    def test_matches_brightnessctl_e4(self):
        self.assertEqual(brightness.percent_to_raw(50, 19200, 4), 1200)
        self.assertEqual(brightness.percent_to_raw(100, 19200, 4), 19200)
        self.assertEqual(brightness.percent_to_raw(0, 19200, 4), 1)
        self.assertEqual(brightness.raw_to_percent(1200, 19200, 4), 50)

    def test_roundtrip_above_dark_end(self):
        for percent in range(15, 101):
            raw = brightness.percent_to_raw(percent, 19200, 4)
            self.assertEqual(brightness.raw_to_percent(raw, 19200, 4), percent)

    def test_every_step_changes_raw(self):
        raws = [brightness.percent_to_raw(p, 19200, 4) for p in range(10, 101, 5)]
        self.assertEqual(len(set(raws)), len(raws))

    def test_raw_clamped(self):
        self.assertEqual(brightness.raw_to_percent(30000, 19200, 4), 100)


class WriteTest(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        base = Path(self._dir.name)
        dev = base / "intel_backlight"
        dev.mkdir()
        (dev / "brightness").write_text("19200\n")
        (dev / "max_brightness").write_text("19200\n")
        self.sysfs = dev / "brightness"
        patches = [mock.patch.object(brightness, "_BASE", base),
                   mock.patch.object(brightness, "_preferred", None),
                   mock.patch.object(brightness, "_reported", set()),
                   mock.patch.object(brightness.config, "BRIGHTNESS_EXPONENT", 4),
                   mock.patch("builtins.print")]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self._dir.cleanup)

    def _set(self, raw):
        self.sysfs.write_text(f"{raw}\n")

    def test_first_backend_verified(self):
        ctl = mock.Mock(side_effect=lambda name, raw: self._set(raw))
        logind = mock.Mock()
        with mock.patch.object(brightness, "_backends", return_value=[("brightnessctl", ctl), ("logind", logind)]):
            self.assertEqual(brightness.write(50), 1200)
        ctl.assert_called_once_with("intel_backlight", 1200)
        logind.assert_not_called()

    def test_failed_backend_falls_through(self):
        failing = mock.Mock(side_effect=subprocess.CalledProcessError(1, "brightnessctl", stderr=b"denied"))
        logind = mock.Mock(side_effect=lambda name, raw: self._set(raw))
        with mock.patch.object(brightness, "_backends", return_value=[("brightnessctl", failing), ("logind", logind)]):
            self.assertEqual(brightness.write(50), 1200)
        self.assertEqual(brightness._preferred, "logind")

    def test_silent_noop_is_caught(self):
        noop = mock.Mock()
        with mock.patch.object(brightness, "_backends", return_value=[("logind", noop)]):
            self.assertIsNone(brightness.write(50))

    def test_preferred_goes_first(self):
        with mock.patch("shutil.which", return_value="/usr/bin/brightnessctl"), \
             mock.patch.object(brightness, "_preferred", "logind"):
            self.assertEqual([label for label, _ in brightness._backends()],
                             ["logind", "brightnessctl", "sysfs"])


class ReconcileTest(unittest.TestCase):
    def setUp(self):
        patches = [mock.patch.object(brightness, "watch", return_value=True),
                   mock.patch.object(brightness.config, "BRIGHTNESS_EXPONENT", 4)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.c = controls.Controls()
        self.events = []
        self.c.subscribe(lambda kind, osd: self.events.append((kind, osd, self.c.brightness)))

    def test_external_change_updates_level(self):
        self.c._on_backlight(1200, 19200)
        self.assertEqual(self.c.brightness, 50)
        self.assertEqual(self.events, [("brightness", False, 50)])

    def test_own_write_keeps_chosen_level(self):
        self.c.brightness = 5
        self.c._backlight_raw = 1
        self.c._on_backlight(1, 19200, force=True)
        self.assertEqual(self.c.brightness, 5)
        self.assertEqual(self.events, [])

    def test_ignored_while_writing(self):
        self.c._busy["brightness"] = True
        self.c._on_backlight(1200, 19200)
        self.assertEqual(self.events, [])


if __name__ == "__main__":
    unittest.main()
