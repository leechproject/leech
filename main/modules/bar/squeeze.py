import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk


def child_rect(alloc_x, alloc_w, natural_w, at_end):
    x = alloc_x + alloc_w - natural_w if at_end else alloc_x
    return x, natural_w


class Squeeze(Gtk.Bin):
    def __init__(self, child, at_end):
        super().__init__()
        self._at_end = at_end
        self.add(child)

    def do_get_preferred_width(self):
        child = self.get_child()
        natural = child.get_preferred_width()[1] if child and child.get_visible() else 0
        return 0, natural

    def do_get_preferred_height(self):
        child = self.get_child()
        if child is None or not child.get_visible():
            return 0, 0
        return child.get_preferred_height()

    def do_size_allocate(self, alloc):
        self.set_allocation(alloc)
        child = self.get_child()
        if child is None or not child.get_visible():
            return
        x, width = child_rect(alloc.x, alloc.width, child.get_preferred_width()[1], self._at_end)
        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = x, alloc.y, width, alloc.height
        child.size_allocate(rect)
        self.set_clip(alloc)

    def do_draw(self, cr):
        cr.rectangle(0, 0, self.get_allocated_width(), self.get_allocated_height())
        cr.clip()
        return Gtk.Bin.do_draw(self, cr)
