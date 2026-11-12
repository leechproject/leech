import math
import cairo


def rounded_rect(cr, x, y, w, h, r):
    cr.new_sub_path()
    cr.arc(x + w - r, y + r,     r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0,            math.pi / 2)
    cr.arc(x + r,     y + h - r, r, math.pi / 2,  math.pi)
    cr.arc(x + r,     y + r,     r, math.pi,      3 * math.pi / 2)
    cr.close_path()


def draw_frame(cr, width, height, left, top, right, bottom, radius, color):
    cr.set_source_rgba(*color)
    cr.rectangle(0, 0, width, height)
    rounded_rect(cr, left, top, width - left - right, height - top - bottom, radius)
    cr.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
    cr.fill()


def notch_path(cr, x0, x1, top, h, r):
    r = min(r, (x1 - x0) / 2, h / 2)
    cr.new_sub_path()
    cr.move_to(x0 - r, 0)
    cr.line_to(x1 + r, 0)
    cr.line_to(x1 + r, top)
    cr.arc_negative(x1 + r, top + r, r, -math.pi / 2, -math.pi)
    cr.line_to(x1, top + h - r)
    cr.arc(x1 - r, top + h - r, r, 0, math.pi / 2)
    cr.line_to(x0 + r, top + h)
    cr.arc(x0 + r, top + h - r, r, math.pi / 2, math.pi)
    cr.line_to(x0, top + r)
    cr.arc_negative(x0 - r, top + r, r, 0, -math.pi / 2)
    cr.close_path()


def corner_path(cr, width, height, w, h, right, bottom, r, top=None):
    r = min(r, w / 2, h / 2)
    xl = width - right - w
    yt = height - bottom - h
    gap = r if top is None else max(0.0, yt - top)
    rt = min(r, gap)

    cr.new_sub_path()
    cr.move_to(width, yt - rt)
    cr.line_to(width - right, yt - rt)
    if rt > 0.01:
        cr.arc(width - right - rt, yt - rt, rt, 0, math.pi / 2)
    cr.line_to(xl + rt, yt)
    if rt > 0.01:
        cr.arc_negative(xl + rt, yt + rt, rt, -math.pi / 2, -math.pi)
    cr.line_to(xl, height - bottom - r)
    cr.arc(xl - r, height - bottom - r, r, 0, math.pi / 2)
    cr.line_to(xl - r, height)
    cr.line_to(width, height)
    cr.close_path()

    rw = r - gap
    if top is not None and rw > 0.01:
        cr.new_sub_path()
        cr.move_to(xl - rw, top - 1)
        cr.line_to(xl - rw, top)
        cr.arc(xl - rw, top + rw, rw, -math.pi / 2, 0)
        cr.line_to(xl + 1, top + rw)
        cr.line_to(xl + 1, top - 1)
        cr.close_path()
