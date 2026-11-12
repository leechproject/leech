import subprocess
from pathlib import Path

_SYS = Path("/sys")


def _read(path):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


def wifi_enabled():
    found = False
    for entry in sorted((_SYS / "class/rfkill").glob("rfkill*")):
        if _read(entry / "type") != "wlan":
            continue
        found = True
        if _read(entry / "soft") == "0" and _read(entry / "hard") == "0":
            return True
    return False if found else None


def connection():
    wired = wireless = False
    for iface in sorted((_SYS / "class/net").iterdir()):
        if iface.name == "lo" or _read(iface / "operstate") != "up":
            continue
        if (iface / "wireless").exists():
            wireless = True
        elif (iface / "device").exists():
            wired = True
    return "ethernet" if wired else ("wifi" if wireless else None)


def set_wifi(on):
    try:
        subprocess.Popen(["rfkill", "unblock" if on else "block", "wifi"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as e:
        print(f"rfkill: {e}")
