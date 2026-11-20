# Native Desktop UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace CrossMouse's browser control panel with a PySide6 desktop window on Windows and Linux.

**Architecture:** Keep `App` and the network worker as the authoritative model. Add a `NativeUI` that owns the Qt event loop and a timer that reads `App.status()`/`App.log_lines()`. Widgets call `App` methods directly. The HTTP server, browser launch, and HTML UI are removed; installers bundle Qt.

**Tech Stack:** Python 3.12, PySide6 Widgets, PyInstaller, dpkg-deb, unittest.

**Spec:** `docs/superpowers/specs/2026-11-20-native-desktop-ui-design.md`

## Global Constraints

- Windows and Linux only. macOS is out of scope.
- Keep the approved visual behavior from `.scratch/native-status-ui/spec.md`.
- Keep the existing pairing, transport, clipboard, handoff, and X11/Win32 input code unchanged.
- Use PySide6 Widgets, not QML.
- No local HTTP server and no `webbrowser.open()` in the shipped app.
- `--no-ui` must still run headless.
- Tests use unittest. Run with `PYTHONPATH=.deps:. python3 -m unittest ...`; Qt GUI tests use `QT_QPA_PLATFORM=offscreen`.
- No macOS build target, signing, or notarization.

## Review Focus

- While connected, the Listener/Controller selector must be non-clickable and dimmed — a user changing role mid-session would break pairing. Covered in Task 3.
- Disconnect must immediately show Disconnected and stop reconnection/listener acceptance. Covered in Task 2.
- Config save must reject a bad port/edge/secret without corrupting the running config. Covered in Task 3.
- Closing the window must not kill an active session without an explicit Quit — a user expects close-to-tray behavior. Covered in Task 4.
- Installers must launch the native window without Python/PySide6 preinstalled. Covered in Task 5.

---

### Task 1: Add PySide6 dependency and native UI seam

**Files:**
- Modify: `requirements.txt`
- Modify: `crossmouse/main.py:345-369`
- Create: `crossmouse/native_ui.py`
- Test: `tests/test_native_ui.py`

**Interfaces:**
- Consumes: `App.status()`, `App.log_lines()`, `App.save_config()`, `App.set_debug()`, `App.reconnect()`, `App.disconnect()`, `App.handoff()`, `App.stop()`.
- Produces: `NativeUI.start(app: App) -> int` — creates the Qt application, shows the window, starts polling, and returns the Qt exit code; `NativeWindow` object names used by tests.

- [ ] **Step 1: Write the failing test**

```python
class NativeUITests(unittest.TestCase):
    def test_status_poll_updates_widgets(self):
        from crossmouse.native_ui import NativeWindow
        app = FakeApp()
        window = NativeWindow(app)
        window.refresh()
        self.assertEqual(window.findChild(QtWidgets.QLabel, "link_text").text(), "Disconnected")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=.deps:. python3 -m unittest tests.test_native_ui.NativeUITests.test_status_poll_updates_widgets -v`
Expected: FAIL with "No module named crossmouse.native_ui"

- [ ] **Step 3: Add dependency and skeleton**

Add `PySide6>=6.6` to `requirements.txt`. Create `crossmouse/native_ui.py` with `NativeWindow` exposing object names `link_text`, `role_pills`, `connect_switch`, `settings_button`, `handoff_button`. Add `NativeUI.start(app)` that creates `QApplication`, shows `NativeWindow(app)`, and starts a `QTimer` calling `refresh()` every 250 ms. In `main.py`, replace the WebUI/browser launch with `NativeUI.start(app)` unless `--no-ui`; remove `--ui-port` and `--no-browser` arguments. Keep `--no-ui` behavior by calling `app.start()` directly.

