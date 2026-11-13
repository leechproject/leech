import unittest
from unittest import mock

from modules.parsing import power


def tools(*available):
    return lambda name: f"/usr/bin/{name}" if name in available else None


class FallbackCommandTest(unittest.TestCase):
    def test_systemd(self):
        with mock.patch("os.path.isdir", return_value=True), \
             mock.patch("shutil.which", side_effect=tools("systemctl", "loginctl")):
            self.assertEqual(power.fallback_command("reboot"), ["systemctl", "reboot"])

    def test_elogind(self):
        with mock.patch("os.path.isdir", return_value=False), \
             mock.patch("shutil.which", side_effect=tools("loginctl")):
            self.assertEqual(power.fallback_command("suspend"), ["loginctl", "suspend"])

    def test_nothing(self):
        with mock.patch("os.path.isdir", return_value=False), \
             mock.patch("shutil.which", side_effect=tools()):
            self.assertIsNone(power.fallback_command("poweroff"))

    def test_verbs(self):
        self.assertEqual(power._VERBS, {"Reboot": "reboot", "PowerOff": "poweroff", "Suspend": "suspend"})


if __name__ == "__main__":
    unittest.main()
