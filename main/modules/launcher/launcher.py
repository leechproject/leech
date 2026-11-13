import cairo
import gi

gi.require_version("GtkLayerShell", "0.1")
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import GtkLayerShell, Gtk, Gdk, GLib, Pango, PangoCairo

from modules.common.surface import ShapedWindow, after_commit, no_input, init_layer, on_monitor

from modules import config
from modules.parsing import apps
from modules.common import drawing
from modules.common import glyph
from modules.common import binds
from modules.common import layerkeys
from modules.common import theme
from modules.launcher import launcher_layout as ll
from modules.launcher import start_layout as sl
from modules.launcher.start_menu import StartFooter
from modules.animations import anim
from modules.animations.anim import Tween
from modules.common.icons import IconCache
from modules.common.ghost import DockGhost
from modules.common.shapes import notch_path, rounded_rect
from modules.common.edge import AttachedEdge

ICON_EYE = "\uf06e"
ICON_HEART = "heart"

EDGE = AttachedEdge(config.LAUNCHER_TOP)
START = config.UNDERCOVER_LAUNCHER
SEP = config.LAUNCHER_SEPARATE and not START
DETACHED = START or SEP
LIFT = sl.SCREEN_GAP if START else (config.DOCK_SEP_GAP if SEP else 0)
FRAME = EDGE.frame + LIFT
_NO_INPUT = no_input()
_HEADER_BAR = (22, 4)
_HIDDEN_ALPHA = 0.45
_NO_TEXT_MODS = (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.MOD1_MASK | Gdk.ModifierType.SUPER_MASK
                 | Gdk.ModifierType.META_MASK)

_TAB = (Gdk.KEY_Tab, Gdk.KEY_ISO_Left_Tab, Gdk.KEY_KP_Tab)
# Tab moves the keyboard focus between these zones; letters type into the search only in "search".
ZONES = (("search",) if config.LAUNCHER_SEARCHBAR else ()) + ("list",) + (("footer",) if START else ())

_NAV = {Gdk.KEY_Up: "up", Gdk.KEY_Down: "down", Gdk.KEY_Home: "home", Gdk.KEY_End: "end",
        Gdk.KEY_Page_Up: "pgup", Gdk.KEY_Page_Down: "pgdn"}


