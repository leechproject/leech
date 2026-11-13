import unittest

from modules.cc import net_layout as nl
from modules.cc import record_panel


class SizeTest(unittest.TestCase):
    def test_four_items_with_header_is_four_and_a_half_record_bars(self):
        self.assertEqual(nl.plate_height(10, True), round(4.5 * record_panel.PLATE_H))

    def test_height_follows_count_up_to_four(self):
        heights = [nl.plate_height(n, False) for n in (0, 1, 2, 4, 9)]
        self.assertEqual(heights[0], heights[1])
        self.assertLess(heights[1], heights[2])
        self.assertEqual(heights[3], heights[4])
        self.assertEqual(nl.plate_height(1, False), nl.PAD + nl.ITEM_H + nl.PAD)

    def test_list_shows_exactly_four(self):
        view = nl.list_height(10)
        self.assertEqual(view, 4 * nl.ITEM_H + 3 * nl.PAD)
        self.assertEqual(nl.hit(view - 1, 0, 10, None, 0), ("row", 3))


class ScrollTest(unittest.TestCase):
    def test_scroll_to_show_last(self):
        view = nl.list_height(10)
        scroll = nl.scroll_to_show(0, 9, 10, None, 0, view)
        self.assertEqual(scroll, nl.content_height(10, None, 0) - view)
        self.assertEqual(nl.scroll_to_show(scroll, 0, 10, None, 0, view), 0)

    def test_clamp(self):
        view = nl.list_height(3)
        self.assertEqual(nl.clamp_scroll(500, 3, None, 0, view), 0)
        self.assertEqual(nl.clamp_scroll(-5, 10, None, 0, nl.list_height(10)), 0)

    def test_menu_pushes_rows(self):
        extra = nl.menu_extra(3)
        self.assertEqual(nl.row_top(2, 1, 3), 2 * nl.PITCH + extra)
        self.assertEqual(nl.row_top(1, 1, 3), nl.PITCH)
        top = nl.menu_top(1)
        self.assertEqual(nl.hit(top + nl.MENU_EDGE + 1, 0, 5, 1, 3), ("menu", 0))
        self.assertEqual(nl.hit(nl.row_top(2, 1, 3) + 1, 0, 5, 1, 3), ("row", 2))
        self.assertIsNone(nl.hit(nl.ITEM_H + 1, 0, 5, None, 0))


class ViewTest(unittest.TestCase):
    def test_menu_grows_short_list_up_to_four_slots(self):
        self.assertEqual(nl.view_height(1, None, 0), nl.list_height(1))
        self.assertEqual(nl.view_height(1, 0, 2), min(nl.list_height(4), nl.ITEM_H + nl.menu_extra(2)))
        self.assertEqual(nl.view_height(10, 0, 3), nl.list_height(4))


if __name__ == "__main__":
    unittest.main()
