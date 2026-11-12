import re

from modules.config.geometry import scaled

BAR_IDS = ("#bar", "#main-inner-sub", "#box-", "#launcher-btn", "#ws-", "#tray-")
SCOPE = "#bar-root"

_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_BLOCK = re.compile(r"([^{}]+)\{([^{}]*)\}")
_PX = re.compile(r"(-?\d+(?:\.\d+)?)px")


def _scale_value(value, scale):
    return _PX.sub(lambda m: f"{scaled(float(m.group(1)), scale)}px", value)


def _sized(body, scale):
    declarations = []
    for declaration in body.split(";"):
        name, colon, value = declaration.partition(":")
        if colon and _PX.search(value):
            declarations.append(f"{name.strip()}: {_scale_value(value.strip(), scale)};")
    return " ".join(declarations)


def _is_bar(selector):
    return any(marker in selector for marker in BAR_IDS)


def _is_generic(selector):
    return "#" not in selector and "." not in selector and ":" not in selector


def scaled_css(text, scale):
    if scale == 1:
        return ""
    generic, own = [], []
    for selectors, body in _BLOCK.findall(_COMMENT.sub("", text)):
        names = [name.strip() for name in selectors.split(",") if name.strip()]
        sized = _sized(body, scale)
        if not sized:
            continue
        bar = [name for name in names if _is_bar(name)]
        if bar:
            own.append(f"{', '.join(bar)} {{ {sized} }}")
        plain = [f"{SCOPE} {name}" for name in names if _is_generic(name)]
        if plain:
            generic.append(f"{', '.join(plain)} {{ {sized} }}")
    return "\n".join(generic + own)
