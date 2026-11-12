import datetime

import gi

gi.require_version("GtkLayerShell", "0.1")
gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GtkLayerShell, Gtk, GLib, GdkPixbuf

from fabric.widgets.window import Window

from modules import config
from modules.parsing import battery, keyboard
from modules.bar.workspaces import Workspaces
from modules.common.surface import init_layer
from modules.common.glyph import GlyphLabel
from modules.common.shapes import rounded_rect
from modules.bar import split as split_geometry
from modules.bar.squeeze import Squeeze
from modules.bar import outline
from modules.config.geometry import scaled

ICON_FALLBACK_LAUNCHER = "\uf17c"
ICON_POWER = "\uf011"

CENTER = Gtk.Align.CENTER
ORIENTATION = Gtk.Orientation.HORIZONTAL if config.BAR_HORIZONTAL else Gtk.Orientation.VERTICAL
Edge = GtkLayerShell.Edge
EDGES = {"left": Edge.LEFT, "top": Edge.TOP, "right": Edge.RIGHT, "bottom": Edge.BOTTOM}
CLOCK_FORMAT = "%H:%M" if config.BAR_HORIZONTAL else "%H\n%M"
NOTCH_GAP = scaled(split_geometry.NOTCH_GAP, config.BAR_SCALE)


def _center_across(widget):
    if config.BAR_HORIZONTAL:
        widget.set_valign(CENTER)
    else:
        widget.set_halign(CENTER)


def _align_along(widget, align):
    if config.BAR_HORIZONTAL:
        widget.set_halign(align)
    else:
        widget.set_valign(align)


def _box(name):
    box = Gtk.Box(orientation=ORIENTATION, spacing=0)
    box.set_name(name)
    _center_across(box)
    outline.apply(box)
    return box


def _anchors(position):
    edge = EDGES[position]
    if config.BAR_HORIZONTAL:
        return edge, Edge.LEFT, Edge.RIGHT
    return edge, Edge.TOP, Edge.BOTTOM


def _label(text=""):
    lbl = Gtk.Label(label=text)
    lbl.set_halign(CENTER)
    lbl.set_valign(CENTER)
    return lbl


def _glyph(text=""):
    lbl = GlyphLabel(label=text)
    lbl.set_halign(CENTER)
    lbl.set_valign(CENTER)
    return lbl


def _button(child, on_click=None):
    btn = Gtk.Button()
    btn.set_relief(Gtk.ReliefStyle.NONE)
    btn.add(child)
    if on_click:
        btn.connect("clicked", lambda *_: on_click())
    return btn


def launcher_widget(icon=None):
    size = config.LAUNCHER_ICON_SIZE
    icon = icon or config.LAUNCHER_BUTTON_ICON
    if icon.glyph:
        return _glyph(icon.glyph)
    if icon.path:
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(icon.path, size, size)
            image = Gtk.Image.new_from_pixbuf(pixbuf)
            image.set_size_request(size, size)
            return image
        except GLib.Error as e:
            print(f"leech: иконка лаунчера {icon.path}: {e.message}")
            if icon is not config.LAUNCHER_BUTTON_ICON:
                return launcher_widget(config.LAUNCHER_BUTTON_ICON)
    return _glyph(ICON_FALLBACK_LAUNCHER)


def show_layout(box, label, layout):
    if label.get_label() != layout:
        label.set_label(layout)
    if box.get_visible() != bool(layout):
        box.set_visible(bool(layout))
        if layout:
            label.show()


class LayoutIndicator:
    """Индикатор раскладки: при включённом Caps Lock буквы заглавные (`en` → `EN`)."""

    def __init__(self, box, label, shown):
        self._box, self._label = box, label
        self._layout = ""
        if shown:
            keyboard.caps_lock.subscribe(self._show)

    def set_layout(self, layout):
        self._layout = layout
        self._show()

    def _show(self):
        show_layout(self._box, self._label, keyboard.layout_text(self._layout, keyboard.caps_lock.on))


def _substrate_style():
    probe = Gtk.Box()
    probe.set_name("main-inner-sub")
    ctx = probe.get_style_context()
    color = ctx.get_property("background-color", Gtk.StateFlags.NORMAL)
    return (color.red, color.green, color.blue, color.alpha), ctx.get_property("border-radius", Gtk.StateFlags.NORMAL)


