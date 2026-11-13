"""Colours, corner radii, font sizes and spacings of everything leech paints itself with cairo,
taken from style.css. Sizes the owner sets in leech.conf stay there.

Each entry is a CSS rule on an id that no real widget uses, e.g.

    #launcher-row         { background-color: #090909; border-radius: 10px; color: #ffffff; }
    #launcher-row.active  { background-color: #111111; }

and is read through a probe widget: background-color, color, border-radius, font-size, padding
and margin of the rule with its classes applied. padding is the inner spacing (from the plate's
edge to its content), margin the spacing between neighbouring items or to the outside. DEFAULTS repeat every rule; they are loaded as a fallback stylesheet below
style.css, so a rule removed from style.css falls back to the default, and in tests (no
stylesheets at all) the defaults are used directly.

The probe is a DrawingArea (CSS node "widget"): style.css styles box, label and button by type,
and a type rule from style.css would beat an id rule from the fallback stylesheet.
"""

import re

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

# selector: {property: value}. A selector with classes inherits the properties of the bare id.
DEFAULTS = {
    # Every black surface: frame, notch, CC, launcher, dock, picker, taskbar, popups.
    "#leech-surface": {"background-color": "#000000", "border-radius": 10},
    # Style `sep`: the gap of the dock, launcher, picker and CC from the frame.
    "#leech-separate": {"margin": 5},
    "#leech-frame": {"border-radius": 10},
    # Outlines (the `outline` parameters): background-color is the outer layer, color the inner one.
    "#leech-outline": {"background-color": "#000000", "color": "#ffffff"},

    "#notch-idle-plate": {"background-color": "#111111", "border-radius": 10, "color": "#ffffff"},
    # Notch menus: padding from the notch edge to the buttons, margin between buttons.
    "#notch-menu": {"padding": 9, "margin": 6},
    # Player: padding from the notch edge, margin between the cover and the timeline.
    "#notch-player": {"padding": 5, "margin": 5},
    "#notch-cover": {"background-color": "#090909", "border-radius": 8},
    "#notch-timeline": {"background-color": "#242424", "color": "#ffffff", "margin": 5},

    # CC: padding of every block from the CC edge and between buttons; push: padding around the card;
    # push card: padding from the card edge to its content.
    "#cc-body": {"padding": 6},
    "#cc-push": {"padding": 5},
    "#cc-push-card": {"padding": 6},
    "#cc-calendar-plate": {"background-color": "#090909", "border-radius": 10, "color": "#ffffff",
                           "padding": "8px 7px"},
    "#cc-calendar-plate.expanded": {"background-color": "#121212"},
    "#cc-calendar-plate.focus": {"background-color": "#1b1b1b"},
    "#cc-calendar-plate.expanded.focus": {"background-color": "#242424"},
    "#cc-calendar-weekday": {"color": "#8a8a8a", "font-size": 11},
    "#cc-calendar-day": {"color": "#ffffff"},
    "#cc-calendar-day.other": {"color": "#454545"},
    "#cc-calendar-day.today": {"background-color": "#ffffff", "border-radius": 8, "color": "#000000"},
    "#cc-slider": {"background-color": "#090909", "border-radius": 10, "color": "#ffffff", "padding": 8},
    "#cc-slider.muted": {"color": "#666666"},
    "#cc-slider-glyph": {"color": "#ffffff", "font-size": 22},
    "#cc-slider-glyph.filled": {"color": "#000000"},
    "#cc-handle": {"background-color": "#ffffff", "padding": 5},
    # The cross shown while the flood guard drops notifications.
    "#cc-flood": {"color": "#ffffff"},
    "#screenshot-overlay": {"background-color": "rgba(0, 0, 0, 0.25)", "color": "rgba(255, 255, 255, 0.9)"},

    "#cc-record": {"background-color": "#000000", "border-radius": 10, "color": "#ffffff", "padding": 6,
                   "font-size": 14},
    "#cc-record-message": {"font-size": 11},
    "#cc-record.recording": {"background-color": "#ffffff", "color": "#000000"},
    "#cc-record-button": {"background-color": "#090909", "border-radius": 8, "color": "#ffffff", "font-size": 20},
    "#cc-record-button.recording": {"background-color": "#d1d1d1", "color": "#000000"},
    "#cc-record-button.hover": {"background-color": "#1b1b1b", "color": "#ffffff"},
    "#cc-record-tray": {"background-color": "#090909", "border-radius": 8, "padding": 5, "font-size": 14},
    "#cc-record-item": {"background-color": "#090909", "border-radius": 6, "color": "#ffffff", "font-size": 16},
    "#cc-record-item.on": {"background-color": "#ffffff", "color": "#000000"},
    "#cc-record-item.hover": {"background-color": "#1b1b1b", "color": "#ffffff"},
    "#cc-record-item.on.hover": {"background-color": "#d1d1d1", "color": "#000000"},

    "#cc-net": {"background-color": "#090909", "border-radius": 10, "color": "#ffffff", "font-size": 13},
    "#cc-net-empty": {"font-size": 12},
    "#cc-net-glyph": {"font-size": 14},
    "#cc-net-lock": {"font-size": 10},
    "#cc-net-item": {"background-color": "#111111", "border-radius": 8, "color": "#ffffff", "font-size": 13},
    "#cc-net-item.hover": {"background-color": "#2c2c2c"},
    "#cc-net-item.on": {"background-color": "#ffffff", "color": "#000000"},
    "#cc-net-item.on.hover": {"background-color": "#d1d1d1"},
    "#cc-net-dim": {"color": "#8a8a8a", "font-size": 11},
    "#cc-net-dim.on": {"color": "#4d4d4d"},
    "#cc-net-menu": {"background-color": "#000000", "border-radius": 8, "font-size": 13},

    # Rows: padding left of the icon and right of the text, margin between the icon and the text.
    "#launcher-row": {"background-color": "#090909", "border-radius": 10, "color": "#ffffff",
                      "padding": "0px 2px 0px 4px", "margin": 5},
    "#launcher-row.active": {"background-color": "#111111"},
    # Search: padding from the launcher edge, margin to the list.
    "#launcher-search": {"background-color": "#121212", "border-radius": 10, "color": "#ffffff", "padding": 5,
                         "margin": 6},
    "#launcher-header": {"background-color": "#090909", "color": "#111111", "font-size": 14},
    "#launcher-header.hover": {"background-color": "#111111", "color": "#1c1c1c"},
    "#launcher-empty": {"color": "#666666"},
    # Context menus: launcher rows, Wi-Fi and Bluetooth rows.
    "#launcher-menu": {"background-color": "#000000", "border-radius": 10},
    "#launcher-menu-item": {"background-color": "#111111", "border-radius": 8, "color": "#ffffff", "padding": 5},
    "#launcher-menu-item.active": {"background-color": "#d1d1d1", "color": "#000000"},

    # Undercover launcher: margin from the screen edge and the taskbar.
    "#start-launcher": {"margin": 10},
    # Footer: padding from its edge to the avatar and buttons, margin between the avatar and the name.
    "#start-footer": {"background-color": "#090909", "border-radius": 10, "color": "#ffffff", "padding": 7,
                      "margin": 7},
    "#start-avatar": {"background-color": "#111111", "color": "#ffffff", "font-size": 15},
    "#start-button": {"background-color": "transparent", "border-radius": 8, "color": "#ffffff", "font-size": 15},
    "#start-button.hover": {"background-color": "#111111"},
    "#start-menu": {"background-color": "#000000", "border-radius": 10, "padding": 6},
    "#start-menu-item": {"background-color": "#090909", "border-radius": 8, "color": "#ffffff", "font-size": 14},
    "#start-menu-item.active": {"background-color": "#ffffff", "color": "#000000"},

    # Picker: padding from its edge, margin between thumbnails; cell padding is the frame width.
    "#picker": {"padding": 8, "margin": 8},
    "#picker-cell": {"background-color": "#090909", "border-radius": 15, "padding": 3},
    "#picker-cell.current": {"background-color": "#666666"},
    "#picker-cell.hover": {"background-color": "#ffffff"},
    "#picker-placeholder": {"background-color": "#0d0d0d"},
    "#picker-empty": {"color": "#666666", "font-size": 16},

    # padding: from the icon to the dots, margin: between dots.
    "#dock-dot": {"background-color": "#ffffff", "padding": 5, "margin": 2},
    # Taskbar: padding of its plates from its edges and between them.
    "#taskbar-plates": {"padding": 5},
    # Undercover tray window: padding around and between icons, margin above the taskbar.
    "#taskbar-tray-grid": {"padding": 6, "margin": 7},
    # Popups over the taskbar (tray, power profiles): margin from the frame or the screen edge.
    "#taskbar-popup": {"margin": 5},
    # Bar tray: padding at the ends of the expanded tray, margin between icons (scaled with the bar).
    "#systray-items": {"padding": 6, "margin": 6},
    "#wallpaper-fill": {"background-color": "#000000"},
}

