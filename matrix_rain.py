#!/usr/bin/env python3
"""
Matrix Screensaver - Digital rain overlay and idle screensaver
Displays falling characters (Latin + Katakana) like in The Matrix. Controllable via system tray;
supports custom messages, speed, glow, and optional screensaver mode (turn on after idle).
"""

import sys
import random
import string
import json
import os
import time
import math
import threading
import urllib.request
import ctypes
from array import array
from ctypes import wintypes
from PyQt5.QtWidgets import (
    QApplication, QWidget, QSystemTrayIcon, QMenu, QAction,
    QInputDialog, QDialog, QVBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QHBoxLayout, QMessageBox, QDialogButtonBox,
    QDoubleSpinBox, QLabel, QFormLayout, QSlider, QCheckBox,
)
from PyQt5.QtCore import Qt, QTimer, QPoint, QRectF
from PyQt5.QtGui import (
    QPainter, QColor, QFont, QFontMetrics, QIcon, QPixmap, QCursor, QImage,
    QBrush, QRadialGradient, QLinearGradient,
    QOpenGLWindow, QOpenGLContext, QOffscreenSurface, QSurfaceFormat, QOpenGLVersionProfile,
    QOpenGLShaderProgram, QOpenGLShader, QOpenGLVertexArrayObject, QOpenGLTexture,
)
from PyQt5 import sip

# Matrix-style character set: Latin, digits, symbols + Katakana (classic Matrix look)
MATRIX_LATIN = string.ascii_letters + string.digits + "!@#$%^&*()_+-=[]{}|;:,.<>?"
# Half-width / full-width Katakana block (iconic digital rain script)
MATRIX_KATAKANA = (
    "ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ"
    "ァアィイゥウェエォオカガキギクグケゲコゴサザシジスズセゼソゾタダチヂッツヅテデトド"
    "ナニヌネノハバパヒビピフブプヘベペホボポマミムメモャヤュユョヨラリルレロヮワヰヱヲン"
)
MATRIX_CHARS = MATRIX_LATIN + MATRIX_KATAKANA

# Global speed scale: 0.85 = 15% slower (applied to all column movement)
SPEED_SCALE = 0.85

# Speeds, flicker and message timing are tuned per animation step, and are applied per second at this
# many steps per second, so the rain moves the same at any frame rate. 64/3 is the rate a 33 ms
# QTimer actually ticked at on Windows (15.6 ms timer granularity), i.e. the look the settings were tuned with.
ANIMATION_STEPS_PER_SEC = 64 / 3

# Affirmations: short lines shown one at a time in the middle of the screen, over the rain.
# Entrance styles: decode (glyphs resolve into letters), catch (rain drops deposit letters),
# type (typed with a block cursor), bloom (soft fade with glow).
AFFIRMATION_STYLES = ("decode", "catch", "type", "bloom")
AFFIRMATION_BACKINGS = ("none", "dim", "clear")
DEFAULT_AFFIRMATIONS = [
    "I am enough",
    "I am worthy of love and respect",
    "I am calm, focused, and in control",
    "I am becoming the best version of myself",
    "I am grateful for everything I have",
    "I am strong, capable, and resilient",
    "I am exactly where I need to be",
    "I am open to new opportunities",
    "I am safe. I am loved. I am whole.",
    "I am in charge of how I feel",
    "I am proud of how far I have come",
    "I am creating a life I love",
    "I am a magnet for good things",
    "I am confident in my abilities",
    "I am at peace with my past",
    "I am allowed to rest",
    "I am learning and growing every day",
    "I am deserving of success",
    "I am healthy, energized, and alive",
    "I am the author of my story",
    "I am loved more than I know",
    "I am brave enough to begin",
    "I am choosing joy today",
    "I am free to be myself",
    "You are doing better than you think",
    "Your work matters",
    "Today is full of possibility",
]


def default_affirmations_config():
    return {
        "enabled": True,
        "messages": list(DEFAULT_AFFIRMATIONS),
        "styles": ["decode", "catch", "type"],
        "rotate": True,
        "interval_seconds": 5,
        "hold_seconds": 7,
        "backing": "dim",
        "font_scale": 1.25,
        # One affirmation per line; when it loads, it replaces "messages" (kept as the offline fallback)
        "source_url": AFFIRMATIONS_URL,
        # Pick message and style from the wall clock, so every PC with the same list shows the same one at once
        "clock_sync": True,
    }


AFFIRMATIONS_URL = "https://raw.githubusercontent.com/ImagineTheGames/MatrixRain/master/affirmations.txt"
# Longest entrance and exit (seconds) any style takes: a clock-synced slot reserves this much around the hold
AFFIRMATION_IN_MAX = 2.5
AFFIRMATION_OUT_MAX = 1.6


def parse_affirmation_list(text):
    """One affirmation per line; blank lines and # comments are skipped."""
    lines = (line.strip() for line in str(text).splitlines())
    return [line for line in lines if line and not line.startswith("#")]


def affirmation_slot_seconds(cfg):
    """Clock-synced cadence: each slot holds one affirmation (entrance, hold, exit) plus the gap."""
    return AFFIRMATION_IN_MAX + cfg["hold_seconds"] + AFFIRMATION_OUT_MAX + cfg["interval_seconds"]


def clock_affirmation(slot, messages, styles, rotate):
    """(message, style) for clock slot number `slot`. Depends only on its arguments, so PCs with the same
    list and settings agree. Messages come in shuffled rounds (every one once per round), never twice in a row."""
    style = styles[slot % len(styles)] if rotate else styles[0]
    n = len(messages)
    if n <= 2:
        return messages[slot % n], style
    deck, pos = divmod(slot, n)

    def order(d):
        o = list(range(n))
        random.Random(d).shuffle(o)
        return o

    o = order(deck)
    if o[0] == order(deck - 1)[-1]:  # swapping the first two keeps each round's last message as it was
        o[0], o[1] = o[1], o[0]
    return messages[o[pos]], style

# Hue cycle speed in degrees per second of wall-clock time (~17 s per full loop).
# Derived from the clock (not frame count) so every PC with a synced clock shows the same color.
HUE_CYCLE_DEG_PER_SEC = 21.0


def clock_hue_angle(now=None):
    """Hue cycle angle (0-360) for a given Unix timestamp; defaults to current time.

    Uses Unix epoch (UTC), so machines in different timezones still agree.
    """
    if now is None:
        now = time.time()
    return (now * HUE_CYCLE_DEG_PER_SEC) % 360.0

def _base_dir():
    """App root: next to the exe when frozen (PyInstaller), else script directory."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


CONFIG_PATH = os.path.join(_base_dir(), "matrix_config.json")


# --- Start with Windows (HKCU Run key; works for the .pyw launcher and the frozen exe) ---
STARTUP_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
STARTUP_VALUE_NAME = "MatrixScreensaver"


def startup_command(frozen=None, executable=None, base_dir=None):
    """Command line Windows runs at login to start this app (tray only, no console)."""
    frozen = getattr(sys, "frozen", False) if frozen is None else frozen
    executable = sys.executable if executable is None else executable
    base_dir = _base_dir() if base_dir is None else base_dir
    if frozen:
        return f'"{executable}"'
    exe_dir, exe_name = os.path.split(executable)
    if exe_name.lower() == "python.exe":
        executable = os.path.join(exe_dir, "pythonw.exe")
    script = os.path.join(base_dir, "run_matrix_rain.pyw")
    return f'"{executable}" "{script}"'


def is_startup_enabled():
    """True if this app is registered to start with Windows."""
    if sys.platform != "win32":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, STARTUP_VALUE_NAME)
            return bool(value)
    except OSError:
        return False


def set_startup_enabled(enabled):
    """Register/unregister this app in the user's Run key. Returns True on success."""
    if sys.platform != "win32":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, STARTUP_VALUE_NAME, 0, winreg.REG_SZ, startup_command())
            else:
                try:
                    winreg.DeleteValue(key, STARTUP_VALUE_NAME)
                except FileNotFoundError:
                    pass
        return True
    except OSError as e:
        print(f"Could not update startup registration: {e}")
        return False


def refresh_startup_registration():
    """If start-with-Windows is on, rewrite the command so it tracks the app's current location."""
    if is_startup_enabled():
        set_startup_enabled(True)

# Windows low-level hooks for screensaver dismiss (any key or mouse = stop)
_kb_hook_id = None
_kb_hook_proc = None
_mouse_hook_id = None
_mouse_hook_proc = None
_user32_hooks = None
if sys.platform == "win32":
    _HOOKPROC = ctypes.CFUNCTYPE(wintypes.LPARAM, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)  # LRESULT-sized
else:
    _HOOKPROC = None


def _hook_user32():
    """user32 with 64-bit-safe prototypes for the hook API. ctypes defaults truncate HHOOK/HMODULE to 32-bit,
    which made SetWindowsHookExW fail with ERROR_MOD_NOT_FOUND (126) and the hooks never install."""
    global _user32_hooks
    if _user32_hooks is None:
        u = ctypes.WinDLL("user32", use_last_error=True)
        u.SetWindowsHookExW.restype = wintypes.HHOOK
        u.SetWindowsHookExW.argtypes = [ctypes.c_int, _HOOKPROC, wintypes.HMODULE, wintypes.DWORD]
        u.UnhookWindowsHookEx.restype = wintypes.BOOL
        u.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
        u.CallNextHookEx.restype = wintypes.LPARAM
        u.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
        _user32_hooks = u
    return _user32_hooks

def get_idle_time_ms():
    """Return system idle time in milliseconds (mouse/keyboard). Windows only; other OS returns 0."""
    try:
        if sys.platform != "win32":
            return 0
        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
        li = LASTINPUTINFO()
        li.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(li)):  # type: ignore
            return 0
        tick = ctypes.windll.kernel32.GetTickCount()  # type: ignore  # ms since boot, 32-bit
        # Unsigned difference to handle GetTickCount wrap
        idle_ms = (tick - li.dwTime) & 0xFFFFFFFF
        return min(idle_ms, 0x7FFFFFFF)  # cap to avoid huge value on wrap
    except Exception:
        pass
    return 0

def _install_screensaver_keyboard_hook(widget):
    """Install global keyboard hook so any keypress dismisses screensaver. Windows only."""
    global _kb_hook_id, _kb_hook_proc
    if sys.platform != "win32" or _kb_hook_id is not None:
        return
    try:
        WH_KEYBOARD_LL = 13
        WM_KEYDOWN, WM_SYSKEYDOWN = 0x100, 0x104
        user32 = _hook_user32()

        def low_level_kb_proc(nCode, wParam, lParam):
            if nCode >= 0 and wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                QTimer.singleShot(0, widget._dismiss_screensaver)
            return user32.CallNextHookEx(None, nCode, wParam, lParam)

        _kb_hook_proc = _HOOKPROC(low_level_kb_proc)
        # hMod=None is correct for low-level hooks (callback lives in this process)
        _kb_hook_id = user32.SetWindowsHookExW(WH_KEYBOARD_LL, _kb_hook_proc, None, 0) or None
    except Exception:
        _kb_hook_id = None

def _install_screensaver_mouse_hook(widget):
    """Install global low-level mouse hook so any mouse move/click dismisses screensaver. Windows only."""
    global _mouse_hook_id, _mouse_hook_proc
    if sys.platform != "win32" or _mouse_hook_id is not None:
        return
    try:
        WH_MOUSE_LL = 14
        user32 = _hook_user32()

        def low_level_mouse_proc(nCode, wParam, lParam):
            if nCode >= 0:  # Any mouse event (move, click, etc.)
                QTimer.singleShot(0, widget._dismiss_screensaver)
            return user32.CallNextHookEx(None, nCode, wParam, lParam)

        _mouse_hook_proc = _HOOKPROC(low_level_mouse_proc)
        _mouse_hook_id = user32.SetWindowsHookExW(WH_MOUSE_LL, _mouse_hook_proc, None, 0) or None
    except Exception:
        _mouse_hook_id = None

