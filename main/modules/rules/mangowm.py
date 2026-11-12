import json
import os
import socket
import threading
import time

from gi.repository import GLib

from modules.common import debug
from modules.parsing import keyboard
from modules.rules.base import Monitor, State


STREAMS = ("all-monitors", "all-clients")
OVERVIEW_TAG = 0

COALESCE_SECONDS = 0.03
REQUEST_TIMEOUT = 2


def active_tags(monitor):
    return tuple(int(t) for t in monitor.get("active_tags") or ())


def in_overview(monitor):
    return OVERVIEW_TAG in active_tags(monitor)


def client_visible(client, monitor_name, tags):
    if client.get("monitor") != monitor_name or client.get("is_minimized"):
        return False
    return client.get("is_global") or bool(set(client.get("tags") or ()) & set(tags))


def client_key(client):
    return (int(client.get("id", 0)), client.get("appid") or "", client.get("monitor") or "",
            tuple(client.get("tags") or ()), bool(client.get("is_minimized")), bool(client.get("is_global")),
            bool(client.get("is_fullscreen")))


def monitor_key(monitor):
    tags = tuple((int(t["index"]), int(t.get("client_count") or 0)) for t in monitor.get("tags") or ())
    return (monitor.get("name"), monitor.get("active"), monitor.get("x"), monitor.get("y"), monitor.get("width"),
            monitor.get("height"), monitor.get("scale"), active_tags(monitor), tags, monitor.get("keyboardlayout"))


def window_list(clients):
    ordered = sorted(clients, key=lambda c: int(c.get("id", 0)))
    return tuple((c.get("appid") or "", min(c.get("tags") or (0,))) for c in ordered)


def logical_size(monitor):
    return int(monitor["width"]), int(monitor["height"]), float(monitor.get("scale") or 1)


def monitor_list(monitors, clients, remembered=None):
    remembered = remembered if remembered is not None else {}
    result = []
    for m in sorted(monitors, key=lambda m: (int(m.get("x", 0)), int(m.get("y", 0)))):
        name = m["name"]
        tags = active_tags(m)
        if in_overview(m) or not tags:
            tags = remembered.get(name, (1,))
        else:
            remembered[name] = tags
        visible = [c for c in clients if client_visible(c, name, tags)]
        occupied = frozenset(int(t["index"]) for t in m.get("tags") or () if int(t.get("client_count") or 0) > 0)
        width, height, scale = logical_size(m)
        result.append(Monitor(name=name, x=int(m.get("x", 0)), y=int(m.get("y", 0)), width=width, height=height,
                              scale=scale, focused=bool(m.get("active")), active=min(tags), windows=len(visible),
                              fullscreen=any(c.get("is_fullscreen") for c in visible), occupied=occupied))
    return tuple(result)


def make_state(monitors, clients, remembered=None):
    overview = any(in_overview(m) for m in monitors)
    focused_raw = next((m for m in monitors if m.get("active")), monitors[0] if monitors else None)
    layout = keyboard.short_name(focused_raw.get("keyboardlayout") or "") if focused_raw else ""
    result = monitor_list(monitors, clients, remembered)
    focused = next((m for m in result if m.focused), result[0] if result else None)
    if focused is None:
        return State(active=1, occupied=set(), windows=0, fullscreen=False, clients=window_list(clients),
                     overview=overview, layout=layout)
    return State(active=focused.active, occupied=set(focused.occupied), windows=focused.windows,
                 fullscreen=focused.fullscreen, clients=window_list(clients), monitors=result, overview=overview,
                 layout=layout)


def focused_scale(monitors):
    chosen = next((m for m in monitors if m.get("active")), monitors[0] if monitors else None)
    try:
        return logical_size(chosen)[2] if chosen else None
    except (KeyError, TypeError, ValueError):
        return None


def goto_command(index, output=None):
    if output:
        return f"dispatch viewcrossmon,{int(index)},{output}"
    return f"dispatch view,{int(index)},0"


