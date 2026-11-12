import json
import os
import socket
import subprocess
import threading
import time

from gi.repository import GLib

from modules.common import debug
from modules.parsing import keyboard
from modules.rules.base import Monitor, State


REFRESH_EVENTS = frozenset(("workspace", "createworkspace", "destroyworkspace", "focusedmon",
                            "openwindow", "closewindow", "movewindow", "fullscreen", "moveworkspace",
                            "monitoradded", "monitorremoved", "monitoraddedv2", "monitorremovedv2"))

GOTO_DIALECTS = {
    "lua": "dispatch hl.dsp.focus({{ workspace = {id} }})",
    "legacy": "dispatch workspace {id}",
}

LAYER_RULE_DIALECTS = {
    "lua": 'eval hl.layer_rule({ name = "leech-no-anim", match = { namespace = "^leech-.*$" }, no_anim = true })',
    "legacy": "keyword layerrule noanim,^(leech-.*)$",
}
LAYER_RULE_EVENTS = frozenset(("configreloaded",))
LAYOUT_EVENT = "activelayout"

COALESCE_SECONDS = 0.03
REQUEST_TIMEOUT = 2


def event_name(line):
    return line.partition(">>")[0].strip()


def needs_refresh(line):
    return event_name(line) in REFRESH_EVENTS


def reply_ok(reply):
    reply = reply.strip()
    return bool(reply) and not reply.startswith("error") and reply != "unknown request"


def window_list(clients):
    return tuple((c.get("class") or c.get("initialClass") or "", int(c.get("workspace", {}).get("id", 0)))
                 for c in clients if c.get("mapped", True))


def monitor_list(monitors, workspaces=()):
    by_id = {int(w["id"]): w for w in workspaces}
    result = []
    for m in monitors:
        if m.get("disabled"):
            continue
        scale = float(m.get("scale") or 1)
        width, height = int(m["width"]), int(m["height"])
        if int(m.get("transform", 0)) % 2:
            width, height = height, width
        active = int(m.get("activeWorkspace", {}).get("id", 0))
        workspace = by_id.get(active, {})
        result.append(Monitor(name=m["name"], x=int(m["x"]), y=int(m["y"]), width=round(width / scale),
                              height=round(height / scale), scale=scale, focused=bool(m.get("focused")),
                              active=active, windows=int(workspace.get("windows", 0)),
                              fullscreen=bool(workspace.get("hasfullscreen", False))))
    return tuple(result)


def event_layout(line):
    keymap = line.partition(">>")[2].partition(",")[2].strip()
    return keyboard.short_name(keymap)


def main_layout(devices):
    keyboards = devices.get("keyboards") or ()
    chosen = next((k for k in keyboards if k.get("main")), keyboards[0] if keyboards else None)
    return keyboard.short_name(chosen.get("active_keymap", "")) if chosen else ""


def make_state(active, workspaces, clients=(), monitors=(), layout=""):
    return State(
        active=int(active["id"]),
        occupied={int(w["id"]) for w in workspaces},
        windows=int(active.get("windows", 0)),
        fullscreen=bool(active.get("hasfullscreen", False)),
        clients=window_list(clients),
        monitors=monitor_list(monitors, workspaces),
        layout=layout,
    )


def focused_scale(monitors):
    chosen = next((m for m in monitors if m.get("focused")), monitors[0] if monitors else None)
    try:
        return float(chosen["scale"]) if chosen else None
    except (KeyError, TypeError, ValueError):
        return None


def _instance_dir():
    sig = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    if not sig:
        return None
    runtime = os.environ.get("XDG_RUNTIME_DIR", "")
    for base in (os.path.join(runtime, "hypr"), "/tmp/hypr"):
        path = os.path.join(base, sig)
        if os.path.isdir(path):
            return path
    return None


def _socket_request(path, command):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(REQUEST_TIMEOUT)
        s.connect(path)
        s.sendall(command.encode())
        chunks = []
        while chunk := s.recv(65536):
            chunks.append(chunk)
    return b"".join(chunks).decode("utf-8", "replace")


def hyprctl_args(command):
    if command.startswith("j/"):
        return [command[2:], "-j"]
    return command.split()


def _hyprctl(command):
    return subprocess.run(["hyprctl", *hyprctl_args(command)], capture_output=True, text=True,
                          timeout=REQUEST_TIMEOUT).stdout


