# Native desktop UI — design

Date: 2026-11-20
Branch: `native-ui`

## Intent

Replace CrossMouse's browser-based control panel with a real desktop application window on Windows and Linux. The user opens one app and gets a native window; no local HTTP server, no `webbrowser` launch, no browser tab.

The visual and interaction design already approved on `main` (`.scratch/native-status-ui/spec.md`) carries over unchanged: a compact status surface with a custom titlebar, large Connect/Disconnect switch, Listener/Controller selector locked while connected, listener address/port strip, connected-only details, and a cog that opens Configuration and Event log tabs in a settings sheet with secret View/Hide and Copy controls.

## Goals

- A real window available from the installed app on Windows and Linux.
- Direct in-process calls into `App` instead of HTTP endpoints.
- Preserve every capability the web UI currently exposes: connection toggle, role selection, config fields, debug toggle, handoff, and event log.
- Keep the existing pairing/transport engine untouched.
- Installers for all three platforms.

## Non-goals

- Redesigning the approved look.
- Reworking protocol, clipboard, handoff, or X11/Win32 input code.
- macOS: dropped from this rewrite. The existing `make_platform()` falls through to `LinuxPlatform` on `darwin` and needs Xlib/X11, so a macOS `.app` would be a non-functional shell. A real macOS peer needs a new Quartz backend and permission handling; out of scope here.

## Constraints

- Current Python 3.12 codebase, packaged with PyInstaller on Windows/Linux.
- `App` already owns state and actions: `status()`, `save_config()`, `set_debug()`, `reconnect()`, `disconnect()`, `handoff()`, `log_lines()`.
- `webui.py` and `ui/index.html` are the only browser-facing pieces.
- A fresh reviewer checks this doc before planning.

## Approaches considered

1. **PySide6/Qt (chosen).** Real desktop window on both target OSes, tray support, enough styling control for the approved custom titlebar and spacing, one Widgets codebase for Windows and Linux. Cost: larger installers and LGPL compliance (dynamic linking plus notices).
2. **wxPython.** Native widgets per OS, smaller dependency. Rejected: weaker styling control over the approved design and rougher macOS packaging.
3. **tkinter.** Smallest footprint. Rejected: dated look, separate `python3-tk` dependency on Linux, and the most manual work to reproduce the approved design.

## Design

### Toolkit and layout

PySide6 Widgets, not QML, so the window is built in Python and uses ordinary widgets with a stylesheet for the approved look. PySide6 remains the pick for Windows/Linux parity and styling control, not because of macOS.

- `main.py` creates `QApplication` on the UI thread and `App` with UI callbacks instead of a web server.
- `crossmouse/native_ui.py` holds the window, status polling, and the settings sheet.
- `App` gains a small observer interface (`subscribe`/`notify`) or the UI polls `status()` on a timer; polling is my call unless the builder flags a problem. Poll at roughly 250 ms for live status and log updates.
- UI actions call `App` methods directly on the UI thread; long work stays in `App`'s existing background thread.

### Window behavior

- Custom titlebar with close/minimize. Close hides to tray when a tray icon is available; quit comes from the tray menu.
- Status page: connect/disconnect switch, Listener/Controller pills, local IP and port in listener mode, connection details while connected, handoff button while controlling.
- Settings sheet: same panel replacing the status surface, with Configuration and Event log tabs; secret field with View/Hide and Copy; debug toggle.
- The Listener/Controller selector is disabled while connected, as approved.
- A tray icon shows status and provides Show, Connect/Disconnect, and Quit.

### Platform packaging

- Replace `webui.py` and `crossmouse/ui/` from runtime paths; remove `--ui-port`, `--no-browser`, and the `webbrowser` import from the CLI. Keep `--no-ui` for headless operation.
- Add PySide6 to `requirements.txt` and to both installer dependency sets.
- Windows: extend `packaging/CrossMouse.spec` and `build-windows.ps1`; produce `CrossMouse.exe` with Qt runtime bundled.
- Linux: update `packaging/build-deb.sh` to bundle PySide6 and declare the needed runtime deps in `control`.
- Update tests for the new CLI and UI wiring; old `test_webui.py` is removed or rewritten.

### Data flow

`App` remains authoritative. The native window reads snapshots (`status()`, `log_lines()`), writes through the same methods the HTTP API called, and reflects results on the next poll. No JSON-over-HTTP boundary remains inside the process.

## Left to the builder

- Exact Qt widget hierarchy and stylesheet values that reproduce the approved look.
- Whether to use a tray icon on Linux when the desktop lacks a status-notification area; hide the tray control gracefully.
- Signal/slot versus timer polling, if the builder finds a cleaner thread-safe approach.
- Nothing macOS-specific; it is out of scope for this rewrite.
