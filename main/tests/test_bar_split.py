import unittest

from modules.bar.split import gap, pieces
from modules.bar.squeeze import child_rect


class SplitTest(unittest.TestCase):
    def test_gap_keeps_spacing_from_notch(self):
        self.assertEqual(gap(370), 380)
        self.assertEqual(gap(0), 0)
        self.assertEqual(gap(0.4), 0)

    def test_without_notch_substrate_is_whole(self):
        self.assertEqual(pieces(5, 1910, 960, 0), [(5, 1910)])

    def test_substrate_splits_around_center(self):
        self.assertEqual(pieces(5, 1910, 960, 380), [(5, 765), (1150, 765)])

    def test_huge_gap_leaves_nothing(self):
        self.assertEqual(pieces(5, 100, 50, 300), [])


class SqueezeTest(unittest.TestCase):
    def test_start_child_keeps_left_edge(self):
        self.assertEqual(child_rect(10, 100, 300, False), (10, 300))

    def test_end_child_keeps_right_edge(self):
        self.assertEqual(child_rect(10, 100, 300, True), (-190, 300))
        self.assertEqual(child_rect(10, 400, 300, True), (110, 300))


if __name__ == "__main__":
    unittest.main()