class HyprlandWorkspaces:
    def __init__(self):
        self.state = None
        self._subscribers = []
        self._events = debug.Rate("hypr", 20)
        self._dirty = threading.Event()
        self._coalesced = 0
        self._last_event = ""
        self._dialect = "lua"
        self._layout = None

    def subscribe(self, callback):
        self._subscribers.append(callback)
        if self.state is not None:
            callback(self.state)

    def start(self):
        self._dirty.set()
        threading.Thread(target=self._refresh_loop, daemon=True).start()
        threading.Thread(target=self._read_events, daemon=True).start()
        self.apply_layer_rules()

    def apply_layer_rules(self):
        threading.Thread(target=self._apply_layer_rules, daemon=True).start()

    def _apply_layer_rules(self):
        order = sorted(LAYER_RULE_DIALECTS, key=lambda dialect: dialect != self._dialect)
        reply = ""
        for dialect in order:
            reply = self._command(LAYER_RULE_DIALECTS[dialect])
            if reply_ok(reply):
                debug.log("hypr", f"правило no_anim для leech-* применено ({dialect})")
                return
        print(f"leech: не удалось отключить анимацию слоёв Hyprland: {reply.strip()[:200]}")

    def goto(self, workspace_id):
        threading.Thread(target=self._goto, args=(int(workspace_id),), daemon=True).start()

    def _goto(self, workspace_id):
        order = sorted(GOTO_DIALECTS, key=lambda dialect: dialect != self._dialect)
        reply = ""
        for dialect in order:
            reply = self._command(GOTO_DIALECTS[dialect].format(id=workspace_id))
            if reply_ok(reply):
                self._dialect = dialect
                return
        debug.log("hypr", f"переключение на воркспейс {workspace_id} не удалось: {reply.strip()[:200]}")

    def output_scale(self):
        try:
            monitors = self._query("monitors")
        except ValueError:
            return None
        return focused_scale(monitors)

    def monitors(self):
        try:
            return monitor_list(self._query("monitors"), self._query("workspaces"))
        except (ValueError, KeyError, TypeError):
            return ()

    def _request_path(self):
        base = _instance_dir()
        return os.path.join(base, ".socket.sock") if base else None

    def _command(self, command):
        path = self._request_path()
        if path:
            try:
                return _socket_request(path, command)
            except OSError as e:
                debug.log("hypr", f"сокет запросов недоступен ({e}), использую hyprctl")
        try:
            return _hyprctl(command)
        except (OSError, subprocess.SubprocessError) as e:
            debug.log("hypr", f"hyprctl {command}: {e!r}")
            return ""

    def _query(self, what):
        return json.loads(self._command(f"j/{what}"))

    def _refresh_loop(self):
        while True:
            self._dirty.wait()
            time.sleep(COALESCE_SECONDS)
            self._dirty.clear()
            coalesced, self._coalesced = self._coalesced, 0
            started = time.monotonic()
            if self._layout is None:
                try:
                    self._layout = main_layout(self._query("devices"))
                except (ValueError, KeyError, TypeError, AttributeError) as e:
                    debug.log("hypr", f"раскладка не прочитана: {e!r}")
            try:
                state = make_state(self._query("activeworkspace"), self._query("workspaces"), self._query("clients"),
                                   self._query("monitors"), self._layout or "")
            except (ValueError, KeyError, TypeError) as e:
                debug.log("hypr", f"refresh упал: {e!r}")
                continue
            debug.log("hypr", f"refresh {(time.monotonic() - started) * 1000:.1f} мс после "
                              f"{self._last_event or 'старта'}, схлопнуто событий: {coalesced}")
            GLib.idle_add(self._emit, state)

    def _emit(self, state):
        if state == self.state:
            return False
        self.state = state
        for callback in self._subscribers:
            callback(state)
        return False

    def _read_events(self):
        while True:
            base = _instance_dir()
            if base:
                try:
                    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                        s.connect(os.path.join(base, ".socket2.sock"))
                        self._dirty.set()
                        for line in s.makefile("r", encoding="utf-8", errors="replace"):
                            name = event_name(line)
                            self._events.hit(name)
                            if name == LAYOUT_EVENT:
                                self._layout = event_layout(line)
                                self._last_event = name
                                self._dirty.set()
                            if name in LAYER_RULE_EVENTS:
                                self.apply_layer_rules()
                            if name in REFRESH_EVENTS:
                                self._last_event = name
                                self._coalesced += 1
                                self._dirty.set()
                except OSError as e:
                    debug.log("hypr", f"сокет событий: {e}")
            time.sleep(1)


def create():
    return HyprlandWorkspaces()
