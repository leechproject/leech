import gi

gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf, GLib

from fabric.system_tray.service import SystemTrayItem, SystemTrayItemPixmap

PIXMAP_PROPERTIES = frozenset(("IconPixmap", "OverlayIconPixmap", "AttentionIconPixmap"))
PIXMAP_SIGNATURE = "a(iiay)"

_INTERPOLATION = {
    "hyper": GdkPixbuf.InterpType.HYPER,
    "bilinear": GdkPixbuf.InterpType.BILINEAR,
    "nearest": GdkPixbuf.InterpType.NEAREST,
    "tiles": GdkPixbuf.InterpType.TILES,
}

_original_get_proxy_property = SystemTrayItem.do_get_proxy_property


def largest_pixmap(variant):
    best = None
    best_width = None
    for index in range(variant.n_children()):
        entry = variant.get_child_value(index)
        width = entry.get_child_value(0).get_int32()
        if best_width is None or width >= best_width:
            best, best_width = entry, width
    if best is None:
        return []
    data = best.get_child_value(2).get_data_as_bytes().get_data()
    return [(best_width, best.get_child_value(1).get_int32(), bytearray(data))]


def argb_to_rgba(data, width, height):
    size = 4 * width * height
    if width <= 0 or height <= 0 or len(data) < size:
        return None
    source = memoryview(data)[:size]
    rgba = bytearray(size)
    rgba[0::4] = source[1::4]
    rgba[1::4] = source[2::4]
    rgba[2::4] = source[3::4]
    rgba[3::4] = source[0::4]
    return rgba


def _get_proxy_property(self, property_name):
    if property_name in PIXMAP_PROPERTIES:
        value = self._proxy.get_cached_property(property_name)
        if value is None:
            return None
        if value.get_type_string() == PIXMAP_SIGNATURE:
            return largest_pixmap(value)
    return _original_get_proxy_property(self, property_name)


def _as_pixbuf(self, size=None, resize_method="nearest"):
    if not (self.width and self.height and self.data):
        return None
    rgba = argb_to_rgba(self.data, self.width, self.height)
    if rgba is None:
        return None
    pixbuf = GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(rgba), GdkPixbuf.Colorspace.RGB, True, 8,
                                             self.width, self.height, self.width * 4)
    if size is None:
        return pixbuf
    return pixbuf.scale_simple(size, size, _INTERPOLATION.get(resize_method.lower(), GdkPixbuf.InterpType.NEAREST))


def install():
    SystemTrayItem.do_get_proxy_property = _get_proxy_property
    SystemTrayItemPixmap.as_pixbuf = _as_pixbuf
