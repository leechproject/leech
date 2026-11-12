import gi

gi.require_version("Gtk", "3.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gtk, PangoCairo


def ink_origin(ink, x, y, width, height):
    return (round(x + (width - ink.width) / 2 - ink.x),
            round(y + (height - ink.height) / 2 - ink.y))


def show_centered(cr, layout, cx, cy):
    ink, _ = layout.get_pixel_extents()
    cr.move_to(*ink_origin(ink, cx, cy, 0, 0))
    PangoCairo.show_layout(cr, layout)


class GlyphLabel(Gtk.Label):

    def _box(self):
        ink, logical = self.get_layout().get_pixel_extents()
        return ink, max(ink.width, logical.width), max(ink.height, logical.height)

    def do_get_preferred_width(self):
        _, width, _ = self._box()
        return width, width

    def do_get_preferred_height(self):
        _, _, height = self._box()
        return height, height

    def do_get_preferred_height_for_width(self, _width):
        return self.do_get_preferred_height()

    def do_get_preferred_width_for_height(self, _height):
        return self.do_get_preferred_width()

    def do_draw(self, cr):
        layout = self.get_layout()
        ink, _ = layout.get_pixel_extents()
        x, y = ink_origin(ink, 0, 0, self.get_allocated_width(), self.get_allocated_height())
        Gtk.render_layout(self.get_style_context(), cr, x, y, layout)
        return False
