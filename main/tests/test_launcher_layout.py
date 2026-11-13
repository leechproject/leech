import unittest
from collections import namedtuple

from modules.launcher import launcher_layout as ll

Entry = namedtuple("Entry", "id name")


class WidthTest(unittest.TestCase):
    def test_dock_width(self):
        self.assertEqual(ll.dock_width(0), 0)
        self.assertEqual(ll.dock_width(1), 40)
        self.assertEqual(ll.dock_width(10), 328)
        self.assertEqual(ll.dock_width(16), 520)

    def test_launcher_width_has_dock_minimum(self):
        self.assertEqual(ll.launcher_width(0), ll.dock_width(9))
        self.assertEqual(ll.launcher_width(3), ll.dock_width(9))
        self.assertEqual(ll.launcher_width(9), ll.dock_width(9))
        self.assertEqual(ll.launcher_width(12), ll.dock_width(12))

    def test_text_visibility(self):
        self.assertTrue(ll.shows_text(328))
        self.assertFalse(ll.shows_text(40))


class GeometryTest(unittest.TestCase):
    def test_menu_constants(self):
        self.assertEqual(ll.MENU_ITEM_H, 26)
        self.assertEqual(ll.MENU_H, 98)
        self.assertEqual(ll.MENU_EXTRA, 102)

    def test_row_top(self):
        self.assertEqual(ll.row_top(3, None), 114)
        self.assertEqual(ll.row_top(1, 1), 38)
        self.assertEqual(ll.row_top(3, 1), 114 + 102)

    def test_content_height(self):
        self.assertEqual(ll.content_height(0, None), 0)
        self.assertEqual(ll.content_height(5, None), 186)
        self.assertEqual(ll.content_height(5, 2), 186 + 102)

    def test_scroll(self):
        self.assertEqual(ll.clamp_scroll(500, 5, None, 100), 86)
        self.assertEqual(ll.clamp_scroll(-5, 5, None, 100), 0)
        self.assertEqual(ll.scroll_to_show(0, 4, 5, None, 100), 86)
        self.assertEqual(ll.scroll_to_show(86, 0, 5, None, 100), 0)


class HitTest(unittest.TestCase):
    def test_rows(self):
        self.assertEqual(ll.hit(0, 0, 5, None), ("row", 0))
        self.assertIsNone(ll.hit(36, 0, 5, None))
        self.assertEqual(ll.hit(38, 0, 5, None), ("row", 1))
        self.assertEqual(ll.hit(0, 38, 5, None), ("row", 1))
        self.assertIsNone(ll.hit(-1, 0, 5, None))
        self.assertIsNone(ll.hit(5 * 38, 0, 5, None))

    def test_menu(self):
        self.assertEqual(ll.hit(38 + 5, 0, 5, 0), ("menu", 0))
        self.assertEqual(ll.hit(38 + 5 + 31, 0, 5, 0), ("menu", 1))
        self.assertIsNone(ll.hit(38 + 5 + 27, 0, 5, 0))
        self.assertIsNone(ll.hit(38 + 99, 0, 5, 0))
        self.assertEqual(ll.hit(38 + 102, 0, 5, 0), ("row", 1))


class MoveTest(unittest.TestCase):
    def test_move(self):
        self.assertEqual(ll.move(0, "up", 10, 4), 0)
        self.assertEqual(ll.move(9, "down", 10, 4), 9)
        self.assertEqual(ll.move(2, "pgdn", 10, 4), 6)
        self.assertEqual(ll.move(2, "pgup", 10, 4), 0)
        self.assertEqual(ll.move(5, "end", 10, 4), 9)


class BuildRowsTest(unittest.TestCase):
    def setUp(self):
        self.entries = [Entry("a", "Firefox"), Entry("b", "GNOME Files"),
                        Entry("c", "Files Manager"), Entry("d", "Terminal")]

    def ids(self, query="", liked=(), hidden=(), show_hidden=False):
        return [e.id for e in ll.build_rows(self.entries, query, list(liked), set(hidden), show_hidden)]

    def test_no_query_keeps_order(self):
        self.assertEqual(self.ids(), ["a", "b", "c", "d"])

    def test_ranking(self):
        self.assertEqual(self.ids("fi"), ["a", "c", "b"])
        self.assertEqual(self.ids("  FI "), ["a", "c", "b"])
        self.assertEqual(self.ids("inal"), ["d"])
        self.assertEqual(self.ids("zzz"), [])

    def test_latest_like_first(self):
        self.assertEqual(self.ids(liked=["a", "d"]), ["d", "a", "b", "c"])

    def test_hidden(self):
        self.assertEqual(self.ids(hidden=["b"]), ["a", "c", "d"])
        self.assertEqual(self.ids(hidden=["b"], show_hidden=True), ["a", "b", "c", "d"])


if __name__ == "__main__":
    unittest.main()
