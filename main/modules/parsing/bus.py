from gi.repository import Gio

_cache = {}


def _get(kind):
    bus = _cache.get(kind)
    if bus is None:
        bus = Gio.bus_get_sync(kind, None)
        _cache[kind] = bus
    return bus


def system():
    return _get(Gio.BusType.SYSTEM)


def session():
    return _get(Gio.BusType.SESSION)
