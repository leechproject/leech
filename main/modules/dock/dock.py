import cairo
import gi

gi.require_version("GtkLayerShell", "0.1")
gi.require_version("Gtk", "3.0")
from gi.repository import GtkLayerShell, Gtk


from modules import config
from modules.animations import anim
from modules.animations.anim import Tween
from modules.animations.reveal import install_clip
from modules.common.shapes import (OUTLINE_LAYERS, notch_edge_path, notch_path, rounded_rect, snap_centered,
                                   stroke_inside)
from modules.common.surface import ShapedWindow, no_input, init_layer
from modules.common.edge import AttachedEdge
from modules.common import dock_items
from modules.dock.row import DockRow

CENTER = Gtk.Align.CENTER




def dock_width(launched, pinned=0):
    return dock_items.offsets(pinned, launched, config.DOCK_EDGE, config.DOCK_ICON, config.DOCK_GAP)[2]


EDGE = AttachedEdge(config.DOCK_TOP)
SEP = config.DOCK_SEPARATE
GAP = config.DOCK_SEP_GAP if SEP else 0
SURFACE_H = EDGE.frame + GAP + config.DOCK_H
HIDDEN_TUCK = config.DOCK_H + GAP

_NO_INPUT = no_input(0, 0 if EDGE.top else SURFACE_H - 1)


