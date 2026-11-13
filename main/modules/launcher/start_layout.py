from modules.common import theme

FOOTER_H = 48
FOOTER_EDGE = theme.pad("#start-footer")
BUTTON = FOOTER_H - 2 * FOOTER_EDGE
MENU_PAD = theme.pad("#start-menu")
MENU_ITEM_H = 34
MENU_W = 150
MENU_ITEMS = ("sleep", "reboot", "shutdown")
SCREEN_GAP = theme.gap("#start-launcher")
NAME_GAP = theme.gap("#start-footer")
REFERENCE_ICONS = 16


def body_height(screen_height):
    return screen_height // 2 + 40


def body_left(screen_width, width, left_mode, frame_left):
    return frame_left + SCREEN_GAP if left_mode else (screen_width - width) // 2


def footer_space():
    return FOOTER_H + FOOTER_EDGE


def footer(x0, x1, body_bottom):
    return x0 + FOOTER_EDGE, body_bottom - FOOTER_EDGE - FOOTER_H, x1 - x0 - 2 * FOOTER_EDGE, FOOTER_H


def avatar(plate):
    x, y, _w, _h = plate
    return x + FOOTER_EDGE, y + FOOTER_EDGE, BUTTON, BUTTON


def username(plate):
    ax, y, aw, h = avatar(plate)
    x = ax + aw + NAME_GAP
    return x, y, max(0, settings(plate)[0] - NAME_GAP - x), h


def power(plate):
    x, y, w, _h = plate
    return x + w - FOOTER_EDGE - BUTTON, y + FOOTER_EDGE, BUTTON, BUTTON


def settings(plate):
    x, y, w, h = power(plate)
    return x - FOOTER_EDGE - w, y, w, h


def menu(power_rect):
    x, y, w, _h = power_rect
    height = 2 * MENU_PAD + len(MENU_ITEMS) * MENU_ITEM_H + (len(MENU_ITEMS) - 1) * MENU_PAD
    return x + w - MENU_W, y - FOOTER_EDGE - height, MENU_W, height


def menu_item(menu_rect, index):
    x, y, w, _h = menu_rect
    return x + MENU_PAD, y + MENU_PAD + index * (MENU_ITEM_H + MENU_PAD), w - 2 * MENU_PAD, MENU_ITEM_H


def inside(rect, px, py):
    x, y, w, h = rect
    return x <= px < x + w and y <= py < y + h


def hit(x0, x1, body_bottom, px, py, menu_open):
    plate = footer(x0, x1, body_bottom)
    if menu_open:
        box = menu(power(plate))
        for index in range(len(MENU_ITEMS)):
            if inside(menu_item(box, index), px, py):
                return ("power-menu", index)
        if inside(box, px, py):
            return ("power-menu", None)
    for kind, rect in (("power", power(plate)), ("settings", settings(plate)), ("avatar", avatar(plate))):
        if inside(rect, px, py):
            return (kind,)
    if inside(plate, px, py):
        return ("footer",)
    return None
