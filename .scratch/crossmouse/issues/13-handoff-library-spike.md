Type: prototype
Status: open
Blocked by: 01

## Question

Can a single cross-platform input library actually deliver Mouse Without Borders-style **seamless edge handoff** — grabbing the local pointer so it cannot leave the screen, detecting the cursor reaching an edge, warping it, and continuing the gesture via relative-motion injection on the other side?

Research 01 found no library that clearly exposes all of grab + warp + relative-motion primitives on both Windows and Linux X11. Build a throwaway prototype (no tests, no polish) with the leading candidate from ticket 01 on both OSes that: grabs the pointer and keyboard, detects an edge crossing, warps the pointer, and continues motion via relative events. Record what works, what breaks, and which primitives the library actually exposes. Link the prototype as an asset. This ticket exists only to answer that question — it does not deliver part of the destination.
