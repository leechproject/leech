import tempfile
import unittest
from pathlib import Path

from modules.config import loader, syntax
from modules.config.values import Bind, Custom, Icon, Position

BASE = "/opt/leech"


def evaluate(text):
    return loader.evaluate(text, BASE)


def messages(problems):
    return [str(p) for p in problems]


class SyntaxTest(unittest.TestCase):
    def test_nested_sections_and_comments(self):
        root, problems = syntax.parse('a {\n  b {\n    k = "x # y" # tail\n  }\n}\n# whole line\n')
        self.assertEqual(problems, [])
        self.assertEqual(root.sections["a"].sections["b"].entries["k"].raw, '"x # y"')

    def test_braces_on_one_line(self):
        root, problems = syntax.parse("a { k = 1 }\nb\n{\nk = 2\n}\n")
        self.assertEqual(problems, [])
        self.assertEqual(root.sections["a"].entries["k"].raw, "1")
        self.assertEqual(root.sections["b"].entries["k"].raw, "2")

    def test_quoted_key(self):
        root, _ = syntax.parse('"wifi" = n\n')
        entry = root.entries["wifi"]
        self.assertTrue(entry.quoted)
        self.assertEqual(entry.raw, "n")

    def test_structure_errors_have_lines(self):
        _, problems = syntax.parse("a {\nk = 1\n}\n}\nwhat is this\nb {\n")
        text = messages(problems)
        self.assertIn("строка 4: лишняя «}»", text)
        self.assertTrue(any(t.startswith("строка 5: непонятная строка") for t in text))
        self.assertIn("строка 6: секция «b» не закрыта", text)

    def test_duplicate_key_keeps_last(self):
        root, problems = syntax.parse("k = 1\nk = 2\n")
        self.assertEqual(root.entries["k"].raw, "2")
        self.assertEqual(len(problems), 1)

    def test_item(self):
        root, problems = syntax.parse('row4 {\n  c1(icon = \\uf077; cmd = "a; b")\n}\n')
        self.assertEqual(problems, [])
        item = root.sections["row4"].items[0]
        self.assertEqual((item.name, item.args), ("c1", {"icon": "\\uf077", "cmd": '"a; b"'}))


