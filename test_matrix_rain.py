"""Tests for pure helpers in matrix_rain. Run: py -3 -m unittest test_matrix_rain"""
import unittest

from matrix_rain import clock_hue_angle, HUE_CYCLE_DEG_PER_SEC


class ClockHueAngleTests(unittest.TestCase):
    def test_zero_at_epoch(self):
        self.assertEqual(clock_hue_angle(0.0), 0.0)

    def test_scales_with_time(self):
        self.assertAlmostEqual(clock_hue_angle(1.0), HUE_CYCLE_DEG_PER_SEC % 360)

    def test_wraps_at_360(self):
        period = 360.0 / HUE_CYCLE_DEG_PER_SEC
        self.assertAlmostEqual(clock_hue_angle(period), 0.0, places=6)
        self.assertAlmostEqual(clock_hue_angle(period * 3 + 1.0), HUE_CYCLE_DEG_PER_SEC % 360, places=6)

    def test_same_time_same_angle(self):
        # Two PCs with synced clocks must agree regardless of launch time
        self.assertEqual(clock_hue_angle(1_700_000_000.5), clock_hue_angle(1_700_000_000.5))

    def test_range(self):
        for t in (0.0, 12.3, 1_700_000_000.0, 9_999_999_999.9):
            a = clock_hue_angle(t)
            self.assertGreaterEqual(a, 0.0)
            self.assertLess(a, 360.0)

    def test_default_uses_wall_clock(self):
        import time
        before = clock_hue_angle(time.time())
        now = clock_hue_angle()
        after = clock_hue_angle(time.time())
        # Monotonic unless a wrap happened inside this tiny window
        if before <= after:
            self.assertTrue(before <= now <= after)


if __name__ == "__main__":
    unittest.main()
