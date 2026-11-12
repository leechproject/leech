def group_start(full_width, area_width, group_width, left):
    if left:
        return 0
    centered = (full_width - group_width) // 2
    return max(0, min(centered, area_width - group_width))


def fade_strength(value, upper, page, fade):
    hidden = upper - page - value
    return max(0.0, min(1.0, hidden / fade)) if fade > 0 else 0.0


def grid_cell(index, columns):
    return divmod(index, columns)


def grid_size(count, columns, icon, spacing):
    if count <= 0:
        return 0, 0
    cols = min(columns, count)
    rows = -(-count // columns)
    return 2 * spacing + cols * icon + (cols - 1) * spacing, 2 * spacing + rows * icon + (rows - 1) * spacing


def window_left(center, width, screen_width, edge):
    return max(edge, min(round(center - width / 2), screen_width - edge - width))
