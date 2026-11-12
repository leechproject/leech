import gi

gi.require_version("GtkLayerShell", "0.1")
from gi.repository import GtkLayerShell


RELAX = True


def effective(level):
    return "exclusive" if level == "on_demand" and not RELAX else level


def set_keyboard(window, level):
    level = effective(level)
    if hasattr(GtkLayerShell, "set_keyboard_mode"):
        modes = {"none": GtkLayerShell.KeyboardMode.NONE,
                 "exclusive": GtkLayerShell.KeyboardMode.EXCLUSIVE,
                 "on_demand": GtkLayerShell.KeyboardMode.ON_DEMAND}
        GtkLayerShell.set_keyboard_mode(window, modes[level])
    else:
        GtkLayerShell.set_keyboard_interactivity(window, level != "none")
    window.queue_draw()
