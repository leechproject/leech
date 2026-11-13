import unittest
from unittest import mock

from modules import config
from modules.animations import anim
from modules.config.values import Duration, Invalid


class DurationTest(unittest.TestCase):
    def test_units(self):
        d = Duration()
        self.assertEqual(d.parse("1000ms", None), d.parse("1s", None))
        self.assertEqual(d.parse("0.5s", None), 500)
        self.assertEqual(d.parse("220 ms", None), 220)
        self.assertEqual(d.parse("0ms", None), 0)

    def test_rejects(self):
        for raw in ("220", "abc", "-1s", "11s", "ms", "1.2.3s"):
            with self.assertRaises(Invalid, msg=raw):
                Duration().parse(raw, None)


class ScaleTest(unittest.TestCase):
    def test_scaled_durations(self):
        with mock.patch.object(config, "ANIMATION_MS", 440):
            self.assertEqual(anim.ms(), 440)
            self.assertEqual(anim.ms(140), 280)
        with mock.patch.object(config, "ANIMATION_MS", 0):
            self.assertEqual(anim.ms(500), 0)

    def test_zero_duration_finishes_at_once(self):
        ticks, done = [], []
        anim.Tween(0, ticks.append).run((0.0,), (1.0,), lambda: done.append(True))
        self.assertEqual((ticks, done), ([(1.0,)], [True]))


class _Clock:
    def __init__(self):
        self.time = 0

    def get_frame_time(self):
        return self.time


class _Widget:
    def __init__(self, mapped=True):
        self.mapped = mapped
        self.clock = _Clock()
        self.callbacks = {}
        self._next = 0

    def get_mapped(self):
        return self.mapped

    def get_frame_clock(self):
        return self.clock if self.mapped else None

    def add_tick_callback(self, callback):
        self._next += 1
        self.callbacks[self._next] = callback
        return self._next

    def remove_tick_callback(self, tick):
        self.callbacks.pop(tick, None)

    def frame(self, time):
        self.clock.time = time
        for tick, callback in list(self.callbacks.items()):
            if not callback(self, self.clock):
                self.callbacks.pop(tick, None)


class FrameClockTest(unittest.TestCase):
    def setUp(self):
        self.now = 1_000_000
        patcher = mock.patch.object(anim.GLib, "get_monotonic_time", lambda: self.now)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_ticks_follow_frame_time(self):
        widget, ticks, done = _Widget(), [], []
        tween = anim.Tween(100, ticks.append, widget)
        tween.run((0.0,), (1.0,), lambda: done.append(True))
        widget.frame(self.now + 50_000)
        self.assertAlmostEqual(ticks[-1][0], 1 - 0.5 ** 3)
        self.assertTrue(tween.running())
        widget.frame(self.now + 100_000)
        self.assertEqual((ticks[-1], done, tween.running(), widget.callbacks), ((1.0,), [True], False, {}))

    def test_finish_jumps_to_end(self):
        widget, ticks, done = _Widget(), [], []
        tween = anim.Tween(100, ticks.append, widget)
        tween.run((0.0,), (4.0,), lambda: done.append(True))
        tween.finish()
        self.assertEqual((ticks, done, tween.running(), widget.callbacks), ([(4.0,)], [True], False, {}))

    def test_restart_from_done_keeps_new_run(self):
        widget, ticks = _Widget(), []
        tween = anim.Tween(100, ticks.append, widget)
        tween.run((0.0,), (1.0,), lambda: tween.run((1.0,), (0.0,)))
        widget.frame(self.now + 100_000)
        self.assertTrue(tween.running())
        self.assertEqual(len(widget.callbacks), 1)

    def test_unrealized_widget_uses_timer(self):
        widget = _Widget(mapped=False)
        tween = anim.Tween(100, lambda v: None, widget)
        tween.run((0.0,), (1.0,))
        self.assertEqual(widget.callbacks, {})
        self.assertTrue(tween.running())
        tween.stop()
        self.assertFalse(tween.running())


if __name__ == "__main__":
    unittest.main()
