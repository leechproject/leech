import unittest

from modules.rules import available, mangowm
from modules.rules.view import view_state


def tags(active, counts):
    return [{"index": i, "is_active": i in active, "client_count": counts.get(i, 0)} for i in range(1, 10)]


def monitor(name, x, active_tags, counts, focused=False, scale=1, width=1920, height=1080, layout="English (US)"):
    return {"name": name, "active": focused, "x": x, "y": 0, "width": width, "height": height, "scale": scale,
            "transform": "normal", "tags": tags(active_tags, counts), "active_tags": list(active_tags),
            "keyboardlayout": layout}


def client(cid, app, mon, client_tags, **flags):
    return {"id": cid, "appid": app, "title": f"t{cid}", "monitor": mon, "tags": list(client_tags),
            "is_minimized": False, "is_global": False, "is_fullscreen": False, **flags}


MONITORS = [
    monitor("HDMI-A-1", 1536, [1], {1: 1}),
    monitor("eDP-1", 0, [2], {1: 2, 2: 1}, focused=True, scale=1.25, width=1536, height=864),
]
CLIENTS = [
    client(5, "term", "eDP-1", [1]),
    client(3, "happ", "eDP-1", [1]),
    client(7, "firefox", "eDP-1", [2]),
    client(9, "mpv", "HDMI-A-1", [1], is_fullscreen=True),
]


class StateTest(unittest.TestCase):
    def test_listed_as_rules(self):
        self.assertIn("mangowm", available())
        self.assertNotIn("view", available())

    def test_focused_monitor(self):
        state = mangowm.make_state(MONITORS, CLIENTS, {})
        self.assertEqual(state.active, 2)
        self.assertEqual(state.occupied, {1, 2})
        self.assertEqual(state.windows, 1)
        self.assertFalse(state.fullscreen)
        self.assertEqual(state.layout, "en")
        self.assertFalse(state.overview)

    def test_clients_in_open_order(self):
        state = mangowm.make_state(MONITORS, CLIENTS, {})
        self.assertEqual(state.clients, (("happ", 1), ("term", 1), ("firefox", 2), ("mpv", 1)))

    def test_monitors_sorted_with_logical_geometry(self):
        state = mangowm.make_state(MONITORS, CLIENTS, {})
        self.assertEqual([m.name for m in state.monitors], ["eDP-1", "HDMI-A-1"])
        edp = state.monitors[0]
        self.assertEqual((edp.width, edp.height, edp.scale), (1536, 864, 1.25))

    def test_per_monitor_view(self):
        state = mangowm.make_state(MONITORS, CLIENTS, {})
        hdmi = view_state(state, "HDMI-A-1")
        self.assertEqual((hdmi.active, hdmi.windows, hdmi.fullscreen, hdmi.occupied), (1, 1, True, {1}))

    def test_fullscreen_only_when_visible(self):
        clients = CLIENTS + [client(11, "game", "eDP-1", [1], is_fullscreen=True)]
        self.assertFalse(mangowm.make_state(MONITORS, clients, {}).fullscreen)
        clients = CLIENTS + [client(11, "game", "eDP-1", [2], is_fullscreen=True)]
        self.assertTrue(mangowm.make_state(MONITORS, clients, {}).fullscreen)

    def test_maximized_is_not_fullscreen(self):
        clients = CLIENTS + [client(11, "game", "eDP-1", [2], is_maximized=True)]
        self.assertFalse(mangowm.make_state(MONITORS, clients, {}).fullscreen)

    def test_minimized_and_global(self):
        clients = [client(1, "a", "eDP-1", [2], is_minimized=True), client(2, "b", "eDP-1", [5], is_global=True)]
        self.assertEqual(mangowm.make_state(MONITORS, clients, {}).windows, 1)

    def test_several_visible_tags(self):
        monitors = [monitor("eDP-1", 0, [3, 1], {1: 2}, focused=True)]
        state = mangowm.make_state(monitors, [client(1, "a", "eDP-1", [1])], {})
        self.assertEqual((state.active, state.windows), (1, 1))

    def test_overview_keeps_last_tag(self):
        remembered = {}
        mangowm.make_state(MONITORS, CLIENTS, remembered)
        overview = [dict(m, active_tags=[0]) for m in MONITORS]
        state = mangowm.make_state(overview, CLIENTS, remembered)
        self.assertTrue(state.overview)
        self.assertEqual((state.active, state.windows), (2, 1))

    def test_no_monitors(self):
        state = mangowm.make_state([], CLIENTS, {})
        self.assertEqual((state.active, state.monitors), (1, ()))

    def test_focused_scale(self):
        self.assertEqual(mangowm.focused_scale(MONITORS), 1.25)
        self.assertIsNone(mangowm.focused_scale([]))


class StreamTest(unittest.TestCase):
    def test_title_change_does_not_refresh(self):
        rules = mangowm.MangoWorkspaces()
        self.assertTrue(rules._accept("all-clients", {"clients": CLIENTS}))
        retitled = [dict(c, title="new") for c in CLIENTS]
        self.assertFalse(rules._accept("all-clients", {"clients": retitled}))
        self.assertEqual(rules._data["all-clients"][0]["title"], "new")
        moved = [dict(CLIENTS[0], tags=[3])] + CLIENTS[1:]
        self.assertTrue(rules._accept("all-clients", {"clients": moved}))

    def test_focus_title_does_not_refresh_monitors(self):
        rules = mangowm.MangoWorkspaces()
        self.assertTrue(rules._accept("all-monitors", {"monitors": MONITORS}))
        self.assertFalse(rules._accept("all-monitors", {"monitors": [dict(m, active_client={"title": "x"})
                                                                      for m in MONITORS]}))
        self.assertTrue(rules._accept("all-monitors", {"monitors": [dict(m, keyboardlayout="Russian")
                                                                     for m in MONITORS]}))


class KeyboardTest(unittest.TestCase):
    def test_menus_keep_exclusive_keyboard(self):
        from modules.common import layerkeys
        self.assertFalse(mangowm.MangoWorkspaces.relax_layer_keyboard)
        saved = layerkeys.RELAX
        try:
            layerkeys.RELAX = False
            self.assertEqual(layerkeys.effective("on_demand"), "exclusive")
            self.assertEqual(layerkeys.effective("none"), "none")
            layerkeys.RELAX = True
            self.assertEqual(layerkeys.effective("on_demand"), "on_demand")
        finally:
            layerkeys.RELAX = saved


class GotoTest(unittest.TestCase):
    def test_commands(self):
        self.assertEqual(mangowm.goto_command(3), "dispatch view,3,0")
        self.assertEqual(mangowm.goto_command(2, "HDMI-A-1"), "dispatch viewcrossmon,2,HDMI-A-1")


if __name__ == "__main__":
    unittest.main()
