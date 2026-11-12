from contextlib import contextmanager

import cairo
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GtkLayerShell, GLib

from fabric.widgets.window import Window


NAMESPACE_PREFIX = "leech-"
_target = [None]


def gdk_monitor(monitor):
    if monitor is None:
        return None
    display = Gdk.Display.get_default()
    for index in range(display.get_n_monitors()):
        candidate = display.get_monitor(index)
        geometry = candidate.get_geometry()
        if (geometry.x, geometry.y) == (monitor.x, monitor.y):
            return candidate
    return None


@contextmanager
def on_monitor(target):
    previous, _target[0] = _target[0], target
    try:
        yield
    finally:
        _target[0] = previous


def move_to(win, target):
    if target is not None and GtkLayerShell.get_monitor(win) != target:
        GtkLayerShell.set_monitor(win, target)


def init_layer(win):
    GtkLayerShell.init_for_window(win)
    if _target[0] is not None:
        GtkLayerShell.set_monitor(win, _target[0])
    name = win.get_name() or "surface"
    if not name.startswith(NAMESPACE_PREFIX):
        name = NAMESPACE_PREFIX + name
    GtkLayerShell.set_namespace(win, name)


def after_commit(widget, callback, timeout_ms=150):
    clock = widget.get_frame_clock()
    if clock is None:
        GLib.idle_add(_once(callback))
        return
    handler = source = 0

    def finish(from_timeout=False):
        nonlocal handler, source
        if handler:
            clock.disconnect(handler)
            handler = 0
        if source and not from_timeout:
            GLib.source_remove(source)
        source = 0
        GLib.idle_add(_once(callback))
        return False

    handler = clock.connect("after-paint", lambda *_: finish())
    source = GLib.timeout_add(timeout_ms, lambda: finish(True) if handler else False)
    widget.queue_draw()


def _once(callback):
    def run():
        callback()
        return False
    return run


def no_input(x=0, y=0):
    return cairo.Region(cairo.RectangleInt(x, y, 1, 1))


def _region_key(region):
    return tuple((r.x, r.y, r.width, r.height)
                 for r in (region.get_rectangle(i) for i in range(region.num_rectangles())))


class ShapedWindow(Window):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._input_key = None
        self.connect("map-event", lambda *_: self._apply_input(force=True))

    def input_region(self):
        raise NotImplementedError

    def do_size_allocate(self, alloc):
        Gtk.Window.do_size_allocate(self, alloc)
        self._apply_input(force=True)

    def _apply_input(self, force=False):
        gdk_window = self.get_window()
        if gdk_window is None:
            return False
        region = self.input_region()
        key = _region_key(region)
        if not force and key == self._input_key:
            return False
        self._input_key = key
        gdk_window.input_shape_combine_region(region, 0, 0)
        self.queue_draw()
        return False
