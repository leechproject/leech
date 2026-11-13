import time

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Gio

from modules import config
from modules.common import theme
from modules.parsing import apps
from modules.common import icons
from modules.common import dock_items

CENTER = Gtk.Align.CENTER
TRACK_WINDOWS = config.DOCK_MARK_RUNNED or config.DOCK_SHOW_LAUNCHED
INDEX_RETRY_SECONDS = 10


def separator_color():
    probe = Gtk.Box()
    probe.set_name("dock-separator")
    color = probe.get_style_context().get_property("background-color", Gtk.StateFlags.NORMAL)
    return color.red, color.green, color.blue, color.alpha


class DockRow:
    def __init__(self, wm, on_change, dots_top, height, leading=None):
        self._output_scale = wm.output_scale()
        self._on_change = on_change
        self._dots_top = dots_top
        self._height = height
        self._leading = leading
        self._separator = None
        self._separator_color = separator_color()
        self._pinned = []
        self._launched = []
        self._counts = {}
        self._clients = ()
        self._class_index = None
        self._index_time = 0.0
        self._buttons = []
        self._reload_source = 0

        pad_v = (height - config.DOCK_ICON) // 2
        self.widget = Gtk.Box(spacing=config.DOCK_GAP)
        self.widget.set_margin_start(config.DOCK_EDGE)
        self.widget.set_margin_end(config.DOCK_EDGE)
        self.widget.set_margin_top(pad_v)
        self.widget.set_margin_bottom(pad_v)

        apps.ensure_pinned_file()
        self._monitor = Gio.File.new_for_path(str(config.PINNED_FILE)).monitor_file(Gio.FileMonitorFlags.NONE, None)
        self._monitor.connect("changed", lambda *_: self._schedule_reload())
        self._load_pinned()

    def connect_marks(self, widget):
        if TRACK_WINDOWS:
            widget.connect_after("draw", self._draw_marks)

    def output_scale(self):
        return self._output_scale

    def _schedule_reload(self):
        if not self._reload_source:
            self._reload_source = GLib.timeout_add(150, self._reload)

    def _reload(self):
        self._reload_source = 0
        self._load_pinned()
        self._on_change(True)
        return False

    def _load_pinned(self):
        pinned = []
        for app_id in apps.read_pinned():
            info = apps.lookup(app_id)
            if info is None:
                print(f"dock: нет приложения {app_id}")
                continue
            pinned.append(info)
        self._pinned = pinned
        self._arrange()
        self._rebuild()

    def _resolve(self, window_class):
        now = time.monotonic()
        if self._class_index is None:
            self._class_index = dock_items.build_index(apps.class_entries())
            self._index_time = now
        found = dock_items.resolve(window_class, self._class_index)
        if found is None and now - self._index_time > INDEX_RETRY_SECONDS:
            self._class_index = dock_items.build_index(apps.class_entries())
            self._index_time = now
            found = dock_items.resolve(window_class, self._class_index)
        return found

    def _arrange(self):
        running = [app_id for app_id in (self._resolve(cls) for cls, _ in self._clients) if app_id]
        pinned_ids = [info.get_id() for info in self._pinned]
        launched, counts = dock_items.arrange(pinned_ids, running, config.DOCK_SHOW_LAUNCHED)
        infos = [info for info in (apps.lookup(app_id) for app_id in launched) if info is not None]
        changed = [i.get_id() for i in infos] != [i.get_id() for i in self._launched]
        self._launched = infos
        self._counts = counts if config.DOCK_MARK_RUNNED else {}
        return changed

    def items(self):
        return [dock_items.DockItem(info.get_id(), info, pinned, self._counts.get(info.get_id(), 0))
                for infos, pinned in ((self._pinned, True), (self._launched, False)) for info in infos]

    def _rebuild(self):
        for child in self.widget.get_children():
            if child is not self._leading:
                child.destroy()
        if self._leading is not None and self._leading.get_parent() is None:
            self.widget.pack_start(self._leading, False, False, 0)
        self._buttons = []
        self._separator = None
        for index, item in enumerate(self.items()):
            if index == len(self._pinned) and self._launched and self._pinned:
                self._separator = self._make_separator()
                self.widget.pack_start(self._separator, False, False, 0)
            button = self._make_button(item.info, item.pinned)
            self._buttons.append((button, item.app_id))
            self.widget.pack_start(button, False, False, 0)
        self.widget.show_all()

    def set_clients(self, clients):
        if not TRACK_WINDOWS or clients == self._clients:
            return
        self._clients = clients
        counts = self._counts
        if self._arrange():
            self._rebuild()
            self._on_change(True)
        elif counts != self._counts:
            self._on_change(False)

    def _draw_separator(self, widget, cr):
        if self._separator is None:
            return
        top = widget.get_toplevel()
        origin = self._separator.translate_coordinates(top, 0, 0)
        local = self._separator.translate_coordinates(widget, 0, 0)
        if origin is None or local is None:
            return
        x, width = dock_items.snap_line(origin[0], self._output_scale, widget.get_scale_factor())
        cr.set_source_rgba(*self._separator_color)
        cr.rectangle(local[0] + x - origin[0], local[1], width, self._separator.get_allocated_height())
        cr.fill()

    def _make_separator(self):
        separator = Gtk.Box()
        separator.set_size_request(dock_items.SEPARATOR_W, self._height // 2)
        separator.set_valign(CENTER)
        return separator

    def _draw_marks(self, widget, cr):
        self._draw_separator(widget, cr)
        cr.set_source_rgba(*theme.bg("#dock-dot"))
        radius = dock_items.DOT / 2
        for button, app_id in self._buttons:
            count = self._counts.get(app_id, 0)
            origin = button.translate_coordinates(widget, 0, 0)
            if not count or origin is None:
                continue
            x, y = origin
            top = dock_items.dot_top(y, button.get_allocated_height(), self._dots_top)
            for dx in dock_items.dot_offsets(count, button.get_allocated_width()):
                cr.arc(x + dx + radius, top + radius, radius, 0, 6.283185307179586)
                cr.fill()
        return False

    @staticmethod
    def _make_button(info, pinned=True):
        size = config.DOCK_ICON
        image = Gtk.Image.new_from_gicon(icons.app_gicon(info, size), Gtk.IconSize.DND)
        image.set_pixel_size(size)

        btn = Gtk.Button()
        btn.set_relief(Gtk.ReliefStyle.NONE)
        btn.set_can_focus(False)
        btn.get_style_context().add_class("dock-btn")
        btn.set_size_request(size, size)
        btn.add(image)
        if pinned:
            btn.connect("clicked", lambda *_: apps.launch(info))
        return btn

    def try_pin(self, app_id):
        info = apps.lookup(app_id)
        if info is None:
            return False, f"нет такого приложения: {app_id} (поиск: python ctl.py apps {app_id})"
        ids = apps.read_pinned()
        desktop_id = apps.normalize(app_id)
        if desktop_id in ids:
            return False, f"уже закреплено: {info.get_name()}"
        apps.write_pinned(ids + [desktop_id])
        self._schedule_reload()
        return True, f"закреплено: {info.get_name()}"

    def try_unpin(self, app_id):
        ids = apps.read_pinned()
        desktop_id = apps.normalize(app_id)
        if desktop_id not in ids:
            return False, f"не закреплено: {app_id}"
        apps.write_pinned([i for i in ids if i != desktop_id])
        self._schedule_reload()
        return True, f"откреплено: {app_id}"

    def pins(self):
        return "\n".join(apps.read_pinned()) or "(ничего не закреплено)"

    def pinned_count(self):
        return len(self._pinned)

    def launched_count(self):
        return len(self._launched)