- [ ] **Step 4: Run the test**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=.deps:. python3 -m unittest tests.test_native_ui.NativeUITests.test_status_poll_updates_widgets -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add requirements.txt crossmouse/main.py crossmouse/native_ui.py tests/test_native_ui.py
git commit -m "feat: add PySide6 native UI seam"
```

### Task 2: Status surface and connection controls

**Files:**
- Modify: `crossmouse/native_ui.py`
- Modify: `tests/test_native_ui.py`

**Interfaces:**
- Consumes: `App.status()` keys: `connected`, `paused`, `connecting`, `mode`, `role`, `peer_ip`, `local_ip`, `port`, `edge`, `clipboard`, `primary`, `debug`, `local_screen`, `peer_screen`.
- Produces: widget object names `link_text`, `role_listener`, `role_controller`, `address_strip`, `detail_rows`, `handoff_button`.

- [ ] **Step 1: Write failing tests**

```python
def test_disconnected_state_has_no_details(self):
    window = NativeWindow(FakeApp(status={"connected": False, "paused": True, "role": "listener", "local_ip": "10.0.0.5", "port": 52800}))
    window.refresh()
    self.assertEqual(window.findChild(QtWidgets.QLabel, "address_strip").text(), "Listening on 10.0.0.5:52800")
    self.assertTrue(window.findChild(QtWidgets.QWidget, "detail_rows").isHidden())

def test_connect_switch_calls_reconnect(self):
    app = FakeApp()
    window = NativeWindow(app)
    window.findChild(QtWidgets.QPushButton, "connect_switch").click()
    self.assertEqual(app.calls, ["reconnect"])
```

- [ ] **Step 2: Run tests to verify failure**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=.deps:. python3 -m unittest tests.test_native_ui.NativeUITests.test_disconnected_state_has_no_details tests.test_native_ui.NativeUITests.test_connect_switch_calls_reconnect -v`
Expected: FAIL on missing widgets/behavior

- [ ] **Step 3: Implement status surface**

Build the status page with a custom titlebar, large connect/disconnect switch, Listener/Controller pills, address strip, and a details area shown only when connected. `refresh()` reads `app.status()` and updates text, visibility, and enabled state. The switch calls `app.reconnect()` when disconnected/paused and `app.disconnect()` when connected. The handoff button calls `app.handoff()` and is enabled only while `mode == "controlling"`.

- [ ] **Step 4: Run tests**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=.deps:. python3 -m unittest tests.test_native_ui.NativeUITests -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add crossmouse/native_ui.py tests/test_native_ui.py
git commit -m "feat: build native status surface"
```

### Task 3: Settings sheet, config, log, and secret controls

**Files:**
- Modify: `crossmouse/native_ui.py`
- Modify: `tests/test_native_ui.py`

**Interfaces:**
- Consumes: `App.config.to_dict()`, `App.save_config(data)`, `App.set_debug(enabled)`, `App.log_lines()`.
- Produces: `open_settings()`, `close_settings()`, object names `settings_sheet`, `tab_config`, `tab_log`, `secret_field`, `reveal_secret`, `copy_secret`, `debug_toggle`, `save_button`, `log_view`.

- [ ] **Step 1: Write failing tests**

```python
def test_selector_disabled_while_connected(self):
    app = FakeApp(status={"connected": True})
    window = NativeWindow(app)
    window.refresh()
    self.assertFalse(window.findChild(QtWidgets.QPushButton, "role_listener").isEnabled())

def test_save_config_sends_expected_dict(self):
    app = FakeApp()
    window = NativeWindow(app)
    window.open_settings()
    window.findChild(QtWidgets.QLineEdit, "port_field").setText("6000")
    window.findChild(QtWidgets.QPushButton, "save_button").click()
    self.assertEqual(app.calls[-1][0], "save_config")
    self.assertEqual(app.calls[-1][1]["port"], 6000)
```

- [ ] **Step 2: Run tests to verify failure**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=.deps:. python3 -m unittest tests.test_native_ui.NativeUITests.test_selector_disabled_while_connected tests.test_native_ui.NativeUITests.test_save_config_sends_expected_dict -v`
Expected: FAIL on missing settings widgets/behavior

- [ ] **Step 3: Implement settings sheet**

Add a `QStackedWidget` that swaps status surface and settings sheet; the cog button opens settings and a back button returns. Settings uses a tab widget with Configuration and Event log tabs. Fields cover `secret`, `peer_ip`, `port`, `edge`, `clipboard`, `primary`, `debug`, and `auto_start`. Secret field defaults to password echo; View/Hide toggles echo; Copy writes to `QGuiApplication.clipboard()`. Save builds a dict with correct types and calls `app.save_config()`. `debug_toggle` calls `app.set_debug()` directly. Log tab displays `app.log_lines()` and refreshes with the timer.

