import datetime

import cairo
import gi

gi.require_version("GtkLayerShell", "0.1")
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import GtkLayerShell, Gtk, Gdk, GLib

from fabric.widgets.window import Window

from modules import config
from modules.bar.bar import LayoutIndicator, launcher_widget
from modules.common.glyph import GlyphLabel
from modules.parsing import battery
from modules.bar.taskbar_layout import group_start, fade_strength
from modules.animations import anim
from modules.animations.anim import Tween
from modules.common import theme
from modules.common.surface import init_layer
from modules.dock.row import DockRow

HEIGHT = config.DOCK_H
EDGE = theme.pad("#taskbar-plates")
PLATE_H = HEIGHT - 2 * EDGE
FADE = 8
WHEEL_STEP = config.DOCK_ICON + config.DOCK_GAP
SMOOTH_FACTOR = 20
CENTER = Gtk.Align.CENTER


def _launcher_icon():
    icon = config.UNDERCOVER_ICON
    return icon if icon.glyph or icon.path else config.LAUNCHER_BUTTON_ICON


class Taskbar(Window):
    def __init__(self, wm, canvas, on_launcher=None, on_clock=None, on_profiles=None):
        super().__init__(name="taskbar", visible=False, all_visible=False)
        visual = self.get_screen().get_rgba_visual()
        if visual:
            self.set_visual(visual)
        self.set_app_paintable(True)

        init_layer(self)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.TOP)
        for edge in (GtkLayerShell.Edge.BOTTOM, GtkLayerShell.Edge.LEFT, GtkLayerShell.Edge.RIGHT):
            GtkLayerShell.set_anchor(self, edge, True)
        GtkLayerShell.set_exclusive_zone(self, -1)
        self.set_size_request(-1, HEIGHT)

        self.tray = None
        self._start = -1

        leading = None
        if config.BAR_LAUNCHER_SHOWN:
            leading = Gtk.Button()
            leading.set_name("taskbar-launcher")
            leading.set_relief(Gtk.ReliefStyle.NONE)
            leading.set_can_focus(False)
            leading.set_size_request(config.DOCK_ICON, config.DOCK_ICON)
            leading.add(launcher_widget(_launcher_icon()))
            if on_launcher:
                leading.connect("clicked", lambda *_: on_launcher())
        self.row = DockRow(wm, self._on_row_change, False, HEIGHT, leading)
        self.row.widget.set_halign(Gtk.Align.START)

        self._spacer = Gtk.Box()
        holder = Gtk.Box()
        holder.pack_start(self._spacer, False, False, 0)
        holder.pack_start(self.row.widget, False, False, 0)
        self.row.connect_marks(holder)

        self._scroll = Gtk.ScrolledWindow()
        self._scroll.set_policy(Gtk.PolicyType.EXTERNAL, Gtk.PolicyType.NEVER)
        self._scroll.set_shadow_type(Gtk.ShadowType.NONE)
        self._scroll.add(holder)
        self._scroll.set_hexpand(True)
        self._scroll.add_events(Gdk.EventMask.SCROLL_MASK | Gdk.EventMask.SMOOTH_SCROLL_MASK)
        self._scroll.connect("scroll-event", self._on_scroll)
        self._scroll.connect("size-allocate", lambda *_: GLib.idle_add(self._place))
        self._scroll.connect_after("draw", self._draw_fade)
        self._scroll.get_hadjustment().connect("changed", lambda *_: self._scroll.queue_draw())
        self._scroll.get_hadjustment().connect("value-changed", lambda *_: self._scroll.queue_draw())

        static = Gtk.Box(spacing=EDGE)
        static.set_margin_end(EDGE)
        static.set_margin_start(EDGE)
        self._canvas = canvas
        self._tray_window = None
        if config.TRAY_ENABLED:
            plate = Gtk.Box()
            plate.set_name("taskbar-tray")
            plate.set_valign(CENTER)
            self._tray_plate = plate
            if config.TRAY_UNDERCOVER:
                plate.add(self._build_tray_toggle())
            else:
                from modules.bar.tray import CollapsibleTray
                self.tray = CollapsibleTray(True, "taskbar-tray", PLATE_H, canvas)
                plate.add(self.tray)
            static.pack_start(plate, False, False, 0)
        # Power profiles: the battery glyph, as on the bar; opens the notch's power profiles menu.
        self.profiles = None
        if config.BAR_PROFILES_SHOWN and battery.read() is not None:
            self._profiles_label = GlyphLabel(label="")
            self._profiles_label.set_halign(CENTER)
            self._profiles_label.set_valign(CENTER)
            self.profiles = Gtk.Button()
            self.profiles.set_name("taskbar-profiles")
            self.profiles.set_relief(Gtk.ReliefStyle.NONE)
            self.profiles.set_can_focus(False)
            self.profiles.set_valign(CENTER)
            self.profiles.set_size_request(PLATE_H, PLATE_H)
            self.profiles.add(self._profiles_label)
            if on_profiles:
                self.profiles.connect("clicked", lambda *_: on_profiles())
            static.pack_start(self.profiles, False, False, 0)
        self.layout_box = Gtk.Box()
        self.layout_box.set_name("taskbar-layout")
        self.layout_box.set_valign(CENTER)
        self.layout_box.set_size_request(PLATE_H, PLATE_H)
        self.layout_label = Gtk.Label()
        self.layout_label.set_halign(CENTER)
        self.layout_label.set_valign(CENTER)
        self.layout_box.set_center_widget(self.layout_label)
        self.layout_box.set_no_show_all(True)
        self._layout = LayoutIndicator(self.layout_box, self.layout_label, config.BAR_LAYOUT_SHOWN)
        if config.BAR_LAYOUT_SHOWN:
            static.pack_start(self.layout_box, False, False, 0)
        self.clock = None
        if config.BAR_CLOCK_SHOWN:
            self.clock = Gtk.Button(label="")
            self.clock.set_name("taskbar-clock")
            self.clock.set_relief(Gtk.ReliefStyle.NONE)
            self.clock.set_can_focus(False)
            self.clock.set_valign(CENTER)
            self.clock.set_size_request(-1, PLATE_H)
            if on_clock:
                self.clock.connect("clicked", lambda *_: on_clock())
            static.pack_start(self.clock, False, False, 0)

        root = Gtk.Box()
        root.set_name("taskbar-root")
        root.pack_start(self._scroll, True, True, 0)
        root.pack_end(static, False, False, 0)
        root.connect("draw", self._draw_body)
        self.add(root)
        self.show_all()

        wm.subscribe(self._on_state)
        if self.clock is not None:
            self._tick_clock()
        if self.profiles is not None:
            self._tick_battery()
            GLib.timeout_add_seconds(10, self._tick_battery)

    def set_profiles_open(self, is_open):
        if self.profiles is not None:
            context = self.profiles.get_style_context()
            (context.add_class if is_open else context.remove_class)("on")

    def _tick_battery(self):
        data = battery.read()
        if data:
            self._profiles_label.set_label(battery.icon(*data, bool(battery.on_ac())))
        return True

    def _on_state(self, state):
        self.row.set_clients(state.clients)
        self._layout.set_layout(state.layout)

    def _build_tray_toggle(self):
        from modules.bar.tray import _Toggle, watch_outside_press
        from modules.bar.tray_window import TrayWindow
        self._tray_window = TrayWindow(HEIGHT)
        self._tray_open = False
        self._toggle = _Toggle(config.TRAY_ICON, 0.0, self.toggle_tray, PLATE_H)
        self._toggle_tween = Tween(anim.ms(), self._on_toggle_tick)
        watch_outside_press(self._toggle, self._close_tray)
        return self._toggle

    def _close_tray(self):
        if self._tray_open:
            self.toggle_tray()

    def _on_toggle_tick(self, values):
        self._toggle.progress = values[0]
        self._toggle.queue_draw()

    def toggle_tray(self):
        self._tray_open = not self._tray_open
        # Undercover tray: the toggle inverts while its window is open, like the clock and profiles buttons.
        context = self._tray_plate.get_style_context()
        (context.add_class if self._tray_open else context.remove_class)("on")
        self._toggle.queue_draw()
        self._toggle_tween.run((self._toggle.progress,), (1.0 if self._tray_open else 0.0,))
        if self._tray_open:
            origin = self._toggle.translate_coordinates(self, 0, 0)
            center = (origin[0] if origin else 0) + self._toggle.get_allocated_width() / 2
            self._tray_window.open_at(center)
            self._canvas.catch("tray", self.toggle_tray)
        else:
            self._tray_window.close()
            self._canvas.release("tray")

    def debug_tray(self, action):
        if self.tray is not None:
            return self.tray.debug(action)
        if self._tray_window is None:
            return "трей отключён"
        if action == "toggle":
            self.toggle_tray()
        return f"open={self._tray_open}"

    def _on_row_change(self, _rebuilt):
        self._scroll.queue_draw()
        GLib.idle_add(self._place)

    def _place(self):
        area = self._scroll.get_allocated_width()
        group = self.row.widget.get_preferred_width()[1]
        start = group_start(self.get_allocated_width(), area, group, config.UNDERCOVER_LEFT)
        if start != self._start:
            self._start = start
            self._spacer.set_size_request(start, -1)
        return False

    def _on_scroll(self, _widget, event):
        if event.direction == Gdk.ScrollDirection.SMOOTH:
            _ok, dx, dy = event.get_scroll_deltas()
            delta = (dx + dy) * SMOOTH_FACTOR
        elif event.direction in (Gdk.ScrollDirection.UP, Gdk.ScrollDirection.LEFT):
            delta = -WHEEL_STEP
        else:
            delta = WHEEL_STEP
        adj = self._scroll.get_hadjustment()
        adj.set_value(max(0.0, min(adj.get_value() + delta, adj.get_upper() - adj.get_page_size())))
        return True

    def _draw_fade(self, widget, cr):
        adj = self._scroll.get_hadjustment()
        strength = fade_strength(adj.get_value(), adj.get_upper(), adj.get_page_size(), FADE)
        if strength <= 0:
            return False
        width, height = widget.get_allocated_width(), widget.get_allocated_height()
        gradient = cairo.LinearGradient(width, 0, width - FADE, 0)
        r, g, b, a = config.COLOR
        gradient.add_color_stop_rgba(0, r, g, b, a * strength)
        gradient.add_color_stop_rgba(1, r, g, b, 0)
        cr.rectangle(width - FADE, 0, FADE, height)
        cr.set_source(gradient)
        cr.fill()
        return False

    def _draw_body(self, widget, cr):
        cr.set_source_rgba(*config.COLOR)
        cr.rectangle(0, 0, widget.get_allocated_width(), widget.get_allocated_height())
        cr.fill()
        return False

    def set_cc_open(self, is_open):
        if self.clock is None:
            return
        context = self.clock.get_style_context()
        (context.add_class if is_open else context.remove_class)("on")

    def _tick_clock(self):
        now = datetime.datetime.now()
        self.clock.set_label(now.strftime("%H:%M"))
        GLib.timeout_add_seconds(61 - now.second, self._tick_clock)
        return False

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
