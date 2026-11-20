# Live debug logging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a persisted Settings toggle that writes a live, timestamped `debug.log` containing pointer state, coordinates, and handoff diagnostics.

**Architecture:** Add a small `debuglog` module for path resolution and an append-and-flush file logger. `Config` gains a `debug` boolean; `App` owns the logger and exposes `set_debug()` plus a `/api/debug` endpoint so the UI can toggle it without reconnecting. `Engine` emits sampled pointer snapshots and transition lines through an injected sink.

**Tech Stack:** Python 3.10+, stdlib `logging`/`pathlib`, existing `ThreadingHTTPServer` WebUI, vanilla HTML/CSS/JS, PyInstaller, dpkg-deb.

**Spec:** `.scratch/debug-logging/spec.md`

## Global Constraints

- Append-only log; never truncate on startup.
- Every line starts with a millisecond timestamp and is flushed immediately.
- The shared secret must never appear in the log.
- Debug off must not change runtime behavior.
- Toggling debug must not reconnect or restart the link.
- Preferred log paths: Windows install dir, `/var/log/crossmouse/debug.log` for `.deb`, app dir for source/`dist`; fall back to CWD if unwritable.

## Review Focus

- Unwritable preferred log path: logger falls back to CWD and still writes.
- Debug switched off: logger closes and no later lines are written.
- Save config while debug is on: `debug` value is preserved.
- Log contents: shared secret never appears.
- Rapid handoff: snapshots show `controlling` and `controlled` transitions with coordinates.

---

### Task 1: Config field and debug logger

**Files:**
- Create: `crossmouse/debuglog.py`
- Create: `tests/test_debuglog.py`
- Modify: `crossmouse/config.py`
- Modify: `tests/test_core.py`
- Modify: `config.example.json`

**Interfaces:**
- Consumes: nothing.
- Produces: `debug_log_path(preferred: Path | None = None) -> Path`, `DebugLogger(path: Path)`, `DebugLogger.log(message: str) -> None`, `DebugLogger.close() -> None`, `Config.debug: bool`.

- [x] **Step 1: Write failing tests for `Config.debug` and `DebugLogger`**

In `tests/test_core.py`, add tests asserting `Config.from_dict({"secret": "s"}).debug is False` and `Config.from_dict({"secret": "s", "debug": True}).to_dict()["debug"] is True`.

In `tests/test_debuglog.py`, write tests that a `DebugLogger` writes two appended lines to a temp path, each matching `^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3} `, and that `close()` stops further writes from that instance. Also pin the fallback rule: call `debug_log_path(Path("/proc/forbidden/debug.log"))` and assert it returns `Path.cwd() / "debug.log"`.

- [x] **Step 2: Run tests to verify RED**

Run: `PYTHONPATH=.deps:. python3 -m unittest tests.test_core.ConfigTests tests.test_debuglog -v`
Expected: FAIL because `Config.debug` and `crossmouse.debuglog` do not exist.

- [x] **Step 3: Implement `crossmouse/debuglog.py`**

Implement `debug_log_path(preferred: Path | None = None) -> Path`: compute the platform path when `preferred` is `None`; otherwise probe `preferred`; on any `OSError`, return `Path.cwd() / "debug.log"`. Implement `DebugLogger` opening the file in append mode, writing `timestamp message` with `flush()` on every line, and making `log()` a no-op after `close()`.

- [x] **Step 4: Add `debug` to `Config`**

Add `debug: bool = False` to the dataclass and `debug=bool(data.get("debug", False))` to `from_dict`. Add `"debug": false` to `config.example.json`.

- [x] **Step 5: Run tests to verify GREEN**

Run: `PYTHONPATH=.deps:. python3 -m unittest tests.test_core.ConfigTests tests.test_debuglog -v`
Expected: PASS.

- [x] **Step 6: Commit**

```bash
git add crossmouse/debuglog.py crossmouse/config.py config.example.json tests/test_debuglog.py tests/test_core.py
git commit -m "feat: add persisted debug config and file logger"
```

