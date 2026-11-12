import socket
import threading
import time

from gi.repository import GLib

from modules import config
from modules.common import debug


class IpcServer:
    def __init__(self, handler):
        self._handler = handler

    def start(self):
        try:
            config.IPC_SOCKET.unlink()
        except FileNotFoundError:
            pass
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(config.IPC_SOCKET))
        server.listen(4)
        threading.Thread(target=self._serve, args=(server,), daemon=True).start()

    def _serve(self, server):
        while True:
            conn, _ = server.accept()
            with conn:
                self._talk(conn)

    def _talk(self, conn):
        conn.settimeout(2)
        try:
            command = conn.recv(512).decode("utf-8", "replace").strip()
        except OSError:
            return
        if not command:
            return

        result = {}
        done = threading.Event()

        received = time.monotonic()

        def run():
            started = time.monotonic()
            try:
                result["reply"] = self._handler(command)
            except Exception as e:
                result["reply"] = f"error: {e}"
            done.set()
            debug.log("ipc", f"{command!r}: ожидание {(started - received) * 1000:.0f} мс, "
                             f"выполнение {(time.monotonic() - started) * 1000:.0f} мс")
            return False

        GLib.idle_add(run)
        done.wait(2)
        try:
            conn.sendall(((result.get("reply") or "ok") + "\n").encode("utf-8"))
        except OSError:
            pass
