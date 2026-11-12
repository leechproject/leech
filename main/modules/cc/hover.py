import cairo
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
from gi.repository import Gtk, Gdk, GtkLayerShell

from modules.common.shapes import rounded_rect
from modules.common.surface import init_layer

SIZE = 5
BAR_W = 22
BAR_H = 4
BAR_PAD = 5
HANDLE_H = BAR_PAD + BAR_H + BAR_PAD


def draw_handle(cr, x, y, w, h, at_top):
    cy = y + BAR_PAD if at_top else y + h - BAR_PAD - BAR_H
    cr.set_source_rgb(1, 1, 1)
    rounded_rect(cr, x + (w - BAR_W) / 2, cy, BAR_W, BAR_H, BAR_H / 2)
    cr.fill()


class HoverTrigger(Gtk.Window):
    def __init__(self, left, top, on_hover, on_click):
        super().__init__()
        self.set_name("cc-trigger")
        visual = self.get_screen().get_rgba_visual()
        if visual:
            self.set_visual(visual)
        self.set_app_paintable(True)
        init_layer(self)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.LEFT if left else GtkLayerShell.Edge.RIGHT, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.TOP if top else GtkLayerShell.Edge.BOTTOM, True)
        GtkLayerShell.set_exclusive_zone(self, -1)
        self.set_size_request(SIZE, SIZE)
        self.add_events(Gdk.EventMask.ENTER_NOTIFY_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK
                        | Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect("draw", self._on_draw)
        self.connect("enter-notify-event", lambda *_: on_hover(True))
        self.connect("leave-notify-event", lambda *_: on_hover(False))
        self.connect("button-press-event", lambda _w, e: e.button == 1 and on_click())
        self.show_all()

    @staticmethod
    def _on_draw(_widget, cr):
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.paint()
        return False
