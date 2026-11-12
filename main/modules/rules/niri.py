import json
import os
import socket
import threading
import time

from gi.repository import GLib

from modules.common import debug
from modules.parsing import keyboard
from modules.parsing.toplevels import FullscreenWatcher
from modules.rules.base import Monitor, State


REFRESH_EVENTS = frozenset(("WorkspacesChanged", "WorkspaceActivated", "WorkspaceActiveWindowChanged"))

COALESCE_SECONDS = 0.03
REQUEST_TIMEOUT = 2


def event_name(message):
    if isinstance(message, dict) and message:
        return next(iter(message))
    return ""


def window_key(window, size=None):
    if size is None:
        size = window.get("layout", {}).get("window_size")
    return window.get("app_id"), window.get("workspace_id"), tuple(size or ())


class WindowTracker:
    def __init__(self):
        self._known = {}
        self.overview = False
        self.layouts = ()
        self.layout_idx = 0

    @property
    def layout(self):
        if 0 <= self.layout_idx < len(self.layouts):
            return keyboard.short_name(self.layouts[self.layout_idx])
        return ""

    def needs_refresh(self, message):
        name = event_name(message)
        body = message.get(name) if name else None
        if name in REFRESH_EVENTS:
            return True
        if name == "OverviewOpenedOrClosed":
            changed = bool(body["is_open"]) != self.overview
            self.overview = bool(body["is_open"])
            return changed
        if name == "KeyboardLayoutsChanged":
            layouts = body["keyboard_layouts"]
            self.layouts = tuple(layouts.get("names") or ())
            self.layout_idx = int(layouts.get("current_idx") or 0)
            return True
        if name == "KeyboardLayoutSwitched":
            self.layout_idx = int(body["idx"])
            return True
        if name == "WindowsChanged":
            self._known = {w["id"]: window_key(w) for w in body["windows"]}
            return True
        if name == "WindowOpenedOrChanged":
            window = body["window"]
            key = window_key(window)
            changed = self._known.get(window["id"]) != key
            self._known[window["id"]] = key
            return changed
        if name == "WindowClosed":
            return self._known.pop(body["id"], None) is not None
        if name == "WindowLayoutsChanged":
            changed = False
            for wid, layout in body["changes"]:
                old = self._known.get(wid)
                if old is None:
                    continue
                key = (old[0], old[1], tuple(layout.get("window_size") or ()))
                changed = changed or key != old
                self._known[wid] = key
            return changed
        return False


def window_list(windows):
    ordered = sorted(windows, key=lambda w: int(w.get("id", 0)))
    return tuple((w.get("app_id") or "", int(w.get("workspace_id") or 0)) for w in ordered)


def is_fullscreen(window, width, height, fullscreen_keys):
    if (window.get("app_id") or "", window.get("title") or "") not in fullscreen_keys:
        return False
    return covers_output(window, width, height)


def covers_output(window, width, height):
    size = window.get("layout", {}).get("window_size") or (0, 0)
    return size[0] >= width and size[1] >= height


def _usable_outputs(outputs):
    return [o for o in outputs.values() if o.get("logical")]


def monitor_list(outputs, workspaces, windows, fullscreen_keys=frozenset()):
    by_window = {int(w["id"]): w for w in windows}
    result = []
    for output in sorted(_usable_outputs(outputs), key=lambda o: (o["logical"]["x"], o["logical"]["y"])):
        name = output["name"]
        logical = output["logical"]
        width, height = int(logical["width"]), int(logical["height"])
        own = [w for w in workspaces if w.get("output") == name]
        active = next((w for w in own if w.get("is_active")), None)
        ids = {int(w["id"]): int(w["idx"]) for w in own}
        occupied = {ids[int(w["workspace_id"])] for w in windows if int(w.get("workspace_id") or -1) in ids}
        count = sum(1 for w in windows if active is not None and w.get("workspace_id") == active["id"])
        focused_window = by_window.get(active.get("active_window_id")) if active else None
        fullscreen = focused_window is not None and is_fullscreen(focused_window, width, height, fullscreen_keys)
        result.append(Monitor(name=name, x=int(logical["x"]), y=int(logical["y"]), width=width, height=height,
                              scale=float(logical.get("scale") or 1),
                              focused=any(w.get("is_focused") for w in own),
                              active=int(active["idx"]) if active else 1, windows=count, fullscreen=fullscreen,
                              occupied=frozenset(occupied)))
    return tuple(result)


