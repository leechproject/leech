import hashlib
import math
import os
import subprocess
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import gi

gi.require_version("GtkLayerShell", "0.1")
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GtkLayerShell, Gtk, Gdk, GLib, GdkPixbuf

from modules.common.surface import ShapedWindow, no_input, init_layer, on_monitor

from modules import config
from modules.animations import anim
from modules.animations.anim import Tween
from modules.parsing import state
from modules.wallpapers import video

_NO_INPUT = no_input()
BLUR_LEVELS = 5
BLUR_FADE_MS = 220
_MPV = video.mpv_installed()


def wallpaper_dir():
    custom = state.get("wallpaper_dir")
    return Path(os.path.expanduser(custom)) if custom else config.WALLPAPER_DIR


def list_wallpapers(directory):
    try:
        files = [p for p in Path(directory).iterdir()
                 if p.is_file() and p.suffix.lower() in video.extensions(_MPV)]
    except OSError:
        return []
    return sorted(files, key=lambda p: p.name.casefold())


def cover_pixbuf(path, width, height):
    if video.is_video(path):
        path = video.still_frame(path)
    info = GdkPixbuf.Pixbuf.get_file_info(str(path))
    image_w, image_h = info[1], info[2]
    if info[0] is None or image_w <= 0 or image_h <= 0:
        raise ValueError(f"не картинка: {path}")
    scale = max(width / image_w, height / image_h)
    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
        str(path), max(width, math.ceil(image_w * scale)), max(height, math.ceil(image_h * scale)), False)
    if pixbuf.get_width() < width or pixbuf.get_height() < height:
        pixbuf = pixbuf.scale_simple(max(width, pixbuf.get_width()), max(height, pixbuf.get_height()),
                                     GdkPixbuf.InterpType.BILINEAR)
    x = (pixbuf.get_width() - width) // 2
    y = (pixbuf.get_height() - height) // 2
    return pixbuf.new_subpixbuf(x, y, width, height).copy()