_loaded = False
_cache = {}
_SELECTOR = re.compile(r"#([\w-]+)((?:\.[\w-]+)*)$")


def fallback_css():
    """DEFAULTS as a stylesheet, loaded below style.css."""
    rules = []
    for selector, props in DEFAULTS.items():
        body = " ".join(f"{name}: {_css_value(name, value)};" for name, value in props.items())
        rules.append(f"{selector} {{ {body} }}")
    return "\n".join(rules)


_PX = ("border-radius", "font-size", "padding", "margin")


def _css_value(name, value):
    if name in _PX and isinstance(value, int):
        return f"{value}px"
    return value


def _parse_box(value):
    """padding/margin: an int or a CSS shorthand ("8px 7px") as (top, right, bottom, left)."""
    if isinstance(value, int):
        return (value,) * 4
    v = [int(float(p.replace("px", ""))) for p in value.split()]
    if len(v) == 1:
        return (v[0],) * 4
    if len(v) == 2:
        return (v[0], v[1], v[0], v[1])
    if len(v) == 3:
        return (v[0], v[1], v[2], v[1])
    return tuple(v[:4])


def set_loaded():
    """Called once the stylesheets are installed: from now on values come from them."""
    global _loaded
    _loaded = True
    _cache.clear()


def _parse_color(text):
    text = text.strip()
    if text == "transparent":
        return (0.0, 0.0, 0.0, 0.0)
    if text.startswith("#"):
        return tuple(int(text[i:i + 2], 16) / 255 for i in (1, 3, 5)) + (1.0,)
    match = re.match(r"rgba?\(([^)]*)\)", text)
    parts = [float(p) for p in match.group(1).split(",")]
    alpha = parts[3] if len(parts) > 3 else 1.0
    return (parts[0] / 255, parts[1] / 255, parts[2] / 255, alpha)


