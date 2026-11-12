from collections import OrderedDict

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gio, Gtk, GLib

from modules import config


class IconCache:
    def __init__(self, limit=80):
        self._theme = Gtk.IconTheme.get_default()
        self._cache = OrderedDict()
        self._limit = limit

    def get(self, app_id, info):
        pixbuf = self._cache.get(app_id)
        if pixbuf is None:
            pixbuf = self._load(info)
            self._cache[app_id] = pixbuf
            while len(self._cache) > self._limit:
                self._cache.popitem(last=False)
        else:
            self._cache.move_to_end(app_id)
        return pixbuf

    def _load(self, info):
        return load_icon(info, config.DOCK_ICON)


FALLBACK = "application-x-executable"
_FLAGS = Gtk.IconLookupFlags.FORCE_SIZE


def app_gicon(info, size=None):
    theme = Gtk.IconTheme.get_default()
    gicon = info.get_icon()
    if gicon is not None and theme.lookup_by_gicon(gicon, size or config.DOCK_ICON, _FLAGS) is not None:
        return gicon
    return Gio.ThemedIcon.new(FALLBACK)


def load_icon(info, size, scale=1):
    theme = Gtk.IconTheme.get_default()
    found = theme.lookup_by_gicon_for_scale(app_gicon(info, size), size, scale, _FLAGS)
    try:
        return found.load_icon() if found is not None else None
    except GLib.Error:
        return None
