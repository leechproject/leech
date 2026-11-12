import math
import cairo

# Двуслойная обводка (`*.outline`), от внешнего края внутрь: чёрный, затем белый.
# Толщина каждого слоя — `outline-thickness` (по умолчанию 1 px).
OUTLINE_LAYERS = ((0.0, 0.0, 0.0, 1.0), (1.0, 1.0, 1.0, 1.0))


def rounded_rect(cr, x, y, w, h, r):
    cr.new_sub_path()
    cr.arc(x + w - r, y + r,     r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0,            math.pi / 2)
    cr.arc(x + r,     y + h - r, r, math.pi / 2,  math.pi)
    cr.arc(x + r,     y + r,     r, math.pi,      3 * math.pi / 2)
    cr.close_path()


def draw_outline(cr, w, h, r, layers, thickness=1):
    """Кольца обводки внутрь от края плашки w×h со скруглением r.

    layers — цвета колец от внешнего к внутреннему, каждое толщиной thickness px.
    """
    cr.save()
    cr.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
    for i, color in enumerate(layers):
        outer, inner = i * thickness, (i + 1) * thickness
        if w - 2 * inner <= 0 or h - 2 * inner <= 0:
            break
        rounded_rect(cr, outer, outer, w - 2 * outer, h - 2 * outer, max(0.0, r - outer))
        rounded_rect(cr, inner, inner, w - 2 * inner, h - 2 * inner, max(0.0, r - inner))
        cr.set_source_rgba(*color)
        cr.fill()
    cr.restore()


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


def notch_edge_path(cr, x0, x1, top, h, r):
    """Свободный край челки из notch_path: скругления у рамки и тело, без отрезков вдоль рамки."""
    r = min(r, (x1 - x0) / 2, h / 2)
    cr.new_sub_path()
    cr.arc_negative(x1 + r, top + r, r, -math.pi / 2, -math.pi)
    cr.line_to(x1, top + h - r)
    cr.arc(x1 - r, top + h - r, r, 0, math.pi / 2)
    cr.line_to(x0 + r, top + h)
    cr.arc(x0 + r, top + h - r, r, math.pi / 2, math.pi)
    cr.line_to(x0, top + r)
    cr.arc_negative(x0 - r, top + r, r, 0, -math.pi / 2)


def snap_centered(total, w):
    """Отрезок длины ≈w по центру total с целыми концами: обводка на полупикселе размывается в серый."""
    x0 = round((total - w) / 2)
    return x0, total - x0


def stroke_inside(cr, shape, line, layers, thickness=1):
    """Обводка вдоль линии line внутрь фигуры shape: кольца по thickness px, layers — цвета снаружи внутрь.

    shape и line — функции, строящие путь в cr.
    """
    cr.save()
    shape(cr)
    cr.clip()
    cr.set_line_cap(cairo.LINE_CAP_BUTT)
    for i in reversed(range(len(layers))):
        line(cr)
        cr.set_line_width(2 * thickness * (i + 1))
        cr.set_source_rgba(*layers[i])
        cr.stroke()
    cr.restore()


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


def corner_edge_path(cr, width, height, w, h, right, bottom, r, top=None):
    """Свободный край фигуры corner_path: без отрезков вдоль рамки."""
    r = min(r, w / 2, h / 2)
    xl = width - right - w
    yt = height - bottom - h
    gap = r if top is None else max(0.0, yt - top)
    rt = min(r, gap)

    cr.new_sub_path()
    if rt > 0.01:
        cr.arc(width - right - rt, yt - rt, rt, 0, math.pi / 2)
        cr.line_to(xl + rt, yt)
        cr.arc_negative(xl + rt, yt + rt, rt, -math.pi / 2, -math.pi)
    else:
        cr.move_to(xl, yt)
    cr.line_to(xl, height - bottom - r)
    cr.arc(xl - r, height - bottom - r, r, 0, math.pi / 2)

    rw = r - gap
    if top is not None and rw > 0.01:
        cr.new_sub_path()
        cr.arc(xl - rw, top + rw, rw, -math.pi / 2, 0)


def frame_shape(cr, width, height, left, top, right, bottom, radius):
    """Фигура рамки для обрезки: экран без скруглённого окна внутри."""
    cr.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
    cr.rectangle(0, 0, width, height)
    rounded_rect(cr, left, top, width - left - right, height - top - bottom, radius)


def clip_out_band(cr, width, height, side, band):
    start, end = band
    if end <= start:
        return
    if side in ("left", "right"):
        lo, hi = (start, end) if side == "left" else (width - end, width - start)
        cr.rectangle(0, 0, max(0, lo), height)
        cr.rectangle(hi, 0, max(0, width - hi), height)
    else:
        lo, hi = (start, end) if side == "top" else (height - end, height - start)
        cr.rectangle(0, 0, width, max(0, lo))
        cr.rectangle(0, hi, width, max(0, height - hi))
    cr.clip()
