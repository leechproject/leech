CLASS_PREFIX = "color-"

DEFAULTS = {
    "silhouette": "#000000",
    "idle-plate": "#111111",
    "idle-text": "#ffffff",
    "timeline-track": "#232323",
    "timeline-fill": "#ffffff",
    "cover-fallback": "#080808",
    "launcher-empty-text": "#666666",
    "launcher-header": "#080808",
    "launcher-header-hover": "#111111",
    "launcher-eye": "#111111",
    "launcher-eye-hover": "#1c1c1c",
    "launcher-search": "#121212",
    "launcher-search-text": "#ffffff",
    "launcher-row": "#090909",
    "launcher-row-active": "#111111",
    "launcher-text": "#ffffff",
    "launcher-menu": "#000000",
    "launcher-menu-item": "#111111",
    "launcher-menu-item-active": "#d1d1d1",
    "launcher-menu-text": "#ffffff",
    "launcher-menu-text-active": "#000000",
    "picker-idle": "#090909",
    "picker-hover": "#ffffff",
    "picker-current": "#666666",
    "picker-empty-text": "#666666",
    "picker-thumb-fallback": "#0c0c0c",
    "wallpaper-base": "#000000",
    "calendar-plate": "#090909",
    "calendar-plate-active": "#121212",
    "calendar-text": "#ffffff",
    "calendar-weekday": "#8a8a8a",
    "calendar-day": "#ffffff",
    "calendar-day-dim": "#454545",
    "calendar-today": "#ffffff",
    "calendar-today-text": "#000000",
    "slider-plate": "#090909",
    "slider-fill": "#ffffff",
    "slider-fill-muted": "#666666",
    "slider-icon": "#ffffff",
    "slider-icon-filled": "#000000",
    "flood-cross": "#ffffff",
    "capture-dim": "rgba(0, 0, 0, 0.25)",
    "capture-border": "rgba(255, 255, 255, 0.9)",
}

_cache = {}
_probe = None
_reader = None


def base_css():
    return "\n".join(f".{CLASS_PREFIX}{name} {{ color: {value}; }}" for name, value in DEFAULTS.items()).encode()


def _read_style(name):
    global _probe
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk

    if _probe is None:
        _probe = Gtk.Label()
    context = _probe.get_style_context()
    for cls in context.list_classes():
        context.remove_class(cls)
    context.add_class(CLASS_PREFIX + name)
    rgba = context.get_color(Gtk.StateFlags.NORMAL)
    return (rgba.red, rgba.green, rgba.blue, rgba.alpha)


def set_reader(reader):
    global _reader
    _reader = reader
    refresh()


def refresh():
    _cache.clear()


def rgba(name):
    value = _cache.get(name)
    if value is None:
        if name not in DEFAULTS:
            raise KeyError(name)
        value = (_reader or _read_style)(name)
        _cache[name] = value
    return value


def rgb(name):
    return rgba(name)[:3]
