import cairo
import gi

gi.require_version("GtkLayerShell", "0.1")
gi.require_version("Gtk", "3.0")
from gi.repository import GtkLayerShell, Gtk, GLib

from fabric.system_tray.widgets import SystemTrayItem, get_tray_watcher
from fabric.widgets.window import Window

from modules import config
from modules.bar import tray_compat
from modules.bar.taskbar_layout import grid_cell, grid_size, window_left
from modules.common.shapes import rounded_rect
from modules.common.surface import init_layer

ICON = 24
SPACING = 6
COLUMNS = 4
GAP = 7
SCREEN_EDGE = 5


class TrayWindow(Window):
    def __init__(self, bottom):
        super().__init__(name="taskbar-tray-window", visible=False, all_visible=False)
        visual = self.get_screen().get_rgba_visual()
        if visual:
            self.set_visual(visual)
        self.set_app_paintable(True)
        init_layer(self)
        GtkLayerShell.set_namespace(self, "leech-tray")
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.TOP)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.BOTTOM, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.LEFT, True)
        GtkLayerShell.set_exclusive_zone(self, -1)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.BOTTOM, bottom + GAP)

        tray_compat.install()
        self._center = 0
        self._items = {}
        self._grid = Gtk.Grid(row_spacing=SPACING, column_spacing=SPACING)
        self._grid.set_border_width(SPACING)
        self.add(self._grid)
        self.connect("draw", self._on_draw)

        self._watcher = get_tray_watcher()
        self._watcher.connect("item-added", lambda _w, ident: GLib.idle_add(self._add, ident))
        self._watcher.connect("item-removed", lambda _w, ident: GLib.idle_add(self._remove, ident))
        for ident in list(self._watcher.items):
            self._add(ident)

    def _add(self, ident):
        item = self._watcher.items.get(ident)
        if item is None or ident in self._items:
            return False
        button = SystemTrayItem(item, ICON)
        self._items[ident] = button
        self._layout()
        return False

    def _remove(self, ident):
        button = self._items.pop(ident, None)
        if button is not None:
            button.destroy()
            self._layout()
        return False

    def _layout(self):
        for child in self._grid.get_children():
            self._grid.remove(child)
        for index, button in enumerate(self._items.values()):
            row, col = grid_cell(index, COLUMNS)
            self._grid.attach(button, col, row, 1, 1)
        self._grid.show_all()
        width, height = grid_size(len(self._items), COLUMNS, ICON, SPACING)
        self.set_size_request(width, height)
        self.resize(max(1, width), max(1, height))
        self._place()

    def open_at(self, center):
        self._center = center
        self._place()
        if self._items:
            self.show_all()

    def close(self):
        self.hide()

    def _place(self):
        width = grid_size(len(self._items), COLUMNS, ICON, SPACING)[0]
        monitor = self.get_display().get_monitor(0)
        screen_width = monitor.get_geometry().width if monitor is not None else 0
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.LEFT,
                                 window_left(self._center, width, screen_width, SCREEN_EDGE))
        if not self._items:
            self.hide()

    def _on_draw(self, widget, cr):
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        rounded_rect(cr, 0, 0, widget.get_allocated_width(), widget.get_allocated_height(), config.RADIUS)
        cr.set_source_rgba(*config.COLOR)
        cr.fill()
        return False
