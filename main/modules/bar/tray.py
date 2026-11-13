import math

import cairo
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from fabric.system_tray.widgets import SystemTray, get_tray_watcher

from modules import config
from modules.animations import anim
from modules.animations.anim import Tween
from modules.bar import tray_compat
from modules.common.shapes import rounded_rect
from modules.bar.tray_layout import clamp_scroll, fade_strengths, visible_length
from modules.common import debug, theme
from modules.common.glyph import show_centered
from modules.config.geometry import scaled

ICON_SIZE = scaled(24, config.BAR_SCALE)
SPACING = scaled(theme.gap("#systray-items"), config.BAR_SCALE)
EDGE = scaled(theme.pad("#systray-items"), config.BAR_SCALE)
FADE = EDGE - 1
TOGGLE = scaled(40, config.BAR_SCALE)
WHEEL_STEP = ICON_SIZE + SPACING
SMOOTH_FACTOR = 20


def _plate_style(name):
    probe = Gtk.Box()
    probe.set_name(name)
    ctx = probe.get_style_context()
    color = ctx.get_property("background-color", Gtk.StateFlags.NORMAL)
    radius = ctx.get_property("border-radius", Gtk.StateFlags.NORMAL)
    return (color.red, color.green, color.blue, color.alpha), radius


class _View(Gtk.Viewport):
    def __init__(self, horizontal):
        super().__init__()
        self._horizontal = horizontal
        self.length = 0
        self.set_shadow_type(Gtk.ShadowType.NONE)

    def do_get_preferred_width(self):
        if self._horizontal:
            return self.length, self.length
        return Gtk.Viewport.do_get_preferred_width(self)

    def do_get_preferred_height(self):
        if self._horizontal:
            return Gtk.Viewport.do_get_preferred_height(self)
        return self.length, self.length

    def do_get_preferred_width_for_height(self, _height):
        return self.do_get_preferred_width()

    def do_get_preferred_height_for_width(self, _width):
        return self.do_get_preferred_height()


class _Toggle(Gtk.DrawingArea):
    def __init__(self, glyph, base_angle, on_click, size=TOGGLE):
        super().__init__()
        self.set_name("tray-toggle")
        self._glyph = glyph
        self._base = base_angle
        self.progress = 0.0
        self.set_size_request(size, size)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect("button-press-event", lambda _w, e: on_click() if e.button == 1 else None)
        self.connect("draw", self._on_draw)

    def _on_draw(self, widget, cr):
        width, height = widget.get_allocated_width(), widget.get_allocated_height()
        color = widget.get_style_context().get_color(Gtk.StateFlags.NORMAL)
        cr.set_source_rgba(color.red, color.green, color.blue, color.alpha)
        cr.translate(width / 2, height / 2)
        cr.rotate(self._base + math.pi * self.progress)
        show_centered(cr, widget.create_pango_layout(self._glyph), 0, 0)
        return False


def watch_outside_press(inside, callback):
    """Зовёт callback при нажатии кнопки мыши в окне виджета inside, но вне его самого.

    Жест в фазе захвата ничего не забирает: нажатие доходит до кнопки, по которой кликнули.
    """
    state = {}

    def on_press(gesture, _n_press, x, y):
        coords = gesture.get_widget().translate_coordinates(inside, int(x), int(y))
        if coords is not None:
            ix, iy = coords
            if 0 <= ix < inside.get_allocated_width() and 0 <= iy < inside.get_allocated_height():
                return
        callback()

    def attach(widget, _previous=None):
        top = widget.get_toplevel()
        if not isinstance(top, Gtk.Window) or state.get("window") is top:
            return
        gesture = Gtk.GestureMultiPress.new(top)
        gesture.set_button(0)
        gesture.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        gesture.connect("pressed", on_press)
        state["window"], state["gesture"] = top, gesture

    inside.connect("hierarchy-changed", attach)
    attach(inside)


