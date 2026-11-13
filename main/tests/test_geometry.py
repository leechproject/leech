import unittest

from modules.config.geometry import bar_band, bar_detached, bar_gap, frame_sides, is_horizontal, snap_inset, visible_frame

FRAME = {"left": 9, "top": 9, "right": 9, "bottom": 9}


class FrameSidesTest(unittest.TestCase):
    def test_bar_replaces_its_side(self):
        sides = frame_sides(FRAME, True, "left", 60, True)
        self.assertEqual(sides, {"left": 60, "top": 9, "right": 9, "bottom": 9})

    def test_bar_on_every_side(self):
        for side in ("top", "right", "bottom"):
            sides = frame_sides(FRAME, True, side, 40, True)
            self.assertEqual(sides[side], 40)
            self.assertEqual(sides["left"], 9)

    def test_without_include_bar_bar_sits_past_frame_and_gap(self):
        sides = frame_sides(FRAME, True, "top", 40, False)
        self.assertEqual(sides["top"], 9 + 5 + 40)
        self.assertEqual(visible_frame(FRAME, True, "top", 40, False), FRAME)
        self.assertEqual(bar_band(FRAME, True, "top", 40, False), (9, 54))

    def test_include_bar_band_starts_at_screen_edge(self):
        self.assertEqual(visible_frame(FRAME, True, "left", 60, True)["left"], 60)
        self.assertEqual(bar_band(FRAME, True, "left", 60, True), (0, 60))

    def test_undercover_keeps_taskbar_at_screen_edge(self):
        self.assertEqual(frame_sides(FRAME, True, "bottom", 40, False, undercover=True)["bottom"], 49)
        self.assertEqual(bar_band(FRAME, True, "bottom", 40, False, undercover=True), (0, 40))

    def test_frame_disabled(self):
        self.assertEqual(frame_sides(FRAME, False, "bottom", 40, True),
                         {"left": 0, "top": 0, "right": 0, "bottom": 40})

    def test_frame_disabled_detached_bar_keeps_gap_from_screen_edge(self):
        self.assertEqual(frame_sides(FRAME, False, "bottom", 40, False)["bottom"], 45)
        self.assertEqual(visible_frame(FRAME, False, "bottom", 40, False),
                         {"left": 0, "top": 0, "right": 0, "bottom": 0})
        self.assertEqual(bar_band(FRAME, False, "bottom", 40, False), (0, 45))

    def test_split_include_bar_keeps_own_frame_without_gap(self):
        self.assertEqual(frame_sides(FRAME, True, "left", 60, True, split=True)["left"], 9 + 60)
        self.assertEqual(visible_frame(FRAME, True, "left", 60, True, split=True), FRAME)
        self.assertEqual(bar_band(FRAME, True, "left", 60, True, split=True), (9, 69))
        self.assertTrue(bar_detached(True, "left", True, split=True))
        self.assertEqual(bar_gap(True, "left", True, split=True), 0)

    def test_split_without_include_bar_matches_detached(self):
        self.assertEqual(frame_sides(FRAME, True, "top", 40, False, split=True),
                         frame_sides(FRAME, True, "top", 40, False))
        self.assertEqual(bar_band(FRAME, True, "top", 40, False, split=True), (9, 54))
        self.assertEqual(bar_gap(True, "top", False, split=True), 5)

    def test_split_ignored_in_undercover(self):
        self.assertFalse(bar_detached(True, "bottom", True, undercover=True, split=True))
        self.assertEqual(bar_band(FRAME, True, "bottom", 40, True, undercover=True, split=True), (0, 40))

    def test_split_frame_disabled_bar_at_screen_edge(self):
        self.assertEqual(frame_sides(FRAME, False, "left", 60, True, split=True)["left"], 60)
        self.assertEqual(bar_band(FRAME, False, "left", 60, True, split=True), (0, 60))

    def test_bar_disabled(self):
        self.assertEqual(frame_sides(FRAME, True, None, 60, True), FRAME)

    def test_orientation(self):
        self.assertTrue(is_horizontal("top"))
        self.assertTrue(is_horizontal("bottom"))
        self.assertFalse(is_horizontal("left"))
        self.assertFalse(is_horizontal(None))


class SnapInsetTest(unittest.TestCase):
    def test_integer_scale_keeps_value(self):
        self.assertEqual(snap_inset(9, 1), 9)
        self.assertEqual(snap_inset(9, 2), 9)

    def test_unknown_scale_keeps_value(self):
        self.assertEqual(snap_inset(9, None), 9)

    def test_fractional_scale_covers_the_partial_pixel(self):
        self.assertAlmostEqual(snap_inset(9, 1.5) * 1.5, 14)
        self.assertAlmostEqual(snap_inset(9, 1.25) * 1.25, 12)

    def test_fractional_scale_also_aligns_to_the_buffer(self):
        self.assertEqual(snap_inset(9, 1.5, 2), 9.5)
        self.assertEqual(snap_inset(60, 1.5, 2), 60)

    def test_aligned_edges_untouched(self):
        self.assertEqual(snap_inset(60, 1.5), 60)
        self.assertEqual(snap_inset(0, 1.5), 0)


if __name__ == "__main__":
    unittest.main()


class AttachedEdgeSlideTest(unittest.TestCase):
    def test_toward_edge(self):
        from modules.common.edge import AttachedEdge
        top, bottom = AttachedEdge(True), AttachedEdge(False)
        self.assertEqual(top.toward(30), -30)
        self.assertEqual(bottom.toward(30), 30)
