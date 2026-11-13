import time
import unittest

from gi.repository import GLib

from fabric.system_tray.service import SystemTrayItemPixmap

from modules.bar import tray_compat


def pixmaps(*sizes):
    entries = []
    for width, height in sizes:
        data = bytes((i * 7 + width) % 256 for i in range(4 * width * height))
        entries.append((width, height, data))
    return GLib.Variant("a(iiay)", entries)


def slow_argb_to_rgba(data, width, height):
    out = bytearray(data)
    for i in range(0, 4 * width * height, 4):
        alpha = out[i]
        out[i], out[i + 1], out[i + 2], out[i + 3] = out[i + 1], out[i + 2], out[i + 3], alpha
    return out[:4 * width * height]


class LargestPixmapTest(unittest.TestCase):
    def test_matches_unpack(self):
        variant = pixmaps((16, 16), (64, 64), (22, 22))
        expected = max(variant.unpack(), key=lambda p: p[0])
        (width, height, data), = tray_compat.largest_pixmap(variant)
        self.assertEqual((width, height), (64, 64))
        self.assertEqual(bytes(data), bytes(expected[2]))
        self.assertIsInstance(data, bytearray)

    def test_equal_widths_take_last(self):
        variant = GLib.Variant("a(iiay)", [(8, 8, b"\x01" * 256), (8, 8, b"\x02" * 256)])
        self.assertEqual(tray_compat.largest_pixmap(variant)[0][2][0], 2)

    def test_empty(self):
        self.assertEqual(tray_compat.largest_pixmap(GLib.Variant("a(iiay)", [])), [])

    def test_large_icon_faster_than_unpack(self):
        data = GLib.Variant.new_from_bytes(GLib.VariantType("ay"), GLib.Bytes.new(bytes(4 * 128 * 128)), True)
        entry = GLib.Variant.new_tuple(GLib.Variant("i", 128), GLib.Variant("i", 128), data)
        built = GLib.Variant.new_array(None, [entry])
        variant = GLib.Variant.new_from_bytes(GLib.VariantType("a(iiay)"), built.get_data_as_bytes(), False)
        started = time.monotonic()
        tray_compat.largest_pixmap(variant)
        fast = time.monotonic() - started
        started = time.monotonic()
        variant.unpack()
        slow = time.monotonic() - started
        self.assertLess(fast * 20, slow)


class ArgbTest(unittest.TestCase):
    def test_matches_original_loop(self):
        data = bytes(range(256)) * 4
        self.assertEqual(tray_compat.argb_to_rgba(data, 16, 4), slow_argb_to_rgba(data, 16, 4))

    def test_extra_bytes_ignored(self):
        data = bytes(range(20))
        self.assertEqual(tray_compat.argb_to_rgba(data, 2, 2), slow_argb_to_rgba(data, 2, 2))

    def test_short_or_empty(self):
        self.assertIsNone(tray_compat.argb_to_rgba(b"\x00" * 8, 2, 2))
        self.assertIsNone(tray_compat.argb_to_rgba(b"", 0, 0))


class AsPixbufTest(unittest.TestCase):
    def setUp(self):
        tray_compat.install()

    def test_pixbuf(self):
        pixmap = SystemTrayItemPixmap(2, 1, bytearray(b"\xff\x10\x20\x30\x80\x01\x02\x03"))
        pixbuf = pixmap.as_pixbuf()
        self.assertEqual((pixbuf.get_width(), pixbuf.get_height()), (2, 1))
        self.assertEqual(pixbuf.get_pixels()[:8], b"\x10\x20\x30\xff\x01\x02\x03\x80")
        self.assertEqual(pixmap.as_pixbuf(size=8).get_width(), 8)

    def test_missing(self):
        self.assertIsNone(SystemTrayItemPixmap().as_pixbuf())


if __name__ == "__main__":
    unittest.main()
