# Live debug logging — approved design

Approved by the user on 2026-11-20.

## Intent

CrossMouse needs a runtime debug mode that can be watched live while the app is running, especially when a pointer handoff fails. The user wants to read `debug.log` in real time and see pointer status, coordinates, and other useful information.

## Decisions

- Debug mode is enabled by a switch in Settings → Configuration.
- The switch is a runtime control: turning it on starts writing `debug.log`; turning it off stops writing. The app keeps running normally either way.
- The setting persists across restarts.
- No separate CLI flag; the settings switch is the only control (builder's call).
- `debug.log` is append-only, with a timestamp on every line.
- Each line is flushed immediately so `tail -f` shows it live.
- The log file location:
  - Windows install: `%LOCALAPPDATA%\Programs\CrossMouse\debug.log`
  - Linux `.deb` install: `/var/log/crossmouse/debug.log`; the installer creates this directory with writable permissions.
  - Running from source or `dist`: the app directory.
  - If the preferred location is not writable, fall back to the current working directory.
- The secret is never written to the log.

## Log content

Every snapshot line contains:

- timestamp with milliseconds
- mode: `idle`, `controlling`, or `controlled`
- role: `listener` or `controller`
- link state: connected or not
- local pointer coordinates
- virtual peer coordinates
- local and peer screen sizes
- configured handoff edge

Transition lines are also written for:

- startup and shutdown
- config summary (peer IP, port, edge, clipboard, primary, debug; secret masked)
- link connect, disconnect, and connection failure
- handoff sent or received
- edge-trigger decision
- pointer grab/release, suppress on/off, hidden/shown
- platform pointer injection failures

Normal key, button, and scroll events are not logged individually. Pointer snapshots are sampled at a steady interval so the file stays readable.

## Non-goals

- No remote log streaming.
- No log rotation in this change.
- No change to normal (debug off) behavior or performance.
