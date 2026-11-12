def visible_length(sizes, spacing, limit):
    shown = sizes if limit <= 0 else sizes[:limit]
    if not shown:
        return 0
    return sum(shown) + spacing * (len(shown) - 1)


def fade_strengths(value, upper, page, fade):
    if fade <= 0:
        return 0.0, 0.0
    hidden_far = max(0.0, value)
    hidden_near = max(0.0, upper - page - value)
    return min(1.0, hidden_far / fade), min(1.0, hidden_near / fade)


def clamp_scroll(value, upper, page):
    return max(0.0, min(value, max(0.0, upper - page)))
