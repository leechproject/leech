from modules import config

ROW_H = config.LAUNCHER_ROW_H
GAP = config.LAUNCHER_ROW_GAP
PITCH = ROW_H + GAP
EDGE = config.LAUNCHER_EDGE
ICON = config.DOCK_ICON

MENU_PAD = config.LAUNCHER_MENU_PAD
MENU_EDGE = config.LAUNCHER_MENU_EDGE
MENU_GAP = config.LAUNCHER_MENU_GAP
MENU_ICON = config.LAUNCHER_MENU_ICON
MENU_ITEMS = 3
MENU_ITEM_H = MENU_ICON + 2 * MENU_PAD
MENU_H = MENU_EDGE + MENU_ITEMS * MENU_ITEM_H + (MENU_ITEMS - 1) * MENU_GAP + MENU_EDGE
MENU_EXTRA = MENU_H + GAP

PAD_L, ICON_GAP, PAD_R = 4, 5, 2


def dock_width(n, edge=config.DOCK_EDGE, icon=config.DOCK_ICON, gap=config.DOCK_GAP):
    return 2 * edge + n * icon + (n - 1) * gap if n > 0 else 0


def launcher_width(pinned_count, extra=0):
    return max(dock_width(config.LAUNCHER_MIN_ICONS), dock_width(pinned_count) + extra)


def plate_width(width):
    return width - 2 * EDGE


def text_width(width):
    return plate_width(width) - PAD_L - ICON - ICON_GAP - PAD_R


MIN_TEXT = 8


def shows_text(width):
    return text_width(width) >= MIN_TEXT


def menu_text_width(width):
    item_w = width - 2 * MENU_PAD - 2 * MENU_EDGE
    return item_w - MENU_PAD - MENU_ICON - 6 - 3


SEARCH_H = config.LAUNCHER_SEARCH_H
SEARCH_GAP = config.LAUNCHER_SEARCH_GAP
SEARCH_EDGE = config.LAUNCHER_SEARCH_EDGE
LIST_OFFSET = config.LAUNCHER_HEAD_H + SEARCH_H + SEARCH_GAP


def list_height(body_h):
    return body_h - LIST_OFFSET - EDGE


def row_top(index, menu_row):
    return index * PITCH + (MENU_EXTRA if menu_row is not None and index > menu_row else 0)


def menu_top(menu_row):
    return (menu_row + 1) * PITCH


def content_height(count, menu_row):
    return max(0, count * PITCH - GAP) + (MENU_EXTRA if menu_row is not None else 0)


def clamp_scroll(scroll, count, menu_row, view_h):
    return max(0, min(max(0, content_height(count, menu_row) - view_h), scroll))


def scroll_to_show(scroll, index, count, menu_row, view_h, with_menu=False):
    top = row_top(index, menu_row)
    bottom = top + ROW_H + (MENU_EXTRA if with_menu else 0)
    if top < scroll:
        scroll = top
    elif bottom > scroll + view_h:
        scroll = bottom - view_h
    return clamp_scroll(scroll, count, menu_row, view_h)


def hit(y, scroll, count, menu_row):
    yy = y + scroll
    if yy < 0:
        return None
    if menu_row is not None:
        top = menu_top(menu_row)
        if yy >= top:
            if yy < top + MENU_H:
                inside = yy - top - MENU_EDGE
                step = MENU_ITEM_H + MENU_GAP
                k, rest = divmod(inside, step)
                return ("menu", int(k)) if 0 <= k < MENU_ITEMS and rest < MENU_ITEM_H else None
            if yy < top + MENU_EXTRA:
                return None
            yy -= MENU_EXTRA
    index, rest = divmod(yy, PITCH)
    return ("row", int(index)) if rest < ROW_H and 0 <= index < count else None


def move(index, key, count, page):
    if key == "up":
        return max(0, index - 1)
    if key == "down":
        return min(count - 1, index + 1)
    if key == "home":
        return 0
    if key == "end":
        return count - 1
    if key == "pgup":
        return max(0, index - page)
    if key == "pgdn":
        return min(count - 1, index + page)
    return index


def _rank(name, query):
    name = name.casefold()
    if name.startswith(query):
        return 0
    if any(word.startswith(query) for word in name.replace("-", " ").replace("_", " ").split()):
        return 1
    return 2 if query in name else None


def build_rows(entries, query, liked, hidden, show_hidden):
    pool = [e for e in entries if show_hidden or e.id not in hidden]
    like_order = {app_id: index for index, app_id in enumerate(liked)}
    query = query.strip().casefold()
    ranked = []
    for position, entry in enumerate(pool):
        rank = 0 if not query else _rank(entry.name, query)
        if rank is None:
            continue
        liked_key = -like_order[entry.id] if entry.id in like_order else 1
        ranked.append((rank, 0 if entry.id in like_order else 1, liked_key, position, entry))
    ranked.sort(key=lambda item: item[:4])
    return [item[4] for item in ranked]
