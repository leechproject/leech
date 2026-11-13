import unittest

from modules.rules import niri
from modules.rules.view import MonitorView, view_state

OUTPUTS = {
    "eDP-1": {"name": "eDP-1", "logical": {"x": 0, "y": 0, "width": 1536, "height": 864, "scale": 1.25}},
    "HDMI-A-1": {"name": "HDMI-A-1", "logical": {"x": 1536, "y": 0, "width": 1920, "height": 1080, "scale": 1.0}},
    "DP-2": {"name": "DP-2", "logical": None},
}
WORKSPACES = [
    {"id": 1, "idx": 1, "output": "eDP-1", "is_active": False, "is_focused": False, "active_window_id": 8},
    {"id": 2, "idx": 2, "output": "eDP-1", "is_active": True, "is_focused": True, "active_window_id": 13},
    {"id": 3, "idx": 3, "output": "eDP-1", "is_active": False, "is_focused": False, "active_window_id": None},
    {"id": 5, "idx": 1, "output": "HDMI-A-1", "is_active": True, "is_focused": False, "active_window_id": 20},
    {"id": 6, "idx": 2, "output": "HDMI-A-1", "is_active": False, "is_focused": False, "active_window_id": None},
]


def window(wid, app, ws, size=(700, 800)):
    return {"id": wid, "app_id": app, "workspace_id": ws, "layout": {"window_size": list(size)}}


FULLSCREEN = frozenset({("term", "")})
WINDOWS = [window(13, "term", 2, (1536, 864)), window(8, "happ", 1), window(9, "term", 1),
           window(20, "firefox", 5, (1000, 1080))]


class EventTest(unittest.TestCase):
    def test_event_name(self):
        self.assertEqual(niri.event_name({"WorkspaceActivated": {"id": 2, "focused": True}}), "WorkspaceActivated")
        self.assertEqual(niri.event_name("Handled"), "")
        self.assertEqual(niri.event_name({}), "")

    def test_workspace_events_refresh(self):
        tracker = niri.WindowTracker()
        self.assertTrue(tracker.needs_refresh({"WorkspaceActivated": {"id": 2, "focused": True}}))
        self.assertFalse(tracker.needs_refresh({"WindowFocusChanged": {"id": 1}}))
        self.assertFalse(tracker.needs_refresh({"Ok": "Handled"}))

    def test_title_change_ignored(self):
        tracker = niri.WindowTracker()
        self.assertTrue(tracker.needs_refresh({"WindowsChanged": {"windows": [window(13, "term", 2)]}}))
        retitled = dict(window(13, "term", 2), title="spinner")
        self.assertFalse(tracker.needs_refresh({"WindowOpenedOrChanged": {"window": retitled}}))
        self.assertTrue(tracker.needs_refresh({"WindowOpenedOrChanged": {"window": window(13, "term", 3)}}))
        self.assertTrue(tracker.needs_refresh({"WindowOpenedOrChanged": {"window": window(14, "web", 3)}}))

    def test_layout_size_change(self):
        tracker = niri.WindowTracker()
        tracker.needs_refresh({"WindowsChanged": {"windows": [window(13, "term", 2)]}})
        same = {"WindowLayoutsChanged": {"changes": [[13, {"window_size": [700, 800]}]]}}
        bigger = {"WindowLayoutsChanged": {"changes": [[13, {"window_size": [1536, 864]}]]}}
        self.assertFalse(tracker.needs_refresh(same))
        self.assertTrue(tracker.needs_refresh(bigger))

    def test_overview(self):
        tracker = niri.WindowTracker()
        self.assertFalse(tracker.needs_refresh({"OverviewOpenedOrClosed": {"is_open": False}}))
        self.assertTrue(tracker.needs_refresh({"OverviewOpenedOrClosed": {"is_open": True}}))
        self.assertTrue(tracker.overview)
        state = niri.make_state(OUTPUTS, WORKSPACES, WINDOWS, overview=True)
        self.assertTrue(view_state(state, "HDMI-A-1").overview)

    def test_window_closed(self):
        tracker = niri.WindowTracker()
        tracker.needs_refresh({"WindowsChanged": {"windows": [window(13, "term", 2)]}})
        self.assertTrue(tracker.needs_refresh({"WindowClosed": {"id": 13}}))
        self.assertFalse(tracker.needs_refresh({"WindowClosed": {"id": 13}}))


