import cairo
import gi

gi.require_version("GtkLayerShell", "0.1")
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import GtkLayerShell, Gtk, Gdk, GLib, Pango, PangoCairo

from pathlib import Path

from modules.common.surface import ShapedWindow, after_commit, no_input, init_layer, on_monitor

from modules import config
from modules.common import binds
from modules.common import theme
from modules.common import layerkeys
from modules.wallpapers import picker_layout as pl
from modules.wallpapers import wallpaper
from modules.common.ghost import DockGhost
from modules.animations import anim
from modules.animations.anim import Tween
from modules.common.shapes import notch_path, rounded_rect
from modules.common.edge import AttachedEdge

_NO_INPUT = no_input()
EDGE = AttachedEdge(config.PICKER_TOP)
UNDER = config.UNDERCOVER
SEP = config.PICKER_SEPARATE and not UNDER
DETACHED = UNDER or SEP
LIFT = config.PICKER_MARGIN[0] if UNDER else (config.DOCK_SEP_GAP if SEP else 0)
FRAME = EDGE.frame + LIFT

_ARROWS = {Gdk.KEY_Left: "left", Gdk.KEY_Right: "right", Gdk.KEY_Up: "up", Gdk.KEY_Down: "down",
           Gdk.KEY_Home: "home", Gdk.KEY_End: "end", Gdk.KEY_Page_Up: "pgup", Gdk.KEY_Page_Down: "pgdn"}


