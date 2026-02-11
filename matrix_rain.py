#!/usr/bin/env python3
"""
Matrix Rain Effect - Windowless transparent overlay
Displays falling ASCII characters like in The Matrix with transparent background.
Controllable via system tray; supports custom messages in the rain.
"""

import sys
import random
import string
import json
import os
import ctypes
from ctypes import wintypes
from PyQt5.QtWidgets import (
    QApplication, QWidget, QSystemTrayIcon, QMenu, QAction,
    QInputDialog, QDialog, QVBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QHBoxLayout, QMessageBox, QDialogButtonBox,
    QDoubleSpinBox, QLabel, QFormLayout, QSlider, QCheckBox,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPainter, QColor, QFont, QFontMetrics, QIcon, QPixmap

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

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'matrix_config.json')

def get_idle_time_ms():
    """Return system idle time in milliseconds (mouse/keyboard). Windows only; other OS returns 0."""
    try:
        if sys.platform != "win32":
            return 0
        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]
        lib = ctypes.windll.user32  # type: ignore
        li = LASTINPUTINFO()
        li.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if lib.GetLastInputInfo(ctypes.byref(li)):
            tick = lib.GetTickCount()
            return (tick - li.dwTime) & 0x7FFFFFFF
    except Exception:
        pass
    return 0

def _safe_int(val, default):
    """Return int(val) or default if invalid."""
    try:
        return int(val)
    except (TypeError, ValueError):
        return default

