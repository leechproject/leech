import math

SIDES = ("left", "top", "right", "bottom")
REFERENCE_BAR_WIDTH = 60


BAR_GAP = 5


def bar_detached(frame_enabled, bar_position, include_bar, undercover=False, split=False):
    return bar_position is not None and not undercover and (not include_bar or split)


def bar_gap(frame_enabled, bar_position, include_bar, undercover=False, split=False):
    detached = bar_detached(frame_enabled, bar_position, include_bar, undercover, split)
    return BAR_GAP if detached and not include_bar else 0


def drawn_sides(frame, frame_enabled):
    return {side: (frame[side] if frame_enabled else 0) for side in SIDES}


def frame_sides(frame, frame_enabled, bar_position, bar_width, include_bar, undercover=False, split=False):
    sides = drawn_sides(frame, frame_enabled)
    if bar_position is not None:
        detached = bar_detached(frame_enabled, bar_position, include_bar, undercover, split)
        own = sides[bar_position] if detached or not include_bar else 0
        gap = bar_gap(frame_enabled, bar_position, include_bar, undercover, split)
        sides[bar_position] = bar_width + own + gap
    return sides


def visible_frame(frame, frame_enabled, bar_position, bar_width, include_bar, undercover=False, split=False):
    if bar_detached(frame_enabled, bar_position, include_bar, undercover, split):
        return drawn_sides(frame, frame_enabled)
    return frame_sides(frame, frame_enabled, bar_position, bar_width, include_bar, undercover)


def bar_band(frame, frame_enabled, bar_position, bar_width, include_bar, undercover=False, split=False):
    if bar_position is None:
        return (0, 0)
    if bar_detached(frame_enabled, bar_position, include_bar, undercover, split):
        own = frame[bar_position] if frame_enabled else 0
        return (own, own + bar_gap(frame_enabled, bar_position, include_bar, undercover, split) + bar_width)
    return (0, bar_width)


def bar_margins(visible, bar_position, offset):
    across = ("left", "right") if is_horizontal(bar_position) else ("top", "bottom")
    margins = {side: visible[side] + BAR_GAP for side in across}
    margins[bar_position] = offset
    return margins


def bar_rect(width, height, bar_position, bar_width, margins):
    m = margins
    if bar_position == "left":
        return m["left"], m["top"], bar_width, height - m["top"] - m["bottom"]
    if bar_position == "right":
        return width - m["right"] - bar_width, m["top"], bar_width, height - m["top"] - m["bottom"]
    if bar_position == "top":
        return m["left"], m["top"], width - m["left"] - m["right"], bar_width
    return m["left"], height - m["bottom"] - bar_width, width - m["left"] - m["right"], bar_width


def is_horizontal(position):
    return position in ("top", "bottom")


def bar_scale(bar_width):
    return bar_width / REFERENCE_BAR_WIDTH


def scaled(value, scale):
    return math.floor(value * scale + 1e-9)


def snap_inset(value, output_scale, buffer_scale=None):
    if not output_scale or value <= 0:
        return value
    physical = value * output_scale
    if abs(physical - round(physical)) < 1e-6:
        return value
    on_output = math.ceil(physical) / output_scale
    if not buffer_scale:
        return on_output
    return math.ceil(on_output * buffer_scale - 1e-6) / buffer_scale


def follows_dock(position, dock_top):
    return dock_top if position == "dock.position" else position == "top"
