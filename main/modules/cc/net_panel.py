import math
from dataclasses import dataclass, field

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gtk, Gdk, GLib, Pango, PangoCairo

from modules import config
from modules.animations import anim
from modules.animations.anim import Tween
from modules.cc import net_layout as nl
from modules.common import binds, glyph, theme
from modules.common.shapes import rounded_rect
from modules.parsing import bluetooth, network, wifi

ICON_WIFI = ""
ICON_ETHERNET = ""
ICON_BLUETOOTH = ""
ICON_LOCK = ""
ICON_RESCAN = ""
ICON_SEARCH = ""
ICON_VISIBLE = ""
ICON_HIDDEN = ""
ICON_SEND = ""
ICON_CONNECT = ""
ICON_DISCONNECT = ""
ICON_TRUST = ""
ICON_REMOVE = ""
BT_ICONS = {
    "audio-headset": "", "audio-headphones": "", "audio-card": "",
    "input-keyboard": "", "input-mouse": "", "input-gaming": "",
    "phone": "", "computer": "", "video-display": "",
}

TITLES = {"wifi": "Wi-Fi", "bluetooth": "Bluetooth"}
WIFI_POLL_S = 4
FAIL_MS = 2500
SPIN_TURN_S = 0.9
# Optical correction for glyphs whose ink box centre differs from their visual centre.
GLYPH_NUDGE = {ICON_SEND: (-1, 1)}
NO_TEXT_MODS = (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.MOD1_MASK | Gdk.ModifierType.SUPER_MASK
                | Gdk.ModifierType.META_MASK)


def _item(on, hover):
    """The style.css rule of a row or header button: on = connected / switched on."""
    return "#cc-net-item" + (".on" if on else "") + (".hover" if hover else "")


@dataclass
class Row:
    key: object
    glyph: str
    title: str
    detail: str = ""
    lock: bool = False
    active: bool = False
    menu: list = field(default_factory=list)
    action: object = None
    source: object = None


