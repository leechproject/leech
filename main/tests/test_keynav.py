import unittest

from modules.cc import keynav
from modules.cc import layout


class KeynavTest(unittest.TestCase):
    # Default CC: vertical sliders at both sides, two rows of two buttons between them,
    # wide row of two buttons below.
    def setUp(self):
        m = layout.Metrics(250, 6, 58, 50)
        groups = [("row", ["wifi", "bluetooth"]), ("sliders", []), ("row", ["caffeine", "dnd"]),
                  ("row", ["screenshot", "record"])]
        places, _ = layout.controls(groups, m)
        self.keys = [p.key for p in places]
        self.rects = [(p.x, p.y, p.w, p.h) for p in places]

    def go(self, key, direction):
        index = keynav.step(self.rects, self.keys.index(key), direction)
        return None if index is None else self.keys[index]

    def test_rows(self):
        self.assertEqual(self.go("wifi", "right"), "bluetooth")
        self.assertEqual(self.go("bluetooth", "left"), "wifi")
        self.assertEqual(self.go("wifi", "down"), "caffeine")
        self.assertEqual(self.go("bluetooth", "down"), "dnd")
        self.assertEqual(self.go("caffeine", "down"), "screenshot")
        self.assertEqual(self.go("record", "up"), "dnd")

    def test_edges(self):
        self.assertIsNone(self.go("wifi", "up"))
        self.assertIsNone(self.go("wifi", "left"))
        self.assertIsNone(self.go("record", "down"))

    def test_overlap_beats_distance(self):
        rects = [(0, 0, 10, 10), (0, 100, 10, 10), (50, 20, 10, 10)]
        self.assertEqual(keynav.step(rects, 0, "down"), 1)


if __name__ == "__main__":
    unittest.main()
