## Destination

A hand-off spec / implementation plan for **CrossMouse**: a stripped-down, bidirectional Mouse-Without-Borders-style tool that lets one mouse and keyboard drive two machines (Linux X11 + Windows) over a LAN, paired by manual IP + shared secret, with plain-text clipboard sync. The map is done when every design decision is resolved and the spec can be written and handed to an implementer.

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

## Decisions so far

<!-- one line per closed ticket: gist + link, never the full answer -->

## Not yet specified

- Exact panic hotkey binding (depends on handoff design and per-OS key conflicts).
- Screen topology and coordinate mapping across differing resolutions / DPI scaling (hangs on handoff design and language choice).
- Key-derivation function and handshake message details (hangs on the pairing protocol).
- Wire message schema and framing details (hangs on the protocol ticket).
- Performance / latency targets for mouse movement (hangs on input-library research).
- Autostart and install/packaging mechanics (hangs on OS-permissions research).
- Per-peer multi-monitor behaviour.

## Out of scope

- Wayland support (ruled out for v1 — blocks global input grab/injection).
- Image/file clipboard transfer and file drag-and-drop (deferred past v1).
- More than two machines.
- Auto-discovery / zero-configuration pairing.
- Building the working software — this map ends at a spec.
