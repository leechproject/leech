"""Arrow-key navigation between CC buttons by their on-screen rectangles."""

_AXES = {"left": (0, -1), "right": (0, 1), "up": (1, -1), "down": (1, 1)}


def _span(rect, axis):
    x, y, w, h = rect
    return (x, x + w) if axis == 0 else (y, y + h)


def step(rects, current, direction):
    """Index of the nearest rectangle from rects[current] in direction, or None.

    Candidates must lie entirely beyond the current one along the axis. Among
    them a candidate overlapping the current one across the axis wins, then the
    smallest gap along the axis, then the smallest offset of the centres across it.
    """
    axis, sign = _AXES[direction]
    cross = 1 - axis
    lo, hi = _span(rects[current], axis)
    clo, chi = _span(rects[current], cross)
    best = None
    for index, rect in enumerate(rects):
        if index == current:
            continue
        olo, ohi = _span(rect, axis)
        gap = olo - hi if sign > 0 else lo - ohi
        if gap < 0:
            continue
        plo, phi = _span(rect, cross)
        overlap = min(chi, phi) - max(clo, plo)
        offset = abs((plo + phi) / 2 - (clo + chi) / 2)
        score = (overlap <= 0, gap, offset)
        if best is None or score < best[0]:
            best = (score, index)
    return None if best is None else best[1]