class PickerWindow(ShapedWindow):
    def __init__(self, controller, items, current, start_size, dock_infos):
        super().__init__(name="wallpaper-picker", visible=False, all_visible=False)
        self._controller = controller
        self._items = items
        self._current = current
        self._start_size = start_size
        self._empty_text = f"No wallpapers in {wallpaper.wallpaper_dir()}"
        self._selected = None
        self._nav_mode = None
        self._pointer = None
        self._top_row = 0
        self._layout = None
        self._size = (0, 0)
        self._shape = None
        self._ghost = DockGhost(self, dock_infos, start_size[0], self._queue_area, EDGE,
                                controller.output_scale(), FRAME)
        self.closing = False
        self._scroll_acc = 0.0
        self._relax_source = 0

        visual = self.get_screen().get_rgba_visual()
        if visual:
            self.set_visual(visual)
        self.set_app_paintable(True)

        init_layer(self)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.TOP)
        for edge in (GtkLayerShell.Edge.TOP, GtkLayerShell.Edge.RIGHT,
                     GtkLayerShell.Edge.BOTTOM, GtkLayerShell.Edge.LEFT):
            GtkLayerShell.set_anchor(self, edge, True)
        GtkLayerShell.set_exclusive_zone(self, -1)
        layerkeys.set_keyboard(self, "exclusive")
        self._relax_source = GLib.timeout_add(180, self._relax)

        self._area = Gtk.DrawingArea()
        self._area.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.POINTER_MOTION_MASK
                              | Gdk.EventMask.LEAVE_NOTIFY_MASK | Gdk.EventMask.SCROLL_MASK
                              | Gdk.EventMask.SMOOTH_SCROLL_MASK)
        self._area.connect("draw", self._on_draw)
        self._area.connect("motion-notify-event", self._on_motion)
        self._area.connect("leave-notify-event", self._on_leave)
        self._area.connect("button-press-event", self._on_press)
        self._area.connect("scroll-event", self._on_scroll)
        self.add(self._area)
        self.connect("key-press-event", self._on_key)

        self._thumbs = wallpaper.Thumbnails(self._area.queue_draw)
        self._grow = Tween(anim.ms(), self._on_grow_tick)
        self._tuck = 0.0
        self._slide = Tween(anim.ms(), self._on_slide_tick)

        self.connect("size-allocate", self._on_allocate)
        self.show_all()

    def _relax(self):
        self._relax_source = 0
        layerkeys.set_keyboard(self, "on_demand")
        return False


    def _on_allocate(self, _widget, allocation):
        if self._layout is None and allocation.width > 200 and allocation.height > 200:
            self._begin(allocation.width, allocation.height)
            self._apply_input()

    def _begin(self, width, height):
        self._size = (width, height)
        self._layout = pl.compute(width, height, config.LEFT, config.RIGHT, config.TOP + (LIFT if EDGE.top else 0),
                                  config.BOTTOM + (0 if EDGE.top else LIFT),
                                  config.PICKER_MARGIN, config.PICKER_PAD, config.PICKER_SPACING,
                                  config.PICKER_COLUMNS, EDGE.top, config.PICKER_ROWS)
        layout = self._layout
        if self._current is not None:
            self._top_row = pl.scroll_to_show(layout, 0, self._current, len(self._items))

        dock_w, dock_h = self._start_size
        if UNDER or (SEP and not (dock_w >= 1 and dock_h >= 1)):
            self._shape = (layout.x0, layout.x1, layout.body_h)
            self._tuck = layout.body_h + LIFT
            self._slide.run((self._tuck,), (0.0,))
            self._controller.on_ready(self)
            return
        if dock_w >= 1 and dock_h >= 1:
            x0 = round((width - dock_w) / 2)
            start = (x0, x0 + dock_w, dock_h)
        else:
            start = (layout.x0, layout.x1, 0)
        self._shape = start
        self._ghost.fade_out()
        self._grow.run(start, (layout.x0, layout.x1, layout.body_h))
        self._controller.on_ready(self)

    def begin_close(self, final_size):
        if self.closing:
            return
        self.closing = True
        self._selected = None
        if self._layout is None:
            self._controller.on_finished()
            return
        if UNDER or (SEP and not final_size):
            self._grow.stop()
            self._slide.run((self._tuck,), (self._shape[2] + LIFT,), self._controller.on_finished)
            return
        if final_size:
            dock_w, dock_h = final_size
            x0 = round((self._size[0] - dock_w) / 2)
            target = (x0, x0 + dock_w, dock_h)
            self._ghost.fade_in_later(dock_w)
        else:
            target = (self._shape[0], self._shape[1], 0)
        self._grow.run(self._shape, target, self._controller.on_finished)

    def dispose(self):
        self._grow.stop()
        self._slide.stop()
        self._ghost.stop()
        self._thumbs.close()
        if self._relax_source:
            GLib.source_remove(self._relax_source)
        self.destroy()


    def _on_grow_tick(self, values):
        self._shape = values
        self._area.queue_draw()
        self._apply_input()

    def _on_slide_tick(self, values):
        self._tuck = values[0]
        self._area.queue_draw()
        self._apply_input()

    def _queue_area(self):
        self._area.queue_draw()


    def _on_draw(self, area, cr):
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        if self._shape is None:
            return False
        x0, x1, h = self._shape
        if config.PICKER_OUTLINE:
            # Целые края: обводка на полупикселе размывается в серый.
            x0, x1, h = round(x0), round(x1), round(h)
        cr.save()
        if DETACHED:
            EDGE.clip_inside(cr, area.get_allocated_width(), area.get_allocated_height())
            cr.translate(0, EDGE.toward(self._tuck))
        if h >= 1 and x1 - x0 >= 1:
            cr.save()
            if DETACHED:
                rounded_rect(cr, x0, EDGE.body_y(area.get_allocated_height(), h, FRAME), x1 - x0, h,
                             min(config.RADIUS, h / 2))
            else:
                EDGE.clip_bar(cr, area.get_allocated_width(), area.get_allocated_height())
                cr.save()
                EDGE.to_edge(cr, area.get_allocated_height())
                notch_path(cr, x0, x1, EDGE.frame, h, config.RADIUS)
                cr.restore()
            cr.set_source_rgba(*config.COLOR)
            cr.fill()
            cr.restore()
        if self._layout is not None and h >= 1:
            cr.save()
            cr.rectangle(x0, EDGE.body_y(area.get_allocated_height(), h, FRAME), x1 - x0, h)
            cr.clip()
            cr.translate(0, EDGE.slide(self._layout.body_h, h))
            self._draw_grid(cr)
            cr.restore()
        if config.PICKER_OUTLINE and h >= 1 and x1 - x0 >= 1:
            EDGE.outline_body(cr, area.get_allocated_width(), area.get_allocated_height(), x0, x1, h, DETACHED, FRAME)
        cr.restore()
        self._ghost.draw(cr, self._size[0], area.get_allocated_height())
        return False

    def _draw_grid(self, cr):
        layout, count = self._layout, len(self._items)
        if count == 0:
            text = self.create_pango_layout(self._empty_text)
            desc = self._area.get_pango_context().get_font_description().copy()
            desc.set_absolute_size(theme.font("#picker-empty") * Pango.SCALE)
            text.set_font_description(desc)
            width, _ = text.get_pixel_size()
            cr.set_source_rgba(*theme.fg("#picker-empty"))
            cr.move_to(layout.x0 + ((layout.x1 - layout.x0) - width) / 2, layout.grid_y + 24)
            PangoCairo.show_layout(cr, text)
            return

        border, radius = config.PICKER_BORDER, theme.radius("#picker-cell")
        first = self._top_row * layout.cols
        last = min(count, (self._top_row + layout.rows) * layout.cols)
        for index in range(first, last):
            x, y, w, h = pl.cell_rect(layout, index, self._top_row)
            if index == self._selected:
                cell = "#picker-cell.hover"
            elif index == self._current:
                cell = "#picker-cell.current"
            else:
                cell = "#picker-cell"
            cr.set_source_rgba(*theme.bg(cell))
            rounded_rect(cr, x, y, w, h, radius)
            cr.fill()

            inner_w, inner_h = w - 2 * border, h - 2 * border
            pixbuf = self._thumbs.get(self._items[index], inner_w, inner_h)
            cr.save()
            rounded_rect(cr, x + border, y + border, inner_w, inner_h, max(0, radius - border))
            cr.clip()
            if pixbuf is not None:
                Gdk.cairo_set_source_pixbuf(cr, pixbuf, x + border, y + border)
            else:
                cr.set_source_rgba(*theme.bg("#picker-placeholder"))
            cr.paint()
            cr.restore()
        for index in range(last, min(count, last + layout.cols)):
            self._thumbs.get(self._items[index], layout.cell_w - 2 * border, layout.cell_h - 2 * border)


    def _hover(self, x, y):
        if self._layout is None or self.closing:
            return
        index = pl.cell_at(self._layout, x, y, self._top_row, len(self._items))
        if index != self._selected:
            self._selected = index
            self._area.queue_draw()

    def _on_motion(self, _widget, event):
        self._pointer = (event.x, event.y)
        self._nav_mode = "mouse"
        self._hover(event.x, event.y)
        return True

    def _on_leave(self, _widget, _event):
        if self._nav_mode == "mouse" and self._selected is not None:
            self._selected = None
            self._area.queue_draw()
        return True

    def _on_press(self, _widget, event):
        if event.button == 1 and self._layout is not None and not self.closing:
            index = pl.cell_at(self._layout, event.x, event.y, self._top_row, len(self._items))
            if index is not None:
                self._apply(index)
        return True

    def _on_scroll(self, _widget, event):
        if self._layout is None:
            return True
        step = 0
        if event.direction == Gdk.ScrollDirection.UP:
            step = -1
        elif event.direction == Gdk.ScrollDirection.DOWN:
            step = 1
        elif event.direction == Gdk.ScrollDirection.SMOOTH:
            self._scroll_acc += event.delta_y
            if abs(self._scroll_acc) >= 1.0:
                step = int(self._scroll_acc)
                self._scroll_acc -= step
        if step:
            self._top_row = pl.clamp_top_row(self._layout, self._top_row + step, len(self._items))
            if self._nav_mode == "mouse" and self._pointer:
                self._hover(*self._pointer)
            self._area.queue_draw()
        return True


    def _on_key(self, _widget, event):
        if self.closing or self._layout is None:
            return True
        key, count = binds.nav_key(event), len(self._items)
        if key == Gdk.KEY_Escape:
            self._controller.close()
            return True
        if count == 0:
            return False
        if key in _ARROWS:
            self._nav_mode = "keyboard"
            if self._selected is None:
                index = self._current if self._current is not None else 0
            else:
                index = pl.move(self._layout, self._selected, _ARROWS[key], count)
            self._selected = index
            self._top_row = pl.scroll_to_show(self._layout, self._top_row, index, count)
            self._area.queue_draw()
            return True
        if key in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_space) and self._selected is not None:
            self._apply(self._selected)
            return True
        return False

    def _apply(self, index):
        self._current = index
        self._controller.apply(self._items[index])


    def input_region(self):
        if self._shape is not None and self._shape[2] >= 1 and self._tuck < 1:
            x0, x1, h = self._shape
            if DETACHED:
                y, body = round(EDGE.body_y(self._size[1], h, FRAME)), round(h)
            else:
                y, body = EDGE.attached_rect(self._size[1], h)
            return cairo.Region(cairo.RectangleInt(round(x0), y, round(x1 - x0), body))
        return _NO_INPUT


