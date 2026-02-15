# Matrix Screensaver

A Matrix-style digital rain overlay for Windows: falling green characters (Latin + Katakana) with white leading shine, controllable from the system tray. Use as a full-screen overlay or as a screensaver that turns on after idle. Uses PyQt5.

## Features

- **Tray control** — Show/hide, add custom messages, speed, glow, screensaver settings
- **Custom messages** — Messages appear randomly in the rain (tray: Add message / Manage messages)
- **Speed & glow** — Adjust fall speed and glow strength/radius from the tray
- **Screensaver mode** — Turn on after N seconds of no mouse/keyboard (5 sec–2 hours; Windows idle detection). Dismiss with any key or mouse move.
- **Full-height lines** — Some streams run from top to bottom before fading
- **Mouse highlight** — Optional highlight of characters under the cursor

## Microsoft Store

Icons and screenshots for store submission are in `store/`. See `store/FEATURES_AND_LISTING.md` for a full feature writeup and asset list.

## Requirements

- Python 3.x
- PyQt5

```bash
pip install PyQt5
```

## Run (no console window)

- **Double-click** `run_matrix_rain.pyw`, or
- `pythonw run_matrix_rain.pyw`

## Config

`matrix_config.json` — speed, animation fps, column length, font, custom_messages, glow, screensaver.

## License

Use as you like.
