import subprocess

from gi.repository import Gio, GLib

_BUS = "org.bluez"
_ADAPTER = "org.bluez.Adapter1"
_PROPS = "org.freedesktop.DBus.Properties"


def _system_bus():
    return Gio.bus_get_sync(Gio.BusType.SYSTEM, None)


def _adapter_path(bus):
    objects = bus.call_sync(_BUS, "/", "org.freedesktop.DBus.ObjectManager", "GetManagedObjects",
                            None, GLib.VariantType("(a{oa{sa{sv}}})"), Gio.DBusCallFlags.NONE,
                            500, None).unpack()[0]
    for path, interfaces in sorted(objects.items()):
        if _ADAPTER in interfaces:
            return path
    return None


def powered():
    try:
        bus = _system_bus()
        path = _adapter_path(bus)
        if path is None:
            return None
        return bus.call_sync(_BUS, path, _PROPS, "Get", GLib.Variant("(ss)", (_ADAPTER, "Powered")),
                             GLib.VariantType("(v)"), Gio.DBusCallFlags.NONE, 500, None).unpack()[0]
    except GLib.Error:
        return None


def set_powered(on):
    try:
        if on:
            subprocess.run(["rfkill", "unblock", "bluetooth"], capture_output=True, timeout=2)
        bus = _system_bus()
        path = _adapter_path(bus)
        if path is None:
            return
        bus.call_sync(_BUS, path, _PROPS, "Set",
                      GLib.Variant("(ssv)", (_ADAPTER, "Powered", GLib.Variant("b", on))),
                      None, Gio.DBusCallFlags.NONE, 1000, None)
    except (GLib.Error, OSError, subprocess.SubprocessError) as e:
        print(f"bluetooth: {e}")


_DEVICE = "org.bluez.Device1"


class Device:
    __slots__ = ("path", "name", "address", "icon", "paired", "trusted", "connected", "rssi")

    def __init__(self, path, props):
        self.path = path
        self.address = props.get("Address", "")
        self.name = props.get("Alias") or props.get("Name") or self.address
        self.icon = props.get("Icon", "")
        self.paired = bool(props.get("Paired"))
        self.trusted = bool(props.get("Trusted"))
        self.connected = bool(props.get("Connected"))
        self.rssi = props.get("RSSI")


def sort_key(device):
    return (not device.connected, not device.paired, -(device.rssi if device.rssi is not None else -999),
            device.name.casefold())


def read():
    try:
        bus = _system_bus()
        objects = bus.call_sync(_BUS, "/", "org.freedesktop.DBus.ObjectManager", "GetManagedObjects",
                                None, GLib.VariantType("(a{oa{sa{sv}}})"), Gio.DBusCallFlags.NONE,
                                1000, None).unpack()[0]
    except GLib.Error:
        return None, []
    adapter = None
    for path, interfaces in sorted(objects.items()):
        if _ADAPTER in interfaces:
            adapter = (path, interfaces[_ADAPTER])
            break
    if adapter is None:
        return None, []
    prefix = adapter[0] + "/"
    devices = [Device(path, interfaces[_DEVICE]) for path, interfaces in objects.items()
               if _DEVICE in interfaces and path.startswith(prefix)]
    devices = [d for d in devices if d.paired or d.connected or d.rssi is not None]
    return adapter, sorted(devices, key=sort_key)


def _call(path, interface, method, params, done, timeout=30000):
    def finish(bus, result):
        try:
            bus.call_finish(result)
            done(True, "")
        except GLib.Error as e:
            done(False, e.message.split(":", 2)[-1].strip())
    try:
        bus = _system_bus()
    except GLib.Error as e:
        done(False, e.message)
        return
    bus.call(_BUS, path, interface, method, params, None, Gio.DBusCallFlags.NONE, timeout, None, finish)


def _set(path, interface, name, value, done):
    _call(path, _PROPS, "Set", GLib.Variant("(ssv)", (interface, name, value)), done, 5000)


def connect(device, done):
    if device.paired:
        _call(device.path, _DEVICE, "Connect", None, done)
        return

    def paired(ok, message):
        if ok:
            _set(device.path, _DEVICE, "Trusted", GLib.Variant("b", True), lambda *_: None)
            _call(device.path, _DEVICE, "Connect", None, done)
        else:
            done(ok, message)
    _call(device.path, _DEVICE, "Pair", None, paired, 60000)


def disconnect(device, done):
    _call(device.path, _DEVICE, "Disconnect", None, done)


def set_trusted(device, trusted, done):
    _set(device.path, _DEVICE, "Trusted", GLib.Variant("b", trusted), done)


def remove(adapter_path, device, done):
    _call(adapter_path, _ADAPTER, "RemoveDevice", GLib.Variant("(o)", (device.path,)), done, 5000)


def set_discovering(adapter_path, on, done):
    _call(adapter_path, _ADAPTER, "StartDiscovery" if on else "StopDiscovery", None, done, 5000)


def set_discoverable(adapter_path, on, done):
    _set(adapter_path, _ADAPTER, "Discoverable", GLib.Variant("b", on), done)


def watch(callback):
    try:
        bus = _system_bus()
    except GLib.Error:
        return lambda: None
    ids = [bus.signal_subscribe(_BUS, iface, member, None, None, Gio.DBusSignalFlags.NONE,
                                lambda *_: callback())
           for iface, member in ((_PROPS, "PropertiesChanged"),
                                 ("org.freedesktop.DBus.ObjectManager", "InterfacesAdded"),
                                 ("org.freedesktop.DBus.ObjectManager", "InterfacesRemoved"))]

    def stop():
        for sid in ids:
            bus.signal_unsubscribe(sid)
    return stop