def _uninstall_screensaver_keyboard_hook():
    """Remove the keyboard hook. Windows only."""
    global _kb_hook_id
    if sys.platform != "win32" or _kb_hook_id is None:
        return
    try:
        _hook_user32().UnhookWindowsHookEx(_kb_hook_id)
    except Exception:
        pass
    _kb_hook_id = None

def _uninstall_screensaver_mouse_hook():
    """Remove the mouse hook. Windows only."""
    global _mouse_hook_id
    if sys.platform != "win32" or _mouse_hook_id is None:
        return
    try:
        _hook_user32().UnhookWindowsHookEx(_mouse_hook_id)
    except Exception:
        pass
    _mouse_hook_id = None

def _safe_int(val, default):
    """Return int(val) or default if invalid."""
    try:
        return int(val)
    except (TypeError, ValueError):
        return default

def _safe_float(val, default):
    """Return float(val) or default if invalid."""
    try:
        return float(val)
    except (TypeError, ValueError):
        return default

def normalize_affirmations(cfg):
    """Fill missing affirmation settings with defaults and clamp the rest to usable values."""
    out = default_affirmations_config()
    if not isinstance(cfg, dict):
        return out
    out["enabled"] = bool(cfg.get("enabled", out["enabled"]))
    if isinstance(cfg.get("messages"), list):
        out["messages"] = [str(m).strip() for m in cfg["messages"] if str(m).strip()]
    if isinstance(cfg.get("styles"), list):
        out["styles"] = [s for s in cfg["styles"] if s in AFFIRMATION_STYLES] or ["decode"]
    out["rotate"] = bool(cfg.get("rotate", out["rotate"]))
    out["interval_seconds"] = max(1.0, min(3600.0, _safe_float(cfg.get("interval_seconds"), out["interval_seconds"])))
    out["hold_seconds"] = max(1.0, min(60.0, _safe_float(cfg.get("hold_seconds"), out["hold_seconds"])))
    if cfg.get("backing") in AFFIRMATION_BACKINGS:
        out["backing"] = cfg["backing"]
    out["font_scale"] = max(0.5, min(4.0, _safe_float(cfg.get("font_scale"), out["font_scale"])))
    if isinstance(cfg.get("source_url"), str):
        out["source_url"] = cfg["source_url"].strip()
    out["clock_sync"] = bool(cfg.get("clock_sync", out["clock_sync"]))
    if "comment" in cfg:
        out["comment"] = cfg["comment"]
    return out

def load_config():
    """Load configuration from JSON file"""
    default_config = {
        "speed": {"min": 4.0, "max": 9.0},
        "animation": {"fps": 30},
        "column": {"min_length": 24, "max_length": 120},
        "font": {"name": "Consolas", "size": 14},
        "custom_messages": [],
        "glow": {"strength": 90, "radius": 3},
        "screensaver": {"enabled": True, "idle_seconds": 60, "black_background": False},
        "mouse_highlight": False,
        "hue": {"shift": 0, "cycle": False},
        "affirmations": default_affirmations_config(),
    }
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                config = json.load(f)
            for key in default_config:
                if key not in config:
                    config[key] = default_config[key]
                elif isinstance(default_config[key], dict) and key != "custom_messages":
                    for subkey in default_config[key]:
                        if subkey not in config[key]:
                            config[key][subkey] = default_config[key][subkey]
            if not isinstance(config.get("custom_messages"), list):
                config["custom_messages"] = default_config["custom_messages"]
            if "glow" not in config or not isinstance(config.get("glow"), dict):
                config["glow"] = {"strength": 90, "radius": 3}
            for k, default in (("strength", 90), ("radius", 3)):
                if k not in config["glow"]:
                    config["glow"][k] = default
                else:
                    config["glow"][k] = _safe_int(config["glow"][k], default)
            if "screensaver" not in config or not isinstance(config.get("screensaver"), dict):
                config["screensaver"] = {"enabled": True, "idle_seconds": 60, "black_background": False}
            # Migrate old idle_minutes to idle_seconds
            if "idle_seconds" not in config["screensaver"] and "idle_minutes" in config["screensaver"]:
                config["screensaver"]["idle_seconds"] = max(5, min(7200, _safe_int(config["screensaver"]["idle_minutes"], 1) * 60))
            for k, default in (("enabled", True), ("idle_seconds", 60), ("black_background", False)):
                if k not in config["screensaver"]:
                    config["screensaver"][k] = default
                elif k == "idle_seconds":
                    config["screensaver"][k] = max(5, min(7200, _safe_int(config["screensaver"][k], 60)))
                elif k == "black_background":
                    config["screensaver"][k] = bool(config["screensaver"][k])
            if "mouse_highlight" not in config:
                config["mouse_highlight"] = False
            if "hue" not in config or not isinstance(config.get("hue"), dict):
                config["hue"] = {"shift": 0, "cycle": False}
            for k, default in (("shift", 0), ("cycle", False)):
                if k not in config["hue"]:
                    config["hue"][k] = default
                elif k == "shift":
                    config["hue"][k] = max(0, min(360, _safe_int(config["hue"][k], 0)))
            config["affirmations"] = normalize_affirmations(config.get("affirmations"))
            return config
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=4)
        return default_config
    except Exception as e:
        print(f"Warning: Could not load config file: {e}. Using defaults.")
        return default_config

def save_custom_messages(messages):
    """Save only custom_messages to config file (merge with existing config)."""
    try:
        config = load_config()
        config["custom_messages"] = list(messages)
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        print(f"Could not save messages: {e}")

def save_mouse_highlight(enabled):
    """Save mouse highlight option to config."""
    try:
        config = load_config()
        config["mouse_highlight"] = bool(enabled)
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
        return config
    except Exception as e:
        print(f"Could not save mouse_highlight: {e}")
        return load_config()

def save_screensaver(enabled, idle_seconds, black_background=None):
    """Save screensaver settings to config. black_background=None keeps the current value."""
    try:
        config = load_config()
        if "screensaver" not in config:
            config["screensaver"] = {}
        config["screensaver"]["enabled"] = bool(enabled)
        config["screensaver"]["idle_seconds"] = max(5, min(7200, int(idle_seconds)))
        if black_background is not None:
            config["screensaver"]["black_background"] = bool(black_background)
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
        return config
    except Exception as e:
        print(f"Could not save screensaver: {e}")
        return load_config()

def save_hue(hue_shift, cycle):
    """Save hue shift (0-360) and cycle option to config."""
    try:
        config = load_config()
        if "hue" not in config:
            config["hue"] = {}
        config["hue"]["shift"] = max(0, min(360, int(hue_shift)))
        config["hue"]["cycle"] = bool(cycle)
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
        return config
    except Exception as e:
        print(f"Could not save hue: {e}")
        return load_config()

def save_glow(strength, radius):
    """Save glow strength and radius to config."""
    try:
        config = load_config()
        if "glow" not in config:
            config["glow"] = {}
        config["glow"]["strength"] = int(strength)
        config["glow"]["radius"] = int(radius)
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
        return config
    except Exception as e:
        print(f"Could not save glow: {e}")
        return load_config()

def save_speed(speed_min, speed_max):
    """Save speed min/max to config and return updated config."""
    try:
        config = load_config()
        if "speed" not in config:
            config["speed"] = {}
        config["speed"]["min"] = float(speed_min)
        config["speed"]["max"] = float(speed_max)
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
        return config
    except Exception as e:
        print(f"Could not save speed: {e}")
        return load_config()

def save_affirmations_enabled(enabled):
    """Turn the centred affirmations on or off in the config file and return the updated config."""
    try:
        config = load_config()
        config["affirmations"]["enabled"] = bool(enabled)
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
        return config
    except Exception as e:
        print(f"Could not save affirmations: {e}")
        return load_config()


def wrap_words(text, max_cols):
    """Greedy word wrap into lines of at most max_cols characters (a longer word gets a line of its own)."""
    lines, cur = [], ""
    for word in str(text).split():
        if not cur:
            cur = word
        elif len(cur) + 1 + len(word) <= max_cols:
            cur += " " + word
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


class Affirmation:
    """One affirmation on screen: its letters laid out in a centred block and its timeline (seconds)."""
    FADE_IN = 0.6
    TYPE_OUT = 0.75   # terminal style: seconds to backspace the whole line
    FALL_ACCEL = 26.0  # decode/catch exit: letters drip down at this many rows/s^2

    def __init__(self, text, style, hold, width, height, cell_w, cell_h, rng):
        self.text, self.style, self.hold = text, style, hold
        self.cell_w, self.cell_h = cell_w, cell_h
        self.t = 0.0
        max_cols = max(10, int(width * 0.62 / max(1, cell_w)))
        self.lines = wrap_words(text, max_cols) or [text]
        self.top = round(height / 2 - len(self.lines) * cell_h / 2)
        # Terminal style types faster for long lines so every entrance fits in AFFIRMATION_IN_MAX
        type_step = min(0.055, 1.85 / max(1, sum(len(line) for line in self.lines)))
        self.cells = []  # [char, x, y, index in message, entrance time]
        for li, line in enumerate(self.lines):
            left = round(width / 2 - len(line) * cell_w / 2)
            for ci, ch in enumerate(line):
                k = len(self.cells)
                if style == "decode":
                    at = rng.uniform(0.15, 1.4)
                elif style == "catch":
                    at = rng.uniform(0.2, 1.8)
                elif style == "type":
                    at = 0.25 + k * type_step
                else:
                    at = 0.1
                self.cells.append((ch, left + ci * cell_w, self.top + li * cell_h, k, at))
        self.in_dur = max(c[4] for c in self.cells) + 0.35
        self.out_dur = 0.9 if style == "type" else 1.6
        self.end = self.in_dur + hold + self.out_dur
        widest = max(len(line) for line in self.lines)
        self.band = (round(width / 2 - widest * cell_w / 2), self.top,
                     round(width / 2 + widest * cell_w / 2), self.top + len(self.lines) * cell_h)

    def phase(self):
        if self.t < self.in_dur:
            return "in"
        return "hold" if self.t < self.in_dur + self.hold else "out"

    def presence(self):
        """0..1: how strongly the affirmation (and its backing) is on screen."""
        t = self.t
        if t < self.in_dur:
            return min(1.0, t / self.FADE_IN)
        out = t - self.in_dur - self.hold
        return 1.0 if out < 0 else max(0.0, 1.0 - out / self.out_dur)

    def ops(self, rng):
        """Draw list for this moment: (kind, char, x, y, alpha, white, glow). kind is "letter" (the text,
        white = flash toward white, glow = extra halo), "scramble" (a dim random glyph), "drop_head" /
        "drop_trail" (a falling rain drop), or "cursor" (terminal block; char is None)."""
        t, style, ch_h = self.t, self.style, self.cell_h
        phase = self.phase()
        out_t = t - self.in_dur - self.hold
        breathe = 0.15 * (1 + math.sin(t * 2.2)) if phase == "hold" else 0.0
        n = len(self.cells)
        ops = []
        last_shown = None
        for ch, x, y, k, at in self.cells:
            if ch == " ":
                if style == "type" and (t >= at if phase != "out" else k < n - int(out_t / self.TYPE_OUT * n)):
                    last_shown = (x, y)
                continue
            if phase == "out":
                if style == "type":
                    if k >= n - int(out_t / self.TYPE_OUT * n):
                        continue
                    ops.append(("letter", ch, x, y, 1.0, 0.0, 0.0))
                    last_shown = (x, y)
                elif style == "bloom":
                    ops.append(("letter", ch, x, y, max(0.0, 1 - out_t / 1.4), 0.0, 0.0))
                else:
                    # Letters scramble back into glyphs and drip down like rain
                    o = out_t - (k * 37 % 11) / 11 * 0.5
                    if o <= 0:
                        ops.append(("letter", ch, x, y, 1.0, 0.0, 0.0))
                        continue
                    alpha = 1 - o / 1.1
                    if alpha <= 0:
                        continue
                    glyph = rng.choice(MATRIX_CHARS) if rng.random() < 0.35 else ch
                    fall = 0.5 * self.FALL_ACCEL * o * o * ch_h
                    ops.append(("letter", glyph, x, y + fall, alpha, max(0.0, 1 - o * 3), 0.0))
                continue
            since = t - at
            if style == "decode":
                if since < 0:
                    if t > 0.05:
                        ops.append(("scramble", rng.choice(MATRIX_CHARS), x, y, 0.55, 0.0, 0.0))
                else:
                    ops.append(("letter", ch, x, y, 1.0, max(0.0, 1 - since / 0.45), breathe))
            elif style == "catch":
                if since < 0:
                    p = 1 + since / 0.55  # a drop races down this column, landing at the letter's time
                    if p > 0:
                        head_y = y - (1 - p) * (y + ch_h)
                        ops.append(("drop_head", rng.choice(MATRIX_CHARS), x, head_y, 1.0, 0.0, 0.0))
                        for j in range(1, 6):
                            ops.append(("drop_trail", rng.choice(MATRIX_CHARS), x, head_y - j * ch_h,
                                        (1 - j / 6) * 0.8, 0.0, 0.0))
                else:
                    ops.append(("letter", ch, x, y, 1.0, max(0.0, 1 - since / 0.5), breathe))
            elif style == "type":
                if since >= 0:
                    ops.append(("letter", ch, x, y, 1.0, max(0.0, 1 - since / 0.2), breathe))
                    last_shown = (x, y)
            else:
                ops.append(("letter", ch, x, y, min(1.0, t / 1.1), 0.0, min(1.0, t / 0.8) * 0.6 + breathe))
        if style == "type":
            presence = self.presence()
            if presence > 0.05 and (phase == "in" or int(t * 2.4) % 2 == 0):
                if last_shown is None:
                    cx, cy = self.cells[0][1], self.cells[0][2]
                else:
                    cx, cy = last_shown[0] + self.cell_w, last_shown[1]
                ops.append(("cursor", None, cx, cy, 0.9 * presence, 0.0, 0.0))
        return ops


