from pathlib import Path

ICON_CHARGING = "\uf0e7"
ICON_LEVELS = ("\uf240", "\uf241", "\uf242", "\uf243")

_BASE = Path("/sys/class/power_supply")
_path = None


def _read(entry, name):
    try:
        return (entry / name).read_text().strip()
    except OSError:
        return None


def _find():
    global _path
    if _path is None:
        for entry in sorted(_BASE.glob("*")):
            if _read(entry, "type") == "Battery" and _read(entry, "scope") != "Device":
                _path = entry
                break
    return _path


def read():
    path = _find()
    if path is None:
        return None
    try:
        return int((path / "capacity").read_text()), (path / "status").read_text().strip()
    except (OSError, ValueError):
        return None


def on_ac():
    seen = False
    for entry in sorted(_BASE.glob("*")):
        if _read(entry, "type") in (None, "Battery"):
            continue
        online = _read(entry, "online")
        if online is None:
            continue
        seen = True
        if online == "1":
            return True
    if seen:
        return False
    data = read()
    return None if data is None else data[1] != "Discharging"


def icon(percent, status, on_socket=False):
    if status == "Charging" or on_socket:
        return ICON_CHARGING
    for limit, glyph in zip((80, 50, 20), ICON_LEVELS):
        if percent > limit:
            return glyph
    return ICON_LEVELS[3]
