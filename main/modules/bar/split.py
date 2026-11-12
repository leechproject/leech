NOTCH_GAP = 5


def gap(notch_width, margin=NOTCH_GAP):
    return notch_width + 2 * margin if notch_width >= 1 else 0


def pieces(x, width, center, gap_width):
    if gap_width < 1:
        return [(x, width)]
    left_end = center - gap_width / 2
    right_start = center + gap_width / 2
    result = []
    if left_end > x:
        result.append((x, left_end - x))
    if right_start < x + width:
        result.append((right_start, x + width - right_start))
    return result
