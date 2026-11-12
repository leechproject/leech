import html
import re
import time
from dataclasses import dataclass
from urllib.parse import unquote, urlparse

from gi.repository import Gio, GLib

from modules.parsing import apps
from modules.common import debug

_PATH = "/org/freedesktop/Notifications"
_IFACE = "org.freedesktop.Notifications"
_XML = """
<node>
  <interface name="org.freedesktop.Notifications">
    <method name="GetCapabilities"><arg direction="out" type="as"/></method>
    <method name="Notify">
      <arg direction="in" type="s" name="app_name"/>
      <arg direction="in" type="u" name="replaces_id"/>
      <arg direction="in" type="s" name="app_icon"/>
      <arg direction="in" type="s" name="summary"/>
      <arg direction="in" type="s" name="body"/>
      <arg direction="in" type="as" name="actions"/>
      <arg direction="in" type="a{sv}" name="hints"/>
      <arg direction="in" type="i" name="expire_timeout"/>
      <arg direction="out" type="u"/>
    </method>
    <method name="CloseNotification"><arg direction="in" type="u" name="id"/></method>
    <method name="GetServerInformation">
      <arg direction="out" type="s"/><arg direction="out" type="s"/>
      <arg direction="out" type="s"/><arg direction="out" type="s"/>
    </method>
    <signal name="NotificationClosed"><arg type="u"/><arg type="u"/></signal>
    <signal name="ActionInvoked"><arg type="u"/><arg type="s"/></signal>
  </interface>
</node>
"""

REASON_EXPIRED, REASON_DISMISSED, REASON_CLOSED = 1, 2, 3
URGENCY_CRITICAL = 2


@dataclass
class Notification:
    id: int
    app_name: str
    summary: str
    body: str
    icon: object
    timeout_ms: int
    urgency: int
    created: float
    local: bool = False
    replaced: bool = False

    @property
    def critical(self):
        return self.urgency == URGENCY_CRITICAL


def _clean(text):
    return html.unescape(re.sub(r"<[^>]+>", "", text or "")).strip()


def resolve_icon(app_name, app_icon, hints):
    entry = hints.get("desktop-entry")
    info = apps.lookup(entry) if entry else None
    if info is None:
        info = apps.find_by_name(app_name)
    if info is not None and info.get_icon() is not None:
        return info.get_icon()

    icon = app_icon or hints.get("image-path") or ""
    if icon.startswith("file://"):
        icon = unquote(urlparse(icon).path)
    if icon.startswith("/"):
        return Gio.FileIcon.new(Gio.File.new_for_path(icon))
    if icon:
        return Gio.ThemedIcon.new(icon)
    return None


class NotificationServer:
    def __init__(self, on_notify, on_close=None):
        self._on_notify = on_notify
        self._on_close = on_close
        self._next_id = 1
        self._conn = None
        self._node = Gio.DBusNodeInfo.new_for_xml(_XML)

    def start(self):
        Gio.bus_own_name(Gio.BusType.SESSION, "org.freedesktop.Notifications",
                         Gio.BusNameOwnerFlags.REPLACE,
                         self._bus_acquired, None, self._name_lost)

    def _bus_acquired(self, conn, _name):
        self._conn = conn
        conn.register_object(_PATH, self._node.interfaces[0], self._method_call, None, None)

    @staticmethod
    def _name_lost(_conn, _name):
        print("уведомления: имя org.freedesktop.Notifications занято другим демоном (mako/dunst/swaync?)")


    def _method_call(self, _conn, _sender, _path, _iface, method, params, invocation):
        if method == "GetCapabilities":
            invocation.return_value(GLib.Variant("(as)", (["body"],)))
        elif method == "GetServerInformation":
            invocation.return_value(GLib.Variant("(ssss)", ("leech", "leech", "0.1", "1.2")))
        elif method == "Notify":
            app_name, replaces_id, app_icon, summary, body, _actions, hints, timeout = params.unpack()
            notification = self._make(app_name, replaces_id, app_icon, summary, body, hints, timeout)
            debug.log("notify", f"входящее id={notification.id} replaces={replaces_id} "
                                f"replaced={notification.replaced} app={app_name!r} "
                                f"entry={hints.get('desktop-entry', '')!r} timeout={timeout} "
                                f"summary={notification.summary!r}")
            invocation.return_value(GLib.Variant("(u)", (notification.id,)))
            self._on_notify(notification)
        elif method == "CloseNotification":
            (nid,) = params.unpack()
            debug.log("notify", f"CloseNotification id={nid}")
            if self._on_close:
                self._on_close(nid)
            self.emit_closed(nid, REASON_CLOSED)
            invocation.return_value(None)
        else:
            invocation.return_dbus_error("org.freedesktop.DBus.Error.UnknownMethod", method)

    def _make(self, app_name, replaces_id, app_icon, summary, body, hints, timeout, local=False):
        replaced = 0 < replaces_id < self._next_id
        if replaces_id:
            nid = replaces_id
        else:
            nid = self._next_id
            self._next_id += 1
        return Notification(
            id=nid, app_name=app_name, summary=_clean(summary), body=_clean(body),
            icon=resolve_icon(app_name, app_icon, hints), timeout_ms=timeout,
            urgency=int(hints.get("urgency", 1)), created=time.monotonic(), local=local, replaced=replaced)

    def dismiss(self, nid):
        self.emit_closed(nid, REASON_DISMISSED)

    def emit_closed(self, nid, reason):
        if self._conn is not None:
            self._conn.emit_signal(None, _PATH, _IFACE, "NotificationClosed",
                                   GLib.Variant("(uu)", (nid, reason)))


    def notify_local(self, summary, body="", icon_name="", critical=False):
        hints = {"urgency": URGENCY_CRITICAL} if critical else {}
        notification = self._make("leech", 0, icon_name, summary, body, hints, -1, local=True)
        debug.log("notify", f"локальное id={notification.id} summary={notification.summary!r}")
        self._on_notify(notification)
        return notification
