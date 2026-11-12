from dataclasses import dataclass

_COLUMN = {("lhalf", "left"): 0, ("lhalf", "right"): 1, ("rhalf", "left"): 2, ("rhalf", "right"): 3}


@dataclass(frozen=True)
class Place:
    key: object
    x: int
    y: int
    w: int
    h: int


@dataclass(frozen=True)
class Metrics:
    width: int
    gap: int
    small: int
    wide_h: int

    @property
    def block_h(self):
        return 2 * self.small + self.gap


def split(width, count, gap):
    if count <= 0:
        return []
    room = width - gap * (count - 1)
    base, extra = divmod(room, count)
    return [base + (1 if i < extra else 0) for i in range(count)]


def _row(keys, x, y, width, height, gap):
    places, cx = [], x
    for key, w in zip(keys, split(width, len(keys), gap)):
        places.append(Place(key, cx, y, w, height))
        cx += w + gap
    return places


def _vertical_sliders(sliders, y, m):
    left = sorted((s for s in sliders if s[1].half == "lhalf"), key=lambda s: _COLUMN[(s[1].half, s[1].side)])
    right = sorted((s for s in sliders if s[1].half != "lhalf"), key=lambda s: _COLUMN.get((s[1].half, s[1].side), 3))
    places = []
    for i, (key, _) in enumerate(left):
        places.append(Place(key, i * (m.small + m.gap), y, m.small, m.block_h))
    for i, (key, _) in enumerate(reversed(right)):
        places.append(Place(key, m.width - (i + 1) * m.small - i * m.gap, y, m.small, m.block_h))
    free_x = len(left) * (m.small + m.gap)
    free_w = m.width - free_x - len(right) * (m.small + m.gap)
    return places, free_x, free_w


def _horizontal_order(sliders):
    def rank(item):
        key, position = item
        if position.half == "full":
            return (0 if position.side == "top" else 1, 0)
        return (0 if key == "brightness" else 1, 1)
    return sorted(sliders, key=rank)


def controls(groups, m, horizontal=False):
    places, y, i = [], 0, 0
    groups = [g for g in groups if g[1]]
    while i < len(groups):
        kind, items = groups[i]
        if y:
            y += m.gap
        if kind == "row":
            places += _row(items, 0, y, m.width, m.wide_h, m.gap)
            y += m.wide_h
            i += 1
            continue
        if horizontal:
            for n, (key, _) in enumerate(_horizontal_order(items)):
                if n:
                    y += m.gap
                places.append(Place(key, 0, y, m.width, m.small))
                y += m.small
            i += 1
            continue
        slider_places, free_x, free_w = _vertical_sliders(items, y, m)
        places += slider_places
        beside = []
        j = i + 1
        while j < len(groups) and len(beside) < 2 and groups[j][0] == "row" and free_w > 0:
            beside.append(groups[j][1])
            j += 1
        heights = split(m.block_h, len(beside), m.gap)
        line_y = y
        for keys, h in zip(beside, heights):
            places += _row(keys, free_x, line_y, free_w, h, m.gap)
            line_y += h + m.gap
        y += m.block_h
        i = j
    return places, y


def order_groups(rows, priorities, sliders, sliders_priority):
    entries = [("sliders", sliders_priority, 0, sliders)]
    for index, (name, keys) in enumerate(rows):
        priority = priorities.get(name)
        entries.append(("row", priority, index + 1, keys))
    entries.sort(key=lambda e: (e[1] is None, e[1] if e[1] is not None else 0, e[2]))
    return [(kind, items) for kind, _, _, items in entries]
