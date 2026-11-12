from modules import config
from modules.common.shapes import (OUTLINE_LAYERS, clip_out_band, notch_edge_path, notch_path, rounded_rect,
                                   stroke_inside)


class AttachedEdge:
    def __init__(self, top):
        self.top = top
        self.frame = config.TOP if top else config.BOTTOM
        self.side = "top" if top else "bottom"
        self.band = config.BAR_BAND if config.BAR_POSITION == self.side else (0, 0)
        self.bar = self.band[1]

    def to_edge(self, cr, height):
        if not self.top:
            cr.translate(0, height)
            cr.scale(1, -1)

    def clip_bar(self, cr, width, height):
        clip_out_band(cr, width, height, self.side, self.band)

    def body_y(self, height, h, frame=None):
        frame = self.frame if frame is None else frame
        return frame if self.top else height - frame - h

    def attached_rect(self, height, h):
        body = round(self.frame + h)
        return (self.bar if self.top else height - body), body - self.bar

    def slide(self, full, h):
        return h - full if self.top else full - h

    def away(self, value):
        return value if self.top else -value

    def toward(self, value):
        return -value if self.top else value

    def outline_body(self, cr, width, height, x0, x1, h, detached, frame=None):
        """Обводка тела, растущего от этого края: плашки целиком, выреза — только по свободному краю."""
        cr.save()
        if detached:
            plate = lambda c: rounded_rect(c, x0, self.body_y(height, h, frame), x1 - x0, h,
                                           min(config.RADIUS, h / 2))
            stroke_inside(cr, plate, plate, OUTLINE_LAYERS, config.OUTLINE_THICKNESS)
        else:
            self.clip_bar(cr, width, height)
            self.to_edge(cr, height)
            stroke_inside(cr, lambda c: notch_path(c, x0, x1, self.frame, h, config.RADIUS),
                          lambda c: notch_edge_path(c, x0, x1, self.frame, h, config.RADIUS),
                          OUTLINE_LAYERS, config.OUTLINE_THICKNESS)
        cr.restore()

    def clip_inside(self, cr, width, height, frame=None):
        frame = self.frame if frame is None else frame
        cr.rectangle(0, frame if self.top else 0, width, height - frame)
        cr.clip()
