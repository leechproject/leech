import glob
import os
from dataclasses import dataclass

from modules.config.syntax import QUOTES

MODIFIERS = ("SUPER", "SHIFT", "CTRL", "ALT", "FN")
INVERT = "invertcolor"


class Invalid(ValueError):
    pass


@dataclass(frozen=True)
class Ref:
    key: str
    modifiers: tuple


@dataclass(frozen=True)
class Icon:
    glyph: str = None
    path: str = None
    invert: bool = False


@dataclass(frozen=True)
class Position:
    half: str
    side: str


@dataclass(frozen=True)
class Bind:
    modifiers: frozenset
    key: str


@dataclass(frozen=True)
class Custom:
    name: str
    icon: Icon
    cmd: str


def _escape(text, i):
    nxt = text[i + 1] if i + 1 < len(text) else ""
    if nxt in "uU":
        width = 4 if nxt == "u" else 8
        digits = text[i + 2:i + 2 + width]
        if len(digits) != width or any(c not in "0123456789abcdefABCDEF" for c in digits):
            raise Invalid(f"\\{nxt} ждёт {width} hex-цифр")
        code = int(digits, 16)
        if code > 0x10FFFF:
            raise Invalid(f"\\{nxt}{digits} вне диапазона Unicode")
        return chr(code), i + 2 + width
    if nxt == "n":
        return "\n", i + 2
    if nxt == "t":
        return "\t", i + 2
    if nxt:
        return nxt, i + 2
    return "\\", i + 1


def scan(text):
    pieces, i, n = [], 0, len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            j = i
            while j < n and text[j].isspace():
                j += 1
            pieces.append(("space", text[i:j]))
            i = j
        elif ch in QUOTES:
            out, j = [], i + 1
            while j < n and text[j] != ch:
                if text[j] == "\\":
                    piece, j = _escape(text, j)
                    out.append(piece)
                else:
                    out.append(text[j])
                    j += 1
            if j >= n:
                raise Invalid(f"не закрыта кавычка {ch}")
            pieces.append(("quoted", "".join(out)))
            i = j + 1
        elif ch == "/":
            pieces.append(("slash", "/"))
            i += 1
        else:
            out, j = [], i
            while j < n and not text[j].isspace() and text[j] not in QUOTES and text[j] != "/":
                if text[j] == "\\":
                    piece, j = _escape(text, j)
                    out.append(piece)
                else:
                    out.append(text[j])
                    j += 1
            pieces.append(("bare", "".join(out)))
            i = j
    return pieces


def text_value(raw):
    return "".join(value for _, value in scan(raw))


def path_value(raw, variables):
    pieces = scan(raw)
    kept = []
    for index, (kind, value) in enumerate(pieces):
        if kind == "space":
            before = pieces[index - 1][0] if index else "slash"
            after = pieces[index + 1][0] if index + 1 < len(pieces) else "slash"
            if before == "slash" or after == "slash":
                continue
        kept.append((kind, value))
    out = []
    for kind, value in kept:
        if kind == "bare" and value in variables:
            resolved = variables[value]
            if out and not out[-1].endswith("/"):
                raise Invalid(f"переменная {value} должна стоять в начале пути или после /")
            out.append(str(resolved))
        else:
            out.append(value)
    joined = "".join(out)
    while "//" in joined:
        joined = joined.replace("//", "/")
    return os.path.expanduser(joined)


def looks_like_path(raw, variables):
    pieces = [value for kind, value in scan(raw) if kind != "space"]
    if any(kind == "slash" for kind, _ in scan(raw)):
        return True
    return bool(pieces) and (pieces[0] in variables or pieces[0].startswith("~"))


class Type:
    def parse(self, raw, ctx):
        raise NotImplementedError


class Bool(Type):
    def parse(self, raw, ctx):
        value = raw.strip().lower()
        if value in ("y", "n"):
            return value == "y"
        raise Invalid(f"ожидается y или n, а не «{raw}»")


class Int(Type):
    def __init__(self, low=None, high=None):
        self.low, self.high = low, high

    def parse(self, raw, ctx):
        try:
            value = int(text_value(raw))
        except ValueError:
            raise Invalid(f"ожидается целое число, а не «{raw}»") from None
        if self.low is not None and value < self.low:
            raise Invalid(f"значение {value} меньше {self.low}")
        if self.high is not None and value > self.high:
            raise Invalid(f"значение {value} больше {self.high}")
        return value


