import unittest
from pathlib import Path

from modules.config.schema import SCHEMA, P

DOCS = Path(__file__).resolve().parents[2] / "CONFIG.md"


def keys(schema, prefix=""):
    for key, spec in schema.items():
        if isinstance(spec, dict):
            yield from keys(spec, f"{prefix}{key}.")
        elif isinstance(spec, P):
            yield prefix + key


class ConfigDocsTest(unittest.TestCase):
    def test_every_parameter_described(self):
        text = DOCS.read_text(encoding="utf-8")
        missing = [key for key in keys(SCHEMA) if f"| `{key}` |" not in text]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
