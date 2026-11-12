from dataclasses import dataclass


@dataclass(frozen=True)
class Layout:
    x0: int
    x1: int
    body_h: int
    cols: int
    rows: int
    cell_w: int
    cell_h: int
    gap: int
    grid_x: int
    grid_y: int


def compute(width, height, left, right, top, bottom, margin, pad, gap, cols, from_top=False, rows=None):
    margin_top, margin_right, margin_left = (margin,) * 3 if isinstance(margin, int) else margin
    x0 = left + margin_left
    x1 = width - right - margin_right
    body_top = top if from_top else top + margin_top
    body_h = height - bottom - top - margin_top
    inner_w = (x1 - x0) - 2 * pad
    inner_h = body_h - 2 * pad

    cell_w = (inner_w - (cols - 1) * gap) // cols
    if rows:
        cell_h = (inner_h - (rows - 1) * gap) // rows
    else:
        cell_h = min(round(cell_w * height / width), inner_h)
        rows = max(1, (inner_h + gap) // (cell_h + gap))

    grid_w = cols * cell_w + (cols - 1) * gap
    grid_h = rows * cell_h + (rows - 1) * gap
    return Layout(x0=x0, x1=x1, body_h=body_h, cols=cols, rows=rows, cell_w=cell_w, cell_h=cell_h, gap=gap,
                  grid_x=x0 + ((x1 - x0) - grid_w) // 2, grid_y=body_top + (body_h - grid_h) // 2)


def cell_rect(layout, index, top_row):
    row, col = divmod(index, layout.cols)
    return (layout.grid_x + col * (layout.cell_w + layout.gap),
            layout.grid_y + (row - top_row) * (layout.cell_h + layout.gap),
            layout.cell_w, layout.cell_h)


def cell_at(layout, x, y, top_row, count):
    dx, dy = x - layout.grid_x, y - layout.grid_y
    if dx < 0 or dy < 0:
        return None
    col, rest_x = divmod(dx, layout.cell_w + layout.gap)
    row, rest_y = divmod(dy, layout.cell_h + layout.gap)
    if col >= layout.cols or row >= layout.rows or rest_x >= layout.cell_w or rest_y >= layout.cell_h:
        return None
    index = (top_row + int(row)) * layout.cols + int(col)
    return index if index < count else None


def max_top_row(layout, count):
    total_rows = -(-count // layout.cols)
    return max(0, total_rows - layout.rows)


def clamp_top_row(layout, top_row, count):
    return max(0, min(max_top_row(layout, count), top_row))


def scroll_to_show(layout, top_row, index, count):
    row = index // layout.cols
    if row < top_row:
        top_row = row
    elif row >= top_row + layout.rows:
        top_row = row - layout.rows + 1
    return clamp_top_row(layout, top_row, count)


def move(layout, index, key, count):
    cols = layout.cols
    if key == "left":
        return max(0, index - 1)
    if key == "right":
        return min(count - 1, index + 1)
    if key == "up":
        return index - cols if index - cols >= 0 else index
    if key == "down":
        if index + cols < count:
            return index + cols
        last_row = (count - 1) // cols
        return count - 1 if index // cols < last_row else index
    if key == "home":
        return 0
    if key == "end":
        return count - 1
    page = layout.rows * cols
    if key == "pgup":
        return max(0, index - page)
    if key == "pgdn":
        return min(count - 1, index + page)
    return index
