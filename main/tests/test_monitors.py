import unittest

from modules.rules import hypr as wm
from modules.rules.base import State
from modules.rules.view import MonitorView, view_state

MONITORS = [
    {"name": "eDP-1", "x": 0, "y": 0, "width": 1920, "height": 1080, "scale": 1.5, "focused": True,
     "activeWorkspace": {"id": 1}, "transform": 0},
    {"name": "HDMI-A-1", "x": 1280, "y": 0, "width": 1080, "height": 1920, "scale": 1.0, "focused": False,
     "activeWorkspace": {"id": 5}, "transform": 1},
    {"name": "OFF", "x": 0, "y": 0, "width": 800, "height": 600, "scale": 1, "disabled": True,
     "activeWorkspace": {"id": 9}},
]
WORKSPACES = [{"id": 1, "windows": 0}, {"id": 5, "windows": 2, "hasfullscreen": True}]


class MonitorListTest(unittest.TestCase):
    def test_logical_geometry_and_workspace(self):
        first, second = wm.monitor_list(MONITORS, WORKSPACES)
        self.assertEqual((first.width, first.height, first.focused, first.active), (1280, 720, True, 1))
        self.assertEqual((second.width, second.height), (1920, 1080))
        self.assertEqual((second.active, second.windows, second.fullscreen), (5, 2, True))

    def test_state_carries_monitors(self):
        state = wm.make_state({"id": 1}, WORKSPACES, (), MONITORS)
        self.assertEqual([m.name for m in state.monitors], ["eDP-1", "HDMI-A-1"])


class ViewTest(unittest.TestCase):
    def setUp(self):
        self.state = wm.make_state({"id": 1, "windows": 0}, WORKSPACES, (), MONITORS)

    def test_view_uses_its_monitor(self):
        view = view_state(self.state, "HDMI-A-1")
        self.assertEqual((view.active, view.windows, view.fullscreen), (5, 2, True))
        self.assertEqual(view.occupied, self.state.occupied)

    def test_unknown_monitor_keeps_the_state(self):
        self.assertEqual(view_state(self.state, "nope"), self.state)

    def test_subscriber_skips_unchanged_views(self):
        class Fake:
            def subscribe(self, callback):
                self.callback = callback

        fake, seen = Fake(), []
        MonitorView(fake, wm.monitor_list(MONITORS, WORKSPACES)[1]).subscribe(seen.append)
        fake.callback(self.state)
        fake.callback(self.state._replace(active=2))
        self.assertEqual(len(seen), 1)

    def test_null_state_has_no_monitors(self):
        self.assertEqual(State(1, set(), 0, False, ()).monitors, ())


if __name__ == "__main__":
    unittest.main()
