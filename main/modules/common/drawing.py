import math

import cairo


def magnifier(cr, cx, cy, size):
    radius = size * 0.32
    cr.set_line_width(max(1.5, size * 0.13))
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    cr.arc(cx - size * 0.08, cy - size * 0.08, radius, 0, 2 * math.pi)
    cr.stroke()
    edge = radius * 0.72
    cr.move_to(cx - size * 0.08 + edge, cy - size * 0.08 + edge)
    cr.line_to(cx + size * 0.42, cy + size * 0.42)
    cr.stroke()


def heart(cr, cx, cy, size):
    s = size
    cr.new_sub_path()
    cr.move_to(cx, cy + 0.42 * s)
    cr.curve_to(cx - 0.5 * s, cy + 0.02 * s, cx - 0.55 * s, cy - 0.38 * s, cx - 0.27 * s, cy - 0.38 * s)
    cr.curve_to(cx - 0.1 * s, cy - 0.38 * s, cx, cy - 0.27 * s, cx, cy - 0.17 * s)
    cr.curve_to(cx, cy - 0.27 * s, cx + 0.1 * s, cy - 0.38 * s, cx + 0.27 * s, cy - 0.38 * s)
    cr.curve_to(cx + 0.55 * s, cy - 0.38 * s, cx + 0.5 * s, cy + 0.02 * s, cx, cy + 0.42 * s)
    cr.close_path()
    cr.fill()


def sun(cr, cx, cy, size):
    cr.new_sub_path()
    cr.arc(cx, cy, size * 0.2, 0, 2 * math.pi)
    cr.fill()
    cr.set_line_width(max(1.2, size * 0.09))
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    for i in range(8):
        angle = i * math.pi / 4
        cr.move_to(cx + math.cos(angle) * size * 0.32, cy + math.sin(angle) * size * 0.32)
        cr.line_to(cx + math.cos(angle) * size * 0.46, cy + math.sin(angle) * size * 0.46)
    cr.stroke()


def speaker(cr, cx, cy, size, level, muted):
    s = size
    cr.new_sub_path()
    cr.move_to(cx - 0.46 * s, cy - 0.14 * s)
    cr.line_to(cx - 0.24 * s, cy - 0.14 * s)
    cr.line_to(cx + 0.02 * s, cy - 0.38 * s)
    cr.line_to(cx + 0.02 * s, cy + 0.38 * s)
    cr.line_to(cx - 0.24 * s, cy + 0.14 * s)
    cr.line_to(cx - 0.46 * s, cy + 0.14 * s)
    cr.close_path()
    cr.fill()
    cr.set_line_width(max(1.2, s * 0.09))
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    if muted:
        cr.move_to(cx + 0.16 * s, cy - 0.2 * s)
        cr.line_to(cx + 0.46 * s, cy + 0.2 * s)
        cr.move_to(cx + 0.46 * s, cy - 0.2 * s)
        cr.line_to(cx + 0.16 * s, cy + 0.2 * s)
        cr.stroke()
        return
    waves = 0 if level <= 0 else (1 if level < 50 else 2)
    for index in range(waves):
        radius = s * (0.22 + 0.2 * index)
        cr.new_sub_path()
        cr.arc(cx + 0.02 * s, cy, radius, -math.pi / 3.2, math.pi / 3.2)
        cr.stroke()


def record_dot(cr, cx, cy, size):
    cr.set_line_width(max(1.5, size * 0.08))
    cr.new_sub_path()
    cr.arc(cx, cy, size * 0.46, 0, 2 * math.pi)
    cr.stroke()
    cr.new_sub_path()
    cr.arc(cx, cy, size * 0.28, 0, 2 * math.pi)
    cr.fill()


def stop_square(cr, cx, cy, size):
    side = size * 0.72
    radius = side * 0.22
    x, y = cx - side / 2, cy - side / 2
    cr.new_sub_path()
    cr.arc(x + side - radius, y + radius, radius, -math.pi / 2, 0)
    cr.arc(x + side - radius, y + side - radius, radius, 0, math.pi / 2)
    cr.arc(x + radius, y + side - radius, radius, math.pi / 2, math.pi)
    cr.arc(x + radius, y + radius, radius, math.pi, 3 * math.pi / 2)
    cr.close_path()
    cr.fill()


def pause_bars(cr, cx, cy, size):
    bar_w, bar_h = size * 0.2, size * 0.7
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    cr.set_line_width(bar_w)
    for dx in (-size * 0.17, size * 0.17):
        cr.move_to(cx + dx, cy - bar_h / 2 + bar_w / 2)
        cr.line_to(cx + dx, cy + bar_h / 2 - bar_w / 2)
    cr.stroke()


def play_triangle(cr, cx, cy, size):
    h = size * 0.72
    w = h * 0.87
    cr.set_line_join(cairo.LINE_JOIN_ROUND)
    cr.set_line_width(size * 0.12)
    cr.move_to(cx - w / 3, cy - h / 2)
    cr.line_to(cx + 2 * w / 3, cy)
    cr.line_to(cx - w / 3, cy + h / 2)
    cr.close_path()
    cr.fill_preserve()
    cr.stroke()


def microphone(cr, cx, cy, size, muted, background=None):
    s = size
    w, h = 0.32 * s, 0.5 * s
    top = cy - 0.42 * s
    r = w / 2
    cr.new_sub_path()
    cr.arc(cx, top + r, r, math.pi, 2 * math.pi)
    cr.arc(cx, top + h - r, r, 0, math.pi)
    cr.close_path()
    cr.fill()
    cr.set_line_width(max(1.2, s * 0.08))
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    cr.new_sub_path()
    cr.arc(cx, top + h - r, 0.3 * s, 0.1, math.pi - 0.1)
    cr.stroke()
    cr.move_to(cx, top + h - r + 0.3 * s)
    cr.line_to(cx, cy + 0.42 * s)
    cr.stroke()
    if muted:
        if background is not None:
            source = cr.get_source()
            cr.set_source_rgb(*background)
            cr.set_line_width(max(1.2, s * 0.08) * 2.6)
            cr.move_to(cx - 0.38 * s, cy - 0.38 * s)
            cr.line_to(cx + 0.38 * s, cy + 0.38 * s)
            cr.stroke()
            cr.set_source(source)
            cr.set_line_width(max(1.2, s * 0.08))
        cr.move_to(cx - 0.38 * s, cy - 0.38 * s)
        cr.line_to(cx + 0.38 * s, cy + 0.38 * s)
        cr.stroke()
