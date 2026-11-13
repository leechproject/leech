import unittest

import cairo

from modules.common.shapes import draw_outline

BLACK, WHITE = (0.0, 0.0, 0.0, 1.0), (1.0, 1.0, 1.0, 1.0)


def _render(w, h, r):
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    cr = cairo.Context(surface)
    cr.set_antialias(cairo.ANTIALIAS_NONE)
    draw_outline(cr, w, h, r, (BLACK, WHITE))
    surface.flush()
    data, stride = surface.get_data(), surface.get_stride()

    def pixel(x, y):
        b, g, red, a = data[y * stride + 4 * x: y * stride + 4 * x + 4]
        return red, g, b, a
    return pixel


class OutlineTest(unittest.TestCase):
    def test_black_outside_white_inside_on_straight_edges(self):
        pixel = _render(40, 40, 10)
        for x, y in ((20, 0), (0, 20), (39, 20), (20, 39)):
            self.assertEqual(pixel(x, y), (0, 0, 0, 255))
        for x, y in ((20, 1), (1, 20), (38, 20), (20, 38)):
            self.assertEqual(pixel(x, y), (255, 255, 255, 255))

    def test_inside_stays_untouched(self):
        pixel = _render(40, 40, 10)
        self.assertEqual(pixel(20, 2)[3], 0)
        self.assertEqual(pixel(20, 20)[3], 0)

    def test_corner_outside_radius_is_empty(self):
        pixel = _render(40, 40, 10)
        self.assertEqual(pixel(0, 0)[3], 0)


if __name__ == "__main__":
    unittest.main()


class StrokeInsideTest(unittest.TestCase):
    def test_rect_ring_matches_layers(self):
        from modules.common.shapes import stroke_inside
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 20, 20)
        cr = cairo.Context(surface)
        cr.set_antialias(cairo.ANTIALIAS_NONE)
        path = lambda c: c.rectangle(0, 0, 20, 20)
        stroke_inside(cr, path, path, (BLACK, WHITE))
        surface.flush()
        data, stride = surface.get_data(), surface.get_stride()
        px = lambda x, y: tuple(data[y * stride + 4 * x: y * stride + 4 * x + 4])
        self.assertEqual(px(10, 0), (0, 0, 0, 255))
        self.assertEqual(px(10, 1), (255, 255, 255, 255))
        self.assertEqual(px(10, 2)[3], 0)
        self.assertEqual(px(19, 10), (0, 0, 0, 255))
        self.assertEqual(px(18, 10), (255, 255, 255, 255))


def _surface(w, h):
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    cr = cairo.Context(surface)
    cr.set_antialias(cairo.ANTIALIAS_NONE)
    return surface, cr


def _reader(surface):
    surface.flush()
    data, stride = surface.get_data(), surface.get_stride()
    return lambda x, y: tuple(data[y * stride + 4 * x: y * stride + 4 * x + 4])


class AttachedOutlineTest(unittest.TestCase):
    def test_notch_has_no_outline_along_frame(self):
        from modules.common.shapes import notch_edge_path, notch_path, stroke_inside
        surface, cr = _surface(100, 60)
        stroke_inside(cr, lambda c: notch_path(c, 30, 70, 10, 40, 10),
                      lambda c: notch_edge_path(c, 30, 70, 10, 40, 10), (BLACK, WHITE))
        px = _reader(surface)
        self.assertEqual(px(50, 0)[3], 0)  # вдоль края экрана
        self.assertEqual(px(50, 49), (0, 0, 0, 255))  # низ: снаружи чёрный
        self.assertEqual(px(50, 48), (255, 255, 255, 255))  # внутри белый
        self.assertEqual(px(30, 30), (0, 0, 0, 255))  # бок
        self.assertEqual(px(31, 30), (255, 255, 255, 255))

    def test_corner_has_no_outline_along_frame(self):
        from modules.common.shapes import corner_edge_path, corner_path, stroke_inside
        surface, cr = _surface(100, 100)
        args = (100, 100, 50, 50, 10, 10, 10)
        stroke_inside(cr, lambda c: corner_path(c, *args), lambda c: corner_edge_path(c, *args), (BLACK, WHITE))
        px = _reader(surface)
        self.assertEqual(px(99, 70)[3], 0)  # правая рамка
        self.assertEqual(px(70, 99)[3], 0)  # нижняя рамка
        self.assertEqual(px(40, 70), (0, 0, 0, 255))  # свободный левый край
        self.assertEqual(px(41, 70), (255, 255, 255, 255))
        self.assertEqual(px(65, 40), (0, 0, 0, 255))  # свободный верхний край
        self.assertEqual(px(65, 41), (255, 255, 255, 255))


class SnapCenteredTest(unittest.TestCase):
    def test_integer_symmetric_ends(self):
        from modules.common.shapes import snap_centered
        self.assertEqual(snap_centered(100, 41), (30, 70))
        self.assertEqual(snap_centered(101, 40.4), (30, 71))
        x0, x1 = snap_centered(390, 233.7)
        self.assertEqual((x0 + x1, isinstance(x0, int)), (390, True))


class ThicknessTest(unittest.TestCase):
    def test_each_layer_gets_thickness(self):
        from modules.common.shapes import draw_outline, stroke_inside
        surface, cr = _surface(40, 40)
        path = lambda c: c.rectangle(0, 0, 40, 40)
        stroke_inside(cr, path, path, (BLACK, WHITE), 3)
        px = _reader(surface)
        self.assertEqual([px(20, y) for y in range(7)],
                         [(0, 0, 0, 255)] * 3 + [(255, 255, 255, 255)] * 3 + [(0, 0, 0, 0)])

        surface, cr = _surface(40, 40)
        draw_outline(cr, 40, 40, 0, (BLACK, WHITE), 2)
        px = _reader(surface)
        self.assertEqual([px(20, y) for y in range(5)],
                         [(0, 0, 0, 255)] * 2 + [(255, 255, 255, 255)] * 2 + [(0, 0, 0, 0)])
