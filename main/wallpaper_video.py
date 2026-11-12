import sys
from pathlib import Path

sys.pycache_prefix = str(Path(__file__).resolve().parents[1] / ".shellcache")

import ctypes

import cairo
import gi

gi.require_version("GtkLayerShell", "0.1")
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import GtkLayerShell, Gtk, Gdk, GLib

from modules.wallpapers import libmpv

GL_FRAMEBUFFER_BINDING = 0x8CA6


def _wl_display(widget):
    try:
        gdk = ctypes.CDLL("libgdk-3.so.0")
        gdk.gdk_wayland_display_get_wl_display.restype = ctypes.c_void_p
        gdk.gdk_wayland_display_get_wl_display.argtypes = (ctypes.c_void_p,)
        capsule = ctypes.pythonapi.PyCapsule_GetPointer
        capsule.restype = ctypes.c_void_p
        capsule.argtypes = (ctypes.py_object, ctypes.c_char_p)
        return gdk.gdk_wayland_display_get_wl_display(capsule(widget.get_display().__gpointer__, None))
    except (OSError, AttributeError, ValueError):
        return None


def _load_gl():
    for name in ("libOpenGL.so.0", "libGL.so.1"):
        try:
            gl = ctypes.CDLL(name)
            gl.glGetIntegerv.argtypes = (ctypes.c_uint, ctypes.POINTER(ctypes.c_int))
            return gl
        except OSError:
            continue
    raise OSError("libOpenGL не найден")


class VideoWindow(Gtk.Window):
    def __init__(self, path, paused, place=None):
        super().__init__()
        self._path = path
        self._player = None
        self._gl = _load_gl()
        self._paused = paused

        GtkLayerShell.init_for_window(self)
        if place is not None:
            display = Gdk.Display.get_default()
            for index in range(display.get_n_monitors()):
                monitor = display.get_monitor(index)
                geometry = monitor.get_geometry()
                if (geometry.x, geometry.y) == place:
                    GtkLayerShell.set_monitor(self, monitor)
        GtkLayerShell.set_namespace(self, "leech-wallpaper-video")
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.BACKGROUND)
        for edge in (GtkLayerShell.Edge.TOP, GtkLayerShell.Edge.RIGHT,
                     GtkLayerShell.Edge.BOTTOM, GtkLayerShell.Edge.LEFT):
            GtkLayerShell.set_anchor(self, edge, True)
        GtkLayerShell.set_exclusive_zone(self, -1)

        self._area = Gtk.GLArea()
        self._area.set_has_alpha(False)
        self._area.set_auto_render(False)
        self._area.connect("realize", self._on_realize)
        self._area.connect("unrealize", self._on_unrealize)
        self._area.connect("render", self._on_render)
        self.add(self._area)
        self.connect("realize", lambda *_: self.get_window().input_shape_combine_region(cairo.Region(), 0, 0))
        self.connect("destroy", lambda *_: Gtk.main_quit())
        self.show_all()

    def _on_realize(self, area):
        area.make_current()
        if area.get_error() is not None:
            print(f"видео-обои: GL недоступен: {area.get_error().message}", file=sys.stderr)
            Gtk.main_quit()
            return
        self._player = libmpv.Player({
            "vo": "libmpv", "profile": "fast", "hwdec": "auto-safe", "loop-file": "inf", "audio": "no",
            "keepaspect": "yes", "panscan": "1.0", "osc": "no", "input-default-bindings": "no",
            "terminal": "no", "pause": "yes" if self._paused else "no",
        })
        self._player.attach_gl(lambda: GLib.idle_add(self._area.queue_render), _wl_display(area))
        self._player.load(self._path)

    def _on_unrealize(self, area):
        area.make_current()
        if self._player is not None:
            self._player.close()
            self._player = None

    def _on_render(self, area, _context):
        if self._player is None:
            return True
        fbo = ctypes.c_int(0)
        self._gl.glGetIntegerv(GL_FRAMEBUFFER_BINDING, ctypes.byref(fbo))
        scale = area.get_scale_factor()
        self._player.render(fbo.value, area.get_allocated_width() * scale, area.get_allocated_height() * scale)
        return True

    def command(self, line):
        if line in ("hide", "show"):
            self.set_visible(line == "show")
            return
        if self._player is None:
            self._paused = line == "pause"
            return
        if line in ("pause", "play"):
            self._player.set_property("pause", "yes" if line == "pause" else "no")


def _watch_stdin(window):
    def on_input(source, _condition):
        line = source.readline()
        if not line or line.strip() == "quit":
            window.destroy()
            return False
        line = line.strip()
        window.command(line)
        return True

    channel = GLib.IOChannel.unix_new(sys.stdin.fileno())
    GLib.io_add_watch(channel, GLib.PRIORITY_DEFAULT, GLib.IOCondition.IN | GLib.IOCondition.HUP, on_input)


def main():
    if len(sys.argv) < 2:
        print("использование: wallpaper_video.py ФАЙЛ [paused|play] [X,Y]", file=sys.stderr)
        return 2
    place = tuple(int(v) for v in sys.argv[3].split(",")) if len(sys.argv) > 3 else None
    window = VideoWindow(sys.argv[1], len(sys.argv) > 2 and sys.argv[2] == "paused", place)
    _watch_stdin(window)
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
