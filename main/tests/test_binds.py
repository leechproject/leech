import unittest

import gi

gi.require_version("Gdk", "3.0")
from gi.repository import Gdk

from modules.common import binds
from modules.config.values import Bind

M = Gdk.ModifierType


def key(keyval, state=0):
    event = Gdk.Event.new(Gdk.EventType.KEY_PRESS)
    event.keyval, event.state = keyval, state
    return event


class BindTest(unittest.TestCase):
    def test_shift_enter(self):
        bind = Bind(frozenset({"SHIFT"}), "ENTER")
        self.assertTrue(binds.matches(bind, key(Gdk.KEY_Return, M.SHIFT_MASK)))
        self.assertTrue(binds.matches(bind, key(Gdk.KEY_KP_Enter, M.SHIFT_MASK | M.MOD2_MASK)))
        self.assertFalse(binds.matches(bind, key(Gdk.KEY_Return)))
        self.assertFalse(binds.matches(bind, key(Gdk.KEY_Return, M.SHIFT_MASK | M.CONTROL_MASK)))

    def test_letter_with_shift(self):
        bind = Bind(frozenset({"SHIFT"}), "A")
        self.assertTrue(binds.matches(bind, key(Gdk.KEY_A, M.SHIFT_MASK)))

    def test_super(self):
        bind = Bind(frozenset({"SUPER"}), "D")
        self.assertTrue(binds.matches(bind, key(Gdk.KEY_d, M.MOD4_MASK)))
        self.assertFalse(binds.matches(bind, key(Gdk.KEY_d)))

    def test_none(self):
        self.assertFalse(binds.matches(None, key(Gdk.KEY_Return)))


class VimArrowTest(unittest.TestCase):
    def test_letters(self):
        for name, arrow in (("h", Gdk.KEY_Left), ("j", Gdk.KEY_Down), ("k", Gdk.KEY_Up), ("l", Gdk.KEY_Right)):
            self.assertEqual(binds.vim_arrow(Gdk.keyval_from_name(name), 0, True), arrow)

    def test_russian_layout(self):
        self.assertEqual(binds.vim_arrow(Gdk.keyval_from_name("Cyrillic_o"), 0, True), Gdk.KEY_Down)
        self.assertEqual(binds.vim_arrow(Gdk.keyval_from_name("Cyrillic_DE"), 0, True), Gdk.KEY_Right)

    def test_off_or_modified(self):
        self.assertIsNone(binds.vim_arrow(Gdk.KEY_j, 0, False))
        self.assertIsNone(binds.vim_arrow(Gdk.KEY_j, M.CONTROL_MASK, True))
        self.assertIsNone(binds.vim_arrow(Gdk.KEY_J, M.SHIFT_MASK, True))
        self.assertIsNone(binds.vim_arrow(Gdk.KEY_a, 0, True))


if __name__ == "__main__":
    unittest.main()