class Dock(ShapedWindow):
    def __init__(self, wm):
        super().__init__(name="dock", visible=False, all_visible=False)

        visual = self.get_screen().get_rgba_visual()
        if visual:
            self.set_visual(visual)
        self.set_app_paintable(True)

        init_layer(self)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.TOP)
        for edge in (GtkLayerShell.Edge.TOP if EDGE.top else GtkLayerShell.Edge.BOTTOM,
                     GtkLayerShell.Edge.LEFT, GtkLayerShell.Edge.RIGHT):
            GtkLayerShell.set_anchor(self, edge, True)
        GtkLayerShell.set_exclusive_zone(self, -1)
        self.set_size_request(-1, SURFACE_H)

        self._w = self._h = 0.0
        self._mode = None
        self._has_windows = False
        self._suspended = False
        self._pending_clients = None

        self._area = Gtk.DrawingArea()
        self._area.connect("draw", self._on_draw)

        self.row = DockRow(wm, self._on_row_change, EDGE.top, config.DOCK_H)

        self._content = Gtk.Box()
        self._content.set_halign(CENTER)
        self._content.set_valign(Gtk.Align.START if EDGE.top else Gtk.Align.END)
        (self._content.set_margin_top if EDGE.top else self._content.set_margin_bottom)(EDGE.frame + GAP)
        self._content.add(self.row.widget)
        self.row.connect_marks(self._content)

        overlay = Gtk.Overlay()
        overlay.add(self._area)
        overlay.add_overlay(self._content)
        self.add(overlay)

        self._grow = Tween(anim.ms(), self._on_grow_tick)
        self._tuck = 0.0
        self._slide = Tween(anim.ms(), self._on_slide_tick)
        install_clip(self._content, self, self._clip_spec)

        self.show_all()

        wm.subscribe(self._on_wm_state)
        self._update()


    def _on_row_change(self, rebuilt):
        if rebuilt:
            self._mode = None
            self._update()
        else:
            self._content.queue_draw()

    def try_pin(self, app_id):
        return self.row.try_pin(app_id)

    def try_unpin(self, app_id):
        return self.row.try_unpin(app_id)

    def pin(self, app_id):
        return self.try_pin(app_id)[1]

    def unpin(self, app_id):
        return self.try_unpin(app_id)[1]

    def pinned_count(self):
        return self.row.pinned_count()

    def pins(self):
        return self.row.pins()


    def _on_wm_state(self, state):
        self._has_windows = config.DOCK_HIDE_BY_WINDOW and state.windows > 0
        self._pending_clients = state.clients
        self._update()
        if not self._hiding():
            self._flush_clients()

    def _hiding(self):
        return self._mode in ("hidden", "suspended") and (self._slide.running() or self._grow.running())

    def _flush_clients(self):
        if self._pending_clients is not None:
            clients, self._pending_clients = self._pending_clients, None
            self.row.set_clients(clients)

    def _visible_count(self):
        return self.row.pinned_count() + self.row.launched_count()

    def _width(self):
        return dock_width(self.row.launched_count(), self.row.pinned_count())

    def output_scale(self):
        return self.row.output_scale()

    def extra_width(self):
        return self._width() - dock_width(0, self.row.pinned_count())

    def _update(self):
        if self._suspended:
            return
        self._go("shown" if self._visible_count() and not self._has_windows else "hidden")


    def current_size(self):
        if self._suspended or self._tuck >= 1 or self._w < 1 or self._h < 1:
            return (0.0, 0.0)
        return (self._w, self._h)

    def final_size(self):
        if self._visible_count() and not self._has_windows:
            return (self._width(), config.DOCK_H)
        return None

    def suspend(self, instant=True):
        self._suspended = True
        if not instant:
            self._mode = "suspended"
            if SEP:
                self._go_sep("hidden")
            elif self._h >= 1:
                self._grow.run((self._w, self._h), (round(self._w), 0), self._flush_clients)
            return
        self._grow.stop()
        self._slide.stop()
        self._tuck = 0.0
        self._w = self._h = 0.0
        self._mode = None
        self._area.queue_draw()
        self._apply_input()

    def resume(self, instant=True):
        self._flush_clients()
        self._suspended = False
        if not instant:
            self._mode = "suspended"
            self._update()
            return False
        self._slide.stop()
        self._tuck = 0.0
        size = self.final_size()
        if size is None:
            self._mode = "hidden"
            return False
        self._mode = "shown"
        self._w, self._h = size
        self._area.queue_draw()
        self._apply_input()
        return True

    def _go(self, mode):
        if mode == self._mode:
            return
        self._mode = mode
        if SEP:
            self._go_sep(mode)
            return
        if mode == "shown":
            target = (self._width(), config.DOCK_H)
            if self._h < 1:
                self._w = target[0]
        else:
            target = (round(self._w), 0)
        if (round(self._w), round(self._h)) != target:
            self._grow.run((self._w, self._h), target, self._flush_clients if mode == "hidden" else None)

    def _go_sep(self, mode):
        if mode == "hidden":
            self._grow.stop()
            if self._h < 1:
                self._tuck = 0.0
                return
            self._slide.run((self._tuck,), (HIDDEN_TUCK,), self._tucked)
            return
        width = self._width()
        if self._h < 1:
            self._tuck = HIDDEN_TUCK
            self._on_grow_tick((width, config.DOCK_H))
        elif round(self._w) != width:
            self._grow.run((self._w, self._h), (width, config.DOCK_H))
        if self._tuck > 0:
            self._slide.run((self._tuck,), (0.0,))

    def _tucked(self):
        if self._mode == "shown":
            return
        self._tuck = 0.0
        self._on_grow_tick((self._w, 0.0))
        self._flush_clients()

    def _on_slide_tick(self, values):
        self._tuck = values[0]
        self._area.queue_draw()
        self._content.queue_draw()
        self._apply_input()

    def _body_rect(self):
        x0 = (self.get_allocated_width() - self._w) / 2
        if SEP:
            y = EDGE.body_y(SURFACE_H, config.DOCK_H, EDGE.frame + GAP) + EDGE.toward(self._tuck)
            return x0, y, self._w, config.DOCK_H
        y, body = EDGE.attached_rect(SURFACE_H, round(self._h))
        return x0, y, self._w, body

    def icon_infos(self):
        return self.row.items()

    def _clip_spec(self):
        if self._w < 1 or self._h < 1:
            return (0, 0, 0, 0, 0)
        x0 = (self.get_allocated_width() - self._w) / 2
        if SEP:
            x0, y, w, h = self._body_rect()
            if EDGE.top:
                top = max(y, EDGE.frame)
                y, h = top, y + h - top
            else:
                h = min(y + h, SURFACE_H - EDGE.frame) - y
            if h < 1:
                return (0, 0, 0, 0, 0)
            return (x0, y, w, h, EDGE.toward(self._tuck))
        return (x0, EDGE.body_y(SURFACE_H, self._h), self._w, self._h, EDGE.slide(config.DOCK_H, self._h))

    def _on_grow_tick(self, values):
        self._w, self._h = values
        self._area.queue_draw()
        self._apply_input()

    def _on_draw(self, area, cr):
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        if self._w >= 1 and self._h >= 1:
            width, height = area.get_allocated_width(), area.get_allocated_height()
            x0, x1, body_h = (width - self._w) / 2, (width + self._w) / 2, self._h
            if config.DOCK_OUTLINE:
                x0, x1 = snap_centered(width, self._w)
                body_h = round(self._h)
            if SEP:
                cr.save()
                EDGE.clip_inside(cr, width, height)
                _, y, _, h = self._body_rect()
                w = x1 - x0
                plate = lambda c: rounded_rect(c, x0, y, w, h, config.RADIUS)
                plate(cr)
                cr.set_source_rgba(*config.COLOR)
                cr.fill()
                if config.DOCK_OUTLINE:
                    stroke_inside(cr, plate, plate, OUTLINE_LAYERS, config.OUTLINE_THICKNESS)
                cr.restore()
                return False
            cr.save()
            EDGE.clip_bar(cr, width, area.get_allocated_height())
            cr.save()
            EDGE.to_edge(cr, height)
            notch_path(cr, x0, x1, EDGE.frame, body_h, config.RADIUS)
            cr.set_source_rgba(*config.COLOR)
            cr.fill()
            if config.DOCK_OUTLINE:
                stroke_inside(cr, lambda c: notch_path(c, x0, x1, EDGE.frame, body_h, config.RADIUS),
                              lambda c: notch_edge_path(c, x0, x1, EDGE.frame, body_h, config.RADIUS),
                              OUTLINE_LAYERS, config.OUTLINE_THICKNESS)
            cr.restore()
            cr.restore()
        return False

    def input_region(self):
        if self._w >= 1 and self._h >= 1 and self._tuck < 1:
            x0, y, w, h = self._body_rect()
            return cairo.Region(cairo.RectangleInt(round(x0), round(y), round(w), round(h)))
        return _NO_INPUT
