import subprocess
import threading
from dataclasses import dataclass

from gi.repository import GLib

TIMEOUT = 10
CONNECT_TIMEOUT = 45
SCAN_TIMEOUT = 30


@dataclass(frozen=True)
class Network:
    ssid: str
    signal: int
    secure: bool
    active: bool
    known: str | None


@dataclass(frozen=True)
class Wired:
    device: str
    name: str


def split_terse(line):
    fields, current, escaped = [], [], False
    for char in line:
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == ":":
            fields.append("".join(current))
            current = []
        else:
            current.append(char)
    fields.append("".join(current))
    return fields


def parse_networks(text, known):
    best = {}
    for line in text.splitlines():
        fields = split_terse(line)
        if len(fields) < 4 or not fields[1]:
            continue
        in_use, ssid, signal, security = fields[:4]
        try:
            strength = int(signal)
        except ValueError:
            strength = 0
        active = in_use.strip() == "*"
        old = best.get(ssid)
        secure = bool(security.strip()) and security.strip() != "--"
        if old is None or active or (not old.active and strength > old.signal):
            best[ssid] = Network(ssid, strength, secure, active or (old is not None and old.active), known.get(ssid))
    return sorted(best.values(), key=lambda n: (not n.active, n.known is None, -n.signal, n.ssid.casefold()))


def parse_wired(text):
    for line in text.splitlines():
        fields = split_terse(line)
        if len(fields) >= 4 and fields[1] == "ethernet" and fields[2] == "connected":
            return Wired(fields[0], fields[3] or fields[0])
    return None


def _run(args, timeout=TIMEOUT):
    try:
        done = subprocess.run(["nmcli", *args], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as e:
        return False, str(e)
    if done.returncode != 0:
        return False, (done.stderr or done.stdout).strip().removeprefix("Error: ")
    return True, done.stdout


def _known():
    ok, out = _run(["-t", "-f", "NAME,TYPE", "connection", "show"])
    if not ok:
        return {}
    known = {}
    for line in out.splitlines():
        fields = split_terse(line)
        if len(fields) >= 2 and fields[1] == "802-11-wireless":
            ok, ssid = _run(["-g", "802-11-wireless.ssid", "connection", "show", "id", fields[0]])
            ssid = split_terse(ssid.strip())[0] if ok else ""
            if ssid:
                known.setdefault(ssid, fields[0])
    return known


def read():
    ok, out = _run(["-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device"])
    wired = parse_wired(out) if ok else None
    if wired is not None:
        return wired, []
    ok, out = _run(["-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "device", "wifi", "list", "--rescan", "no"])
    return None, parse_networks(out, _known()) if ok else []


MISSING = ("not found", "no network", "no such")


def needs_password(network, message):
    text = message.casefold()
    return network.secure and not any(marker in text for marker in MISSING)


def _store_password(name, password):
    ok, out = _run(["-g", "802-11-wireless-security.key-mgmt", "connection", "show", "id", name])
    args = ["connection", "modify", "id", name]
    if not ok or not out.strip():
        args += ["802-11-wireless-security.key-mgmt", "wpa-psk"]
    args += ["802-11-wireless-security.psk", password, "802-11-wireless-security.psk-flags", "0"]
    return _run(args)


def connect(network, password=None):
    if network.known:
        if password is not None:
            ok, message = _store_password(network.known, password)
            if not ok:
                return ok, message
        return _run(["connection", "up", "id", network.known], CONNECT_TIMEOUT)
    args = ["device", "wifi", "connect", network.ssid]
    if password is not None:
        args += ["password", password]
    return _run(args, CONNECT_TIMEOUT)


def disconnect(network):
    if network.known:
        return _run(["connection", "down", "id", network.known])
    return False, "no saved connection"


def forget(network):
    if network.known:
        return _run(["connection", "delete", "id", network.known])
    return False, "no saved connection"


def rescan():
    # `list --rescan yes` returns only after NetworkManager finishes the scan,
    # unlike `device wifi rescan`, which returns as soon as the request is queued.
    return _run(["-t", "-f", "SSID", "device", "wifi", "list", "--rescan", "yes"], SCAN_TIMEOUT)


def in_thread(work, done=None):
    def run():
        result = work()
        if done is not None:
            GLib.idle_add(lambda: (done(result), False)[1])
    threading.Thread(target=run, daemon=True).start()
