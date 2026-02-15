"""Resize store icon to required sizes. Run from repo root: python store/resize_icons.py"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PyQt5.QtGui import QImage, QPainter
from PyQt5.QtCore import Qt

ICONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")
SIZES = [(300, "icon_300.png"), (150, "icon_150.png"), (71, "icon_71.png"), (16, "tray_16.png")]

def main():
    src = os.path.join(ICONS_DIR, "icon_300.png")
    if not os.path.exists(src):
        print("Missing icon_300.png in store/icons")
        return
    img = QImage(src)
    if img.isNull():
        print("Failed to load icon_300.png")
        return
    for size, name in SIZES:
        out = os.path.join(ICONS_DIR, name)
        if size == 300:
            img.save(out)
            print("Kept", out)
            continue
        scaled = img.scaled(size, size, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        scaled.save(out)
        print("Saved", out, size, "x", size)

if __name__ == "__main__":
    main()
