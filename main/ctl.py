#!/usr/bin/env python3
import sys
from pathlib import Path

sys.pycache_prefix = str(Path(__file__).resolve().parents[1] / ".shellcache")

USAGE = """python ctl.py toggle cc | cc-full | launcher | wallpaper | battery | power | player
python ctl.py close
python ctl.py apps [запрос]
python ctl.py pin | unpin <приложение>
python ctl.py pins
python ctl.py volume up | down | mute
python ctl.py brightness up | down
python ctl.py stats
python ctl.py reload"""
import os
import socket

args = sys.argv[1:]


def list_apps(query):
    from gi.repository import Gio
    query = query.lower()
    for info in sorted(Gio.AppInfo.get_all(), key=lambda i: (i.get_name() or "").lower()):
        if not info.should_show():
            continue
        app_id, name = info.get_id() or "", info.get_name() or ""
        if query in app_id.lower() or query in name.lower():
            print(f"{app_id:45} {name}")


if args[:1] == ["apps"]:
    list_apps(" ".join(args[1:]))
    sys.exit(0)

if not args:
    sys.exit(USAGE)

path = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "leech.sock")
try:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(3)
        s.connect(path)
        s.sendall(" ".join(args).encode())
        s.shutdown(socket.SHUT_WR)
        reply = b""
        while chunk := s.recv(4096):
            reply += chunk
except OSError as e:
    sys.exit(f"leech не запущен? ({e})")

text = reply.decode("utf-8", "replace").strip()
if text and text != "ok":
    print(text)
