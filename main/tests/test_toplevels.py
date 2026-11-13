import struct
import unittest

from modules.parsing import toplevels as t


def event(obj, opcode, payload=b""):
    return t.encode_message(obj, opcode, payload)


def global_event(name, interface, version):
    return event(t.REGISTRY_ID, 0, struct.pack("=I", name) + t.encode_string(interface) + struct.pack("=I", version))


def states(*values):
    data = struct.pack(f"={len(values)}I", *values)
    return struct.pack("=I", len(data)) + data


def feed(table, data):
    messages, rest = t.split_messages(data)
    replies = b"".join(table.handle(*m) for m in messages)
    return replies, rest


class WireTest(unittest.TestCase):
    def test_string_padding(self):
        self.assertEqual(t.encode_string("abc"), struct.pack("=I", 4) + b"abc\0")
        self.assertEqual(t.encode_string("abcd"), struct.pack("=I", 5) + b"abcd\0\0\0\0")
        self.assertEqual(t.read_string(t.encode_string("abcd") + b"tail"), ("abcd", 12))

    def test_split_keeps_partial_message(self):
        data = event(5, 1, b"1234") + event(6, 2, b"5678")
        messages, rest = t.split_messages(data[:-3])
        self.assertEqual(messages, [(5, 1, b"1234")])
        self.assertEqual(rest, data[12:-3])


class TableTest(unittest.TestCase):
    def test_binds_manager(self):
        table = t.ToplevelTable()
        replies, _ = feed(table, global_event(1, "wl_compositor", 6) + global_event(9, t.MANAGER_INTERFACE, 3))
        self.assertTrue(table.supported)
        messages, _ = t.split_messages(replies)
        self.assertEqual(messages[0][:2], (t.REGISTRY_ID, 0))

    def test_unsupported_after_sync(self):
        table = t.ToplevelTable()
        feed(table, global_event(1, "wl_compositor", 6) + event(t.SYNC_ID, 0, struct.pack("=I", 0)))
        self.assertIs(table.supported, False)

    def test_fullscreen_after_done(self):
        table = t.ToplevelTable()
        handle = 0xFF000001
        feed(table, global_event(9, t.MANAGER_INTERFACE, 3) + event(t.MANAGER_ID, 0, struct.pack("=I", handle))
             + event(handle, t.HANDLE_APP_ID, t.encode_string("game")) + event(handle, t.HANDLE_TITLE, t.encode_string("Game"))
             + event(handle, t.HANDLE_STATE, states(2, t.STATE_FULLSCREEN)))
        self.assertEqual(table.fullscreen(), frozenset())
        feed(table, event(handle, t.HANDLE_DONE))
        self.assertEqual(table.fullscreen(), frozenset({("game", "Game")}))
        feed(table, event(handle, t.HANDLE_STATE, states(2)) + event(handle, t.HANDLE_DONE))
        self.assertEqual(table.fullscreen(), frozenset())

    def test_closed_destroys_handle(self):
        table = t.ToplevelTable()
        handle = 0xFF000002
        feed(table, event(t.MANAGER_ID, 0, struct.pack("=I", handle)) + event(handle, t.HANDLE_STATE, states(3))
             + event(handle, t.HANDLE_DONE))
        replies, _ = feed(table, event(handle, t.HANDLE_CLOSED))
        self.assertEqual(replies, t.encode_message(handle, t.HANDLE_DESTROY))
        self.assertEqual(table.fullscreen(), frozenset())


if __name__ == "__main__":
    unittest.main()
