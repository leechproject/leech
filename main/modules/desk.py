from collections import namedtuple

from modules import config
from modules.common.absent import DetachedDock, NoDock, NoNotch
from modules.common.canvas import create_canvas
from modules.common.surface import gdk_monitor, on_monitor
from modules.rules.view import MonitorView

Target = namedtuple("Target", "dock notch monitor")


class Desk:
    def __init__(self, wm, monitor):
        self.monitor = monitor
        self.name = monitor.name if monitor is not None else "default"
        self.target = gdk_monitor(monitor)
        self.view = MonitorView(wm, monitor)
        with on_monitor(self.target):
            surfaces = create_canvas(self.view.output_scale())
        self.canvas = surfaces.canvas
        self.windows = list(surfaces.windows)
        self.notch = self.taskbar = self.dock = self.bar = None

    def build(self, shell, canvases, media):
        canvas = canvases.scoped(self.name)
        with on_monitor(self.target):
            if config.NOTCH_ENABLED:
                from modules.notch.notch import Notch
                self.notch = Notch(self.view, media, canvas)
                self.windows.append(self.notch)
            if config.UNDERCOVER:
                from modules.bar.taskbar import Taskbar
                notch = self.notch
                popup = None
                if config.PROFILES_BY_TASKBAR:
                    from modules.notch.profiles_popup import ProfilesPopup
                    popup = ProfilesPopup(canvas)
                    self.windows.append(popup)
                    if notch is not None:
                        notch.battery_redirect = popup.toggle
                on_profiles = popup.toggle if popup else ((lambda: notch.toggle("battery")) if notch else None)
                self.taskbar = Taskbar(self.view, canvas, on_launcher=shell.toggle_launcher,
                                       on_clock=lambda: shell.toggle_cc(2, self.target),
                                       on_profiles=on_profiles)
                if popup is not None:
                    popup.on_state = self.taskbar.set_profiles_open
                self.windows.append(self.taskbar)
            if config.DOCK_ENABLED and not config.UNDERCOVER:
                from modules.dock.dock import Dock
                self.dock = Dock(self.view)
                self.windows.append(self.dock)
            if config.BAR_ENABLED and not config.UNDERCOVER:
                from modules.bar.bar import Bar
                notch = self.notch
                self.bar = Bar(
                    self.view,
                    on_launcher=shell.toggle_launcher if config.LAUNCHER_ENABLED else None,
                    on_battery=(lambda: notch.toggle("battery")) if notch else None,
                    on_power=(lambda: notch.toggle("power")) if notch else None,
                    notch=notch,
                    canvas=canvas,
                )
                self.windows.append(self.bar)

    def dock_for(self, top):
        if self.taskbar is not None:
            return DetachedDock(self.taskbar)
        if self.dock is None:
            return NoDock()
        return self.dock if top == config.DOCK_TOP else DetachedDock(self.dock)

    def target_for(self, top):
        return Target(self.dock_for(top), self.notch or NoNotch(), self.target)

    def pins(self):
        return self.dock or self.taskbar

    def tray_owner(self):
        return self.taskbar or self.bar