class CollapsibleTray(Gtk.Box):
    def __init__(self, horizontal, plate="box-tray", toggle=TOGGLE, canvas=None):
        orientation = Gtk.Orientation.HORIZONTAL if horizontal else Gtk.Orientation.VERTICAL
        super().__init__(orientation=orientation, spacing=0)
        self._horizontal = horizontal
        self._canvas = canvas
        self._expanded = False
        self._progress = 0.0
        self._from_near = 0.0
        self._fade_color, self._radius = _plate_style(plate)

        tray_compat.install()
        self._items = SystemTray(icon_size=ICON_SIZE, spacing=SPACING,
                                 orientation="horizontal" if horizontal else "vertical")
        debug.watch_tray(get_tray_watcher())
        if horizontal:
            self._items.set_valign(Gtk.Align.CENTER)
            self._items.set_margin_start(EDGE)
            self._items.set_margin_end(EDGE)
        else:
            self._items.set_halign(Gtk.Align.CENTER)
            self._items.set_margin_top(EDGE)
            self._items.set_margin_bottom(EDGE)

        self._view = _View(horizontal)
        self._view.add(self._items)
        self._view.add_events(Gdk.EventMask.SCROLL_MASK | Gdk.EventMask.SMOOTH_SCROLL_MASK)
        self._view.connect("scroll-event", self._on_scroll)
        self._view.connect_after("draw", self._draw_fades)
        self._view.set_no_show_all(True)
        self._adjustment().connect("changed", lambda *_: self._apply_scroll())

        self._toggle = _Toggle(config.TRAY_ICON, -math.pi / 2 if horizontal else 0.0, self.toggle, toggle)
        self.pack_start(self._view, False, False, 0)
        self.pack_start(self._toggle, False, False, 0)

        self._tween = Tween(anim.ms(), self._on_tick)
        watcher = get_tray_watcher()
        watcher.connect("item-added", lambda *_: GLib.idle_add(self._refit))
        watcher.connect("item-removed", lambda *_: GLib.idle_add(self._refit))
        watch_outside_press(self, self.collapse)

    def toggle(self):
        self._expanded = not self._expanded
        self._from_near = 0.0
        self._tween.run((self._progress,), (1.0 if self._expanded else 0.0,))
        if self._canvas is not None:
            if self._expanded:
                self._canvas.catch("tray", self.collapse)
            else:
                self._canvas.release("tray")

    def collapse(self):
        if self._expanded:
            self.toggle()

    def debug(self, action):
        if action == "toggle":
            self.toggle()
        elif action.startswith("scroll:"):
            self._from_near -= float(action.split(":", 1)[1])
            self._apply_scroll()
        else:
            return f"неизвестное действие {action}"
        adj = self._adjustment()
        return f"length={self._view.length} value={adj.get_value():.0f} upper={adj.get_upper():.0f} page={adj.get_page_size():.0f}"

    def _adjustment(self):
        return self._view.get_hadjustment() if self._horizontal else self._view.get_vadjustment()

    def _target_length(self):
        sizes = []
        for child in self._items.get_children():
            if child.get_visible():
                natural = child.get_preferred_width()[1] if self._horizontal else child.get_preferred_height()[1]
                sizes.append(natural)
        length = visible_length(sizes, SPACING, config.TRAY_LIMIT)
        return length + 2 * EDGE if length else 0

    def _refit(self):
        self._set_length()
        return False

    def _on_tick(self, values):
        self._progress = values[0]
        self._toggle.progress = self._progress
        self._toggle.queue_draw()
        self._set_length()

    def _set_length(self):
        length = round(self._target_length() * self._progress)
        if length != self._view.length:
            self._view.length = length
            self._view.queue_resize()
        if self._view.get_visible() != (length > 0):
            self._show_view(length > 0)

    def _show_view(self, shown):
        if shown:
            self._view.set_no_show_all(False)
            self._view.show_all()
        else:
            self._view.hide()
        self._view.set_no_show_all(True)

    def _apply_scroll(self):
        adj = self._adjustment()
        upper, page = adj.get_upper(), adj.get_page_size()
        value = clamp_scroll(upper - page - self._from_near, upper, page)
        self._from_near = upper - page - value
        if abs(adj.get_value() - value) > 0.01:
            adj.set_value(value)
        self._view.queue_draw()

    def _on_scroll(self, _widget, event):
        if not config.TRAY_SCROLLABLE:
            return True
        if event.direction == Gdk.ScrollDirection.SMOOTH:
            _ok, dx, dy = event.get_scroll_deltas()
            delta = (dx + dy) * SMOOTH_FACTOR
        elif event.direction in (Gdk.ScrollDirection.UP, Gdk.ScrollDirection.LEFT):
            delta = -WHEEL_STEP
        else:
            delta = WHEEL_STEP
        self._from_near -= delta
        self._apply_scroll()
        return True

    def _draw_fades(self, view, cr):
        adj = self._adjustment()
        far, near = fade_strengths(adj.get_value(), adj.get_upper(), adj.get_page_size(), FADE)
        width, height = view.get_allocated_width(), view.get_allocated_height()
        length = width if self._horizontal else height
        if far > 0 or near > 0:
            cr.save()
            radius = min(self._radius, width / 2, height / 2)
            if self._horizontal:
                rounded_rect(cr, 0, 0, width + radius, height, radius)
            else:
                rounded_rect(cr, 0, 0, width, height + radius, radius)
            cr.clip()
        for strength, start, end in ((far, 0, FADE), (near, length, length - FADE)):
            if strength <= 0:
                continue
            if self._horizontal:
                gradient = cairo.LinearGradient(start, 0, end, 0)
                x0, x1 = sorted((start, end))
                cr.rectangle(x0, 0, x1 - x0, height)
            else:
                gradient = cairo.LinearGradient(0, start, 0, end)
                y0, y1 = sorted((start, end))
                cr.rectangle(0, y0, width, y1 - y0)
            r, g, b, a = self._fade_color
            gradient.add_color_stop_rgba(0, r, g, b, a * strength)
            gradient.add_color_stop_rgba(1, r, g, b, 0)
            cr.set_source(gradient)
            cr.fill()
        if far > 0 or near > 0:
            cr.restore()
        return False


def build_tray(canvas=None):
    return CollapsibleTray(config.BAR_HORIZONTAL, canvas=canvas)
