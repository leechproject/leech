import subprocess
from dataclasses import dataclass

from gi.repository import Gio

from modules import config

def normalize(app_id):
    app_id = app_id.strip()
    return app_id if app_id.endswith(".desktop") else app_id + ".desktop"


def lookup(app_id):
    try:
        return Gio.DesktopAppInfo.new(normalize(app_id))
    except TypeError:
        return None


def class_entries():
    entries = []
    for info in Gio.AppInfo.get_all():
        desktop_id = info.get_id()
        if desktop_id and isinstance(info, Gio.DesktopAppInfo):
            entries.append((desktop_id, info.get_startup_wm_class(), info.get_executable()))
    return entries


def find_by_name(name):
    wanted = (name or "").strip().lower()
    if not wanted:
        return None
    for info in Gio.AppInfo.get_all():
        stem = (info.get_id() or "").lower().removesuffix(".desktop")
        if wanted in (stem, (info.get_name() or "").lower()):
            return info
    return None


def launch(info):
    try:
        subprocess.Popen(["gio", "launch", info.get_filename()], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        info.launch([], None)


def read_pinned():
    try:
        lines = config.PINNED_FILE.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    ids = []
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#") and normalize(line) not in ids:
            ids.append(normalize(line))
    return ids


def write_pinned(ids):
    config.STATES_DIR.mkdir(parents=True, exist_ok=True)
    config.PINNED_FILE.write_text("".join(f"{i}\n" for i in ids), encoding="utf-8")


def ensure_pinned_file():
    if not config.PINNED_FILE.exists():
        write_pinned([])


def read_hidden():
    try:
        lines = config.HIDDEN_FILE.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    ids = []
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#") and normalize(line) not in ids:
            ids.append(normalize(line))
    return ids


def write_hidden(ids):
    config.STATES_DIR.mkdir(parents=True, exist_ok=True)
    config.HIDDEN_FILE.write_text("".join(f"{i}\n" for i in ids), encoding="utf-8")


@dataclass
class AppEntry:
    id: str
    name: str
    info: object


def all_entries():
    entries = []
    for info in Gio.AppInfo.get_all():
        app_id = info.get_id() or ""
        if app_id and info.should_show():
            entries.append(AppEntry(app_id, info.get_display_name() or info.get_name() or app_id, info))
    entries.sort(key=lambda e: e.name.casefold())
    return entries


def read_liked():
    try:
        lines = config.LIKED_FILE.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    ids = []
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#") and normalize(line) not in ids:
            ids.append(normalize(line))
    return ids


def write_liked(ids):
    config.STATES_DIR.mkdir(parents=True, exist_ok=True)
    config.LIKED_FILE.write_text("".join(f"{i}\n" for i in ids), encoding="utf-8")