class Float(Int):
    def parse(self, raw, ctx):
        try:
            value = float(text_value(raw).replace(",", "."))
        except ValueError:
            raise Invalid(f"ожидается число, а не «{raw}»") from None
        if self.low is not None and value < self.low:
            raise Invalid(f"значение {value} меньше {self.low}")
        if self.high is not None and value > self.high:
            raise Invalid(f"значение {value} больше {self.high}")
        return value


class Duration(Type):
    UNITS = (("ms", 1), ("s", 1000))

    def __init__(self, high_ms=10000):
        self.high = high_ms

    def parse(self, raw, ctx):
        text = text_value(raw).strip().lower().replace(" ", "")
        for unit, factor in self.UNITS:
            number = text[:-len(unit)]
            if text.endswith(unit) and number and not number[-1].isalpha():
                try:
                    value = float(number.replace(",", ".")) * factor
                except ValueError:
                    break
                if value < 0:
                    raise Invalid(f"длительность не может быть отрицательной: «{raw}»")
                if value > self.high:
                    raise Invalid(f"длительность {value:g} ms больше {self.high} ms")
                return round(value)
        raise Invalid(f"ожидается длительность в ms или s (например 220ms или 0.5s), а не «{raw}»")


class Text(Type):
    def parse(self, raw, ctx):
        return text_value(raw)


class Enum(Type):
    def __init__(self, *choices):
        self.choices = choices

    def parse(self, raw, ctx):
        value = text_value(raw).strip().lower()
        if value not in self.choices:
            raise Invalid(f"допустимые значения: {' | '.join(self.choices)}, а не «{raw}»")
        return value


class PathType(Type):
    def __init__(self, pattern=False):
        self.pattern = pattern

    def parse(self, raw, ctx):
        path = path_value(raw, ctx.variables)
        if self.pattern:
            matches = sorted(glob.glob(path)) if glob.has_magic(path) else [path]
            found = [m for m in matches if os.path.isfile(m)]
            if not found:
                raise Invalid(f"файлы не найдены: {path}")
            return tuple(found)
        return path


class IconType(Type):
    def parse(self, raw, ctx):
        value = raw.strip()
        base, _, modifier = value.partition(":")
        if modifier and base in ctx.siblings:
            modifiers = tuple(m.strip().lower() for m in modifier.split(":"))
            unknown = [m for m in modifiers if m != INVERT]
            if unknown:
                raise Invalid(f"неизвестный модификатор «{unknown[0]}» (есть только {INVERT})")
            return Ref(base, modifiers)
        if base in ctx.siblings and not modifier:
            return Ref(base, ())
        if looks_like_path(value, ctx.variables):
            return Icon(path=path_value(value, ctx.variables))
        glyph = text_value(value)
        if not glyph:
            raise Invalid("пустая иконка")
        return Icon(glyph=glyph)


class PositionType(Type):
    HALVES = ("lhalf", "rhalf")
    SIDES = ("left", "right")
    FULL = ("top", "bottom")

    def parse(self, raw, ctx):
        value = text_value(raw).strip().lower()
        if value in self.FULL:
            return Position("full", value)
        half, _, side = value.partition(":")
        if half in self.HALVES and side in self.SIDES:
            return Position(half, side)
        raise Invalid(f"ожидается lhalf|rhalf:left|right или top|bottom, а не «{raw}»")


class BindType(Type):
    def parse(self, raw, ctx):
        value = text_value(raw)
        separator = "," if "," in value else "+"
        parts = [p.strip().upper() for p in value.split(separator) if p.strip()]
        if not parts:
            raise Invalid("пустой бинд")
        *mods, key = parts
        unknown = [m for m in mods if m not in MODIFIERS]
        if unknown:
            raise Invalid(f"неизвестный модификатор «{unknown[0]}» (есть {', '.join(MODIFIERS)})")
        if key in MODIFIERS:
            raise Invalid("после модификаторов нужна клавиша")
        return Bind(frozenset(mods), key)


def parse_custom(item, ctx):
    unknown = sorted(set(item.args) - {"icon", "cmd"})
    if unknown:
        raise Invalid(f"у «{item.name}» неизвестный параметр «{unknown[0]}» (есть icon и cmd)")
    if not item.args.get("cmd"):
        raise Invalid(f"у «{item.name}» не задан cmd")
    icon = IconType().parse(item.args["icon"], ctx) if item.args.get("icon") else None
    if isinstance(icon, Ref):
        raise Invalid(f"у «{item.name}» icon не может ссылаться на другой параметр")
    return Custom(item.name, icon, text_value(item.args["cmd"]))
