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

`matrix_config.json` — speed, animation fps, column length, font, custom_messages, glow, screensaver, hue.

## Build for Microsoft Store

1. **Bump version** in `version.py` (see `.cursor/rules/version-and-build.mdc`).
2. Install PyInstaller: `pip install pyinstaller`
3. From repo root, run: `.\build\build.ps1`
4. Output: `dist\Matrix Screensaver\` (exe + store assets). The script cleans `dist/` and `build/` before building and removes `build/` after to keep size small.
5. **Publish via command line:** Use the [Microsoft Store Developer CLI](https://learn.microsoft.com/en-us/windows/apps/publish/msstore-dev-cli/overview-exe). See **`store/PUBLISH_CLI.md`** for install, configure (Entra ID), and: `.\build\publish-store.ps1 -ProductId "9NXXXXXXXX"`.  
   Alternatively, package the `dist\Matrix Screensaver\` contents as MSIX (e.g. MSIX Packaging Tool or Partner Center).

## License

Use as you like.
