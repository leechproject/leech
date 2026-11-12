from collections import namedtuple

import cairo
import gi

gi.require_version("GtkLayerShell", "0.1")
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import GtkLayerShell, Gtk, Gdk

from modules import config
from modules.common.shapes import OUTLINE_LAYERS, draw_frame, frame_shape, rounded_rect, stroke_inside
from modules.config.geometry import bar_rect, snap_inset
from modules.common.surface import ShapedWindow, no_input, init_layer

Edge = GtkLayerShell.Edge
ALL_EDGES = (Edge.TOP, Edge.RIGHT, Edge.BOTTOM, Edge.LEFT)

Surfaces = namedtuple("Surfaces", "windows canvas")

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


class Canvas(ShapedWindow):
    def __init__(self, output_scale=None):
        super().__init__(name="leech-canvas", visible=False, all_visible=False)
        _configure_layer(self, ALL_EDGES, zone=-1)
        self._catchers = {}
        self._output_scale = output_scale

        area = Gtk.DrawingArea()
        area.connect("draw", self._on_draw)
        self.add(area)

        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect("button-press-event", self._on_press)

    def _on_draw(self, area, cr):
        w, h = area.get_allocated_width(), area.get_allocated_height()
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        insets = [snap_inset(side, self._output_scale, area.get_scale_factor())
                  for side in (config.FRAME_LEFT, config.FRAME_TOP, config.FRAME_RIGHT, config.FRAME_BOTTOM)]
        draw_frame(cr, w, h, *insets, config.FRAME_RADIUS, config.COLOR)
        if config.FRAME_OUTLINE:
            left, top, right, bottom = insets
            stroke_inside(cr, lambda c: frame_shape(c, w, h, *insets, config.FRAME_RADIUS),
                          lambda c: rounded_rect(c, left, top, w - left - right, h - top - bottom, config.FRAME_RADIUS),
                          OUTLINE_LAYERS, config.OUTLINE_THICKNESS)
        if config.BAR_DETACHED and not config.BAR_SPLIT:
            x, y, bw, bh = bar_rect(w, h, config.BAR_POSITION, config.BAR_SIZE, config.BAR_MARGINS)
            cr.set_source_rgba(*config.COLOR)
            plate = lambda c: rounded_rect(c, x, y, bw, bh, min(config.RADIUS, bw / 2, bh / 2))
            plate(cr)
            cr.fill()
            if config.FRAME_OUTLINE:
                stroke_inside(cr, plate, plate, OUTLINE_LAYERS, config.OUTLINE_THICKNESS)
        return False

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


def create_canvas(output_scale=None):
    canvas = Canvas(output_scale)
    windows = [canvas]
    for name, edge, amount in (("top", Edge.TOP, config.TOP), ("right", Edge.RIGHT, config.RIGHT),
                               ("bottom", Edge.BOTTOM, config.BOTTOM), ("left", Edge.LEFT, config.LEFT)):
        if amount > 0:
            windows.append(_reserve(f"leech-reserve-{name}", edge, amount))
    for win in windows:
        win.show_all()
    return Surfaces(windows, canvas)


class ScopedCanvas:
    def __init__(self, group, scope):
        self._group = group
        self._scope = scope

    def catch(self, owner, callback):
        self._group.catch(f"{self._scope}:{owner}", callback)

    def release(self, owner):
        self._group.release(f"{self._scope}:{owner}")


class CanvasGroup:
    def __init__(self, canvases):
        self._canvases = list(canvases)

    def catch(self, owner, callback):
        for canvas in self._canvases:
            canvas.catch(owner, callback)

    def release(self, owner):
        for canvas in self._canvases:
            canvas.release(owner)

    def scoped(self, scope):
        return ScopedCanvas(self, scope)
