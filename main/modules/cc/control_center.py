import datetime
import math
import subprocess
import time
from types import SimpleNamespace

import cairo
import gi

gi.require_version("GtkLayerShell", "0.1")
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("PangoCairo", "1.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GtkLayerShell, Gtk, Gdk, GLib, GdkPixbuf, Pango, PangoCairo


from modules import config
from modules.parsing import bluetooth
from modules.parsing import caffeine
from modules.cc import calendar_grid
from modules.common import debug
from modules.parsing import network
from modules.parsing import state
from modules.common import timefmt
from modules.animations import anim
from modules.animations.anim import Tween
from modules.cc.capture import Recorder, ScreenshotOverlay, take_screenshot
from modules.cc.floodguard import FloodGuard
from modules.animations.reveal import install_clip
from modules.common.shapes import (OUTLINE_LAYERS, clip_out_band, corner_edge_path, corner_path, rounded_rect,
                                   stroke_inside)
from modules.cc import layout
from modules.cc.record_panel import RecordPanel
from modules.cc.net_panel import NetPanel
from modules.common import layerkeys
from modules.cc import hover
from modules.cc import keynav
from modules.common import binds
from modules.cc.sliders import Slider
from modules.config.values import Custom
from modules.common.surface import ShapedWindow, no_input, init_layer
from modules.common.glyph import GlyphLabel

ICON_WIFI, ICON_ETHERNET = "\uf1eb", "\uf0e8"
ICON_BLUETOOTH = "\uf294"
ICON_DND = "\uf1f6"
ICON_SHOT = "\uf030"
ICON_RECORD = "\uf03d"
ICON_CUSTOM = "\uf120"
CUSTOM_IMAGE_SIZE = 24

PAD = config.KC_PAD
PUSH_PAD = config.KC_PUSH_PAD
INNER_W = config.KC_W - 2 * PAD
W_SMALL = (config.KC_W - 5 * PAD) // 4
METRICS = layout.Metrics(INNER_W, PAD, W_SMALL, config.KC_ROW1_H)
GROUPS = layout.order_groups(config.CC_ROWS, config.CC_ROW_PRIORITIES, config.CC_SLIDERS, config.CC_SLIDERS_PRIORITY)
PLACES, CONTROLS_H = layout.controls(GROUPS, METRICS, config.CC_HORIZONTAL)
SLIDER_SIZE = (INNER_W, W_SMALL) if config.CC_HORIZONTAL else (W_SMALL, METRICS.block_h)
HOVER = config.CC_HOVER
HANDLE_H = hover.HANDLE_H if HOVER else 0
COMPACT_H = HANDLE_H + PAD + CONTROLS_H + PAD
PUSH_H = config.KC_CARD_H + 2 * PUSH_PAD
OSD_W = SLIDER_SIZE[0] + 2 * PAD
OSD_H = SLIDER_SIZE[1] + 2 * PAD
FLOOD_SIZE = config.KC_FLOOD_ICON + 2 * PAD
FULL_FIXED = PAD + CONTROLS_H + PAD + PAD + PAD
CAL_W = config.KC_W - 2 * PAD

SIZES = {
    "hidden": (0, 0),
    "peek": (config.KC_W, hover.HANDLE_H),
    "compact": (config.KC_W, COMPACT_H),
    "compact_push": (config.KC_W, COMPACT_H + PUSH_H),
    "push": (config.KC_W, PUSH_H),
    "osd": (OSD_W, OSD_H),
    "flood": (FLOOD_SIZE, FLOOD_SIZE),
}

LEFT = config.CC_LEFT
TOP = config.CC_TOP
SEP = config.CC_SEPARATE
GAP = config.CC_SEP_GAP if SEP else 0
NEAR = config.LEFT if LEFT else config.RIGHT
EDGE = config.TOP if TOP else config.BOTTOM
FAR = config.BOTTOM if TOP else config.TOP
SURFACE_W = NEAR + GAP + config.KC_W + config.RADIUS
SIGN = -1 if TOP else 1
HANDLE_MODES = ("peek", "compact", "compact_push", "drag")
DRAG_SLOP = 3

_NO_INPUT = no_input()

CENTER = Gtk.Align.CENTER
VERTICAL = Gtk.Orientation.VERTICAL

_ARROWS = {Gdk.KEY_Left: "left", Gdk.KEY_Right: "right", Gdk.KEY_Up: "up", Gdk.KEY_Down: "down"}
# The calendar and notifications lie on the side of the button block away from the CC's anchor edge.
TOWARD_UPPER = "down" if TOP else "up"
TOWARD_BLOCK = "up" if TOP else "down"
FOCUS_LIGHTEN = 0.07
# Shift+Enter held this long toggles the Wi-Fi/Bluetooth menu; a shorter press is a tap.
HOLD_MS = 450


class BeanIcon(Gtk.DrawingArea):
    def __init__(self):
        super().__init__()
        self.get_style_context().add_class("cc-bean")
        self.set_size_request(24, 24)
        self.connect("draw", self._on_draw)

    def _on_draw(self, widget, cr):
        context = widget.get_style_context()
        color = context.get_color(context.get_state())
        w, h = widget.get_allocated_width(), widget.get_allocated_height()
        cr.push_group()
        cr.translate(w / 2, h / 2)
        cr.rotate(-math.pi / 4)
        cr.save()
        cr.scale(9.5, 6.8)
        cr.arc(0, 0, 1, 0, 2 * math.pi)
        cr.restore()
        cr.set_source_rgba(color.red, color.green, color.blue, color.alpha)
        cr.fill()
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.set_line_width(1.8)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.move_to(-8.2, 0.4)
        cr.curve_to(-3.5, -4.6, 3.5, 4.6, 8.2, -0.4)
        cr.stroke()
        cr.pop_group_to_source()
        cr.paint()
        return False


def _draw_crossed(cr, left, right, x, cy, cross=9, gap=9):
    lw, lh = left.get_pixel_size()
    _, rh = right.get_pixel_size()
    cr.move_to(x, cy - lh / 2)
    PangoCairo.show_layout(cr, left)
    cr.set_line_width(2)
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    cx = x + lw + gap + cross / 2
    cr.move_to(cx - cross / 2 + 1, cy - cross / 2 + 1)
    cr.line_to(cx + cross / 2 - 1, cy + cross / 2 - 1)
    cr.move_to(cx + cross / 2 - 1, cy - cross / 2 + 1)
    cr.line_to(cx - cross / 2 + 1, cy + cross / 2 - 1)
    cr.stroke()
    cr.move_to(x + lw + gap + cross + gap, cy - rh / 2)
    PangoCairo.show_layout(cr, right)


def _ordered(widgets):
    return widgets[::-1] if TOP else widgets


def _crossed_width(left, right, cross=9, gap=9):
    return left.get_pixel_size()[0] + gap + cross + gap + right.get_pixel_size()[0]


class DateLabel(Gtk.Box):
    def __init__(self):
        super().__init__()
        self.set_app_paintable(True)
        self.set_name("cc-date")
        self.set_size_request(-1, 20)
        self.connect("draw", self._on_draw)

    def refresh(self):
        self.queue_draw()

    def _on_draw(self, widget, cr):
        today = datetime.date.today()
        left = widget.create_pango_layout(f"{calendar_grid.MONTHS[today.month - 1]} {today.day}")
        right = widget.create_pango_layout(str(today.year))
        context = widget.get_style_context()
        color = context.get_color(context.get_state())
        cr.set_source_rgba(color.red, color.green, color.blue, color.alpha)
        w, h = widget.get_allocated_width(), widget.get_allocated_height()
        _draw_crossed(cr, left, right, (w - _crossed_width(left, right)) / 2, h / 2)
        return False


def _draw_fade(widget, cr):
    w, h = widget.get_allocated_width(), widget.get_allocated_height()
    if TOP:
        cr.translate(0, h)
        cr.scale(1, -1)
    gradient = cairo.LinearGradient(0, 0, 0, h / 2)
    for step in range(9):
        t = step / 8
        gradient.add_color_stop_rgba(t, 0, 0, 0, (1 - t) ** 1.3)
    cr.rectangle(0, 0, w, h / 2)
    cr.set_source(gradient)
    cr.fill()
    return False


class _Button:
    def __init__(self, glyph, text, width, height, on_click, icon_widget=None):
        if icon_widget is not None:
            self.icon = None
            icon = icon_widget
        else:
            self.icon = GlyphLabel(label=glyph)
            self.icon.get_style_context().add_class("cc-icon")
            icon = self.icon
        box = Gtk.Box(orientation=VERTICAL, spacing=2)
        box.set_halign(CENTER)
        box.set_valign(CENTER)
        box.pack_start(icon, False, False, 0)
        self.label = None
        if text:
            self.label = Gtk.Label(label=text)
            self.label.get_style_context().add_class("cc-label")
            box.pack_start(self.label, False, False, 0)

        self.widget = Gtk.Button()
        self.widget.set_relief(Gtk.ReliefStyle.NONE)
        self.widget.set_can_focus(False)
        self.widget.get_style_context().add_class("cc-btn")
        self.widget.set_size_request(width, height)
        self.widget.add(box)
        self.widget.connect("clicked", lambda *_: on_click())

    def set_on(self, on):
        ctx = self.widget.get_style_context()
        (ctx.add_class if on else ctx.remove_class)("on")

    def set_available(self, available):
        self.widget.set_opacity(1.0 if available else 0.4)


class CardSlider(Gtk.Fixed):
    def __init__(self, width, height, x, y, slot):
        super().__init__()
        self._width = width
        self._x, self._y, self._slot = x, y, slot
        self._current = self._old = None
        self._tween = Tween(anim.ms(), self._on_tick)
        self.set_size_request(width, height)
        self.connect("draw", self._clip)

    def do_get_preferred_width(self):
        return self._width, self._width

    @staticmethod
    def _clip(widget, cr):
        cr.rectangle(0, 0, widget.get_allocated_width(), widget.get_allocated_height())
        cr.clip()
        return False

    def show_card(self, card, animate):
        self._finish()
        old, self._current = self._current, card
        if old is not None and animate:
            self._old = old
            self.put(card, self._x, self._y - SIGN * self._slot)
            self._tween.run((0.0,), (1.0,), self._finish)
        else:
            if old is not None:
                old.destroy()
            self.put(card, self._x, self._y)

    def _on_tick(self, values):
        t = values[0]
        if self._current is not None:
            self.move(self._current, self._x, round(self._y - SIGN * self._slot * (1 - t)))
        if self._old is not None:
            self.move(self._old, self._x, round(self._y + SIGN * self._slot * t))

    def _finish(self):
        self._tween.stop()
        if self._old is not None:
            self._old.destroy()
            self._old = None
        if self._current is not None:
            self.move(self._current, self._x, self._y)


class CalendarPlate(Gtk.DrawingArea):
    def __init__(self, width, on_height):
        super().__init__()
        self.set_name("cc-calendar")
        self._width = width
        self._on_height = on_height
        self._h = float(config.KC_CAL_COLLAPSED_H)
        self._expanded = False
        self._focused = False
        today = datetime.date.today()
        self._year, self._month = today.year, today.month
        self._tween = Tween(anim.ms(), self._on_tick)
        self.set_size_request(width, round(self._h))
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect("draw", self._on_draw)
        self.connect("button-press-event", self._on_press)

    def height(self):
        return round(self._h)

    @property
    def expanded(self):
        return self._expanded

    def set_focused(self, focused):
        if focused != self._focused:
            self._focused = focused
            self.queue_draw()

    def shift(self, delta):
        self._year, self._month = calendar_grid.shift_month(self._year, self._month, delta)
        self.queue_draw()

    def toggle(self):
        self._expanded = not self._expanded
        if self._expanded:
            today = datetime.date.today()
            self._year, self._month = today.year, today.month
        target = float(config.KC_CAL_H if self._expanded else config.KC_CAL_COLLAPSED_H)
        self._tween.run((self._h,), (target,))

    def _on_tick(self, values):
        self._h = values[0]
        self.set_size_request(self._width, round(self._h))
        self._on_height()
        self.queue_draw()

    def _on_press(self, _widget, event):
        if event.button != 1:
            return True
        if self._expanded and event.y < 40 and event.x < 44:
            self._year, self._month = calendar_grid.shift_month(self._year, self._month, -1)
            self.queue_draw()
        elif self._expanded and event.y < 40 and event.x > self._width - 44:
            self._year, self._month = calendar_grid.shift_month(self._year, self._month, 1)
            self.queue_draw()
        else:
            self.toggle()
        return True

    def _text(self, text, size=None):
        layout = self.create_pango_layout(text)
        if size is not None:
            desc = self.get_pango_context().get_font_description().copy()
            desc.set_absolute_size(size * Pango.SCALE)
            layout.set_font_description(desc)
        return layout

    def _on_draw(self, widget, cr):
        w = widget.get_allocated_width()
        h = widget.get_allocated_height()
        color = config.KC_COLOR_CAL_ACTIVE if self._expanded else config.KC_COLOR_CAL
        if self._focused:
            color = tuple(min(1.0, c + FOCUS_LIGHTEN) for c in color)
        cr.set_source_rgb(*color)
        rounded_rect(cr, 0, 0, w, h, 10)
        cr.fill()
        if h <= config.KC_CAL_COLLAPSED_H + 2:
            return False
        cr.save()
        cr.rectangle(0, 0, w, h)
        cr.clip()
        self._draw_header(cr, w)
        self._draw_days(cr, w)
        cr.restore()
        return False

    def _draw_header(self, cr, w):
        month = self._text(calendar_grid.MONTHS[self._month - 1])
        year = self._text(str(self._year))
        cy = 8 + 16
        cr.set_source_rgb(1, 1, 1)
        _draw_crossed(cr, month, year, (w - _crossed_width(month, year)) / 2, cy)
        for center, direction in ((22, -1), (w - 22, 1)):
            cr.move_to(center - 3 * direction, cy - 6)
            cr.line_to(center + 3 * direction, cy)
            cr.line_to(center - 3 * direction, cy + 6)
            cr.stroke()

    def _draw_days(self, cr, w):
        side = 7
        col_w = (w - 2 * side) / 7
        top = 8 + 32
        for col, name in enumerate(calendar_grid.weekday_labels(config.CALENDAR_WEEK_START)):
            label = self._text(name, 11)
            lw, lh = label.get_pixel_size()
            cr.set_source_rgb(0.54, 0.54, 0.54)
            cr.move_to(side + col * col_w + (col_w - lw) / 2, top + (20 - lh) / 2)
            PangoCairo.show_layout(cr, label)
        today = datetime.date.today()
        grid_top = top + 20
        for index, (day, in_month) in enumerate(calendar_grid.month_grid(self._year, self._month, config.CALENDAR_WEEK_START)):
            row, col = divmod(index, 7)
            x, y = side + col * col_w, grid_top + row * 28
            is_today = day == today
            if is_today:
                cr.set_source_rgb(1, 1, 1)
                rounded_rect(cr, x + 4, y + 2, col_w - 8, 24, 8)
                cr.fill()
            label = self._text(str(day.day))
            lw, lh = label.get_pixel_size()
            shade = 0.0 if is_today else (1.0 if in_month else 0.27)
            cr.set_source_rgb(shade, shade, shade)
            cr.move_to(x + (col_w - lw) / 2, y + (28 - lh) / 2)
            PangoCairo.show_layout(cr, label)


class ControlCenter(ShapedWindow):
    def __init__(self, wm, server, canvas, controls):
        super().__init__(name="control-center", visible=False, all_visible=False)
        self._server = server
        self._controls = controls
        self._canvas = canvas

        visual = self.get_screen().get_rgba_visual()
        if visual:
            self.set_visual(visual)
        self.set_app_paintable(True)

        init_layer(self)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
        side = GtkLayerShell.Edge.LEFT if LEFT else GtkLayerShell.Edge.RIGHT
        for edge in (side, GtkLayerShell.Edge.TOP, GtkLayerShell.Edge.BOTTOM):
            GtkLayerShell.set_anchor(self, edge, True)
        GtkLayerShell.set_exclusive_zone(self, -1)
        self.set_size_request(SURFACE_W, -1)

        self._w = self._h = 0.0
        self._mode = None
        self._anchor = "slide"
        self._level = 0
        self._open_listeners = []
        self._open_seen = False
        self._has_fullscreen = False
        self._push = None
        self._push_timer = 0
        self._osd = None
        self._osd_timer = 0
        self._poll_source = 0
        self._flooding = False
        self._shake_phase = None
        self._guard = FloodGuard(config.FLOOD_COUNT, config.FLOOD_WINDOW) if config.FLOODGUARD_ENABLED else None
        self._recorder = Recorder()
        self._history = {}
        self._order = []
        self._peeking = False
        self._peek_blocked = False
        self._hover_trigger = False
        self._hover_cc = False
        self._peek_source = 0
        self._drag = None
        self._dnd = state.get_bool("dnd")
        self._caffeine = state.get_bool("caffeine")
        self._kbd = False
        self._kbd_relax = 0
        self._focus = None
        self._last_btn = None
        self._hold = None

        self._area = Gtk.DrawingArea()
        self._area.connect("draw", self._on_draw)
        if HOVER:
            self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK
                            | Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.ENTER_NOTIFY_MASK
                            | Gdk.EventMask.LEAVE_NOTIFY_MASK)
            self.connect("button-press-event", self._on_handle_press)
            self.connect("motion-notify-event", self._on_handle_motion)
            self.connect("button-release-event", self._on_handle_release)
            self.connect("enter-notify-event", self._on_area_cross, True)
            self.connect("leave-notify-event", self._on_area_cross, False)

        self._stack = Gtk.Stack()
        self._stack.set_hhomogeneous(False)
        self._stack.set_vhomogeneous(False)
        self._stack.add_named(self._build_main(), "main")
        self._stack.add_named(self._build_push(), "push")
        self._stack.add_named(self._build_osd(), "osd")
        self._stack.add_named(Gtk.Box(), "flood")
        self._stack.add_named(Gtk.Box(), "peek")

        self._content = Gtk.Box()
        self._content.set_halign(Gtk.Align.START if LEFT else Gtk.Align.END)
        self._content.set_valign(Gtk.Align.START if TOP else Gtk.Align.END)
        self._content.add(self._stack)
        install_clip(self._content, self, self._clip_spec)

        overlay = Gtk.Overlay()
        overlay.add(self._area)
        overlay.add_overlay(self._content)
        self._handle_layer = Gtk.Box()
        self._handle_layer.set_app_paintable(True)
        self._handle_layer.connect("draw", self._draw_handle)
        overlay.add_overlay(self._handle_layer)
        overlay.set_overlay_pass_through(self._handle_layer, True)
        self.add(overlay)

        self._grow = Tween(anim.ms(), self._on_grow_tick)
        self._tuck = 0.0
        self._slide = Tween(anim.ms(), self._on_slide_tick)
        self._shake = Tween(anim.ms(500), self._on_shake_tick)

        self.connect("key-press-event", self._on_key)
        self.connect("key-release-event", self._on_key_release)
        self.show_all()
        self._upper.hide()
        self._push_block.hide()
        self._handle_space.set_visible(HOVER)
        self._rec_btn.label.hide()
        self._panel_box.hide()
        self._apply_layout()

        if self._caffeine:
            caffeine.set_on(True)
        self._dnd_btn.set_on(self._dnd)
        self._caffeine_btn.set_on(caffeine.is_on())
        if self._recorder.active():
            self._rec_btn.set_on(True)
            self._watch_record()

        wm.subscribe(self._on_wm_state)
        controls.subscribe(self._on_controls)
        controls.refresh()
        self._update()
        self._trigger = hover.HoverTrigger(LEFT, TOP, self._on_trigger_hover, self._on_trigger_click) if HOVER else None


    def _build_main(self):
        self._wifi = _Button(ICON_WIFI, None, 0, 0, self._toggle_wifi)
        self._bt = _Button(ICON_BLUETOOTH, None, 0, 0, self._toggle_bluetooth)
        self._caffeine_btn = _Button(None, None, 0, 0, self._toggle_caffeine, icon_widget=BeanIcon())
        self._dnd_btn = _Button(ICON_DND, None, 0, 0, self._toggle_dnd)
        self._shot_btn = _Button(ICON_SHOT, None, 0, 0, self._start_screenshot)
        self._rec_btn = _Button(ICON_RECORD, "00:00", 0, 0, self._toggle_panel)
        self._panel_open = False
        self._rec_panel = RecordPanel(INNER_W, self._recorder, self._toggle_recording, self._follow_panel)
        self._rec_panel.audio, self._rec_panel.microphone = self._recorder.audio, self._recorder.microphone
        self._panel_box = Gtk.Box()
        (self._panel_box.set_margin_bottom if TOP else self._panel_box.set_margin_top)(PAD)
        self._panel_box.set_margin_start(PAD)
        self._panel_box.set_margin_end(PAD)
        self._panel_box.add(self._rec_panel)
        self._net = NetPanel(INNER_W, TOP, self._follow_panel, self._on_net_open)
        self._net.set_margin_start(PAD)
        self._net.set_margin_end(PAD)
        for button, kind in ((self._wifi, "wifi"), (self._bt, "bluetooth")):
            button.widget.connect("button-press-event", self._on_net_button, kind)
        self._kc_sliders = self._make_sliders()
        widgets = {
            "wifi": self._wifi.widget, "bluetooth": self._bt.widget,
            "caffeine": self._caffeine_btn.widget, "dnd": self._dnd_btn.widget,
            "screenshot": self._shot_btn.widget, "record": self._rec_btn.widget,
            **self._kc_sliders,
        }

        block = Gtk.Fixed()
        block.set_size_request(INNER_W, CONTROLS_H)
        self._nav_buttons = []
        for place in PLACES:
            widget = self._custom_button(place.key) if isinstance(place.key, Custom) else widgets[place.key]
            widget.set_size_request(place.w, place.h)
            block.put(widget, place.x, place.y)
            if isinstance(widget, Gtk.Button):
                self._nav_buttons.append((place, widget))
                widget.connect("enter-notify-event", self._on_button_enter)
        self._nav_rects = [(p.x, p.y, p.w, p.h) for p, _ in self._nav_buttons]

        self._calendar = CalendarPlate(CAL_W, self._apply_layout)

        self._cards = Gtk.Box(orientation=VERTICAL, spacing=0)
        self._empty = Gtk.Label(label="No notifications")
        self._empty.set_name("cc-empty")
        self._empty.set_vexpand(True)
        self._cards.pack_start(self._empty, True, True, 0)
        self._zone = Gtk.ScrolledWindow()
        self._zone.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._zone.set_size_request(INNER_W, 60)
        self._zone.add(self._cards)
        self._stick = True
        adjustment = self._zone.get_vadjustment()
        adjustment.connect("changed", self._on_zone_changed)
        adjustment.connect("value-changed", self._on_zone_scrolled)

        fade = Gtk.Box()
        fade.set_app_paintable(True)
        fade.connect("draw", _draw_fade)
        self._time = Gtk.Label()
        self._time.set_name("cc-time")
        self._date = DateLabel()
        header = Gtk.Box(orientation=VERTICAL, spacing=0)
        header.set_valign(Gtk.Align.END if TOP else Gtk.Align.START)
        (header.set_margin_bottom if TOP else header.set_margin_top)(PAD)
        header.pack_start(self._time, False, False, 0)
        header.pack_start(self._date, False, False, 0)
        notifications = Gtk.Overlay()
        notifications.add(self._zone)
        for layer in (fade, header):
            notifications.add_overlay(layer)
            notifications.set_overlay_pass_through(layer, True)
        self._clock_source = 0

        self._upper = Gtk.Box(orientation=VERTICAL, spacing=PAD)
        (self._upper.set_margin_bottom if TOP else self._upper.set_margin_top)(PAD)
        self._upper.set_margin_start(PAD)
        self._upper.set_margin_end(PAD)
        upper = [notifications, self._calendar] if config.CC_CALENDAR else [notifications]
        for widget in _ordered(upper):
            self._upper.pack_start(widget, False, False, 0)

        inner = Gtk.Box(orientation=VERTICAL, spacing=PAD)
        inner.set_border_width(PAD)
        inner.pack_start(block, False, False, 0)

        self._block_slider = CardSlider(config.KC_W, PUSH_H - 1, PUSH_PAD, PUSH_PAD, config.KC_CARD_H + PUSH_PAD)
        separator = Gtk.Box()
        separator.get_style_context().add_class("cc-sep")
        separator.set_size_request(config.KC_W - 2 * PAD, 1)
        separator.set_margin_start(PAD)
        self._push_block = Gtk.Box(orientation=VERTICAL)
        for widget in _ordered([self._block_slider, separator]):
            self._push_block.pack_start(widget, False, False, 0)

        self._handle_space = Gtk.Box()
        self._handle_space.set_size_request(-1, HANDLE_H)
        page = Gtk.Box(orientation=VERTICAL)
        for widget in _ordered([self._handle_space, self._upper, self._push_block, self._net, self._panel_box, inner]):
            page.pack_start(widget, False, False, 0)
        return page

    def _on_zone_changed(self, adjustment):
        if self._stick:
            adjustment.set_value(0 if TOP else adjustment.get_upper() - adjustment.get_page_size())

    def _on_zone_scrolled(self, adjustment):
        if TOP:
            self._stick = adjustment.get_value() <= 1
        else:
            self._stick = adjustment.get_value() >= adjustment.get_upper() - adjustment.get_page_size() - 1

    def _tick_clock(self):
        now = datetime.datetime.now()
        self._time.set_label(now.strftime("%H:%M"))
        self._date.refresh()
        if self._mode != "full":
            self._clock_source = 0
            return False
        self._clock_source = GLib.timeout_add_seconds(61 - now.second, self._tick_clock)
        return False

    def _start_clock(self):
        if self._clock_source:
            GLib.source_remove(self._clock_source)
            self._clock_source = 0
        self._tick_clock()

    def _make_sliders(self):
        return {
            "brightness": Slider("brightness", *SLIDER_SIZE, self._controls.set_brightness, config.CC_HORIZONTAL),
            "volume": Slider("volume", *SLIDER_SIZE, self._controls.set_volume, config.CC_HORIZONTAL),
        }

    def _custom_button(self, custom):
        icon = custom.icon
        image = None
        if icon is not None and icon.path:
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(icon.path, CUSTOM_IMAGE_SIZE, CUSTOM_IMAGE_SIZE)
                image = Gtk.Image.new_from_pixbuf(pixbuf)
            except GLib.Error as e:
                print(f"leech: {custom.name}: {icon.path}: {e.message}")
        glyph = icon.glyph if icon is not None and icon.glyph else ICON_CUSTOM
        button = _Button(glyph, None, 0, 0, lambda: self._run_custom(custom), icon_widget=image)
        return button.widget

    def _run_custom(self, custom):
        debug.log("cc", f"{custom.name}: {custom.cmd}")
        self._level = 0
        self._cancel_push()
        self._update()
        try:
            subprocess.Popen(["sh", "-c", custom.cmd], start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as e:
            print(f"leech: {custom.name}: {e}")

    def _build_osd(self):
        self._osd_sliders = self._make_sliders()
        self._osd_stack = Gtk.Stack()
        for name, slider in self._osd_sliders.items():
            self._osd_stack.add_named(slider, name)
        page = Gtk.Box()
        page.set_border_width(PAD)
        page.add(self._osd_stack)
        return page

    def _build_push(self):
        self._push_slider = CardSlider(config.KC_W, PUSH_H, PUSH_PAD, PUSH_PAD, config.KC_CARD_H + PUSH_PAD)
        return self._push_slider

    def _make_card(self, n, width):
        pad = config.KC_CARD_PAD
        if n.icon is not None:
            icon = Gtk.Image.new_from_gicon(n.icon, Gtk.IconSize.DND)
        else:
            icon = Gtk.Image.new_from_icon_name("dialog-information", Gtk.IconSize.DND)
        icon.set_pixel_size(config.KC_CARD_ICON)
        icon.set_valign(CENTER)
        icon.set_margin_start(pad)

        title = Gtk.Label(label=n.summary or n.app_name)
        title.set_name("cc-card-title")
        title.set_xalign(0)
        title.set_ellipsize(Pango.EllipsizeMode.END)
        title.set_max_width_chars(34)

        body = Gtk.Label(label=n.body)
        body.set_name("cc-card-body")
        body.set_xalign(0)
        body.set_ellipsize(Pango.EllipsizeMode.END)
        body.set_max_width_chars(38)

        text = Gtk.Box(orientation=VERTICAL, spacing=0)
        text.set_valign(CENTER)
        text.set_margin_start(10)
        text.set_margin_end(pad)
        text.pack_start(title, False, False, 0)
        text.pack_start(body, False, False, 0)

        card = Gtk.Box()
        card.get_style_context().add_class("cc-card")
        card.set_size_request(width, config.KC_CARD_H)
        card.pack_start(icon, False, False, 0)
        card.pack_start(text, True, True, 0)
        card.show_all()
        return card


    def on_notification(self, n):
        dnd = self._dnd and not (n.local and n.critical)
        if dnd and not config.DND_TO_LIST:
            debug.log("notify", f"id={n.id} отброшено: dnd, ignore-dnd-inlist = n")
            return
        self._add_history(n)
        if not config.PUSH_ALLOWED:
            debug.log("notify", f"id={n.id} только в список: push-allowed = n")
            return
        if dnd or self._has_fullscreen or self._flooding or self._level == 2:
            debug.log("notify", f"id={n.id} только в список: dnd={dnd} fullscreen={self._has_fullscreen} "
                                f"flooding={self._flooding} level={self._level}")
            return
        if self._level == 0 and self._guard is not None and self._guard.register(n):
            debug.log("notify", f"id={n.id} сработал флуд-гард")
            self._start_flood()
        else:
            debug.log("notify", f"id={n.id} пуш, level={self._level}")
            self._show_push(n)

    def remove_notification(self, nid):
        self._drop_history(nid)

    def _add_history(self, n):
        self._drop_history(n.id)
        card = self._make_card(n, config.KC_W - 2 * PAD)
        (card.set_margin_bottom if TOP else card.set_margin_top)(PAD)
        wrapper = Gtk.EventBox()
        wrapper.add(card)
        wrapper.connect("button-press-event", lambda *_: self._dismiss(n.id))
        revealer = Gtk.Revealer()
        revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN if TOP else Gtk.RevealerTransitionType.SLIDE_UP)
        revealer.set_transition_duration(anim.ms())
        revealer.add(wrapper)
        revealer.show_all()
        self._cards.pack_start(revealer, False, False, 0)
        if TOP:
            self._cards.reorder_child(revealer, 0)
        self._stick = True
        self._history[n.id] = revealer
        self._order.insert(0, n.id)

        card.set_opacity(0.0)
        Tween(anim.ms(), lambda v: card.get_parent() is not None and card.set_opacity(v[0]), card).run((0.0,), (1.0,))
        GLib.idle_add(lambda: (revealer.set_reveal_child(True), False)[1])

        while len(self._order) > config.HISTORY_MAX:
            self._drop_history(self._order[-1])
        self._sync_empty()

    def _drop_history(self, nid):
        revealer = self._history.pop(nid, None)
        if revealer is not None:
            index = self._order.index(nid)
            self._order.remove(nid)
            if self._focus == ("card", nid):
                # Keep the focus in the list: the next older card, else the newer one, else the calendar.
                self._focus = None
                if self._order:
                    self._set_focus(("card", self._order[min(index, len(self._order) - 1)]))
                else:
                    self._set_focus(("cal",) if config.CC_CALENDAR else self._button_focus())
            revealer.destroy()
        self._sync_empty()

    def _sync_empty(self):
        self._empty.set_visible(not self._order)
        end = Gtk.Align.START if TOP else Gtk.Align.END
        self._cards.set_valign(Gtk.Align.FILL if not self._order else end)

    def _dismiss(self, nid):
        self._drop_history(nid)
        self._server.dismiss(nid)
        return True


    def _on_controls(self, kind, osd):
        value = self._controls.volume if kind == "volume" else self._controls.brightness
        muted = self._controls.muted if kind == "volume" else False
        self._kc_sliders[kind].set_value(value, muted)
        self._osd_sliders[kind].set_value(value, muted)
        if osd and self._level == 0 and self._push is None and not self._flooding:
            self._show_osd(kind)

    def _show_osd(self, kind):
        self._osd = kind
        self._osd_stack.set_visible_child_name(kind)
        if self._osd_timer:
            GLib.source_remove(self._osd_timer)
        self._osd_timer = GLib.timeout_add(int(config.OSD_SECONDS * 1000), self._end_osd)
        self._update()

    def _end_osd(self):
        self._osd_timer = 0
        self._osd = None
        self._update()
        return False

    def _cancel_osd(self):
        if self._osd_timer:
            GLib.source_remove(self._osd_timer)
            self._osd_timer = 0
        self._osd = None

    def _show_push(self, n):
        self._cancel_osd()
        self._push = n
        slider = self._block_slider if self._level == 1 else self._push_slider
        card = self._make_card(n, config.KC_W - 2 * PUSH_PAD)
        slider.show_card(card, animate=self._mode in ("push", "compact_push"))
        seconds = n.timeout_ms / 1000 if n.timeout_ms > 0 else config.PUSH_SECONDS
        if self._push_timer:
            GLib.source_remove(self._push_timer)
        self._push_timer = GLib.timeout_add(int(min(seconds, 10) * 1000), self._end_push)
        self._update()

    def _end_push(self):
        self._push_timer = 0
        self._push = None
        self._update()
        return False

    def _cancel_push(self):
        if self._push_timer:
            GLib.source_remove(self._push_timer)
            self._push_timer = 0
        self._push = None

    def _start_flood(self):
        self._cancel_push()
        self._flooding = True
        self._go("flood")

    def _on_shake_tick(self, values):
        self._shake_phase = values[0]
        self._area.queue_draw()

    def _finish_flood(self):
        self._shake_phase = None
        self._flooding = False
        if self._guard is not None:
            self._guard.reset()
        self._set_dnd(True)
        self._level = 0
        self._update()


    def _set_dnd(self, value):
        self._dnd = value
        state.set_bool("dnd", value)
        self._dnd_btn.set_on(value)
        if value:
            self._cancel_push()

    def _toggle_dnd(self):
        self._set_dnd(not self._dnd)
        self._update()

    def _toggle_caffeine(self):
        new = not self._caffeine
        if caffeine.set_on(new):
            self._caffeine = new
            state.set_bool("caffeine", new)
        self._caffeine_btn.set_on(caffeine.is_on())

    def _toggle_wifi(self):
        enable = not network.wifi_enabled()
        network.set_wifi(enable)
        self._wifi.set_on(enable)
        GLib.timeout_add(800, self._refresh_once)
        GLib.timeout_add(1500, lambda: (self._net.kind == "wifi" and self._net.refresh(), False)[1])

    def _toggle_bluetooth(self):
        enable = not bluetooth.powered()
        bluetooth.set_powered(enable)
        self._bt.set_on(bool(bluetooth.powered()))

    def _toggle_panel(self):
        if self._panel_open:
            self._panel_open = False
            self._relayout(self._sync_panel)
        else:
            self._panel_open = True
            self._panel_box.show()
            self._relayout()

    def debug_press(self, name):
        if name == "panel":
            self._toggle_panel()
        elif name in ("hover", "unhover"):
            self._on_trigger_hover(name == "hover")
        elif name == "trigger":
            self._on_trigger_click()
        elif name.startswith("net:"):
            self._net.toggle(name[4:])
        elif name.startswith("drag:"):
            self._debug_drag(int(name[5:]))
        else:
            self._rec_panel.press(name)

    def _debug_drag(self, distance):
        x, y, w, h = self._rect()
        start = y + h - 2 if TOP else y + 2
        steps = [start - SIGN * distance * k / 10 for k in range(1, 11)]
        if not self._on_handle_press(None, SimpleNamespace(button=1, x=x + w / 2, y=start)):
            return

        def step():
            if not steps:
                self._on_handle_release(None, SimpleNamespace(button=1))
                return False
            self._on_handle_motion(None, SimpleNamespace(x=0, y=steps.pop(0)))
            return True
        GLib.timeout_add(30, step)

    def _sync_panel(self):
        self._panel_box.set_visible(self._panel_open)

    def _panel_extra(self):
        return (PAD + self._rec_panel.height() if self._panel_open else 0) + self._net.height()

    def _on_net_button(self, _widget, event, kind):
        if event.button != 3:
            return False
        if self._level > 0:
            self._net.toggle(kind)
        return True

    def _on_net_open(self, _opened):
        self._sync_keyboard()

    def _sync_keyboard(self):
        want = self._level > 0
        if want == self._kbd:
            return
        self._kbd = want
        if self._kbd_relax:
            GLib.source_remove(self._kbd_relax)
            self._kbd_relax = 0
        if want:
            # Take the keyboard at once (the CC is usually opened by a bind), then relax so
            # the pointer keeps working on other layer surfaces (see layerkeys.RELAX).
            layerkeys.set_keyboard(self, "exclusive")
            self._kbd_relax = GLib.timeout_add(180, self._relax_keyboard)
        else:
            layerkeys.set_keyboard(self, "none")
            if self._hold is not None and self._hold[1]:
                GLib.source_remove(self._hold[1])
            self._hold = None
            self._set_focus(None)
            self._last_btn = None

    def _relax_keyboard(self):
        self._kbd_relax = 0
        if self._kbd:
            layerkeys.set_keyboard(self, "on_demand")
        return False

    def _is_menu_key(self, event):
        return binds.matches(config.LAUNCHER_MENU_BIND, event) or (
            event.keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) and event.state & Gdk.ModifierType.SHIFT_MASK)

    def _on_key(self, _widget, event):
        if self._level == 0:
            return False
        if self._hold is not None:
            # Key repeat while the menu key is held.
            return Gdk.keyval_to_lower(event.keyval) == self._hold[0] or self._net.key_press(event)
        if self._is_menu_key(event) and not self._net.typing:
            self._start_hold(event)
            return True
        if self._net.is_open:
            return self._net.key_press(event)
        key = event.keyval
        if key == Gdk.KEY_Escape:
            self._set_level(0)
            return True
        if key in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_space):
            self._focus_activate()
            return True
        if key in _ARROWS:
            self._focus_move(_ARROWS[key])
            return True
        return False

    # Keyboard focus: ("btn", index) in the button block; on stage 2 also ("cal",) and ("card", nid).
    def _button_focus(self):
        if not self._nav_buttons:
            return None
        return ("btn", self._last_btn if self._last_btn is not None else 0)

    def _focus_widget(self, focus):
        if focus is None:
            return None
        if focus[0] == "btn":
            return self._nav_buttons[focus[1]][1]
        if focus[0] == "card":
            revealer = self._history.get(focus[1])
            return revealer.get_child().get_child() if revealer is not None else None
        return None

    def _set_focus(self, focus):
        if focus == self._focus:
            return
        old = self._focus_widget(self._focus)
        if old is not None:
            old.get_style_context().remove_class("kfocus")
        if self._focus == ("cal",):
            self._calendar.set_focused(False)
        self._focus = focus
        if focus is None:
            return
        if focus[0] == "btn":
            self._last_btn = focus[1]
        widget = self._focus_widget(focus)
        if widget is not None:
            widget.get_style_context().add_class("kfocus")
        if focus == ("cal",):
            self._calendar.set_focused(True)
        elif focus[0] == "card":
            self._scroll_to_card(focus[1])

    def _scroll_to_card(self, nid):
        revealer = self._history.get(nid)
        if revealer is None:
            return
        alloc = revealer.get_allocation()
        adjustment = self._zone.get_vadjustment()
        value, page = adjustment.get_value(), adjustment.get_page_size()
        if alloc.y < value:
            adjustment.set_value(alloc.y)
        elif alloc.y + alloc.height > value + page:
            adjustment.set_value(alloc.y + alloc.height - page)

    def _upper_open(self):
        return self._level == 2 and self._mode == "full"

    def _focus_move(self, direction):
        focus = self._focus
        if focus is None:
            self._set_focus(self._button_focus())
            return
        kind = focus[0]
        if kind == "btn":
            index = keynav.step(self._nav_rects, focus[1], direction)
            if index is not None:
                self._set_focus(("btn", index))
            elif direction == TOWARD_UPPER and self._upper_open():
                if config.CC_CALENDAR:
                    self._set_focus(("cal",))
                elif self._order:
                    self._set_focus(("card", self._order[0]))
            return
        if kind == "cal":
            if direction == TOWARD_UPPER and self._order:
                self._set_focus(("card", self._order[0]))
            elif direction == TOWARD_BLOCK:
                self._set_focus(self._button_focus())
            elif direction in ("left", "right") and self._calendar.expanded:
                self._calendar.shift(-1 if direction == "left" else 1)
            return
        index = self._order.index(focus[1])
        if direction == TOWARD_UPPER and index + 1 < len(self._order):
            self._set_focus(("card", self._order[index + 1]))
        elif direction == TOWARD_BLOCK:
            if index > 0:
                self._set_focus(("card", self._order[index - 1]))
            else:
                self._set_focus(("cal",) if config.CC_CALENDAR else self._button_focus())

    def _focus_activate(self):
        focus = self._focus
        if focus is None:
            self._set_focus(self._button_focus())
        elif focus[0] == "btn":
            self._nav_buttons[focus[1]][1].clicked()
        elif focus[0] == "cal":
            self._calendar.toggle()
        else:
            self._dismiss(focus[1])

    # Shift+Enter: a tap opens the context menu of the row under focus in the Wi-Fi/Bluetooth menu;
    # holding it opens that menu from a focused Wi-Fi/Bluetooth button or closes it when open.
    def _start_hold(self, event):
        source = GLib.timeout_add(HOLD_MS, self._on_hold)
        self._hold = (Gdk.keyval_to_lower(event.keyval), source)

    def _on_hold(self):
        if self._hold is not None:
            self._hold = (self._hold[0], 0)
        if self._net.is_open:
            self._net.close()
        else:
            self._focus_menu()
        return False

    def _on_key_release(self, _widget, event):
        if self._hold is None or Gdk.keyval_to_lower(event.keyval) != self._hold[0]:
            return False
        _, source = self._hold
        self._hold = None
        if source:
            GLib.source_remove(source)
            if self._net.is_open:
                self._net.menu_tap()
        return True

    def _focus_menu(self):
        if self._focus is None or self._focus[0] != "btn":
            return
        widget = self._nav_buttons[self._focus[1]][1]
        kind = "wifi" if widget is self._wifi.widget else "bluetooth" if widget is self._bt.widget else None
        if kind is not None:
            self._net.open(kind)

    def _on_button_enter(self, _widget, _event):
        if self._focus is not None and self._focus[0] == "btn":
            self._set_focus(None)
        return False

    def _toggle_recording(self):
        if self._recorder.active():
            self._recorder.stop()
        elif self._recorder.start(self._rec_panel.audio, self._rec_panel.microphone):
            self._rec_btn.set_on(True)
            self._watch_record()

    def _update_record_label(self):
        label = self._rec_btn.label
        if self._recorder.active():
            label.set_label(timefmt.stopwatch(self._recorder.elapsed()))
            label.show()
            self._rec_btn.icon.hide()
        else:
            label.hide()
            self._rec_btn.icon.show()
        self._rec_panel.refresh()

    def _watch_record(self):
        if self._recorder.active():
            self._update_record_label()
            delay = 1000 - int(self._recorder.elapsed() * 1000) % 1000
            GLib.timeout_add(max(50, delay + 5), self._watch_record)
            return False
        self._rec_btn.set_on(False)
        self._update_record_label()
        self._server.notify_local("Recording saved", str(self._recorder.path), "video-x-generic")
        return False

    def _start_screenshot(self):
        self._level = 0
        self._cancel_push()
        self._update()
        GLib.timeout_add(350, self._open_overlay)

    def _open_overlay(self):
        self._overlay = ScreenshotOverlay(self._on_shot_choice)
        return False

    def _on_shot_choice(self, kind, region):
        if kind == "cancel":
            return

        def shoot():
            take_screenshot(region, self._on_shot_done)
            return False
        GLib.timeout_add(250, shoot)

    def _on_shot_done(self, path):
        if path:
            self._server.notify_local("Screenshot saved", str(path), "camera-photo")
        else:
            self._server.notify_local("Screenshot failed", "grim не смог сделать снимок", "dialog-error")

    def _refresh_once(self):
        self._refresh_states()
        return False

    def _refresh_states(self):
        wifi = network.wifi_enabled()
        self._wifi.set_available(wifi is not None)
        self._wifi.set_on(bool(wifi))
        self._wifi.icon.set_label(ICON_ETHERNET if network.connection() == "ethernet" else ICON_WIFI)

        powered = bluetooth.powered()
        self._bt.set_available(powered is not None)
        self._bt.set_on(bool(powered))

        self._rec_btn.set_on(self._recorder.active())
        self._update_record_label()
        self._controls.refresh()

    def _poll(self):
        if self._level == 0:
            self._poll_source = 0
            return False
        self._refresh_states()
        return True


    def is_idle(self):
        return self._mode in (None, "hidden") and self._h < 1 and self._drag is None

    def close_now(self):
        self._peeking = self._hover_trigger = self._hover_cc = False
        if self._peek_source:
            GLib.source_remove(self._peek_source)
            self._peek_source = 0
        self._set_level(0)
        for _ in range(4):
            running = [tween for tween in (self._shake, self._slide, self._grow) if tween.running()]
            if not running:
                break
            for tween in running:
                tween.finish()

    def subscribe_open(self, callback):
        self._open_listeners.append(callback)
        callback(self._level > 0)

    def _notify_open(self):
        is_open = self._level > 0
        if is_open != self._open_seen:
            self._open_seen = is_open
            for callback in self._open_listeners:
                callback(is_open)

    def toggle(self, level=1):
        if config.UNDERCOVER:
            level = 2
        if level not in config.CC_STAGES:
            return f"стадия {level} КЦ отключена в конфиге"
        if self._flooding:
            return None
        self._set_level(0 if self._level == level else level)

    def _set_level(self, level):
        self._drag = None
        self._cancel_push()
        self._cancel_osd()
        self._level = level
        if self._level and not self._poll_source:
            self._refresh_states()
            self._poll_source = GLib.timeout_add_seconds(2, self._poll)
        self._update()

    def _on_trigger_hover(self, inside):
        self._hover_trigger = inside
        if not inside:
            self._peek_blocked = False
        self._sync_peek()

    def _point(self, event):
        x, y = event.x, event.y
        window, top = getattr(event, "window", None), self.get_window()
        while window is not None and window != top:
            x, y = window.coords_to_parent(x, y)
            window = window.get_effective_parent()
        return x, y

    def _on_area_cross(self, _widget, event, inside):
        if event.window != self.get_window():
            return False
        if not inside and event.detail == Gdk.NotifyType.INFERIOR:
            return False
        self._hover_cc = inside and self._mode == "peek"
        self._sync_peek()
        return False

    def _sync_peek(self):
        want = (self._hover_trigger or self._hover_cc) and not self._peek_blocked and not self._has_fullscreen
        if want:
            if self._peek_source:
                GLib.source_remove(self._peek_source)
                self._peek_source = 0
            if not self._peeking:
                self._peeking = True
                self._update()
        elif self._peeking and not self._peek_source:
            self._peek_source = GLib.timeout_add(250, self._end_peek)

    def _end_peek(self):
        self._peek_source = 0
        if not (self._hover_trigger or self._hover_cc) or self._peek_blocked or self._has_fullscreen:
            self._peeking = False
            self._update()
        return False

    def _on_trigger_click(self):
        if self._has_fullscreen or self._flooding or self._drag is not None:
            return False
        if self._level == 1:
            self._peek_blocked = True
            self._peeking = False
            self._set_level(0)
        elif 1 in config.CC_STAGES:
            self._set_level(1)
        return True

    def _on_handle(self, x, y):
        if self._mode not in HANDLE_MODES or self._mode == "drag":
            return False
        rx, ry, w, h = self._rect()
        top = ry + h - hover.HANDLE_H if TOP else ry
        return rx <= x <= rx + w and top <= y <= top + hover.HANDLE_H

    def _on_handle_press(self, _widget, event):
        x, y = self._point(event)
        if event.button != 1 or self._flooding or not self._on_handle(x, y):
            return False
        self._drag = {"y": y, "h": self._h, "from": self._mode, "moved": False, "done": False}
        return True

    def _on_handle_motion(self, _widget, event):
        drag = self._drag
        if drag is None or drag["done"]:
            return False
        dy = SIGN * (drag["y"] - self._point(event)[1])
        if not drag["moved"]:
            if abs(dy) < DRAG_SLOP or 2 not in config.CC_STAGES:
                return True
            drag["moved"] = True
            self._begin_drag()
        low = self._target("compact")[1]
        self._h = min(max(drag["h"] + dy, low), self._full_height())
        self._area.queue_draw()
        self._handle_layer.queue_draw()
        self._apply_input()
        if self._h >= self._surface_height() * 5 / 6:
            drag["done"] = True
            self._finish_drag(2)
        return True

    def _on_handle_release(self, _widget, event):
        drag, self._drag = self._drag, None
        if drag is None or event.button != 1:
            return False
        if drag["done"]:
            return True
        if not drag["moved"]:
            if drag["from"] == "peek":
                self._on_trigger_click()
            elif 2 in config.CC_STAGES:
                self._set_level(2)
            return True
        self._finish_drag(2 if self._h >= self._surface_height() / 2 else 1)
        return True

    def _begin_drag(self):
        self._cancel_push()
        self._cancel_osd()
        if self._level == 0:
            self._level = 1
            if not self._poll_source:
                self._refresh_states()
                self._poll_source = GLib.timeout_add_seconds(2, self._poll)
        self._canvas.catch("cc", self._close_by_click)
        self._grow.stop()
        self._mode = "drag"
        self._anchor = "fixed"
        self._w = config.KC_W
        self._stack.set_visible_child_name("main")
        self._push_block.hide()
        self._handle_space.hide()
        self._upper.show()
        self._start_clock()
        self._apply_layout()

    def _finish_drag(self, level):
        self._level = level
        self._update()

    def _draw_handle(self, widget, cr):
        if not HOVER or self._mode not in HANDLE_MODES or self._w < 1 or self._h < hover.HANDLE_H:
            return False
        x, y, w, h = self._rect()
        self._clip_inner(cr)
        hover.draw_handle(cr, x, y, w, h, not TOP)
        return False

    def _on_wm_state(self, wm_state):
        if wm_state.fullscreen == self._has_fullscreen:
            return
        self._has_fullscreen = wm_state.fullscreen
        if self._trigger is not None:
            self._trigger.set_visible(not wm_state.fullscreen)
        self._sync_peek()
        self._apply_layout()
        if self._flooding:
            return
        if self._level > 0 or self._push is not None:
            self._mode = None
            self._update()
        else:
            self._area.queue_draw()

    def _frame(self):
        if self._has_fullscreen:
            return 0, 0, 0
        return NEAR, EDGE, FAR

    def _bar_overlap(self):
        if self._has_fullscreen:
            return 0, 0
        near_side = "left" if LEFT else "right"
        edge_side = "top" if TOP else "bottom"
        return (config.BAR_BAND[1] if config.BAR_POSITION == near_side else 0,
                config.BAR_BAND[1] if config.BAR_POSITION == edge_side else 0)

    def _bar_bands(self):
        if self._has_fullscreen:
            return (0, 0), (0, 0)
        near_side = "left" if LEFT else "right"
        edge_side = "top" if TOP else "bottom"
        return (config.BAR_BAND if config.BAR_POSITION == near_side else (0, 0),
                config.BAR_BAND if config.BAR_POSITION == edge_side else (0, 0))

    def _surface_height(self):
        monitor = GtkLayerShell.get_monitor(self)
        if monitor is not None:
            return monitor.get_geometry().height
        height = self.get_allocated_height()
        return height if height > 100 else config.KC_FULL_H + config.TOP + config.BOTTOM

    def _full_height(self):
        _, edge, far = self._frame()
        return self._surface_height() - far - edge - 2 * GAP

    def _rect(self):
        near, edge, _ = self._frame()
        width, height = SURFACE_W, self._surface_height()
        x = width - near - GAP - self._w
        y = height - edge - GAP - self._h
        if LEFT:
            x = width - x - self._w
        if TOP:
            y = height - y - self._h
        return x, y + SIGN * self._tuck, self._w, self._h

    def _apply_layout(self):
        near, edge, _ = self._frame()
        (self._content.set_margin_start if LEFT else self._content.set_margin_end)(near + GAP)
        (self._content.set_margin_top if TOP else self._content.set_margin_bottom)(edge + GAP)
        calendar_h = self._calendar.height() + PAD if config.CC_CALENDAR else 0
        zone_h = self._full_height() - (FULL_FIXED - PAD) - calendar_h - self._panel_extra()
        self._zone.set_size_request(config.KC_W - 2 * PAD, max(60, zone_h))

    def _close_by_click(self):
        self._level = 0
        self._update()

    def _update(self):
        if self._flooding:
            return
        self._notify_open()
        if self._level > 0:
            self._canvas.catch("cc", self._close_by_click)
        else:
            self._canvas.release("cc")
        self._sync_keyboard()
        if self._level != 2 and self._focus is not None and self._focus[0] != "btn":
            self._set_focus(self._button_focus())
        if self._level == 0:
            self._peeking = self._peeking and (self._hover_trigger or self._hover_cc) and not self._peek_blocked
            mode = "push" if self._push is not None else ("osd" if self._osd else ("peek" if self._peeking else "hidden"))
        elif self._level == 1:
            mode = "compact_push" if self._push is not None else "compact"
        else:
            mode = "full"
        self._go(mode)

    def _go(self, mode):
        if mode == self._mode:
            return
        previous, self._mode = self._mode, mode
        self._shake.stop()
        self._shake_phase = None
        staged = {"compact", "compact_push", "full", "drag"}
        self._anchor = "fixed" if previous in staged and mode in staged else "slide"
        self._apply_layout()

        if mode != "peek":
            self._hover_cc = False
        if mode in ("compact", "compact_push", "full"):
            self._stack.set_visible_child_name("main")
            self._handle_space.set_visible(HOVER and mode != "full")
            if mode == "compact_push":
                self._push_block.show()
            if mode == "full":
                self._push_block.hide()
                self._upper.show()
                self._start_clock()
        elif mode in ("push", "flood", "osd", "peek"):
            self._stack.set_visible_child_name(mode)

        def settled():
            if self._mode != mode:
                return
            if mode in ("compact", "compact_push", "hidden"):
                self._upper.hide()
            if mode == "hidden":
                self._net.close(instant=True)
            if mode == "hidden" and not self._recorder.active():
                self._panel_open = False
                self._sync_panel()
            if mode != "compact_push":
                self._push_block.hide()
            if mode == "flood":
                self._begin_shake()

        if SEP:
            self._go_sep(mode, settled)
            return
        if mode == "hidden":
            target = (round(self._w), 0)
        else:
            target = self._target(mode)
            if self._h < 1:
                self._w = target[0]
        if (round(self._w), round(self._h)) == target:
            settled()
        else:
            self._grow.run((self._w, self._h), target, settled)

    def _go_sep(self, mode, settled):
        if mode == "hidden":
            self._grow.stop()
            if self._h < 1:
                self._tuck = 0.0
                settled()
                return
            self._slide.run((self._tuck,), (self._h + GAP,), lambda: self._tucked(mode, settled))
            return
        target = self._target(mode)
        if self._h < 1:
            self._anchor = "fixed"
            self._tuck = target[1] + GAP
            self._on_grow_tick(target)
        resize = (round(self._w), round(self._h)) != target
        if self._tuck > 0:
            self._slide.run((self._tuck,), (0.0,), None if resize else settled)
        if resize:
            self._grow.run((self._w, self._h), target, settled)
        elif self._tuck <= 0:
            settled()

    def _tucked(self, mode, settled):
        if self._mode != mode:
            return
        self._tuck = 0.0
        self._on_grow_tick((self._w, 0.0))
        settled()

    def _on_slide_tick(self, values):
        self._tuck = values[0]
        self._area.queue_draw()
        self._content.queue_draw()
        self._handle_layer.queue_draw()
        self._apply_input()

    def _clip_inner(self, cr):
        if self._tuck <= 0:
            return
        edge, height = self._frame()[1], self._surface_height()
        cr.rectangle(0, edge if TOP else 0, SURFACE_W, height - edge)
        cr.clip()

    def _target(self, mode):
        if mode == "full":
            return (config.KC_W, self._full_height())
        width, height = SIZES[mode]
        if mode in ("compact", "compact_push"):
            height += self._panel_extra()
        return (width, height)

    def _relayout(self, after=None):
        if self._mode not in ("compact", "compact_push"):
            if after:
                after()
            self._apply_layout()
            return
        self._apply_layout()
        self._anchor = "fixed"
        self._grow.run((self._w, self._h), self._target(self._mode), after)

    def _follow_panel(self):
        self._apply_layout()
        if self._mode not in ("compact", "compact_push") or self._grow.running():
            return
        self._anchor = "fixed"
        self._w, self._h = self._target(self._mode)
        self._area.queue_draw()
        self._apply_input()

    def _begin_shake(self):
        self._shake_phase = 0.0
        self._shake.run((0.0,), (1.0,), self._finish_flood)

    def _clip_spec(self):
        if self._w < 1 or self._h < 1:
            return (0, 0, 0, 0, 0)
        x, y, w, h = self._rect()
        dy = SIGN * (self._content.get_allocated_height() - h) if self._anchor == "slide" else 0
        if self._tuck > 0:
            dy += SIGN * self._tuck
            edge, height = self._frame()[1], self._surface_height()
            if TOP:
                top = max(y, edge)
                y, h = top, y + h - top
            else:
                h = min(y + h, height - edge) - y
            if h < 1:
                return (0, 0, 0, 0, 0)
        return (x, y, w, h, dy)


    def _on_grow_tick(self, values):
        self._w, self._h = values
        self._area.queue_draw()
        self._handle_layer.queue_draw()
        self._apply_input()

    def _on_draw(self, area, cr):
        if not config.CC_OUTLINE:
            return self._paint(area, cr)
        # На кадр — целые размеры: обводка на полупикселе размывается в серый.
        w, h = self._w, self._h
        self._w, self._h = round(w), round(h)
        try:
            return self._paint(area, cr)
        finally:
            self._w, self._h = w, h

    def _paint(self, area, cr):
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        if self._w >= 1 and self._h >= 1:
            width, height = area.get_allocated_width(), area.get_allocated_height()
            cr.set_source_rgba(*config.COLOR)
            if SEP:
                x, y, w, h = self._rect()
                cr.save()
                self._clip_inner(cr)
                plate = lambda c: rounded_rect(c, x, y, w, h, min(config.RADIUS, w / 2, h / 2))
                plate(cr)
                cr.fill()
                if config.CC_OUTLINE:
                    stroke_inside(cr, plate, plate, OUTLINE_LAYERS, config.OUTLINE_THICKNESS)
                    cr.set_source_rgba(*config.COLOR)
                cr.restore()
            else:
                self._fill_corner(cr, width, height)
            if self._mode == "flood" and self._shake_phase is not None:
                self._draw_cross(cr)
        return False

    def _fill_corner(self, cr, width, height):
        near, edge, far = self._frame()
        cr.save()
        if LEFT:
            cr.translate(width, 0)
            cr.scale(-1, 1)
        if TOP:
            cr.translate(0, height)
            cr.scale(1, -1)
        near_band, edge_band = self._bar_bands()
        clip_out_band(cr, width, height, "right", near_band)
        clip_out_band(cr, width, height, "bottom", edge_band)
        corner_path(cr, width, height, self._w, self._h, near, edge, config.RADIUS, top=far)
        cr.fill()
        if config.CC_OUTLINE:
            # Только свободный край: вдоль рамки обводки нет.
            stroke_inside(
                cr, lambda c: corner_path(c, width, height, self._w, self._h, near, edge, config.RADIUS, top=far),
                lambda c: corner_edge_path(c, width, height, self._w, self._h, near, edge, config.RADIUS, top=far),
                OUTLINE_LAYERS, config.OUTLINE_THICKNESS)
            cr.set_source_rgba(*config.COLOR)
        cr.restore()

    def _draw_cross(self, cr):
        phase = self._shake_phase
        dx = math.sin(phase * 2 * math.pi * 5) * 5 * (1 - 0.4 * phase)
        x, y, w, h = self._rect()
        cx = x + w / 2 + dx
        cy = y + h / 2
        half = config.KC_FLOOD_ICON / 2 - 3
        cr.set_source_rgba(1, 1, 1, 1)
        cr.set_line_width(3)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.move_to(cx - half, cy - half)
        cr.line_to(cx + half, cy + half)
        cr.move_to(cx + half, cy - half)
        cr.line_to(cx - half, cy + half)
        cr.stroke()

    def input_region(self):
        if self._w >= 1 and self._h >= 1 and self._tuck < 1:
            x, y, w, h = self._rect()
            near, edge, _ = self._frame()
            near_bar, edge_bar = self._bar_overlap()
            near, edge = max(0, near - near_bar), max(0, edge - edge_bar)
            if not SEP:
                if LEFT:
                    x -= near
                w += near
                if TOP:
                    y -= edge
                h += edge
            return cairo.Region(cairo.RectangleInt(round(x), round(y), round(w), round(h)))
        return _NO_INPUT
