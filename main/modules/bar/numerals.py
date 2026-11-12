_ROMAN = ((1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
          (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"))
_CHINESE_DIGITS = "〇一二三四五六七八九"


def roman(n):
    out = []
    for value, letters in _ROMAN:
        count, n = divmod(n, value)
        out.append(letters * count)
    return "".join(out)


def chinese(n):
    if n < 10:
        return _CHINESE_DIGITS[n]
    if n < 100:
        tens, ones = divmod(n, 10)
        return ("" if tens == 1 else _CHINESE_DIGITS[tens]) + "十" + (_CHINESE_DIGITS[ones] if ones else "")
    hundreds, rest = divmod(n, 100)
    if rest == 0:
        tail = ""
    elif rest < 10:
        tail = "〇" + _CHINESE_DIGITS[rest]
    else:
        tens, ones = divmod(rest, 10)
        tail = _CHINESE_DIGITS[tens] + "十" + (_CHINESE_DIGITS[ones] if ones else "")
    return _CHINESE_DIGITS[hundreds] + "百" + tail


def workspace_label(n, style):
    if style == "roman":
        return roman(n)
    if style == "chinese":
        return chinese(n)
    return str(n)


def workspace_symbol(n, state, style, icons):
    glyph = icons.get(state)
    return glyph if glyph else workspace_label(n, style)
