import importlib
import sys
from pathlib import Path

from modules.rules.base import NullRules


def available():
    return sorted(p.stem for p in Path(__file__).parent.glob("*.py") if p.stem not in ("__init__", "base", "view"))


def load(name):
    if name in available():
        try:
            return importlib.import_module(f"modules.rules.{name}").create()
        except Exception as e:
            print(f"leech: правила «{name}» не загрузились: {e!r}", file=sys.stderr)
    else:
        print(f"leech: нет правил WM «{name}», доступны: {', '.join(available()) or 'ничего'}", file=sys.stderr)
    return NullRules()
