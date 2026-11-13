import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from modules import config
from modules.common import theme
from modules.common.shapes import draw_outline


def _draw(widget, cr):
    ctx = widget.get_style_context()
    margin = ctx.get_margin(Gtk.StateFlags.NORMAL)
    radius = ctx.get_property("border-radius", Gtk.StateFlags.NORMAL)
    # CSS-margin входит в выделение виджета, фон плашки рисуется внутри него.
    w = widget.get_allocated_width() - margin.left - margin.right
    h = widget.get_allocated_height() - margin.top - margin.bottom
    cr.save()
    cr.translate(margin.left, margin.top)
    draw_outline(cr, w, h, min(radius, w / 2, h / 2), theme.outline_layers(), config.OUTLINE_THICKNESS)
    cr.restore()
    return False


def apply(box):
    """Двуслойная обводка плашки бара, если она включена параметром `outline`."""
    if config.BAR_OUTLINE.get(box.get_name()):
        box.connect_after("draw", _draw)
