import threading

from gi.repository import GLib

from modules.parsing import audio
from modules.parsing import brightness

from modules import config


class Controls:
    def __init__(self):
        self.volume = 0
        self.muted = False
        self.brightness = 0
        self._subscribers = []
        self._lock = threading.Lock()
        self._latest = {"volume": None, "brightness": None}
        self._busy = {"volume": False, "brightness": False}
        self._backlight_raw = None
        brightness.watch(self._on_backlight)

    def subscribe(self, callback):
        self._subscribers.append(callback)

    def _notify(self, kind, osd):
        for callback in list(self._subscribers):
            callback(kind, osd)

    def refresh(self):
        def work():
            return audio.read(), brightness.read_raw()

        def done(result):
            volume, backlight = result
            if volume is not None:
                self.volume, self.muted = volume
                self._notify("volume", False)
            if backlight is not None:
                self._on_backlight(*backlight, force=True)

        audio.in_thread(work, done)

    def _on_backlight(self, raw, maximum, force=False):
        with self._lock:
            if self._busy["brightness"] or raw == self._backlight_raw:
                return
            self._backlight_raw = raw
        level = max(1, brightness.to_percent(raw, maximum))
        if level != self.brightness or force:
            self.brightness = level
            self._notify("brightness", False)

    def step_volume(self, direction):
        self.set_volume(self.volume + direction * config.CONTROL_STEP, osd=True)

    def step_brightness(self, direction):
        self.set_brightness(self.brightness + direction * config.CONTROL_STEP, osd=True)

    def set_volume(self, percent, osd=False):
        self.volume = max(0, min(100, int(percent)))
        self._notify("volume", osd)
        self._write("volume", self.volume)

    def set_brightness(self, percent, osd=False):
        self.brightness = max(1, min(100, int(percent)))
        self._notify("brightness", osd)
        self._write("brightness", self.brightness)

    def toggle_mute(self):
        self.muted = not self.muted
        self._notify("volume", True)
        audio.in_thread(audio.toggle_mute)

    def _write(self, kind, value):
        with self._lock:
            self._latest[kind] = value
            if self._busy[kind]:
                return
            self._busy[kind] = True
        writer = audio.write_volume if kind == "volume" else brightness.write

        def work():
            written = None
            while True:
                with self._lock:
                    value = self._latest[kind]
                    self._latest[kind] = None
                    if value is None:
                        self._busy[kind] = False
                        if kind == "brightness":
                            self._backlight_raw = written
                            if written is None:
                                GLib.idle_add(self._resync_backlight)
                        return
                written = writer(value)

        threading.Thread(target=work, daemon=True).start()

    def _resync_backlight(self):
        backlight = brightness.read_raw()
        if backlight is not None:
            self._on_backlight(*backlight, force=True)
        return False