def load_config():
    """Load configuration from JSON file"""
    default_config = {
        "speed": {"min": 4.0, "max": 9.0},
        "animation": {"fps": 30},
        "column": {"min_length": 12, "max_length": 48},
        "font": {"name": "Consolas", "size": 14},
        "custom_messages": [],
        "glow": {"strength": 90, "radius": 3},
        "screensaver": {"enabled": False, "idle_minutes": 1},
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
                config["screensaver"] = {"enabled": False, "idle_minutes": 1}
            for k, default in (("enabled", False), ("idle_minutes", 1)):
                if k not in config["screensaver"]:
                    config["screensaver"][k] = default
                elif k == "idle_minutes":
                    config["screensaver"][k] = max(1, min(120, _safe_int(config["screensaver"][k], 1)))
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

def save_screensaver(enabled, idle_minutes):
    """Save screensaver settings to config."""
    try:
        config = load_config()
        if "screensaver" not in config:
            config["screensaver"] = {}
        config["screensaver"]["enabled"] = bool(enabled)
        config["screensaver"]["idle_minutes"] = max(1, min(120, int(idle_minutes)))
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
        return config
    except Exception as e:
        print(f"Could not save screensaver: {e}")
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
        # Some columns span full screen height (top to bottom) before fading; rest use random length
        full_height_chars = max(length_min, int(window_height / char_height) + random.randint(10, 40))
        if random.random() < 0.45:
            self.length = full_height_chars
        else:
            self.length = random.randint(length_min, min(length_max, full_height_chars))
        self.chars = []
        self.is_message = False
        self.head_offset = 0.0
        self.trail_persistence = random.uniform(0.6, 1.6)
        self.generate_chars()
        self.y = -self.length * self.char_height - random.randint(0, window_height)
    
    def generate_chars(self):
        """Generate random characters for this column (Matrix-style: Latin + Katakana)"""
        self.chars = [random.choice(MATRIX_CHARS) for _ in range(self.length)]
    
    def set_message(self, text):
        """Display a custom message in this column (one char per position). White shine will animate top to bottom."""
        if not text:
            return
        self.chars = list(str(text))
        self.length = len(self.chars)
        self.is_message = True
        self.head_offset = 0.0  # Start white at top of message so it animates down
        self.y = -self.length * self.char_height  # Start above top so message falls in from top
    
    def update(self, window_height):
        """Update column position; advance white shine down the column; flicker trail chars."""
        self.y += self.speed * SPEED_SCALE
        # Advance white shine down through the column (so it "falls" over the letters)
        try:
            self.head_offset = (getattr(self, "head_offset", 0) + self.speed * 0.35 * SPEED_SCALE) % 1e6
        except (TypeError, ValueError):
            self.head_offset = 0
        if self.y + self.length * self.char_height > window_height:
            self.y = -self.length * self.char_height
            self.speed = random.uniform(self.speed_min, self.speed_max)
            self.head_offset = 0.0
            self.trail_persistence = random.uniform(0.6, 1.6)
            if self.is_message:
                self.is_message = False
            # ~45% of columns span full screen (top to bottom) before fading
            full_height_chars = max(self.length_min, int(window_height / self.char_height) + random.randint(10, 40))
            if random.random() < 0.45:
                self.length = full_height_chars
            else:
                self.length = random.randint(self.length_min, min(self.length_max, full_height_chars))
            self.generate_chars()
        elif not self.is_message and random.random() < 0.2:
            # Flicker less often: ~20% of frames, replace only one character per column
            if self.length > 0:
                idx = random.randint(0, self.length - 1)
                self.chars[idx] = random.choice(MATRIX_CHARS)

class MatrixRainWidget(QWidget):
    """Main widget for Matrix rain effect"""
    def __init__(self):
        super().__init__()
        # Load configuration
        self.config = load_config()
        self.init_ui()
        self.init_matrix()
        
        # Timer for animation
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_animation)
        fps = self.config.get("animation", {}).get("fps", 30)
        interval = int(1000 / fps)
        self.timer.start(interval)
        # Screensaver: check idle periodically
        self._screensaver_active = False
        self._idle_check_timer = QTimer()
        self._idle_check_timer.timeout.connect(self._check_screensaver_idle)
        self._idle_check_timer.start(10000)  # Check every 10 seconds
        # System tray (must be after widget is created)
        self.create_tray_icon()
    
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
        
        for i in range(num_columns):
            x = i * col_spacing
            self.columns.append(MatrixColumn(x, height, speed_min, speed_max, length_min, length_max, self.char_height))
        
        self._message_inject_counter = 0
        self._message_inject_interval = max(15, int(1.0 * (self.config.get("animation", {}).get("fps", 30))))  # ~every 1 sec so messages are visible
    
    def _glow_offsets(self):
        """Return list of (dx, dy, alpha_scale) for glow layers from config (radius 1–3 = more glow)."""
        glow_cfg = self.config.get("glow") or {}
        radius = max(1, min(3, _safe_int(glow_cfg.get("radius"), 3)))
        # Rings at 1px, 2px, 3px with decreasing alpha for softer, larger glow
        scale_by_d = {1: 1.0, 2: 0.55, 3: 0.3}
        offsets = []
        for d in (1, 2, 3):
            if d > radius:
                break
            scale = scale_by_d.get(d, 0.3)
            for dx, dy in ((-d,-d),(-d,0),(-d,d),(0,-d),(0,d),(d,-d),(d,0),(d,d)):
                if (dx, dy) == (0, 0):
                    continue
                offsets.append((dx, dy, scale))
        return offsets

    def _draw_char_glow(self, painter, x, y, char, color, base_glow_alpha=70):
        """Draw a character with configurable luminous glow (strength 0 = no glow)."""
        glow_cfg = self.config.get("glow") or {}
        strength = max(0, min(100, _safe_int(glow_cfg.get("strength"), 90)))
        if strength <= 0:
            painter.setPen(color)
            painter.drawText(x, int(y), char)
            return
        r, g, b, a = color.red(), color.green(), color.blue(), color.alpha()
        alpha_scale = strength / 100.0
        offsets = self._glow_offsets()
        for dx, dy, scale in offsets:
            glow_alpha = max(0, min(255, int(base_glow_alpha * alpha_scale * scale)))
            if glow_alpha <= 0:
                continue
            painter.setPen(QColor(max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)), min(glow_alpha, a)))
            painter.drawText(x + dx, int(y) + dy, char)
        painter.setPen(color)
        painter.drawText(x, int(y), char)
    
    def paintEvent(self, event):
        """Paint the matrix rain effect (Matrix-style: white leading shine, green trail fade, glow)"""
        try:
            painter = QPainter(self)
            painter.setFont(self.font)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.TextAntialiasing)
            
            height = self.height()
            columns = getattr(self, "columns", [])
        except Exception:
            return
        try:
            bottom_fade_zone = max(60, height // 8)  # Pixels from bottom where fade starts
            for col in columns:
                if not getattr(col, "chars", None) or col.length <= 0:
                    continue
                L = max(col.length, 1)
                try:
                    ho = getattr(col, "head_offset", 0)
                    head_index = int(ho) % L
                except (TypeError, ValueError):
                    head_index = 0
                for i, char in enumerate(col.chars):
                    y = col.y + (i * self.char_height)
                    if -self.char_height <= y <= height:
                        # Steps behind the white head (0 = at head, 1+ = trail that fades after white passed)
                        steps_behind = (head_index - i) % L
                        # Smooth fade at bottom of screen so lines don't cut off
                        bottom_fade = 1.0
                        if y > height - bottom_fade_zone:
                            bottom_fade = max(0.0, (height - y) / bottom_fade_zone)
                        # Same white-shine animation for both regular and custom message columns
                        if steps_behind == 0:
                            # White shine here (moves down the column over time)
                            glow_cfg = self.config.get("glow") or {}
                            strength = max(0, min(100, _safe_int(glow_cfg.get("strength"), 90)))
                            if strength > 0:
                                alpha_scale = strength / 100.0 * bottom_fade
                                for dx, dy, scale in self._glow_offsets():
                                    a_glow = max(0, min(255, int(130 * alpha_scale * scale)))
                                    if a_glow > 0:
                                        painter.setPen(QColor(180, 255, 180, a_glow))
                                        painter.drawText(col.x + dx, int(y) + dy, char)
                            a = int(255 * bottom_fade)
                            painter.setPen(QColor(255, 255, 255, a))
                            painter.drawText(col.x, int(y), char)
                        elif steps_behind <= 2:
                            color = QColor(0, 255, 70, int(255 * bottom_fade))
                            self._draw_char_glow(painter, col.x, y, char, color, base_glow_alpha=80)
                        elif steps_behind <= 6:
                            persistence = max(0.3, getattr(col, "trail_persistence", 1.0))
                            eff = (steps_behind - 2) / persistence  # Slower fade for high-persistence columns
                            alpha = int(220 * (1 - min(1, eff / 5)) * bottom_fade)
                            color = QColor(0, 220, 60, max(alpha, 80))
                            self._draw_char_glow(painter, col.x, y, char, color, base_glow_alpha=40)
                        else:
                            persistence = max(0.3, getattr(col, "trail_persistence", 1.0))
                            eff_trail = (steps_behind - 6) / persistence
                            denom = max(L - 6, 1)
                            alpha = int(160 * (1 - min(1, eff_trail / denom)) * bottom_fade)
                            color = QColor(0, 180, 55, max(alpha, 60))
                            painter.setPen(color)
                            painter.drawText(col.x, int(y), char)
        except Exception:
            pass
    
    def update_animation(self):
        """Update animation frame"""
        try:
            height = self.height()
            columns = getattr(self, "columns", [])
            for col in columns:
                col.update(height)
            messages = self.config.get("custom_messages") or []
            if messages:
                self._message_inject_counter = getattr(self, "_message_inject_counter", 0) + 1
                interval = getattr(self, "_message_inject_interval", 30)
                if self._message_inject_counter >= interval:
                    self._message_inject_counter = 0
                    eligibles = [c for c in columns if not getattr(c, "is_message", False)]
                    if eligibles:
                        col = random.choice(eligibles)
                        msg = random.choice(messages)
                        if str(msg).strip():
                            col.set_message(msg.strip())
            self.update()
        except Exception:
            pass
    
    def _check_screensaver_idle(self):
        """If screensaver enabled and idle long enough, show fullscreen (screensaver on)."""
        if getattr(self, "_screensaver_active", False):
            return
        cfg = self.config.get("screensaver") or {}
        if not cfg.get("enabled"):
            return
        if self.isVisible():
            return
        idle_minutes = max(1, min(120, _safe_int(cfg.get("idle_minutes"), 1)))
        threshold_ms = idle_minutes * 60 * 1000
        try:
            idle_ms = get_idle_time_ms()
        except Exception:
            idle_ms = 0
        if sys.platform != "win32" and idle_ms == 0:
            return  # Idle detection only on Windows
        if idle_ms >= threshold_ms:
            self._screensaver_active = True
            self.showFullScreen()
            self.raise_()
            self.activateWindow()

    def _dismiss_screensaver(self):
        """Hide window and clear screensaver state on user input."""
        if getattr(self, "_screensaver_active", False):
            self._screensaver_active = False
            self.hide()

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
            self._dismiss_screensaver()
            event.accept()
            return
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
        # Simple green 16x16 icon
        pix = QPixmap(16, 16)
        pix.fill(Qt.transparent)
        painter = QPainter(pix)
        painter.setPen(QColor(0, 255, 0))
        painter.setBrush(QColor(0, 180, 0))
        painter.drawRect(2, 2, 12, 12)
        painter.end()
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon(pix))
        self.tray_icon.setToolTip("Matrix Rain")
        menu = QMenu()
        show_action = QAction("Show", self)
        show_action.triggered.connect(self.show)
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
        screensaver_action = QAction("Screensaver...", self)
        screensaver_action.triggered.connect(self.show_screensaver_dialog)
        menu.addAction(screensaver_action)
        menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit_app)
        menu.addAction(quit_action)
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()
        return self.tray_icon

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            if self.isVisible():
                self.hide()
            else:
                self.show()

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

    def show_screensaver_dialog(self):
        """Show screensaver enable and idle timeout dialog."""
        cfg = self.config.get("screensaver") or {}
        enabled = bool(cfg.get("enabled", False))
        idle_minutes = max(1, min(120, _safe_int(cfg.get("idle_minutes"), 1)))
        dlg = ScreensaverDialog(enabled, idle_minutes, self)
        if dlg.exec_() == QDialog.Accepted:
            en, mins = dlg.get_values()
            self.config = save_screensaver(en, mins)

    def quit_app(self):
        self.tray_icon.hide()
        QApplication.quit()


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


