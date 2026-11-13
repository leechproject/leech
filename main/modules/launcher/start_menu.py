import getpass
import math
from pathlib import Path

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gdk, GdkPixbuf, GLib, PangoCairo

from modules import config
from modules.common import glyph, theme
from modules.common.shapes import rounded_rect
from modules.launcher import start_layout as sl
from modules.parsing import power

ICON_SETTINGS = ""
ICON_POWER = ""
ICON_USER = ""
USERNAME = getpass.getuser()


def _menu_entries():
    return (("Sleep", config.ICON_SLEEP, power.suspend),
            ("Reboot", config.ICON_REBOOT, power.reboot),
            ("Shutdown", config.ICON_POWEROFF, power.poweroff))


def _avatar_pixbuf(size):
    for name in (".face.icon", ".face"):
        path = Path.home() / name
        if not path.is_file():
            continue
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(str(path))
        except GLib.Error:
            continue
        scale = max(size / pixbuf.get_width(), size / pixbuf.get_height())
        width = max(size, math.ceil(pixbuf.get_width() * scale))
        height = max(size, math.ceil(pixbuf.get_height() * scale))
        scaled = pixbuf.scale_simple(width, height, GdkPixbuf.InterpType.BILINEAR)
        return scaled.new_subpixbuf((width - size) // 2, (height - size) // 2, size, size)
    return None


class StartFooter:
    def __init__(self, window, controller):
        self._window = window
        self._controller = controller
        self._avatar = _avatar_pixbuf(sl.BUTTON)
        self._hover = None
        self.menu_open = False

    def hit(self, x0, x1, body_bottom, x, y):
        return sl.hit(x0, x1, body_bottom, x, y, self.menu_open)

    def set_hover(self, found):
        hover = found if found is not None and found[0] in ("power", "settings", "power-menu") else None
        if hover == self._hover:
            return False
        self._hover = hover
        return True

    def close_menu(self):
        self.menu_open = False

    def focus(self, target):
        """Keyboard focus: ("settings",), ("power",), ("power-menu", index) or None; drawn like the hover."""
        self._hover = target

    def key(self, key):
        """A key (arrows already resolved from vim keys) while the footer or its power menu has the focus."""
        if self.menu_open:
            count = len(sl.MENU_ITEMS)
            index = self._hover[1] if self._hover is not None and self._hover[0] == "power-menu" else None
            if key in (Gdk.KEY_Up, Gdk.KEY_Down):
                step = 1 if key == Gdk.KEY_Down else -1
                index = 0 if index is None else max(0, min(count - 1, index + step))
                self._hover = ("power-menu", index)
            elif key in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_space) and index is not None:
                self.press(("power-menu", index))
            return True
        if key in (Gdk.KEY_Left, Gdk.KEY_Right):
            self._hover = ("settings",) if key == Gdk.KEY_Left else ("power",)
        elif key in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_space):
            if self._hover == ("power",):
                self.menu_open = True
                self._hover = ("power-menu", 0)
        return True

    def press(self, found):
        kind = found[0] if found is not None else None
        if kind == "power":
            self.menu_open = not self.menu_open
            return True
        if kind == "power-menu":
            if found[1] is not None:
                self.menu_open = False
                _menu_entries()[found[1]][2]()
                self._controller.close()
            return True
        if kind in ("settings", "avatar", "footer"):
            self.menu_open = False
            return True
        if self.menu_open:
            self.menu_open = False
            return True
        return False

    def draw(self, cr, x0, x1, body_bottom):
        plate = sl.footer(x0, x1, body_bottom)
        cr.set_source_rgba(*theme.bg("#start-footer"))
        rounded_rect(cr, *plate, theme.radius("#start-footer"))
        cr.fill()
        self._draw_avatar(cr, sl.avatar(plate))
        self._draw_username(cr, sl.username(plate))
        self._draw_button(cr, sl.settings(plate), ICON_SETTINGS, self._hover == ("settings",))
        power_rect = sl.power(plate)
        self._draw_button(cr, power_rect, ICON_POWER, self._hover == ("power",) or self.menu_open)
        if self.menu_open:
            self._draw_menu(cr, sl.menu(power_rect))

    def _draw_avatar(self, cr, rect):
        x, y, w, h = rect
        cr.save()
        cr.arc(x + w / 2, y + h / 2, w / 2, 0, 2 * math.pi)
        cr.clip()
        if self._avatar is not None:
            Gdk.cairo_set_source_pixbuf(cr, self._avatar, x, y)
            cr.paint()
        else:
            cr.set_source_rgba(*theme.bg("#start-avatar"))
            cr.paint()
            cr.set_source_rgba(*theme.fg("#start-avatar"))
            glyph.show_centered(cr, self._window._text_layout(ICON_USER, None, theme.font("#start-avatar")), x + w / 2, y + h / 2)
        cr.restore()

    def _draw_username(self, cr, rect):
        x, y, w, h = rect
        if w <= 0:
            return
        text = self._window._text_layout(USERNAME, w)
        _tw, th = text.get_pixel_size()
        cr.set_source_rgba(*theme.fg("#start-footer"))
        cr.move_to(x, y + (h - th) / 2)
        PangoCairo.show_layout(cr, text)

    def _draw_button(self, cr, rect, icon, active):
        x, y, w, h = rect
        button = "#start-button.hover" if active else "#start-button"
        cr.set_source_rgba(*theme.bg(button))
        rounded_rect(cr, x, y, w, h, theme.radius(button))
        cr.fill()
        cr.set_source_rgba(*theme.fg(button))
        glyph.show_centered(cr, self._window._text_layout(icon, None, theme.font("#start-button")), x + w / 2, y + h / 2)

    def _draw_menu(self, cr, box):
        cr.set_source_rgba(*theme.bg("#start-menu"))
        rounded_rect(cr, *box, theme.radius("#start-menu"))
        cr.fill()
        for index, (label, icon, _action) in enumerate(_menu_entries()):
            x, y, w, h = sl.menu_item(box, index)
            active = self._hover == ("power-menu", index)
            item = "#start-menu-item.active" if active else "#start-menu-item"
            cr.set_source_rgba(*theme.bg(item))
            rounded_rect(cr, x, y, w, h, theme.radius(item))
            cr.fill()
            cr.set_source_rgba(*theme.fg(item))
            menu_glyph = theme.font("#start-menu-item")
            icon_layout = self._window._text_layout(icon or "", None, menu_glyph)
            glyph.show_centered(cr, icon_layout, x + sl.MENU_PAD + menu_glyph / 2, y + h / 2)
            text_x = x + sl.MENU_PAD + menu_glyph + sl.MENU_PAD
            text = self._window._text_layout(label, w - (text_x - x) - sl.MENU_PAD)
            _tw, th = text.get_pixel_size()
            cr.move_to(text_x, y + (h - th) / 2)
            PangoCairo.show_layout(cr, text)
