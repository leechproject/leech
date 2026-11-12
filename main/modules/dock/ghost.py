import gi

gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib

from modules import config
from modules.animations.anim import Tween
from modules.common.icons import load_icon

FADE_MS = 90
SHOW_DELAY_MS = 130


class DockGhost:
    def __init__(self, widget, dock_infos, start_width, queue_draw):
        self._widget = widget
        self._infos = list(dock_infos)
        self._scale = 0
        self._pixbufs = []
        self._width = start_width
        self.alpha = 1.0 if start_width >= 1 else 0.0
        self._queue_draw = queue_draw
        self._fade = Tween(FADE_MS, self._on_tick, widget)
        self._delay = 0

    def fade_out(self):
        self._cancel_delay()
        self._fade.run((self.alpha,), (0.0,))

    def fade_in_later(self, width):
        self._width = width
        self._cancel_delay()
        self._delay = GLib.timeout_add(SHOW_DELAY_MS, self._fade_in)

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
            self._pixbufs = [load_icon(info, config.DOCK_ICON, scale) for info in self._infos]
        x = (surface_width - self._width) // 2 + config.DOCK_EDGE
        y = height - config.BOTTOM - config.DOCK_H + (config.DOCK_H - config.DOCK_ICON) / 2
        for pixbuf in self._pixbufs:
            if pixbuf is not None:
                cr.save()
                cr.translate(x, y)
                cr.scale(1 / self._scale, 1 / self._scale)
                Gdk.cairo_set_source_pixbuf(cr, pixbuf, 0, 0)
                cr.paint_with_alpha(self.alpha)
                cr.restore()
            x += config.DOCK_ICON + config.DOCK_GAP
