import unittest

from modules.bar.taskbar_layout import group_start, fade_strength, grid_cell, grid_size, window_left


class GroupStartTest(unittest.TestCase):
    def test_centered_on_the_screen(self):
        self.assertEqual(group_start(1280, 1100, 200, False), 540)

    def test_pushed_left_by_static_items(self):
        self.assertEqual(group_start(1280, 800, 600, False), 200)

    def test_overflow_starts_at_zero(self):
        self.assertEqual(group_start(1280, 800, 1000, False), 0)

    def test_left_mode(self):
        self.assertEqual(group_start(1280, 1100, 200, True), 0)


class FadeTest(unittest.TestCase):
    def test_no_fade_when_everything_fits(self):
        self.assertEqual(fade_strength(0, 500, 500, 8), 0.0)

    def test_full_fade_with_hidden_content(self):
        self.assertEqual(fade_strength(0, 900, 500, 8), 1.0)

    def test_partial_near_the_end(self):
        self.assertEqual(fade_strength(396, 900, 500, 8), 0.5)


class TrayGridTest(unittest.TestCase):
    def test_four_in_a_row(self):
        self.assertEqual(grid_cell(5, 4), (1, 1))

    def test_size(self):
        self.assertEqual(grid_size(0, 4, 24, 6), (0, 0))
        self.assertEqual(grid_size(2, 4, 24, 6), (66, 36))
        self.assertEqual(grid_size(5, 4, 24, 6), (126, 66))

    def test_window_centered_on_the_button(self):
        self.assertEqual(window_left(600, 126, 1280, 5), 537)

    def test_window_stays_on_screen(self):
        self.assertEqual(window_left(1250, 126, 1280, 5), 1149)
        self.assertEqual(window_left(20, 126, 1280, 5), 5)


if __name__ == "__main__":
    unittest.main()
