import time

from modules.common import debug


class FloodGuard:

    def __init__(self, count, window):
        self._count = count
        self._window = window
        self._times = []

    def hit(self, now=None):
        now = time.monotonic() if now is None else now
        self._times = [t for t in self._times if now - t < self._window] + [now]
        if len(self._times) >= self._count:
            self._times = []
            return True
        return False

    def register(self, n, now=None):
        reason = skip_reason(n)
        result = reason or ("flood" if self.hit(now) else "counted")
        debug.log("flood", f"id={n.id} {result}")
        return result == "flood"

    def reset(self):
        self._times = []


def skip_reason(n):
    if n.local:
        return "local"
    if n.replaced:
        return "update"
    return None
