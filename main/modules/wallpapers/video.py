import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from modules import config

HELPER = Path(__file__).resolve().parents[2] / "wallpaper_video.py"


def mpv_installed():
    return shutil.which("mpv") is not None


def extensions(mpv):
    return config.WALLPAPER_EXTENSIONS + (config.VIDEO_EXTENSIONS if mpv else ())


def is_video(path):
    return Path(path).suffix.lower() in config.VIDEO_EXTENSIONS


def covered(state):
    return state.windows > 0 or state.fullscreen


def still_path(path, cache_dir):
    stat = os.stat(path)
    raw = f"{path}|{stat.st_mtime_ns}|{stat.st_size}"
    return Path(cache_dir) / "stills" / (hashlib.sha1(raw.encode()).hexdigest() + ".png")


def still_command(path, outdir):
    return ["mpv", "--no-config", "--really-quiet", "--no-audio", "--frames=1", "--vo=image",
            "--vo-image-format=png", f"--vo-image-outdir={outdir}", "--", str(path)]


def still_frame(path):
    target = still_path(path, config.CACHE_DIR)
    if target.exists():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=target.parent) as outdir:
        subprocess.run(still_command(path, outdir), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=30, check=False)
        frames = sorted(Path(outdir).glob("*.png"))
        if not frames:
            raise OSError(f"mpv не вытащил кадр: {path}")
        os.replace(frames[0], target)
    return target


class VideoProcess:
    def __init__(self, path, paused, place=None):
        self.path = str(path)
        self._paused = paused
        self._hidden = False
        args = [sys.executable, str(HELPER), self.path, "paused" if paused else "play"]
        if place is not None:
            args.append(f"{place[0]},{place[1]}")
        self._proc = subprocess.Popen(
            args,
            stdin=subprocess.PIPE, text=True, start_new_session=True)

    def set_paused(self, paused):
        if paused != self._paused:
            self._paused = paused
            self._send("pause" if paused else "play")

    def set_hidden(self, hidden):
        if hidden != self._hidden:
            self._hidden = hidden
            self._send("hide" if hidden else "show")

    def stop(self):
        self._send("quit")
        try:
            self._proc.stdin.close()
        except OSError:
            pass
        threading.Thread(target=self._reap, daemon=True).start()

    def _reap(self):
        try:
            self._proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._proc.kill()
            self._proc.wait()

    def _send(self, line):
        if self._proc.poll() is not None:
            return
        try:
            self._proc.stdin.write(line + "\n")
            self._proc.stdin.flush()
        except OSError:
            pass