### Task 2: App toggle and WebUI endpoint

**Files:**
- Modify: `crossmouse/main.py`
- Modify: `crossmouse/webui.py`
- Modify: `tests/test_core.py`
- Create: `tests/test_webui.py`

**Interfaces:**
- Consumes: `DebugLogger`, `debug_log_path()`, `Config.debug`.
- Produces: `App.set_debug(enabled: bool) -> None`, `App.status()["debug"]`, `POST /api/debug {"enabled": bool}`.

- [x] **Step 1: Write failing tests**

In `tests/test_core.py`, add `AppStatusTests.test_status_includes_debug`, `AppDebugTests.test_set_debug_persists_without_reconnect`, `AppDebugTests.test_set_debug_off_closes_logger`, and `AppDebugTests.test_save_config_preserves_debug`. Use an `App` built via `__new__` with a temp config path and patched `App._log`. Assert saved JSON has `debug: true`, `app.engine.config.debug` is true, `_reconnect.set` was never called, switching off leaves `_debug_logger is None`, and saving an unrelated field keeps `debug` true.

In `tests/test_webui.py`, start `WebUI` with a fake app exposing `status`, `config`, `log_lines`, and `set_debug`; POST `/api/debug` with `{"enabled": true}`; assert the fake recorded `True` and the response is `{"ok": true, "debug": true}`.

- [x] **Step 2: Run tests to verify RED**

Run: `PYTHONPATH=.deps:. python3 -m unittest tests.test_core.AppStatusTests tests.test_core.AppDebugTests tests.test_webui -v`
Expected: FAIL because `set_debug`, status `debug`, and `/api/debug` do not exist.

- [x] **Step 3: Implement `App.set_debug()` and status field**

Add `self._debug_logger`, create/close the logger in `set_debug()`, persist config without setting `_reconnect`, update `self.engine.config`, and add `"debug": bool(self.config.debug)` to `status()`. Add `App._debug(message)` that forwards to the logger when present. Ensure `App.stop()` closes the logger.

- [x] **Step 4: Implement `POST /api/debug`**

In `webui.py`, route `/api/debug` to `app.app.set_debug(bool(data.get("enabled")))` and return `{"ok": True, "debug": bool(self.config.debug)}` from the app's current config.

- [x] **Step 5: Run tests to verify GREEN**

Run: `PYTHONPATH=.deps:. python3 -m unittest tests.test_core.AppStatusTests tests.test_core.AppDebugTests tests.test_webui -v`
Expected: PASS.

- [x] **Step 6: Commit**

```bash
git add crossmouse/main.py crossmouse/webui.py tests/test_core.py tests/test_webui.py
git commit -m "feat: add runtime debug toggle endpoint"
```

### Task 3: Engine pointer snapshots

**Files:**
- Modify: `crossmouse/engine.py`
- Modify: `crossmouse/main.py`
- Modify: `tests/test_engine.py`

**Interfaces:**
- Consumes: `App._debug` as optional `debug_sink`.
- Produces: `Engine.debug_sink`, `Engine.debug_snapshot(reason: str) -> None`.

- [ ] **Step 1: Write failing test**

In `tests/test_engine.py`, create an engine with a debug sink that appends messages to a list, cross the edge to enter `controlling`, and assert that at least one emitted line contains `mode=controlling`, `local=(`, `virtual=(`, `edge=right`, and does not contain the configured secret.

- [ ] **Step 2: Run test to verify RED**

Run: `PYTHONPATH=.deps:. python3 -m unittest tests.test_engine.EngineDebugTests -v`
Expected: FAIL because `debug_sink` and `debug_snapshot` do not exist.

- [ ] **Step 3: Implement engine diagnostics**

Add optional `debug_sink` to `Engine.__init__`; add `Engine._debug(message)` and `Engine.debug_snapshot(reason)` producing a single line with mode, role, link state, local pointer coordinates, virtual peer coordinates, local/peer screens, and edge. Call `debug_snapshot` on handoff start/end and remote handoff receipt. Add `_debug` transition lines next to the existing `log.info` handoff messages. Never include `config.secret`.

