Type: research
Status: resolved

## Question

What OS permissions and autostart mechanisms are required to run a background process that globally captures and injects input on Windows and Linux X11?

Specifically: does X11 input grabbing / XTest need root, what UAC / manifest considerations exist on Windows, and what are the standard autostart options (systemd `--user`, Windows Startup folder / Task Scheduler)? Resolve against primary sources and write findings to a cited Markdown file.

## Answer

Resolved by a research subagent on branch `research/os-permissions` (commit `f7b50ef`). Findings: `docs/research/os-permissions.md` in this repo (cited; copied from the throwaway branch `research/os-permissions`, commit `f7b50ef`, which is not merged).

- Linux X11: root is not required — an authorized X connection (`DISPLAY` + readable `XAUTHORITY` / MIT-MAGIC-COOKIE-1) grants full capture and injection. The real boundary is trusted vs untrusted clients: the SECURITY extension withholds XTEST and RECORD from untrusted connections.
- Windows: `WH_MOUSE_LL` / `WH_KEYBOARD_LL` hooks are global-only, require a message pump on the installing thread, and can be silently removed on timeout. `SendInput` and hooks are UIPI-limited to equal-or-lower integrity processes; reaching elevated UI needs `uiAccess="true"`, Authenticode signing, and a secure install location.
- Autostart: Linux — XDG `~/.config/autostart` `.desktop` files or `systemd --user` units; Windows — Startup folder, Run/RunOnce registry keys, or logon-triggered Task Scheduler tasks. An interactive session is required for input grabbing.