class LauncherWindow(ShapedWindow):
    def __init__(self, controller, entries, pinned_ids, pinned_count, start_size, dock_infos, dock_extra=0):
        super().__init__(name="launcher", visible=False, all_visible=False)
        self._controller = controller
        self._all = entries
        self._pinned = set(pinned_ids)
        self._pinned_count = pinned_count
        self._dock_extra = dock_extra
        self._hidden = set(apps.read_hidden())
        self._liked = apps.read_liked()
        self._show_hidden = False
        self._query = ""
        self._rows = []
        self._start_size = start_size
        self._selected = None
        self._nav_mode = None
        self._menu_row = None
        self._menu_sel = None
        self._zone = ZONES[0]
        self._header_hover = False
        self._scroll = 0.0
        self._pointer = None
        self._size = (0, 0)
        self._body_h = 0
        self._shape = None
        self.closing = False
        self._relax_source = 0
        self._icons = IconCache()
        self._ghost = DockGhost(self, dock_infos, start_size[0], self._queue_area, EDGE,
                                controller.output_scale(), FRAME)
        self._alpha = 0.0
        self._footer = StartFooter(self, controller) if START else None
        self._rebuild_rows()

        visual = self.get_screen().get_rgba_visual()
        if visual:
            self.set_visual(visual)
        self.set_app_paintable(True)

        init_layer(self)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.TOP)
        for edge in (GtkLayerShell.Edge.TOP, GtkLayerShell.Edge.BOTTOM,
                     GtkLayerShell.Edge.LEFT, GtkLayerShell.Edge.RIGHT):
            GtkLayerShell.set_anchor(self, edge, True)
        GtkLayerShell.set_exclusive_zone(self, -1)
        layerkeys.set_keyboard(self, "exclusive")
        self._relax_source = GLib.timeout_add(180, self._relax)

        self._area = Gtk.DrawingArea()
        self._area.set_name("launcher-area")
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

        self._grow = Tween(anim.ms(), self._on_grow_tick)
        self._fade = Tween(anim.ms(140), self._on_fade_tick)
        self._tuck = 0.0
        self._slide = Tween(anim.ms(), self._on_slide_tick)

        self.connect("size-allocate", self._on_allocate)
        self.show_all()

    def _relax(self):
        self._relax_source = 0
        layerkeys.set_keyboard(self, "on_demand")
        return False


    def _rebuild_rows(self, select_first=False):
        selected_id = self._rows[self._selected].id if self._selected is not None and self._selected < len(self._rows) else None
        self._rows = ll.build_rows(self._all, self._query, self._liked, self._hidden, self._show_hidden)
        if select_first and self._rows:
            self._selected = 0
        else:
            self._selected = next((i for i, e in enumerate(self._rows) if e.id == selected_id), None)
        self._menu_row = None
        self._menu_sel = None
        self._scroll = ll.clamp_scroll(self._scroll, len(self._rows), None, self._list_h())
        if self._selected is not None:
            self._scroll = ll.scroll_to_show(self._scroll, self._selected, len(self._rows), None, self._list_h())

    def _list_h(self):
        if not self._body_h:
            return 0
        return ll.list_height(self._body_h) - (sl.footer_space() if START else 0)


    def _target_shape(self):
        if START:
            width = ll.dock_width(sl.REFERENCE_ICONS)
            x0 = sl.body_left(self._size[0], width, config.UNDERCOVER_LEFT, config.LEFT)
            return (x0, x0 + width, self._body_h)
        width = ll.launcher_width(self._pinned_count, self._dock_extra)
        x0 = (self._size[0] - width) // 2
        return (x0, x0 + width, self._body_h)

    def _on_allocate(self, _widget, allocation):
        if self._shape is None and allocation.width > 100 and allocation.height > 200:
            self._begin(allocation.width, allocation.height)
            self._apply_input()

    def _begin(self, width, height):
        self._size = (width, height)
        self._body_h = sl.body_height(height) if START else round(height * config.LAUNCHER_HEIGHT)
        target = self._target_shape()
        dock_w, dock_h = self._start_size
        if START or (SEP and not (dock_w >= 1 and dock_h >= 1)):
            self._shape = target
            self._alpha = 1.0
            self._tuck = target[2] + LIFT
            self._slide.run((self._tuck,), (0.0,))
            self._controller.on_ready(self)
            return
        if dock_w >= 1 and dock_h >= 1:
            x0 = (width - round(dock_w)) // 2
            start = (x0, x0 + round(dock_w), dock_h)
        else:
            start = (target[0], target[1], 0)
        self._shape = start
        self._ghost.fade_out()
        self._grow.run(start, target, lambda: self._fade.run((0.0,), (1.0,)))
        self._controller.on_ready(self)

    def begin_close(self, final_size):
        if self.closing:
            return
        self.closing = True
        self._fade.stop()
        self._selected = self._menu_row = self._menu_sel = None
        if self._shape is None:
            self._controller.on_finished()
            return
        if START or (SEP and not final_size):
            self._grow.stop()
            self._slide.run((self._tuck,), (self._shape[2] + LIFT,), self._controller.on_finished)
            return
        self._alpha = 0.0
        if final_size:
            dock_w, dock_h = final_size
            x0 = (self._size[0] - dock_w) // 2
            target = (x0, x0 + dock_w, dock_h)
            self._ghost.fade_in_later(dock_w)
        else:
            target = (self._shape[0], self._shape[1], 0)
        self._grow.run(self._shape, target, self._controller.on_finished)

    def dispose(self):
        self._grow.stop()
        self._fade.stop()
        self._slide.stop()
        self._ghost.stop()
        if self._relax_source:
            GLib.source_remove(self._relax_source)
        self.destroy()

    def _retarget_width(self):
        if not self.closing and self._shape is not None:
            self._grow.run(self._shape, self._target_shape(), None)

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

    def _on_fade_tick(self, values):
        self._alpha = values[0]
        self._area.queue_draw()


    def _geometry(self):
        x0, x1, _ = self._target_shape()
        body_top = EDGE.body_y(self._size[1], self._body_h, FRAME)
        return x0, x1, body_top, body_top + config.LAUNCHER_HEAD_H, body_top + ll.LIST_OFFSET, self._list_h()

    def _classify(self, x, y):
        if self._shape is None or self.closing:
            return None
        x0, x1, body_top, search_top, list_top, list_h = self._geometry()
        if not x0 <= x < x1:
            return None
        if self._footer is not None:
            found = self._footer.hit(x0, x1, body_top + self._body_h, x, y)
            if found is not None:
                return found
        if body_top <= y < search_top:
            return ("header",) if config.LAUNCHER_SHOW_HIDDEN_TOGGLE else None
        if search_top <= y < search_top + ll.SEARCH_H:
            return ("search",)
        if not list_top <= y < list_top + list_h:
            return None
        found = ll.hit(y - list_top, self._scroll, len(self._rows), self._menu_row)
        if found is None:
            return None
        kind, index = found
        if kind == "row" and not x0 + ll.EDGE <= x < x1 - ll.EDGE:
            return None
        if kind == "menu" and not x0 + ll.MENU_PAD + ll.MENU_EDGE <= x < x1 - ll.MENU_PAD - ll.MENU_EDGE:
            return None
        return found


    def _on_draw(self, area, cr):
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        if self._shape is None:
            return False
        x0, x1, h = self._shape
        if config.LAUNCHER_OUTLINE:
            # Целые края: обводка на полупикселе размывается в серый.
            x0, x1, h = round(x0), round(x1), round(h)
        height = area.get_allocated_height()
        cr.save()
        if DETACHED:
            EDGE.clip_inside(cr, area.get_allocated_width(), height)
            cr.translate(0, EDGE.toward(self._tuck))
        if h >= 1 and x1 - x0 >= 1:
            cr.save()
            if DETACHED:
                rounded_rect(cr, x0, EDGE.body_y(height, h, FRAME), x1 - x0, h, min(config.RADIUS, h / 2))
            else:
                EDGE.clip_bar(cr, area.get_allocated_width(), area.get_allocated_height())
                cr.save()
                EDGE.to_edge(cr, height)
                notch_path(cr, x0, x1, EDGE.frame, h, config.RADIUS)
                cr.restore()
            cr.set_source_rgba(*config.COLOR)
            cr.fill()
            cr.restore()
        if self._alpha > 0:
            cr.push_group()
            self._draw_content(cr)
            cr.pop_group_to_source()
            cr.paint_with_alpha(self._alpha)
        if config.LAUNCHER_OUTLINE and h >= 1 and x1 - x0 >= 1:
            EDGE.outline_body(cr, area.get_allocated_width(), height, x0, x1, h, DETACHED, FRAME)
        cr.restore()
        self._ghost.draw(cr, self._size[0], height)
        return False

    def _text_layout(self, text, width, size=None, ellipsize=Pango.EllipsizeMode.END):
        layout = self._area.create_pango_layout(text)
        if size is not None:
            desc = self._area.get_pango_context().get_font_description().copy()
            desc.set_absolute_size(size * Pango.SCALE)
            layout.set_font_description(desc)
        if width is not None:
            layout.set_width(max(0, int(width)) * Pango.SCALE)
            layout.set_ellipsize(ellipsize)
            layout.set_height(-1)
        return layout

    def _draw_content(self, cr):
        x0, x1, body_top, search_top, list_top, list_h = self._geometry()
        width = x1 - x0
        if config.LAUNCHER_SHOW_HIDDEN_TOGGLE:
            self._draw_header(cr, x0, width, body_top)
        if config.LAUNCHER_SEARCHBAR:
            self._draw_search(cr, x0, width, search_top)

        cr.save()
        cr.rectangle(x0, list_top, width, list_h)
        cr.clip()
        count = len(self._rows)
        if count == 0:
            layout = self._text_layout("No applications", None)
            text_w, _ = layout.get_pixel_size()
            cr.set_source_rgba(*theme.fg("#launcher-empty"))
            cr.move_to(x0 + max(ll.EDGE, (width - text_w) / 2), list_top + 8)
            PangoCairo.show_layout(cr, layout)
        first = max(0, int(self._scroll // ll.PITCH) - 1)
        for index in range(first, count):
            y = list_top + ll.row_top(index, self._menu_row) - self._scroll
            if y >= list_top + list_h:
                break
            if y + ll.ROW_H >= list_top:
                self._draw_row(cr, index, x0 + ll.EDGE, y, ll.plate_width(width), width)
            if index == self._menu_row:
                self._draw_menu(cr, x0, width, list_top + ll.menu_top(index) - self._scroll, self._rows[index])
        cr.restore()
        if self._footer is not None:
            self._footer.draw(cr, x0, x1, body_top + self._body_h)

    def _draw_header(self, cr, x0, width, body_top):
        cx, cy = x0 + width / 2, body_top + config.LAUNCHER_HEAD_H / 2
        header = "#launcher-header.hover" if self._header_hover else "#launcher-header"
        if self._show_hidden:
            layout = self._text_layout(ICON_EYE, None, theme.font("#launcher-header"))
            cr.set_source_rgba(*theme.fg(header))
            glyph.show_centered(cr, layout, cx, cy)
        else:
            bar_w, bar_h = min(_HEADER_BAR[0], width - 2 * ll.EDGE), _HEADER_BAR[1]
            cr.set_source_rgba(*theme.bg(header))
            rounded_rect(cr, cx - bar_w / 2, cy - bar_h / 2, bar_w, bar_h, bar_h / 2)
            cr.fill()

    def _draw_search(self, cr, x0, width, top):
        edge = ll.SEARCH_EDGE
        bar_x, bar_w, bar_h = x0 + edge, width - 2 * edge, ll.SEARCH_H
        cr.set_source_rgba(*theme.bg("#launcher-search"))
        rounded_rect(cr, bar_x, top, bar_w, bar_h, theme.radius("#launcher-search"))
        cr.fill()

        icon_w = 14
        room = bar_w - edge - icon_w - 6 - edge
        cr.set_source_rgba(*theme.fg("#launcher-search"))
        if room < ll.MIN_TEXT:
            drawing.magnifier(cr, bar_x + bar_w / 2, top + bar_h / 2, icon_w)
            return
        drawing.magnifier(cr, bar_x + edge + icon_w / 2, top + bar_h / 2, icon_w)
        text = self._text_layout(self._query, room, ellipsize=Pango.EllipsizeMode.START)
        text_w, text_h = text.get_pixel_size()
        text_x = bar_x + edge + icon_w + 6
        cr.move_to(text_x, top + (bar_h - text_h) / 2)
        PangoCairo.show_layout(cr, text)
        if self._zone == "search":
            cr.rectangle(text_x + min(text_w, room) + 1, top + (bar_h - 14) / 2, 1, 14)
            cr.fill()

    def _draw_row(self, cr, index, x, y, plate_w, width):
        entry = self._rows[index]
        active = index == self._selected
        row = "#launcher-row.active" if active else "#launcher-row"
        cr.set_source_rgba(*theme.bg(row))
        rounded_rect(cr, x, y, plate_w, ll.ROW_H, theme.radius(row))
        cr.fill()

        alpha = _HIDDEN_ALPHA if entry.id in self._hidden else 1.0
        with_text = ll.shows_text(width)
        icon_x = x + ll.PAD_L if with_text else x + (plate_w - config.DOCK_ICON) / 2
        icon_y = y + (ll.ROW_H - config.DOCK_ICON) / 2
        pixbuf = self._icons.get(entry.id, entry.info)
        if pixbuf is not None:
            Gdk.cairo_set_source_pixbuf(cr, pixbuf, icon_x, icon_y)
            cr.paint_with_alpha(alpha)
        liked = entry.id in self._liked
        if with_text:
            room = ll.text_width(width) - (config.LAUNCHER_HEART + 4 if liked else 0)
            layout = self._text_layout(entry.name, room)
            _, text_h = layout.get_pixel_size()
            r, g, b, a = theme.fg(row)
            cr.set_source_rgba(r, g, b, a * alpha)
            cr.move_to(icon_x + config.DOCK_ICON + ll.ICON_GAP, y + (ll.ROW_H - text_h) / 2)
            PangoCairo.show_layout(cr, layout)
            if liked:
                size = config.LAUNCHER_HEART
                drawing.heart(cr, x + plate_w - ll.PAD_L - size / 2, y + ll.ROW_H / 2, size)

    def _menu_items(self, entry):
        pinned, hidden, liked = entry.id in self._pinned, entry.id in self._hidden, entry.id in self._liked
        return [(config.ICON_PIN, "Unpin from dock" if pinned else "Pin to dock"),
                (ICON_EYE if hidden else config.ICON_HIDE, "Unhide from launcher" if hidden else "Hide from launcher"),
                (ICON_HEART, "Unlike" if liked else "Like")]

    def _draw_menu(self, cr, x0, width, top, entry):
        pad, edge, gap = ll.MENU_PAD, ll.MENU_EDGE, ll.MENU_GAP
        menu_x, menu_w = x0 + pad, width - 2 * pad
        cr.set_source_rgba(*theme.bg("#launcher-menu"))
        rounded_rect(cr, menu_x, top, menu_w, ll.MENU_H, theme.radius("#launcher-menu"))
        cr.fill()

        item_w = menu_w - 2 * edge
        with_text = ll.menu_text_width(width) >= ll.MIN_TEXT
        for k, (icon_text, label) in enumerate(self._menu_items(entry)):
            y = top + edge + k * (ll.MENU_ITEM_H + gap)
            active = k == self._menu_sel
            item = "#launcher-menu-item.active" if active else "#launcher-menu-item"
            cr.set_source_rgba(*theme.bg(item))
            rounded_rect(cr, menu_x + edge, y, item_w, ll.MENU_ITEM_H, theme.radius(item))
            cr.fill()

            cr.set_source_rgba(*theme.fg(item))
            icon_w = ll.MENU_ICON
            icon_x = menu_x + edge + (pad if with_text else (item_w - icon_w) / 2)
            icon_cx, icon_cy = icon_x + icon_w / 2, y + ll.MENU_ITEM_H / 2
            if icon_text == ICON_HEART:
                drawing.heart(cr, icon_cx, icon_cy, icon_w)
            else:
                glyph.show_centered(cr, self._text_layout(icon_text, None, ll.MENU_ICON), icon_cx, icon_cy)
            if with_text:
                text = self._text_layout(label, ll.menu_text_width(width))
                _, text_h = text.get_pixel_size()
                cr.move_to(menu_x + edge + pad + ll.MENU_ICON + 6, y + (ll.MENU_ITEM_H - text_h) / 2)
                PangoCairo.show_layout(cr, text)


    def _hover(self, x, y):
        found = self._classify(x, y)
        if self._footer is not None and self._footer.set_hover(found):
            self._area.queue_draw()
        header = found == ("header",)
        if found is not None and found[0] == "row":
            selected, menu_sel = found[1], None
        elif found is not None and found[0] == "menu":
            selected, menu_sel = self._menu_row, found[1]
        else:
            selected, menu_sel = (self._menu_row if self._menu_row is not None else None), None
        if (selected, menu_sel, header) != (self._selected, self._menu_sel, self._header_hover):
            self._selected, self._menu_sel, self._header_hover = selected, menu_sel, header
            self._area.queue_draw()

    def _on_motion(self, _widget, event):
        self._pointer = (event.x, event.y)
        self._nav_mode = "mouse"
        self._hover(event.x, event.y)
        return True

    def _on_leave(self, _widget, _event):
        if self._nav_mode == "mouse":
            self._hover(-1, -1)
        return True

    def _on_press(self, _widget, event):
        found = self._classify(event.x, event.y)
        if self._footer is not None and event.button == 1 and self._footer.press(found):
            self._area.queue_draw()
            return True
        if event.button == 3:
            if found is not None and found[0] == "row":
                self._toggle_menu(found[1])
        elif event.button == 1:
            if found == ("header",):
                self._toggle_show_hidden()
            elif found is not None and found[0] == "row":
                self._launch(found[1])
            elif found is not None and found[0] == "menu":
                self._activate_menu(found[1])
            elif self._menu_row is not None:
                self._close_menu()
        return True

    def _on_scroll(self, _widget, event):
        pixels = 0.0
        if event.direction == Gdk.ScrollDirection.UP:
            pixels = -ll.PITCH * 2
        elif event.direction == Gdk.ScrollDirection.DOWN:
            pixels = ll.PITCH * 2
        elif event.direction == Gdk.ScrollDirection.SMOOTH:
            pixels = event.delta_y * 30
        if pixels:
            self._scroll = ll.clamp_scroll(self._scroll + pixels, len(self._rows), self._menu_row, self._list_h())
            if self._nav_mode == "mouse" and self._pointer:
                self._hover(*self._pointer)
            self._area.queue_draw()
        return True


    @staticmethod
    def _typed_char(event):
        if event.state & _NO_TEXT_MODS:
            return ""
        code = Gdk.keyval_to_unicode(event.keyval)
        if code == 0:
            return ""
        char = chr(code)
        return char if char.isprintable() else ""

    def _set_query(self, query):
        self._query = query
        self._rebuild_rows(select_first=bool(query))
        self._area.queue_draw()

    def _on_key(self, _widget, event):
        if self.closing or self._shape is None:
            return True
        key, count = event.keyval, len(self._rows)

        if key == Gdk.KEY_Escape:
            if self._footer is not None and self._footer.menu_open:
                self._footer.close_menu()
                if self._zone == "footer":
                    self._footer.focus(("power",))
                self._area.queue_draw()
            elif self._menu_row is not None:
                self._close_menu()
            elif self._query:
                self._set_query("")
            else:
                self._controller.close()
            return True

        if key in _TAB and not event.state & _NO_TEXT_MODS:
            self._cycle_zone(-1 if key == Gdk.KEY_ISO_Left_Tab or event.state & Gdk.ModifierType.SHIFT_MASK else 1)
            return True

        if self._footer is not None and (self._zone == "footer" or self._footer.menu_open):
            if self._footer.key(binds.nav_key(event)):
                self._area.queue_draw()
            return True

        if self._zone == "list":
            key = binds.nav_key(event)

        if binds.matches(config.LAUNCHER_MENU_BIND, event):
            if self._menu_row is not None:
                self._close_menu()
            elif self._selected is not None:
                self._toggle_menu(self._selected, from_keyboard=True)
            return True

        if key in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            if self._menu_row is not None and self._menu_sel is not None:
                self._activate_menu(self._menu_sel)
            elif self._selected is not None:
                self._launch(self._selected)
            return True

        if key == Gdk.KEY_BackSpace:
            if self._query:
                self._set_query("" if event.state & Gdk.ModifierType.CONTROL_MASK else self._query[:-1])
            return True

        if self._menu_row is not None:
            if key in (Gdk.KEY_Up, Gdk.KEY_Down):
                self._nav_mode = "keyboard"
                step = 1 if key == Gdk.KEY_Down else -1
                self._menu_sel = 0 if self._menu_sel is None else max(0, min(ll.MENU_ITEMS - 1, self._menu_sel + step))
                self._area.queue_draw()
                return True
            if key == Gdk.KEY_Left:
                self._close_menu()
                return True

        if count and key in (Gdk.KEY_Right, Gdk.KEY_Menu) and self._menu_row is None:
            if self._selected is not None:
                self._nav_mode = "keyboard"
                self._toggle_menu(self._selected, from_keyboard=True)
            return True

        if count and key in _NAV and self._menu_row is None:
            self._nav_mode = "keyboard"
            if self._selected is None:
                index = max(0, min(count - 1, int(self._scroll // ll.PITCH)))
            else:
                page = max(1, self._list_h() // ll.PITCH)
                index = ll.move(self._selected, _NAV[key], count, page)
            self._selected = index
            self._scroll = ll.scroll_to_show(self._scroll, index, count, None, self._list_h())
            self._area.queue_draw()
            return True

        char = self._typed_char(event) if config.LAUNCHER_SEARCHBAR else ""
        if char and self._zone == "list" and config.VIM_KEYBINDS:
            # The list takes vim keys; "/" jumps to the search like in vim, other letters do nothing.
            if char == "/":
                self._set_zone("search")
            return True
        if char:
            if self._menu_row is not None:
                self._close_menu()
            if self._zone != "search":
                self._set_zone("search")
            self._set_query(self._query + char)
            return True
        return False

    def _cycle_zone(self, step):
        index = ZONES.index(self._zone) if self._zone in ZONES else 0
        self._set_zone(ZONES[(index + step) % len(ZONES)])

    def _set_zone(self, zone):
        if zone == self._zone:
            return
        if self._zone == "footer" and self._footer is not None:
            self._footer.close_menu()
            self._footer.focus(None)
        self._zone = zone
        if zone == "list" and self._rows and self._selected is None:
            self._nav_mode = "keyboard"
            self._selected = max(0, min(len(self._rows) - 1, int(self._scroll // ll.PITCH)))
            self._scroll = ll.scroll_to_show(self._scroll, self._selected, len(self._rows), None, self._list_h())
        elif zone == "footer":
            self._nav_mode = "keyboard"
            if self._menu_row is not None:
                self._close_menu()
            self._footer.focus(("power",))
        self._area.queue_draw()


    def _toggle_menu(self, index, from_keyboard=False):
        if not config.LAUNCHER_MENU_ENABLED:
            return
        if self._menu_row == index:
            self._close_menu()
            return
        self._menu_row = index
        self._selected = index
        self._menu_sel = 0 if from_keyboard else None
        self._scroll = ll.scroll_to_show(self._scroll, index, len(self._rows), index, self._list_h(), with_menu=True)
        self._area.queue_draw()

    def _close_menu(self):
        self._menu_row = self._menu_sel = None
        self._scroll = ll.clamp_scroll(self._scroll, len(self._rows), None, self._list_h())
        self._area.queue_draw()

    def _activate_menu(self, item):
        entry = self._rows[self._menu_row]
        if item == 0:
            self._toggle_pin(entry)
        elif item == 1:
            self._toggle_hidden(entry)
        else:
            self._toggle_like(entry)
        if self._menu_row is not None:
            self._close_menu()

    def _toggle_pin(self, entry):
        if entry.id in self._pinned:
            ok, message = self._controller.unpin(entry.id)
            if ok:
                self._pinned.discard(entry.id)
                self._pinned_count = max(0, self._pinned_count - 1)
        else:
            ok, message = self._controller.pin(entry.id)
            if ok:
                self._pinned.add(entry.id)
                self._pinned_count += 1
        if not ok:
            print(f"launcher: {message}")
        self._retarget_width()

    def _toggle_hidden(self, entry):
        ids = apps.read_hidden()
        if entry.id in self._hidden:
            self._hidden.discard(entry.id)
            ids = [i for i in ids if i != entry.id]
        else:
            self._hidden.add(entry.id)
            ids.append(entry.id)
        apps.write_hidden(ids)
        self._rebuild_rows()
        self._area.queue_draw()

    def _toggle_like(self, entry):
        liked = apps.read_liked()
        if entry.id in liked:
            liked = [i for i in liked if i != entry.id]
        else:
            liked.append(entry.id)
        apps.write_liked(liked)
        self._liked = liked
        self._rebuild_rows()
        self._area.queue_draw()

    def _toggle_show_hidden(self):
        self._show_hidden = not self._show_hidden
        self._rebuild_rows()
        self._area.queue_draw()

    def _launch(self, index):
        apps.launch(self._rows[index].info)
        self._controller.close()


    def input_region(self):
        if self._shape is not None and self._shape[2] >= 1 and self._tuck < 1:
            x0, x1, h = self._shape
            if DETACHED:
                y, body = round(EDGE.body_y(self._size[1], h, FRAME)), round(h)
            else:
                y, body = EDGE.attached_rect(self._size[1], h)
            return cairo.Region(cairo.RectangleInt(round(x0), y, round(x1 - x0), body))
        return _NO_INPUT


class Launcher:
    def __init__(self, targets, canvas):
        self._targets = targets
        self._dock = None
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
        target = self._targets()
        self._dock = target.dock
        with on_monitor(target.monitor):
            start = self._dock.current_size() if self._morph() else (0.0, 0.0)
            self._window = LauncherWindow(self, apps.all_entries(), apps.read_pinned(), self._dock.pinned_count(),
                                          start, self._dock.icon_infos(), self._dock.extra_width())
        self._canvas.catch("launcher", self.close)

    def close(self):
        if self._window is None:
            return
        self._canvas.release("launcher")
        self._window.begin_close(self._dock.final_size() if self._morph() else None)

    def pin(self, app_id):
        return self._dock.try_pin(app_id)

    def unpin(self, app_id):
        return self._dock.try_unpin(app_id)


    def output_scale(self):
        return self._dock.output_scale()

    @staticmethod
    def _morph():
        return config.DOCK_SEPARATE == (config.LAUNCHER_SEPARATE and not START)

    def on_ready(self, window):
        after_commit(window, lambda: self._suspend_dock(window))

    def _suspend_dock(self, window):
        if window is self._window and not window.closing:
            self._dock.suspend(instant=self._morph())

    def on_finished(self):
        window, self._window = self._window, None
        if window is None:
            self._dock.resume(instant=self._morph())
        elif self._dock.resume(instant=self._morph()):
            after_commit(self._dock, window.dispose)
        else:
            window.dispose()
