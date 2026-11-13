import unittest

import gi

gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf

from modules.wallpapers.wallpaper import blurred_pixbuf


class BlurTest(unittest.TestCase):
    def test_size_kept_and_edges_softened(self):
        source = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 101, 64)
        source.fill(0x000000FF)
        source.new_subpixbuf(50, 0, 51, 64).fill(0xFFFFFFFF)
        result = blurred_pixbuf(source, 3)
        self.assertEqual((result.get_width(), result.get_height()), (101, 64))
        pixels = result.get_pixels()
        middle = pixels[32 * result.get_rowstride() + 50 * result.get_n_channels()]
        self.assertTrue(20 < middle < 235, middle)

    def test_zero_levels_is_identity_size(self):
        source = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 7, 5)
        self.assertEqual(blurred_pixbuf(source, 0).get_width(), 7)


if __name__ == "__main__":
    unittest.main()
