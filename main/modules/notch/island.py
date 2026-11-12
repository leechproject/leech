GAP = 5


def radius(h, idle_h, expanded_h, expanded_radius):
    pill = h / 2
    if h <= idle_h or expanded_h <= idle_h:
        return pill
    t = min(1.0, (h - idle_h) / (expanded_h - idle_h))
    start = idle_h / 2
    return min(pill, start + (expanded_radius - start) * t)
