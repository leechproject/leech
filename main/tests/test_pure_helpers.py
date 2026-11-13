import datetime
import unittest

from modules.parsing import audio
from modules.parsing import brightness
from modules.cc import calendar_grid
from modules.parsing import media
from modules.common import timefmt
from unittest import mock

from modules.notifications import notifications
from modules.cc.floodguard import FloodGuard
from modules.notifications.notifications import Notification


class CalendarTest(unittest.TestCase):
    def test_monday_start(self):
        grid = calendar_grid.month_grid(2026, 11, 0)
        self.assertEqual(len(grid), 42)
        self.assertEqual(grid[0], (datetime.date(2026, 10, 26), False))
        self.assertEqual(grid[6], (datetime.date(2026, 11, 1), True))
        self.assertEqual(sum(in_month for _, in_month in grid), 30)

    def test_sunday_start(self):
        grid = calendar_grid.month_grid(2026, 11, 6)
        self.assertEqual(grid[0], (datetime.date(2026, 11, 1), True))

    def test_shift_month(self):
        self.assertEqual(calendar_grid.shift_month(2026, 12, 1), (2027, 1))
        self.assertEqual(calendar_grid.shift_month(2026, 1, -1), (2025, 12))
        self.assertEqual(calendar_grid.shift_month(2026, 5, -17), (2024, 12))

    def test_weekday_labels(self):
        self.assertEqual(calendar_grid.weekday_labels(0)[0], "Mo")
        self.assertEqual(calendar_grid.weekday_labels(6), ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"])


class TimefmtTest(unittest.TestCase):
    def test_clock(self):
        self.assertEqual(timefmt.clock(65_000_000), "1:05")
        self.assertEqual(timefmt.clock(3_725_000_000), "1:02:05")
        self.assertEqual(timefmt.clock(-5), "0:00")

    def test_progress(self):
        self.assertEqual(timefmt.progress(30_000_000, 90_000_000), "0:30/1:00")
        self.assertEqual(timefmt.progress(100_000_000, 90_000_000), "1:30/0:00")
        self.assertEqual(timefmt.progress(5_000_000, 0), "0:05/0:00")

    def test_stopwatch(self):
        self.assertEqual(timefmt.stopwatch(5), "00:05")
        self.assertEqual(timefmt.stopwatch(3661), "1:01:01")


class AudioParseTest(unittest.TestCase):
    def test_wpctl(self):
        self.assertEqual(audio.parse_wpctl("Volume: 0.45 [MUTED]\n"), (45, True))
        self.assertEqual(audio.parse_wpctl("Volume: 1.00\n"), (100, False))
        self.assertIsNone(audio.parse_wpctl("garbage"))

    def test_pactl(self):
        output = "Volume: front-left: 32768 /  50% / -18.06 dB,   front-right: 32768 /  50% / -18.06 dB"
        self.assertEqual(audio.parse_pactl_volume(output), 50)
        self.assertIsNone(audio.parse_pactl_volume(""))
        self.assertTrue(audio.parse_pactl_mute("Mute: yes"))
        self.assertFalse(audio.parse_pactl_mute("Mute: no"))


class BrightnessConvertTest(unittest.TestCase):
    def test_percent_to_raw(self):
        self.assertEqual(brightness.percent_to_raw(0, 255), 1)
        self.assertEqual(brightness.percent_to_raw(100, 255), 255)
        self.assertEqual(brightness.percent_to_raw(50, 255), 128)
        self.assertEqual(brightness.percent_to_raw(150, 100), 100)

    def test_raw_to_percent(self):
        self.assertEqual(brightness.raw_to_percent(128, 255), 50)
        self.assertEqual(brightness.raw_to_percent(10, 0), 0)


class FloodGuardTest(unittest.TestCase):
    def test_triggers_on_count(self):
        guard = FloodGuard(3, 3.0)
        self.assertFalse(guard.hit(0))
        self.assertFalse(guard.hit(1))
        self.assertTrue(guard.hit(2))
        self.assertFalse(guard.hit(2.5))

    def test_window_expires(self):
        guard = FloodGuard(3, 3.0)
        guard.hit(0)
        guard.hit(1)
        self.assertFalse(guard.hit(4))

    def test_reset(self):
        guard = FloodGuard(3, 3.0)
        guard.hit(0)
        guard.hit(0.5)
        guard.reset()
        self.assertFalse(guard.hit(1))

    @staticmethod
    def _n(nid, summary="s", app="app", local=False, replaced=False):
        return Notification(nid, app, summary, "", None, -1, 1, 0.0, local=local, replaced=replaced)

    def test_distinct_notifications_trigger(self):
        guard = FloodGuard(3, 3.0)
        self.assertFalse(guard.register(self._n(1, "a"), now=0))
        self.assertFalse(guard.register(self._n(2, "b"), now=0.5))
        self.assertTrue(guard.register(self._n(3, "c"), now=1))

    def test_updates_and_local_not_counted(self):
        guard = FloodGuard(3, 3.0)
        guard.register(self._n(1, "Connecting"), now=0)
        self.assertFalse(guard.register(self._n(1, "Connected", replaced=True), now=0.1))
        self.assertFalse(guard.register(self._n(2, "Screenshot saved", local=True), now=0.2))
        self.assertFalse(guard.register(self._n(3, "Battery 80%"), now=0.3))
        self.assertTrue(guard.register(self._n(4, "Third"), now=0.4))

    def test_identical_spam_counts(self):
        guard = FloodGuard(3, 3.0)
        self.assertFalse(guard.register(self._n(1, "Telegram"), now=0))
        self.assertFalse(guard.register(self._n(2, "Telegram"), now=0.25))
        self.assertTrue(guard.register(self._n(3, "Telegram"), now=0.5))


class NotificationServerTest(unittest.TestCase):
    def test_replaced_only_for_issued_ids(self):
        server = notifications.NotificationServer(lambda n: None)
        with mock.patch.object(notifications, "resolve_icon", return_value=None):
            first = server._make("app", 0, "", "a", "", {}, -1)
            update = server._make("app", first.id, "", "b", "", {}, -1)
            foreign = server._make("app", 999, "", "c", "", {}, -1)
            local = server._make("leech", 0, "", "d", "", {}, -1, local=True)
        self.assertFalse(first.replaced)
        self.assertTrue(update.replaced)
        self.assertEqual(update.id, first.id)
        self.assertFalse(foreign.replaced)
        self.assertTrue(local.local)


class MediaTest(unittest.TestCase):
    def test_pick_player(self):
        players = [("a", "Stopped", {}), ("b", "Paused", {}), ("c", "Playing", {})]
        self.assertEqual(media.pick_player(players)[0], "c")
        self.assertEqual(media.pick_player(players[:2])[0], "b")
        self.assertIsNone(media.pick_player(players[:1]))

    def test_make_track(self):
        self.assertEqual(media.make_track(None), media.Track())
        track = media.make_track(("p", "Playing", {"xesam:title": "T", "xesam:artist": ["A", "B"],
                                                    "mpris:length": 5}))
        self.assertEqual((track.title, track.artist, track.playing, track.length), ("T", "A, B", True, 5))
        self.assertTrue(track.available)
        self.assertEqual(media.make_track(("p", "Paused", {})).title, "Unknown")

    def test_art_path(self):
        self.assertEqual(media.art_path("file:///tmp/a%20b.png"), "/tmp/a b.png")
        self.assertIsNone(media.art_path("https://example.org/a.png"))


if __name__ == "__main__":
    unittest.main()