class StateTest(unittest.TestCase):
    def test_window_list_in_opening_order(self):
        self.assertEqual(niri.window_list(WINDOWS), (("happ", 1), ("term", 1), ("term", 2), ("firefox", 5)))

    def test_monitors_skip_disabled_outputs(self):
        names = [m.name for m in niri.monitor_list(OUTPUTS, WORKSPACES, WINDOWS)]
        self.assertEqual(names, ["eDP-1", "HDMI-A-1"])

    def test_monitor_fields(self):
        laptop, external = niri.monitor_list(OUTPUTS, WORKSPACES, WINDOWS, FULLSCREEN)
        self.assertEqual((laptop.width, laptop.height, laptop.scale), (1536, 864, 1.25))
        self.assertTrue(laptop.focused)
        self.assertEqual((laptop.active, laptop.windows, laptop.fullscreen), (2, 1, True))
        self.assertEqual(laptop.occupied, frozenset({1, 2}))
        self.assertFalse(external.focused)
        self.assertEqual((external.active, external.windows, external.fullscreen), (1, 1, False))
        self.assertEqual(external.occupied, frozenset({1}))

    def test_state_follows_focused_output(self):
        state = niri.make_state(OUTPUTS, WORKSPACES, WINDOWS, FULLSCREEN)
        self.assertEqual((state.active, state.occupied, state.windows, state.fullscreen), (2, {1, 2}, 1, True))
        self.assertEqual(len(state.clients), 4)

    def test_maximized_to_edges_is_not_fullscreen(self):
        laptop = niri.monitor_list(OUTPUTS, WORKSPACES, WINDOWS)[0]
        self.assertFalse(laptop.fullscreen)

    def test_fullscreen_needs_covering_size(self):
        small = [window(13, "term", 2, (700, 800))]
        laptop = niri.monitor_list(OUTPUTS, WORKSPACES, small, FULLSCREEN)[0]
        self.assertFalse(laptop.fullscreen)

    def test_state_without_outputs(self):
        state = niri.make_state({}, [], [])
        self.assertEqual((state.active, state.occupied, state.monitors), (1, set(), ()))

    def test_view_uses_own_occupied(self):
        state = niri.make_state(OUTPUTS, WORKSPACES, WINDOWS)
        view = view_state(state, "HDMI-A-1")
        self.assertEqual((view.active, view.occupied, view.fullscreen), (1, {1}, False))

    def test_focused_scale(self):
        self.assertEqual(niri.focused_scale(OUTPUTS, WORKSPACES), 1.25)
        self.assertIsNone(niri.focused_scale({}, []))


class GotoTest(unittest.TestCase):
    def test_existing_workspace_by_id(self):
        self.assertEqual(niri.goto_requests(WORKSPACES, 2, "HDMI-A-1"),
                         [{"Action": {"FocusWorkspace": {"reference": {"Id": 6}}}}])
        self.assertEqual(niri.goto_requests(WORKSPACES, 3),
                         [{"Action": {"FocusWorkspace": {"reference": {"Id": 3}}}}])

    def test_missing_workspace_on_other_output(self):
        self.assertEqual(niri.goto_requests(WORKSPACES, 4, "HDMI-A-1"),
                         [{"Action": {"FocusMonitor": {"output": "HDMI-A-1"}}},
                          {"Action": {"FocusWorkspace": {"reference": {"Index": 4}}}}])

    def test_view_passes_its_output(self):
        calls = []

        class Fake:
            per_output_workspaces = True

            def goto(self, *args):
                calls.append(args)

        monitor = niri.monitor_list(OUTPUTS, WORKSPACES, WINDOWS)[1]
        MonitorView(Fake(), monitor).goto(2)
        self.assertEqual(calls, [(2, "HDMI-A-1")])



class RefitTest(unittest.TestCase):
    def test_active_tiled_windows_are_refit_and_focus_returns(self):
        outputs = {"A": {"name": "A", "logical": {"x": 0, "y": 0, "width": 1536, "height": 864, "scale": 1}},
                   "B": {"name": "B", "logical": {"x": 1536, "y": 0, "width": 1920, "height": 1080, "scale": 1}}}
        workspaces = [{"id": 1, "output": "A", "is_active": True, "active_window_id": 10},
                      {"id": 2, "output": "A", "is_active": False, "active_window_id": 11},
                      {"id": 3, "output": "B", "is_active": True, "active_window_id": 12}]
        windows = [{"id": 10, "is_floating": False, "layout": {"window_size": [700, 800]}},
                   {"id": 11, "is_floating": False, "layout": {"window_size": [700, 800]}},
                   {"id": 12, "is_floating": True, "layout": {"window_size": [700, 800]}}]
        requests = niri.refit_requests(outputs, workspaces, windows, 12)
        self.assertEqual(requests, [{"Action": {"FocusWindow": {"id": 10}}},
                                    {"Action": {"MaximizeColumn": {}}},
                                    {"Action": {"MaximizeColumn": {}}},
                                    {"Action": {"FocusWindow": {"id": 12}}}])

    def test_maximized_to_edges_is_skipped(self):
        outputs = {"A": {"name": "A", "logical": {"x": 0, "y": 0, "width": 1536, "height": 864, "scale": 1}}}
        workspaces = [{"id": 1, "output": "A", "is_active": True, "active_window_id": 10}]
        edges = [{"id": 10, "is_floating": False, "layout": {"window_size": [1518, 815]}}]
        column = [{"id": 10, "is_floating": False, "layout": {"window_size": [1485, 782]}}]
        self.assertEqual(niri.refit_requests(outputs, workspaces, edges, 10, (9, 9, 9, 40)), [])
        self.assertEqual(len(niri.refit_requests(outputs, workspaces, column, 10, (9, 9, 9, 40))), 4)

    def test_fullscreen_and_empty_are_skipped(self):
        outputs = {"A": {"name": "A", "logical": {"x": 0, "y": 0, "width": 1536, "height": 864, "scale": 1}}}
        workspaces = [{"id": 1, "output": "A", "is_active": True, "active_window_id": 10}]
        windows = [{"id": 10, "is_floating": False, "layout": {"window_size": [1536, 864]}}]
        self.assertEqual(niri.refit_requests(outputs, workspaces, windows, 10), [])
        self.assertEqual(niri.refit_requests(outputs, [{"id": 1, "output": "A", "is_active": True,
                                                        "active_window_id": None}], [], None), [])


if __name__ == "__main__":
    unittest.main()
