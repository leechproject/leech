import os
import tempfile
import unittest
from pathlib import Path

from modules.rules.base import State
from modules.wallpapers import video


def _state(windows=0, fullscreen=False):
    return State(active=1, occupied=set(), windows=windows, fullscreen=fullscreen, clients=())


class VideoTest(unittest.TestCase):
    def test_kinds(self):
        self.assertTrue(video.is_video("/a/b.MP4"))
        self.assertTrue(video.is_video("x.gif"))
        self.assertFalse(video.is_video("x.png"))

    def test_extensions_follow_mpv(self):
        self.assertIn(".webm", video.extensions(True))
        self.assertNotIn(".webm", video.extensions(False))
        self.assertIn(".png", video.extensions(False))

    def test_covered(self):
        self.assertFalse(video.covered(_state()))
        self.assertTrue(video.covered(_state(windows=1)))
        self.assertTrue(video.covered(_state(fullscreen=True)))

    def test_still_path_changes_with_file(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "a.mp4"
            f.write_bytes(b"1")
            first = video.still_path(f, d)
            os.utime(f, ns=(1, 1))
            self.assertNotEqual(first, video.still_path(f, d))
            self.assertEqual(first.parent, Path(d) / "stills")

    def test_still_command_takes_one_frame(self):
        cmd = video.still_command("/v/-x.mp4", "/out")
        self.assertIn("--frames=1", cmd)
        self.assertEqual(cmd[-2:], ["--", "/v/-x.mp4"])


if __name__ == "__main__":
    unittest.main()
