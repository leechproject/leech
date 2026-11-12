import os
import re
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path

from modules.config import syntax
from modules.config.schema import SCHEMA, VARIABLES, P, Rows
from modules.config.syntax import Problem
from modules.config.values import INVERT, Bool, Icon, Invalid, Ref, parse_custom

ROW_SECTION = re.compile(r"^row\d+$")
HEADER = """#########
# LEECH #
#########

# y = yes, n = no. empty value = default.
"""


@dataclass
class Context:
    variables: dict
    siblings: frozenset = frozenset()


@dataclass
class Row:
    named: dict = field(default_factory=dict)
    custom: list = field(default_factory=list)
    order: list = field(default_factory=list)

    def visible(self):
        return [item for item in self.order if not isinstance(item, str) or self.named.get(item)]


class Settings:
    def __init__(self, values):
        self._values = values

    def get(self, dotted):
        node = self._values
        for part in dotted.split("."):
            node = node[part]
        return node

    def __getitem__(self, dotted):
        return self.get(dotted)


def _parse_value(param, raw, ctx):
    if not raw:
        return None
    return param.type.parse(raw, ctx)


def _resolve(param, entry, ctx, where, problems):
    if entry is not None and entry.raw != "":
        try:
            return _parse_value(param, entry.raw, ctx)
        except Invalid as e:
            problems.append(Problem(entry.line, f"{where}: {e}; используется значение по умолчанию"))
    try:
        return _parse_value(param, param.default, ctx)
    except Invalid as e:
        problems.append(Problem(0, f"{where}: значение по умолчанию недоступно ({e})"))
        return None


def _note_unsupported(spec, entry, value, ctx, path, problems):
    if spec.implemented or entry is None or entry.raw == "":
        return
    try:
        default = _parse_value(spec, spec.default, ctx)
    except Invalid:
        default = None
    if value != default:
        problems.append(Problem(entry.line, f"{path}: пока не поддерживается, значение не применяется"))


def _apply_refs(values, problems, where):
    for key, value in list(values.items()):
        if isinstance(value, Ref):
            target = values.get(value.key)
            if isinstance(target, Ref):
                problems.append(Problem(0, f"{where}.{key}: ссылка на ссылку не поддерживается"))
                target = None
            if isinstance(target, Icon) and INVERT in value.modifiers:
                target = replace(target, invert=not target.invert)
            values[key] = target


def _walk(schema, section, ctx, where, problems):
    values = {}
    ctx = Context(ctx.variables, frozenset(k for k, v in schema.items() if isinstance(v, P)))
    row_spec = schema.get("*rows")
    for key, spec in schema.items():
        if isinstance(spec, Rows) or (not where and key in VARIABLES):
            continue
        path = f"{where}.{key}" if where else key
        if isinstance(spec, dict):
            sub = section.sections.get(key) if section else None
            if row_spec is not None and ROW_SECTION.match(key):
                values[key] = _row(spec, sub, ctx, path, problems, row_spec)
            else:
                values[key] = _walk(spec, sub, ctx, path, problems)
            continue
        entry = section.entries.get(key) if section else None
        if entry is not None and entry.quoted and not spec.named:
            problems.append(Problem(entry.line, f"{path}: кавычки у этого ключа не нужны"))
        values[key] = _resolve(spec, entry, ctx, path, problems)
        _note_unsupported(spec, entry, values[key], ctx, path, problems)
    _apply_refs(values, problems, where or "конфиг")
    if section is None:
        return values
    place = where or "корне"
    for key, entry in section.entries.items():
        spec = schema.get(key)
        if isinstance(spec, dict):
            problems.append(Problem(entry.line, f"«{key}» — секция, ожидается «{key} {{ ... }}»"))
        elif spec is None or isinstance(spec, Rows):
            problems.append(Problem(entry.line, f"неизвестный параметр «{key}» в «{place}»"))
    for key, sub in section.sections.items():
        spec = schema.get(key)
        if isinstance(spec, dict):
            continue
        if row_spec is not None and ROW_SECTION.match(key):
            values[key] = _row({}, sub, ctx, f"{where}.{key}", problems, row_spec)
        elif spec is not None:
            problems.append(Problem(sub.line, f"«{key}» — параметр, а не секция"))
        else:
            problems.append(Problem(sub.line, f"неизвестная секция «{key}» в «{place}»"))
    for item in section.items:
        problems.append(Problem(item.line, f"кастомные элементы («{item.name}(...)») допустимы только в рядах cc"))
    return values