class WallpaperPicker:
    def __init__(self, manager, targets, canvas):
        self._manager = manager
        self._targets = targets
        self._dock = self._notch = None
        self._canvas = canvas
        self._window = None
        self.others = ()

    @property
    def busy(self):
        return self._window is not None

    def toggle(self):
        self.close() if self._window is not None else self.open()

    def open(self):
        if self._window is not None or any(other.busy for other in self.others):
            return
        items = wallpaper.list_wallpapers(wallpaper.wallpaper_dir())
        current = None
        if self._manager.current:
            try:
                current = items.index(Path(self._manager.current))
            except ValueError:
                pass
        target = self._targets()
        self._dock, self._notch = target.dock, target.notch
        self._notch.suppress(True)
        with on_monitor(target.monitor):
            start = self._dock.current_size() if self._morph() else (0.0, 0.0)
            self._window = PickerWindow(self, items, current, start, self._dock.icon_infos())
        self._canvas.catch("picker", self.close)

    def close(self):
        if self._window is None:
            return
        self._canvas.release("picker")
        self._window.begin_close(self._dock.final_size() if self._morph() else None)

    def apply(self, path):
        self._manager.apply(path)


    def output_scale(self):
        return self._dock.output_scale()

    @staticmethod
    def _morph():
        return config.DOCK_SEPARATE == SEP

    def on_ready(self, window):
        after_commit(window, lambda: self._suspend_dock(window))

    def _suspend_dock(self, window):
        if window is self._window and not window.closing:
            self._dock.suspend(instant=self._morph())

    def on_finished(self):
        window, self._window = self._window, None
        self._notch.suppress(False)
        if window is None:
            self._dock.resume(instant=self._morph())
        elif self._dock.resume(instant=self._morph()):
            after_commit(self._dock, window.dispose)
        else:
            window.dispose()
