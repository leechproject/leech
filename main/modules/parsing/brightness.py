import shutil
import subprocess
import threading
from pathlib import Path

from gi.repository import Gio, GLib

from modules import config
from modules.common import debug

_BASE = Path("/sys/class/backlight")
_PRIORITY = ("intel_backlight", "amdgpu_bl", "nvidia", "acpi_video")
_TIMEOUT_S = 2

_lock = threading.Lock()
_preferred = None
_reported = set()


def percent_to_raw(percent, maximum, exponent=1.0):
    percent = max(0, min(100, percent))
    return max(1, round(maximum * (percent / 100) ** exponent))


def raw_to_percent(raw, maximum, exponent=1.0):
    if maximum <= 0:
        return 0
    return round(100 * (max(0, min(raw, maximum)) / maximum) ** (1 / exponent))


def device():
    try:
        names = sorted(p.name for p in _BASE.iterdir())
    except OSError:
        return None
    for prefix in _PRIORITY:
        for name in names:
            if name.startswith(prefix):
                return name
    return names[0] if names else None


def _read_int(path):
    try:
        return int(Path(path).read_text().strip())
    except (OSError, ValueError):
        return None


def read_raw():
    name = device()
    if name is None:
        return None
    raw = _read_int(_BASE / name / "brightness")
    maximum = _read_int(_BASE / name / "max_brightness")
    if raw is None or not maximum:
        return None
    return raw, maximum


def to_percent(raw, maximum):
    return raw_to_percent(raw, maximum, config.BRIGHTNESS_EXPONENT)


def read():
    value = read_raw()
    return None if value is None else to_percent(*value)


def _report(message):
    debug.log("brightness", message)
    with _lock:
        if message in _reported:
            return
        _reported.add(message)
    print(f"brightness: {message}")


def _brightnessctl(name, raw):
    subprocess.run(["brightnessctl", "-q", "-d", name, "set", str(raw)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                   timeout=_TIMEOUT_S, check=True)


def _logind(name, raw):
    bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    bus.call_sync("org.freedesktop.login1", "/org/freedesktop/login1/session/auto",
                  "org.freedesktop.login1.Session", "SetBrightness",
                  GLib.Variant("(ssu)", ("backlight", name, raw)), None,
                  Gio.DBusCallFlags.NONE, _TIMEOUT_S * 1000, None)


def _sysfs(name, raw):
    (_BASE / name / "brightness").write_text(str(raw))


def _backends():
    backends = []
    if shutil.which("brightnessctl"):
        backends.append(("brightnessctl", _brightnessctl))
    backends.append(("logind", _logind))
    backends.append(("sysfs", _sysfs))
    if _preferred is not None:
        backends.sort(key=lambda b: b[0] != _preferred)
    return backends


def _describe(error):
    if isinstance(error, subprocess.CalledProcessError):
        return (error.stderr or b"").decode(errors="replace").strip() or f"код {error.returncode}"
    return getattr(error, "message", None) or str(error)


def write(percent):
    global _preferred
    name = device()
    if name is None:
        return None
    maximum = _read_int(_BASE / name / "max_brightness")
    if not maximum:
        return None
    raw = percent_to_raw(percent, maximum, config.BRIGHTNESS_EXPONENT)
    for label, backend in _backends():
        try:
            backend(name, raw)
        except (GLib.Error, OSError, subprocess.SubprocessError) as e:
            _report(f"{label}: {_describe(e)}")
            continue
        actual = _read_int(_BASE / name / "brightness")
        if actual == raw:
            if _preferred != label:
                debug.log("brightness", f"бэкенд {label}")
                _preferred = label
            return actual
        _report(f"{label}: записано {raw}, в sysfs {actual}")
    return None


def watch(callback):
    name = device()
    if name is None:
        return False
    path = _BASE / name / "actual_brightness"
    try:
        stream = open(path, "rb", buffering=0)
        stream.read()
    except OSError as e:
        _report(f"не слежу за {path}: {e}")
        return False
    maximum = _read_int(_BASE / name / "max_brightness") or 0

    def on_event(_fd, _condition):
        stream.seek(0)
        try:
            raw = int(stream.read().strip())
        except (OSError, ValueError):
            return True
        if maximum:
            callback(raw, maximum)
        return True

    watch.stream = stream
    GLib.io_add_watch(stream.fileno(), GLib.PRIORITY_DEFAULT,
                      GLib.IOCondition.PRI | GLib.IOCondition.ERR, on_event)
    return True
