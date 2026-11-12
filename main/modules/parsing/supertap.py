import os
import re
import select
import struct
import threading

from gi.repository import Gio, GLib

from modules.common import debug

EV_KEY = 1
EV_REL = 2
REL_HWHEEL = 6
REL_WHEEL = 8
REL_WHEEL_HI_RES = 11
REL_HWHEEL_HI_RES = 12
SCROLL_CODES = frozenset((REL_HWHEEL, REL_WHEEL, REL_WHEEL_HI_RES, REL_HWHEEL_HI_RES))
SUPER_KEYS = frozenset((125, 126))
TAP_SECONDS = 0.5

EVENT = struct.Struct("llHHi")
DEVICES_FILE = "/proc/bus/input/devices"
KEY_BIT = 1 << EV_KEY


def key_devices(text):
    result = []
    for block in text.split("\n\n"):
        handlers = re.search(r"^H: Handlers=(.*)$", block, re.M)
        events = re.search(r"^B: EV=([0-9a-f]+)$", block, re.M)
        if not handlers or not events or not int(events.group(1), 16) & KEY_BIT:
            continue
        result += [f"/dev/input/{name}" for name in handlers.group(1).split() if name.startswith("event")]
    return result


class TapDetector:
    def __init__(self, limit=TAP_SECONDS):
        self._limit = limit
        self._held = set()
        self._armed_at = None

    def feed(self, kind, code, value, when):
        if kind == EV_REL and code in SCROLL_CODES:
            self._armed_at = None
            return False
        if kind != EV_KEY:
            return False
        if code in SUPER_KEYS:
            if value == 1:
                self._armed_at = when if not (self._held - SUPER_KEYS) else None
                self._held.add(code)
                return False
            if value == 0:
                self._held.discard(code)
                armed, self._armed_at = self._armed_at, None
                return armed is not None and when - armed <= self._limit and not self._held
            return False
        if value == 0:
            self._held.discard(code)
        else:
            self._held.add(code)
            self._armed_at = None
        return False


class SuperTap:
    def __init__(self, on_tap):
        self._on_tap = on_tap
        self._wake_read, self._wake_write = os.pipe()
        self._monitor = None

    def start(self):
        self._monitor = Gio.File.new_for_path("/dev/input").monitor_directory(Gio.FileMonitorFlags.NONE, None)
        self._monitor.connect("changed", lambda *_: os.write(self._wake_write, b"x"))
        threading.Thread(target=self._run, daemon=True).start()

    def _open_devices(self, opened):
        try:
            with open(DEVICES_FILE, encoding="utf-8", errors="replace") as f:
                wanted = set(key_devices(f.read()))
        except OSError:
            wanted = set()
        for path in list(opened):
            if path not in wanted:
                os.close(opened.pop(path))
        for path in wanted - set(opened):
            try:
                opened[path] = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
            except OSError as e:
                debug.log("supertap", f"{path}: {e}")
        if not opened:
            print("leech: нет доступа к /dev/input (нужна группа input), лаунчер по Super не работает")

    def _run(self):
        opened = {}
        detector = TapDetector()
        self._open_devices(opened)
        while True:
            ready, _, _ = select.select([self._wake_read, *opened.values()], [], [])
            if self._wake_read in ready:
                os.read(self._wake_read, 4096)
                self._open_devices(opened)
                continue
            for fd in ready:
                try:
                    data = os.read(fd, EVENT.size * 64)
                except BlockingIOError:
                    continue
                except OSError:
                    self._open_devices(opened)
                    break
                for offset in range(0, len(data) - EVENT.size + 1, EVENT.size):
                    sec, usec, kind, code, value = EVENT.unpack_from(data, offset)
                    if detector.feed(kind, code, value, sec + usec / 1e6):
                        GLib.idle_add(self._emit)

    def _emit(self):
        self._on_tap()
        return False
