from modules import config

PAD = config.KC_PAD
ITEM_H = 34
HEAD_H = 26
VISIBLE = 4
PITCH = ITEM_H + PAD
RADIUS = 10
ITEM_RADIUS = 8

MENU_PAD = config.LAUNCHER_MENU_PAD
MENU_EDGE = config.LAUNCHER_MENU_EDGE
MENU_GAP = config.LAUNCHER_MENU_GAP
MENU_ICON = config.LAUNCHER_MENU_ICON
MENU_ITEM_H = MENU_ICON + 2 * MENU_PAD


def slots(count):
    return max(1, min(VISIBLE, count))


def list_height(count):
    n = slots(count)
    return n * ITEM_H + (n - 1) * PAD


def plate_height(count, header, view=None):
    return PAD + (HEAD_H + PAD if header else 0) + (list_height(count) if view is None else view) + PAD


def view_height(count, menu_row, menu_items):
    full = list_height(VISIBLE)
    return min(full, max(list_height(count), content_height(count, menu_row, menu_items)))


def list_top(header):
    return PAD + (HEAD_H + PAD if header else 0)


def menu_height(items):
    return MENU_EDGE + items * MENU_ITEM_H + (items - 1) * MENU_GAP + MENU_EDGE if items else 0


def menu_extra(items):
    return menu_height(items) + PAD if items else 0


def row_top(index, menu_row, menu_items):
    return index * PITCH + (menu_extra(menu_items) if menu_row is not None and index > menu_row else 0)


def menu_top(menu_row):
    return (menu_row + 1) * PITCH


def content_height(count, menu_row, menu_items):
    return max(0, count * PITCH - PAD) + (menu_extra(menu_items) if menu_row is not None else 0)


def clamp_scroll(scroll, count, menu_row, menu_items, view_h):
    return max(0.0, min(max(0, content_height(count, menu_row, menu_items) - view_h), scroll))


def scroll_to_show(scroll, index, count, menu_row, menu_items, view_h):
    top = row_top(index, menu_row, menu_items)
    bottom = top + ITEM_H + (menu_extra(menu_items) if menu_row == index else 0)
    if bottom - top > view_h:
        bottom = top + view_h
    if top < scroll:
        scroll = top
    elif bottom > scroll + view_h:
        scroll = bottom - view_h
    return clamp_scroll(scroll, count, menu_row, menu_items, view_h)


def hit(y, scroll, count, menu_row, menu_items):
    yy = y + scroll
    if yy < 0:
        return None
    if menu_row is not None:
        top = menu_top(menu_row)
        if yy >= top:
            if yy < top + menu_height(menu_items):
                inside = yy - top - MENU_EDGE
                k, rest = divmod(inside, MENU_ITEM_H + MENU_GAP)
                return ("menu", int(k)) if 0 <= k < menu_items and rest < MENU_ITEM_H else None
            if yy < top + menu_extra(menu_items):
                return None
            yy -= menu_extra(menu_items)
    index, rest = divmod(yy, PITCH)
    return ("row", int(index)) if rest < ITEM_H and 0 <= index < count else None


def header_buttons(width, count):
    size = HEAD_H
    right = width - PAD
    return [(right - (i + 1) * size - i * PAD, size) for i in range(count)][::-1]
