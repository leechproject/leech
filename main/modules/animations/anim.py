from gi.repository import GLib

from modules import config

BASE_MS = 220
GUARD_MS = 250


def ms(base=BASE_MS):
    return max(0, round(base * config.ANIMATION_MS / BASE_MS))


def _owner(on_tick):
    owner = getattr(on_tick, "__self__", None)
    return owner if hasattr(owner, "add_tick_callback") else None


def _ease(t):
    return 1 - (1 - t) ** 3


class Tween:
    def __init__(self, duration_ms, on_tick, widget=None):
        self._duration = duration_ms
        self._on_tick = on_tick
        self._widget = widget if widget is not None else _owner(on_tick)
        self._source = 0
        self._tick = 0
        self._guard = 0
        self._end = None

    def run(self, start, end, on_done=None):
        self.stop()
        if self._duration <= 0:
            self._on_tick(tuple(end))
            if on_done:
                on_done()
            return
        t0 = GLib.get_monotonic_time()
        span = self._duration * 1000
        self._end = lambda: apply(t0 + span, owned=False)

        def apply(now, owned=True):
            t = min(1.0, max(0.0, (now - t0) / span))
            k = _ease(t)
            self._on_tick(tuple(a + (b - a) * k for a, b in zip(start, end)))
            if t < 1.0:
                return True
            if owned:
                self._source = self._tick = 0
            self._clear()
            if on_done:
                on_done()
            return False

        widget = self._widget
        clock = widget.get_frame_clock() if widget is not None else None
        if clock is None:
            self._source = GLib.timeout_add(16, lambda: apply(GLib.get_monotonic_time()))
            return

        def on_frame(_widget, frame_clock):
            if not self._tick:
                return False
            return apply(max(frame_clock.get_frame_time(), t0))

        def on_guard():
            self._guard = 0
            if self._tick:
                apply(t0 + span, owned=False)
            return False

        self._tick = widget.add_tick_callback(on_frame)
        self._guard = GLib.timeout_add(self._duration + GUARD_MS, on_guard)

    def running(self):
        return bool(self._source or self._tick)

    def finish(self):
        if self.running() and self._end is not None:
            self._end()

    def _clear(self):
        self._end = None
        if self._source:
            GLib.source_remove(self._source)
            self._source = 0
        if self._tick:
            tick, self._tick = self._tick, 0
            self._widget.remove_tick_callback(tick)
        if self._guard:
            GLib.source_remove(self._guard)
            self._guard = 0

    def stop(self):
        self._clear()