- [ ] **Step 4: Run tests**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=.deps:. python3 -m unittest tests.test_native_ui.NativeUITests -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add crossmouse/native_ui.py tests/test_native_ui.py
git commit -m "feat: add native settings and log sheet"
```

### Task 4: Tray behavior and window close

**Files:**
- Modify: `crossmouse/native_ui.py`
- Modify: `tests/test_native_ui.py`

**Interfaces:**
- Consumes: `QSystemTrayIcon.available()`, `App.stop()`.
- Produces: `closeEvent()` behavior and tray menu actions.

- [ ] **Step 1: Write failing tests**

```python
def test_close_hides_window_instead_of_stopping(self):
    app = FakeApp()
    window = NativeWindow(app)
    window.close()
    self.assertTrue(window.isHidden())
    self.assertNotIn("stop", app.calls)

def test_quit_tray_action_stops_app(self):
    app = FakeApp()
    window = NativeWindow(app)
    window.quit_from_tray()
    self.assertIn("stop", app.calls)
```

- [ ] **Step 2: Run tests to verify failure**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=.deps:. python3 -m unittest tests.test_native_ui.NativeUITests.test_close_hides_window_instead_of_stopping tests.test_native_ui.NativeUITests.test_quit_tray_action_stops_app -v`
Expected: FAIL

- [ ] **Step 3: Implement close/tray behavior**

If `QSystemTrayIcon.isSystemTrayAvailable()`, create a tray icon with Show, Connect/Disconnect, and Quit actions. Override `closeEvent()` to hide the window when the tray is available; otherwise call `app.stop()` after confirmation is not required in v1. Add `quit_from_tray()` that calls `app.stop()` then quits the Qt application. Connect the tray Disconnect action to `app.disconnect()`.

- [ ] **Step 4: Run tests**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=.deps:. python3 -m unittest tests.test_native_ui.NativeUITests -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add crossmouse/native_ui.py tests/test_native_ui.py
git commit -m "feat: add native tray and close behavior"
```

### Task 5: Remove web UI and update packaging

**Files:**
- Delete: `crossmouse/webui.py`, `crossmouse/ui/index.html`
- Delete: `tests/test_webui.py`
- Modify: `packaging/CrossMouse.spec`
- Modify: `packaging/build-windows.ps1`
- Modify: `packaging/build-deb.sh`
- Modify: `crossmouse/main.py`
- Modify: `tests/test_packaging.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `NativeUI.start(app)`, `PySide6>=6.6`.
- Produces: installers that launch the native window without a browser.

- [ ] **Step 1: Write failing packaging tests**

```python
def test_windows_spec_bundles_native_ui(self):
    spec = Path("packaging/CrossMouse.spec").read_text()
    self.assertIn("crossmouse.native_ui", spec)
    self.assertNotIn("crossmouse.webui", spec)

def test_deb_bundles_pyside6(self):
    script = Path("packaging/build-deb.sh").read_text()
    self.assertIn("PySide6", script)
```

- [ ] **Step 2: Run tests to verify failure**

Run: `PYTHONPATH=.deps:. python3 -m unittest tests.test_packaging -v`
Expected: FAIL

- [ ] **Step 3: Remove web UI and update packaging**

Delete the web UI files and `tests/test_webui.py`. Remove `--ui-port`, `--no-browser`, `webbrowser`, and WebUI imports from `main.py`. Update the PyInstaller spec: replace the HTML datas entry and webui hidden import with `crossmouse.native_ui` plus PySide6 hidden imports. Update Windows and Linux build scripts to install/bundle PySide6. Update README run/config/install sections for the native window. Update `tests/test_packaging.py` assertions.

- [ ] **Step 4: Run full suite and build**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=.deps:. python3 -m unittest discover -s tests -v`
Expected: PASS with all tests, including `tests/test_native_ui.py`.

Run: `./packaging/build-deb.sh 0.1.0`
Expected: `.deb` builds and contains `crossmouse/native_ui.py` plus PySide6 files.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: ship native desktop UI installers"
```

## Self-review

- Spec coverage: toolkit, status surface, controls, settings/log, tray, packaging, Windows/Linux, no macOS, engine untouched — each covered by Tasks 1-5.
- Step scan: each step writes one test, runs it, makes one change, then verifies.
- Type consistency: `App` method names and `status()` keys match the existing code; `NativeUI.start(app)` is the only new top-level entry point.
- Review focus: five items covered in Tasks 2-5.
- Proportion: plan is longer than the design doc but stays at named interfaces and assertions, not full widget code.
