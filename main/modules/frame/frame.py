from collections import namedtuple

import cairo
import gi

gi.require_version("GtkLayerShell", "0.1")
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import GtkLayerShell, Gtk, Gdk

from modules import config
from modules.common import palette
from modules.frame.shapes import draw_frame
from modules.common.surface import ShapedWindow, no_input, init_layer

Edge = GtkLayerShell.Edge
ALL_EDGES = (Edge.TOP, Edge.RIGHT, Edge.BOTTOM, Edge.LEFT)

Frame = namedtuple("Frame", "windows canvas")

_INPUT_REGION = no_input()


def _configure_layer(win, anchors, zone, size=None):
    visual = win.get_screen().get_rgba_visual()
    if visual:
        win.set_visual(visual)
    win.set_app_paintable(True)

    init_layer(win)
    GtkLayerShell.set_layer(win, GtkLayerShell.Layer.TOP)
    for edge in anchors:
        GtkLayerShell.set_anchor(win, edge, True)
    GtkLayerShell.set_exclusive_zone(win, zone)
    if size:
        win.set_size_request(*size)


class _Reserve(ShapedWindow):
    def __init__(self, name, anchors, zone, size):
        super().__init__(name=name, visible=False, all_visible=False)
        _configure_layer(self, anchors, zone, size)

    def input_region(self):
        return _INPUT_REGION


def _on_draw(area, cr):
    w, h = area.get_allocated_width(), area.get_allocated_height()
    cr.set_operator(cairo.OPERATOR_CLEAR)
    cr.paint()
    cr.set_operator(cairo.OPERATOR_OVER)
    draw_frame(cr, w, h, config.LEFT, config.TOP, config.RIGHT,
               config.BOTTOM, config.RADIUS, palette.rgba("silhouette"))
    return False


class Canvas(ShapedWindow):
    def __init__(self):
        super().__init__(name="leech-canvas", visible=False, all_visible=False)
        _configure_layer(self, ALL_EDGES, zone=-1)
        self._catchers = {}

        area = Gtk.DrawingArea()
        area.connect("draw", _on_draw)
        self.add(area)

        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect("button-press-event", self._on_press)

    def catch(self, owner, callback):
        self._catchers[owner] = callback
        self._apply_input()

    def release(self, owner):
        if self._catchers.pop(owner, None) is not None:
            self._apply_input()

    def _on_press(self, _widget, _event):
        for callback in list(self._catchers.values()):
            callback()
        return True

    def input_region(self):
        if self._catchers:
            return cairo.Region(cairo.RectangleInt(
                0, 0, self.get_allocated_width(), self.get_allocated_height()))
        return _INPUT_REGION


def _reserve(name, edge, amount):
    horizontal = edge in (Edge.TOP, Edge.BOTTOM)
    perpendicular = (Edge.LEFT, Edge.RIGHT) if horizontal else (Edge.TOP, Edge.BOTTOM)
    size = (-1, 1) if horizontal else (1, -1)
    return _Reserve(name, (edge, *perpendicular), amount, size)


def create_frame():
    canvas = Canvas()
    windows = [
        canvas,
        _reserve("leech-reserve-top", Edge.TOP, config.TOP),
        _reserve("leech-reserve-right", Edge.RIGHT, config.RIGHT),
        _reserve("leech-reserve-bottom", Edge.BOTTOM, config.BOTTOM),
        _reserve("leech-reserve-left", Edge.LEFT, config.LEFT),
    ]
    for win in windows:
        win.show_all()
    return Frame(windows, canvas)