class ValueTest(unittest.TestCase):
    def test_defaults_parse_cleanly(self):
        settings, problems = evaluate(loader.default_text())
        self.assertEqual([p for p in messages(problems) if "не найдены" not in p], [])
        self.assertEqual(settings["frame.top"], 9)
        self.assertEqual(settings["ASSETS_DIR"], Path(BASE) / "assets")

    def test_empty_means_default(self):
        settings, problems = evaluate("frame {\n  top =\n}\n")
        self.assertEqual(problems, [])
        self.assertEqual(settings["frame.top"], 9)

    def test_invalid_falls_back_with_line(self):
        settings, problems = evaluate("frame {\n  top = wide\n}\n")
        self.assertEqual(settings["frame.top"], 9)
        self.assertTrue(messages(problems)[0].startswith("строка 2: frame.top"))

    def test_unknown_parameter(self):
        _, problems = evaluate("dock {\n  sparkle = y\n}\nnope {\n}\n")
        self.assertEqual(messages(problems), ["строка 2: неизвестный параметр «sparkle» в «dock»",
                                              "строка 4: неизвестная секция «nope» в «корне»"])

    def test_bool(self):
        settings, problems = evaluate("notifications {\n  push-allowed = N\n}\n")
        self.assertEqual(problems, [])
        self.assertFalse(settings["notifications.push-allowed"])

    def test_three_path_spellings(self):
        for raw in ("/a/My\\ Dir/x", '"/a/My Dir/x"', "'/a/My Dir/x'"):
            settings, problems = evaluate(f"wallpapers {{\n  dir = {raw}\n}}\n")
            self.assertEqual(problems, [], raw)
            self.assertEqual(settings["wallpapers.dir"], "/a/My Dir/x", raw)

    def test_path_variables(self):
        text = 'BASE_DIR = /srv/l\nASSETS_DIR = BASE_DIR / "art"\nnotch {\n expand {\n  player {\n' \
               '   cover-fallback-image = ASSETS_DIR / "c.png"\n  }\n }\n}\n'
        settings, problems = evaluate(text)
        self.assertEqual(problems, [])
        self.assertEqual(settings["notch.expand.player.cover-fallback-image"], "/srv/l/art/c.png")

    def test_home_expansion(self):
        settings, _ = evaluate("WALLPAPERS_DIR = ~/W\nwallpapers {\n  dir = WALLPAPERS_DIR\n}\n")
        self.assertEqual(settings["wallpapers.dir"], str(Path.home() / "W"))

    def test_glyph_escapes(self):
        text = "launcher {\n context-menu {\n  pin-icon = \\uf08d\n  hide-icon = \\U000F024B\n }\n}\n"
        settings, problems = evaluate(text)
        self.assertEqual(problems, [])
        self.assertEqual(settings["launcher.context-menu.pin-icon"], Icon(glyph="\uf08d"))
        self.assertEqual(settings["launcher.context-menu.hide-icon"], Icon(glyph="\U000f024b"))

    def test_icon_path(self):
        settings, _ = evaluate('bar {\n launcher-btn {\n  launcher-button-icon = ASSETS_DIR / "l.svg"\n }\n}\n')
        self.assertEqual(settings["bar.launcher-btn.launcher-button-icon"], Icon(path=BASE + "/assets/l.svg"))

    def test_icon_reference(self):
        text = "bar {\n workspace {\n  ws-inuse-icon = \\uf111\n  ws-active-icon = ws-inuse-icon:invertcolor\n }\n}\n"
        settings, _ = evaluate(text)
        self.assertEqual(settings["bar.workspace.ws-active-icon"], Icon(glyph="\uf111", invert=True))

    def test_bind(self):
        for raw in ("SHIFT, ENTER", "shift + enter"):
            settings, problems = evaluate(f"launcher {{\n context-menu {{\n  bind = {raw}\n }}\n}}\n")
            self.assertEqual(problems, [], raw)
            self.assertEqual(settings["launcher.context-menu.bind"], Bind(frozenset({"SHIFT"}), "ENTER"))
        _, problems = evaluate("launcher {\n context-menu {\n  bind = HYPER, X\n }\n}\n")
        self.assertIn("HYPER", messages(problems)[0])

    def test_position(self):
        settings, _ = evaluate("cc {\n sliders {\n  volume-position = rhalf:right\n }\n}\n")
        self.assertEqual(settings["cc.sliders.volume-position"], Position("rhalf", "right"))

    def test_rows_and_custom_buttons(self):
        text = 'cc {\n row1 {\n  "wifi" = y\n }\n row4 {\n  files(icon = \\uf07b; cmd = "nautilus ~")\n }\n}\n'
        settings, problems = evaluate(text)
        self.assertEqual(settings["cc.row4"].custom, [Custom("files", Icon(glyph="\uf07b"), "nautilus ~")])
        self.assertTrue(all("не поддерживаются" in m for m in messages(problems)))

    def test_unsupported_value_is_reported(self):
        _, problems = evaluate("bar {\n launcher-btn {\n  launcher-icon-spacing = 4\n }\n}\n")
        self.assertEqual(messages(problems),
                         ["строка 3: bar.launcher-btn.launcher-icon-spacing: пока не поддерживается, значение не применяется"])
        _, problems = evaluate("bar {\n launcher-btn {\n  launcher-icon-spacing =\n }\n}\n")
        self.assertEqual(problems, [])

    def test_font_pattern(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("Face-Solid.otf", "Face-Regular.otf"):
                (Path(tmp) / name).write_bytes(b"")
            settings, problems = evaluate(f"ICON_FONT = '{tmp}/Face*'\nGLOBAL_FONT = {tmp}/missing.ttf\n")
            self.assertEqual(settings["ICON_FONT"], (f"{tmp}/Face-Regular.otf", f"{tmp}/Face-Solid.otf"))
            self.assertIsNone(settings["GLOBAL_FONT"])
            self.assertEqual(len(problems), 1)


class FileTest(unittest.TestCase):
    def test_missing_file_is_generated(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "leech.conf"
            settings, _ = loader.load(path, tmp)
            self.assertTrue(path.read_text().startswith("#########\n# LEECH #"))
            self.assertIn("GLOBAL_FONT =\n", path.read_text())
            self.assertEqual(settings["dock.icon-size"], 24)


if __name__ == "__main__":
    unittest.main()


class CheckTest(unittest.TestCase):
    def test_check_reports_lines_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "leech.conf"
            path.write_text("dock {\n  hide-by-window = maybe\n}\n")
            problems = loader.check(path, tmp)
            self.assertEqual([p.line for p in problems], [2])
            self.assertIsNone(loader.check(None, tmp) or None)
            self.assertTrue(loader.check(Path(tmp) / "missing.conf", tmp))
            self.assertFalse((Path(tmp) / "missing.conf").exists())

    def test_module_flags_are_implemented(self):
        settings, problems = loader.evaluate("dock {\n  module-enabled = n\n  hide-by-window = n\n}\n", "/")
        self.assertEqual(problems, [])
        self.assertFalse(settings.get("dock.module-enabled"))
        self.assertFalse(settings.get("dock.hide-by-window"))
