# Matrix Screensaver – Features & Microsoft Store Listing

## Short description (Microsoft Store)

**Matrix Screensaver** turns your PC into the digital rain from The Matrix. Use it as a full-screen overlay or as a real screensaver that turns on after you’ve been idle. Control everything from the system tray: speed, glow, custom messages, and more.

---

## Full feature list

### Rain effect
- **Digital rain overlay** – Full-screen falling characters (Latin letters, digits, symbols, and Katakana) in classic Matrix green.
- **Leading shine** – Bright white “head” character that moves down each column for a film-accurate look.
- **Glow** – Configurable glow strength (0–100%) and radius (1–3 px) so you can tune how much the characters glow.
- **Variable columns** – Column length and spacing tuned for a natural rain effect; some columns span the full screen.
- **Smooth animation** – Configurable FPS; default 30 for a good balance of smoothness and CPU use.

### Screensaver mode
- **Use as screensaver** – Option to use Matrix Screensaver as your screensaver: overlay appears after a set idle time.
- **Idle timeout in seconds** – Set how long (in seconds) with no mouse/keyboard before the overlay turns on (e.g. 5 for testing, 60 for 1 minute, 300 for 5 minutes). Range: 5 seconds to 2 hours.
- **Start with tray only** – When screensaver mode is on, the app starts minimized to the system tray; the full-screen rain appears only after the idle timeout (or when you choose “Show” from the tray).
- **Dismiss on any input** – Any key press or mouse move (anywhere on the PC) turns off the overlay and hides it back to the tray. Uses Windows low-level hooks for reliable detection.

### Custom messages
- **Add message** – Type a phrase; it’s added to the pool and shown as falling text in the rain (same white-shine animation as the rest of the rain).
- **Manage messages** – Add, remove, and reorder messages. Stored in config so they persist between runs.
- **Automatic injection** – Messages are randomly injected into columns so they appear naturally in the rain.

### System tray control
- **Show / Hide** – Show or hide the rain overlay without closing the app.
- **Speed** – Presets: Slower, Normal, Faster; or **Custom…** to set min/max falling speed (pixels per frame).
- **Glow…** – Dialog to set glow strength (0–100%) and radius (1–3 px).
- **Screensaver…** – Enable or disable screensaver mode and set idle timeout in seconds.
- **Mouse highlight** – Toggle to highlight characters under the cursor in white.
- **Add message…** / **Manage messages…** – Quick access to custom message management.
- **Quit** – Exit the app. Closing the window only hides it to the tray.

### Visual options
- **Mouse highlight** – When enabled, characters under the cursor are drawn in white.
- **Glow** – Strength and radius are configurable; can be turned off (0%) for a flatter look.
- **Speed** – Global falling speed so you can match the effect to your preference.

### Technical
- **Borderless, always-on-top overlay** – Rain sits on top of the desktop; transparent background so it doesn’t block the view of icons/wallpaper when desired.
- **Config file** – Settings (speed, glow, screensaver, messages, font, etc.) are stored in `matrix_config.json` next to the app.
- **Crash logging** – Unhandled exceptions are written to `matrix_rain_crash.log` for debugging.
- **Runs without console** – Use `pythonw run_matrix_rain.pyw` (or the packaged app) for a tray-only run with no terminal window.

---

## Store assets checklist

| Asset | Path | Notes |
|-------|------|--------|
| Icon 300×300 | `store/icons/icon_300.png` | Microsoft Store large icon |
| Icon 150×150 | `store/icons/icon_150.png` | Microsoft Store medium |
| Icon 71×71 | `store/icons/icon_71.png` | Microsoft Store small |
| Tray icon 16×16 | `store/icons/tray_16.png` | System tray (used by app if present) |
| Screenshot – rain | `store/screenshots/screenshot_rain.png` | Full-screen rain overlay |
| Screenshot – settings | `store/screenshots/screenshot_settings.png` | Tray menu & screensaver settings |

---

## Keywords (for store search)

Matrix, screensaver, digital rain, green rain, overlay, idle, Katakana, custom messages, system tray, Windows.
