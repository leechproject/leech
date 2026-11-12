import gi

gi.require_version("Gdk", "3.0")
from gi.repository import Gdk

_M = Gdk.ModifierType
MODIFIER_MASKS = {
    "SHIFT": _M.SHIFT_MASK,
    "CTRL": _M.CONTROL_MASK,
    "ALT": _M.MOD1_MASK,
    "SUPER": _M.SUPER_MASK | _M.MOD4_MASK,
}
_RELEVANT = _M.SHIFT_MASK | _M.CONTROL_MASK | _M.MOD1_MASK | _M.SUPER_MASK | _M.MOD4_MASK

KEY_ALIASES = {
    "ENTER": ("Return", "KP_Enter"),
    "RETURN": ("Return", "KP_Enter"),
    "ESC": ("Escape",),
    "SPACE": ("space",),
    "TAB": ("Tab", "ISO_Left_Tab"),
    "BACKSPACE": ("BackSpace",),
    "DEL": ("Delete",),
    "DELETE": ("Delete",),
    "MENU": ("Menu",),
    "UP": ("Up",),
    "DOWN": ("Down",),
    "LEFT": ("Left",),
    "RIGHT": ("Right",),
}


def keyvals(key):
    names = KEY_ALIASES.get(key) or (key, key.lower(), key.capitalize())
    found = set()
    for name in names:
        value = Gdk.keyval_from_name(name)
        if value != Gdk.KEY_VoidSymbol and value != 0:
            found.add(Gdk.keyval_to_lower(value))
    return frozenset(found)


def matches(bind, event):
    if bind is None or Gdk.keyval_to_lower(event.keyval) not in keyvals(bind.key):
        return False
    wanted = 0
    for name in bind.modifiers:
        wanted |= MODIFIER_MASKS.get(name, 0)
    state = event.state & _RELEVANT
    if "SUPER" in bind.modifiers:
        return bool(state & MODIFIER_MASKS["SUPER"]) and \
            (state & ~MODIFIER_MASKS["SUPER"]) == (wanted & ~MODIFIER_MASKS["SUPER"])
    return state == wanted
