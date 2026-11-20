# Native status UI — approved design

## Verdict
Variant A ("Desktop window") from the throwaway prototype was approved on 2026-11-20.
Prototype is preserved on branch `prototype/native-status-ui` (commit `811de4d`).

## Question settled
What should the CrossMouse window look and behave like so it reads as a native desktop app rather than a web page?

## Approved behavior
- Default screen is the status surface inside a compact desktop-style window with a custom titlebar.
- A large Connect/Disconnect switch sits at the top of the status surface.
- The Listener/Controller selector sits directly under the switch. It is locked (dimmed, non-clickable) while connected.
- Listener mode shows the local IP address and port on the home screen. Controller mode shows no address and no port.
- Full connection details (role, control mode, screens, address/port for listener) appear only while connected. While disconnected, listener mode shows a compact "Listening on IP:port" strip; controller mode shows no strip.
- The cog button opens Configuration and Event log as tabs inside the settings sheet, replacing the status surface. The toggle is not visible on the settings page.
- The shared secret field has View/Hide and Copy controls.
- Spacing between all elements uses a consistent, roomier rhythm.
- No tagline or explanatory hint copy on the status surface.
