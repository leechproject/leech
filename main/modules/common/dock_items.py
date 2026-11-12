import math
from collections import Counter, namedtuple

DockItem = namedtuple("DockItem", "app_id info pinned dots")

SEPARATOR_W = 1
DOT = 3
DOT_GAP = 2
DOT_OFFSET = 5


def class_keys(desktop_id, wm_class, executable):
    keys = [desktop_id.removesuffix(".desktop")]
    if wm_class:
        keys.append(wm_class)
    if executable:
        keys.append(executable.rsplit("/", 1)[-1])
    keys.append(keys[0].rsplit(".", 1)[-1])
    return [key.lower() for key in keys if key]


def build_index(entries):
    index = {}
    for desktop_id, wm_class, executable in entries:
        for priority, key in enumerate(class_keys(desktop_id, wm_class, executable)):
            if key not in index or index[key][0] > priority:
                index[key] = (priority, desktop_id)
    return {key: desktop_id for key, (_, desktop_id) in index.items()}


def resolve(window_class, index):
    if not window_class:
        return None
    key = window_class.lower()
    return index.get(key) or index.get(key.rsplit(".", 1)[-1])


def arrange(pinned_ids, running_ids, show_launched):
    counts = Counter(running_ids)
    pinned = set(pinned_ids)
    launched = []
    if show_launched:
        for app_id in reversed(running_ids):
            if app_id not in pinned and app_id not in launched:
                launched.append(app_id)
    return launched[::-1], counts


def offsets(pinned, launched, edge, icon, gap):
    x = edge
    positions = []
    separator = None
    for index in range(pinned + launched):
        if index == pinned and pinned and launched:
            separator = x
            x += SEPARATOR_W + gap
        positions.append(x)
        x += icon + gap
    width = x - gap + edge if positions else 0
    return positions, separator, width


def dot_offsets(count, icon):
    fits = max(1, (icon + DOT_GAP) // (DOT + DOT_GAP))
    count = min(count, fits)
    total = count * DOT + (count - 1) * DOT_GAP
    start = (icon - total) / 2
    return [start + i * (DOT + DOT_GAP) for i in range(count)]


def dot_top(icon_top, icon, top):
    return icon_top - DOT_OFFSET - DOT if top else icon_top + icon + DOT_OFFSET


def snap_line(x, output_scale, buffer_scale=None):
    if not output_scale:
        return x, SEPARATOR_W
    width = max(1, round(SEPARATOR_W * output_scale))
    pixel = math.floor(x * output_scale + (SEPARATOR_W * output_scale - width) / 2 + 0.5)
    left, right = pixel / output_scale, (pixel + width) / output_scale
    if buffer_scale:
        left = math.floor(left * buffer_scale + 1e-6) / buffer_scale
        right = math.ceil(right * buffer_scale - 1e-6) / buffer_scale
    return left, right - left
