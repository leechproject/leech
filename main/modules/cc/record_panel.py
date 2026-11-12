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

PLATE_H = 44
MESSAGE_H = 18
ICON = 24
EDGE = 6
GAP = 6
HIT = 15
MESSAGE_MS = 1500
TRAY_GLYPH = config.TRAY_ICON or "\uf077"
MESSAGE = "Can't change while record is running"

IDLE = ((9 / 255, 9 / 255, 9 / 255), (1.0, 1.0, 1.0))
RECORDING = ((212 / 255, 212 / 255, 212 / 255), (0.0, 0.0, 0.0))


class RecordPanel(Gtk.DrawingArea):
    def __init__(self, width, recorder, on_record, on_resize):
        super().__init__()
        self.set_name("cc-record-panel")
        self._width = width
        self._recorder = recorder
        self._on_record = on_record
        self._on_resize = on_resize
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
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect("draw", self._on_draw)
        self.connect("button-press-event", self._on_press)

    def height(self):
        return PLATE_H + round(self._extra)

    def refresh(self):
        self.queue_draw()


    def _centers(self):
        cy = EDGE + 4 + ICON / 2
        record = EDGE + ICON / 2
        pause = record + ICON + GAP
        tray = self._width - EDGE - ICON / 2
        audio = tray - ICON - GAP
        microphone = audio - ICON - GAP
        return cy, {"record": record, "pause": pause, "tray": tray, "audio": audio, "microphone": microphone}

    def _hit(self, x, y):
        cy, centers = self._centers()
        if abs(y - cy) > HIT:
            return None
        recording = self._recorder.active()
        for name, cx in centers.items():
            if name == "pause" and not recording:
                continue
            if name in ("audio", "microphone") and not self._tray_open:
                continue
            if abs(x - cx) <= HIT:
                return name
        return None

    def _on_press(self, _widget, event):
        if event.button == 1:
            self.press(self._hit(event.x, event.y))
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

    def _on_draw(self, widget, cr):
        w, h = widget.get_allocated_width(), widget.get_allocated_height()
        recording = self._recorder.active()
        plate, ink = RECORDING if recording else IDLE
        cr.set_source_rgb(*plate)
        rounded_rect(cr, 0, 0, w, h, 10)
        cr.fill()
        cr.set_source_rgb(*ink)
        cy, centers = self._centers()

        if recording:
            drawing.stop_square(cr, centers["record"], cy, ICON)
            if self._recorder.paused:
                drawing.play_triangle(cr, centers["pause"], cy, ICON)
            else:
                drawing.pause_bars(cr, centers["pause"], cy, ICON)
            timer = self._layout(timefmt.stopwatch(self._recorder.elapsed()), 14)
            _, th = timer.get_pixel_size()
            cr.move_to(centers["pause"] + ICON / 2 + GAP, cy - th / 2)
            PangoCairo.show_layout(cr, timer)
        else:
            drawing.record_dot(cr, centers["record"], cy, ICON)

        cr.save()
        cr.translate(centers["tray"], cy)
        cr.rotate(-math.pi / 2 + math.pi * self._tray)
        glyph.show_centered(cr, self._layout(TRAY_GLYPH, 16), 0, 0)
        cr.restore()

        if self._tray > 0.01:
            cr.save()
            cr.push_group()
            cr.set_source_rgb(*ink)
            drawing.speaker(cr, centers["audio"] + 2, cy, ICON, 100, not self.audio)
            cr.set_source_rgb(*ink)
            drawing.microphone(cr, centers["microphone"], cy, ICON, not self.microphone, plate)
            cr.pop_group_to_source()
            cr.paint_with_alpha(self._tray)
            cr.restore()

        if self._extra > 0.5:
            text = self._layout(MESSAGE, 11)
            tw, th = text.get_pixel_size()
            cr.set_source_rgba(*ink, self._extra / MESSAGE_H)
            cr.move_to((w - tw) / 2, PLATE_H + (MESSAGE_H - th) / 2 - 4)
            PangoCairo.show_layout(cr, text)
        return False
