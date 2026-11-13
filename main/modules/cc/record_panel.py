import math

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gtk, Gdk, GLib, Pango, PangoCairo

from modules import config
from modules.animations import anim
from modules.animations.anim import Tween
from modules.common import drawing, glyph, timefmt
from modules.common.shapes import rounded_rect
from modules.cc import record_layout as rl
from modules.common import theme

PLATE_H = rl.PLATE_H
MESSAGE_H = 18
ICON = theme.font("#cc-record-button")
ITEM_ICON = theme.font("#cc-record-item")
MESSAGE_MS = 1500
TRAY_GLYPH = config.TRAY_ICON or "\uf077"
MESSAGE = "Can't change while record is running"


class RecordPanel(Gtk.DrawingArea):
    def __init__(self, width, recorder, on_record, on_resize, on_hover=None):
        super().__init__()
        self.set_name("cc-record-panel")
        self._width = width
        self._recorder = recorder
        self._on_record = on_record
        self._on_resize = on_resize
        self._on_hover = on_hover
        self._hover = None
        self._focus = None
        self.audio = False
        self.microphone = False
        self._tray = 0.0
        self._tray_open = False
        self._message = False
        self._message_source = 0
        self._extra = 0.0
        self._tray_tween = Tween(anim.ms(180), self._on_tray_tick)
        self._extra_tween = Tween(anim.ms(), self._on_extra_tick)
        self.set_size_request(width, PLATE_H)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.POINTER_MOTION_MASK
                        | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        self.connect("draw", self._on_draw)
        self.connect("button-press-event", self._on_press)
        self.connect("motion-notify-event", self._on_motion)
        self.connect("leave-notify-event", self._on_leave)

    def height(self):
        return PLATE_H + round(self._extra)

    def refresh(self):
        self.queue_draw()


    def rects(self):
        """Pressable elements, left to right, as {name: (x, y, w, h)} in panel coordinates."""
        return rl.rects(self._width, self._recorder.active(), self._tray_open)

    def set_focus(self, name):
        """Keyboard focus (None clears it); it looks like the mouse hover and replaces it."""
        if name is not None:
            self._hover = None
        if name != self._focus:
            self._focus = name
            self.queue_draw()

    def _on_motion(self, _widget, event):
        name = rl.hit(self._width, self._recorder.active(), self._tray_open, event.x, event.y)
        if name is not None and self._on_hover is not None:
            self._on_hover()
        if name != self._hover:
            self._hover = name
            self.queue_draw()
        return False

    def _on_leave(self, _widget, _event):
        if self._hover is not None:
            self._hover = None
            self.queue_draw()
        return False

    def _on_press(self, _widget, event):
        if event.button == 1:
            self.press(rl.hit(self._width, self._recorder.active(), self._tray_open, event.x, event.y))
        return True

    def press(self, name):
        if name == "record":
            self._on_record()
        elif name == "pause":
            self._recorder.toggle_pause()
        elif name == "tray":
            self._tray_open = not self._tray_open
            self._tray_tween.run((self._tray,), (1.0 if self._tray_open else 0.0,))
        elif name in ("audio", "microphone"):
            if self._recorder.active():
                self._show_message()
            else:
                setattr(self, name, not getattr(self, name))
        self.queue_draw()

    def _on_tray_tick(self, values):
        self._tray = values[0]
        self.queue_draw()

    def _show_message(self):
        if self._message_source:
            GLib.source_remove(self._message_source)
        self._message_source = GLib.timeout_add(MESSAGE_MS, self._hide_message)
        if not self._message:
            self._message = True
            self._extra_tween.run((self._extra,), (MESSAGE_H,))

    def _hide_message(self):
        self._message_source = 0
        self._message = False
        self._extra_tween.run((self._extra,), (0.0,))
        return False

    def _on_extra_tick(self, values):
        self._extra = values[0]
        self.set_size_request(self._width, self.height())
        self.queue_draw()
        self._on_resize()


    def _layout(self, text, size):
        layout = self.create_pango_layout(text)
        desc = self.get_pango_context().get_font_description().copy()
        desc.set_absolute_size(size * Pango.SCALE)
        layout.set_font_description(desc)
        return layout

    def _highlighted(self, name):
        return name == (self._focus if self._focus is not None else self._hover)

    def _plate(self, cr, rect, selector):
        cr.set_source_rgba(*theme.bg(selector))
        rounded_rect(cr, *rect, theme.radius(selector))
        cr.fill()

    def _on_draw(self, widget, cr):
        w, h = widget.get_allocated_width(), widget.get_allocated_height()
        recording = self._recorder.active()
        panel = rl.panel_selector(recording)
        ink = theme.fg(panel)
        self._plate(cr, (0, 0, w, h), panel)
        rects = rl.rects(self._width, recording, True)

        def button(name, on=False):
            selector = rl.selector(name, recording, on, self._highlighted(name))
            x, y, bw, bh = rects[name]
            self._plate(cr, rects[name], selector)
            cr.set_source_rgba(*theme.fg(selector))
            return x + bw / 2, y + bh / 2, theme.bg(selector)[:3]

        cx, cy, _ = button("record")
        if recording:
            drawing.stop_square(cr, cx, cy, ICON)
            cx, cy, _ = button("pause")
            if self._recorder.paused:
                drawing.play_triangle(cr, cx, cy, ICON)
            else:
                drawing.pause_bars(cr, cx, cy, ICON)
            x, _, bw, _ = rects["pause"]
            timer = self._layout(timefmt.stopwatch(self._recorder.elapsed()), theme.font("#cc-record"))
            _, th = timer.get_pixel_size()
            cr.set_source_rgba(*ink)
            cr.move_to(x + bw + rl.PAD, cy - th / 2)
            PangoCairo.show_layout(cr, timer)
        else:
            drawing.record_dot(cr, cx, cy, ICON)

        tray = rl.tray_rect(self._width, self._tray)
        self._plate(cr, tray, "#cc-record-tray")
        if self._tray > 0.01:
            cr.save()
            rounded_rect(cr, *tray, theme.radius("#cc-record-tray"))
            cr.clip()
            cr.push_group()
            cx, cy, _ = button("audio", self.audio)
            drawing.speaker(cr, cx + 1, cy, ITEM_ICON, 100, not self.audio)
            cx, cy, fill = button("microphone", self.microphone)
            drawing.microphone(cr, cx, cy, ITEM_ICON, not self.microphone, fill)
            cr.pop_group_to_source()
            cr.paint_with_alpha(self._tray)
            cr.restore()

        cx, cy, _ = button("tray")
        cr.save()
        cr.translate(cx, cy)
        cr.rotate(-math.pi / 2 + math.pi * self._tray)
        glyph.show_centered(cr, self._layout(TRAY_GLYPH, theme.font("#cc-record-tray")), 0, 0)
        cr.restore()

        if self._extra > 0.5:
            text = self._layout(MESSAGE, theme.font("#cc-record-message"))
            tw, th = text.get_pixel_size()
            cr.set_source_rgba(*ink[:3], ink[3] * self._extra / MESSAGE_H)
            cr.move_to((w - tw) / 2, PLATE_H + (MESSAGE_H - th) / 2 - 4)
            PangoCairo.show_layout(cr, text)
        return False