def _row(schema, section, ctx, where, problems, row_spec):
    row = Row()
    for key, spec in schema.items():
        entry = section.entries.get(key) if section else None
        row.named[key] = _resolve(spec, entry, ctx, f"{where}.{key}", problems)
        _note_unsupported(spec, entry, row.named[key], ctx, f"{where}.{key}", problems)
    if section is None:
        row.order = list(schema)
        return row
    placed = []
    for key, entry in section.entries.items():
        if key in schema or key in row_spec.names:
            placed.append((entry.line, key))
        if key in schema:
            continue
        if key in row_spec.names:
            spec = P(Bool(), "y")
            row.named[key] = _resolve(spec, entry, ctx, f"{where}.{key}", problems)
            _note_unsupported(spec, entry, row.named[key], ctx, f"{where}.{key}", problems)
        else:
            problems.append(Problem(entry.line, f"неизвестный элемент «{key}» в «{where}» "
                                                f"(есть {', '.join(row_spec.names)})"))
    for sub in section.sections.values():
        problems.append(Problem(sub.line, f"в ряду «{where}» не может быть секций"))
    for item in section.items:
        try:
            custom = parse_custom(item, ctx)
        except Invalid as e:
            problems.append(Problem(item.line, f"{where}: {e}"))
            continue
        row.custom.append(custom)
        placed.append((item.line, custom))
    placed.sort(key=lambda pair: pair[0])
    row.order = [item for _, item in placed] + [key for key in schema if key not in section.entries]
    return row


def _variables(section, base_dir, problems):
    variables = {}
    for name in VARIABLES:
        param = SCHEMA[name]
        entry = section.entries.get(name)
        ctx = Context(dict(variables))
        if name == "BASE_DIR" and (entry is None or entry.raw == ""):
            variables[name] = str(base_dir)
            continue
        value = _resolve(param, entry, ctx, name, problems)
        variables[name] = value if value is not None else str(base_dir)
    return variables


def evaluate(text, base_dir):
    root, problems = syntax.parse(text)
    variables = _variables(root, base_dir, problems)
    values = _walk(SCHEMA, root, Context(variables), "", problems)
    for name in VARIABLES:
        values[name] = Path(variables[name])
    return Settings(values), problems


def _render(schema, depth, lines):
    indent = "  " * depth
    for key, spec in schema.items():
        if isinstance(spec, Rows):
            continue
        if isinstance(spec, dict):
            if depth == 0:
                lines.append("")
            lines.append(f"{indent}{key} {{")
            _render(spec, depth + 1, lines)
            lines.append(f"{indent}}}")
            continue
        name = f'"{key}"' if spec.named else key
        value = spec.default if spec.show else ""
        lines.append(f"{indent}{name} = {value}".rstrip() if value else f"{indent}{name} =")


def default_text():
    lines = []
    top = {k: v for k, v in SCHEMA.items() if not isinstance(v, dict)}
    sections = {k: v for k, v in SCHEMA.items() if isinstance(v, dict)}
    lines.append("")
    _render(top, 0, lines)
    _render(sections, 0, lines)
    return HEADER + "\n".join(lines) + "\n"


_DEFAULTS = {}


def default_value(dotted, base_dir="/"):
    if base_dir not in _DEFAULTS:
        _DEFAULTS[base_dir] = evaluate("", base_dir)[0]
    return _DEFAULTS[base_dir].get(dotted)


def report(problems, path):
    for problem in problems:
        print(f"leech: {path}: {problem}", file=sys.stderr)


def load(path, base_dir):
    if path is None:
        settings, problems = evaluate("", base_dir)
        report(problems, "встроенные значения")
        return settings, problems
    path = Path(path)
    if not path.exists():
        try:
            path.write_text(default_text())
            print(f"leech: записан конфиг по умолчанию {path}", file=sys.stderr)
        except OSError as e:
            print(f"leech: не удалось записать {path}: {e}", file=sys.stderr)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        print(f"leech: не удалось прочитать {path}: {e}; используются значения по умолчанию", file=sys.stderr)
        text = ""
    settings, problems = evaluate(text, base_dir)
    report(problems, path.name)
    return settings, problems


def check(path, base_dir):
    if path is None:
        return []
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return [f"не удалось прочитать: {e}"]
    return evaluate(text, base_dir)[1]


def config_path(base_dir):
    override = os.environ.get("LEECH_CONFIG")
    if override is not None:
        return Path(os.path.expanduser(override)) if override else None
    return Path(base_dir) / "leech.conf"