- [ ] **Step 4: Sample snapshots while debug is on**

In `App.start()`, change the loop sleep to `0.1` seconds and call `self.engine.debug_snapshot("poll")` when `config.debug` is true and at least `0.25` seconds have elapsed since the last sample.

- [ ] **Step 5: Run test to verify GREEN**

Run: `PYTHONPATH=.deps:. python3 -m unittest tests.test_engine.EngineDebugTests -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add crossmouse/engine.py crossmouse/main.py tests/test_engine.py
git commit -m "feat: log pointer snapshots during handoff"
```

### Task 4: Settings toggle

**Files:**
- Modify: `crossmouse/ui/index.html`
- Modify: `tests/test_webui.py`

**Interfaces:**
- Consumes: `POST /api/debug`, `App.status()["debug"]`, `/api/config`.
- Produces: Settings checkbox with `data-field="debug"`.

- [ ] **Step 1: Write failing test**

In `tests/test_webui.py`, add a test that GET `/` contains `data-field="debug"` and the label text `Debug logging`.

- [ ] **Step 2: Run test to verify RED**

Run: `PYTHONPATH=.deps:. python3 -m unittest tests.test_webui.WebUIPageTests -v`
Expected: FAIL because the checkbox is absent.

- [ ] **Step 3: Add the UI toggle**

Add a checkbox labeled `Debug logging (writes debug.log)` to the Configuration form. Initialize it from `/api/config`. On change, POST `/api/debug` immediately, update local state, and show a short `Debug logging on/off` status message. Ensure `saveConfig()` does not send or clear `debug`.

- [ ] **Step 4: Run test to verify GREEN**

Run: `PYTHONPATH=.deps:. python3 -m unittest tests.test_webui.WebUIPageTests -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add crossmouse/ui/index.html tests/test_webui.py
git commit -m "feat: add debug toggle to settings page"
```

### Task 5: Packaging and rebuilt artifacts

**Files:**
- Modify: `packaging/build-deb.sh`
- Modify: `README.md`
- Rebuild: `dist/CrossMouse.exe`, `dist/crossmouse_0.1.0_amd64.deb`

**Interfaces:**
- Consumes: all previous tasks.
- Produces: installers containing the debug toggle and logger.

- [ ] **Step 1: Make Linux log dir writable**

In `packaging/build-deb.sh`, extend `postinst` to create `/var/log/crossmouse` and set writable permissions. Add a short README note describing the Settings toggle and log locations.

- [ ] **Step 2: Run full tests and JS syntax check**

Run:
```bash
PYTHONPATH=.deps:. python3 -m unittest discover -s tests
python3 - <<'PY'
import re, pathlib
p = pathlib.Path('crossmouse/ui/index.html')
pathlib.Path('/tmp/opencode/crossmouse-ui.js').write_text(re.search(r'<script>(.*)</script>', p.read_text(), re.S).group(1))
PY
node --check /tmp/opencode/crossmouse-ui.js
```
Expected: all tests pass and JS syntax check exits 0.

- [ ] **Step 3: Rebuild both artifacts**

Windows: run PyInstaller via PowerShell from `packaging/CrossMouse.spec`.
Linux: stage source in `/tmp/opencode/crossmouse-linux-build` (the `/mnt/d` mount forces `0777` and breaks `dpkg-deb`), run `packaging/build-deb.sh 0.1.0`, copy the `.deb` back to `dist/`, and restore/copy `dist/CrossMouse.exe`.

- [ ] **Step 4: Verify artifacts**

Assert the `.deb` contains `crossmouse/debuglog.py` and `data-field="debug"` in `ui/index.html`. Assert both files exist in `dist/`.

- [ ] **Step 5: Commit and push**

```bash
git add packaging/build-deb.sh README.md dist/CrossMouse.exe dist/crossmouse_0.1.0_amd64.deb
git commit -m "build: ship debug logging in both installers"
git push origin main
```
