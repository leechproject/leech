"""Geometry and colours of the record panel (pure, no GTK).

The panel plate holds, left to right, the record/stop button, the pause button
(only while recording) and the timer; on the right lies the panel's own tray, a
plate that grows leftwards from its toggle and reveals the microphone and
audio switches. Buttons and the tray plate stand PAD from the panel's edges, the
tray's items ITEM_PAD from the tray plate's edges and from each other.
"""

from modules.common import theme

PLATE_H = 44
PAD = theme.pad("#cc-record")
BUTTON = PLATE_H - 2 * PAD
ITEM_PAD = theme.pad("#cc-record-tray")
ITEM = BUTTON - 2 * ITEM_PAD
TRAY_ITEMS = ("audio", "microphone")


def tray_width(progress):
    closed = BUTTON
    opened = ITEM_PAD + (len(TRAY_ITEMS) + 1) * (ITEM + ITEM_PAD)
    return closed + (opened - closed) * progress


def tray_rect(width, progress):
    w = tray_width(progress)
    return (width - PAD - w, PAD, w, BUTTON)


def rects(width, recording, tray_open):
    """Pressable elements, in keyboard order, as {name: (x, y, w, h)}."""
    out = {"record": (PAD, PAD, BUTTON, BUTTON)}
    if recording:
        out["pause"] = (2 * PAD + BUTTON, PAD, BUTTON, BUTTON)
    toggle_x = width - PAD - ITEM_PAD - ITEM
    y = PAD + ITEM_PAD
    if tray_open:
        # Audio next to the toggle, the microphone left of it.
        out["microphone"] = (toggle_x - 2 * (ITEM + ITEM_PAD), y, ITEM, ITEM)
        out["audio"] = (toggle_x - (ITEM + ITEM_PAD), y, ITEM, ITEM)
    out["tray"] = (toggle_x, y, ITEM, ITEM)
    return out


def hit(width, recording, tray_open, x, y):
    for name, (rx, ry, rw, rh) in rects(width, recording, tray_open).items():
        if rx <= x < rx + rw and ry <= y < ry + rh:
            return name
    return None


def selector(name, recording, on, highlighted):
    """The style.css rule (theme.py) of one element. on: a tray switch is on. Tray items never invert.

    Highlight (hover or arrow focus): an element that is not on lightens, one that is on greys.
    """
    if name in ("tray",) + TRAY_ITEMS:
        return "#cc-record-item" + (".on" if on else "") + (".hover" if highlighted else "")
    if highlighted:
        return "#cc-record-button.hover"
    return "#cc-record-button.recording" if recording else "#cc-record-button"


def panel_selector(recording):
    """The panel plate; its color is for the timer and the message."""
    return "#cc-record.recording" if recording else "#cc-record"