def _socket_path():
    return os.environ.get("MANGO_INSTANCE_SIGNATURE")


def _request(command):
    path = _socket_path()
    if not path:
        raise OSError("MANGO_INSTANCE_SIGNATURE не задан")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(REQUEST_TIMEOUT)
        s.connect(path)
        s.sendall((command + "\n").encode())
        line = s.makefile("r", encoding="utf-8", errors="replace").readline()
    reply = json.loads(line)
    if isinstance(reply, dict) and "error" in reply:
        raise ValueError(reply["error"])
    return reply


def _query(what):
    reply = _request(f"get {what}")
    return reply["monitors"] if what == "all-monitors" else reply["clients"]


class MangoWorkspaces:
    per_output_workspaces = True
    relax_layer_keyboard = False

    def __init__(self):
        self.state = None
        self._subscribers = []
        self._events = debug.Rate("mango", 20)
        self._dirty = threading.Event()
        self._coalesced = 0
        self._last_event = ""
        self._data = {"all-monitors": None, "all-clients": None}
        self._keys = {}
        self._remembered = {}

    def subscribe(self, callback):
        self._subscribers.append(callback)
        if self.state is not None:
            callback(self.state)

    def start(self):
        threading.Thread(target=self._refresh_loop, daemon=True).start()
        for stream in STREAMS:
            threading.Thread(target=self._watch, args=(stream,), daemon=True).start()

    def apply_layer_rules(self):
        pass

    def goto(self, workspace_id, output=None):
        threading.Thread(target=self._goto, args=(int(workspace_id), output), daemon=True).start()

    def _goto(self, index, output):
        try:
            _request(goto_command(index, output))
        except (OSError, ValueError, TypeError) as e:
            debug.log("mango", f"переключение на тег {index} ({output}) не удалось: {e!r}")

    def output_scale(self):
        try:
            return focused_scale(_query("all-monitors"))
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def monitors(self):
        try:
            return monitor_list(_query("all-monitors"), _query("all-clients"), dict(self._remembered))
        except (OSError, ValueError, KeyError, TypeError):
            return ()

    def _refresh_loop(self):
        while True:
            self._dirty.wait()
            time.sleep(COALESCE_SECONDS)
            self._dirty.clear()
            coalesced, self._coalesced = self._coalesced, 0
            monitors, clients = self._data["all-monitors"], self._data["all-clients"]
            if monitors is None or clients is None:
                continue
            started = time.monotonic()
            try:
                state = make_state(monitors, clients, self._remembered)
            except (ValueError, KeyError, TypeError) as e:
                debug.log("mango", f"refresh упал: {e!r}")
                continue
            debug.log("mango", f"refresh {(time.monotonic() - started) * 1000:.1f} мс после "
                               f"{self._last_event or 'старта'}, схлопнуто событий: {coalesced}")
            GLib.idle_add(self._emit, state)

    def _emit(self, state):
        if state == self.state:
            return False
        self.state = state
        for callback in self._subscribers:
            callback(state)
        return False

    def _accept(self, stream, message):
        items = message["monitors"] if stream == "all-monitors" else message["clients"]
        key = tuple(map(monitor_key if stream == "all-monitors" else client_key, items))
        self._data[stream] = items
        if self._keys.get(stream) == key:
            return False
        self._keys[stream] = key
        return True

    def _watch(self, stream):
        while True:
            path = _socket_path()
            if path:
                try:
                    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                        s.connect(path)
                        s.sendall(f"watch {stream}\n".encode())
                        self._keys.pop(stream, None)
                        for line in s.makefile("r", encoding="utf-8", errors="replace"):
                            try:
                                changed = self._accept(stream, json.loads(line))
                            except (ValueError, KeyError, TypeError, AttributeError):
                                continue
                            self._events.hit(stream)
                            if changed:
                                self._last_event = stream
                                self._coalesced += 1
                                self._dirty.set()
                except OSError as e:
                    debug.log("mango", f"поток {stream}: {e}")
            time.sleep(1)


def create():
    return MangoWorkspaces()
