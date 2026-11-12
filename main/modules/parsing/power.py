import os
import shutil
import subprocess
import threading
import time
from pathlib import Path

from gi.repository import Gio, GLib

from modules.common import debug

PROFILES = ("power-saver", "balanced", "performance")

_LOGIND = ("org.freedesktop.login1", "/org/freedesktop/login1", "org.freedesktop.login1.Manager")
_VERBS = {"Reboot": "reboot", "PowerOff": "poweroff", "Suspend": "suspend"}
_TIMEOUT_MS = 10000
DRY_RUN = os.environ.get("LEECH_POWER_DRYRUN", "")
LOG_FILE = Path.home() / ".cache" / "leech" / "power.log"

_error_handler = None


def set_error_handler(handler):
    global _error_handler
    _error_handler = handler


def _write_log(message):
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")
    except OSError:
        pass


def _report(message):
    print(f"power: {message}")
    debug.log("power", message)
    _write_log(message)
    if _error_handler is not None:
        _error_handler(message)


def fallback_command(verb):
    if os.path.isdir("/run/systemd/system") and shutil.which("systemctl"):
        return ["systemctl", verb]
    if shutil.which("loginctl"):
        return ["loginctl", verb]
    return None


def _fallback(method, reason):
    command = fallback_command(_VERBS[method])
    if command is None:
        _report(f"{method} не удался ({reason}), запасной команды нет")
        return
    debug.log("power", f"{method} через logind не удался ({reason}), пробую {' '.join(command)}")
    _write_log(f"{method} через logind не удался ({reason}), пробую {' '.join(command)}")
    if DRY_RUN:
        _report(f"{method} не удался: logind — {reason}; dry-run, {' '.join(command)} не запускался")
        return

    def work():
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError) as e:
            GLib.idle_add(_report, f"{' '.join(command)}: {e}")
            return
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip() or f"код {result.returncode}"
            GLib.idle_add(_report, f"{method} не удался: logind — {reason}; {' '.join(command)} — {detail}")

    threading.Thread(target=work, daemon=True).start()


def _logind(method):
    debug.log("power", f"logind {method}")

    def done(connection, result, _data):
        try:
            reply = connection.call_finish(result)
            debug.log("power", f"logind {method}: принято {reply.unpack() if reply else ''}")
        except GLib.Error as e:
            _fallback(method, e.message)

    try:
        bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    except GLib.Error as e:
        _fallback(method, f"нет system bus: {e.message}")
        return
    if DRY_RUN:
        name, args = f"Can{method}{'Fail' if DRY_RUN == 'fail' else ''}", None
    else:
        name, args = method, GLib.Variant("(b)", (True,))
    bus.call(*_LOGIND, name, args, None,
             Gio.DBusCallFlags.ALLOW_INTERACTIVE_AUTHORIZATION, _TIMEOUT_MS, None, done, None)


def reboot():
    _logind("Reboot")


def poweroff():
    _logind("PowerOff")


def suspend():
    _logind("Suspend")


def get_profile(callback):
    def work():
        try:
            out = subprocess.run(["powerprofilesctl", "get"], capture_output=True,
                                 text=True, timeout=2).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            out = ""
        def deliver():
            callback(out or None)
            return False
        GLib.idle_add(deliver)
    threading.Thread(target=work, daemon=True).start()


def set_profile(profile):
    try:
        subprocess.Popen(["powerprofilesctl", "set", profile],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as e:
        print(f"powerprofilesctl: {e}")