class NetPanel(Gtk.DrawingArea):
    def __init__(self, width, top, on_resize, on_open):
        super().__init__()
        self.set_name("cc-net-panel")
        self._width = width
        self._top = top
        self._on_resize = on_resize
        self._on_open = on_open
        self.kind = None
        self._h = 0.0
        self._tween = Tween(anim.ms(), self._on_tick)
        self._rows = []
        self._message = ""
        self._header = []
        self._selected = None
        self._menu_row = None
        self._menu_sel = None
        self._head_hover = None
        self._head_sel = None
        self._scroll = 0.0
        self._pointer = None
        self._nav = "mouse"
        self._password = None
        self._busy = {}
        self._failed = {}
        self._adapter = None
        self._adapter_props = {}
        self._poll_source = 0
        self._bt_refresh = 0
        self._bt_unwatch = None
        self._generation = 0
        self._scanning = False
        self._spin = 0.0
        self._spin_tick = 0
        self._spin_last = None
        self.set_size_request(width, 0)
        self.set_no_show_all(True)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.POINTER_MOTION_MASK
                        | Gdk.EventMask.LEAVE_NOTIFY_MASK | Gdk.EventMask.SCROLL_MASK
                        | Gdk.EventMask.SMOOTH_SCROLL_MASK)
        self.connect("draw", self._on_draw)
        self.connect("button-press-event", self._on_press)
        self.connect("motion-notify-event", self._on_motion)
        self.connect("leave-notify-event", self._on_leave)
        self.connect("scroll-event", self._on_scroll)


    @property
    def is_open(self):
        return self.kind is not None

    def height(self):
        return round(self._h)

    def toggle(self, kind):
        if self.kind == kind:
            self.close()
        else:
            self.open(kind)

    def open(self, kind):
        switching = self.kind is not None
        self._stop_sources()
        self.kind = kind
        self._generation += 1
        self._rows, self._header, self._message = [], [], ""
        self._selected = self._menu_row = self._menu_sel = self._password = self._head_sel = None
        self._scroll = 0.0
        self._busy, self._failed = {}, {}
        self._nav = "mouse"
        if kind == "wifi":
            self._read_wifi()
            self._rescan()
            self._poll_source = GLib.timeout_add_seconds(WIFI_POLL_S, self._poll_wifi)
        else:
            self._bt_unwatch = bluetooth.watch(self._schedule_bt)
            self._read_bt()
        self.show()
        if not switching:
            self._on_open(True)
        self._retarget()

    def close(self, instant=False):
        if self.kind is None and self._h <= 0:
            return
        was_open = self.kind is not None
        self._leave_kind()
        self.kind = None
        self._password = None
        if was_open:
            self._on_open(False)
        if instant:
            self._tween.stop()
            self._on_tick((0.0,))
        else:
            self._tween.run((self._h,), (0.0,))

    def refresh(self):
        if self.kind == "wifi":
            self._read_wifi()
        elif self.kind == "bluetooth":
            self._read_bt()

    def _leave_kind(self):
        if self.kind == "bluetooth" and self._adapter is not None and self._adapter_prop("Discovering"):
            bluetooth.set_discovering(self._adapter, False, lambda *_: None)
        self._stop_sources()
        self._generation += 1

    def _stop_sources(self):
        self._scanning = False
        if self._poll_source:
            GLib.source_remove(self._poll_source)
            self._poll_source = 0
        if self._bt_refresh:
            GLib.source_remove(self._bt_refresh)
            self._bt_refresh = 0
        if self._bt_unwatch is not None:
            self._bt_unwatch()
            self._bt_unwatch = None

    def _target(self):
        if self.kind is None:
            return 0.0
        return float(nl.PAD + nl.plate_height(len(self._rows), bool(self._header), self._view_h()))

    def _retarget(self):
        target = self._target()
        if round(self._h) != round(target) or self._tween.running():
            self._tween.run((self._h,), (target,))

    def _on_tick(self, values):
        self._h = max(0.0, values[0])
        self.set_size_request(self._width, round(self._h))
        if self._h <= 0 and self.kind is None:
            self.hide()
        self.queue_draw()
        self._on_resize()


    def _read_wifi(self):
        generation = self._generation

        def done(result):
            if generation == self._generation:
                self._set_wifi(*result)
        wifi.in_thread(lambda: (network.wifi_enabled(), *wifi.read()), done)

    def _poll_wifi(self):
        if self.kind != "wifi":
            self._poll_source = 0
            return False
        if self._password is None and self._menu_row is None:
            self._read_wifi()
        return True

    def _set_wifi(self, enabled, wired, networks):
        if wired is not None:
            self._header = []
            rows = [Row(("eth", wired.device), ICON_ETHERNET, wired.name, wired.device, active=True)]
            self._message = ""
        else:
            self._header = [(ICON_RESCAN, False, self._rescan)] if enabled else []
            rows = [self._wifi_row(n) for n in networks] if enabled else []
            self._message = "No networks found" if enabled else "Wi-Fi is off"
        self._set_rows(rows)

    def _wifi_row(self, n):
        menu = [(ICON_DISCONNECT, "Disconnect", self._wifi_disconnect) if n.active
                else (ICON_CONNECT, "Connect", self._wifi_connect)]
        if n.known:
            menu.append((ICON_REMOVE, "Forget", self._wifi_forget))
        detail = "Saved" if n.known and not n.active else ""
        return Row(("wifi", n.ssid), ICON_WIFI, n.ssid, detail or f"{n.signal}%", lock=n.secure, active=n.active,
                   menu=menu, action=self._wifi_disconnect if n.active else self._wifi_connect, source=n)

    def _rescan(self):
        if self._scanning:
            return
        generation = self._generation
        self._scanning = True
        self._start_spin()

        def done(_result):
            if generation == self._generation:
                self._scanning = False
                if self.kind == "wifi":
                    self._read_wifi()
        wifi.in_thread(wifi.rescan, done)

    def _start_spin(self):
        if not self._spin_tick:
            self._spin_last = None
            self._spin_tick = self.add_tick_callback(self._on_spin)

    def _on_spin(self, _widget, clock):
        now = clock.get_frame_time() / 1e6
        step = 0.0 if self._spin_last is None else max(0.0, now - self._spin_last)
        self._spin_last = now
        spin = self._spin + step / SPIN_TURN_S
        if not self._scanning and spin >= 1.0:
            # Scan finished: complete the current turn so the glyph comes to rest upright.
            self._spin_tick = 0
            self._spin = 0.0
            self.queue_draw()
            return GLib.SOURCE_REMOVE
        self._spin = spin % 1.0 if self._scanning else spin
        self.queue_draw()
        return GLib.SOURCE_CONTINUE

    def _wifi_connect(self, row):
        n = row.source
        if n.secure and not n.known:
            self._password = [row.key, ""]
            self.queue_draw()
            return
        self._run_wifi(row, lambda: wifi.connect(n), "Connecting…",
                       on_fail=lambda message: n.known is not None and wifi.needs_password(n, message))

    def _ask_password(self, key):
        if self._row_by_key(key) is None or self.kind != "wifi":
            return False
        self._password = [key, ""]
        self.queue_draw()
        return True

    def _submit_password(self):
        key, text = self._password
        self._password = None
        row = self._row_by_key(key)
        if row is not None and text:
            self._run_wifi(row, lambda: wifi.connect(row.source, text), "Connecting…")
        self.queue_draw()

    def _wifi_disconnect(self, row):
        self._run_wifi(row, lambda: wifi.disconnect(row.source), "Disconnecting…")

    def _wifi_forget(self, row):
        self._run_wifi(row, lambda: wifi.forget(row.source), "Forgetting…")

    def _run_wifi(self, row, work, label, on_fail=None):
        key, generation = row.key, self._generation
        self._busy[key] = label
        self.queue_draw()

        def done(result):
            self._busy.pop(key, None)
            if generation != self._generation:
                return
            ok, message = result
            if not ok and not (on_fail and on_fail(message) and self._ask_password(key)):
                self._fail(key, message)
            self._read_wifi()
        wifi.in_thread(work, done)


    def _schedule_bt(self):
        if not self._bt_refresh and self.kind == "bluetooth":
            self._bt_refresh = GLib.timeout_add(200, self._bt_refresh_now)

    def _bt_refresh_now(self):
        self._bt_refresh = 0
        if self.kind == "bluetooth" and self._menu_row is None:
            self._read_bt()
        return False

    def _read_bt(self):
        adapter, devices = bluetooth.read()
        self._adapter = adapter[0] if adapter else None
        self._adapter_props = adapter[1] if adapter else {}
        powered = bool(self._adapter_props.get("Powered"))
        if not powered:
            self._header, self._message = [], "Bluetooth is off" if adapter else "No Bluetooth adapter"
            self._set_rows([])
            return
        discovering = bool(self._adapter_props.get("Discovering"))
        visible = bool(self._adapter_props.get("Discoverable"))
        self._header = [(ICON_SEARCH, discovering, self._toggle_discovery),
                        (ICON_VISIBLE if visible else ICON_HIDDEN, visible, self._toggle_visible),
                        (ICON_SEND, False, self._send_file)]
        self._message = "Searching…" if discovering else "No devices"
        self._set_rows([self._bt_row(d) for d in devices])

    def _adapter_prop(self, name):
        return bool(self._adapter_props.get(name))

    def _bt_row(self, d):
        menu = [(ICON_DISCONNECT, "Disconnect", self._bt_disconnect) if d.connected
                else (ICON_CONNECT, "Connect", self._bt_connect),
                (ICON_TRUST, "Untrust" if d.trusted else "Trust", self._bt_trust)]
        if d.paired:
            menu.append((ICON_REMOVE, "Remove", self._bt_remove))
        detail = "Connected" if d.connected else ("Paired" if d.paired else "")
        return Row(("bt", d.path), BT_ICONS.get(d.icon, ICON_BLUETOOTH), d.name, detail, active=d.connected,
                   menu=menu, action=self._bt_disconnect if d.connected else self._bt_connect, source=d)

    def _bt_job(self, row, label, start):
        key, generation = row.key, self._generation
        self._busy[key] = label
        self.queue_draw()

        def done(ok, message):
            self._busy.pop(key, None)
            if generation != self._generation:
                return
            if not ok:
                self._fail(key, message)
            self._read_bt()
        start(done)

    def _bt_connect(self, row):
        self._bt_job(row, "Connecting…", lambda done: bluetooth.connect(row.source, done))

    def _bt_disconnect(self, row):
        self._bt_job(row, "Disconnecting…", lambda done: bluetooth.disconnect(row.source, done))

    def _bt_trust(self, row):
        self._bt_job(row, "…", lambda done: bluetooth.set_trusted(row.source, not row.source.trusted, done))

    def _bt_remove(self, row):
        self._bt_job(row, "Removing…", lambda done: bluetooth.remove(self._adapter, row.source, done))

    def _toggle_discovery(self):
        if self._adapter is not None:
            bluetooth.set_discovering(self._adapter, not self._adapter_prop("Discovering"),
                                      lambda ok, message: ok or print(f"bluetooth: {message}"))

    def _toggle_visible(self):
        if self._adapter is not None:
            bluetooth.set_discoverable(self._adapter, not self._adapter_prop("Discoverable"),
                                       lambda ok, message: ok or print(f"bluetooth: {message}"))

    def _send_file(self):
        row = self._rows[self._selected] if self._selected is not None and self._selected < len(self._rows) else None
        args = ["blueman-sendto"]
        if row is not None and isinstance(row.source, bluetooth.Device):
            args.append(f"--device={row.source.address}")
        try:
            GLib.spawn_async(args, flags=GLib.SpawnFlags.SEARCH_PATH)
        except GLib.Error as e:
            print(f"bluetooth: {e.message}")


    def _fail(self, key, message):
        print(f"net: {message}")
        self._failed[key] = "Failed"
        GLib.timeout_add(FAIL_MS, lambda: (self._failed.pop(key, None), self.queue_draw(), False)[2])
        self.queue_draw()

    def _row_by_key(self, key):
        return next((row for row in self._rows if row.key == key), None)

    def _set_rows(self, rows):
        keys = [row.key for row in self._rows]
        selected = keys[self._selected] if self._selected is not None and self._selected < len(keys) else None
        menu = keys[self._menu_row] if self._menu_row is not None and self._menu_row < len(keys) else None
        self._rows = rows
        new_keys = [row.key for row in rows]
        self._selected = new_keys.index(selected) if selected in new_keys else None
        self._menu_row = new_keys.index(menu) if menu in new_keys else None
        if self._menu_row is None:
            self._menu_sel = None
        if self._password is not None and self._password[0] not in new_keys:
            self._password = None
        self._clamp()
        self._retarget()
        self.queue_draw()


    def _menu_items(self):
        return len(self._rows[self._menu_row].menu) if self._menu_row is not None else 0

    def _view_h(self):
        return nl.view_height(len(self._rows), self._menu_row, self._menu_items())

    def _clamp(self):
        self._scroll = nl.clamp_scroll(self._scroll, len(self._rows), self._menu_row, self._menu_items(),
                                       self._view_h())

    def _show(self, index):
        self._scroll = nl.scroll_to_show(self._scroll, index, len(self._rows), self._menu_row, self._menu_items(),
                                         self._view_h())

    def _plate_y(self):
        return 0 if self._top else nl.PAD

    def _classify(self, x, y):
        if self.kind is None:
            return None
        y -= self._plate_y()
        if self._header and nl.PAD <= y < nl.PAD + nl.HEAD_H:
            for index, (bx, size) in enumerate(nl.header_buttons(self._width, len(self._header))):
                if bx <= x < bx + size:
                    return ("head", index)
            return None
        top = nl.list_top(bool(self._header))
        if not top <= y < top + self._view_h() or not nl.PAD <= x < self._width - nl.PAD:
            return None
        return nl.hit(y - top, self._scroll, len(self._rows), self._menu_row, self._menu_items())

    def _hover(self, x, y):
        found = self._classify(x, y)
        head = found[1] if found is not None and found[0] == "head" else None
        selected, menu_sel = self._selected, self._menu_sel
        if found is not None and found[0] == "row":
            selected, menu_sel = found[1], None
        elif found is not None and found[0] == "menu":
            selected, menu_sel = self._menu_row, found[1]
        elif self._nav == "mouse":
            selected, menu_sel = self._menu_row, None
        if (selected, menu_sel, head) != (self._selected, self._menu_sel, self._head_hover):
            self._selected, self._menu_sel, self._head_hover = selected, menu_sel, head
            self.queue_draw()

    def _on_motion(self, _widget, event):
        self._pointer = (event.x, event.y)
        self._nav = "mouse"
        if self._head_sel is not None:
            self._head_sel = None
            self.queue_draw()
        self._hover(event.x, event.y)
        return True

    def _on_leave(self, _widget, _event):
        self._pointer = None
        if self._nav == "mouse":
            self._hover(-1, -1)
        return True

    def _on_press(self, _widget, event):
        found = self._classify(event.x, event.y)
        if found is None:
            if self._menu_row is not None:
                self._close_menu()
            return True
        kind, index = found
        if self._password is not None and not (kind == "row" and self._password[0] == self._rows[index].key):
            self._password = None
        if event.button == 3 and kind == "row":
            self._toggle_menu(index)
        elif event.button == 1:
            if kind == "head":
                self._header[index][2]()
            elif kind == "row":
                self._activate(index)
            elif kind == "menu":
                self._activate_menu(found[1])
        self.queue_draw()
        return True

    def _on_scroll(self, _widget, event):
        pixels = 0.0
        if event.direction == Gdk.ScrollDirection.UP:
            pixels = -nl.PITCH
        elif event.direction == Gdk.ScrollDirection.DOWN:
            pixels = nl.PITCH
        elif event.direction == Gdk.ScrollDirection.SMOOTH:
            pixels = event.delta_y * 30
        if pixels:
            self._scroll += pixels
            self._clamp()
            if self._nav == "mouse" and self._pointer:
                self._hover(*self._pointer)
            self.queue_draw()
        return True


    def _activate(self, index):
        row = self._rows[index]
        self._selected = index
        if row.action is not None and row.key not in self._busy:
            row.action(row)

    def _toggle_menu(self, index, from_keyboard=False):
        if self._menu_row == index:
            self._close_menu()
            return
        if not self._rows[index].menu:
            return
        self._menu_row = self._selected = index
        self._menu_sel = 0 if from_keyboard else None
        self._show(index)
        self._retarget()
        self.queue_draw()

    def _close_menu(self):
        self._menu_row = self._menu_sel = None
        self._clamp()
        self._retarget()
        self.queue_draw()

    def _activate_menu(self, item):
        row = self._rows[self._menu_row]
        self._close_menu()
        if row.key not in self._busy:
            row.menu[item][2](row)

    def key_press(self, event):
        if self.kind is None:
            return False
        if self._password is not None:
            return self._password_key(event)
        key = binds.nav_key(event)
        if key == Gdk.KEY_Escape:
            if self._menu_row is not None:
                self._close_menu()
            else:
                self.close()
            return True
        count = len(self._rows)
        if binds.matches(config.LAUNCHER_MENU_BIND, event):
            self.menu_tap()
            return True
        if self._head_sel is not None:
            return self._head_key(key, event)
        if (self._header and key == Gdk.KEY_Up and self._menu_row is None
                and (self._selected == 0 or not count)):
            self._nav = "keyboard"
            self._selected = None
            self._head_sel = 0
            self.queue_draw()
            return True
        if key in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            if event.state & (Gdk.ModifierType.SHIFT_MASK | NO_TEXT_MODS):
                return True
            if self._menu_row is not None and self._menu_sel is not None:
                self._activate_menu(self._menu_sel)
            elif self._selected is not None:
                self._activate(self._selected)
            self.queue_draw()
            return True
        if self._menu_row is not None:
            if key in (Gdk.KEY_Up, Gdk.KEY_Down):
                self._nav = "keyboard"
                last = self._menu_items() - 1
                step = 1 if key == Gdk.KEY_Down else -1
                self._menu_sel = 0 if self._menu_sel is None else max(0, min(last, self._menu_sel + step))
                self.queue_draw()
                return True
            if key == Gdk.KEY_Left:
                self._close_menu()
                return True
        if count and key in (Gdk.KEY_Right, Gdk.KEY_Menu) and self._menu_row is None:
            if self._selected is not None:
                self._nav = "keyboard"
                self._toggle_menu(self._selected, from_keyboard=True)
            return True
        if count and key in (Gdk.KEY_Up, Gdk.KEY_Down, Gdk.KEY_Home, Gdk.KEY_End, Gdk.KEY_Page_Up,
                             Gdk.KEY_Page_Down) and self._menu_row is None:
            self._nav = "keyboard"
            if self._selected is None:
                index = max(0, min(count - 1, int(self._scroll // nl.PITCH)))
            else:
                index = {Gdk.KEY_Up: self._selected - 1, Gdk.KEY_Down: self._selected + 1,
                         Gdk.KEY_Home: 0, Gdk.KEY_End: count - 1,
                         Gdk.KEY_Page_Up: self._selected - nl.VISIBLE,
                         Gdk.KEY_Page_Down: self._selected + nl.VISIBLE}[key]
            self._selected = max(0, min(count - 1, index))
            self._show(self._selected)
            self.queue_draw()
            return True
        return False

    @property
    def typing(self):
        return self._password is not None

    def menu_tap(self):
        """Context menu of the selected row (Shift+Enter tap or launcher.context-menu.bind)."""
        if self._password is not None or self._head_sel is not None:
            return
        if self._menu_row is not None:
            self._close_menu()
        elif self._selected is not None:
            self._toggle_menu(self._selected, from_keyboard=True)

    def _head_key(self, key, event):
        # Keyboard focus on the header buttons (rescan, search, visibility, send).
        count = len(self._header)
        if not count:
            self._head_sel = None
            return True
        self._head_sel = min(self._head_sel, count - 1)
        if key in (Gdk.KEY_Left, Gdk.KEY_Right):
            step = 1 if key == Gdk.KEY_Right else -1
            self._head_sel = max(0, min(count - 1, self._head_sel + step))
        elif key == Gdk.KEY_Down:
            self._head_sel = None
            if self._rows:
                self._selected = 0
                self._show(0)
        elif key in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_space):
            if not event.state & (Gdk.ModifierType.SHIFT_MASK | NO_TEXT_MODS):
                self._header[self._head_sel][2]()
        elif key not in (Gdk.KEY_Up, Gdk.KEY_Home, Gdk.KEY_End):
            return False
        self.queue_draw()
        return True

    def _password_key(self, event):
        key = event.keyval
        if key == Gdk.KEY_Escape:
            self._password = None
        elif key in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            self._submit_password()
        elif key == Gdk.KEY_BackSpace:
            self._password[1] = "" if event.state & Gdk.ModifierType.CONTROL_MASK else self._password[1][:-1]
        elif not event.state & NO_TEXT_MODS:
            code = Gdk.keyval_to_unicode(key)
            if code and chr(code).isprintable():
                self._password[1] += chr(code)
        self.queue_draw()
        return True


    def _layout(self, text, size=None, width=None):
        layout = self.create_pango_layout(text)
        if size is not None:
            desc = self.get_pango_context().get_font_description().copy()
            desc.set_absolute_size(size * Pango.SCALE)
            layout.set_font_description(desc)
        if width is not None:
            layout.set_width(max(1, int(width)) * Pango.SCALE)
            layout.set_ellipsize(Pango.EllipsizeMode.END)
        return layout

    def _on_draw(self, widget, cr):
        h = widget.get_allocated_height() - nl.PAD
        if h < 1:
            return False
        w = widget.get_allocated_width()
        y0 = self._plate_y()
        cr.save()
        rounded_rect(cr, 0, y0, w, h, min(theme.radius("#cc-net"), h / 2))
        cr.set_source_rgba(*theme.bg("#cc-net"))
        cr.fill_preserve()
        cr.clip()
        cr.translate(0, y0)
        if self._header:
            self._draw_header(cr, w)
        self._draw_list(cr, w)
        cr.restore()
        return False

    def _draw_header(self, cr, w):
        title = self._layout(TITLES.get(self.kind, ""), theme.font("#cc-net"))
        _, th = title.get_pixel_size()
        cr.set_source_rgba(*theme.fg("#cc-net"))
        cr.move_to(nl.PAD + 4, nl.PAD + (nl.HEAD_H - th) / 2)
        PangoCairo.show_layout(cr, title)
        for index, ((bx, size), (icon, on, _)) in enumerate(zip(nl.header_buttons(w, len(self._header)),
                                                                self._header)):
            hover = index == self._head_hover or index == self._head_sel
            item = _item(on, hover)
            cr.set_source_rgba(*theme.bg(item))
            rounded_rect(cr, bx, nl.PAD, size, nl.HEAD_H, theme.radius(item))
            cr.fill()
            cr.set_source_rgba(*theme.fg(item))
            dx, dy = GLYPH_NUDGE.get(icon, (0, 0))
            cx, cy = bx + size / 2 + dx, nl.PAD + nl.HEAD_H / 2 + dy
            if icon == ICON_RESCAN and self._spin_tick:
                cr.save()
                cr.translate(cx, cy)
                cr.rotate(self._spin * 2 * math.pi)
                glyph.show_centered(cr, self._layout(icon, theme.font("#cc-net")), 0, 0)
                cr.restore()
            else:
                glyph.show_centered(cr, self._layout(icon, theme.font("#cc-net")), cx, cy)

    def _draw_list(self, cr, w):
        top = nl.list_top(bool(self._header))
        view = self._view_h()
        cr.save()
        cr.rectangle(nl.PAD, top, w - 2 * nl.PAD, view)
        cr.clip()
        if not self._rows:
            text = self._layout(self._message, theme.font("#cc-net-empty"))
            tw, th = text.get_pixel_size()
            cr.set_source_rgba(*theme.fg("#cc-net-dim"))
            cr.move_to((w - tw) / 2, top + (nl.ITEM_H - th) / 2)
            PangoCairo.show_layout(cr, text)
        items = self._menu_items()
        for index, row in enumerate(self._rows):
            y = top + nl.row_top(index, self._menu_row, items) - self._scroll
            if y >= top + view:
                break
            if y + nl.ITEM_H > top:
                self._draw_row(cr, row, index, nl.PAD, y, w - 2 * nl.PAD)
            if index == self._menu_row:
                self._draw_menu(cr, row, nl.PAD, top + nl.menu_top(index) - self._scroll, w - 2 * nl.PAD)
        cr.restore()

    def _draw_row(self, cr, row, index, x, y, width):
        item = _item(row.active, index == self._selected)
        cr.set_source_rgba(*theme.bg(item))
        rounded_rect(cr, x, y, width, nl.ITEM_H, theme.radius(item))
        cr.fill()
        ink = theme.fg(item)
        dim = theme.fg("#cc-net-dim")
        cy = y + nl.ITEM_H / 2
        cr.set_source_rgba(*ink)
        glyph.show_centered(cr, self._layout(row.glyph, theme.font("#cc-net-glyph")), x + 18, cy)

        typing = self._password is not None and self._password[0] == row.key
        if typing:
            detail = "Enter ↵"
        else:
            detail = self._failed.get(row.key) or self._busy.get(row.key) or row.detail
        detail_layout = self._layout(detail, theme.font("#cc-net-dim")) if detail else None
        detail_w = detail_layout.get_pixel_size()[0] if detail_layout else 0
        lock_w = 14 if row.lock and not typing else 0
        right = x + width - 10
        if detail_layout is not None:
            dh = detail_layout.get_pixel_size()[1]
            cr.set_source_rgba(*theme.fg("#cc-net-dim.on" if row.active else "#cc-net-dim"))
            cr.move_to(right - detail_w, cy - dh / 2)
            PangoCairo.show_layout(cr, detail_layout)
        if lock_w:
            cr.set_source_rgba(*ink)
            glyph.show_centered(cr, self._layout(ICON_LOCK, theme.font("#cc-net-lock")), right - detail_w - 4 - lock_w / 2, cy)

        text_x = x + 36
        room = right - detail_w - (lock_w + 8 if lock_w else 0) - 8 - text_x
        if typing:
            secret = "•" * len(self._password[1])
            title = self._layout(secret + "|" if secret else "Password", theme.font("#cc-net-item"), room)
            cr.set_source_rgba(*(ink if secret else dim))
        else:
            title = self._layout(row.title, theme.font("#cc-net-item"), room)
            cr.set_source_rgba(*ink)
        _, th = title.get_pixel_size()
        cr.move_to(text_x, cy - th / 2)
        PangoCairo.show_layout(cr, title)

    def _draw_menu(self, cr, row, x, y, width):
        height = nl.menu_height(len(row.menu))
        cr.set_source_rgba(*theme.bg("#cc-net-menu"))
        rounded_rect(cr, x, y, width, height, theme.radius("#cc-net-menu"))
        cr.fill()
        item_w = width - 2 * nl.MENU_EDGE
        for k, (icon, label, _) in enumerate(row.menu):
            iy = y + nl.MENU_EDGE + k * (nl.MENU_ITEM_H + nl.MENU_GAP)
            active = k == self._menu_sel
            item = "#launcher-menu-item.active" if active else "#launcher-menu-item"
            cr.set_source_rgba(*theme.bg(item))
            rounded_rect(cr, x + nl.MENU_EDGE, iy, item_w, nl.MENU_ITEM_H, theme.radius(item))
            cr.fill()
            cr.set_source_rgba(*theme.fg(item))
            icon_cx = x + nl.MENU_EDGE + nl.MENU_PAD + nl.MENU_ICON / 2
            glyph.show_centered(cr, self._layout(icon, nl.MENU_ICON - 3), icon_cx, iy + nl.MENU_ITEM_H / 2)
            text = self._layout(label, theme.font("#cc-net-menu"))
            _, text_h = text.get_pixel_size()
            cr.move_to(x + nl.MENU_EDGE + nl.MENU_PAD + nl.MENU_ICON + 6, iy + (nl.MENU_ITEM_H - text_h) / 2)
            PangoCairo.show_layout(cr, text)
