import os
import socket
import struct
import threading

from modules.common import debug

MANAGER_INTERFACE = "zwlr_foreign_toplevel_manager_v1"
MANAGER_VERSION = 3
STATE_FULLSCREEN = 3

DISPLAY_ID = 1
REGISTRY_ID = 2
SYNC_ID = 3
MANAGER_ID = 4

HANDLE_TITLE = 0
HANDLE_APP_ID = 1
HANDLE_STATE = 4
HANDLE_DONE = 5
HANDLE_CLOSED = 6
HANDLE_DESTROY = 7


def _padded(length):
    return (length + 3) & ~3


def encode_string(text):
    data = text.encode() + b"\0"
    return struct.pack("=I", len(data)) + data.ljust(_padded(len(data)), b"\0")


def encode_message(obj, opcode, payload=b""):
    return struct.pack("=II", obj, (8 + len(payload)) << 16 | opcode) + payload


def split_messages(buffer):
    messages = []
    offset = 0
    while len(buffer) - offset >= 8:
        obj, word = struct.unpack_from("=II", buffer, offset)
        size = word >> 16
        if size < 8 or len(buffer) - offset < size:
            break
        messages.append((obj, word & 0xFFFF, bytes(buffer[offset + 8:offset + size])))
        offset += size
    return messages, bytes(buffer[offset:])


def read_uint(payload, offset=0):
    return struct.unpack_from("=I", payload, offset)[0], offset + 4


def read_bytes(payload, offset=0):
    length, offset = read_uint(payload, offset)
    return payload[offset:offset + length], offset + _padded(length)


def read_string(payload, offset=0):
    data, offset = read_bytes(payload, offset)
    return data.rstrip(b"\0").decode("utf-8", "replace"), offset


def read_states(payload):
    data, _ = read_bytes(payload)
    return frozenset(struct.unpack(f"={len(data) // 4}I", data[:len(data) // 4 * 4]))


class ToplevelTable:
    def __init__(self):
        self.supported = None
        self._pending = {}
        self._committed = {}

    def start_requests(self):
        return (encode_message(DISPLAY_ID, 1, struct.pack("=I", REGISTRY_ID))
                + encode_message(DISPLAY_ID, 0, struct.pack("=I", SYNC_ID)))

    def fullscreen(self):
        return frozenset((app_id, title) for app_id, title, states in self._committed.values()
                         if STATE_FULLSCREEN in states)

    def handle(self, obj, opcode, payload):
        if obj == DISPLAY_ID and opcode == 0:
            raise ConnectionError(f"wayland error: {read_string(payload, 8)[0]}")
        if obj == REGISTRY_ID and opcode == 0:
            return self._on_global(payload)
        if obj == SYNC_ID and opcode == 0 and self.supported is None:
            self.supported = False
            return b""
        if obj == MANAGER_ID and opcode == 0:
            handle_id, _ = read_uint(payload)
            self._pending[handle_id] = ["", "", frozenset()]
            return b""
        if obj in self._pending:
            return self._on_handle(obj, opcode, payload)
        return b""

    def _on_global(self, payload):
        name, offset = read_uint(payload)
        interface, offset = read_string(payload, offset)
        version, _ = read_uint(payload, offset)
        if interface != MANAGER_INTERFACE or self.supported:
            return b""
        self.supported = True
        body = (struct.pack("=I", name) + encode_string(interface)
                + struct.pack("=II", min(version, MANAGER_VERSION), MANAGER_ID))
        return encode_message(REGISTRY_ID, 0, body)

    def _on_handle(self, obj, opcode, payload):
        entry = self._pending[obj]
        if opcode == HANDLE_APP_ID:
            entry[0] = read_string(payload)[0]
        elif opcode == HANDLE_TITLE:
            entry[1] = read_string(payload)[0]
        elif opcode == HANDLE_STATE:
            entry[2] = read_states(payload)
        elif opcode == HANDLE_DONE:
            self._committed[obj] = tuple(entry)
        elif opcode == HANDLE_CLOSED:
            del self._pending[obj]
            self._committed.pop(obj, None)
            return encode_message(obj, HANDLE_DESTROY)
        return b""


def _display_path():
    name = os.environ.get("WAYLAND_DISPLAY", "wayland-0")
    if os.path.isabs(name):
        return name
    return os.path.join(os.environ.get("XDG_RUNTIME_DIR", ""), name)


class FullscreenWatcher:
    def __init__(self, on_change):
        self._on_change = on_change
        self.fullscreen = frozenset()
        self.supported = None

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        table = ToplevelTable()
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.connect(_display_path())
                s.sendall(table.start_requests())
                rest = b""
                while chunk := s.recv(65536):
                    messages, rest = split_messages(rest + chunk)
                    replies = b"".join(table.handle(*message) for message in messages)
                    if replies:
                        s.sendall(replies)
                    if table.supported is False:
                        debug.log("toplevels", f"{MANAGER_INTERFACE} не поддерживается, fullscreen не определяется")
                        self.supported = False
                        return
                    self.supported = table.supported
                    current = table.fullscreen()
                    if current != self.fullscreen:
                        self.fullscreen = current
                        self._on_change()
        except (OSError, ConnectionError, struct.error) as e:
            debug.log("toplevels", f"соединение с wayland: {e!r}")
        self.supported = False
