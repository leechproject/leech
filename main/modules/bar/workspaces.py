import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from modules import config
from modules.animations import anim
from modules.animations.anim import Tween
from modules.bar.numerals import workspace_symbol
from modules.common.glyph import GlyphLabel
from modules.common.shapes import rounded_rect
from modules.config.geometry import scaled

BUTTON_PADDING = scaled(4, config.BAR_SCALE)
SPACING = scaled(3, config.BAR_SCALE)
STATES = {"empty": "ws-empty", "occupied": "ws-occupied", "active": "ws-active"}


def _plate_style():
    probe = Gtk.Box()
    probe.set_name("ws-plate")
    ctx = probe.get_style_context()
    color = ctx.get_property("background-color", Gtk.StateFlags.NORMAL)
    return (color.red, color.green, color.blue, color.alpha), ctx.get_property("border-radius", Gtk.StateFlags.NORMAL)


def plate_rect(button, across, horizontal, gap, shrink=0):
    x, y, w, h = button
    if horizontal:
        x, y, w, h = x, gap, w, across - 2 * gap
    else:
        x, y, w, h = gap, y, across - 2 * gap, h
    inset = shrink / 2
    return x + inset, y + inset, w - shrink, h - shrink


def blend(start, end, t):
    return tuple(a + (b - a) * t for a, b in zip(start, end))


class _Button(Gtk.Button):
    def __init__(self, horizontal):
        super().__init__()
        self._horizontal = horizontal

    def do_get_preferred_width(self):
        minimum, natural = Gtk.Button.do_get_preferred_width(self)
        child = self.get_child()
        if not self._horizontal or child is None:
            return minimum, natural
        across = Gtk.Button.do_get_preferred_height(self)[1] + BUTTON_PADDING
        return max(minimum, across), max(natural, across)


class Workspaces(Gtk.Box):
    def __init__(self, wm, orientation, horizontal):
        super().__init__(orientation=orientation, spacing=SPACING)
        self._wm = wm
        self._horizontal = horizontal
        self._labels = {}
        self._buttons = {}
        self._active = None
        self._plate_from = None
        self._plate_t = 1.0
        self._plate_tween = Tween(anim.ms(), self._on_plate_tick)
        glyphs = any(config.WS_ICONS.values())
        for n in range(1, config.WORKSPACES + 1):
            text = workspace_symbol(n, "empty", config.WS_STYLE, config.WS_ICONS)
            label = GlyphLabel(label=text) if glyphs else Gtk.Label(label=text)
            label.set_name(STATES["empty"])
            button = _Button(horizontal)
            button.set_relief(Gtk.ReliefStyle.NONE)
            button.add(label)
            if config.WS_CLICKABLE:
                button.connect("clicked", lambda *_, ws=n: self._wm.goto(ws))
            self.pack_start(button, False, False, 0)
            self._labels[n] = label
            self._buttons[n] = button
        if config.WS_HIGHLIGHT:
            self._plate = _plate_style()
            self.connect("draw", self._draw_plate)

    def update(self, state):
        for n, label in self._labels.items():
            kind = "active" if n == state.active else ("occupied" if n in state.occupied else "empty")
            label.set_name(STATES[kind])
            label.set_label(workspace_symbol(n, kind, config.WS_STYLE, config.WS_ICONS))
            context = label.get_style_context()
            if kind == "active" and config.WS_HIGHLIGHT:
                context.add_class("on-plate")
            else:
                context.remove_class("on-plate")
        if state.active != self._active and config.WS_HIGHLIGHT:
            previous = self._current_rect()
            self._active = state.active
            if previous is not None and self._button_rect(state.active) is not None:
                self._plate_from = previous
                self._plate_t = 0.0
                self._plate_tween.run((0.0,), (1.0,))
            self.queue_draw()
        self._active = state.active

    def _on_plate_tick(self, values):
        self._plate_t = values[0]
        self.queue_draw()

    def _button_rect(self, n):
        button = self._buttons.get(n)
        if button is None or not button.get_realized():
            return None
        x, y = button.translate_coordinates(self, 0, 0)
        across = self.get_allocated_height() if self._horizontal else self.get_allocated_width()
        alloc = button.get_allocation()
        return plate_rect((x, y, alloc.width, alloc.height), across, self._horizontal,
                          config.WS_PLATE_GAP, config.WS_PLATE_SHRINK)

    def _current_rect(self):
        target = self._button_rect(self._active)
        if target is None:
            return None
        if self._plate_from is None or self._plate_t >= 1.0:
            return target
        return blend(self._plate_from, target, self._plate_t)

    def _draw_plate(self, _widget, cr):
        rect = self._current_rect()
        if rect is None:
            return False
        color, radius = self._plate
        x, y, w, h = rect
        cr.set_source_rgba(*color)
        rounded_rect(cr, x, y, w, h, min(radius, w / 2, h / 2))
        cr.fill()
        return False
