import os
import sys
from pathlib import Path

sys.pycache_prefix = str(Path(__file__).resolve().parents[1] / ".shellcache")

import gi

gi.require_version("GtkLayerShell", "0.1")
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import GtkLayerShell
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gtk, Gdk, GLib, Pango, PangoCairo

from fabric import Application

from modules import config
from modules import rules
from modules.config import loader
from modules.common import debug
from modules.common import fonts
from modules.common import layerkeys
from modules.common.absent import NoNotifications
from modules.common.canvas import CanvasGroup
from modules.common.surface import move_to, on_monitor
from modules.desk import Desk
from modules.rules.view import view_state
from modules.parsing import power
from modules.parsing import state as saved_state
from modules.parsing.ipc import IpcServer
from modules.parsing.stats import report as memory_report

BASE_CSS = b"window, window.background { background: transparent; }"


def _add_provider(provider, priority=Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION):
    Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider, priority)


def _system_family():
    name = Gtk.Settings.get_default().props.gtk_font_name or ""
    return Pango.FontDescription.from_string(name).get_family() if name else None


def apply_fonts():
    text = fonts.register(config.GLOBAL_FONT)
    icons = fonts.register(config.ICON_FONT)
    fontmap = PangoCairo.FontMap.get_default()
    if (text or icons) and hasattr(fontmap, "config_changed"):
        fontmap.config_changed()
    css = fonts.font_css(text, icons, _system_family())
    if css:
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())
        _add_provider(provider)


def apply_css():
    base = Gtk.CssProvider()
    base.load_from_data(BASE_CSS)
    _add_provider(base)
    apply_fonts()

    from modules.common import theme as drawn
    fallback = Gtk.CssProvider()
    fallback.load_from_data(drawn.fallback_css().encode())
    _add_provider(fallback, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION - 1)
    drawn.set_loaded()

    theme = Gtk.CssProvider()
    try:
        theme.load_from_path(str(config.STYLE_FILE))
        _add_provider(theme)
    except GLib.Error as e:
        print(f"style.css: {e.message}")
        return
    if config.BAR_ENABLED and config.BAR_SCALE != 1:
        from modules.bar.scale import scaled_css
        bar = Gtk.CssProvider()
        bar.load_from_data(scaled_css(config.STYLE_FILE.read_text(), config.BAR_SCALE).encode())
        _add_provider(bar, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)


def _restart():
    sys.stdout.flush()
    sys.stderr.flush()
    os.execv(sys.executable, sys.orig_argv)