def make_state(outputs, workspaces, windows, fullscreen_keys=frozenset(), overview=False, layout=""):
    monitors = monitor_list(outputs, workspaces, windows, fullscreen_keys)
    focused = next((m for m in monitors if m.focused), monitors[0] if monitors else None)
    if focused is None:
        return State(active=1, occupied=set(), windows=0, fullscreen=False, clients=window_list(windows),
                     overview=overview, layout=layout)
    return State(active=focused.active, occupied=set(focused.occupied), windows=focused.windows,
                 fullscreen=focused.fullscreen, clients=window_list(windows), monitors=monitors, overview=overview,
                 layout=layout)


def focused_scale(outputs, workspaces):
    focused = next((w.get("output") for w in workspaces if w.get("is_focused")), None)
    usable = _usable_outputs(outputs)
    chosen = next((o for o in usable if o["name"] == focused), usable[0] if usable else None)
    return float(chosen["logical"].get("scale") or 1) if chosen else None


def goto_requests(workspaces, index, output=None):
    focused = next((w.get("output") for w in workspaces if w.get("is_focused")), None)
    target = output or focused
    match = next((w for w in workspaces if w.get("output") == target and int(w["idx"]) == index), None)
    if match is not None:
        return [{"Action": {"FocusWorkspace": {"reference": {"Id": int(match["id"])}}}}]
    requests = []
    if target and target != focused:
        requests.append({"Action": {"FocusMonitor": {"output": target}}})
    requests.append({"Action": {"FocusWorkspace": {"reference": {"Index": index}}}})
    return requests


def fills_working_area(window, width, height, insets):
    left, top, right, bottom = insets
    return covers_output(window, width - left - right - 1, height - top - bottom - 1)


def refit_requests(outputs, workspaces, windows, focused_id, insets=(0, 0, 0, 0)):
    sizes = {o["name"]: (int(o["logical"]["width"]), int(o["logical"]["height"])) for o in _usable_outputs(outputs)}
    by_id = {int(w["id"]): w for w in windows}
    targets = []
    for workspace in workspaces:
        window = by_id.get(workspace.get("active_window_id") or -1)
        size = sizes.get(workspace.get("output"))
        if not workspace.get("is_active") or window is None or size is None or window.get("is_floating"):
            continue
        if fills_working_area(window, *size, insets):
            continue
        targets.append(int(window["id"]))
    if not targets:
        return []
    requests = []
    for wid in targets:
        requests.append({"Action": {"FocusWindow": {"id": wid}}})
        requests.append({"Action": {"MaximizeColumn": {}}})
        requests.append({"Action": {"MaximizeColumn": {}}})
    if focused_id is not None:
        requests.append({"Action": {"FocusWindow": {"id": int(focused_id)}}})
    return requests


def _socket_path():
    return os.environ.get("NIRI_SOCKET")


def _request(request):
    path = _socket_path()
    if not path:
        raise OSError("NIRI_SOCKET не задан")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(REQUEST_TIMEOUT)
        s.connect(path)
        s.sendall((json.dumps(request) + "\n").encode())
        line = s.makefile("r", encoding="utf-8", errors="replace").readline()
    reply = json.loads(line)
    if "Ok" not in reply:
        raise ValueError(reply.get("Err", reply))
    return reply["Ok"]


def _query(what):
    return _request(what)[what]


