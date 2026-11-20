# CrossMouse

Stripped-down Mouse Without Borders: one mouse and keyboard shared between two machines (Linux X11 and Windows) over a LAN. Peers pair by IP address plus a shared secret; control hands off when the cursor crosses the configured screen edge. Plain-text clipboard sync is included.

## Status

Working prototype. The Linux side is exercised against a live X server; the Windows side is written but could not be exercised in this environment. Cross-machine handoff needs a real two-machine LAN to validate end to end.

## Setup

```bash
python3 -m pip install --target .deps -r requirements.txt
```

`cryptography` is required at runtime; `python-xlib` is required on Linux. `.deps` is gitignored. The `run.sh` wrapper puts `.deps` on `PYTHONPATH`.

## Configure

The app creates `~/.config/crossmouse/config.json` on first run with a random secret. Edit that file on both machines (or use the UI's configuration form). For development, copy `config.example.json` to `config.json` and pass `--config config.json`.

- `secret` — must match on both peers.
- `peer_ip` — the other machine's LAN IP on one machine; omit it on the other to become the listener.
- `port` — must match on both peers (default `52800`).
- `edge` — the side of *this* machine's screen that faces the peer: `left`, `right`, `top`, or `bottom`. Set the two machines to opposite edges.
- `clipboard` — enable plain-text clipboard sync.
- `primary` — set `true` on the machine that has the physical mouse plugged in. Only that peer can initiate a handoff; the other peer must set `false` and only receives input. Defaults to `true`.

Example: machine A has `peer_ip` set, `edge: "right"`, and `primary: true`; machine B omits `peer_ip` and uses `edge: "left"`, `primary: false`.

## Run

```bash
./run.sh --config config.json
```

By default a control panel opens at `http://127.0.0.1:7788/`. It shows link status, active control, and an event log, and lets you edit the config, reconnect, and request a handoff. Use `--no-ui` for headless operation, `--ui-port N` to change the port, and `--no-browser` to suppress auto-opening the browser.

The connector retries every two seconds; the listener accepts a single authenticated session at a time.

## Installable packages

**Linux (.deb)** — built entirely on Linux:

```bash
python3 -m pip install --target .deps -r requirements.txt
./packaging/build-deb.sh          # -> dist/crossmouse_0.1.0_amd64.deb
sudo dpkg -i dist/crossmouse_0.1.0_amd64.deb
```

The package installs the launcher `/usr/bin/crossmouse` and a desktop entry. On first launch it creates a user-owned config at `~/.config/crossmouse/config.json` and opens the control panel in your browser. `/etc/crossmouse/config.json` is only a system-wide example; pass `--config /etc/crossmouse/config.json` to use it explicitly.

**Windows (.exe)** — PyInstaller cannot cross-compile, so this must be built on Windows (or by the included GitHub Actions workflow):

```powershell
powershell -File packaging/build-windows.ps1   # -> dist/CrossMouse.exe
```

The workflow at `.github/workflows/build.yml` builds both packages on `workflow_dispatch` and uploads them as artifacts.

## How handoff works

Each peer captures local input. When the cursor reaches the configured edge, that peer sends a handoff, grabs the pointer, and forwards input to the other machine, which injects it. Moving the injected cursor back to the shared edge returns control locally. Held keys are released on every handoff.

The link is TCP with AES-GCM. The session key comes from PBKDF2-HMAC-SHA256 over the shared secret with a salt sent by the listener; a handshake probe rejects a wrong secret before any input is exchanged.

## Limitations

- Linux X11 only; Wayland is out of scope.
- No true pointer grab on the Windows path; the local cursor is warped to screen center while forwarding.
- Windows UIPI blocks injection into elevated windows unless the process is signed with `uiAccess`.
- Clipboard is plain text only, last write wins. No image/file transfer.
- Two peers only; no discovery.

## Makefile

```bash
make build            # .deb on Linux, CrossMouse.exe on Windows
make install          # build then install
make run              # run from source
make test             # test suite
make clean            # remove build artifacts
```

OS-specific targets: `build-linux`, `install-linux`, `build-windows`, `install-windows`. On Windows use GNU make from MSYS2, Chocolatey, or Git Bash. `install-windows` copies the exe to `%LOCALAPPDATA%\Programs\CrossMouse` and adds a Start Menu shortcut; `install-linux` installs the `.deb` via `sudo` (override with `SUDO=`).

## Tests

```bash
PYTHONPATH=.deps:. python3 -m unittest discover -s tests -v
```
