import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk

from modules import config
from modules.common import drawing
from modules.common.shapes import rounded_rect

_PLATE = (9 / 255, 9 / 255, 9 / 255)
_DIM = (0.4, 0.4, 0.4)
_ICON_SIZE = 22


class Slider(Gtk.DrawingArea):
    def __init__(self, kind, width, height, on_change, horizontal=False):
        super().__init__()
        self._kind = kind
        self._horizontal = horizontal
        self._on_change = on_change
        self._value = 0
        self._muted = False
        self._dragging = False
        self.set_size_request(width, height)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK
                        | Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.SCROLL_MASK)
        self.connect("draw", self._on_draw)
        self.connect("button-press-event", self._on_press)
        self.connect("motion-notify-event", self._on_motion)
        self.connect("button-release-event", self._on_release)
        self.connect("scroll-event", self._on_scroll)

    def set_value(self, value, muted=False):
        if self._dragging:
            return
        self._value, self._muted = value, muted
        self.queue_draw()

    def _value_at(self, event):
        if self._horizontal:
            fraction = event.x / max(1, self.get_allocated_width())
        else:
            fraction = 1 - event.y / max(1, self.get_allocated_height())
        return max(0, min(100, round(100 * fraction)))

    def _on_press(self, _widget, event):
        if event.button == 1:
            self._dragging = True
            self._value = self._value_at(event)
            self._on_change(self._value)
            self.queue_draw()
        return True

    def _on_motion(self, _widget, event):
        if self._dragging:
            self._value = self._value_at(event)
            self._on_change(self._value)
            self.queue_draw()
        return True

    def _on_release(self, _widget, _event):
        self._dragging = False
        return True

    def _on_scroll(self, _widget, event):
        step = config.CONTROL_STEP
        if event.direction in (Gdk.ScrollDirection.UP, Gdk.ScrollDirection.RIGHT):
            self._value = min(100, self._value + step)
        elif event.direction in (Gdk.ScrollDirection.DOWN, Gdk.ScrollDirection.LEFT):
            self._value = max(0, self._value - step)
        else:
            return True
        self._on_change(self._value)
        self.queue_draw()
        return True

    def _icon(self, cr, cx, cy):
        if self._kind == "brightness":
            drawing.sun(cr, cx, cy, _ICON_SIZE)
        else:
            drawing.speaker(cr, cx, cy, _ICON_SIZE, self._value, self._muted)

    def _on_draw(self, widget, cr):
        w, h = widget.get_allocated_width(), widget.get_allocated_height()
        cr.set_source_rgb(*_PLATE)
        rounded_rect(cr, 0, 0, w, h, 10)
        cr.fill()
        if self._horizontal:
            fill_w = w * self._value / 100
            filled, empty = (0, 0, fill_w, h), (fill_w, 0, w - fill_w, h)
            cx, cy = 8 + _ICON_SIZE / 2, h / 2
        else:
            fill_h = h * self._value / 100
            filled, empty = (0, h - fill_h, w, fill_h), (0, 0, w, h - fill_h)
            cx, cy = w / 2, h - 8 - _ICON_SIZE / 2
        cr.save()
        rounded_rect(cr, 0, 0, w, h, 10)
        cr.clip()
        cr.set_source_rgb(*(_DIM if self._muted else (1, 1, 1)))
        cr.rectangle(*filled)
        cr.fill()
        cr.restore()

        for inside in (False, True):
            cr.save()
            cr.rectangle(*(filled if inside else empty))
            cr.clip()
            shade = 0.0 if inside else 1.0
            cr.set_source_rgb(shade, shade, shade)
            self._icon(cr, cx, cy)
            cr.restore()
        return False
