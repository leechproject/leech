import unittest

from modules.bar.tray_layout import clamp_scroll, fade_strengths, visible_length


class TrayLayoutTest(unittest.TestCase):
    def test_limit_counts_application_icons(self):
        self.assertEqual(visible_length([24] * 6, 6, 4), 4 * 24 + 3 * 6)
        self.assertEqual(visible_length([24] * 2, 6, 4), 2 * 24 + 6)

    def test_zero_limit_shows_everything(self):
        self.assertEqual(visible_length([24] * 6, 6, 0), 6 * 24 + 5 * 6)

    def test_empty(self):
        self.assertEqual(visible_length([], 6, 4), 0)

    def test_fades_follow_scroll_progress(self):
        self.assertEqual(fade_strengths(0, 100, 100, 5), (0.0, 0.0))
        self.assertEqual(fade_strengths(60, 200, 120, 5), (1.0, 1.0))
        self.assertEqual(fade_strengths(2.5, 200, 120, 5), (0.5, 1.0))
        self.assertEqual(fade_strengths(80, 200, 120, 5), (1.0, 0.0))

    def test_clamp(self):
        self.assertEqual(clamp_scroll(-5, 200, 120), 0.0)
        self.assertEqual(clamp_scroll(500, 200, 120), 80)
        self.assertEqual(clamp_scroll(10, 50, 120), 0.0)


if __name__ == "__main__":
    unittest.main()
