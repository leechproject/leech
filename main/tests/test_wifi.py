import unittest
from unittest import mock

from modules.parsing import wifi
from modules.parsing.wifi import Network


def _net(known="Home", secure=True):
    return Network("Home", 80, secure, False, known)


class KnownTest(unittest.TestCase):
    def test_ssid_with_colon_is_unescaped(self):
        answers = {("-t", "-f", "NAME,TYPE", "connection", "show"): (True, "Cafe\\: 2:802-11-wireless\n"),
                   ("-g", "802-11-wireless.ssid", "connection", "show", "id", "Cafe: 2"): (True, "Cafe\\: 2\n")}
        with mock.patch.object(wifi, "_run", side_effect=lambda args, *_: answers[tuple(args)]):
            self.assertEqual(wifi._known(), {"Cafe: 2": "Cafe: 2"})


class ConnectTest(unittest.TestCase):
    def test_saved_network_without_password_brings_profile_up(self):
        with mock.patch.object(wifi, "_run", return_value=(True, "")) as run:
            wifi.connect(_net())
        run.assert_called_once_with(["connection", "up", "id", "Home"], wifi.CONNECT_TIMEOUT)

    def test_saved_network_with_password_updates_profile_then_connects(self):
        calls = []

        def run(args, *_):
            calls.append(args)
            return (True, "wpa-psk\n") if args[0] == "-g" else (True, "")
        with mock.patch.object(wifi, "_run", side_effect=run):
            wifi.connect(_net(), "secret")
        self.assertEqual(calls[1], ["connection", "modify", "id", "Home", "802-11-wireless-security.psk", "secret",
                                    "802-11-wireless-security.psk-flags", "0"])
        self.assertEqual(calls[2], ["connection", "up", "id", "Home"])

    def test_profile_without_security_gets_key_mgmt(self):
        calls = []

        def run(args, *_):
            calls.append(args)
            return True, ""
        with mock.patch.object(wifi, "_run", side_effect=run):
            wifi.connect(_net(), "secret")
        self.assertIn("802-11-wireless-security.key-mgmt", calls[1])

    def test_new_network_uses_device_connect(self):
        with mock.patch.object(wifi, "_run", return_value=(True, "")) as run:
            wifi.connect(_net(known=None), "secret")
        run.assert_called_once_with(["device", "wifi", "connect", "Home", "password", "secret"],
                                    wifi.CONNECT_TIMEOUT)


class NeedsPasswordTest(unittest.TestCase):
    def test_secrets_error_asks_password(self):
        self.assertTrue(wifi.needs_password(_net(), "Connection activation failed: Secrets were required, "
                                                    "but not provided"))

    def test_missing_network_does_not(self):
        self.assertFalse(wifi.needs_password(_net(), "No network with SSID 'Home' found."))

    def test_open_network_does_not(self):
        self.assertFalse(wifi.needs_password(_net(secure=False), "Secrets were required"))


if __name__ == "__main__":
    unittest.main()
