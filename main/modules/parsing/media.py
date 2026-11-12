import hashlib
import os
import threading
import urllib.request
from dataclasses import dataclass
from urllib.parse import unquote, urlparse

from gi.repository import Gio, GLib, GdkPixbuf

NO_AUDIO = "No audio"
_PREFIX = "org.mpris.MediaPlayer2."
_PLAYER = "org.mpris.MediaPlayer2.Player"
_PROPS = "org.freedesktop.DBus.Properties"
_PATH = "/org/mpris/MediaPlayer2"
_CACHE = os.path.join(os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), "leech")
_COVER_MAX = 256


@dataclass(frozen=True)
class Track:
    title: str = NO_AUDIO
    artist: str = ""
    playing: bool = False
    available: bool = False
    length: int = 0
    trackid: str = ""
    art: str = ""


def pick_player(players):
    for wanted in ("Playing", "Paused"):
        for player in players:
            if player[1] == wanted:
                return player
    return None


def art_path(url):
    if url.startswith("file://"):
        return unquote(urlparse(url).path)
    return None


def make_track(player):
    if player is None:
        return Track()
    _, status, metadata = player
    artist = metadata.get("xesam:artist", "")
    if isinstance(artist, (list, tuple)):
        artist = ", ".join(str(a) for a in artist)
    return Track(title=metadata.get("xesam:title") or "Unknown", artist=str(artist), playing=status == "Playing",
                 available=True, length=int(metadata.get("mpris:length", 0) or 0),
                 trackid=str(metadata.get("mpris:trackid", "")), art=metadata.get("mpris:artUrl", ""))


class Media:
    def __init__(self):
        self._subscribers = []
        self._pending = False
        self._bus = None
        self._player = None
        self._generation = 0
        self.track = Track()
        self.cover = None

    def subscribe(self, callback):
        self._subscribers.append(callback)
        callback(self.track, self.cover)

    def start(self):
        try:
            self._bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        except GLib.Error as e:
            print(f"media: нет session bus ({e.message})")
            return
        flags = Gio.DBusSignalFlags.NONE
        self._bus.signal_subscribe(None, _PROPS, "PropertiesChanged", _PATH, _PLAYER, flags, self._on_signal, None)
        self._bus.signal_subscribe("org.freedesktop.DBus", "org.freedesktop.DBus", "NameOwnerChanged",
                                   "/org/freedesktop/DBus", None, flags, self._on_owner_changed, None)
        self.refresh()


    def _on_signal(self, *_):
        self.refresh()

    def _on_owner_changed(self, _conn, _sender, _path, _iface, _signal, params, *_):
        try:
            name = params.unpack()[0]
        except (IndexError, TypeError):
            return
        if name.startswith(_PREFIX):
            self.refresh()

    def refresh(self):
        if self._pending or self._bus is None:
            return
        self._pending = True
        GLib.timeout_add(150, self._query)


    def _call(self, name, path, iface, method, params, reply_type, callback):
        def finished(bus, result, _data):
            try:
                reply = bus.call_finish(result).unpack()
            except GLib.Error:
                reply = None
            callback(reply)
        self._bus.call(name, path, iface, method, params, GLib.VariantType(reply_type) if reply_type else None,
                       Gio.DBusCallFlags.NONE, 800, None, finished, None)

    def _query(self):
        self._pending = False
        self._generation += 1
        generation = self._generation
        self._call("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "ListNames",
                   None, "(as)", lambda reply: self._on_names(generation, reply))
        return False

    def _on_names(self, generation, reply):
        if generation != self._generation:
            return
        names = [n for n in (reply[0] if reply else []) if n.startswith(_PREFIX)]
        if not names:
            self._apply([])
            return
        results, waiting = [], [len(names)]

        def got(name, answer):
            if generation != self._generation:
                return
            if answer:
                props = answer[0]
                results.append((name, props.get("PlaybackStatus", ""), props.get("Metadata", {})))
            waiting[0] -= 1
            if waiting[0] == 0:
                self._apply(results)

        for name in names:
            self._call(name, _PATH, _PROPS, "GetAll", GLib.Variant("(s)", (_PLAYER,)), "(a{sv})",
                       lambda answer, n=name: got(n, answer))

    def _apply(self, players):
        chosen = pick_player(players)
        self._player = chosen[0] if chosen else None
        track = make_track(chosen)
        old = self.track
        if track == old:
            return
        same_cover = track.art == old.art and track.art != ""
        self.track = track
        if not same_cover:
            self.cover = None
            self._load_cover(track)
        self._notify()

    def _notify(self):
        for callback in self._subscribers:
            callback(self.track, self.cover)


    def play_pause(self):
        if self._bus is None or self._player is None:
            return
        self._bus.call(self._player, _PATH, _PLAYER, "PlayPause", None, None,
                       Gio.DBusCallFlags.NONE, -1, None, None, None)

    def request_position(self, callback):
        if self._bus is None or self._player is None:
            callback(None)
            return
        self._call(self._player, _PATH, _PROPS, "Get", GLib.Variant("(ss)", (_PLAYER, "Position")), "(v)",
                   lambda reply: callback(int(reply[0]) if reply else None))

    def seek(self, fraction):
        if self._bus is None or self._player is None or self.track.length <= 0:
            return
        target = int(max(0.0, min(1.0, fraction)) * self.track.length)
        try:
            params = GLib.Variant("(ox)", (self.track.trackid, target))
        except (TypeError, ValueError):
            return
        self._bus.call(self._player, _PATH, _PLAYER, "SetPosition", params, None,
                       Gio.DBusCallFlags.NONE, 800, None, None, None)


    def _load_cover(self, track):
        art = track.art
        if not art:
            return
        threading.Thread(target=self._fetch_cover, args=(track, art), daemon=True).start()

    def _fetch_cover(self, track, art):
        path = art_path(art)
        if path is None and art.startswith(("http://", "https://")):
            os.makedirs(_CACHE, exist_ok=True)
            path = os.path.join(_CACHE, hashlib.sha1(art.encode()).hexdigest())
            try:
                if not os.path.exists(path):
                    with urllib.request.urlopen(art, timeout=3) as resp, open(path, "wb") as f:
                        f.write(resp.read())
            except OSError:
                return
        if path is None:
            return
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, _COVER_MAX, _COVER_MAX, True)
        except GLib.Error:
            return

        def deliver():
            if self.track.art == art:
                self.cover = pixbuf
                self._notify()
            return False
        GLib.idle_add(deliver)
