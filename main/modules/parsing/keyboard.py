import functools
import re
import xml.etree.ElementTree as ET
from pathlib import Path

REGISTRIES = ("/usr/share/X11/xkb/rules/evdev.xml", "/usr/share/xkeyboard-config-2/rules/evdev.xml",
              "/usr/share/X11/xkb/rules/base.xml")


def parse_registry(root):
    names = {}
    for layout in root.iter("layout"):
        item = layout.find("configItem")
        if item is None:
            continue
        short = (item.findtext("shortDescription") or item.findtext("name") or "").strip()
        description = (item.findtext("description") or "").strip()
        if description and short:
            names.setdefault(description, short)
        for variant in layout.iter("variant"):
            vitem = variant.find("configItem")
            if vitem is None:
                continue
            vdescription = (vitem.findtext("description") or "").strip()
            vshort = (vitem.findtext("shortDescription") or short).strip()
            if vdescription and vshort:
                names.setdefault(vdescription, vshort)
    return names


@functools.lru_cache(maxsize=1)
def _registry():
    for path in REGISTRIES:
        try:
            return parse_registry(ET.parse(path).getroot())
        except (OSError, ET.ParseError):
            continue
    return {}


def fallback(description):
    letters = re.sub(r"[^a-z]", "", description.lower())
    return letters[:2]


def short_name(description, registry=None):
    description = (description or "").strip()
    if not description:
        return ""
    names = _registry() if registry is None else registry
    short = names.get(description) or fallback(description)
    return short.lower()


LEDS = Path("/sys/class/leds")
CAPS_POLL_MS = 200
CAPS_RESCAN_TICKS = 25


def caps_lock_leds(root=LEDS):
    """Файлы яркости светодиодов Caps Lock всех клавиатур (`inputN::capslock`)."""
    return sorted(root.glob("*::capslock/brightness"))


def caps_lock_on(paths):
    """Caps Lock включён, если горит светодиод хотя бы одной клавиатуры."""
    for path in paths:
        try:
            if int(path.read_text().strip() or 0) > 0:
                return True
        except (OSError, ValueError):
            continue
    return False


def layout_text(layout, caps):
    return layout.upper() if caps else layout


class CapsLockWatch:
    """Следит за светодиодом Caps Lock. Его ставит композитор, поэтому способ одинаков для любого WM.

    sysfs светодиодов не шлёт уведомлений, поэтому опрос: чтение файла в пару байт раз в 200 мс.
    Список клавиатур перечитывается раз в 5 с (подключение новой клавиатуры).
    """

    def __init__(self):
        self.on = False
        self._callbacks = []
        self._paths = []
        self._ticks = 0
        self._source = 0

    def subscribe(self, callback):
        from gi.repository import GLib
        self._callbacks.append(callback)
        if not self._source:
            self._paths = caps_lock_leds()
            self.on = caps_lock_on(self._paths)
            self._source = GLib.timeout_add(CAPS_POLL_MS, self._poll)

    def _poll(self):
        self._ticks += 1
        if self._ticks >= CAPS_RESCAN_TICKS:
            self._ticks = 0
            self._paths = caps_lock_leds()
        on = caps_lock_on(self._paths)
        if on != self.on:
            self.on = on
            for callback in list(self._callbacks):
                callback()
        return True


caps_lock = CapsLockWatch()
