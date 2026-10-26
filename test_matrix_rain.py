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


class WrapWordsTests(unittest.TestCase):
    def test_wraps_at_word_boundaries(self):
        from matrix_rain import wrap_words
        self.assertEqual(wrap_words("I am calm, focused, and in control", 14),
                         ["I am calm,", "focused, and", "in control"])

    def test_short_text_stays_on_one_line(self):
        from matrix_rain import wrap_words
        self.assertEqual(wrap_words("  I am   enough ", 40), ["I am enough"])

    def test_long_word_gets_own_line(self):
        from matrix_rain import wrap_words
        self.assertEqual(wrap_words("go supercalifragilistic now", 8), ["go", "supercalifragilistic", "now"])


class AffirmationConfigTests(unittest.TestCase):
    def test_missing_block_gets_defaults(self):
        from matrix_rain import normalize_affirmations, DEFAULT_AFFIRMATIONS
        cfg = normalize_affirmations(None)
        self.assertTrue(cfg["enabled"])
        self.assertEqual(cfg["styles"], ["decode", "catch", "type"])
        self.assertTrue(cfg["rotate"])
        self.assertEqual(cfg["interval_seconds"], 5)
        self.assertEqual(cfg["hold_seconds"], 7)
        self.assertEqual(cfg["backing"], "dim")
        self.assertEqual(cfg["messages"], DEFAULT_AFFIRMATIONS)
        self.assertIsNot(cfg["messages"], DEFAULT_AFFIRMATIONS)  # editing one config must not edit the defaults

    def test_bad_values_are_fixed(self):
        from matrix_rain import normalize_affirmations
        cfg = normalize_affirmations({"styles": ["sparkle"], "interval_seconds": "x", "hold_seconds": 999,
                                      "backing": "fog", "messages": ["  I am here ", "", 3]})
        self.assertEqual(cfg["styles"], ["decode"])
        self.assertEqual(cfg["interval_seconds"], 5)
        self.assertEqual(cfg["hold_seconds"], 60)
        self.assertEqual(cfg["backing"], "dim")
        self.assertEqual(cfg["messages"], ["I am here", "3"])

    def test_load_config_adds_block_to_old_file(self):
        import json, os, tempfile
        import matrix_rain
        path = os.path.join(tempfile.mkdtemp(), "matrix_config.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"custom_messages": ["hi"]}, f)
        orig = matrix_rain.CONFIG_PATH
        matrix_rain.CONFIG_PATH = path
        try:
            cfg = matrix_rain.load_config()
        finally:
            matrix_rain.CONFIG_PATH = orig
        self.assertTrue(cfg["affirmations"]["enabled"])
        self.assertEqual(cfg["custom_messages"], ["hi"])


class AffirmationPlayerTests(unittest.TestCase):
    W, H, CW, CH = 1920, 1080, 20, 24

    def _cfg(self, **kw):
        from matrix_rain import normalize_affirmations
        return normalize_affirmations(dict({"messages": ["I am enough", "I am allowed to rest"],
                                            "clock_sync": False}, **kw))

    def _player(self):
        import random
        from matrix_rain import AffirmationPlayer
        return AffirmationPlayer(random.Random(7))

    def _step(self, player, cfg, seconds, dt=0.05):
        started = []
        for _ in range(int(round(seconds / dt))):
            a = player.update(dt, cfg, self.W, self.H, self.CW, self.CH)
            if a is not None:
                started.append(a)
        return started

    def test_first_one_starts_after_delay(self):
        p, cfg = self._player(), self._cfg()
        self.assertEqual(self._step(p, cfg, 1.9), [])
        self.assertEqual(len(self._step(p, cfg, 0.2)), 1)

    def test_styles_rotate_and_messages_do_not_repeat(self):
        p, cfg = self._player(), self._cfg()
        shown = self._step(p, cfg, 120)
        self.assertGreater(len(shown), 6)
        self.assertEqual([a.style for a in shown[:4]], ["decode", "catch", "type", "decode"])
        for prev, cur in zip(shown, shown[1:]):
            self.assertNotEqual(prev.text, cur.text)

    def test_gap_after_one_leaves(self):
        p, cfg = self._player(), self._cfg(interval_seconds=6)
        a = self._step(p, cfg, 2.1)[0]
        remaining = a.end - a.t
        self.assertEqual(self._step(p, cfg, remaining + 5.8), [])
        self.assertEqual(len(self._step(p, cfg, 0.4)), 1)

    def test_fixed_style_without_rotate(self):
        p, cfg = self._player(), self._cfg(rotate=False, styles=["type", "decode"])
        self.assertEqual({a.style for a in self._step(p, cfg, 60)}, {"type"})

    def test_disabled_shows_nothing(self):
        p = self._player()
        self.assertEqual(self._step(p, self._cfg(enabled=False), 30), [])
        self.assertIsNone(p.current)

    def test_text_is_centred_and_wrapped_on_screen(self):
        import random
        from matrix_rain import Affirmation
        a = Affirmation("I am becoming the best version of myself " * 3, "decode", 5,
                        800, 600, 20, 24, random.Random(1))
        self.assertGreater(len(a.lines), 1)
        xs = [c[1] for c in a.cells]
        self.assertGreaterEqual(min(xs), 0)
        self.assertLessEqual(max(xs) + 20, 800)
        x0, y0, x1, y1 = a.band
        self.assertAlmostEqual((x0 + x1) / 2, 400, delta=20)
        self.assertAlmostEqual((y0 + y1) / 2, 300, delta=24)

    def test_decode_letters_resolve_by_end_of_entrance(self):
        import random
        from matrix_rain import Affirmation
        rng = random.Random(3)
        a = Affirmation("I am enough", "decode", 5, 1920, 1080, 20, 24, rng)
        a.t = 0.1
        self.assertTrue(all(op[0] == "scramble" for op in a.ops(rng)))
        a.t = a.in_dur
        letters = [op[1] for op in a.ops(rng) if op[0] == "letter"]
        self.assertEqual("".join(letters), "Iamenough")

    def test_terminal_backspaces_then_ends(self):
        import random
        from matrix_rain import Affirmation
        rng = random.Random(3)
        a = Affirmation("I am enough", "type", 5, 1920, 1080, 20, 24, rng)
        a.t = a.in_dur + a.hold + 0.3
        partial = [op for op in a.ops(rng) if op[0] == "letter"]
        self.assertTrue(0 < len(partial) < 9)
        a.t = a.in_dur + a.hold + a.TYPE_OUT + 0.01
        self.assertEqual([op for op in a.ops(rng) if op[0] == "letter"], [])
        self.assertAlmostEqual(a.presence(), 1 - (a.TYPE_OUT + 0.01) / a.out_dur)

    def test_presence_fades_in_holds_and_out(self):
        import random
        from matrix_rain import Affirmation
        a = Affirmation("I am enough", "catch", 5, 1920, 1080, 20, 24, random.Random(2))
        a.t = 0.3
        self.assertAlmostEqual(a.presence(), 0.5)
        a.t = a.in_dur + 1
        self.assertEqual((a.phase(), a.presence()), ("hold", 1.0))
        a.t = a.end
        self.assertEqual(a.phase(), "out")
        self.assertAlmostEqual(a.presence(), 0.0)


class ClockSyncTests(unittest.TestCase):
    MSGS = ["I am enough", "I am allowed to rest", "I am brave enough to begin", "Your work matters",
            "I am free to be myself"]

    def _cfg(self, **kw):
        from matrix_rain import normalize_affirmations
        return normalize_affirmations(dict({"messages": self.MSGS, "clock_sync": True}, **kw))

    def test_each_round_shows_every_message_once(self):
        from matrix_rain import clock_affirmation
        n = len(self.MSGS)
        for deck in (0, 1, 7, 123456):
            got = [clock_affirmation(deck * n + i, self.MSGS, ["decode"], True)[0] for i in range(n)]
            self.assertEqual(sorted(got), sorted(self.MSGS))

    def test_never_the_same_message_twice_in_a_row(self):
        from matrix_rain import clock_affirmation
        prev = None
        for slot in range(110_000_000, 110_005_000):
            msg = clock_affirmation(slot, self.MSGS, ["decode"], True)[0]
            self.assertNotEqual(msg, prev)
            prev = msg

    def test_styles_follow_the_slot(self):
        from matrix_rain import clock_affirmation
        styles = ["decode", "catch", "type"]
        self.assertEqual([clock_affirmation(s, self.MSGS, styles, True)[1] for s in range(300, 304)],
                         ["decode", "catch", "type", "decode"])
        self.assertEqual(clock_affirmation(301, self.MSGS, styles, False)[1], "decode")

    def test_two_pcs_started_apart_show_the_same_thing(self):
        # PC A has been running; PC B starts its rain mid-entrance. Same clock -> same message, style and moment.
        import random
        from matrix_rain import AffirmationPlayer, affirmation_slot_seconds
        cfg = self._cfg()
        slot_len = affirmation_slot_seconds(cfg)
        start = 1_800_000_000 // slot_len * slot_len + slot_len
        a, b = AffirmationPlayer(random.Random(1)), AffirmationPlayer(random.Random(2))
        a.update(0.03, cfg, 1920, 1080, 20, 24, now=start - 3)  # A was already running
        self.assertIsNone(a.current)
        got_a = a.update(0.03, cfg, 1920, 1080, 20, 24, now=start + 0.01)
        got_b = b.update(0.03, cfg, 2560, 1440, 26, 30, now=start + 0.4)
        self.assertEqual((got_a.text, got_a.style), (got_b.text, got_b.style))
        self.assertAlmostEqual(got_b.t, 0.4, places=5)
        a.update(0.03, cfg, 1920, 1080, 20, 24, now=start + 0.4)
        self.assertAlmostEqual(a.current.t, 0.4, places=5)
        # Same letter timings too: they are seeded by the slot, not by each PC's own random state
        self.assertEqual([c[4] for c in got_a.cells], [c[4] for c in got_b.cells])

    def test_joining_after_the_entrance_waits_for_the_next_slot(self):
        from matrix_rain import AffirmationPlayer, affirmation_slot_seconds
        cfg = self._cfg()
        slot_len = affirmation_slot_seconds(cfg)
        start = 1_800_000_000 // slot_len * slot_len
        p = AffirmationPlayer()
        self.assertIsNone(p.update(0.03, cfg, 1920, 1080, 20, 24, now=start + 5))
        self.assertIsNone(p.update(0.03, cfg, 1920, 1080, 20, 24, now=start + 5.1))
        self.assertIsNotNone(p.update(0.03, cfg, 1920, 1080, 20, 24, now=start + slot_len + 0.05))

    def test_each_affirmation_ends_before_its_slot_does(self):
        import random
        from matrix_rain import Affirmation, affirmation_slot_seconds, AFFIRMATION_IN_MAX
        cfg = self._cfg()
        long_text = "meu nome e soh coisas boas acontecem comigo todos os dias de manha a noite " * 2
        for style in ("decode", "catch", "type", "bloom"):
            a = Affirmation(long_text, style, cfg["hold_seconds"], 1920, 1080, 20, 24, random.Random(9))
            self.assertLessEqual(a.in_dur, AFFIRMATION_IN_MAX)
            self.assertLessEqual(a.end + cfg["interval_seconds"], affirmation_slot_seconds(cfg) + 1e-9)


class AffirmationFeedTests(unittest.TestCase):
    def test_parse_skips_blanks_and_comments(self):
        from matrix_rain import parse_affirmation_list
        self.assertEqual(parse_affirmation_list("# list\r\n\r\n I am enough \r\n#x\r\nYour work matters"),
                         ["I am enough", "Your work matters"])

    def test_fetch_updates_list_and_cache(self):
        import os, tempfile, time, pathlib
        from matrix_rain import AffirmationFeed
        d = tempfile.mkdtemp()
        src = os.path.join(d, "affirmations.txt")
        with open(src, "w", encoding="utf-8") as f:
            f.write("# header\nI am enough\nI am allowed to rest\n")
        cache = os.path.join(d, "cache.txt")
        feed = AffirmationFeed(cache)
        self.assertEqual(feed.messages, [])
        feed.poll(pathlib.Path(src).as_uri())
        deadline = time.time() + 5
        while feed._busy and time.time() < deadline:
            time.sleep(0.01)
        self.assertEqual(feed.messages, ["I am enough", "I am allowed to rest"])
        self.assertEqual(AffirmationFeed(cache).messages, feed.messages)  # next start uses the cached copy

    def test_failed_fetch_keeps_cached_list(self):
        import os, tempfile, time
        from matrix_rain import AffirmationFeed
        d = tempfile.mkdtemp()
        cache = os.path.join(d, "cache.txt")
        with open(cache, "w", encoding="utf-8") as f:
            f.write("I am enough\n")
        feed = AffirmationFeed(cache)
        feed.poll("file:///" + d.replace("\\", "/") + "/missing.txt")
        deadline = time.time() + 5
        while feed._busy and time.time() < deadline:
            time.sleep(0.01)
        self.assertEqual(feed.messages, ["I am enough"])


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

    def test_affirmation_runs_and_paints_on_every_style(self):
        # Drive the real widget: the timer step starts an affirmation and each style paints without error.
        from PyQt5.QtGui import QImage, QPainter
        w = self._widget()
        w.resize(1280, 720)
        w.config["affirmations"].update({"enabled": True, "messages": ["I am enough"], "backing": "dim",
                                         "styles": ["decode", "catch", "type", "bloom"], "rotate": True,
                                         "clock_sync": False, "source_url": ""})
        w._start_animation()
        w.affirm.wait = 0
        seen = set()
        img = QImage(1280, 720, QImage.Format_ARGB32_Premultiplied)
        for _ in range(4000):
            w._last_tick = __import__("time").perf_counter() - 0.05  # one 50 ms step per call
            w.update_animation()
            a = w.affirm.current
            if a is not None:
                seen.add(a.style)
                p = QPainter(img)
                w.paint_affirmation(p)
                p.end()
                if a.phase() == "hold":
                    self.assertTrue(a.ops(w.affirm.rng))
            if len(seen) == 4:
                break
        w.timer.stop()
        self.assertEqual(seen, {"decode", "catch", "type", "bloom"})
        self.assertIn("I", w._affirm_atlas[1].slots)

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