def blurred_pixbuf(pixbuf, levels):
    sizes = [(pixbuf.get_width(), pixbuf.get_height())]
    result = pixbuf
    for _ in range(levels):
        width, height = max(1, result.get_width() // 2), max(1, result.get_height() // 2)
        result = result.scale_simple(width, height, GdkPixbuf.InterpType.BILINEAR)
        sizes.append((width, height))
    for width, height in reversed(sizes[:-1]):
        result = result.scale_simple(width, height, GdkPixbuf.InterpType.BILINEAR)
    return result


class Thumbnails:
    def __init__(self, on_ready):
        self._on_ready = on_ready
        self._pool = ThreadPoolExecutor(max_workers=2)
        self._cache = OrderedDict()
        self._pending = set()
        self._failed = set()
        self._closed = False

    def get(self, path, width, height):
        key = (str(path), width, height)
        pixbuf = self._cache.get(key)
        if pixbuf is not None:
            self._cache.move_to_end(key)
            return pixbuf
        if key not in self._pending and key not in self._failed and not self._closed:
            self._pending.add(key)
            self._pool.submit(self._work, key)
        return None

    def close(self):
        self._closed = True
        self._pool.shutdown(wait=False, cancel_futures=True)
        self._cache.clear()


    def _work(self, key):
        path, width, height = key
        pixbuf = None
        try:
            pixbuf = self._load(path, width, height)
        except (GLib.Error, OSError, ValueError, subprocess.SubprocessError) as e:
            print(f"миниатюра {path}: {e}")
        GLib.idle_add(self._done, key, pixbuf)

    @staticmethod
    def _cache_file(path, width, height):
        stat = os.stat(path)
        raw = f"{path}|{stat.st_mtime_ns}|{stat.st_size}|{width}x{height}"
        return config.CACHE_DIR / "thumbs" / (hashlib.sha1(raw.encode()).hexdigest() + ".png")

    def _load(self, path, width, height):
        cache_file = self._cache_file(path, width, height)
        if cache_file.exists():
            try:
                return GdkPixbuf.Pixbuf.new_from_file(str(cache_file))
            except GLib.Error:
                pass
        pixbuf = cover_pixbuf(path, width, height)
        try:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            pixbuf.savev(str(cache_file), "png", [], [])
        except (GLib.Error, OSError):
            pass
        return pixbuf


    def _done(self, key, pixbuf):
        self._pending.discard(key)
        if self._closed:
            return False
        if pixbuf is None:
            self._failed.add(key)
        else:
            self._cache[key] = pixbuf
            while len(self._cache) > config.THUMB_CACHE_MAX:
                self._cache.popitem(last=False)
            self._on_ready()
        return False


class WallpaperSurface(ShapedWindow):
    def __init__(self):
        super().__init__(name="wallpaper", visible=False, all_visible=False)
        init_layer(self)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.BACKGROUND)
        for edge in (GtkLayerShell.Edge.TOP, GtkLayerShell.Edge.RIGHT,
                     GtkLayerShell.Edge.BOTTOM, GtkLayerShell.Edge.LEFT):
            GtkLayerShell.set_anchor(self, edge, True)
        GtkLayerShell.set_exclusive_zone(self, -1)

        self._path = None
        self._size = (0, 0)
        self._pixbuf = None
        self._blurred = None
        self._blur_wanted = False
        self._blur_t = 0.0
        self._blur_tween = Tween(anim.ms(BLUR_FADE_MS), self._on_blur_tick)

        self._area = Gtk.DrawingArea()
        self._area.connect("draw", self._on_draw)
        self.add(self._area)
        self.connect("size-allocate", self._on_allocate)
        self.show_all()

    def input_region(self):
        return _NO_INPUT

    def set_image(self, path):
        self._path = str(path)
        self._reload()

    def _on_allocate(self, _widget, allocation):
        size = (allocation.width, allocation.height)
        if size != self._size and allocation.width > 100 and allocation.height > 100:
            self._size = size
            self._reload()

    def _reload(self):
        path, size = self._path, self._size
        if path is None or size[0] == 0:
            return

        def work():
            try:
                pixbuf = cover_pixbuf(path, *size)
            except (GLib.Error, OSError, ValueError, subprocess.SubprocessError) as e:
                print(f"обои {path}: {e}")
                return
            GLib.idle_add(self._loaded, path, size, pixbuf)
        threading.Thread(target=work, daemon=True).start()

    def _loaded(self, path, size, pixbuf):
        if path == self._path and size == self._size:
            self._pixbuf = pixbuf
            self._blurred = None
            if self._blur_wanted:
                self._make_blurred()
            self._area.queue_draw()
        return False

    def set_blurred(self, wanted):
        if wanted == self._blur_wanted:
            return
        self._blur_wanted = wanted
        if wanted and self._blurred is None:
            self._make_blurred()
        else:
            self._fade_blur()

    def _make_blurred(self):
        pixbuf = self._pixbuf
        if pixbuf is None:
            return

        def work():
            result = blurred_pixbuf(pixbuf, BLUR_LEVELS)
            GLib.idle_add(self._blur_ready, pixbuf, result)
        threading.Thread(target=work, daemon=True).start()

    def _blur_ready(self, source, result):
        if source is self._pixbuf:
            self._blurred = result
            self._fade_blur()
        return False

    def _fade_blur(self):
        target = 1.0 if self._blur_wanted and self._blurred is not None else 0.0
        if target != self._blur_t:
            self._blur_tween.run((self._blur_t,), (target,))

    def _on_blur_tick(self, values):
        self._blur_t = values[0]
        self._area.queue_draw()

    def _on_draw(self, _area, cr):
        cr.set_source_rgb(0, 0, 0)
        cr.paint()
        if self._pixbuf is not None and self._blur_t < 1.0:
            Gdk.cairo_set_source_pixbuf(cr, self._pixbuf, 0, 0)
            cr.paint()
        if self._blurred is not None and self._blur_t > 0.0:
            Gdk.cairo_set_source_pixbuf(cr, self._blurred, 0, 0)
            cr.paint_with_alpha(self._blur_t)
        return False


class _Screen:
    def __init__(self, view, target):
        self.view = view
        self.target = target
        self.surface = None
        self.video = None
        self.covered = False
        self.blurred = False


class WallpaperManager:
    def __init__(self, screens):
        self._screens = [_Screen(view, target) for view, target in screens]
        self.current = state.get("wallpaper")
        for screen in self._screens:
            screen.view.subscribe(lambda wm_state, screen=screen: self._on_wm(screen, wm_state))

    def start(self):
        if self.current and Path(self.current).is_file():
            self.apply(self.current, remember=False)

    def _on_wm(self, screen, wm_state):
        screen.covered = video.covered(wm_state)
        screen.blurred = config.WALLPAPER_OVERVIEW_BLUR and wm_state.overview
        if screen.surface is not None:
            screen.surface.set_blurred(screen.blurred)
        if screen.video is not None:
            screen.video.set_paused(screen.covered)
            screen.video.set_hidden(screen.blurred)

    def apply(self, path, remember=True):
        self.current = str(path)
        if remember:
            state.set_value("wallpaper", self.current)
        for screen in self._screens:
            if screen.surface is None:
                with on_monitor(screen.target):
                    screen.surface = WallpaperSurface()
            screen.surface.set_image(self.current)
            screen.surface.set_blurred(screen.blurred)
            if screen.video is not None and screen.video.path != self.current:
                screen.video.stop()
                screen.video = None
            if screen.video is None and video.is_video(self.current):
                monitor = screen.view.monitor
                place = (monitor.x, monitor.y) if monitor is not None else None
                screen.video = video.VideoProcess(self.current, screen.covered, place)
                screen.video.set_hidden(screen.blurred)