def _default(selector, prop):
    """The default of selector, inheriting from the selectors with fewer of its classes."""
    match = _SELECTOR.match(selector)
    if match is None or f"#{match.group(1)}" not in DEFAULTS:
        raise KeyError(f"theme: нет правила {selector}")
    name, classes = match.group(1), [c for c in match.group(2).split(".") if c]
    value = None
    for candidate, props in DEFAULTS.items():
        m = _SELECTOR.match(candidate)
        own = [c for c in m.group(2).split(".") if c]
        if m.group(1) == name and set(own) <= set(classes) and prop in props:
            if value is None or len(own) >= value[0]:
                value = (len(own), props[prop])
    if value is None:
        raise KeyError(f"theme: у {selector} нет {prop}")
    return value[1]


def _from_css(selector, prop):
    match = _SELECTOR.match(selector)
    probe = Gtk.DrawingArea()
    probe.set_name(match.group(1))
    ctx = probe.get_style_context()
    for cls in (c for c in match.group(2).split(".") if c):
        ctx.add_class(cls)
    if prop == "border-radius":
        return ctx.get_property("border-radius", Gtk.StateFlags.NORMAL)
    if prop == "font-size":
        return ctx.get_property("font-size", Gtk.StateFlags.NORMAL)
    if prop in ("padding", "margin"):
        b = (ctx.get_padding if prop == "padding" else ctx.get_margin)(Gtk.StateFlags.NORMAL)
        return (b.top, b.right, b.bottom, b.left)
    if prop == "color":
        c = ctx.get_color(Gtk.StateFlags.NORMAL)
    else:
        c = ctx.get_property("background-color", Gtk.StateFlags.NORMAL)
    return (c.red, c.green, c.blue, c.alpha)


def _get(selector, prop):
    key = (selector, prop)
    if key in _cache:
        return _cache[key]
    default = _default(selector, prop)
    if not _loaded:
        if prop in ("padding", "margin"):
            return _parse_box(default)
        if prop in ("border-radius", "font-size"):
            return default
        return _parse_color(default)
    value = _from_css(selector, prop)
    _cache[key] = value
    return value


def bg(selector):
    """background-color as (r, g, b, a)."""
    return _get(selector, "background-color")


def fg(selector):
    """color as (r, g, b, a)."""
    return _get(selector, "color")


def radius(selector):
    """border-radius in px."""
    return _get(selector, "border-radius")


def font(selector):
    """font-size in px."""
    return _get(selector, "font-size")


def padding(selector):
    """padding as (top, right, bottom, left)."""
    return _get(selector, "padding")


def pad(selector):
    """The left padding: the spacing of rules that set one value."""
    return padding(selector)[3]


def gap(selector):
    """The left margin: the spacing of rules that set one value."""
    return _get(selector, "margin")[3]


def outline_layers():
    """Outline layers from the outer edge inwards."""
    return (bg("#leech-outline"), fg("#leech-outline"))
