import unittest

from modules.wallpapers import picker_layout as pl


def full_hd():
    return pl.compute(1920, 1080, 60, 9, 9, 9, margin=25, pad=8, gap=8, cols=5)


class ComputeTest(unittest.TestCase):
    def test_full_hd_geometry(self):
        layout = full_hd()
        self.assertEqual((layout.x0, layout.x1, layout.body_h), (85, 1886, 1037))
        self.assertEqual((layout.cell_w, layout.cell_h), (350, 197))
        self.assertEqual((layout.cols, layout.rows), (5, 5))
        self.assertEqual((layout.grid_x, layout.grid_y), (94, 44))

    def test_cell_keeps_screen_aspect(self):
        layout = full_hd()
        self.assertAlmostEqual(layout.cell_w / layout.cell_h, 1920 / 1080, places=1)


class CellTest(unittest.TestCase):
    def setUp(self):
        self.layout = full_hd()

    def test_cell_rect(self):
        self.assertEqual(pl.cell_rect(self.layout, 0, 0), (94, 44, 350, 197))
        self.assertEqual(pl.cell_rect(self.layout, 6, 0), (94 + 358, 44 + 205, 350, 197))
        self.assertEqual(pl.cell_rect(self.layout, 6, 1), (94 + 358, 44, 350, 197))

    def test_cell_at(self):
        self.assertEqual(pl.cell_at(self.layout, 94, 44, 0, 25), 0)
        self.assertEqual(pl.cell_at(self.layout, 94 + 358 + 1, 44 + 205 + 1, 0, 25), 6)
        self.assertEqual(pl.cell_at(self.layout, 94 + 358 + 1, 44 + 1, 1, 25), 6)

    def test_cell_at_misses(self):
        self.assertIsNone(pl.cell_at(self.layout, 93, 44, 0, 25))
        self.assertIsNone(pl.cell_at(self.layout, 94 + 351, 44, 0, 25))
        self.assertIsNone(pl.cell_at(self.layout, 94 + 358, 44, 0, 1))


class ScrollTest(unittest.TestCase):
    def setUp(self):
        self.layout = full_hd()

    def test_max_top_row(self):
        self.assertEqual(pl.max_top_row(self.layout, 25), 0)
        self.assertEqual(pl.max_top_row(self.layout, 26), 1)

    def test_clamp(self):
        self.assertEqual(pl.clamp_top_row(self.layout, -3, 40), 0)
        self.assertEqual(pl.clamp_top_row(self.layout, 9, 40), 3)

    def test_scroll_to_show(self):
        self.assertEqual(pl.scroll_to_show(self.layout, 0, 25, 26), 1)
        self.assertEqual(pl.scroll_to_show(self.layout, 1, 0, 26), 0)
        self.assertEqual(pl.scroll_to_show(self.layout, 0, 12, 26), 0)


class MoveTest(unittest.TestCase):
    def setUp(self):
        self.layout = full_hd()

    def test_horizontal(self):
        self.assertEqual(pl.move(self.layout, 0, "left", 12), 0)
        self.assertEqual(pl.move(self.layout, 4, "right", 12), 5)
        self.assertEqual(pl.move(self.layout, 11, "right", 12), 11)

    def test_vertical(self):
        self.assertEqual(pl.move(self.layout, 2, "up", 12), 2)
        self.assertEqual(pl.move(self.layout, 7, "up", 12), 2)
        self.assertEqual(pl.move(self.layout, 2, "down", 12), 7)
        self.assertEqual(pl.move(self.layout, 8, "down", 12), 11)
        self.assertEqual(pl.move(self.layout, 11, "down", 12), 11)

    def test_jumps(self):
        self.assertEqual(pl.move(self.layout, 7, "home", 12), 0)
        self.assertEqual(pl.move(self.layout, 0, "end", 12), 11)
        self.assertEqual(pl.move(self.layout, 0, "pgdn", 60), 25)
        self.assertEqual(pl.move(self.layout, 30, "pgup", 60), 5)
        self.assertEqual(pl.move(self.layout, 3, "unknown", 12), 3)


class PickerRowsTest(unittest.TestCase):
    def test_rows_come_from_the_config(self):
        for rows in (1, 3, 5, 7):
            layout = pl.compute(1280, 720, 60, 9, 9, 9, 25, 8, 8, 5, rows=rows)
            self.assertEqual(layout.rows, rows)
            inner_h = layout.body_h - 2 * 8
            self.assertLessEqual(rows * layout.cell_h + (rows - 1) * 8, inner_h)
            self.assertGreater((rows + 1) * layout.cell_h + rows * 8, inner_h)


class PickerFromTopTest(unittest.TestCase):
    def test_spacing_moves_to_the_free_side(self):
        args = (1280, 720, 60, 9, 9, 9, (25, 25, 25), 8, 8, 5)
        bottom = pl.compute(*args)
        top = pl.compute(*args, from_top=True)
        self.assertEqual(top.body_h, bottom.body_h)
        self.assertEqual(top.grid_y, bottom.grid_y - 25)
        self.assertEqual((top.cell_w, top.cell_h, top.rows), (bottom.cell_w, bottom.cell_h, bottom.rows))


if __name__ == "__main__":
    unittest.main()
