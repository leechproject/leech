import unittest

from modules.common import dock_items as di


class ResolveTest(unittest.TestCase):
    def setUp(self):
        self.index = di.build_index([
            ("org.wezfurlong.wezterm.desktop", None, "/usr/bin/wezterm-gui"),
            ("Happ.desktop", None, "happ"),
            ("firefox.desktop", "firefox", "firefox"),
            ("code.desktop", "Code", "/usr/bin/code"),
        ])

    def test_desktop_id(self):
        self.assertEqual(di.resolve("org.wezfurlong.wezterm", self.index), "org.wezfurlong.wezterm.desktop")
        self.assertEqual(di.resolve("Happ", self.index), "Happ.desktop")

    def test_wm_class_and_case(self):
        self.assertEqual(di.resolve("Code", self.index), "code.desktop")
        self.assertEqual(di.resolve("FIREFOX", self.index), "firefox.desktop")

    def test_last_component(self):
        self.assertEqual(di.resolve("wezterm", self.index), "org.wezfurlong.wezterm.desktop")

    def test_unknown(self):
        self.assertIsNone(di.resolve("nothing", self.index))
        self.assertIsNone(di.resolve("", self.index))


class ArrangeTest(unittest.TestCase):
    def test_counts_all_windows(self):
        _, counts = di.arrange(["a.desktop"], ["a.desktop", "b.desktop", "a.desktop"], False)
        self.assertEqual(counts["a.desktop"], 2)
        self.assertEqual(counts["b.desktop"], 1)

    def test_launched_newest_last_without_pinned(self):
        launched, _ = di.arrange(["a.desktop"], ["b.desktop", "a.desktop", "c.desktop", "b.desktop"], True)
        self.assertEqual(launched, ["c.desktop", "b.desktop"])

    def test_launched_off(self):
        self.assertEqual(di.arrange([], ["b.desktop"], False)[0], [])


class OffsetsTest(unittest.TestCase):
    def test_plain_dock_matches_old_width(self):
        _, separator, width = di.offsets(0, 5, 8, 24, 8)
        self.assertIsNone(separator)
        self.assertEqual(width, 2 * 8 + 5 * 24 + 4 * 8)

    def test_separator_between_groups(self):
        positions, separator, width = di.offsets(2, 3, 8, 24, 8)
        self.assertEqual(positions[:3], [8, 40, 81])
        self.assertEqual(separator, 72)
        self.assertEqual(width, 2 * 8 + 5 * 24 + 4 * 8 + 1 + 8)

    def test_only_launched_no_separator(self):
        self.assertIsNone(di.offsets(2, 0, 8, 24, 8)[1])

    def test_empty(self):
        self.assertEqual(di.offsets(0, 0, 8, 24, 8), ([], None, 0))


class DotsTest(unittest.TestCase):
    def test_centered(self):
        self.assertEqual(di.dot_offsets(1, 24), [10.5])
        self.assertEqual(di.dot_offsets(2, 24), [8.0, 13.0])

    def test_fit_under_icon(self):
        dots = di.dot_offsets(20, 24)
        self.assertEqual(len(dots), 5)
        self.assertGreaterEqual(dots[0], 0)
        self.assertLessEqual(dots[-1] + di.DOT, 24)


class MarksTest(unittest.TestCase):
    def test_dots_above_in_a_top_dock(self):
        self.assertEqual(di.dot_top(8, 24, False), 8 + 24 + 5)
        self.assertEqual(di.dot_top(8, 24, True), 8 - 5 - 3)

    def test_separator_on_whole_output_pixels(self):
        x, w = di.snap_line(100.5, 1.5)
        self.assertAlmostEqual(x * 1.5, round(x * 1.5))
        self.assertAlmostEqual(w * 1.5, 2)
        self.assertEqual(di.snap_line(100, None), (100, 1))
        x, w = di.snap_line(100, 2)
        self.assertEqual((x, w), (100, 1))

    def test_separator_covers_whole_buffer_pixels(self):
        x, w = di.snap_line(576, 1.5, 2)
        self.assertEqual((x * 2, (x + w) * 2), (1152, 1155))


if __name__ == "__main__":
    unittest.main()
