import re
import unittest
from pathlib import Path

from modules.common import theme

ROOT = Path(__file__).resolve().parents[2]
MODULES = Path(__file__).resolve().parents[1] / "modules"
_RULE = re.compile(r"([^{}]+)\{([^{}]*)\}")


def _css_rules():
    text = re.sub(r"/\*.*?\*/", "", (ROOT / "style.css").read_text(), flags=re.S)
    rules = {}
    for selectors, body in _RULE.findall(text):
        props = {}
        for declaration in body.split(";"):
            name, colon, value = declaration.partition(":")
            if colon:
                props[name.strip()] = value.strip()
        for selector in selectors.split(","):
            rules.setdefault(selector.strip(), {}).update(props)
    return rules


class ThemeTest(unittest.TestCase):
    def test_defaults_parse(self):
        for selector, props in theme.DEFAULTS.items():
            for prop in props:
                theme._get(selector, prop)

    def test_classes_inherit(self):
        self.assertEqual(theme.radius("#launcher-row.active"), 10)
        self.assertEqual(theme.fg("#launcher-row.active"), (1.0, 1.0, 1.0, 1.0))
        self.assertEqual(theme.bg("#cc-net-item.on.hover")[:3], (0xd1 / 255,) * 3)
        self.assertEqual(theme.bg("#screenshot-overlay"), (0.0, 0.0, 0.0, 0.25))

    def test_spacings(self):
        self.assertEqual(theme.padding("#cc-calendar-plate"), (8, 7, 8, 7))
        self.assertEqual(theme.padding("#launcher-row"), (0, 2, 0, 4))
        self.assertEqual(theme.gap("#launcher-row"), 5)
        self.assertEqual(theme.pad("#cc-body"), 6)
        self.assertEqual(theme.font("#cc-record"), 14)

    def test_unknown(self):
        with self.assertRaises(KeyError):
            theme.bg("#nothing-here")

    def test_style_css_lists_every_rule(self):
        # The owner tunes colours in style.css: every drawn rule must be there, with the default values.
        rules = _css_rules()
        for selector, props in theme.DEFAULTS.items():
            self.assertIn(selector, rules, f"нет правила {selector} в style.css")
            for prop, value in props.items():
                expected = theme._css_value(prop, value)
                self.assertEqual(rules[selector].get(prop), expected, f"{selector} {prop}")

    def test_code_uses_known_rules(self):
        used = set()
        for path in MODULES.rglob("*.py"):
            used |= set(re.findall(r'theme\.(?:bg|fg|radius|font|pad|gap|padding)\("(#[\w.-]+)"\)', path.read_text()))
        for selector in used:
            self.assertTrue(any(theme._SELECTOR.match(selector).group(1) == theme._SELECTOR.match(d).group(1)
                                for d in theme.DEFAULTS), selector)


if __name__ == "__main__":
    unittest.main()
