import datetime
import json
import os
import shutil
import signal
import subprocess
import threading
import time
from pathlib import Path

import cairo
import gi

gi.require_version("GtkLayerShell", "0.1")
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import GtkLayerShell, Gtk, Gdk, GLib

from fabric.widgets.window import Window

from modules import config
from modules.common.surface import init_layer

_MIN_SELECTION = 5


def _stamp():
    return datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


RECORDER_NAME = "gpu-screen-recorder"
STATE_FILE = config.IPC_SOCKET.with_name("leech-record.json")


def _is_recorder(pid):
    try:
        with open(f"/proc/{pid}/stat") as stat:
            if stat.read().rsplit(")", 1)[1].split()[0] == "Z":
                return False
        with open(f"/proc/{pid}/cmdline", "rb") as cmdline:
            return os.path.basename(cmdline.read().split(b"\0")[0]).decode() == RECORDER_NAME
    except (OSError, IndexError, UnicodeDecodeError):
        return False


def _alive(pid):
    try:
        done, _ = os.waitpid(pid, os.WNOHANG)
        if done == pid:
            return False
    except ChildProcessError:
        pass
    return _is_recorder(pid)


class Recorder:
    def __init__(self):
        self._proc = None
        self._pid = None
        self.path = None
        self.started_at = 0.0
        self.paused = False
        self._paused_at = 0.0
        self._paused_total = 0.0
        self.audio = False
        self.microphone = False
        self._restore()

    def active(self):
        if self._pid is None:
            return False
        if self._proc.poll() is None if self._proc is not None else _alive(self._pid):
            return True
        self._pid = self._proc = None
        self._forget()
        return False

    def start(self, audio=False, microphone=False):
        if self.active():
            return True
        if shutil.which(RECORDER_NAME) is None:
            print("запись экрана: gpu-screen-recorder не найден")
            return False
        config.RECORD_DIR.mkdir(parents=True, exist_ok=True)
        self.path = config.RECORD_DIR / f"Recording_{_stamp()}.mp4"
        command = [RECORDER_NAME, "-w", "screen", "-f", "60"]
        sources = [name for name, on in (("default_output", audio), ("default_input", microphone)) if on]
        if sources:
            command += ["-a", "|".join(sources)]
        proc = subprocess.Popen(command + ["-o", str(self.path)], start_new_session=True,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self._proc = proc
        self._pid = proc.pid
        self.started_at = time.monotonic()
        self.paused = False
        self._paused_total = 0.0
        self.audio, self.microphone = audio, microphone
        self._save()
        return True

    def toggle_pause(self):
        if not self.active():
            return
        os.kill(self._pid, signal.SIGUSR2)
        now = time.monotonic()
        if self.paused:
            self._paused_total += now - self._paused_at
        else:
            self._paused_at = now
        self.paused = not self.paused
        self._save()

    def elapsed(self):
        end = self._paused_at if self.paused else time.monotonic()
        return max(0.0, end - self.started_at - self._paused_total)

    def stop(self):
        if self.active():
            os.kill(self._pid, signal.SIGINT)

    def _save(self):
        state = {"pid": self._pid, "path": str(self.path), "started_at": self.started_at,
                 "paused": self.paused, "paused_at": self._paused_at, "paused_total": self._paused_total,
                 "audio": self.audio, "microphone": self.microphone}
        try:
            STATE_FILE.write_text(json.dumps(state))
        except OSError as e:
            print(f"запись экрана: не удалось сохранить состояние: {e}")

    def _forget(self):
        try:
            STATE_FILE.unlink()
        except OSError:
            pass

    def _restore(self):
        try:
            state = json.loads(STATE_FILE.read_text())
            pid = int(state["pid"])
        except (OSError, ValueError, KeyError, TypeError):
            return
        if not _alive(pid):
            self._forget()
            return
        self._pid = pid
        self.path = Path(state.get("path", ""))
        self.started_at = float(state.get("started_at", time.monotonic()))
        self.paused = bool(state.get("paused"))
        self._paused_at = float(state.get("paused_at", 0.0))
        self._paused_total = float(state.get("paused_total", 0.0))
        self.audio = bool(state.get("audio"))
        self.microphone = bool(state.get("microphone"))


def take_screenshot(region, on_done):
    if shutil.which("grim") is None:
        print("скриншот: grim не найден")
        on_done(None)
        return
    config.SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = config.SCREENSHOT_DIR / f"Screenshot_{_stamp()}.png"
    cmd = ["grim"]
    if region:
        x, y, w, h = region
        cmd += ["-g", f"{x},{y} {w}x{h}"]
    cmd.append(str(path))
    proc = subprocess.Popen(cmd, start_new_session=True,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def wait():
        code = proc.wait()
        GLib.idle_add(lambda: (on_done(path if code == 0 else None), False)[1])
    threading.Thread(target=wait, daemon=True).start()


class ScreenshotOverlay(Window):
    def __init__(self, on_result):
        super().__init__(name="screenshot-overlay", visible=False, all_visible=False)
        self._on_result = on_result
        self._start = self._end = None
        self._finished = False

        visual = self.get_screen().get_rgba_visual()
        if visual:
            self.set_visual(visual)
        self.set_app_paintable(True)

        init_layer(self)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
        for edge in (GtkLayerShell.Edge.TOP, GtkLayerShell.Edge.RIGHT,
                     GtkLayerShell.Edge.BOTTOM, GtkLayerShell.Edge.LEFT):
            GtkLayerShell.set_anchor(self, edge, True)
        GtkLayerShell.set_exclusive_zone(self, -1)
        if hasattr(GtkLayerShell, "set_keyboard_mode"):
            GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.EXCLUSIVE)
        else:
            GtkLayerShell.set_keyboard_interactivity(self, True)

        area = Gtk.DrawingArea()
        area.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK
                        | Gdk.EventMask.POINTER_MOTION_MASK)
        area.connect("draw", self._on_draw)
        area.connect("button-press-event", self._on_press)
        area.connect("motion-notify-event", self._on_motion)
        area.connect("button-release-event", self._on_release)
        self.add(area)
        self._area = area
        self.connect("key-press-event", self._on_key)
        self.show_all()


    def _on_key(self, _w, event):
        if event.keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            self._finish("full", None)
        elif event.keyval == Gdk.KEY_Escape:
            self._finish("cancel", None)
        return True

    def _on_press(self, _w, event):
        if event.button == 3:
            self._finish("full", None)
        elif event.button == 1:
            self._start = self._end = (event.x, event.y)
        return True

    def _on_motion(self, _w, event):
        if self._start is not None:
            self._end = (event.x, event.y)
            self._area.queue_draw()
        return True

    def _on_release(self, _w, event):
        if event.button != 1 or self._start is None:
            return True
        x, y, w, h = self._rect()
        if w < _MIN_SELECTION or h < _MIN_SELECTION:
            self._start = self._end = None
            self._area.queue_draw()
        else:
            self._finish("area", (round(x), round(y), round(w), round(h)))
        return True

    def _rect(self):
        (x1, y1), (x2, y2) = self._start, self._end
        return min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1)

    def _finish(self, kind, region):
        if self._finished:
            return
        self._finished = True
        self.destroy()
        self._on_result(kind, region)


    def _on_draw(self, _area, cr):
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0.25)
        cr.paint()
        if self._start is not None:
            x, y, w, h = self._rect()
            cr.set_operator(cairo.OPERATOR_CLEAR)
            cr.rectangle(x, y, w, h)
            cr.fill()
            cr.set_operator(cairo.OPERATOR_OVER)
            cr.set_source_rgba(1, 1, 1, 0.9)
            cr.set_line_width(1)
            cr.rectangle(x + 0.5, y + 0.5, w, h)
            cr.stroke()
        return False
