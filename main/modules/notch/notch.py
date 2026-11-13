import getpass
import os
import socket

import cairo
import gi

gi.require_version("GtkLayerShell", "0.1")
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import GtkLayerShell, Gtk, Gdk, GLib, GdkPixbuf, Pango, PangoCairo

from modules.common.surface import ShapedWindow, no_input, init_layer
from modules.common.glyph import GlyphLabel

from modules import config
from modules.common import theme
from modules.parsing import battery
from modules.common import binds
from modules.common import debug
from modules.common import layerkeys
from modules.parsing import power
from modules.common import timefmt
from modules.animations import anim
from modules.animations.anim import Tween
from modules.common.shapes import (notch_edge_path, notch_path, rounded_rect, snap_centered,
                                   stroke_inside)
from modules.common.edge import AttachedEdge
from modules.config.geometry import scaled
from modules.notch import island

SURFACE_W = config.NOTCH_W + 2 * config.RADIUS
EDGE = AttachedEdge(config.NOTCH_SIDE == "top")
SPLIT = config.NOTCH_INSCRIBED and config.BAR_SPLIT
INSCRIBED = config.NOTCH_INSCRIBED and not SPLIT
FRAME = ((config.FRAME_TOP if EDGE.top else config.FRAME_BOTTOM) if SPLIT else EDGE.frame)
ISLAND = config.NOTCH_ISLAND and not INSCRIBED
PILL_PLATE = config.NOTCH_ISLAND
SPLIT_INSET = scaled(10, config.BAR_SCALE)
ISLAND_GAP = config.BAR_OFFSET + SPLIT_INSET - FRAME if SPLIT else island.GAP
SPLIT_IDLE_H = config.BAR_SIZE - 2 * SPLIT_INSET
BODY_TOP = config.BAR_OFFSET if INSCRIBED else FRAME + (ISLAND_GAP if ISLAND else 0)
SURFACE_H = max(FRAME, BODY_TOP + config.NOTCH_H)

MENU_MODES = ("battery", "power", "player")
NAV_MODES = ("battery", "power")
EXPANDED = (config.NOTCH_W, config.NOTCH_H)
SIZES = {
    "battery": EXPANDED,
    "power": EXPANDED,
    "player": EXPANDED,
}

CENTER = Gtk.Align.CENTER
START = Gtk.Align.START
SP = config.NOTCH_SPACING

_NO_INPUT = no_input(0, 0 if EDGE.top else SURFACE_H - 1)

ICON_PAUSE, ICON_PLAY = "\uf04c", "\uf04b"


def idle_text(setting):
    if setting is None or setting.strip().lower() == "userhost":
        return f"{getpass.getuser()}@{socket.gethostname().split('.')[0]}"
    return setting


def _label(text="", name=None):
    lbl = Gtk.Label(label=text)
    if name:
        lbl.set_name(name)
    return lbl


def _action_button(icon, text, on_click, invert=False):
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    box.set_valign(CENTER)
    box.set_halign(CENTER)
    glyph = GlyphLabel(label=icon)
    glyph.get_style_context().add_class("notch-btn-icon")
    box.pack_start(glyph, False, False, 0)
    if text:
        box.pack_start(_label(text), False, False, 0)

    btn = Gtk.Button()
    btn.set_relief(Gtk.ReliefStyle.NONE)
    btn.set_can_focus(False)
    ctx = btn.get_style_context()
    ctx.add_class("notch-btn")
    if invert:
        ctx.add_class("invert")
    btn.add(box)
    btn.connect("clicked", lambda *_: on_click())
    return btn


def _keep_hidden(widget):
    widget.set_no_show_all(True)
    widget.hide()


