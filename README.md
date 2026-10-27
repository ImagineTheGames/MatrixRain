# Matrix Screensaver

A Matrix-style digital rain overlay for Windows: falling green characters (Latin + Katakana) with white leading shine, controllable from the system tray. Use as a full-screen overlay or as a screensaver that turns on after idle. Uses PyQt5.

## Features

- **Tray control** — Show/hide, add custom messages, speed, glow, screensaver settings
- **Custom messages** — Messages appear randomly in the rain (tray: Add message / Manage messages)
- **Speed & glow** — Adjust fall speed and glow strength/radius from the tray
- **Screensaver mode** — Turn on after N seconds of no mouse/keyboard (5 sec–2 hours; Windows idle detection). Dismiss with any key or mouse move.
- **Black background** — Optional opaque black backdrop while the screensaver is on, so the desktop is hidden (tray: Screensaver settings). Off by default.
- **Affirmations** — Short "I am" lines appear one at a time in the middle of the screen, cycling three entrances: decode (glyphs resolve into letters), rain drop (falling drops deposit the letters) and terminal (typed with a cursor). The rain dims behind the text. The list is `affirmations.txt` in this repo (one per line), fetched from GitHub hourly and cached; with `clock_sync` on, every PC picks the line and style from the wall clock, so all screens show the same affirmation at the same moment (keep hold/interval/styles the same on each PC). Tray: Affirmations toggle; timing in `matrix_config.json`.
- **Full-height lines** — Some streams run from top to bottom before fading
- **Mouse highlight** — Optional highlight of characters under the cursor
- **Start with Windows** — Tray toggle registers the app in the current user's Run key (`HKCU\Software\Microsoft\Windows\CurrentVersion\Run`, value `MatrixScreensaver`). Re-written on every launch, so it keeps pointing at wherever the app lives now.

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

`matrix_config.json` — speed, animation fps, column length, font, custom_messages, glow, screensaver, hue, affirmations (`messages`, `styles`, `rotate`, `interval_seconds` = gap after one leaves, `hold_seconds`, `backing`: none / dim / clear, `font_scale`, `source_url`, `clock_sync`).

## License

Use as you like.
