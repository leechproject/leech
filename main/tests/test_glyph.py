import unittest
from collections import namedtuple

from modules.common.glyph import ink_origin

Rect = namedtuple("Rect", "x y width height")


class InkOriginTest(unittest.TestCase):
    def test_overflowing_advance(self):
        self.assertEqual(ink_origin(Rect(0, 6, 26, 18), 0, 0, 80, 60), (27, 15))

    def test_negative_bearing(self):
        self.assertEqual(ink_origin(Rect(-1, 2, 26, 20), 0, 0, 80, 60), (28, 18))

    def test_center_point(self):
        x, y = ink_origin(Rect(3, 4, 10, 10), 50, 20, 0, 0)
        self.assertEqual((x + 3 + 5, y + 4 + 5), (50, 20))


if __name__ == "__main__":
    unittest.main()
