import unittest

from modules.bar.workspaces import blend, plate_rect


class PlateTest(unittest.TestCase):
    def test_vertical_plate_keeps_gap_across(self):
        self.assertEqual(plate_rect((0, 30, 40, 20), 40, False, 5), (5, 30, 30, 20))

    def test_horizontal_plate_keeps_gap_across(self):
        self.assertEqual(plate_rect((30, 0, 14, 40), 40, True, 5), (30, 5, 14, 30))

    def test_shrink_keeps_center(self):
        self.assertEqual(plate_rect((0, 30, 40, 20), 40, False, 5, 3), (6.5, 31.5, 27, 17))

    def test_blend(self):
        self.assertEqual(blend((0, 0), (10, 20), 0.5), (5, 10))


if __name__ == "__main__":
    unittest.main()