class NiriWorkspaces:
    per_output_workspaces = True

    def __init__(self):
        self.state = None
        self._subscribers = []
        self._events = debug.Rate("niri", 20)
        self._dirty = threading.Event()
        self._coalesced = 0
        self._overview = False
        self._layout = ""
        self._toplevels = FullscreenWatcher(self._on_fullscreen)
        self._last_event = ""

    def subscribe(self, callback):
        self._subscribers.append(callback)
        if self.state is not None:
            callback(self.state)

    def start(self):
        self._dirty.set()
        self._toplevels.start()
        threading.Thread(target=self._refresh_loop, daemon=True).start()
        threading.Thread(target=self._read_events, daemon=True).start()

    def apply_layer_rules(self):
        pass

    def goto(self, workspace_id, output=None):
        threading.Thread(target=self._goto, args=(int(workspace_id), output), daemon=True).start()

    def _goto(self, index, output):
        try:
            for request in goto_requests(_query("Workspaces"), index, output):
                _request(request)
        except (OSError, ValueError, KeyError, TypeError) as e:
            debug.log("niri", f"переключение на воркспейс {index} ({output}) не удалось: {e!r}")

    def refit_columns(self, insets):
        threading.Thread(target=self._refit_columns, args=(insets,), daemon=True).start()

    def _refit_columns(self, insets):
        try:
            windows = _query("Windows")
            focused = next((w["id"] for w in windows if w.get("is_focused")), None)
            for request in refit_requests(_query("Outputs"), _query("Workspaces"), windows, focused, insets):
                _request(request)
        except (OSError, ValueError, KeyError, TypeError) as e:
            debug.log("niri", f"перестановка колонок не удалась: {e!r}")

    def output_scale(self):
        try:
            return focused_scale(_query("Outputs"), _query("Workspaces"))
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def monitors(self):
        try:
            return monitor_list(_query("Outputs"), _query("Workspaces"), _query("Windows"), self._toplevels.fullscreen)
        except (OSError, ValueError, KeyError, TypeError):
            return ()

    def _refresh_loop(self):
        while True:
            self._dirty.wait()
            time.sleep(COALESCE_SECONDS)
            self._dirty.clear()
            coalesced, self._coalesced = self._coalesced, 0
            started = time.monotonic()
            try:
                state = make_state(_query("Outputs"), _query("Workspaces"), _query("Windows"),
                                   self._toplevels.fullscreen, self._overview, self._layout)
            except (OSError, ValueError, KeyError, TypeError) as e:
                debug.log("niri", f"refresh упал: {e!r}")
                continue
            debug.log("niri", f"refresh {(time.monotonic() - started) * 1000:.1f} мс после "
                              f"{self._last_event or 'старта'}, схлопнуто событий: {coalesced}")
            GLib.idle_add(self._emit, state)

    def _on_fullscreen(self):
        self._last_event = "fullscreen"
        self._coalesced += 1
        self._dirty.set()

    def _emit(self, state):
        if state == self.state:
            return False
        self.state = state
        for callback in self._subscribers:
            callback(state)
        return False

    def _read_events(self):
        while True:
            path = _socket_path()
            if path:
                try:
                    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                        s.connect(path)
                        s.sendall(b'"EventStream"\n')
                        self._dirty.set()
                        tracker = WindowTracker()
                        for line in s.makefile("r", encoding="utf-8", errors="replace"):
                            try:
                                message = json.loads(line)
                                name = event_name(message)
                                refresh = tracker.needs_refresh(message)
                                self._overview = tracker.overview
                                self._layout = tracker.layout
                            except (ValueError, KeyError, TypeError, AttributeError):
                                continue
                            self._events.hit(name)
                            if refresh:
                                self._last_event = name
                                self._coalesced += 1
                                self._dirty.set()
                except OSError as e:
                    debug.log("niri", f"сокет событий: {e}")
            time.sleep(1)


def create():
    return NiriWorkspaces()