class Shell:
    def __init__(self):
        self.wm = rules.load(config.WM)
        layerkeys.RELAX = getattr(self.wm, "relax_layer_keyboard", True)
        monitors = self.wm.monitors() or (None,)
        self.desks = [Desk(self.wm, monitor) for monitor in monitors]
        self._names = frozenset(desk.name for desk in self.desks)
        self._focused = next((d for d in self.desks if d.monitor is not None and d.monitor.focused), self.desks[0])
        self._restarting = False
        canvases = CanvasGroup(desk.canvas for desk in self.desks)
        self.media = self.wallpaper = None

        if config.NOTCH_ENABLED:
            from modules.parsing.media import Media
            self.media = Media()
        self.launcher = self.cc = self.picker = None
        for desk in self.desks:
            desk.build(self, canvases, self.media)

        self.notifications = None
        if config.NOTIFICATIONS_ENABLED:
            from modules.notifications.notifications import NotificationServer
            self.notifications = NotificationServer(self._on_notification, self._on_notification_closed)
        notifier = self.notifications or NoNotifications()
        power.set_error_handler(lambda message: notifier.notify_local(
            "Power action failed", message, "dialog-error", critical=True))

        self.controls = None
        if config.CC_ENABLED:
            from modules.cc.control_center import ControlCenter
            from modules.cc.controls import Controls
            self.controls = Controls()
            with on_monitor(self._focused.target):
                self.cc = ControlCenter(self.wm, notifier, canvases, self.controls)
            for desk in self.desks:
                if desk.taskbar is not None:
                    self.cc.subscribe_open(desk.taskbar.set_cc_open)

        if config.WALLPAPERS_ENABLED:
            from modules.wallpapers.wallpaper import WallpaperManager
            from modules.wallpapers.wallpaper_picker import WallpaperPicker
            self.wallpaper = WallpaperManager([(desk.view, desk.target) for desk in self.desks])
            self.picker = WallpaperPicker(self.wallpaper, lambda: self._focused.target_for(config.PICKER_TOP),
                                          canvases)

        if config.LAUNCHER_ENABLED:
            from modules.launcher.launcher import Launcher
            self.launcher = Launcher(lambda: self._focused.target_for(config.LAUNCHER_TOP), canvases)

        if self.launcher is not None and config.LAUNCHER_SUPER_TAP:
            from modules.parsing.supertap import SuperTap
            self.super_tap = SuperTap(self._on_super_tap)
            self.super_tap.start()

        if self.picker and self.launcher:
            self.picker.others = (self.launcher,)
            self.launcher.others = (self.picker,)

        self.windows = [w for desk in self.desks for w in desk.windows] + ([self.cc] if self.cc else [])
        self.wm.subscribe(self._on_wm)

    def _on_wm(self, state):
        if not state.monitors:
            return
        names = frozenset(m.name for m in state.monitors)
        if names != self._names and not self._restarting:
            self._restarting = True
            debug.log("monitors", f"набор мониторов изменился: {sorted(names)}, перезапуск")
            GLib.timeout_add(500, _restart)
            return
        focused = next((m.name for m in state.monitors if m.focused), None)
        self._focused = next((d for d in self.desks if d.name == focused), self._focused)
        self._place_cc()

    def _place_cc(self):
        if self.cc is not None and self.cc.is_idle():
            move_to(self.cc, self._focused.target)

    def _on_super_tap(self):
        state = getattr(self.wm, "state", None)
        if state is not None and view_state(state, self._focused.name).fullscreen:
            return
        self.launcher.toggle()

    def toggle_launcher(self):
        if self.launcher is not None:
            self.launcher.toggle()

    def toggle_cc(self, level, target=None):
        if self.cc is None:
            return None
        target = target or self._focused.target
        if target is not None and GtkLayerShell.get_monitor(self.cc) != target and not self.cc.is_idle():
            self.cc.close_now()
        if self.cc.is_idle():
            move_to(self.cc, target)
        return self.cc.toggle(level)

    def _on_notification(self, n):
        if self.cc is not None:
            self._place_cc()
            self.cc.on_notification(n)

    def _on_notification_closed(self, nid):
        if self.cc is not None:
            self.cc.remove_notification(nid)

    def handle(self, command):
        parts = command.split()
        if not parts:
            return "пустая команда"
        head = parts[0]
        if parts[:2] in (["toggle", "cc"], ["toggle", "cc-full"]):
            return self._call(self.cc, "cc", lambda: self.toggle_cc(1 if parts[1] == "cc" else 2))
        if parts[:2] == ["toggle", "wallpaper"]:
            return self._call(self.picker, "wallpapers", self.picker and self.picker.toggle)
        if parts[:2] == ["toggle", "launcher"]:
            return self._call(self.launcher, "launcher", self.launcher and self.launcher.toggle)
        if head in ("toggle", "close"):
            notch = self._focused.notch
            return self._call(notch, "notch", lambda: notch.handle(command))
        if head in ("pin", "unpin") and len(parts) == 2:
            dock = self._focused.pins()
            return self._call(dock, "dock", lambda: getattr(dock, head)(parts[1]))
        if head == "pins":
            dock = self._focused.pins()
            return self._call(dock, "dock", dock and dock.pins)
        if head == "stats":
            return memory_report()
        if head == "reload":
            return self.reload()
        if head == "debug-cc" and debug.ENABLED and len(parts) == 2:
            return self._call(self.cc, "cc", lambda: self.cc.debug_press(parts[1]))
        if head == "debug-tray" and debug.ENABLED and len(parts) == 2:
            owner = self._focused.tray_owner()
            if owner is not None and owner is self._focused.taskbar:
                return self._call(owner, "bar.tray", lambda: owner.debug_tray(parts[1]))
            return self._call(owner and owner.tray, "bar.tray", lambda: owner.tray.debug(parts[1]))
        if head == "volume" and len(parts) == 2 and parts[1] in ("up", "down", "mute"):
            if parts[1] == "mute":
                return self._call(self.controls, "cc", lambda: self.controls.toggle_mute())
            return self._call(self.controls, "cc", lambda: self.controls.step_volume(1 if parts[1] == "up" else -1))
        if head == "brightness" and len(parts) == 2 and parts[1] in ("up", "down"):
            return self._call(self.controls, "cc", lambda: self.controls.step_brightness(1 if parts[1] == "up" else -1))
        return f"неизвестная команда: {command}"

    def reload(self):
        problems = loader.check(config.CONFIG_FILE, config.ROOT)
        GLib.timeout_add(150, _restart)
        name = config.CONFIG_FILE.name if config.CONFIG_FILE else "конфиг"
        lines = [f"{name}: {problem}" for problem in problems]
        return "\n".join(lines + ["перезапуск"]) if lines else "перезапуск"

    @staticmethod
    def _call(module, name, action):
        if module is None:
            return f"модуль {name} отключён в конфиге"
        return action()

    def start(self):
        IpcServer(self.handle).start()
        for service in (self.notifications, self.wm, self.media, self.wallpaper):
            if service is not None:
                service.start()
        debug.start()
        refit = getattr(self.wm, "refit_columns", None)
        zones = f"{config.LEFT},{config.RIGHT}"
        if refit is not None and saved_state.get("side-zones", zones) != zones:
            insets = (config.LEFT, config.TOP, config.RIGHT, config.BOTTOM)
            GLib.timeout_add(600, lambda: refit(insets) or False)
        saved_state.set_value("side-zones", zones)


if __name__ == "__main__":
    apply_css()
    shell = Shell()
    shell.start()
    app = Application("leech", *shell.windows)
    app.run()
