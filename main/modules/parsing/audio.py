import re
import shutil
import subprocess
import threading

from gi.repository import GLib

_SINK_WPCTL = "@DEFAULT_AUDIO_SINK@"
_SINK_PACTL = "@DEFAULT_SINK@"


def parse_wpctl(output):
    match = re.search(r"Volume:\s*([0-9.]+)", output)
    if not match:
        return None
    return round(float(match.group(1)) * 100), "[MUTED]" in output


def parse_pactl_volume(output):
    match = re.search(r"(\d+)%", output)
    return int(match.group(1)) if match else None


def parse_pactl_mute(output):
    return "yes" in output.lower()


def backend():
    if shutil.which("wpctl"):
        return "wpctl"
    if shutil.which("pactl"):
        return "pactl"
    return None


def _run(*command):
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=3).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def read():
    tool = backend()
    if tool == "wpctl":
        return parse_wpctl(_run("wpctl", "get-volume", _SINK_WPCTL))
    if tool == "pactl":
        volume = parse_pactl_volume(_run("pactl", "get-sink-volume", _SINK_PACTL))
        if volume is None:
            return None
        return volume, parse_pactl_mute(_run("pactl", "get-sink-mute", _SINK_PACTL))
    return None


def write_volume(percent):
    percent = max(0, min(100, int(percent)))
    tool = backend()
    if tool == "wpctl":
        _run("wpctl", "set-volume", _SINK_WPCTL, f"{percent}%")
    elif tool == "pactl":
        _run("pactl", "set-sink-volume", _SINK_PACTL, f"{percent}%")


def toggle_mute():
    tool = backend()
    if tool == "wpctl":
        _run("wpctl", "set-mute", _SINK_WPCTL, "toggle")
    elif tool == "pactl":
        _run("pactl", "set-sink-mute", _SINK_PACTL, "toggle")


def in_thread(work, done=None):
    def run():
        result = work()
        if done is not None:
            GLib.idle_add(lambda: (done(result), False)[1])
    threading.Thread(target=run, daemon=True).start()
