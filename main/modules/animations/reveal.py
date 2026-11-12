def install_clip(widget, toplevel, provider):
    def on_draw(_widget, cr):
        spec = provider()
        if spec is None:
            return False
        origin = widget.translate_coordinates(toplevel, 0, 0)
        if origin is None:
            return False
        x, y, w, h, dy = spec
        cr.rectangle(x - origin[0], y - origin[1], w, h)
        cr.clip()
        cr.translate(0, dy)
        return False

    widget.connect("draw", on_draw)
