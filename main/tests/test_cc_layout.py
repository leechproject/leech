import unittest

from modules.cc.layout import Metrics, Place, controls, order_groups, split
from modules.config.values import Position

M = Metrics(width=250, gap=6, small=58, wide_h=52)
RL, RR = Position("rhalf", "left"), Position("rhalf", "right")
SLIDERS = [("brightness", RL), ("volume", RR)]


def by_key(places):
    return {p.key: (p.x, p.y, p.w, p.h) for p in places}


class LayoutTest(unittest.TestCase):
    def test_split(self):
        self.assertEqual(split(250, 2, 6), [122, 122])
        self.assertEqual(split(10, 3, 0), [4, 3, 3])
        self.assertEqual(split(10, 0, 6), [])

    def test_default_matches_current_build(self):
        groups = order_groups([("row1", ["wifi", "bluetooth"]), ("row2", ["caffeine", "dnd"]),
                               ("row3", ["screenshot", "record"])], {"row1": 1, "row2": 3}, SLIDERS, 2)
        places, height = controls(groups, M)
        self.assertEqual(by_key(places), {
            "wifi": (0, 0, 122, 52), "bluetooth": (128, 0, 122, 52),
            "brightness": (128, 58, 58, 122), "volume": (192, 58, 58, 122),
            "caffeine": (0, 58, 58, 58), "dnd": (64, 58, 58, 58),
            "screenshot": (0, 122, 58, 58), "record": (64, 122, 58, 58),
        })
        self.assertEqual(height, 180)

    def test_hidden_bluetooth_stretches_wifi(self):
        places, _ = controls([("row", ["wifi"])], M)
        self.assertEqual(by_key(places)["wifi"], (0, 0, 250, 52))

    def test_hidden_volume_moves_brightness_to_edge(self):
        places, _ = controls([("sliders", [("brightness", RL)]), ("row", ["caffeine", "dnd"]),
                              ("row", ["screenshot", "record"])], M)
        got = by_key(places)
        self.assertEqual(got["brightness"], (192, 0, 58, 122))
        self.assertEqual(got["caffeine"], (0, 0, 90, 58))
        self.assertEqual(got["dnd"], (96, 0, 90, 58))

    def test_sliders_first_shrinks_row1_to_squares(self):
        groups = order_groups([("row1", ["wifi", "bluetooth"]), ("row2", ["caffeine", "dnd"]),
                               ("row3", ["screenshot", "record"])], {"row1": 2, "row2": 3}, SLIDERS, 1)
        places, height = controls(groups, M)
        got = by_key(places)
        self.assertEqual(got["wifi"], (0, 0, 58, 58))
        self.assertEqual(got["caffeine"], (0, 64, 58, 58))
        self.assertEqual(got["screenshot"], (0, 128, 122, 52))
        self.assertEqual(height, 180)

    def test_single_row_beside_sliders_takes_full_height(self):
        places, _ = controls([("sliders", SLIDERS), ("row", ["a"])], M)
        self.assertEqual(by_key(places)["a"], (0, 0, 122, 122))

    def test_left_half_sliders(self):
        sliders = [("brightness", Position("lhalf", "left")), ("volume", RR)]
        places, _ = controls([("sliders", sliders), ("row", ["a", "b"])], M)
        got = by_key(places)
        self.assertEqual(got["brightness"], (0, 0, 58, 122))
        self.assertEqual(got["volume"], (192, 0, 58, 122))
        self.assertEqual(got["a"], (64, 0, 58, 122))

    def test_horizontal_sliders_full_width(self):
        sliders = [("volume", Position("full", "top")), ("brightness", Position("full", "bottom"))]
        places, height = controls([("row", ["wifi"]), ("sliders", sliders)], M, horizontal=True)
        got = by_key(places)
        self.assertEqual(got["volume"], (0, 58, 250, 58))
        self.assertEqual(got["brightness"], (0, 122, 250, 58))
        self.assertEqual(height, 180)

    def test_empty_groups_are_skipped(self):
        places, height = controls([("row", []), ("sliders", []), ("row", ["a"])], M)
        self.assertEqual(places, [Place("a", 0, 0, 250, 52)])
        self.assertEqual(height, 52)

    def test_unprioritized_rows_follow_in_order(self):
        groups = order_groups([("row1", ["a"]), ("row2", ["b"]), ("row4", ["d"]), ("row3", ["c"])],
                              {"row1": 1, "row2": 3}, [], 2)
        self.assertEqual([items for _, items in groups if items], [["a"], ["b"], ["d"], ["c"]])


if __name__ == "__main__":
    unittest.main()
