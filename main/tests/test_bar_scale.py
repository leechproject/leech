import unittest

from modules.bar.scale import scaled_css
from modules.config.geometry import bar_scale, scaled


class BarScaleTest(unittest.TestCase):
    def test_factor_is_relative_to_sixty(self):
        self.assertEqual(bar_scale(60), 1)
        self.assertEqual(bar_scale(90), 1.5)

    def test_scaled_rounds_down_so_parts_never_outgrow_the_bar(self):
        self.assertEqual(scaled(5, 1.5), 7)
        self.assertEqual(scaled(3, 1.1), 3)
        parts = (5, 5, 40, 5, 5)
        for width in (45, 61, 75, 90, 100):
            scale = bar_scale(width)
            self.assertLessEqual(sum(scaled(p, scale) for p in parts), width)

    def test_reference_width_gives_nothing(self):
        self.assertEqual(scaled_css("#box-clock { min-height: 55px; }", 1), "")

    def test_bar_rules_scaled_colors_dropped(self):
        css = scaled_css("#main-inner-sub { background-color: #090909; margin: 5px; padding: 5px 0px; }", 2)
        self.assertEqual(css, "#main-inner-sub { margin: 10px; padding: 10px 0px; }")

    def test_other_modules_untouched(self):
        self.assertEqual(scaled_css(".cc-btn { border-radius: 10px; }\n#notch-area { font-size: 16px; }", 2), "")

    def test_generic_rules_scoped_to_bar(self):
        css = scaled_css("button, label { color: #fff; font-size: 13px; }", 2)
        self.assertEqual(css, "#bar-root button, #bar-root label { font-size: 26px; }")

    def test_generic_rules_come_first(self):
        css = scaled_css("#box-clock label { font-size: 16px; }\nlabel { font-size: 13px; }", 2)
        self.assertLess(css.index("#bar-root label"), css.index("#box-clock label"))

    def test_mixed_selector_lists_keep_only_bar_part(self):
        css = scaled_css("#box-power, .cc-card { margin-bottom: 0px; }", 2)
        self.assertEqual(css, "#box-power { margin-bottom: 0px; }")

    def test_comments_ignored(self):
        css = scaled_css("/* #box-x { margin: 1px; } */ #ws-plate { border-radius: 5px; }", 2)
        self.assertEqual(css, "#ws-plate { border-radius: 10px; }")


if __name__ == "__main__":
    unittest.main()
