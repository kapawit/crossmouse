# CrossMouse

CrossMouse shares one mouse and keyboard between two machines over a LAN. Both machines run the same software symmetrically, so control can move in either direction.

## Language

**Peer**:
One of the two machines running CrossMouse. Both peers are symmetric — either can hold the physical input or be controlled.
_Avoid_: host, client, server, master, slave

**Pairing**:
The one-time manual setup in which each peer is given the other peer's IP address and a matching shared secret, establishing a trusted link.
_Avoid_: discovery, enrolment, binding

**Shared secret**:
The pre-shared passphrase entered on both peers, from which the link's encryption key is derived.
_Avoid_: password, PIN, token

**Handoff**:
The transfer of active input from one peer to the other when the cursor crosses the configured edge of the local screen.
_Avoid_: switch, takeover, handover

**Edge**:
The configured border of a peer's screen at which a handoff triggers.
_Avoid_: boundary, border, margin

**Panic hotkey**:
The key combination that immediately releases input back to the local peer, regardless of cursor position.
_Avoid_: escape key, kill switch

**Held-key cleanup**:
The release of all currently held keys at the moment of handoff, preventing keys from getting stuck on the remote peer.
_Avoid_: key reset, state flush

**Clipboard sync**:
The propagation of plain-text clipboard content between peers, last write winning on conflict.
_Avoid_: clipboard sharing, copy-paste bridge
