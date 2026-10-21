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


class StartupCommandTests(unittest.TestCase):
    def test_frozen_runs_exe_only(self):
        from matrix_rain import startup_command
        self.assertEqual(startup_command(frozen=True, executable=r"C:\App\Matrix Rain.exe", base_dir=r"C:\App"),
                         r'"C:\App\Matrix Rain.exe"')

    def test_script_uses_pythonw_and_launcher(self):
        from matrix_rain import startup_command
        cmd = startup_command(frozen=False, executable=r"C:\Py\python.exe", base_dir=r"E:\Proj\MatrixRain")
        self.assertEqual(cmd, r'"C:\Py\pythonw.exe" "E:\Proj\MatrixRain\run_matrix_rain.pyw"')

    def test_pythonw_kept_as_is(self):
        from matrix_rain import startup_command
        cmd = startup_command(frozen=False, executable=r"C:\Py\pythonw.exe", base_dir=r"E:\P")
        self.assertTrue(cmd.startswith(r'"C:\Py\pythonw.exe"'))


class ColumnStartTests(unittest.TestCase):
    def test_initial_columns_are_spread_across_screen(self):
        # Steady-state placement: most columns already have glyphs on screen at frame 0,
        # otherwise a black-background screensaver shows a blank screen for 10-30 s.
        from matrix_rain import MatrixColumn
        H, ch = 1440, 17
        cols = [MatrixColumn(i * 12, H, 2.0, 5.0, 10, 30, ch) for i in range(400)]
        visible = sum(1 for c in cols if c.y <= H and c.y + (c.length - 1) * ch >= -ch)
        self.assertGreater(visible / len(cols), 0.9)
        self.assertTrue(all(c.y >= -c.length * ch for c in cols))  # never above the travel range

    def test_motion_scales_with_elapsed_steps(self):
        # Movement is time-based: one update of 2 steps equals two updates of 1 step (frame-rate independent).
        import random
        from matrix_rain import MatrixColumn
        random.seed(5)
        one = MatrixColumn(0, 4000, 3.0, 3.0, 10, 30, 19)
        random.seed(5)
        two = MatrixColumn(0, 4000, 3.0, 3.0, 10, 30, 19)
        y0, h0 = one.y, one.head_offset
        one.update(4000, 2.0)
        two.update(4000, 1.0)
        two.update(4000, 1.0)
        self.assertAlmostEqual(one.y - y0, two.y - y0)
        self.assertAlmostEqual(one.head_offset - h0, two.head_offset - h0)

    def test_reset_still_restarts_above_screen(self):
        from matrix_rain import MatrixColumn
        H, ch = 1440, 17
        col = MatrixColumn(0, H, 2.0, 5.0, 10, 30, ch)
        col.y = H  # force bottom past the edge
        col.update(H)
        self.assertLessEqual(col.y, -ch)  # restarted above the top edge


@unittest.skipUnless(__import__("sys").platform == "win32", "Windows hooks")
class HookTests(unittest.TestCase):
    def test_hooks_install_and_uninstall(self):
        import matrix_rain

        class Dummy:
            def _dismiss_screensaver(self):
                pass

        matrix_rain._install_screensaver_keyboard_hook(Dummy())
        matrix_rain._install_screensaver_mouse_hook(Dummy())
        self.assertTrue(matrix_rain._kb_hook_id, "keyboard hook failed to install")
        self.assertTrue(matrix_rain._mouse_hook_id, "mouse hook failed to install")
        matrix_rain._uninstall_screensaver_keyboard_hook()
        matrix_rain._uninstall_screensaver_mouse_hook()
        self.assertIsNone(matrix_rain._kb_hook_id)
        self.assertIsNone(matrix_rain._mouse_hook_id)


class ScreensaverStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt5.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _widget(self):
        import matrix_rain
        w = matrix_rain.MatrixRainWidget()
        self.addCleanup(w.deleteLater)
        return w

    def test_external_hide_while_active_clears_state(self):
        # Windows minimizes a fullscreen window when another app takes focus -> hideEvent.
        # State must be cleared, otherwise overlay is left "active" but frozen.
        w = self._widget()
        w.show()
        w._screensaver_active = True
        w._screensaver_dismiss_timer.start()
        w.hide()
        self.assertFalse(w._screensaver_active)
        self.assertFalse(w._screensaver_dismiss_timer.isActive())

    def test_mouse_move_at_same_position_does_not_dismiss(self):
        # Windows posts WM_MOUSEMOVE when a window appears under the cursor; it must not dismiss.
        from PyQt5.QtCore import Qt, QPoint, QEvent
        from PyQt5.QtGui import QMouseEvent
        w = self._widget()
        w._screensaver_active = True
        w._screensaver_cursor_start = QPoint(100, 100)
        ev = QMouseEvent(QEvent.MouseMove, QPoint(10, 10), QPoint(100, 100), Qt.NoButton, Qt.NoButton, Qt.NoModifier)
        w.mouseMoveEvent(ev)
        self.assertTrue(w._screensaver_active)
        ev2 = QMouseEvent(QEvent.MouseMove, QPoint(10, 10), QPoint(140, 100), Qt.NoButton, Qt.NoButton, Qt.NoModifier)
        w.mouseMoveEvent(ev2)
        self.assertFalse(w._screensaver_active)

    def test_black_background_uses_solid_window(self):
        # Black-background screensaver draws in an opaque window (cheaper than the per-pixel-alpha overlay).
        import matrix_rain
        w = self._widget()
        w.config["screensaver"] = {"enabled": True, "idle_seconds": 5, "black_background": True}
        orig_idle = matrix_rain.get_idle_time_ms
        matrix_rain.get_idle_time_ms = lambda: 60000
        try:
            w._check_screensaver_idle()
        finally:
            matrix_rain.get_idle_time_ms = orig_idle
        self.assertTrue(w._screensaver_active)
        self.assertTrue(w._solid_saver.isVisible())
        self.assertFalse(w.isVisible())
        self.assertTrue(w.timer.isActive())
        w._solid_saver.hide()  # e.g. Windows minimised it
        self.assertFalse(w._screensaver_active)
        self.assertFalse(w.timer.isActive())

    def test_fallback_to_cpu_window_keeps_screensaver_up(self):
        # If the GPU window fails to initialise, its replacement takes over without ending the screensaver.
        import matrix_rain
        w = self._widget()
        w.config["screensaver"] = {"enabled": True, "idle_seconds": 5, "black_background": True}
        orig_idle = matrix_rain.get_idle_time_ms
        matrix_rain.get_idle_time_ms = lambda: 60000
        try:
            w._check_screensaver_idle()
            old = w._solid_saver
            w._use_cpu_screensaver()
        finally:
            matrix_rain.get_idle_time_ms = orig_idle
        self.assertIsNot(w._solid_saver, old)
        self.assertIsInstance(w._solid_saver, matrix_rain.SolidScreensaverWindow)
        self.assertTrue(w._solid_saver.isVisible())
        self.assertFalse(old.isVisible())
        self.assertTrue(w._screensaver_active)
        w._dismiss_screensaver()


