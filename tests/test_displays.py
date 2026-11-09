import unittest
from displays import bounds, contains, physical_selection, capture_region


class DisplayTests(unittest.TestCase):
    def test_extended_screen_to_left_and_above(self):
        monitor = dict(left=-2560, top=-400, width=2560, height=1440)
        region = capture_region(monitor, (200, 100, 1000, 500))
        self.assertEqual(region, dict(left=-2360, top=-300, width=1000, height=500))
        self.assertTrue(contains(monitor, region))
        self.assertFalse(contains(dict(left=0, top=0, width=1920, height=1080), region))

    def test_scaled_preview_uses_physical_pixels(self):
        # Selection display scale is independent of the target monitor's Windows scale.
        selection = physical_selection(3840, 2160, 1200, 675, (300, 150, 600, 300))
        self.assertEqual(selection, (960, 480, 1920, 960))
        monitor = dict(left=1920, top=0, width=3840, height=2160)
        self.assertEqual(capture_region(monitor, selection)['left'], 2880)

    def test_rounded_thumbnail_edges_stay_inside_monitor(self):
        box = physical_selection(2560, 1440, 1156, 650, (0, 0, 1156, 650))
        self.assertEqual(box, (0, 0, 2560, 1440))
        box = physical_selection(2560, 1440, 1156, 650, (1155, 649, 1, 1))
        self.assertEqual(box[0]+box[2], 2560)
        self.assertEqual(box[1]+box[3], 1440)

    def test_invalid_or_cross_monitor_crop_rejected(self):
        monitor = dict(left=-1920, top=0, width=1920, height=1080)
        for box in [(-1, 0, 100, 100), (1800, 0, 200, 100), (0, 0, 0, 10)]:
            with self.assertRaises(ValueError):
                capture_region(monitor, box)

    def test_same_resolution_monitors_remain_distinct(self):
        primary = dict(left=0, top=0, width=1920, height=1080)
        extended = dict(left=1920, top=0, width=1920, height=1080)
        crop = capture_region(extended, (10, 20, 500, 400))
        self.assertTrue(contains(extended, crop))
        self.assertFalse(contains(primary, crop))
        self.assertEqual(bounds(dict(**extended, extra='ignored')), extended)
