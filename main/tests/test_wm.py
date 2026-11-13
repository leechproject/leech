import unittest

from modules.rules import hypr as wm


class EventTest(unittest.TestCase):
    def test_exact_names(self):
        self.assertTrue(wm.needs_refresh("workspace>>3\n"))
        self.assertTrue(wm.needs_refresh("openwindow>>55e0,1,kitty,kitty\n"))
        self.assertTrue(wm.needs_refresh("fullscreen>>1\n"))

    def test_v2_duplicates_ignored(self):
        for line in ("workspacev2>>3,3\n", "movewindowv2>>55e0,3,3\n", "createworkspacev2>>4,4\n",
                     "destroyworkspacev2>>4,4\n", "focusedmonv2>>eDP-1,3\n"):
            self.assertFalse(wm.needs_refresh(line), line)

    def test_unrelated_ignored(self):
        self.assertFalse(wm.needs_refresh("activewindow>>kitty,title\n"))
        self.assertFalse(wm.needs_refresh("windowtitlev2>>55e0,title\n"))
        self.assertFalse(wm.needs_refresh(""))

    def test_event_name(self):
        self.assertEqual(wm.event_name("openwindow>>a,b>>c\n"), "openwindow")


class StateTest(unittest.TestCase):
    def test_focused_scale(self):
        monitors = [{"focused": False, "scale": 1.0}, {"focused": True, "scale": 1.5}]
        self.assertEqual(wm.focused_scale(monitors), 1.5)
        self.assertEqual(wm.focused_scale([{"scale": 1.25}]), 1.25)
        self.assertIsNone(wm.focused_scale([]))

    def test_window_list_in_opening_order(self):
        clients = [{"class": "b", "workspace": {"id": 2}}, {"class": "", "initialClass": "a", "workspace": {"id": 1}},
                   {"class": "c", "workspace": {"id": 1}, "mapped": False}]
        self.assertEqual(wm.window_list(clients), (("b", 2), ("a", 1)))

    def test_make_state(self):
        state = wm.make_state({"id": 2, "windows": 3, "hasfullscreen": True}, [{"id": 1}, {"id": 2}])
        self.assertEqual(state, wm.State(active=2, occupied={1, 2}, windows=3, fullscreen=True, clients=()))

    def test_defaults(self):
        state = wm.make_state({"id": "4"}, [])
        self.assertEqual(state, wm.State(active=4, occupied=set(), windows=0, fullscreen=False, clients=()))


class HyprctlArgsTest(unittest.TestCase):
    def test_json_query(self):
        self.assertEqual(wm.hyprctl_args("j/activeworkspace"), ["activeworkspace", "-j"])

    def test_plain(self):
        self.assertEqual(wm.hyprctl_args("dispatch workspace 3"), ["dispatch", "workspace", "3"])

    def test_dialects(self):
        self.assertEqual(wm.GOTO_DIALECTS["lua"].format(id=3), "dispatch hl.dsp.focus({ workspace = 3 })")
        self.assertEqual(wm.GOTO_DIALECTS["legacy"].format(id=3), "dispatch workspace 3")


if __name__ == "__main__":
    unittest.main()


class ReplyTest(unittest.TestCase):
    def test_ok(self):
        self.assertTrue(wm.reply_ok("ok"))
        self.assertTrue(wm.reply_ok("ok\n"))

    def test_failures(self):
        self.assertFalse(wm.reply_ok(""))
        self.assertFalse(wm.reply_ok("unknown request"))
        self.assertFalse(wm.reply_ok("error: return hl.layer_rule({ bogus = 1 });:1: unknown field"))