class AffirmationPlayer:
    """Decides when the next affirmation starts, which message and entrance style it gets, and advances
    the one on screen. Pure Python (no Qt) so the timing is testable; the widget draws Affirmation.ops()."""
    FIRST_DELAY = 2.0  # seconds after the rain starts

    def __init__(self, rng=None):
        self.rng = rng or random.Random()
        self.current = None
        self.wait = self.FIRST_DELAY
        self._last_message = None
        self._style_index = -1
        self._clock_slot = None  # clock-synced mode: slot already shown (or skipped)

    def reset(self):
        """The rain (re)started: clear the screen and show the first affirmation shortly."""
        self.current = None
        self.wait = self.FIRST_DELAY
        self._clock_slot = None

    def _next_style(self, cfg):
        styles = cfg["styles"]
        if not cfg["rotate"]:
            return styles[0]
        self._style_index = (self._style_index + 1) % len(styles)
        return styles[self._style_index]

    def _next_message(self, messages):
        choices = [m for m in messages if m != self._last_message] or messages
        msg = self.rng.choice(choices)
        self._last_message = msg
        return msg

    def update(self, dt, cfg, width, height, cell_w, cell_h, messages=None, now=None):
        """Advance dt seconds. Returns the new Affirmation when one starts this step, else None.
        messages overrides cfg["messages"] (e.g. the synced list); now is the Unix time (clock-synced mode)."""
        messages = cfg["messages"] if messages is None else messages
        if not cfg["enabled"] or not messages:
            self.current = None
            return None
        if cfg.get("clock_sync"):
            return self._update_clock(cfg, messages, time.time() if now is None else now,
                                      width, height, cell_w, cell_h)
        if self.current is not None:
            self.current.t += dt
            if self.current.t >= self.current.end:
                self.current = None
                self.wait = cfg["interval_seconds"]
            return None
        self.wait -= dt
        if self.wait > 0:
            return None
        self.current = Affirmation(self._next_message(messages), self._next_style(cfg),
                                   cfg["hold_seconds"], width, height, cell_w, cell_h, self.rng)
        return self.current

    def _update_clock(self, cfg, messages, now, width, height, cell_w, cell_h):
        """Clock-synced mode: slot k of the day-independent Unix timeline starts at k * slot length on
        every PC; its message, style and letter timings come from k alone."""
        slot_len = affirmation_slot_seconds(cfg)
        slot = int(now // slot_len)
        start = slot * slot_len
        if self.current is not None:
            self.current.t = now - self.current.clock_start
            if self.current.t < self.current.end:
                return None
            self.current = None
        if slot == self._clock_slot:
            return None
        self._clock_slot = slot
        msg, style = clock_affirmation(slot, messages, cfg["styles"], cfg["rotate"])
        a = Affirmation(msg, style, cfg["hold_seconds"], width, height, cell_w, cell_h, random.Random(slot))
        a.t = now - start
        if a.t > a.in_dur:
            return None  # joined after its entrance: stay in step and wait for the next slot
        a.clock_start = start
        self.current = a
        return a


class AffirmationFeed:
    """The affirmation list from a text file on the web (one per line), fetched on a background thread
    and cached on disk so the last good copy survives restarts and offline PCs."""
    REFRESH_SECONDS = 3600
    RETRY_SECONDS = 300

    def __init__(self, cache_path):
        self.cache_path = cache_path
        self.messages = []
        try:
            with open(cache_path, encoding="utf-8") as f:
                self.messages = parse_affirmation_list(f.read())
        except OSError:
            pass
        self._next_fetch = 0.0
        self._busy = False

    def poll(self, url):
        """Start a fetch if one is due; cheap enough to call every frame."""
        if not url or self._busy or time.monotonic() < self._next_fetch:
            return
        self._busy = True
        self._next_fetch = time.monotonic() + self.RETRY_SECONDS  # pushed out to REFRESH_SECONDS on success
        threading.Thread(target=self._fetch, args=(url,), daemon=True).start()

    def _fetch(self, url):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "MatrixRain", "Cache-Control": "no-cache"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                text = resp.read(1_000_000).decode("utf-8")
            messages = parse_affirmation_list(text)
            if messages:
                self.messages = messages
                self._next_fetch = time.monotonic() + self.REFRESH_SECONDS
                with open(self.cache_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(messages) + "\n")
        except Exception as e:
            print(f"Could not fetch affirmations from {url}: {e}")
        finally:
            self._busy = False


class MatrixColumn:
    """Represents a single column of falling characters. Always starts above screen and falls top to bottom."""
    def __init__(self, x, window_height, speed_min, speed_max, length_min, length_max, char_height):
        self.x = x
        self.char_height = char_height
        self.speed_min = speed_min
        self.speed_max = speed_max
        self.length_min = length_min
        self.length_max = length_max
        self.speed = random.uniform(speed_min, speed_max)
        # Many columns span full screen (top to bottom) in one go; rest use random length with longer trails
        full_height_chars = max(length_min, (window_height // char_height) + random.randint(5, 50))
        if random.random() < 0.65:
            self.length = full_height_chars  # Top to bottom in one go
        else:
            low = max(length_min, full_height_chars // 2)
            high = min(length_max, full_height_chars)
            self.length = random.randint(low, high) if low <= high else full_height_chars
        self.chars = []
        # Bumped on every change to chars; last_flicker = (version, index) lets the GPU renderer patch one cell
        self.chars_version = 0
        self.last_flicker = None
        self.is_message = False
        self.head_offset = 0.0
        self.trail_persistence = random.uniform(0.6, 1.6)
        self.generate_chars()
        # Place anywhere along the travel range (steady state), so the first frame already shows rain.
        # Starting every column above the screen left a black-background screensaver blank for 10-30 s.
        self.y = -self.length * self.char_height + random.randint(0, window_height)
        self.head_offset = random.uniform(0, self.length)
    
    def generate_chars(self):
        """Generate random characters for this column (Matrix-style: Latin + Katakana)"""
        self.chars = [random.choice(MATRIX_CHARS) for _ in range(self.length)]
        self.chars_version += 1

    def set_message(self, text):
        """Display a custom message in this column (one char per position). White shine will animate top to bottom."""
        if not text:
            return
        self.chars = list(str(text))
        self.chars_version += 1
        self.length = len(self.chars)
        self.is_message = True
        self.head_offset = 0.0  # Start white at top of message so it animates down
        self.y = -self.length * self.char_height  # Start above top so message falls in from top
    
    def update(self, window_height, steps=1.0):
        """Advance by steps animation steps (fractional; see ANIMATION_STEPS_PER_SEC): move the column,
        move the white shine down it, flicker trail chars."""
        self.y += self.speed * SPEED_SCALE * steps
        # Advance white shine down through the column (so it "falls" over the letters)
        try:
            self.head_offset = (getattr(self, "head_offset", 0) + self.speed * 0.35 * SPEED_SCALE * steps) % 1e6
        except (TypeError, ValueError):
            self.head_offset = 0
        if self.y + self.length * self.char_height > window_height:
            self.y = -self.length * self.char_height
            self.speed = random.uniform(self.speed_min, self.speed_max)
            self.head_offset = 0.0
            self.trail_persistence = random.uniform(0.6, 1.6)
            if self.is_message:
                self.is_message = False
            # ~65% of columns span full screen (top to bottom) in one go; rest get longer trails
            full_height_chars = max(self.length_min, (window_height // self.char_height) + random.randint(5, 50))
            if random.random() < 0.65:
                self.length = full_height_chars
            else:
                low = max(self.length_min, full_height_chars // 2)
                high = min(self.length_max, full_height_chars)
                self.length = random.randint(low, high) if low <= high else full_height_chars
            self.generate_chars()
        elif not self.is_message and random.random() < 0.2 * steps:
            # Flicker less often: ~20% of steps, replace only one character per column
            if self.length > 0:
                idx = random.randint(0, self.length - 1)
                self.chars[idx] = random.choice(MATRIX_CHARS)
                self.chars_version += 1
                self.last_flicker = (self.chars_version, idx)

def hue_shift_rgb(rgb, hue_degrees):
    """(r, g, b) with its HSV hue rotated by hue_degrees; greys (incl. white) are unchanged."""
    h, s, v, _ = QColor(*rgb).getHsv()
    if s == 0 or h < 0:
        return tuple(rgb)
    out = QColor.fromHsv(int((h + hue_degrees) % 360), s, v)
    return (out.red(), out.green(), out.blue())


class GlyphAtlas:
    """Pre-rendered glyph sprites so painting is one blit per character instead of text shaping.

    drawText re-shapes its string on every call and the glow drew each glyph up to 25 times, which
    capped the rain at ~7 fps on one full core. Here every glyph is rasterised once in white into a
    "core" atlas; glow atlases are built from it with shifted, faded copies (the same layers the old
    per-frame glow drew), and each colour tier is the white mask tinted with CompositionMode_SourceIn.
    Hue changes only re-tint a handful of small images.
    """
    PAD = 6  # room for the 3 px glow plus glyph side bearings
    CORE_INSET = 4  # glyph ink stays within PAD - 4 px of the cell box; core-only sprites skip that margin
    COLS = 32
    GLOW_SCALE_BY_D = {1: 1.0, 2: 0.55, 3: 0.3}
    # Colour tiers: name -> (mask, base rgb). Head core is plain white, which no hue shift changes.
    TIERS = {
        "head_glow": ("glow130", (180, 255, 180)),
        "head2": ("t2", (0, 255, 70)),
        "near_glow": ("glow40", (0, 220, 60)),
        "near": ("core", (0, 220, 60)),
        "trail": ("core", (0, 180, 55)),
    }

    def __init__(self, font):
        self.font = font
        fm = QFontMetrics(font)
        self.ascent = fm.ascent()
        self.cell_h = fm.height() + 2 * self.PAD
        self.cell_w = max(fm.width(c) for c in MATRIX_CHARS) + 2 * self.PAD
        self._fm = fm
        self.slots = {}
        self._chars = []
        self.core = None
        self.images = {}
        self._glow_key = None
        self._hue = None
        self.add_chars(MATRIX_CHARS)

    def add_chars(self, chars):
        """Register characters (e.g. from a custom message); new ones are rasterised immediately."""
        new = [c for c in dict.fromkeys(chars) if c not in self.slots]
        if not new:
            return
        widest = max(self._fm.width(c) for c in new) + 2 * self.PAD
        if widest > self.cell_w:
            self.cell_w = widest
        self._chars.extend(new)
        self._rebuild_core()

    def _rebuild_core(self):
        rows = (len(self._chars) + self.COLS - 1) // self.COLS
        self.core = QImage(self.COLS * self.cell_w, rows * self.cell_h, QImage.Format_ARGB32_Premultiplied)
        self.core.fill(Qt.transparent)
        p = QPainter(self.core)
        p.setFont(self.font)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        p.setPen(QColor(255, 255, 255))
        self.slots = {}
        for n, ch in enumerate(self._chars):
            sx, sy = (n % self.COLS) * self.cell_w, (n // self.COLS) * self.cell_h
            self.slots[ch] = (sx, sy)
            p.setClipRect(sx, sy, self.cell_w, self.cell_h)
            p.drawText(sx + self.PAD, sy + self.PAD + self.ascent, ch)
        p.end()
        self.trim()  # glow and tinted images derive from core

    def trim(self):
        """Drop the derived glow and tinted images; prepare() rebuilds them when the rain is drawn again."""
        self._masks = {}
        self.images = {}
        self._glow_key = None
        self._hue = None

    def _glow_mask(self, base_alpha, strength, radius, with_core=False):
        """White mask of the glow rings (alpha = base * strength * ring scale), optionally with the core on top."""
        img = QImage(self.core.size(), QImage.Format_ARGB32_Premultiplied)
        img.fill(Qt.transparent)
        p = QPainter(img)
        for d in range(1, radius + 1):
            alpha = max(0, min(255, int(base_alpha * strength / 100.0 * self.GLOW_SCALE_BY_D[d])))
            if alpha <= 0:
                continue
            p.setOpacity(alpha / 255.0)
            for dx, dy in ((-d, -d), (-d, 0), (-d, d), (0, -d), (0, d), (d, -d), (d, 0), (d, d)):
                p.drawImage(dx, dy, self.core)
        if with_core:
            p.setOpacity(1.0)
            p.drawImage(0, 0, self.core)
        p.end()
        return img

    def masks(self, strength, radius):
        """White masks: glyph cores plus glow rings for these glow settings (a new dict whenever rebuilt)."""
        glow_key = (strength, radius)
        if glow_key != self._glow_key:
            self._masks = {
                "core": self.core,
                "glow130": self._glow_mask(130, strength, radius),
                "glow40": self._glow_mask(40, strength, radius),
                "t2": self._glow_mask(80, strength, radius, with_core=True),
            }
            self._glow_key = glow_key
            self._hue = None
        return self._masks

    def prepare(self, strength, radius, hue_degrees):
        """Rebuild glow masks if glow settings changed and re-tint if the (integer) hue changed."""
        self.masks(strength, radius)
        hue = int(hue_degrees) % 360
        if hue == self._hue:
            return
        images = {"head_core": self.core}
        for name, (mask, rgb) in self.TIERS.items():
            img = self._masks[mask].copy()
            p = QPainter(img)
            p.setCompositionMode(QPainter.CompositionMode_SourceIn)
            p.fillRect(img.rect(), QColor(*hue_shift_rgb(rgb, hue)))
            p.end()
            images[name] = img
        self.images = images
        self._hue = hue


class MatrixRainWidget(QWidget):
    """Main widget for Matrix rain effect"""
    def __init__(self):
        super().__init__()
        # Load configuration
        self.config = load_config()
        self.affirm = AffirmationPlayer()
        self._affirm_atlas = None  # built on first use: (font scale, atlas, text cell size)
        self.affirm_feed = AffirmationFeed(os.path.join(_base_dir(), "affirmations_cache.txt"))
        self.affirm_feed.poll((self.config.get("affirmations") or {}).get("source_url"))
        self.init_ui()
        self.init_matrix()
        # Black-background screensaver window; swapped for the GPU-drawn one on first use (see
        # _check_screensaver_idle) so the OpenGL driver is not loaded while the app just sits in the tray
        self._solid_saver = SolidScreensaverWindow(self)
        self._try_gpu_saver = True

        # Timer for animation (started in showEvent so we don't run when hidden in screensaver mode)
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_animation)
        self._animation_interval = int(1000 / (self.config.get("animation", {}).get("fps", 30)))
        # Screensaver: check idle periodically; when active, check often for activity to dismiss
        # Timer parented to app so it runs even when widget was never shown (screensaver-only start)
        self._screensaver_active = False
        app = QApplication.instance()
        self._idle_check_timer = QTimer(app if app else self)
        self._idle_check_timer.timeout.connect(self._check_screensaver_idle)
        self._idle_check_timer.start(5000)  # Check every 5 seconds to show
        QTimer.singleShot(2000, self._check_screensaver_idle)  # First check after 2 s
        self._screensaver_dismiss_timer = QTimer()
        self._screensaver_dismiss_timer.timeout.connect(self._check_screensaver_dismiss)
        self._screensaver_dismiss_timer.setInterval(200)  # When active, check every 200ms for activity
        # Follow screen changes (resolution switch, monitor plug/unplug, virtual displays)
        if app is not None:
            app.primaryScreenChanged.connect(lambda *_: self._on_screen_changed())
            screen = app.primaryScreen()
            if screen is not None:
                screen.geometryChanged.connect(lambda *_: self._on_screen_changed())
        # System tray (must be after widget is created)
        self.create_tray_icon()
        self.setMouseTracking(self.config.get("mouse_highlight", False))
    
    def init_ui(self):
        """Initialize the UI"""
        # Set window flags for borderless, always on top, transparent
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |
            Qt.FramelessWindowHint |
            Qt.Tool
        )
        
        # Enable transparency
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Set window size (fullscreen by default, can be adjusted)
        try:
            screen = QApplication.primaryScreen()
            if screen is not None:
                self.setGeometry(screen.geometry())
            else:
                self.setGeometry(0, 0, 1920, 1080)
        except Exception:
            self.setGeometry(0, 0, 1920, 1080)
        
        # Set font from config (use Japanese-capable font for Katakana)
        font_name = self.config.get("font", {}).get("name", "Consolas")
        font_size = self.config.get("font", {}).get("size", 14)
        self.font = QFont(font_name, font_size, QFont.Bold)
        if not self.font.exactMatch():
            for fallback in ("MS Gothic", "Yu Gothic UI", "Meiryo", "Consolas"):
                self.font = QFont(fallback, font_size, QFont.Bold)
                if self.font.exactMatch() or fallback == "Consolas":
                    break
        self.font_metrics = QFontMetrics(self.font)
        self.char_height = max(1, self.font_metrics.height())
        self.char_width = max(1, self.font_metrics.width('A'), self.font_metrics.width('ｱ'))
        self.atlas = GlyphAtlas(self.font)
        self.atlas.add_chars("".join(str(m) for m in self.config.get("custom_messages") or []))
    
    def init_matrix(self):
        """Initialize matrix columns (spaced for distinct streams like the movie)"""
        self.columns = []
        width = max(1, self.width())
        height = max(1, self.height())
        col_spacing = max(self.char_width + 2, int(self.char_width * 1.3))
        num_columns = max(1, width // col_spacing)
        
        speed_min = self.config.get("speed", {}).get("min", 2.0)
        speed_max = self.config.get("speed", {}).get("max", 5.0)
        length_min = self.config.get("column", {}).get("min_length", 10)
        length_max = self.config.get("column", {}).get("max_length", 30)
        
        self.col_spacing = col_spacing
        for i in range(num_columns):
            x = i * col_spacing
            self.columns.append(MatrixColumn(x, height, speed_min, speed_max, length_min, length_max, self.char_height))
        
        self._message_inject_counter = 0
        self._message_inject_interval = max(15, int(1.0 * (self.config.get("animation", {}).get("fps", 30))))  # ~every 1 sec so messages are visible
    
    def _effective_hue_degrees(self):
        """Current hue shift in degrees (config shift + clock-synced cycle offset when cycling)."""
        cfg = self.config.get("hue") or {}
        shift = max(0, min(360, _safe_int(cfg.get("shift"), 0)))
        if cfg.get("cycle"):
            shift = (shift + clock_hue_angle()) % 360
        return shift

    def glow_settings(self):
        """(strength 0-100, radius 1-3) from config."""
        glow_cfg = self.config.get("glow") or {}
        return (max(0, min(100, _safe_int(glow_cfg.get("strength"), 90))),
                max(1, min(3, _safe_int(glow_cfg.get("radius"), 3))))

    def paintEvent(self, event):
        """Paint the matrix rain effect (Matrix-style: white leading shine, green trail fade, glow)"""
        try:
            painter = QPainter(self)
            painter.setFont(self.font)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.TextAntialiasing)
        except Exception:
            return
        self.paint_rain(painter)
        self.paint_affirmation(painter)

    def _affirmation_sprites(self, cfg):
        """(atlas, (cell_w, cell_h)) for the affirmation text: the rain font scaled up, rebuilt if the scale changes."""
        scale = cfg.get("font_scale", 1.25)
        if self._affirm_atlas is None or self._affirm_atlas[0] != scale:
            size = self.font.pointSizeF() if self.font.pointSizeF() > 0 else 14.0
            font = QFont(self.font.family(), max(1, round(size * scale)), QFont.Bold)
            atlas = GlyphAtlas(font)
            atlas.add_chars("".join(cfg.get("messages") or []))
            fm = QFontMetrics(font)
            # Letters sit on a wide monospace grid, like the rain's own columns
            cell = (max(2, round(max(1, fm.width("M")) * 1.5)), max(2, fm.height()))
            self._affirm_atlas = (scale, atlas, cell)
        return self._affirm_atlas[1], self._affirm_atlas[2]

    def paint_affirmation(self, painter):
        """Draw the affirmation on screen (if any) over the rain: the backing, then its glyph sprites."""
        a = self.affirm.current
        if a is None or self._affirm_atlas is None:
            return
        atlas = self._affirm_atlas[1]
        painter.save()
        try:
            presence = a.presence()
            x0, y0, x1, y1 = a.band
            backing = (self.config.get("affirmations") or {}).get("backing", "dim")
            if backing == "dim" and presence > 0:
                # Wide black halo that fades the rain toward the text (on the overlay it also darkens the desktop)
                grad = QRadialGradient(0, 0, 1)
                grad.setColorAt(0, QColor(0, 0, 0, int(150 * presence)))
                grad.setColorAt(1, QColor(0, 0, 0, 0))
                painter.save()
                painter.translate((x0 + x1) / 2, (y0 + y1) / 2)
                painter.scale(self.width() * 0.45, max(a.cell_h * 5, (y1 - y0 + 4 * a.cell_h) * 1.4))
                painter.fillRect(QRectF(-1, -1, 2, 2), QBrush(grad))
                painter.restore()
                # Then a feathered strip hugging the text, so passing drops do not cross the letters:
                # stacked rounded rects, each a little larger and adding a little more black toward the middle
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(0, 0, 0, int(76 * presence)))
                step = a.cell_h * 0.3
                for i in range(6):
                    grow = step * (5 - i)
                    painter.drawRoundedRect(QRectF(x0 - a.cell_w * 0.5 - grow, y0 - a.cell_h * 0.25 - grow,
                                                   x1 - x0 + a.cell_w + 2 * grow, y1 - y0 + a.cell_h * 0.5 + 2 * grow),
                                            a.cell_h * 0.6 + grow, a.cell_h * 0.6 + grow)
            elif backing == "clear" and presence > 0:
                pad = a.cell_h * 1.5
                grad = QLinearGradient(0, y0 - pad, 0, y1 + pad)
                solid = QColor(0, 0, 0, int(230 * presence))
                grad.setColorAt(0, QColor(0, 0, 0, 0))
                grad.setColorAt(0.25, solid)
                grad.setColorAt(0.75, solid)
                grad.setColorAt(1, QColor(0, 0, 0, 0))
                painter.fillRect(QRectF(0, y0 - pad, self.width(), y1 - y0 + 2 * pad), QBrush(grad))
            strength, radius = self.glow_settings()
            hue = self._effective_hue_degrees()
            atlas.prepare(strength, radius, hue)
            images, slots = atlas.images, atlas.slots
            cw, chh, pad = atlas.cell_w, atlas.cell_h, atlas.PAD
            cursor_rgb = hue_shift_rgb(atlas.TIERS["near"][1], int(hue) % 360)

            def blit(name, opacity):
                if opacity > 0.004:
                    painter.setOpacity(min(1.0, opacity))
                    painter.drawImage(dx, dy, images[name], sx, sy, cw, chh)

            for kind, ch, x, y, alpha, white, glow in a.ops(self.affirm.rng):
                if kind == "cursor":
                    painter.setOpacity(alpha)
                    painter.fillRect(QRectF(x + 2, y + 2, a.cell_w - 3, a.cell_h - 2), QColor(*cursor_rgb))
                    continue
                slot = slots.get(ch)
                if slot is None:
                    continue
                sx, sy = slot
                dx, dy = int(x) - pad, int(y) - pad
                if kind == "letter":
                    blit("head2", alpha)
                    blit("head_glow", alpha * (0.35 + glow))
                    blit("head_core", alpha * white)
                elif kind == "scramble":
                    blit("trail", alpha)
                elif kind == "drop_head":
                    blit("head_glow", alpha)
                    blit("head_core", alpha)
                else:
                    blit("near", alpha)
        except Exception:
            pass
        painter.restore()

    def paint_rain(self, painter):
        """Draw the rain with painter; shared by this overlay and the solid screensaver window."""
        height = self.height()
        columns = getattr(self, "columns", [])
        try:
            # Settings and hue are resolved once per frame; the atlas only re-tints when the integer hue moves
            strength, radius = self.glow_settings()
            atlas = self.atlas
            atlas.prepare(strength, radius, self._effective_hue_degrees())
            images = atlas.images
            head_core, head_glow, head2 = images["head_core"], images["head_glow"], images["head2"]
            near, near_glow, trail = images["near"], images["near_glow"], images["trail"]
            slots = atlas.slots
            cw, chh = atlas.cell_w, atlas.cell_h
            top = atlas.ascent + atlas.PAD  # baseline y -> sprite top
            ci = atlas.CORE_INSET
            ccw, cch = cw - 2 * ci, chh - 2 * ci
            draw = painter.drawImage
            set_opacity = painter.setOpacity
            char_height = self.char_height
            bottom_fade_zone = max(60, height // 8)
            fade_start = height - bottom_fade_zone
            mouse_highlight = self.config.get("mouse_highlight", False)
            cursor_pos = self.mapFromGlobal(QCursor.pos()) if mouse_highlight else None
            cx, cy = (cursor_pos.x(), cursor_pos.y()) if cursor_pos is not None else (None, None)
            opacity = None  # last value given to set_opacity, so runs of equal trail alpha skip the call
            for col in columns:
                chars = col.chars
                if not chars or col.length <= 0:
                    continue
                L = max(col.length, 1)
                try:
                    head_index = int(col.head_offset) % L
                except (TypeError, ValueError):
                    head_index = 0
                persistence = max(0.3, col.trail_persistence)
                denom = max(L - 6, 1)
                trail_rate = 1.0 / (persistence * denom)
                col_y = col.y
                sx_col = col.x - atlas.PAD
                cx_col = sx_col + ci
                in_cursor_col = cx is not None and col.x <= cx < col.x + self.char_width
                # Only walk the rows that are on screen (columns extend well above and below it)
                first = max(0, math.ceil((-char_height - col_y) / char_height))
                last = min(len(chars), math.floor((height - col_y) / char_height) + 1)
                for i in range(first, last):
                    y = col_y + i * char_height
                    slot = slots.get(chars[i])
                    if slot is None:  # not registered (message chars are added when injected)
                        continue
                    sx, sy = slot
                    csx, csy = sx + ci, sy + ci
                    iy = int(y)
                    steps_behind = head_index - i
                    if steps_behind < 0:
                        steps_behind += L
                    under_cursor = in_cursor_col and iy - char_height <= cy <= iy
                    if steps_behind > 6 and not under_cursor:
                        # Trail (the bulk of the glyphs): kept to the bare minimum of work per character
                        fade = 1 - min(1, (steps_behind - 6) * trail_rate)
                        if y > fade_start:
                            fade *= max(0.0, (height - y) / bottom_fade_zone)
                        alpha = int(160 * fade)
                        trail_opacity = (alpha if alpha > 60 else 60) / 255.0
                        if trail_opacity != opacity:
                            set_opacity(trail_opacity)
                            opacity = trail_opacity
                        draw(cx_col, iy - top + ci, trail, csx, csy, ccw, cch)
                        continue
                    opacity = None  # the head/near tiers below set their own
                    dy = iy - top
                    cdy = dy + ci
                    bottom_fade = max(0.0, (height - y) / bottom_fade_zone) if y > fade_start else 1.0
                    # Mouse highlight: character under cursor drawn solid white
                    if under_cursor:
                        set_opacity(1.0)
                        draw(cx_col, cdy, head_core, csx, csy, ccw, cch)
                        continue
                    if steps_behind == 0:
                        # White shine here (moves down the column over time)
                        set_opacity(bottom_fade)
                        draw(sx_col, dy, head_glow, sx, sy, cw, chh)
                        set_opacity(int(255 * bottom_fade) / 255.0)
                        draw(cx_col, cdy, head_core, csx, csy, ccw, cch)
                    elif steps_behind <= 2:
                        set_opacity(int(255 * bottom_fade) / 255.0)
                        draw(sx_col, dy, head2, sx, sy, cw, chh)
                    else:
                        eff = (steps_behind - 2) / persistence  # Slower fade for high-persistence columns
                        alpha = int(220 * (1 - min(1, eff / 5)) * bottom_fade)
                        set_opacity(1.0)
                        draw(sx_col, dy, near_glow, sx, sy, cw, chh)
                        set_opacity(max(alpha, 80) / 255.0)
                        draw(cx_col, cdy, near, csx, csy, ccw, cch)
        except Exception:
            pass
    
    def update_animation(self):
        """Update animation frame"""
        try:
            # When screensaver is on, check every frame for activity so we dismiss immediately
            if getattr(self, "_screensaver_active", False) and sys.platform == "win32":
                try:
                    if get_idle_time_ms() < 2500:
                        self._dismiss_screensaver()
                        self._screensaver_dismiss_timer.stop()
                except Exception:
                    pass
            # Animation steps since the last frame, from the clock, so motion does not depend on the frame rate
            # (capped so a stall does not make the rain jump)
            now = time.perf_counter()
            last = getattr(self, "_last_tick", None)
            self._last_tick = now
            steps = 1.0 if last is None else min(5.0, (now - last) * ANIMATION_STEPS_PER_SEC)
            height = self.height()
            columns = getattr(self, "columns", [])
            for col in columns:
                col.update(height, steps)
            affirm_cfg = self.config.get("affirmations")
            if isinstance(affirm_cfg, dict) and affirm_cfg.get("enabled"):
                atlas, (cell_w, cell_h) = self._affirmation_sprites(affirm_cfg)
                url = affirm_cfg.get("source_url")
                self.affirm_feed.poll(url)
                messages = (self.affirm_feed.messages if url else None) or affirm_cfg["messages"]
                started = self.affirm.update(steps / ANIMATION_STEPS_PER_SEC, affirm_cfg,
                                             self.width(), height, cell_w, cell_h, messages)
                if started is not None:
                    atlas.add_chars(started.text)
            else:
                self.affirm.current = None
            # Hue cycle angle is derived from the wall clock in _effective_hue_degrees (no per-frame state)
            messages = self.config.get("custom_messages") or []
            if messages:
                self._message_inject_counter = getattr(self, "_message_inject_counter", 0) + steps
                interval = getattr(self, "_message_inject_interval", 30)
                if self._message_inject_counter >= interval:
                    self._message_inject_counter = 0
                    eligibles = [c for c in columns if not getattr(c, "is_message", False)]
                    if eligibles:
                        col = random.choice(eligibles)
                        msg = random.choice(messages)
                        if str(msg).strip():
                            self.atlas.add_chars(msg.strip())
                            col.set_message(msg.strip())
            if self._solid_saver.isVisible():
                self._solid_saver.update()
            else:
                self.update()
        except Exception:
            pass
    
    def _check_screensaver_idle(self):
        """If screensaver enabled: show when idle long enough; hide when activity detected."""
        try:
            idle_ms = get_idle_time_ms()
        except Exception:
            idle_ms = 0
        # When screensaver is showing, any recent activity (low idle) should stop it
        if getattr(self, "_screensaver_active", False):
            if sys.platform == "win32" and idle_ms < 2500:  # Activity in last 2.5 sec
                self._dismiss_screensaver()
            return
        cfg = self.config.get("screensaver") or {}
        if not cfg.get("enabled"):
            return
        if self.isVisible():
            return
        idle_seconds = max(5, min(7200, _safe_int(cfg.get("idle_seconds"), 60)))
        threshold_ms = idle_seconds * 1000
        if sys.platform != "win32" and idle_ms == 0:
            return
        if idle_ms >= threshold_ms:
            self._screensaver_active = True
            self._screensaver_cursor_start = QCursor.pos()
            self._screensaver_dismiss_timer.start()
            # Global hooks: any key or mouse activity anywhere will dismiss
            _install_screensaver_keyboard_hook(self)
            _install_screensaver_mouse_hook(self)
            self._sync_geometry_to_screen()
            # Black background needs no see-through desktop, so use the cheaper opaque window
            if (cfg.get("black_background") and self._try_gpu_saver
                    and not isinstance(self._solid_saver, GLScreensaverWindow)):
                self._try_gpu_saver = False  # decide once per run
                if gl_screensaver_supported():
                    self._solid_saver.retired = True
                    self._solid_saver = GLScreensaverWindow(self)
            view = self._solid_saver if cfg.get("black_background") else self
            if view is self._solid_saver:
                view.setGeometry(self.geometry())
                self._start_animation(precise=isinstance(view, GLScreensaverWindow))
            view.showFullScreen()
            view.raise_()
            view.activateWindow()

    def _use_cpu_screensaver(self):
        """GPU window failed to initialise: swap in the CPU window, keeping the screensaver up if it is."""
        old = self._solid_saver
        self._solid_saver = SolidScreensaverWindow(self)
        if old.isVisible():
            self._solid_saver.setGeometry(self.geometry())
            self._start_animation()  # back to the default timer: CPU frames are too costly for full fps
            self._solid_saver.showFullScreen()
            self._solid_saver.raise_()
            self._solid_saver.activateWindow()
        old.retired = True
        old.hide()

    def _start_animation(self, precise=False):
        """(Re)start the frame timer. The default timer only ticks ~21 times a second on Windows at the
        configured 33 ms; the precise one reaches the configured fps but is only worth it when frames
        are cheap (GPU screensaver). Motion is time-based, so both look the same apart from smoothness."""
        self._last_tick = None
        self.affirm.reset()
        self.timer.setTimerType(Qt.PreciseTimer if precise else Qt.CoarseTimer)
        self.timer.start(self._animation_interval)

    def _check_screensaver_dismiss(self):
        """When screensaver is on, detect activity via idle time and stop displaying."""
        if not getattr(self, "_screensaver_active", False):
            self._screensaver_dismiss_timer.stop()
            return
        try:
            idle_ms = get_idle_time_ms()
        except Exception:
            return
        if sys.platform == "win32" and idle_ms < 2500:
            self._dismiss_screensaver()
            self._screensaver_dismiss_timer.stop()

    def _dismiss_screensaver(self):
        """Hide window and clear screensaver state on user input."""
        if getattr(self, "_screensaver_active", False):
            self._screensaver_active = False
            self._screensaver_dismiss_timer.stop()
            _uninstall_screensaver_keyboard_hook()
            _uninstall_screensaver_mouse_hook()
            self._solid_saver.hide()
            self.hide()
            self.timer.stop()  # hideEvent does not fire if only the solid window was showing
            self._trim_atlases()

    def mousePressEvent(self, event):
        if getattr(self, "_screensaver_active", False):
            self._dismiss_screensaver()
            event.accept()
            return
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if getattr(self, "_screensaver_active", False):
            # Windows posts a WM_MOUSEMOVE when a window appears under the cursor; only a real move counts
            start = getattr(self, "_screensaver_cursor_start", None)
            if start is None or (event.globalPos() - start).manhattanLength() >= 3:
                self._dismiss_screensaver()
            event.accept()
            return
        if self.config.get("mouse_highlight", False):
            self.update()  # Repaint so highlight follows cursor
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self.drag_position)
            event.accept()

    def keyPressEvent(self, event):
        if getattr(self, "_screensaver_active", False):
            self._dismiss_screensaver()
            event.accept()
            return
        if event.key() == Qt.Key_Escape:
            self.hide()  # Minimize to tray
        elif event.key() == Qt.Key_F11:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
                self.init_matrix()

    def resizeEvent(self, event):
        """Rebuild columns when the window size changes (screen resolution / monitor changes)."""
        super().resizeEvent(event)
        if event.oldSize() != event.size():
            self.init_matrix()

    def _on_screen_changed(self):
        """Primary screen changed or resized: re-sync geometry; also re-listen on the new screen object."""
        try:
            screen = QApplication.primaryScreen()
            if screen is not None:
                try:
                    screen.geometryChanged.disconnect()
                except TypeError:
                    pass
                screen.geometryChanged.connect(lambda *_: self._on_screen_changed())
        except Exception:
            pass
        if self.isVisible():
            self._sync_geometry_to_screen()
            if self.isFullScreen():
                self.showFullScreen()
        elif self._solid_saver.isVisible():
            self._sync_geometry_to_screen()
            self._solid_saver.setGeometry(self.geometry())
            self._solid_saver.showFullScreen()

    def _sync_geometry_to_screen(self):
        """Match the primary screen; the screen can change size while we are hidden in the tray."""
        try:
            screen = QApplication.primaryScreen()
            if screen is not None and self.geometry() != screen.geometry():
                self.setGeometry(screen.geometry())
                if not self.isVisible():
                    self.init_matrix()  # resizeEvent is not delivered while hidden
        except Exception:
            pass

    def showEvent(self, event):
        """Start animation when window is shown."""
        super().showEvent(event)
        if not self.timer.isActive():
            self._start_animation()

    def hideEvent(self, event):
        """Stop animation when hidden to save CPU and keep idle-check timer responsive.
        Windows minimizes a fullscreen window when another app takes focus; if that happens while the
        screensaver is active, clear its state so it is not left 'active' but frozen."""
        super().hideEvent(event)
        self.timer.stop()
        self._trim_atlases()  # derived sprite images are rebuilt on the next frame drawn
        if getattr(self, "_screensaver_active", False):
            self._dismiss_screensaver()

    def _trim_atlases(self):
        self.atlas.trim()
        if self._affirm_atlas is not None:
            self._affirm_atlas[1].trim()

    def closeEvent(self, event):
        """Hide to system tray instead of quitting."""
        event.ignore()
        self.hide()

    def reload_messages(self):
        """Reload config so custom_messages are up to date."""
        self.config = load_config()

    def apply_speed_to_columns(self):
        """Apply current config speed (min/max) to all columns."""
        speed_min = self.config.get("speed", {}).get("min", 2.0)
        speed_max = self.config.get("speed", {}).get("max", 5.0)
        for col in self.columns:
            col.speed_min = speed_min
            col.speed_max = speed_max
            col.speed = random.uniform(speed_min, speed_max)

    def create_tray_icon(self):
        """Create system tray icon with menu."""
        base_dir = _base_dir()
        tray_path = os.path.join(base_dir, "store", "icons", "tray_16.png")
        if os.path.exists(tray_path):
            pix = QPixmap(tray_path)
        else:
            pix = QPixmap(16, 16)
            pix.fill(Qt.transparent)
            painter = QPainter(pix)
            painter.setPen(QColor(0, 255, 0))
            painter.setBrush(QColor(0, 180, 0))
            painter.drawRect(2, 2, 12, 12)
            painter.end()
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon(pix))
        self.tray_icon.setToolTip("Matrix Screensaver")
        menu = QMenu()
        show_action = QAction("Show", self)
        show_action.triggered.connect(self._show_on_screen)
        menu.addAction(show_action)
        hide_action = QAction("Hide", self)
        hide_action.triggered.connect(self.hide)
        menu.addAction(hide_action)
        menu.addSeparator()
        add_msg_action = QAction("Add message...", self)
        add_msg_action.triggered.connect(self.add_custom_message)
        menu.addAction(add_msg_action)
        manage_msg_action = QAction("Manage messages...", self)
        manage_msg_action.triggered.connect(self.manage_custom_messages)
        menu.addAction(manage_msg_action)
        menu.addSeparator()
        # Speed submenu
        speed_menu = QMenu("Speed", self)
        for label, (smin, smax) in [("Slower", (1.0, 2.5)), ("Normal", (2.0, 5.0)), ("Faster", (4.0, 9.0))]:
            act = QAction(label, self)
            act.triggered.connect(lambda checked, a=smin, b=smax: self.set_speed(a, b))
            speed_menu.addAction(act)
        custom_speed = QAction("Custom...", self)
        custom_speed.triggered.connect(self.show_speed_dialog)
        speed_menu.addAction(custom_speed)
        menu.addMenu(speed_menu)
        glow_action = QAction("Glow...", self)
        glow_action.triggered.connect(self.show_glow_dialog)
        menu.addAction(glow_action)
        hue_action = QAction("Hue...", self)
        hue_action.triggered.connect(self.show_hue_dialog)
        menu.addAction(hue_action)
        screensaver_action = QAction("Screensaver...", self)
        screensaver_action.triggered.connect(self.show_screensaver_dialog)
        menu.addAction(screensaver_action)
        self.mouse_highlight_action = QAction("Mouse highlight", self)
        self.mouse_highlight_action.setCheckable(True)
        self.mouse_highlight_action.setChecked(bool(self.config.get("mouse_highlight", False)))
        self.mouse_highlight_action.triggered.connect(self.toggle_mouse_highlight)
        menu.addAction(self.mouse_highlight_action)
        self.affirmations_action = QAction("Affirmations", self)
        self.affirmations_action.setCheckable(True)
        self.affirmations_action.setChecked(bool((self.config.get("affirmations") or {}).get("enabled")))
        self.affirmations_action.triggered.connect(self.toggle_affirmations)
        menu.addAction(self.affirmations_action)
        self.startup_action = QAction("Start with Windows", self)
        self.startup_action.setCheckable(True)
        self.startup_action.setChecked(is_startup_enabled())
        self.startup_action.setEnabled(sys.platform == "win32")
        self.startup_action.triggered.connect(self.toggle_startup)
        menu.addAction(self.startup_action)
        menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit_app)
        menu.addAction(quit_action)
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()
        return self.tray_icon

    def _show_on_screen(self):
        self._sync_geometry_to_screen()
        self.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            if self.isVisible():
                self.hide()
            else:
                self._show_on_screen()

    def add_custom_message(self):
        text, ok = QInputDialog.getText(self, "Add message", "Message to show in the rain:")
        if ok and text and str(text).strip():
            messages = list(self.config.get("custom_messages") or [])
            messages.append(str(text).strip())
            save_custom_messages(messages)
            self.reload_messages()

    def manage_custom_messages(self):
        dlg = ManageMessagesDialog(self.config.get("custom_messages") or [], self)
        if dlg.exec_() == QDialog.Accepted:
            save_custom_messages(dlg.get_messages())
            self.reload_messages()

    def set_speed(self, speed_min, speed_max):
        """Set rain speed and apply to columns."""
        if speed_min > speed_max:
            speed_min, speed_max = speed_max, speed_min
        self.config = save_speed(speed_min, speed_max)
        self.apply_speed_to_columns()

    def show_speed_dialog(self):
        """Show custom speed min/max dialog."""
        smin = self.config.get("speed", {}).get("min", 2.0)
        smax = self.config.get("speed", {}).get("max", 5.0)
        dlg = SpeedDialog(smin, smax, self)
        if dlg.exec_() == QDialog.Accepted:
            mn, mx = dlg.get_speed()
            self.set_speed(mn, mx)

    def show_glow_dialog(self):
        """Show glow strength/radius dialog."""
        glow = self.config.get("glow") or {}
        strength = max(0, min(100, _safe_int(glow.get("strength"), 90)))
        radius = max(1, min(3, _safe_int(glow.get("radius"), 3)))
        dlg = GlowDialog(strength, radius, self)
        if dlg.exec_() == QDialog.Accepted:
            s, r = dlg.get_glow()
            self.config = save_glow(s, r)

    def show_hue_dialog(self):
        """Show hue shift and cycle dialog."""
        cfg = self.config.get("hue") or {}
        hue_shift = max(0, min(360, _safe_int(cfg.get("shift"), 0)))
        cycle = bool(cfg.get("cycle", False))
        dlg = HueDialog(hue_shift, cycle, self)
        if dlg.exec_() == QDialog.Accepted:
            shift, cycle_enabled = dlg.get_values()
            self.config = save_hue(shift, cycle_enabled)
            self.update()

    def toggle_mouse_highlight(self):
        """Toggle mouse highlight and save; update tracking and menu."""
        new_val = not self.config.get("mouse_highlight", False)
        self.config = save_mouse_highlight(new_val)
        self.setMouseTracking(new_val)
        if hasattr(self, "mouse_highlight_action"):
            self.mouse_highlight_action.setChecked(new_val)
        self.update()

    def toggle_affirmations(self, checked):
        """Turn the centred affirmations on or off and save."""
        self.config = save_affirmations_enabled(checked)
        self.affirm.reset()
        self.affirmations_action.setChecked(bool(self.config["affirmations"]["enabled"]))

    def toggle_startup(self, checked):
        """Register or unregister the app to start with Windows; revert the menu check on failure."""
        if not set_startup_enabled(checked):
            self.startup_action.setChecked(is_startup_enabled())
            QMessageBox.warning(self, "Start with Windows",
                                "Could not update the Windows startup setting.")

    def show_screensaver_dialog(self):
        """Show screensaver enable and idle timeout dialog."""
        cfg = self.config.get("screensaver") or {}
        enabled = bool(cfg.get("enabled", True))
        idle_seconds = max(5, min(7200, _safe_int(cfg.get("idle_seconds"), 60)))
        black_bg = bool(cfg.get("black_background", False))
        dlg = ScreensaverDialog(enabled, idle_seconds, black_bg, self)
        if dlg.exec_() == QDialog.Accepted:
            en, secs, black = dlg.get_values()
            self.config = save_screensaver(en, secs, black)
            self.update()

    def quit_app(self):
        self.tray_icon.hide()
        QApplication.quit()


class SolidScreensaverWindow(QWidget):
    """Opaque fullscreen window for the black-background screensaver.

    The overlay is a per-pixel-alpha window so the desktop shows through, which Windows has to
    composite in full every frame; behind a black background that work buys nothing. Rain state,
    timers and input handling stay on the MatrixRainWidget this window draws for.
    """
    def __init__(self, rain):
        super().__init__()
        self.rain = rain
        self.retired = False  # set when replaced, so hiding it does not end the screensaver
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_OpaquePaintEvent)  # paintEvent covers every pixel
        self.setMouseTracking(True)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.black)
        self.rain.paint_rain(painter)
        self.rain.paint_affirmation(painter)

    def mousePressEvent(self, event):
        self.rain.mousePressEvent(event)

    def mouseMoveEvent(self, event):
        self.rain.mouseMoveEvent(event)

    def keyPressEvent(self, event):
        self.rain.keyPressEvent(event)

    def hideEvent(self, event):
        """Hidden externally (e.g. Windows minimised it when another app took focus): end the screensaver."""
        super().hideEvent(event)
        if not self.retired:
            self.rain._dismiss_screensaver()


GL_RAIN_VERTEX_SHADER = """#version 410 core
void main() {
    // One triangle that covers the whole screen
    vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
    gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
}
"""

# Same tiers, fades and draw order as MatrixRainWidget.paint_rain, evaluated per pixel: every glyph
# sprite covering the pixel is composited (premultiplied "over"), columns left to right, rows top to
# bottom, glow before core. The masks are GlyphAtlas images; colours come in already hue-shifted.
GL_RAIN_FRAGMENT_SHADER = """#version 410 core
uniform sampler2D uCore, uGlowHead, uHead2, uGlowNear;  // white glyph masks (alpha), atlas layout
uniform sampler2D uCols;   // per column: y, head index, length, trail persistence
uniform sampler2D uChars;  // [row, column]: atlas cell (x, y) of the glyph; x < 0 = none
uniform int uNumCols, uColSpacing, uCharHeight, uCharWidth, uCellW, uCellH, uPad, uTop, uHighlight;
uniform float uHeight, uFadeZone, uDpr, uFbHeight;
uniform vec2 uCursor;
uniform vec3 uHeadGlowRgb, uHead2Rgb, uNearRgb, uTrailRgb;
out vec4 fragColor;

vec4 acc;
void over(vec3 rgb, float a) { acc = vec4(rgb * a, a) + acc * (1.0 - a); }

void main() {
    ivec2 p = ivec2(floor(vec2(gl_FragCoord.x, uFbHeight - gl_FragCoord.y) / uDpr));
    acc = vec4(0.0);
    float ch = float(uCharHeight);
    float fadeStart = uHeight - uFadeZone;
    // Columns whose sprites (x - pad .. x - pad + cell width) cover this pixel
    int c0 = max(0, int(ceil(float(p.x + uPad - uCellW + 1) / float(uColSpacing))));
    int c1 = min(uNumCols - 1, int(floor(float(p.x + uPad) / float(uColSpacing))));
    for (int c = c0; c <= c1; ++c) {
        vec4 col = texelFetch(uCols, ivec2(c, 0), 0);
        int len = int(col.z);
        int head = int(col.y);
        float persistence = col.w;
        int colX = c * uColSpacing;
        int lx = p.x - (colX - uPad);
        // Rows whose sprites (baseline - top .. + cell height) may cover this pixel
        int r0 = max(0, int(floor((float(p.y + uTop - uCellH) - col.x) / ch)));
        int r1 = min(len - 1, int(floor((float(p.y + uTop) - col.x) / ch)) + 1);
        for (int r = r0; r <= r1; ++r) {
            float y = col.x + float(r) * ch;
            if (y < -ch || y > uHeight) continue;
            int iy = int(y);
            int ly = p.y - (iy - uTop);
            if (ly < 0 || ly >= uCellH) continue;
            vec2 cell = texelFetch(uChars, ivec2(r, c), 0).xy;
            if (cell.x < 0.0) continue;
            ivec2 t = ivec2(cell) + ivec2(lx, ly);
            float core = texelFetch(uCore, t, 0).a;
            float fade = y > fadeStart ? max(0.0, (uHeight - y) / uFadeZone) : 1.0;
            if (uHighlight != 0 && float(colX) <= uCursor.x && uCursor.x < float(colX + uCharWidth)
                    && float(iy - uCharHeight) <= uCursor.y && uCursor.y <= float(iy)) {
                over(vec3(1.0), core);  // mouse highlight: solid white, no glow
                continue;
            }
            int s = head - r;
            if (s < 0) s += len;
            if (s == 0) {
                over(uHeadGlowRgb, texelFetch(uGlowHead, t, 0).a * fade);
                over(vec3(1.0), core * floor(255.0 * fade) / 255.0);
            } else if (s <= 2) {
                over(uHead2Rgb, texelFetch(uHead2, t, 0).a * floor(255.0 * fade) / 255.0);
            } else if (s <= 6) {
                float a = floor(220.0 * (1.0 - min(1.0, float(s - 2) / persistence / 5.0)) * fade);
                over(uNearRgb, texelFetch(uGlowNear, t, 0).a);
                over(uNearRgb, core * max(a, 80.0) / 255.0);
            } else {
                float a = floor(160.0 * (1.0 - min(1.0, float(s - 6) / (persistence * float(max(len - 6, 1))))) * fade);
                over(uTrailRgb, core * max(a, 60.0) / 255.0);
            }
        }
    }
    fragColor = vec4(acc.rgb, 1.0);  // over the black background
}
"""

_GL_TEXTURE_2D, _GL_TRIANGLES, _GL_COLOR_BUFFER_BIT, _GL_TEXTURE0 = 0x0DE1, 0x0004, 0x4000, 0x84C0


def gl_surface_format():
    """OpenGL 4.1 core: what GLRainRenderer's shaders and PyQt5's function bindings need."""
    fmt = QSurfaceFormat()
    fmt.setVersion(4, 1)
    fmt.setProfile(QSurfaceFormat.CoreProfile)
    return fmt


class GLRainRenderer:
    """Draws the rain on the GPU. Per frame the CPU only uploads each column's position and any
    changed characters (a few KB); the fragment shader does the per-glyph tiers, fades and blending
    that cost tens of thousands of QPainter calls per frame on a large screen."""

    def __init__(self):
        self.ready = False

    def initialize(self, context):
        """Set up GL objects in the current context; raises RuntimeError if anything is unsupported."""
        gl = context.versionFunctions(QOpenGLVersionProfile(context.format()))
        if gl is None or not gl.initializeOpenGLFunctions():
            raise RuntimeError("OpenGL 4.1 functions unavailable")
        self.gl = gl
        self.program = QOpenGLShaderProgram()
        if not (self.program.addShaderFromSourceCode(QOpenGLShader.Vertex, GL_RAIN_VERTEX_SHADER)
                and self.program.addShaderFromSourceCode(QOpenGLShader.Fragment, GL_RAIN_FRAGMENT_SHADER)
                and self.program.link()):
            raise RuntimeError("shader build failed: " + self.program.log())
        self.vao = QOpenGLVertexArrayObject()  # core profile cannot draw without one bound
        if not self.vao.create():
            raise RuntimeError("vertex array object unavailable")
        self._loc = {}
        self._masks = None
        self._mask_textures = []
        self._cols_tex = self._chars_tex = None
        self._shape = None
        self.ready = True

    def _uniform(self, name):
        loc = self._loc.get(name)
        if loc is None:
            loc = self._loc[name] = self.program.uniformLocation(name)
        return loc

    @staticmethod
    def _float_texture(fmt, width, height):
        tex = QOpenGLTexture(QOpenGLTexture.Target2D)
        tex.setFormat(fmt)
        tex.setSize(width, height)
        tex.setMipLevels(1)
        tex.allocateStorage()
        tex.setMinMagFilters(QOpenGLTexture.Nearest, QOpenGLTexture.Nearest)
        return tex

    def _sync_masks(self, masks):
        """Upload the atlas masks when they were rebuilt (glow settings, new message glyphs, trim)."""
        if masks is self._masks:
            return False
        for tex in self._mask_textures:
            tex.destroy()
        self._mask_textures = []
        for name in ("core", "glow130", "t2", "glow40"):
            tex = QOpenGLTexture(masks[name], QOpenGLTexture.DontGenerateMipMaps)
            tex.setMinMagFilters(QOpenGLTexture.Nearest, QOpenGLTexture.Nearest)
            self._mask_textures.append(tex)
        self._masks = masks
        return True

    def _sync_columns(self, columns, slots, remap):
        """Upload column positions every frame; re-encode characters only where they changed."""
        n = max(1, len(columns))
        width = max([len(c.chars) for c in columns] + [1])
        if self._shape is None or self._shape[0] != n or self._shape[1] < width:
            for tex in (self._cols_tex, self._chars_tex):
                if tex is not None:
                    tex.destroy()
            width = (width + 63) // 64 * 64  # headroom so longer messages rarely force a resize
            self._shape = (n, width)
            self._cols_tex = self._float_texture(QOpenGLTexture.RGBA32F, n, 1)
            self._chars_tex = self._float_texture(QOpenGLTexture.RG32F, width, n)
            self._chars = array("f", [-1.0]) * (2 * width * n)
            self._encoded = [None] * n
            remap = True
        width = self._shape[1]
        params = array("f")
        chars_dirty = False
        for c, col in enumerate(columns):
            L = max(col.length, 1)
            try:
                head = int(col.head_offset) % L
            except (TypeError, ValueError):
                head = 0
            params.extend((col.y, head, col.length if col.chars else 0, max(0.3, col.trail_persistence)))
            done = self._encoded[c]
            version = col.chars_version
            if not remap and done is not None and done[0] is col and done[1] == version:
                continue
            base = 2 * width * c
            flicker = col.last_flicker
            if (not remap and done is not None and done[0] is col and done[1] == version - 1
                    and flicker is not None and flicker[0] == version):
                rows = (flicker[1],)  # only one character changed since the last upload
            else:
                self._chars[base:base + 2 * width] = array("f", [-1.0]) * (2 * width)
                rows = range(min(len(col.chars), width))
            for r in rows:
                slot = slots.get(col.chars[r])
                self._chars[base + 2 * r:base + 2 * r + 2] = array("f", slot[:2] if slot else (-1.0, -1.0))
            self._encoded[c] = (col, version)
            chars_dirty = True
        self._cols_tex.setData(QOpenGLTexture.RGBA, QOpenGLTexture.Float32, sip.voidptr(params.buffer_info()[0]))
        if chars_dirty:
            self._chars_tex.setData(QOpenGLTexture.RG, QOpenGLTexture.Float32,
                                    sip.voidptr(self._chars.buffer_info()[0]))

    def render(self, rain, fb_width, fb_height, dpr=1.0):
        """Draw one frame of rain's columns into the bound framebuffer (black background)."""
        gl = self.gl
        atlas = rain.atlas
        strength, radius = rain.glow_settings()
        remap = self._sync_masks(atlas.masks(strength, radius))  # new atlas layout moves every glyph
        columns = getattr(rain, "columns", [])
        self._sync_columns(columns, atlas.slots, remap)

        height = rain.height()
        hue = int(rain._effective_hue_degrees()) % 360
        cursor = rain.mapFromGlobal(QCursor.pos()) if rain.config.get("mouse_highlight", False) else None
        gl.glViewport(0, 0, fb_width, fb_height)
        gl.glClearColor(0.0, 0.0, 0.0, 1.0)
        gl.glClear(_GL_COLOR_BUFFER_BIT)
        self.program.bind()
        self.vao.bind()
        u = self._uniform
        for unit, (name, tex) in enumerate(zip(("uCore", "uGlowHead", "uHead2", "uGlowNear"), self._mask_textures)):
            tex.bind(unit)
            gl.glUniform1i(u(name), unit)
        self._cols_tex.bind(4)
        gl.glUniform1i(u("uCols"), 4)
        self._chars_tex.bind(5)
        gl.glUniform1i(u("uChars"), 5)
        for name, value in (("uNumCols", len(columns)), ("uColSpacing", rain.col_spacing),
                            ("uCharHeight", rain.char_height), ("uCharWidth", rain.char_width),
                            ("uCellW", atlas.cell_w), ("uCellH", atlas.cell_h), ("uPad", atlas.PAD),
                            ("uTop", atlas.ascent + atlas.PAD), ("uHighlight", int(cursor is not None))):
            gl.glUniform1i(u(name), value)
        for name, value in (("uHeight", float(height)), ("uFadeZone", float(max(60, height // 8))),
                            ("uDpr", float(dpr)), ("uFbHeight", float(fb_height))):
            gl.glUniform1f(u(name), value)
        gl.glUniform2f(u("uCursor"), *((float(cursor.x()), float(cursor.y())) if cursor is not None else (-1e9, -1e9)))
        for name, tier in (("uHeadGlowRgb", "head_glow"), ("uHead2Rgb", "head2"), ("uNearRgb", "near"),
                           ("uTrailRgb", "trail")):
            r, g, b = hue_shift_rgb(atlas.TIERS[tier][1], hue)
            gl.glUniform3f(u(name), r / 255.0, g / 255.0, b / 255.0)
        gl.glDrawArrays(_GL_TRIANGLES, 0, 3)
        self.vao.release()
        self.program.release()
        # Leave texture units as QPainter expects them (it draws the affirmation on top, using unit 0)
        for unit, tex in enumerate(self._mask_textures + [self._cols_tex, self._chars_tex]):
            tex.release(unit)
        gl.glActiveTexture(_GL_TEXTURE0)


_gl_support = None


def gl_screensaver_supported():
    """True if this machine can run GLRainRenderer (checked once, off screen)."""
    global _gl_support
    if _gl_support is None:
        _gl_support = False
        try:
            ctx = QOpenGLContext()
            ctx.setFormat(gl_surface_format())
            surface = QOffscreenSurface()
            surface.setFormat(gl_surface_format())
            surface.create()
            if ctx.create() and not ctx.isOpenGLES() and (ctx.format().majorVersion(), ctx.format().minorVersion()) >= (4, 1) \
                    and ctx.makeCurrent(surface):
                GLRainRenderer().initialize(ctx)
                ctx.doneCurrent()
                _gl_support = True
        except Exception as e:
            print(f"GPU screensaver unavailable ({e}); using the CPU renderer.")
    return _gl_support


class GLScreensaverWindow(QOpenGLWindow):
    """Fullscreen black-background screensaver drawn by GLRainRenderer (input handling stays on the
    MatrixRainWidget, as with SolidScreensaverWindow). If GL setup fails at runtime it hands over
    to the CPU window."""

    def __init__(self, rain):
        super().__init__()
        self.rain = rain
        self.retired = False
        self.setFormat(gl_surface_format())
        self.setFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.renderer = GLRainRenderer()

    def activateWindow(self):
        self.requestActivate()

    def initializeGL(self):
        try:
            self.renderer.initialize(self.context())
        except Exception as e:
            print(f"GPU screensaver failed ({e}); switching to the CPU renderer.")
            QTimer.singleShot(0, self.rain._use_cpu_screensaver)

    def paintGL(self):
        if self.renderer.ready:
            dpr = self.devicePixelRatio()
            self.renderer.render(self.rain, round(self.width() * dpr), round(self.height() * dpr), dpr)
            if self.rain.affirm.current is not None:
                # A handful of sprites: QPainter's GL engine draws them over the shader's rain
                painter = QPainter(self)
                self.rain.paint_affirmation(painter)
                painter.end()

    def mousePressEvent(self, event):
        self.rain.mousePressEvent(event)

    def mouseMoveEvent(self, event):
        self.rain.mouseMoveEvent(event)

    def keyPressEvent(self, event):
        self.rain.keyPressEvent(event)

    def hideEvent(self, event):
        """Hidden externally (e.g. Windows minimised it when another app took focus): end the screensaver."""
        super().hideEvent(event)
        if not self.retired:
            self.rain._dismiss_screensaver()


class ManageMessagesDialog(QDialog):
    """Dialog to add/remove custom messages."""
    def __init__(self, messages, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage messages")
        self.messages = list(messages)
        layout = QVBoxLayout(self)
        self.list_widget = QListWidget()
        for m in self.messages:
            self.list_widget.addItem(QListWidgetItem(m))
        layout.addWidget(self.list_widget)
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("Add...")
        add_btn.clicked.connect(self._add)
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self._remove)
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(remove_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        layout.addWidget(QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, accepted=self.accept, rejected=self.reject))

    def _add(self):
        text, ok = QInputDialog.getText(self, "Add message", "Message:")
        if ok and text and str(text).strip():
            self.messages.append(str(text).strip())
            self.list_widget.addItem(QListWidgetItem(str(text).strip()))

    def _remove(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            self.list_widget.takeItem(row)
            self.messages.pop(row)

    def get_messages(self):
        return [self.list_widget.item(i).text() for i in range(self.list_widget.count())]


class SpeedDialog(QDialog):
    """Dialog to set min/max fall speed."""
    def __init__(self, speed_min, speed_max, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Speed")
        layout = QFormLayout(self)
        self.spin_min = QDoubleSpinBox()
        self.spin_min.setRange(0.2, 20.0)
        self.spin_min.setSingleStep(0.5)
        self.spin_min.setValue(float(speed_min))
        self.spin_min.setDecimals(1)
        layout.addRow("Min speed:", self.spin_min)
        self.spin_max = QDoubleSpinBox()
        self.spin_max.setRange(0.5, 25.0)
        self.spin_max.setSingleStep(0.5)
        self.spin_max.setValue(float(speed_max))
        self.spin_max.setDecimals(1)
        layout.addRow("Max speed:", self.spin_max)
        layout.addRow(QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, accepted=self.accept, rejected=self.reject))

    def get_speed(self):
        return self.spin_min.value(), self.spin_max.value()


class GlowDialog(QDialog):
    """Dialog to set glow strength and radius."""
    def __init__(self, strength, radius, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Glow")
        layout = QFormLayout(self)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(int(strength))
        self.slider.setTickPosition(QSlider.TicksBelow)
        self.slider.setTickInterval(25)
        self.slider_label = QLabel(f"{int(strength)}%")
        self.slider.valueChanged.connect(lambda v: self.slider_label.setText(f"{v}%"))
        layout.addRow("Strength:", self.slider)
        layout.addRow("", self.slider_label)
        self.radius_spin = QDoubleSpinBox()
        self.radius_spin.setRange(1, 3)
        self.radius_spin.setValue(max(1, min(3, _safe_int(radius, 3))))
        self.radius_spin.setDecimals(0)
        self.radius_spin.setSuffix(" px")
        layout.addRow("Radius:", self.radius_spin)
        layout.addRow(QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, accepted=self.accept, rejected=self.reject))

    def get_glow(self):
        return self.slider.value(), int(self.radius_spin.value())


class HueDialog(QDialog):
    """Dialog to set hue shift (0-360) and optional cycle through hues."""
    def __init__(self, hue_shift, cycle, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Hue")
        layout = QFormLayout(self)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 360)
        self.slider.setValue(max(0, min(360, int(hue_shift))))
        self.slider.setTickPosition(QSlider.TicksBelow)
        self.slider.setTickInterval(60)
        self.slider_label = QLabel(f"{int(hue_shift)}° (0=green, 120=cyan, 240=blue)")
        self.slider.valueChanged.connect(lambda v: self.slider_label.setText(f"{v}° (0=green, 120=cyan, 240=blue)"))
        layout.addRow("Hue:", self.slider)
        layout.addRow("", self.slider_label)
        self.cycle_check = QCheckBox("Cycle through all hues")
        self.cycle_check.setChecked(bool(cycle))
        layout.addRow("", self.cycle_check)
        layout.addRow(QLabel("When cycling, the rain color animates through the spectrum over time.\n"
                             "Synced to the PC clock, so every machine shows the same color at the same moment."))
        layout.addRow(QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, accepted=self.accept, rejected=self.reject))

    def get_values(self):
        return self.slider.value(), self.cycle_check.isChecked()


class ScreensaverDialog(QDialog):
    """Dialog to enable screensaver and set idle timeout (in seconds)."""
    def __init__(self, enabled, idle_seconds, black_background=False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Screensaver")
        layout = QFormLayout(self)
        self.enabled_check = QCheckBox("Use Matrix Screensaver as screensaver")
        self.enabled_check.setChecked(bool(enabled))
        layout.addRow("", self.enabled_check)
        self.idle_spin = QDoubleSpinBox()
        self.idle_spin.setRange(5, 7200)  # 5 sec to 2 hours
        self.idle_spin.setValue(max(5, min(7200, int(idle_seconds))))
        self.idle_spin.setDecimals(0)
        self.idle_spin.setSuffix(" sec")
        layout.addRow("Turn on after (no mouse/keyboard):", self.idle_spin)
        self.black_bg_check = QCheckBox("Black background (hide the desktop behind the rain)")
        self.black_bg_check.setChecked(bool(black_background))
        layout.addRow("", self.black_bg_check)
        layout.addRow(QLabel("Any key or mouse move dismisses the overlay."))
        layout.addRow(QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, accepted=self.accept, rejected=self.reject))

    def get_values(self):
        return (self.enabled_check.isChecked(), int(self.idle_spin.value()),
                self.black_bg_check.isChecked())


def main():
    """Main entry point"""
    try:
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)  # Keep running when hidden to tray
        refresh_startup_registration()  # Keep the startup entry pointing at this copy of the app
        widget = MatrixRainWidget()
        # If screensaver mode is on, start hidden (tray only); overlay appears after idle timeout
        if not (widget.config.get("screensaver") or {}).get("enabled", False):
            widget.show()
        sys.exit(app.exec_())
    except Exception as e:
        import traceback
        traceback.print_exc()
        try:
            log_path = os.path.join(_base_dir(), "matrix_rain_crash.log")
            with open(log_path, "w", encoding="utf-8") as f:
                traceback.print_exc(file=f)
        except Exception:
            pass
        sys.exit(1)

if __name__ == "__main__":
    main()
