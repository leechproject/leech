import faulthandler
import fcntl
import os
import struct
import sys
import termios
import threading
import time
from collections import Counter

from gi.repository import GLib

ENABLED = bool(os.environ.get("LEECH_DEBUG"))

WATCHDOG_SECONDS = 4
LAG_INTERVAL_MS = 100
LAG_REPORT_SECONDS = 0.2

_START = time.monotonic()
_LOCK = threading.Lock()


def log(tag, message):
    if not ENABLED:
        return
    stamp = time.monotonic() - _START
    with _LOCK:
        print(f"[{stamp:9.3f}] {tag}: {message}", file=sys.stderr, flush=True)


class Rate:
    def __init__(self, tag, threshold):
        self._tag = tag
        self._threshold = threshold
        self._lock = threading.Lock()
        self._window_start = time.monotonic()
        self._kinds = Counter()

    def hit(self, kind=""):
        if not ENABLED:
            return
        now = time.monotonic()
        with self._lock:
            elapsed = now - self._window_start
            if elapsed >= 1:
                total = sum(self._kinds.values())
                if total > self._threshold:
                    log(self._tag, f"{total} за {elapsed:.2f} с: {self._describe()}")
                self._kinds.clear()
                self._window_start = now
            self._kinds[kind] += 1
            if sum(self._kinds.values()) == self._threshold + 1:
                log(self._tag, f"всплеск: больше {self._threshold} в секунду")

    def _describe(self):
        return ", ".join(f"{kind or '?'}x{count}" for kind, count in self._kinds.most_common(8))


def pending_bytes(sock):
    try:
        raw = fcntl.ioctl(sock.fileno(), termios.FIONREAD, struct.pack("i", 0))
        return struct.unpack("i", raw)[0]
    except OSError:
        return -1


def watch_tray(watcher):
    if not ENABLED:
        return
    changes = Rate("tray", 10)

    def added(_watcher, identifier):
        log("tray", f"добавлен {identifier}")
        item = watcher.items.get(identifier)
        if item is not None:
            item.changed.connect(lambda *_: changes.hit(identifier))

    watcher.connect("item-added", added)
    watcher.connect("item-removed", lambda _w, identifier: log("tray", f"удалён {identifier}"))


def _arm_watchdog():
    faulthandler.dump_traceback_later(WATCHDOG_SECONDS, repeat=False)
    return True


def _start_lag_monitor():
    state = {"last": time.monotonic()}

    def tick():
        now = time.monotonic()
        lag = now - state["last"] - LAG_INTERVAL_MS / 1000
        state["last"] = now
        if lag > LAG_REPORT_SECONDS:
            log("loop", f"главный цикл опоздал на {lag * 1000:.0f} мс")
        return True

    GLib.timeout_add(LAG_INTERVAL_MS, tick)


def start():
    if not ENABLED:
        return
    log("debug", f"включён, pid {os.getpid()}")
    _arm_watchdog()
    GLib.timeout_add(1000, _arm_watchdog)
    _start_lag_monitor()
