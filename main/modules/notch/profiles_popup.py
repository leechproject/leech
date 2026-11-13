"""The power profiles menu above the Undercover taskbar (notch.expand.power-profiles.undercover).

Same page and size as the notch's menu, in the bottom right corner: 5 px above the taskbar
and 5 px from the frame (or the screen edge without a frame).
"""

import cairo
import gi

gi.require_version("GtkLayerShell", "0.1")
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import GtkLayerShell, Gtk, Gdk, GLib

from fabric.widgets.window import Window

from modules import config
from modules.common import theme
from modules.animations import anim
from modules.animations.anim import Tween
from modules.common import binds, layerkeys
from modules.common.shapes import rounded_rect, stroke_inside
from modules.common.surface import init_layer
from modules.notch.notch import EXPANDED, BatteryPage

GAP = theme.gap("#taskbar-popup")
FADE_MS = 140


class ProfilesPopup(Window):
    def __init__(self, canvas, on_state=None):
        super().__init__(name="profiles-popup", visible=False, all_visible=False)
        visual = self.get_screen().get_rgba_visual()
        if visual:
            self.set_visual(visual)
        self.set_app_paintable(True)
        init_layer(self)
        GtkLayerShell.set_namespace(self, "leech-profiles")
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.TOP)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.BOTTOM, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.RIGHT, True)
        GtkLayerShell.set_exclusive_zone(self, -1)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.BOTTOM, config.DOCK_H + GAP)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.RIGHT, config.FRAME_RIGHT + GAP)
        self.set_size_request(*EXPANDED)

        self._canvas = canvas
        self.on_state = on_state
        self.is_open = False
        self._alpha = 0.0
        self._tick_source = 0
        self._relax_source = 0
        self._selected = None
        self._nav_mode = None

        self._page = BatteryPage()
        self._buttons = list(self._page.buttons.values())
        for btn in self._buttons:
            btn.add_events(Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK)
            btn.connect("motion-notify-event", lambda _w, _e, b=btn: self._on_motion(b))
            btn.connect("leave-notify-event", lambda _w, _e, b=btn: self._on_leave(b))
        self.add(self._page.widget)
        self.connect("draw", self._on_draw)
        self.connect("key-press-event", self._on_key)
        self._fade = Tween(anim.ms(FADE_MS), self._on_fade_tick)

    def toggle(self):
        if self.is_open:
            self.close()
        else:
            self.open()

    def open(self):
        if self.is_open:
            return
        self.is_open = True
        self._page.refresh()
        if not self._tick_source:
            self._tick_source = GLib.timeout_add_seconds(2, self._tick)
        self._select(None)
        self._nav_mode = None
        self._page.widget.set_opacity(self._alpha)
        self.show_all()
        layerkeys.set_keyboard(self, "exclusive")
        if self._relax_source:
            GLib.source_remove(self._relax_source)
        self._relax_source = GLib.timeout_add(180, self._relax)
        self._canvas.catch("profiles", self.close)
        self._fade.run((self._alpha,), (1.0,))
        self._notify()

    def close(self):
        if not self.is_open:
            return
        self.is_open = False
        if self._relax_source:
            GLib.source_remove(self._relax_source)
            self._relax_source = 0
        layerkeys.set_keyboard(self, "none")
        self._canvas.release("profiles")
        self._fade.run((self._alpha,), (0.0,), self._hidden)
        self._notify()

    def _hidden(self):
        if not self.is_open:
            self.hide()

    def _notify(self):
        if self.on_state is not None:
            self.on_state(self.is_open)

    def _relax(self):
        self._relax_source = 0
        if self.is_open:
            layerkeys.set_keyboard(self, "on_demand")
        return False

    def _tick(self):
        if not self.is_open:
            self._tick_source = 0
            return False
        self._page.refresh_info()
        return True

    def _on_fade_tick(self, values):
        self._alpha = values[0]
        self._page.widget.set_opacity(self._alpha)
        self.queue_draw()

    def _select(self, button):
        for btn in self._buttons:
            ctx = btn.get_style_context()
            (ctx.add_class if btn is button else ctx.remove_class)("sel")
        self._selected = button

    def _on_motion(self, button):
        self._nav_mode = "mouse"
        if self._selected is not button:
            self._select(button)
        return False

    def _on_leave(self, button):
        if self._nav_mode == "mouse" and self._selected is button:
            self._select(None)
        return False

    def _on_key(self, _widget, event):
        if not self.is_open:
            return False
        key = binds.nav_key(event)
        if key == Gdk.KEY_Escape:
            self.close()
            return True
        if not self._buttons:
            return False
        if key in (Gdk.KEY_Left, Gdk.KEY_Up, Gdk.KEY_Right, Gdk.KEY_Down):
            self._nav_mode = "keyboard"
            step = 1 if key in (Gdk.KEY_Right, Gdk.KEY_Down) else -1
            if self._selected in self._buttons:
                index = max(0, min(len(self._buttons) - 1, self._buttons.index(self._selected) + step))
            else:
                index = self._page.start_index()
            self._select(self._buttons[index])
            return True
        if key in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_space) and self._selected in self._buttons:
            self._selected.clicked()
            return True
        return False

    def _on_draw(self, widget, cr):
        w, h = widget.get_allocated_width(), widget.get_allocated_height()
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        cr.push_group()
        plate = lambda c: rounded_rect(c, 0, 0, w, h, config.RADIUS)
        cr.set_source_rgba(*config.COLOR)
        plate(cr)
        cr.fill()
        if config.NOTCH_OUTLINE:
            stroke_inside(cr, plate, plate, theme.outline_layers(), config.OUTLINE_THICKNESS)
        cr.pop_group_to_source()
        cr.paint_with_alpha(self._alpha)
        return False
