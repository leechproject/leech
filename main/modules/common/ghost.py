import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib, Gtk

from modules import config
from modules.common import theme
from modules.animations import anim
from modules.animations.anim import Tween
from modules.common.icons import load_icon
from modules.common import dock_items

FADE_MS = 90
SHOW_DELAY_MS = 130


class DockGhost:
    def __init__(self, widget, dock_infos, start_width, queue_draw, edge, output_scale=None, frame=None):
        self._frame = frame
        self._widget = widget
        self._output_scale = output_scale
        self._edge = edge
        self._items = list(dock_infos)
        self._launched = sum(1 for item in self._items if not item.pinned)
        self._separator_color = _separator_color()
        self._scale = 0
        self._pixbufs = []
        self._width = start_width
        self.alpha = 1.0 if start_width >= 1 else 0.0
        self._queue_draw = queue_draw
        self._fade = Tween(anim.ms(FADE_MS), self._on_tick, widget)
        self._delay = 0

    def fade_out(self):
        self._cancel_delay()
        self._fade.run((self.alpha,), (0.0,))

    def fade_in_later(self, width):
        self._width = width
        self._cancel_delay()
        self._delay = GLib.timeout_add(anim.ms(SHOW_DELAY_MS), self._fade_in)

    def _fade_in(self):
        self._delay = 0
        self._fade.run((self.alpha,), (1.0,))
        return False

    def _cancel_delay(self):
        if self._delay:
            GLib.source_remove(self._delay)
            self._delay = 0

    def stop(self):
        self._fade.stop()
        self._cancel_delay()

    def _on_tick(self, values):
        self.alpha = values[0]
        self._queue_draw()

    def draw(self, cr, surface_width, height):
        if self.alpha <= 0 or self._width < 1:
            return
        scale = self._widget.get_scale_factor()
        if scale != self._scale:
            self._scale = scale
            self._pixbufs = [load_icon(item.info, config.DOCK_ICON, scale) for item in self._items]
        left = (surface_width - self._width + 1) // 2
        top = self._edge.body_y(height, config.DOCK_H, self._frame)
        y = top + (config.DOCK_H - config.DOCK_ICON) / 2
        positions, separator, _ = dock_items.offsets(len(self._items) - self._launched, self._launched,
                                                     config.DOCK_EDGE, config.DOCK_ICON, config.DOCK_GAP)
        if separator is not None:
            cr.set_source_rgba(*self._separator_color[:3], self._separator_color[3] * self.alpha)
            sx, sw = dock_items.snap_line(left + separator, self._output_scale, self._scale)
            cr.rectangle(sx, top + config.DOCK_H / 4, sw, config.DOCK_H // 2)
            cr.fill()
        radius = dock_items.DOT / 2
        for item, pixbuf, offset in zip(self._items, self._pixbufs, positions):
            x = left + offset
            if pixbuf is not None:
                cr.save()
                cr.translate(x, y)
                cr.scale(1 / self._scale, 1 / self._scale)
                Gdk.cairo_set_source_pixbuf(cr, pixbuf, 0, 0)
                cr.paint_with_alpha(self.alpha)
                cr.restore()
            r, g, b, a = theme.bg("#dock-dot")
            cr.set_source_rgba(r, g, b, a * self.alpha)
            for dx in dock_items.dot_offsets(item.dots, config.DOCK_ICON) if item.dots else ():
                dot_y = dock_items.dot_top(y, config.DOCK_ICON, self._edge.top)
                cr.arc(x + dx + radius, dot_y + radius, radius, 0, 6.283185307179586)
                cr.fill()


def _separator_color():
    probe = Gtk.Box()
    probe.set_name("dock-separator")
    color = probe.get_style_context().get_property("background-color", Gtk.StateFlags.NORMAL)
    return color.red, color.green, color.blue, color.alpha
