Type: research
Status: open

## Question

Which input capture and injection library/API reliably supports **global** mouse + keyboard capture and injection on both Windows and Linux X11, and is maintained?

Specifically: what does each candidate (e.g. `rdev`, `enigo`, `pynput`, python-Xlib/XTest, Win32 low-level hooks + `SendInput`) actually support for global input grabbing and synthetic injection on each OS, and what are the known limitations (permissions, latency, key-state fidelity)? Resolve against primary sources (official docs / source) and write findings to a cited Markdown file.