class ScreensaverDialog(QDialog):
    """Dialog to enable screensaver and set idle timeout."""
    def __init__(self, enabled, idle_minutes, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Screensaver")
        layout = QFormLayout(self)
        self.enabled_check = QCheckBox("Use Matrix Rain as screensaver")
        self.enabled_check.setChecked(bool(enabled))
        layout.addRow("", self.enabled_check)
        self.idle_spin = QDoubleSpinBox()
        self.idle_spin.setRange(1, 120)
        self.idle_spin.setValue(max(1, min(120, int(idle_minutes))))
        self.idle_spin.setDecimals(0)
        self.idle_spin.setSuffix(" min")
        layout.addRow("Turn on after (no mouse/keyboard):", self.idle_spin)
        layout.addRow(QLabel("(Windows: uses system idle time. Any key or mouse move dismisses.)"))
        layout.addRow(QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, accepted=self.accept, rejected=self.reject))

    def get_values(self):
        return self.enabled_check.isChecked(), int(self.idle_spin.value())


def main():
    """Main entry point"""
    try:
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)  # Keep running when hidden to tray
        widget = MatrixRainWidget()
        widget.show()
        sys.exit(app.exec_())
    except Exception as e:
        import traceback
        traceback.print_exc()
        try:
            log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "matrix_rain_crash.log")
            with open(log_path, "w", encoding="utf-8") as f:
                traceback.print_exc(file=f)
        except Exception:
            pass
        sys.exit(1)

if __name__ == "__main__":
    main()
