## Destination

All design decisions for **CrossMouse** are resolved, so a hand-off spec / implementation plan can be written and given to an implementer. CrossMouse is a stripped-down, bidirectional Mouse-Without-Borders-style tool that lets one mouse and keyboard drive two machines (Linux X11 + Windows) over a LAN, paired by manual IP + shared secret, with plain-text clipboard sync.

## Notes

- **Domain**: cross-platform LAN input sharing (KVM-like). Terms are defined in `GLOSSARY.md`.
- **Skills every session should consult**: `grilling` and `domain-modeling`; research tickets also use `research`.
- **Tracker**: local markdown under `.scratch/crossmouse/` (see `docs/agents/issue-tracker.md`). Refer to tickets by name, never bare number.
- **Standing preferences (settled during charting — do not re-litigate)**:
  - Deliverable is a spec, not working software.
  - Bidirectional control between the two peers (not one-way host/client).
  - Manual IP + shared-secret pairing; no auto-discovery.
  - Clipboard: plain text only, last-write-wins; images/files deferred.
  - Single cross-platform codebase; X11 only on Linux (Wayland out of scope).
  - TCP link with authenticated encryption keyed from the shared secret.
  - Edge-crossing handoff, panic hotkey, and held-key cleanup on handoff.
- **Implementation calls made (human opted out of ticket grilling, 2026-11-20)**: Python single codebase; PBKDF2-HMAC-SHA256 + AES-GCM with a salted handshake probe; fixed configurable port; explicit connector/listener roles; no identity pinning beyond IP + secret; pointer warp to screen centre while forwarding (no true grab on Windows); X11 CLIPBOARD selection for text sync. See `README.md`.

## Decisions so far

- [Research: Input capture/injection libraries](./issues/01-input-library-research.md): `rdev` is the only named library with global capture + injection on both Windows and Linux X11, but its release is stale; `enigo` is maintained but injection-only; `pynput` is maintained with both but has Windows key-fidelity caveats.
- [Research: OS permissions & autostart](./issues/02-os-permissions-research.md): X11 needs no root (just an authorized X connection); Windows UIPI limits injection to equal-or-lower integrity unless `uiAccess` + signing; autostart via XDG / `systemd --user` and Startup folder / Task Scheduler.

## Not yet specified

- Exact panic hotkey binding (depends on handoff design and per-OS key conflicts).
- Screen topology and coordinate mapping across differing resolutions / DPI scaling (hangs on handoff design and language choice).
- Key-derivation function and handshake message details (hangs on the pairing protocol).
- Wire message schema and framing details (hangs on the protocol ticket).
- Per-peer multi-monitor behaviour.

## Out of scope

- Wayland support (ruled out for v1 — blocks global input grab/injection).
- Image/file clipboard transfer and file drag-and-drop (deferred past v1).
- More than two machines.
- Auto-discovery / zero-configuration pairing.
- Building the working software — this map ends at a spec.
