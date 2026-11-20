Type: research
Status: resolved

## Question

Which input capture and injection library/API reliably supports **global** mouse + keyboard capture and injection on both Windows and Linux X11, and is maintained?

Specifically: what does each candidate (e.g. `rdev`, `enigo`, `pynput`, python-Xlib/XTest, Win32 low-level hooks + `SendInput`) actually support for global input grabbing and synthetic injection on each OS, and what are the known limitations (permissions, latency, key-state fidelity)? Resolve against primary sources (official docs / source) and write findings to a cited Markdown file.

## Answer

Resolved by a research subagent on branch `research/input-libraries` (commit `f2ee7d9`). Findings: `docs/research/input-libraries.md` in this repo (cited; copied from the throwaway branch `research/input-libraries`, commit `f2ee7d9`, which is not merged).

- `rdev` is the only named cross-platform library with both global capture and injection on Windows (`WH_KEYBOARD_LL`/`WH_MOUSE_LL` + `SendInput`) and Linux X11 (XRecord + XTest), but its crates.io release is stale (0.5.3, 2023-06-26) despite 2026 upstream / RustDesk-fork commits.
- `enigo` is actively maintained (0.6.1, 2025-08-28) but is injection-only — it has no global listener API.
- `pynput` has global listeners and controllers on Windows and X11 with a fresh release (1.8.2, 2026-05-12), but its own docs warn that Windows-injected keypresses are not treated as truly pressed (no auto-repeat, broken Shift+arrow).
- Windows low-level hooks can be silently removed on timeout and are UIPI-limited; XRecord can observe events no client receives; `XGrab*` are exclusive grabs, not passive capture.
