import unittest

from modules.notch.island import radius


class IslandRadiusTest(unittest.TestCase):
    def test_idle_is_a_pill(self):
        self.assertEqual(radius(35, 35, 90, 10), 17.5)

    def test_hiding_stays_a_pill(self):
        self.assertEqual(radius(10, 35, 90, 10), 5)

    def test_expanded_uses_the_notch_radius(self):
        self.assertEqual(radius(90, 35, 90, 10), 10)

    def test_radius_moves_smoothly(self):
        middle = radius(62.5, 35, 90, 10)
        self.assertAlmostEqual(middle, 13.75)

    def test_expanding_from_nothing(self):
        self.assertEqual(radius(90, 0, 90, 10), 10)


if __name__ == "__main__":
    unittest.main()
