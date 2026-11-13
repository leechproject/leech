import unittest

from modules.cc import keynav
from modules.cc import record_layout as rl
from modules.common import theme


class RecordLayoutTest(unittest.TestCase):
    W = 250

    def test_idle_closed(self):
        rects = rl.rects(self.W, False, False)
        self.assertEqual(list(rects), ["record", "tray"])
        self.assertEqual(rects["record"], (6, 6, 32, 32))
        # The toggle sits 5 px inside a 32 px tray plate that stands 6 px from the panel edge.
        self.assertEqual(rects["tray"], (self.W - 6 - 5 - 22, 11, 22, 22))
        self.assertEqual(rl.tray_rect(self.W, 0.0), (self.W - 6 - 32, 6, 32, 32))

    def test_recording_open(self):
        rects = rl.rects(self.W, True, True)
        self.assertEqual(list(rects), ["record", "pause", "microphone", "audio", "tray"])
        self.assertEqual(rects["pause"], (44, 6, 32, 32))
        tray = rl.tray_rect(self.W, 1.0)
        self.assertEqual(tray[0] + 5, rects["microphone"][0])
        self.assertEqual(rects["audio"][0] - rects["microphone"][0], 27)

    def test_hit(self):
        self.assertEqual(rl.hit(self.W, False, False, 10, 10), "record")
        self.assertIsNone(rl.hit(self.W, False, False, 60, 20))
        self.assertIsNone(rl.hit(self.W, False, False, 2, 20))

    def test_arrows_walk_the_row(self):
        rects = rl.rects(self.W, True, True)
        names = list(rects)
        boxes = list(rects.values())
        order = [names[0]]
        index = 0
        while True:
            index = keynav.step(boxes, index, "right")
            if index is None:
                break
            order.append(names[index])
        self.assertEqual(order, names)

    def test_selectors(self):
        # Idle: #090909 plates on a black panel; a tray switch that is on turns white.
        self.assertEqual(rl.panel_selector(False), "#cc-record")
        self.assertEqual(rl.selector("record", False, False, False), "#cc-record-button")
        self.assertEqual(rl.selector("audio", False, True, False), "#cc-record-item.on")
        # Recording: white panel, stop and pause on #d1d1d1, the tray does not invert.
        self.assertEqual(rl.panel_selector(True), "#cc-record.recording")
        self.assertEqual(rl.selector("pause", True, False, False), "#cc-record-button.recording")
        self.assertEqual(rl.selector("audio", True, True, False), "#cc-record-item.on")
        self.assertEqual(rl.selector("audio", True, False, False), "#cc-record-item")
        # Highlight: dark for elements that are off, grey for those that are on.
        self.assertEqual(rl.selector("record", True, False, True), "#cc-record-button.hover")
        self.assertEqual(rl.selector("microphone", False, True, True), "#cc-record-item.on.hover")
        self.assertEqual(theme.bg("#cc-record-button.hover")[:3], (0x1b / 255,) * 3)
        self.assertEqual(theme.bg("#cc-record-item.on.hover")[:3], (0xd1 / 255,) * 3)


if __name__ == "__main__":
    unittest.main()
