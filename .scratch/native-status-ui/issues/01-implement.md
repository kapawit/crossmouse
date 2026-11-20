# Implement approved native status UI

Type: task
Status: resolved

Implement variant A from the approved design in `../spec.md`.

Prototype reference: branch `prototype/native-status-ui`, commit `811de4d`, final artifact
`.superpowers/brainstorm/18079-1795163001/content/ui-native-layouts-v12.html`.

## Resolution
- Replaced `crossmouse/ui/index.html` with the approved desktop-window status surface.
- Added `local_ip_address()` and `App.status()["local_ip"]` so Listener mode can show the LAN IP.
- Added tests for the LAN IP probe, loopback fallback, and status exposure.
- Full suite: 51 tests passing; JS syntax checked; HTTP smoke test confirmed status/config/UI endpoints.
