from dataclasses import dataclass, field

QUOTES = "\"'"


@dataclass
class Entry:
    key: str
    raw: str
    line: int
    quoted: bool = False


@dataclass
class Item:
    name: str
    args: dict
    line: int


@dataclass
class Section:
    name: str
    line: int
    entries: dict = field(default_factory=dict)
    sections: dict = field(default_factory=dict)
    items: list = field(default_factory=list)


@dataclass
class Problem:
    line: int
    message: str

    def __str__(self):
        return f"строка {self.line}: {self.message}" if self.line else self.message


def strip_comment(line):
    quote = None
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == "\\":
            i += 2
            continue
        if quote:
            if ch == quote:
                quote = None
        elif ch in QUOTES:
            quote = ch
        elif ch == "#":
            return line[:i]
        i += 1
    return line


def _split_top(text, separators):
    parts, start, quote, depth, i = [], 0, None, 0, 0
    while i < len(text):
        ch = text[i]
        if ch == "\\":
            i += 2
            continue
        if quote:
            if ch == quote:
                quote = None
        elif ch in QUOTES:
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif depth == 0 and ch in separators:
            parts.append(text[start:i])
            parts.append(ch)
            start = i + 1
        i += 1
    parts.append(text[start:])
    return parts


def find_top(text, char):
    parts = _split_top(text, char)
    return len(parts[0]) if len(parts) > 1 else -1


def find_unquoted(text, char, start=0):
    quote, i = None, start
    while i < len(text):
        ch = text[i]
        if ch == "\\":
            i += 2
            continue
        if quote:
            if ch == quote:
                quote = None
        elif ch in QUOTES:
            quote = ch
        elif ch == char:
            return i
        i += 1
    return -1


def matching_paren(text, open_at):
    quote, depth, i = None, 0, open_at
    while i < len(text):
        ch = text[i]
        if ch == "\\":
            i += 2
            continue
        if quote:
            if ch == quote:
                quote = None
        elif ch in QUOTES:
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def unquote_key(key):
    if len(key) >= 2 and key[0] in QUOTES and key[-1] == key[0]:
        return key[1:-1], True
    return key, False


def _parse_item(text, line, problems):
    open_at = find_unquoted(text, "(")
    name = text[:open_at].strip()
    close = matching_paren(text, open_at)
    if close < 0:
        problems.append(Problem(line, f"не закрыта скобка в «{text.strip()}»"))
        return None
    body, tail = text[open_at + 1:close], text[close + 1:]
    if tail.strip():
        problems.append(Problem(line, f"лишний текст после «{name}(...)»: «{tail.strip()}» (комментарий начинается с #)"))
    args = {}
    for part in _split_top(body, ";")[::2]:
        if not part.strip():
            continue
        eq = find_unquoted(part, "=")
        if eq < 0:
            problems.append(Problem(line, f"в «{name}(...)» ожидается ключ = значение, а не «{part.strip()}»"))
            continue
        key, _ = unquote_key(part[:eq].strip())
        args[key] = part[eq + 1:].strip()
    return Item(name, args, line)


def _is_name(text):
    return bool(text) and all(ch.isalnum() or ch in "-_" for ch in text)


def parse(text):
    root = Section("", 0)
    stack = [root]
    problems = []
    pending = None
    for number, raw_line in enumerate(text.splitlines(), 1):
        line = strip_comment(raw_line)
        for token in _split_top(line, "{}"):
            if token == "{":
                if pending is None:
                    problems.append(Problem(number, "«{» без имени секции"))
                    pending = ""
                name = pending
                pending = None
                section = stack[-1].sections.get(name)
                if section is None:
                    section = Section(name, number)
                    stack[-1].sections[name] = section
                stack.append(section)
                continue
            if token == "}":
                if pending:
                    problems.append(Problem(number, f"непонятная строка «{pending}»"))
                    pending = None
                if len(stack) == 1:
                    problems.append(Problem(number, "лишняя «}»"))
                else:
                    stack.pop()
                continue
            statement = token.strip()
            if not statement:
                continue
            if pending:
                problems.append(Problem(number, f"непонятная строка «{pending}»"))
                pending = None
            eq = find_top(statement, "=")
            paren = find_unquoted(statement, "(")
            if eq >= 0 and (paren < 0 or eq < paren):
                key, quoted = unquote_key(statement[:eq].strip())
                if not key:
                    problems.append(Problem(number, "пустое имя параметра"))
                    continue
                section = stack[-1]
                if key in section.entries:
                    problems.append(Problem(number, f"«{key}» уже задан в строке {section.entries[key].line}, "
                                                    f"используется последнее значение"))
                section.entries[key] = Entry(key, statement[eq + 1:].strip(), number, quoted)
            elif paren > 0:
                item = _parse_item(statement, number, problems)
                if item is not None:
                    stack[-1].items.append(item)
            elif _is_name(statement):
                pending = statement
            else:
                problems.append(Problem(number, f"непонятная строка «{statement}»"))
    if pending:
        problems.append(Problem(0, f"после «{pending}» ожидалась «{{»"))
    for section in stack[1:]:
        problems.append(Problem(section.line, f"секция «{section.name}» не закрыта"))
    return root, problems
