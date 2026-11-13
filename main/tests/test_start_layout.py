import unittest

from modules.launcher import start_layout as sl


class StartLayoutTest(unittest.TestCase):
    def test_body(self):
        self.assertEqual(sl.body_height(720), 400)
        self.assertEqual(sl.body_left(1280, 520, False, 9), 380)
        self.assertEqual(sl.body_left(1280, 520, True, 9), 19)

    def test_footer_and_buttons(self):
        plate = sl.footer(100, 620, 500)
        self.assertEqual(plate, (107, 445, 506, 48))
        self.assertEqual(sl.avatar(plate), (114, 452, 34, 34))
        self.assertEqual(sl.power(plate), (572, 452, 34, 34))
        self.assertEqual(sl.settings(plate), (531, 452, 34, 34))

    def test_username_beside_the_avatar(self):
        plate = sl.footer(0, 520, 600)
        ax, ay, aw, ah = sl.avatar(plate)
        x, y, w, h = sl.username(plate)
        self.assertEqual((x, y, h), (ax + aw + 7, ay, ah))
        self.assertEqual(x + w + 7, sl.settings(plate)[0])

    def test_menu_above_the_power_button(self):
        power = sl.power(sl.footer(100, 620, 500))
        box = sl.menu(power)
        self.assertEqual(box[0] + box[2], power[0] + power[2])
        self.assertEqual(box[1] + box[3], power[1] - 7)
        self.assertEqual(sl.menu_item(box, 0)[1], box[1] + 6)

    def test_hit(self):
        self.assertEqual(sl.hit(100, 620, 500, 580, 460, False), ("power",))
        self.assertEqual(sl.hit(100, 620, 500, 120, 460, False), ("avatar",))
        self.assertEqual(sl.hit(100, 620, 500, 300, 460, False), ("footer",))
        self.assertIsNone(sl.hit(100, 620, 500, 300, 200, False))
        box = sl.menu(sl.power(sl.footer(100, 620, 500)))
        item = sl.menu_item(box, 2)
        self.assertEqual(sl.hit(100, 620, 500, item[0] + 1, item[1] + 1, True), ("power-menu", 2))


if __name__ == "__main__":
    unittest.main()