def _square(pixbuf, size):
    w, h = pixbuf.get_width(), pixbuf.get_height()
    k = size / min(w, h)
    nw, nh = max(size, round(w * k)), max(size, round(h * k))
    scaled = pixbuf.scale_simple(nw, nh, GdkPixbuf.InterpType.HYPER)
    return scaled.new_subpixbuf((nw - size) // 2, (nh - size) // 2, size, size)


class CoverArt(Gtk.DrawingArea):
    def __init__(self, size, radius):
        super().__init__()
        self._size = size
        self._radius = radius
        self._pixbuf = None
        self.set_size_request(size, size)
        self.set_valign(START)
        self.connect("draw", self._on_draw)

    def set_pixbuf(self, pixbuf):
        self._pixbuf = _square(pixbuf, self._size) if pixbuf else None
        self.queue_draw()

    def _on_draw(self, _widget, cr):
        rounded_rect(cr, 0, 0, self._size, self._size, theme.radius("#notch-cover"))
        if self._pixbuf:
            cr.clip()
            Gdk.cairo_set_source_pixbuf(cr, self._pixbuf, 0, 0)
            cr.paint()
        else:
            cr.set_source_rgba(*theme.bg("#notch-cover"))
            cr.fill()
        return False


class TimelineBar(Gtk.DrawingArea):
    def __init__(self, width, height, on_seek):
        super().__init__()
        self._on_seek = on_seek
        self._fraction = 0.0
        self._dragging = False
        self.set_size_request(width, height)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK
                        | Gdk.EventMask.POINTER_MOTION_MASK)
        self.connect("draw", self._on_draw)
        self.connect("button-press-event", self._on_press)
        self.connect("motion-notify-event", self._on_motion)
        self.connect("button-release-event", self._on_release)

    def set_fraction(self, fraction):
        if not self._dragging:
            self._fraction = max(0.0, min(1.0, fraction))
            self.queue_draw()

    def _fraction_at(self, x):
        return max(0.0, min(1.0, x / max(1, self.get_allocated_width())))

    def _on_press(self, _widget, event):
        if event.button == 1:
            self._dragging = True
            self._fraction = self._fraction_at(event.x)
            self.queue_draw()
        return True

    def _on_motion(self, _widget, event):
        if self._dragging:
            self._fraction = self._fraction_at(event.x)
            self.queue_draw()
        return True

    def _on_release(self, _widget, event):
        if event.button == 1 and self._dragging:
            self._dragging = False
            self._fraction = self._fraction_at(event.x)
            self._on_seek(self._fraction)
            self.queue_draw()
        return True

    def _on_draw(self, widget, cr):
        w, h = widget.get_allocated_width(), widget.get_allocated_height()
        cr.set_source_rgba(*theme.bg("#notch-timeline"))
        rounded_rect(cr, 0, 0, w, h, h / 2)
        cr.fill()
        filled = w * self._fraction
        if filled >= 1:
            cr.set_source_rgba(*theme.fg("#notch-timeline"))
            rounded_rect(cr, 0, 0, max(filled, h), h, h / 2)
            cr.fill()
        return False


def _expanded_page(orientation, spacing):
    page = Gtk.Box(orientation=orientation, spacing=spacing)
    page.set_border_width(config.BUTTONS_EDGE)
    page.set_size_request(*EXPANDED)
    return page


class BatteryPage:
    """The battery and power profiles menu: charge, source and the profile buttons.

    Shown in the notch, or above the Undercover taskbar (notch.expand.power-profiles.undercover).
    """

    def __init__(self):
        page = _expanded_page(Gtk.Orientation.VERTICAL, SP)
        header = Gtk.Box()
        self._percent = _label("", "notch-percent")
        self._icon = GlyphLabel(label="", name="notch-bat-icon")
        self._source = _label("", "notch-source")
        header.pack_start(self._percent, False, False, 4)
        header.pack_end(self._icon, False, False, 4)
        header.pack_end(self._source, False, False, 8)
        for widget, shown in ((self._percent, config.NOTCH_SHOW_PERCENTAGE),
                              (self._icon, config.NOTCH_SHOW_STATUS_ICON),
                              (self._source, config.NOTCH_SHOW_TEXT_STATUS)):
            if not shown:
                _keep_hidden(widget)
        page.pack_start(header, False, False, 0)

        icons = {"power-saver": config.ICON_ECO, "balanced": config.ICON_BALANCE, "performance": config.ICON_PERF}
        self.buttons = {}
        self.active = None
        if config.NOTCH_PROFILES:
            row = Gtk.Box(spacing=SP)
            row.set_homogeneous(True)
            for profile in config.NOTCH_PROFILES:
                btn = _action_button(icons[profile], None, lambda p=profile: self.set_profile(p))
                btn.get_style_context().add_class("profile")
                self.buttons[profile] = btn
                row.pack_start(btn, True, True, 0)
            page.pack_start(row, True, True, 0)
        self.widget = page

    def refresh(self):
        self.refresh_info()
        power.get_profile(self.mark)

    def refresh_info(self):
        data = battery.read()
        if data:
            self._percent.set_label(f"{data[0]}%")
            self._icon.set_label(battery.icon(*data, bool(battery.on_ac())))
        else:
            self._percent.set_label("—")
            self._icon.set_label("")
        ac = battery.on_ac()
        self._source.set_label("" if ac is None else ("On socket" if ac else "On battery"))

    def mark(self, active):
        self.active = active
        for profile, btn in self.buttons.items():
            ctx = btn.get_style_context()
            (ctx.add_class if profile == active else ctx.remove_class)("active")

    def set_profile(self, profile):
        power.set_profile(profile)
        self.mark(profile)

    def start_index(self):
        """Where arrow keys start: the active profile, else the middle one."""
        names = list(self.buttons)
        return names.index(self.active) if self.active in names else min(1, len(names) - 1)