class Bar(Window):
    def __init__(self, wm, on_launcher=None, on_battery=None, on_power=None, notch=None, canvas=None):
        super().__init__(name="bar", visible=False, all_visible=False)

        visual = self.get_screen().get_rgba_visual()
        if visual:
            self.set_visual(visual)
        self.set_app_paintable(True)

        init_layer(self)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.TOP)
        for edge in _anchors(config.BAR_POSITION):
            GtkLayerShell.set_anchor(self, edge, True)
        GtkLayerShell.set_exclusive_zone(self, -1)
        if config.BAR_DETACHED:
            for edge, margin in config.BAR_MARGINS.items():
                GtkLayerShell.set_margin(self, EDGES[edge], margin)
        if config.BAR_HORIZONTAL:
            self.set_size_request(-1, config.BAR_WIDTH)
        else:
            self.set_size_request(config.BAR_WIDTH, -1)

        self._wm = wm
        self._canvas = canvas
        self.tray = None
        self._has_battery = battery.read() is not None

        split = notch is not None and config.NOTCH_INSCRIBED
        root = Gtk.Box(orientation=ORIENTATION)
        root.set_name("bar-root")
        root_ctx = root.get_style_context()
        root_ctx.add_class("horizontal" if config.BAR_HORIZONTAL else "vertical")
        inner = Gtk.Box(orientation=ORIENTATION, spacing=0)
        inner.set_name("main-inner-sub")
        top, bottom = self._build_top(on_launcher), self._build_bottom(on_battery, on_power)
        if split or config.BAR_SPLIT:
            root_ctx.add_class("split")
        if split:
            self._notch_gap = 0
            self._substrate = None if config.BAR_SPLIT else _substrate_style()
            self._gap = Gtk.Box()
            left, right = Squeeze(top, at_end=False), Squeeze(bottom, at_end=True)
            left.set_margin_end(NOTCH_GAP)
            right.set_margin_start(NOTCH_GAP)
            inner.set_center_widget(self._gap)
            inner.pack_start(left, True, True, 0)
            inner.pack_end(right, True, True, 0)
            if self._substrate:
                root.connect("draw", self._draw_substrate, inner)
        else:
            inner.pack_start(top, True, True, 0)
            inner.pack_end(bottom, False, False, 0)
        root.pack_start(inner, True, True, 0)
        self.add(root)

        self.bat_box.set_no_show_all(not self._has_battery)
        self.layout_box.set_no_show_all(True)
        self.show_all()

        wm.subscribe(self._on_workspaces)
        if split:
            notch.subscribe_width(self._on_notch_width)
        if config.BAR_PROFILES_SHOWN and self._has_battery:
            self._tick_battery()
            GLib.timeout_add_seconds(10, self._tick_battery)
        if config.BAR_CLOCK_SHOWN:
            self._tick_clock()


    def _build_top(self, on_launcher):
        top = Gtk.Box(orientation=ORIENTATION, spacing=0)
        _align_along(top, Gtk.Align.START)

        if config.BAR_LAUNCHER_SHOWN:
            avatar_box = _box("box-avatar")
            launcher = _button(launcher_widget(), on_launcher)
            launcher.set_name("launcher-btn")
            avatar_box.pack_start(launcher, True, False, 0)
            top.pack_start(avatar_box, False, False, 0)

        ws_box = _box("box-workspaces")
        self._workspaces = Workspaces(self._wm, ORIENTATION, config.BAR_HORIZONTAL)
        if not config.WS_HIGHLIGHT:
            _center_across(self._workspaces)
        ws_box.add(self._workspaces)
        top.pack_start(ws_box, False, False, 0)
        return top

    def _build_bottom(self, on_battery, on_power):
        bottom = Gtk.Box(orientation=ORIENTATION, spacing=0)
        _align_along(bottom, Gtk.Align.END)

        if config.TRAY_ENABLED:
            from modules.bar.tray import build_tray
            tray_box = _box("box-tray")
            self.tray = build_tray(self._canvas)
            tray_box.pack_start(self.tray, True, False, 0)
            bottom.pack_start(tray_box, False, False, 0)

        self.bat_box = _box("box-battery")
        self.bat_label = _glyph()
        self.bat_box.pack_start(_button(self.bat_label, on_battery), True, False, 0)
        if config.BAR_PROFILES_SHOWN:
            bottom.pack_start(self.bat_box, False, False, 0)

        self.layout_box = _box("box-layout")
        self.layout_label = _label()
        self.layout_box.pack_start(self.layout_label, True, False, 0)
        self._layout = LayoutIndicator(self.layout_box, self.layout_label, config.BAR_LAYOUT_SHOWN)
        if config.BAR_LAYOUT_SHOWN:
            bottom.pack_start(self.layout_box, False, False, 0)

        self.clock_label = _label()
        if config.BAR_CLOCK_SHOWN:
            clock_box = _box("box-clock")
            clock_box.pack_start(self.clock_label, True, False, 0)
            bottom.pack_start(clock_box, False, False, 0)

        if config.BAR_POWER_SHOWN:
            power_box = _box("box-power")
            power_box.pack_start(_button(_glyph(ICON_POWER), on_power), True, False, 0)
            bottom.pack_start(power_box, False, False, 0)
        return bottom


    def _on_notch_width(self, width):
        gap = round(split_geometry.gap(width, NOTCH_GAP))
        if gap == self._notch_gap:
            return
        self._notch_gap = gap
        self._gap.set_size_request(max(0, gap - 2 * NOTCH_GAP), -1)
        self.queue_draw()

    def _draw_substrate(self, root, cr, inner):
        alloc = inner.get_allocation()
        margin = inner.get_style_context().get_margin(Gtk.StateFlags.NORMAL)
        x0, y0 = alloc.x + margin.left, alloc.y + margin.top
        w0, h0 = alloc.width - margin.left - margin.right, alloc.height - margin.top - margin.bottom
        color, radius = self._substrate
        cr.set_source_rgba(*color)
        for x, width in split_geometry.pieces(x0, w0, root.get_allocated_width() / 2, self._notch_gap):
            rounded_rect(cr, x, y0, width, h0, min(radius, width / 2, h0 / 2))
            cr.fill()
        return False

    def _on_workspaces(self, state):
        self._workspaces.update(state)
        self._layout.set_layout(state.layout)

    def _tick_clock(self):
        now = datetime.datetime.now()
        self.clock_label.set_label(now.strftime(CLOCK_FORMAT))
        GLib.timeout_add_seconds(61 - now.second, self._tick_clock)
        return False

    def _tick_battery(self):
        data = battery.read()
        if data:
            self.bat_label.set_label(battery.icon(*data, bool(battery.on_ac())))
        return True
