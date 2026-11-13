import unittest

from modules.bar.numerals import chinese, roman, workspace_label, workspace_symbol


class NumeralsTest(unittest.TestCase):
    def test_symbol_falls_back_to_numeral(self):
        icons = {"empty": None, "occupied": "\uf111", "active": "\uf111"}
        self.assertEqual(workspace_symbol(3, "empty", "roman", icons), "III")
        self.assertEqual(workspace_symbol(3, "occupied", "roman", icons), "\uf111")
        self.assertEqual(workspace_symbol(3, "active", "digit", {}), "3")

    def test_roman(self):
        self.assertEqual([roman(n) for n in (1, 4, 9, 10, 14, 40, 99, 100)],
                         ["I", "IV", "IX", "X", "XIV", "XL", "XCIX", "C"])

    def test_chinese(self):
        self.assertEqual([chinese(n) for n in (1, 9, 10, 11, 20, 21, 99, 100, 101, 110)],
                         ["一", "九", "十", "十一", "二十", "二十一", "九十九", "一百", "一百〇一", "一百一十"])

    def test_digit(self):
        self.assertEqual(workspace_label(7, "digit"), "7")
        self.assertEqual(workspace_label(7, "roman"), "VII")
        self.assertEqual(workspace_label(7, "chinese"), "七")


if __name__ == "__main__":
    unittest.main()