@unittest.skipUnless(__import__("sys").platform == "win32", "Windows hooks")
class HookCallbackTests(unittest.TestCase):
    def test_hook_callbacks_schedule_dismiss(self):
        # Drive the hook procedures directly (as Windows would) and check they reach _dismiss_screensaver.
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        import matrix_rain

        class Stub:
            calls = 0
            def _dismiss_screensaver(self):
                Stub.calls += 1

        stub = Stub()
        matrix_rain._install_screensaver_keyboard_hook(stub)
        matrix_rain._install_screensaver_mouse_hook(stub)
        try:
            self.assertTrue(matrix_rain._kb_hook_id and matrix_rain._mouse_hook_id)
            matrix_rain._kb_hook_proc(0, 0x100, 0)      # WM_KEYDOWN
            matrix_rain._mouse_hook_proc(0, 0x200, 0)   # WM_MOUSEMOVE
            app.processEvents()
            self.assertEqual(Stub.calls, 2)
        finally:
            matrix_rain._uninstall_screensaver_keyboard_hook()
            matrix_rain._uninstall_screensaver_mouse_hook()


class ResizeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt5.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_columns_follow_widget_width(self):
        # Screen size changes (Parsec virtual display, dock/undock) must not leave part of the screen without rain.
        import matrix_rain
        w = matrix_rain.MatrixRainWidget()
        self.addCleanup(w.deleteLater)
        w.show()  # resize events are only delivered to visible widgets
        w.resize(1000, 500)
        self.app.processEvents()
        n_small = len(w.columns)
        w.resize(3000, 500)
        self.app.processEvents()
        n_big = len(w.columns)
        self.assertGreater(n_big, n_small * 2)
        self.assertTrue(all(c.x < 3000 for c in w.columns))


class GlyphAtlasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt5.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _atlas(self):
        from PyQt5.QtGui import QFont
        import matrix_rain
        return matrix_rain.GlyphAtlas(QFont("Consolas", 14, QFont.Bold))

    def test_hue_shift_keeps_white_and_rotates_green(self):
        from matrix_rain import hue_shift_rgb
        self.assertEqual(hue_shift_rgb((255, 255, 255), 200), (255, 255, 255))
        self.assertEqual(hue_shift_rgb((0, 255, 70), 360), hue_shift_rgb((0, 255, 70), 0))
        r, g, b = hue_shift_rgb((0, 255, 70), 120)  # green -> blue side
        self.assertGreater(b, g)

    def test_tiers_are_tinted_with_hue(self):
        # Tier sprites must carry the tier colour (hue-shifted), not the white mask colour.
        # The mask is painted by hand: the offscreen test platform has no fonts to rasterise.
        from PyQt5.QtGui import QPainter, QColor
        from matrix_rain import hue_shift_rgb
        atlas = self._atlas()
        sx, sy = atlas.slots["M"][:2]
        p = QPainter(atlas.core)
        p.fillRect(sx + 8, sy + 8, 4, 4, QColor(255, 255, 255))
        p.end()
        for hue in (0, 200):
            atlas.prepare(90, 2, hue)
            c = atlas.images["near"].pixelColor(sx + 9, sy + 9)
            self.assertEqual((c.red(), c.green(), c.blue(), c.alpha()), hue_shift_rgb((0, 220, 60), hue) + (255,))
            glow = atlas.images["head_glow"].pixelColor(sx + 7, sy + 9)  # 1 px left of the mask: glow ring
            self.assertGreater(glow.alpha(), 0)

    def test_message_chars_get_slots(self):
        atlas = self._atlas()
        self.assertNotIn(" ", atlas.slots)
        atlas.add_chars("ola mundo")
        self.assertIn(" ", atlas.slots)
        self.assertIn("M", atlas.slots)  # existing glyphs survive the rebuild
