import os

from gi.repository import Gio, GLib

_fd = None


def is_on():
    return _fd is not None


def set_on(on):
    global _fd
    if on == is_on():
        return True
    if not on:
        os.close(_fd)
        _fd = None
        return True
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        reply, fd_list = bus.call_with_unix_fd_list_sync(
            "org.freedesktop.login1", "/org/freedesktop/login1", "org.freedesktop.login1.Manager",
            "Inhibit", GLib.Variant("(ssss)", ("idle", "leech", "Caffeine mode", "block")),
            GLib.VariantType("(h)"), Gio.DBusCallFlags.NONE, 1000, None, None)
        _fd = fd_list.get(reply.unpack()[0])
        return True
    except GLib.Error as e:
        print(f"caffeine: {e.message}")
        return False
