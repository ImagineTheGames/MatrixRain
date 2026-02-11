# Matrix Rain

A Matrix-style digital rain overlay for Windows: falling green characters with white leading shine, controllable from the system tray. Uses PyQt5.

## Features

- **Tray control** — Show/hide, add custom messages, speed, glow, screensaver settings
- **Custom messages** — Messages appear randomly in the rain (tray: Add message / Manage messages)
- **Speed & glow** — Adjust fall speed and glow strength/radius from the tray
- **Screensaver mode** — Turn on after N minutes of no mouse/keyboard (Windows idle detection)
- **Full-height lines** — Some streams run from top to bottom before fading

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