class Notch(ShapedWindow):
    def __init__(self, wm, media, canvas):
        super().__init__(name="notch", visible=False, all_visible=False)
        self._canvas = canvas
        self._suppressed = False

        visual = self.get_screen().get_rgba_visual()
        if visual:
            self.set_visual(visual)
        self.set_app_paintable(True)

        init_layer(self)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.TOP)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.TOP if EDGE.top else GtkLayerShell.Edge.BOTTOM, True)
        GtkLayerShell.set_exclusive_zone(self, -1)
        self.set_size_request(SURFACE_W, SURFACE_H)

        self._media = media
        self._width_listeners = []
        self._w = self._h = 0.0
        self._mode = None
        self._expanded = None
        self._has_windows = False
        self._battery_tick_source = 0
        # Set by Desk when the power profiles menu lives above the Undercover taskbar.
        self.battery_redirect = None
        self._fallback_cover = self._load_fallback_cover()
        self._idle_text = idle_text(config.IDLE_TEXT)
        self._idle_alpha = 0.0
        self._idle_h = 0
        self._position = 0
        self._position_source = 0
        self._track = None
        self._menus = tuple(name for name in config.NOTCH_MENUS
                            if name != "power" or config.NOTCH_POWER_OPTIONS)

        self._area = Gtk.DrawingArea()
        self._area.set_name("notch-area")
        self._area.connect("draw", self._on_draw)

        self._stack = Gtk.Stack()
        self._stack.set_hhomogeneous(False)
        self._stack.set_vhomogeneous(False)
        self._stack.add_named(Gtk.Box(), "none")
        self._stack.add_named(self._build_battery(), "battery")
        self._stack.add_named(self._build_power(), "power")
        self._stack.add_named(self._build_player(), "player")

        self._content = Gtk.Box()
        self._content.set_halign(CENTER)
        self._content.set_valign(START if EDGE.top else Gtk.Align.END)
        (self._content.set_margin_top if EDGE.top else self._content.set_margin_bottom)(BODY_TOP)
        self._content.add(self._stack)

        overlay = Gtk.Overlay()
        overlay.add(self._area)
        overlay.add_overlay(self._content)
        self.add(overlay)

        self._selected = None
        self._nav_mode = None
        self._relax_source = 0
        for btn in self._nav_all():
            btn.add_events(Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK)
            btn.connect("motion-notify-event", lambda _w, _e, b=btn: self._on_nav_motion(b))
            btn.connect("leave-notify-event", lambda _w, _e, b=btn: self._on_nav_leave(b))

        self._grow = Tween(anim.ms(), self._on_grow_tick)
        self._tuck = 0.0
        self._slide = Tween(anim.ms(), self._on_slide_tick)
        self._idle_fade = Tween(anim.ms(140), self._on_idle_tick)
        self._content_fade = Tween(anim.ms(140), lambda v: self._content.set_opacity(v[0]), self)

        self.connect("key-press-event", self._on_key)

        self.show_all()
        self._content.set_opacity(0)

        wm.subscribe(self._on_wm_state)
        media.subscribe(self._on_media)
        self._update()


    def subscribe_width(self, callback):
        self._width_listeners.append(callback)
        callback(self._w if self._visible() else 0)

    def _visible(self):
        return self._w >= 1 and (INSCRIBED or self._h >= 1)

    def _idle_size(self):
        margin = 2 * (config.IDLE_SPACING + config.IDLE_PADDING)
        text_w, text_h = self._area.create_pango_layout(self._idle_text).get_pixel_size()
        w = text_w + margin
        w = min(w + w % 2, config.NOTCH_W)
        h = 0 if INSCRIBED else (SPLIT_IDLE_H if SPLIT and ISLAND else text_h + margin)
        self._idle_h = h
        if os.environ.get("LEECH_DEBUG"):
            print(f"[notch] idle {w}x{h} (текст {text_w}x{text_h})")
        return (w, h)

    def _expanded_page(self, orientation, spacing):
        return _expanded_page(orientation, spacing)

    def _build_battery(self):
        self._battery = BatteryPage()
        self._profile_buttons = self._battery.buttons
        return self._battery.widget

    def _build_power(self):
        page = self._expanded_page(Gtk.Orientation.HORIZONTAL, SP)
        page.set_homogeneous(True)
        options = {"reboot": (config.ICON_REBOOT, power.reboot), "sleep": (config.ICON_SLEEP, power.suspend),
                   "shutdown": (config.ICON_POWEROFF, power.poweroff)}
        self._power_buttons = [
            _action_button(options[name][0], None, lambda action=options[name][1]: self._do(action), invert=True)
            for name in config.NOTCH_POWER_OPTIONS
        ]
        for btn in self._power_buttons:
            page.pack_start(btn, True, True, 0)
        return page

    def _build_player(self):
        pad, gap = config.PLAYER_SPACING, config.PLAYER_GAP
        timeline_h, bottom = config.PLAYER_TIMELINE_H, config.PLAYER_TIMELINE_BOTTOM
        cover = config.NOTCH_H - pad - gap - timeline_h - bottom
        button, time_w = 44, 72
        button_x = config.NOTCH_W - pad - button
        time_x = button_x - 8 - time_w
        show = config.PLAYER_SHOW
        title_x = pad + cover + 10 if show["cover"] else pad + 4
        title_y = pad + 4

        page = Gtk.Fixed()
        page.set_size_request(*EXPANDED)

        self._cover = CoverArt(cover, None)
        page.put(self._cover, pad, pad)

        self._title = _label("", "notch-title")
        self._title.set_xalign(0)
        self._title.set_ellipsize(Pango.EllipsizeMode.END)
        self._title.set_size_request(time_x - 6 - title_x, -1)
        page.put(self._title, title_x, title_y)

        self._artist = _label("", "notch-artist")
        self._artist.set_xalign(0)
        self._artist.set_ellipsize(Pango.EllipsizeMode.END)
        self._artist.set_size_request(button_x - 8 - title_x, -1)
        page.put(self._artist, title_x, title_y + 21)

        self._time = _label("", "notch-time")
        self._time.set_xalign(1.0)
        self._time.set_size_request(time_w, -1)
        page.put(self._time, time_x, title_y)

        self._play_icon = GlyphLabel(label=ICON_PLAY)
        play = Gtk.Button()
        play.set_relief(Gtk.ReliefStyle.NONE)
        play.set_can_focus(False)
        play.get_style_context().add_class("notch-play")
        play.set_size_request(button, button)
        play.add(self._play_icon)
        play.connect("clicked", lambda *_: self._media.play_pause())
        page.put(play, button_x, pad + (cover - button) // 2)

        self._timeline = TimelineBar(config.NOTCH_W - 2 * pad, timeline_h, self._media.seek)
        page.put(self._timeline, pad, config.NOTCH_H - bottom - timeline_h)

        for widget, name in ((self._cover, "cover"), (play, "playbutton"), (self._time, "time"),
                             (self._timeline, "timeline"), (self._title, "title"), (self._artist, "artist")):
            if not show[name]:
                _keep_hidden(widget)
        return page

    @staticmethod
    def _load_fallback_cover():
        try:
            return GdkPixbuf.Pixbuf.new_from_file(str(config.COVER_FALLBACK))
        except GLib.Error:
            return None


    def toggle(self, name):
        if name == "battery" and self.battery_redirect is not None:
            self.battery_redirect()
            return None
        if name not in self._menus:
            return f"меню {name} отключено в конфиге"
        self._expanded = None if self._expanded == name else name
        if self._expanded == "battery":
            self._refresh_battery()
            if not self._battery_tick_source:
                self._battery_tick_source = GLib.timeout_add_seconds(2, self._battery_tick)
        elif self._expanded == "player":
            self._media.refresh()
            self._start_position_poll()
        self._update()
        return None

    def close(self):
        self._expanded = None
        self._update()

    def suppress(self, on):
        self._suppressed = on
        if on:
            self._expanded = None
        self._update()

    def handle(self, command):
        parts = command.split()
        if parts[:1] == ["toggle"] and len(parts) == 2 and parts[1] in ("battery", "power", "player"):
            return self.toggle(parts[1])
        elif parts[:1] == ["close"]:
            self.close()


    def _nav_all(self):
        return list(self._profile_buttons.values()) + self._power_buttons

    def _nav_buttons(self, mode):
        if mode == "battery":
            return list(self._profile_buttons.values())
        if mode == "power":
            return self._power_buttons
        return []

    def _set_selected(self, button):
        for btn in self._nav_all():
            ctx = btn.get_style_context()
            (ctx.add_class if btn is button else ctx.remove_class)("sel")
        self._selected = button

    def _on_nav_motion(self, button):
        self._nav_mode = "mouse"
        if self._selected is not button:
            self._set_selected(button)
        return False

    def _on_nav_leave(self, button):
        if self._nav_mode == "mouse" and self._selected is button:
            self._set_selected(None)
        return False

    def _on_key(self, _widget, event):
        if self._expanded is None:
            return False
        key = binds.nav_key(event)
        if key == Gdk.KEY_Escape:
            self.close()
            return True
        buttons = self._nav_buttons(self._expanded)
        if not buttons:
            return False
        if key in (Gdk.KEY_Left, Gdk.KEY_Up, Gdk.KEY_Right, Gdk.KEY_Down):
            self._nav_mode = "keyboard"
            step = 1 if key in (Gdk.KEY_Right, Gdk.KEY_Down) else -1
            if self._selected in buttons:
                index = max(0, min(len(buttons) - 1, buttons.index(self._selected) + step))
            else:
                index = self._start_index(self._expanded)
            self._set_selected(buttons[index])
            return True
        if key in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_space) and self._selected in buttons:
            self._selected.clicked()
            return True
        return False

    def _start_index(self, mode):
        if mode == "battery":
            return self._battery.start_index()
        return 0

    def _set_keyboard(self, level):
        layerkeys.set_keyboard(self, level)

    def _grab_keyboard(self):
        self._set_keyboard("exclusive")
        if self._relax_source:
            GLib.source_remove(self._relax_source)
        self._relax_source = GLib.timeout_add(180, self._relax_keyboard)

    def _relax_keyboard(self):
        self._relax_source = 0
        if self._mode in MENU_MODES:
            self._set_keyboard("on_demand")
        return False

    def _do(self, action):
        debug.log("notch", f"действие {getattr(action, '__name__', action)}")
        self.close()
        action()

    def _on_wm_state(self, state):
        self._has_windows = config.NOTCH_HIDE_BY_WINDOW and state.windows > 0
        self._update()

    def _update(self):
        if self._expanded:
            self._canvas.catch("notch", self.close)
        else:
            self._canvas.release("notch")
        self._go("hidden" if self._suppressed else (self._expanded or ("hidden" if self._has_windows else "idle")))

    def _go(self, mode):
        if mode == self._mode:
            return
        tuck_idle = ISLAND and mode == "hidden" and self._mode == "idle"
        self._mode = mode
        self._set_selected(None)
        self._nav_mode = None
        self._idle_fade.stop()
        self._content_fade.stop()
        if not tuck_idle:
            self._idle_alpha = 0.0
        self._content.set_opacity(0)
        if mode in MENU_MODES:
            self._grab_keyboard()
            self._stack.set_visible_child_name(mode)
        else:
            if self._relax_source:
                GLib.source_remove(self._relax_source)
                self._relax_source = 0
            self._set_keyboard("none")
            self._stack.set_visible_child_name("none")

        if mode == "hidden":
            target = (0, 0) if INSCRIBED else (round(self._w), 0)
        else:
            target = self._idle_size() if mode == "idle" else SIZES[mode]
            if self._h < 1 and not INSCRIBED:
                self._w = target[0]

        def revealed():
            if self._mode != mode:
                return
            if mode in MENU_MODES:
                self._content_fade.run((0.0,), (1.0,))
            elif mode == "idle":
                self._idle_fade.run((0.0,), (1.0,))

        if ISLAND:
            self._go_island(mode, target, revealed)
            return
        if (round(self._w), round(self._h)) == target:
            revealed()
        else:
            self._grow.run((self._w, self._h), target, revealed)

    def _go_island(self, mode, target, revealed):
        if mode == "hidden":
            self._grow.stop()
            if self._h < 1:
                self._tuck = 0.0
                return
            self._slide.run((self._tuck,), (self._h + ISLAND_GAP,), lambda: self._tucked(mode))
            return
        if self._h < 1:
            self._tuck = target[1] + ISLAND_GAP
            self._on_grow_tick(target)
        resize = (round(self._w), round(self._h)) != target
        if self._tuck > 0:
            self._slide.run((self._tuck,), (0.0,), None if resize else revealed)
        if resize:
            self._grow.run((self._w, self._h), target, revealed)
        elif self._tuck <= 0:
            revealed()

    def _tucked(self, mode):
        if self._mode != mode:
            return
        self._tuck = 0.0
        self._idle_alpha = 0.0
        self._on_grow_tick((self._w, 0.0))

    def _on_slide_tick(self, values):
        self._tuck = values[0]
        self._area.queue_draw()
        self._apply_input()

    def _on_idle_tick(self, values):
        self._idle_alpha = values[0]
        self._area.queue_draw()


    def _refresh_battery(self):
        self._battery.refresh()

    def _refresh_battery_info(self):
        self._battery.refresh_info()

    def _battery_tick(self):
        if self._expanded != "battery":
            self._battery_tick_source = 0
            return False
        self._refresh_battery_info()
        return True

    def _on_media(self, track, pixbuf):
        self._track = track
        self._title.set_label(track.title)
        self._artist.set_label(track.artist)
        self._artist.set_visible(config.PLAYER_SHOW["artist"] and bool(track.artist))
        self._cover.set_pixbuf(pixbuf or self._fallback_cover)
        self._play_icon.set_label(ICON_PAUSE if track.playing else ICON_PLAY)
        self._timeline.set_visible(config.PLAYER_SHOW["timeline"] and track.available)
        self._time.set_visible(config.PLAYER_SHOW["time"] and track.available)
        self._show_progress()

    def _show_progress(self):
        track = self._track
        if track is None or not track.available:
            return
        if track.length > 0:
            self._time.set_label(timefmt.progress(self._position, track.length))
            self._timeline.set_fraction(self._position / track.length)
        else:
            self._time.set_label(timefmt.clock(self._position))
            self._timeline.set_fraction(0.0)

    def _start_position_poll(self):
        self._media.request_position(self._on_position)
        if not self._position_source:
            self._position_source = GLib.timeout_add(500, self._poll_position)

    def _poll_position(self):
        if self._expanded != "player":
            self._position_source = 0
            return False
        if self._track is not None and self._track.playing:
            self._media.request_position(self._on_position)
        return True

    def _on_position(self, position):
        if position is not None:
            self._position = position
            self._show_progress()


    def _on_grow_tick(self, values):
        self._w, self._h = values
        width = self._w if self._visible() else 0
        for callback in self._width_listeners:
            callback(width)
        self._area.queue_draw()
        self._apply_input()

    def _idle_box(self):
        if INSCRIBED:
            return config.BAR_OFFSET, config.BAR_SIZE
        return BODY_TOP, self._h

    def _on_draw(self, area, cr):
        if not config.NOTCH_OUTLINE:
            return self._paint(area, cr)
        # На кадр — целые края: обводка на полупикселе размывается в серый.
        w, h = self._w, self._h
        x0, x1 = snap_centered(area.get_allocated_width(), w)
        self._w, self._h = x1 - x0, round(h)
        try:
            return self._paint(area, cr)
        finally:
            self._w, self._h = w, h

    def _paint(self, area, cr):
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        if self._visible():
            x0 = (area.get_allocated_width() - self._w) / 2
            if ISLAND:
                cr.save()
                EDGE.clip_inside(cr, area.get_allocated_width(), area.get_allocated_height(), FRAME)
                cr.translate(0, EDGE.toward(self._tuck))
            cr.set_source_rgba(*config.COLOR)
            cr.save()
            EDGE.to_edge(cr, area.get_allocated_height())
            if INSCRIBED:
                self._fill_inscribed(cr, area, x0)
            elif ISLAND:
                rounded_rect(cr, x0, BODY_TOP, self._w, self._h, self._island_radius())
                cr.fill()
            else:
                notch_path(cr, x0, x0 + self._w, FRAME, self._h, config.RADIUS)
                cr.fill()
            cr.restore()
            if self._idle_alpha > 0:
                top, height = self._idle_box()
                top = EDGE.body_y(area.get_allocated_height(), height, top)
                cr.save()
                cr.rectangle(x0, top, self._w, height)
                cr.clip()
                self._draw_idle(cr, x0, top, height)
                cr.restore()
            if config.NOTCH_OUTLINE:
                cr.save()
                EDGE.to_edge(cr, area.get_allocated_height())
                self._draw_outline(cr, area, x0)
                cr.restore()
            if ISLAND:
                cr.restore()
        return False

    def _island_radius(self):
        if SPLIT:
            return min(config.RADIUS, self._w / 2, self._h / 2)
        return island.radius(self._h, self._idle_h, config.NOTCH_H, config.RADIUS)

    def _draw_outline(self, cr, area, x0):
        x1 = x0 + self._w
        if ISLAND:
            radius = self._island_radius()
            path = lambda c: rounded_rect(c, x0, BODY_TOP, self._w, self._h, radius)
            stroke_inside(cr, path, path, theme.outline_layers(), config.OUTLINE_THICKNESS)
            return
        # Вырез в рамке и челка в баре: обводка только по свободному краю, там, где челка
        # сливается с рамкой или баром, её нет.
        below = self._h + config.BAR_OFFSET - FRAME if INSCRIBED else self._h
        if below < 1:
            return

        def shape(c):
            notch_path(c, x0, x1, FRAME, below, config.RADIUS)
            if INSCRIBED:
                c.clip()
                c.rectangle(0, FRAME, area.get_allocated_width(), area.get_allocated_height())

        stroke_inside(cr, shape, lambda c: notch_edge_path(c, x0, x1, FRAME, below, config.RADIUS),
                      theme.outline_layers(), config.OUTLINE_THICKNESS)

    def _fill_inscribed(self, cr, area, x0):
        cr.rectangle(x0, config.BAR_OFFSET, self._w, FRAME - config.BAR_OFFSET)
        cr.fill()
        below = self._h + config.BAR_OFFSET - FRAME
        if below < 1:
            return
        cr.save()
        cr.rectangle(x0, config.BAR_OFFSET, self._w, FRAME - config.BAR_OFFSET)
        cr.rectangle(0, FRAME, area.get_allocated_width(), area.get_allocated_height())
        cr.clip()
        notch_path(cr, x0, x0 + self._w, FRAME, below, config.RADIUS)
        cr.fill()
        cr.restore()

    def _draw_idle(self, cr, x0, top, height):
        gap = config.IDLE_SPACING
        w, h = self._w - 2 * gap, height - 2 * gap
        if w < 2 or h < 2:
            return
        r, g, b, a = theme.bg("#notch-idle-plate")
        cr.set_source_rgba(r, g, b, a * self._idle_alpha)
        plate_radius = theme.radius("#notch-idle-plate")
        rounded_rect(cr, x0 + gap, top + gap, w, h, h / 2 if PILL_PLATE else min(plate_radius, w / 2, h / 2))
        cr.fill()
        layout = self._area.create_pango_layout(self._idle_text)
        text_w, text_h = layout.get_pixel_size()
        r, g, b, a = theme.fg("#notch-idle-plate")
        cr.set_source_rgba(r, g, b, a * self._idle_alpha)
        cr.move_to(x0 + (self._w - text_w) / 2, top + (height - text_h) / 2)
        PangoCairo.show_layout(cr, layout)

    def input_region(self):
        if self._visible():
            x0 = round((SURFACE_W - self._w) / 2)
            body = round(max(FRAME, BODY_TOP + self._h))
            if ISLAND:
                if self._tuck >= 1:
                    return _NO_INPUT
                height = round(self._h)
                y = BODY_TOP if EDGE.top else SURFACE_H - BODY_TOP - height
                return cairo.Region(cairo.RectangleInt(x0, y, round(self._w), height))
            return cairo.Region(cairo.RectangleInt(x0, 0 if EDGE.top else SURFACE_H - body, round(self._w), body))
        return _NO_INPUT
