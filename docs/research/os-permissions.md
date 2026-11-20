# OS permissions and autostart for global input capture/injection (Windows, Linux X11)

Research question: what OS permissions and autostart mechanisms are required for a
background process that globally captures and injects mouse/keyboard input on
Windows and on Linux X11? This note records source-backed facts only. Every
claim is followed by an inline link to the primary source that owns it.

## Linux X11

### Connection, not root, is the gate

The core X11 protocol's security model checks the client's address at connection
time; if the client is allowed to connect it is "granted full access to the
server", including the ability to "monitor the state of all devices (including
all keystrokes, mouse movements, etc.)" ([X New Developer's Guide, "X Protocol
Security model"](https://www.x.org/guide/communication/)). The client can also
send events to other clients, capture the screen, read/write the clipboard and
alter other clients' properties ([X New Developer's Guide, "Access control within
the X server"](https://www.x.org/guide/communication/)). So the relevant
credential is an authorized X server connection, not a Unix root privilege.

The authorization in common use is a shared secret: the session starter records a
random 128-bit value in the server's `-auth` file and in an Xauthority file at
`$HOME/.Xauthority` or `$XAUTHORITY`, and a client connects if it can read that
file and present the correct value ([X New Developer's Guide, "xauth"](https://www.x.org/guide/communication/)). `xauth` uses `$XAUTHORITY` when set and
`$HOME/.Xauthority` otherwise ([xauth(1) man page](https://xorg.freedesktop.org/archive/current/doc/man/man1/xauth.1.xhtml)). A `DISPLAY` plus a readable
authority file is therefore what a background process needs. `xhost` provides an
alternative host/user-based access control method ([X New Developer's Guide,
"xhost"](https://www.x.org/guide/communication/)).

### XTest injection

XTEST is a server extension whose purpose is "limited synthesis of input device
events, almost as if a cooperative user had moved the pointing device or pressed
a key or button" ([XTEST Extension Protocol](https://xorg.freedesktop.org/releases/X11R7.7/doc/xextproto/xtest.html)). `XTestFakeInput` takes events of type
`KeyPress`, `KeyRelease`, `MotionNotify`, `ButtonPress` or `ButtonRelease`
([XTEST Extension Protocol](https://xorg.freedesktop.org/releases/X11R7.7/doc/xextproto/xtest.html)); the library API exposes these as
`XTestFakeKeyEvent`, `XTestFakeButtonEvent`, `XTestFakeMotionEvent` and
`XTestFakeRelativeMotionEvent`, each conditional on `XTestQueryExtension`
reporting that the display supports XTEST ([XTEST(3) man page](https://xorg.freedesktop.org/archive/current/doc/man/man3/XTestQueryExtension.3.xhtml)). XTEST also has `XTestGrabControl`, which can make a client "impervious to
server grabs" ([XTEST Extension Protocol](https://xorg.freedesktop.org/releases/X11R7.7/doc/xextproto/xtest.html)).

In the X server implementation, `ProcXTestFakeInput` validates event shape,
device and keycode/button ranges and injects events through the XTest virtual
devices; it contains no root-uid or filesystem-privilege check
([xorg-server `Xext/xtest.c`](https://github.com/XQuartz/xorg-server/blob/master/Xext/xtest.c)). Root is not part of the XTEST request path.

### XRecord global capture

The Record extension records core and extension protocol "entirely within the X
server itself" and "provides a mechanism for capturing all events, including
input device events that do not go to any clients"
([X Record Extension Library](https://xorg.freedesktop.org/releases/X11R7.7/doc/libXtst/recordlib.html)). A recording application typically opens two
connections to the server: one for record control and one for reading recorded
data. `XRecordCreateContext` expresses interest in clients (e.g.
`XRecordAllClients`) and protocol ranges; `XRecordEnableContext` starts delivery
through an `XRecordInterceptProc` callback
([X Record Extension Library](https://xorg.freedesktop.org/releases/X11R7.7/doc/libXtst/recordlib.html)). The `device_events` range covers core and extension input
device events, including those not delivered to any client
([X Record Extension Library](https://xorg.freedesktop.org/releases/X11R7.7/doc/libXtst/recordlib.html)). Like XTEST, XRecord is an ordinary extension request over an
X connection and does not require root.

### Active grabs: XGrabPointer / XGrabKeyboard

`XGrabPointer` "actively grabs control of the pointer"; further pointer events
are reported only to the grabbing client, and it can fail with `AlreadyGrabbed`
or `GrabFrozen` if another client holds or freezes the device
([XGrabPointer(3) man page](https://xorg.freedesktop.org/archive/current/doc/man/man3/XGrabPointer.3.xhtml)). `XGrabKeyboard` "actively grabs control of the keyboard and
generates FocusIn and FocusOut events"; further key events are reported only to
the grabbing client, and both `KeyPress` and `KeyRelease` are always reported
([XGrabKeyboard(3) man page](https://xorg.freedesktop.org/archive/current/doc/man/man3/XGrabKeyboard.3.xhtml)). X.org describes active grabs as taking "exclusive
control of a given resource immediately and lock[ing] out all other clients
until the grab is released" ([X New Developer's Guide, "Grabs"](https://www.x.org/guide/concepts/)). These are core-protocol requests over the same X
connection; no root privilege is required. On multi-pointer systems, a core grab
of one device blocks other clients from grabbing that device and prevents events
from other devices reaching the grabbing client
([X.org MPX documentation, "Grabs"](https://www.x.org/Development/Documentation/MPX/)).

### XTest vs XRecord vs grabs: the trust distinction

The SECURITY extension adds a per-connection "Trusted"/"Untrusted" distinction
([Security Extension Specification](https://xorg.freedesktop.org/releases/X11R7.6/doc/xextproto/security.html)). Under it, `QueryExtension` on an insecure
extension reports the extension as not present to an untrusted client, and
requests using a guessed opcode fail with a Request error
([Security Extension Specification](https://xorg.freedesktop.org/releases/X11R7.6/doc/xextproto/security.html)). In the X server source, the list of extensions
untrusted clients may use contains only `XC-MISC` and `BIG-REQUESTS`
([xorg-server `Xext/security.c`, `SecurityTrustedExtensions`](https://github.com/XQuartz/xorg-server/blob/master/Xext/security.c)); neither XTEST nor RECORD is in
that list, so both are withheld from untrusted connections (the SECURITY code
registers an XACE extension-access hook that sets `BadAccess` for other
extensions, `SecurityExtension()` in the same source). The standard
MIT-MAGIC-COOKIE-1 cookie can be generated as `trusted` or `untrusted`;
`xauth generate ... untrusted` produces a client "considered untrusted and
prevented from stealing or tampering with data belonging to trusted clients"
([xauth(1) man page](https://xorg.freedesktop.org/archive/current/doc/man/man1/xauth.1.xhtml)).

Grabs are core requests and are governed by different rules: the SECURITY
specification states that for an untrusted client `GrabKeyboard` returns
`AlreadyGrabbed`, while root windows are explicitly allowed as the grab-window
or confine-to fields of `GrabPointer`
([Security Extension Specification, "Keyboard Security" and "Resource ID Usage"](https://xorg.freedesktop.org/releases/X11R7.6/doc/xextproto/security.html)). X.org notes that the SECURITY extension can only disable extensions
wholesale, not individual requests
([X.org "Development/Documentation/Security"](https://www.x.org/Development/Documentation/Security/)).

Net source-backed position: XTest injection, XRecord capture and XGrab*
grabs all work over a normal X connection with a readable Xauthority cookie and
do not need root; the practical privilege boundary on X11 is *trusted vs
untrusted X client*, and XTEST and XRecord are both unavailable to untrusted
clients ([xorg-server `Xext/security.c`](https://github.com/XQuartz/xorg-server/blob/master/Xext/security.c), [Security Extension Specification](https://xorg.freedesktop.org/releases/X11R7.6/doc/xextproto/security.html)).

## Windows

### Low-level global hooks (WH_MOUSE_LL / WH_KEYBOARD_LL)

`SetWindowsHookEx` installs a hook into a hook chain; `WH_KEYBOARD_LL` and
`WH_MOUSE_LL` are "Global only" hooks, and a `dwThreadId` of zero associates the
hook with "all existing threads running in the same desktop as the calling
thread" ([SetWindowsHookExA](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwindowshookexa)). Global hooks are a shared resource and
affect all applications in the calling thread's desktop
([SetWindowsHookExA](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwindowshookexa), [Hooks Overview](https://learn.microsoft.com/en-us/windows/win32/winmsg/about-hooks)).

Unlike ordinary global hooks, low-level hooks do not require a DLL to be injected
into the target processes: "Low-level hook procedures are called on the thread
that installed the hook. Low-level hooks do not require that the hook procedure
be implemented in a DLL" ([Microsoft archived blog, "Low-Level Global Hooks in
.NET 2.0", quoting KB318804](https://learn.microsoft.com/en-us/archive/blogs/srivatsn/low-level-global-hooks-in-net-2-0)). The official callback docs state that
`WH_MOUSE_LL` and `WH_KEYBOARD_LL` are called in the context of the thread that
installed the hook (via a message sent to it), so that thread must have a message
loop, and the hook is "not injected into another process"
([LowLevelMouseProc](https://learn.microsoft.com/en-us/windows/win32/winmsg/lowlevelmouseproc), [LowLevelKeyboardProc](https://learn.microsoft.com/en-us/windows/win32/winmsg/lowlevelkeyboardproc)). Microsoft documents no administrator-rights
requirement for installing these hooks; the documented requirements are the
message loop and desktop scope.

Practical constraints that are documented: the hook procedure should finish
within `LowLevelHooksTimeout` under `HKEY_CURRENT_USER\Control Panel\Desktop`;
on Windows 7 and later a timed-out hook is silently removed, and on Windows 10
1709 and later the maximum allowed timeout is 1000 ms
([LowLevelMouseProc](https://learn.microsoft.com/en-us/windows/win32/winmsg/lowlevelmouseproc)). Microsoft advises running low-level hooks on a dedicated thread
that hands work to a worker and returns immediately
([LowLevelMouseProc](https://learn.microsoft.com/en-us/windows/win32/winmsg/lowlevelmouseproc)). Hook code must match the bitness of the application, with
32-bit/64-bit considerations for global hooks on 64-bit Windows
([SetWindowsHookExA](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwindowshookexa)).

### SendInput and UIPI / integrity levels

`SendInput` "synthesizes keystrokes, mouse motions, and button clicks"
([SendInput function](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput)). It is explicitly "subject to UIPI. Applications are
permitted to inject input only into applications that are at an equal or lesser
integrity level", and it can fail when blocked by UIPI without `GetLastError` or
the return value indicating that this was the cause
([SendInput function](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput)).

UIPI "implements restrictions in the Windows subsystem that prevent
lower-privilege applications from sending messages or installing hooks in
higher-privilege processes"; higher-privilege applications may send messages to
lower-privilege ones, and UIPI does not affect same-integrity-level
communication ([UAC: Only elevate UIAccess applications installed in secure
locations](https://learn.microsoft.com/en-us/previous-versions/windows/it-pro/windows-server-2012-r2-and-2012/jj852244(v=ws.11))). UAC assigns integrity levels: lower-IL
applications cannot modify data in higher-IL applications, and when an
administrator signs in, `explorer.exe` runs with the standard-user token so apps
normally run as standard user unless consent or credentials are supplied
([How User Account Control works](https://learn.microsoft.com/en-us/windows/security/application-security/application-control/user-account-control/how-it-works)).

Consequences for a non-elevated input tool, as stated by Microsoft: a process
started with UIAccess rights can "drive any application window by using the
SendInput function" and "use read input for all integrity levels by using
low-level hooks, raw input, GetKeyState, GetAsyncKeyState, and GetKeyboardInput"
([UAC: Only elevate UIAccess applications installed in secure
locations](https://learn.microsoft.com/en-us/previous-versions/windows/it-pro/windows-server-2012-r2-and-2012/jj852244(v=ws.11))). Without that, equal-or-lower
integrity is the documented limit.

### Manifest / UAC considerations

A normal desktop app starts at medium integrity and cannot access elevated
("medium+" IL) UI; setting the `uiAccess="true"` attribute on
`requestedExecutionLevel` in the manifest is the documented mechanism for
crossing that boundary, and `uiAccess` is false by default
([Security Considerations for Assistive Technologies](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-securityoverview)). To use UIAccess an application must
be Authenticode-signed, be trusted by the system (installed in a secure location
such as Program Files), and have a manifest containing the `uiAccess` flag
([Security Considerations for Assistive Technologies](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-securityoverview)); the secure locations are
`\Program Files\`, `\Windows\system32\`, and `\Program Files (x86)\`, and a PKI
signature check is enforced on interactive UIAccess applications regardless of
policy state ([UAC: Only elevate UIAccess applications installed in secure
locations](https://learn.microsoft.com/en-us/previous-versions/windows/it-pro/windows-server-2012-r2-and-2012/jj852244(v=ws.11))). Resulting IL depends on the launching
account: no manifest => medium IL; UIAccess + non-admin user => "medium+" IL;
UIAccess + admin user => high IL
([Security Considerations for Assistive Technologies](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-securityoverview)). Microsoft states UIAccess is not a
mechanism for a process to move up through the IL boundary by itself, and that
system-IL UI is reachable only when launched under the UAC desktop as SYSTEM
([Security Considerations for Assistive Technologies](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-securityoverview)).

UWP applications do not have UIAccess as an option
([Security Considerations for Assistive Technologies](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-securityoverview)).

## Autostart options

### Linux

**XDG autostart (`~/.config/autostart`).** Placing an application's `.desktop`
file in an Autostart Directory causes it to be launched automatically during
startup of the user's desktop environment after the user has logged in; the
user-specific directory is `~/.config/autostart/` when `$XDG_CONFIG_HOME` is
unset, and the system-wide directory is `/etc/xdg/autostart/` when
`$XDG_CONFIG_DIRS` is unset ([Desktop Application Autostart Specification v0.5](https://specifications.freedesktop.org/autostart/latest/)). A user can disable a
system-wide entry by placing a `.desktop` file of the same name with `Hidden=true`
in their personal autostart directory; `OnlyShowIn`, `NotShowIn` and `TryExec`
are also defined there ([Desktop Application Autostart Specification v0.5](https://specifications.freedesktop.org/autostart/latest/)).

**systemd --user.** The system manager starts a separate unprivileged per-user
systemd instance (`user@uid.service`) for each user; that user manager starts
units pulled in by its `default.target`, and on graphical login the login
manager starts `graphical-session.target` to pull in units required for the
graphical session ([bootup(7)](https://freedesktop.org/software/systemd/man/latest/bootup.html)). User unit search paths include `~/.config/systemd/user/`
and `/etc/systemd/user/`; `systemctl --user enable <unit>` hooks a unit into
the user manager's startup, while `--global` enables it for all future logins of
all users ([systemctl(1)](https://freedesktop.org/software/systemd/man/latest/systemctl.html)). `graphical-session.target` is active whenever a graphical
session is running and is intended for services that only apply to a graphical
(X, Wayland, etc.) session; `xdg-desktop-autostart.target` plus
`systemd-xdg-autostart-generator` let systemd consume XDG autostart `.desktop`
files ([systemd.special(7)](https://freedesktop.org/software/systemd/man/latest/systemd.special.html)). The generator sets `After=graphical-session.target` on
generated units and honours `OnlyShowIn`/`NotShowIn`
([systemd.io, "Desktop Environment Integration"](https://systemd.io/DESKTOP_ENVIRONMENTS/)).

### Windows

**Startup folder.** Copying or creating a shortcut in `shell:startup`
(`%userprofile%\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup`)
starts the app when the current user signs in; `shell:common startup`
(`%ProgramData%\Microsoft\Windows\Start Menu\Programs\Startup`) is the all-users
location ([Microsoft Support, "Configure startup applications in Windows"](https://support.microsoft.com/en-us/windows/experience/startup-boot/configure-startup-applications-in-windows)).

**Registry Run/RunOnce keys.** `Run` runs a program every time the user logs on,
`RunOnce` runs it once and then deletes the value; keys exist under HKLM and
HKCU at `Software\Microsoft\Windows\CurrentVersion\Run` and `...\RunOnce`
([Run and RunOnce Registry Keys](https://learn.microsoft.com/en-us/windows/win32/setupapi/run-and-runonce-registry-keys)). The command line value is limited to 260
characters, and the system may delay execution of `Run` and Startup-folder
programs ([Run and RunOnce Registry Keys](https://learn.microsoft.com/en-us/windows/win32/setupapi/run-and-runonce-registry-keys)). Windows groups Run keys,
RunOnce keys and Startup folders together as "startup apps" visible and
controllable from Task Manager's Startup tab
([Desktop Startup apps – Compatibility Cookbook](https://learn.microsoft.com/en-us/windows/compatibility/startup-apps)).

**Task Scheduler.** A task can use a `LogonTrigger` so it starts when a user logs
on ([Logon Trigger Example (XML)](https://learn.microsoft.com/en-us/windows/win32/taskschd/logon-trigger-example--xml-)). Task logon type
`TASK_LOGON_INTERACTIVE_TOKEN` means "User must already be logged on. The task
will be run only in an existing interactive session."
([TASK_LOGON_TYPE](https://learn.microsoft.com/en-us/windows/win32/api/taskschd/ne-taskschd-task_logon_type)); "Run only when user is logged on" runs a task
interactively, whereas "Run whether user is logged on or not" runs it
non-interactively ([Task Security Context](https://learn.microsoft.com/en-us/previous-versions/windows/it-pro/windows-server-2008-R2-and-2008/cc722152(v=ws.11))). A
task's security context, principal and credentials are set at registration
([Task Security Context (Task Scheduler)](https://learn.microsoft.com/en-us/windows/win32/taskschd/security-contexts-for-running-tasks)).

## Key facts for decision-makers

- On X11, an authorized connection to the X server grants full access, including
  monitoring all keystrokes and mouse movements; no root is involved
  ([X Protocol Security model](https://www.x.org/guide/communication/)).
- The Xauthority cookie is the normal connecting credential (`$XAUTHORITY` or
  `$HOME/.Xauthority`) ([xauth(1)](https://xorg.freedesktop.org/archive/current/doc/man/man1/xauth.1.xhtml), [X guide, "xauth"](https://www.x.org/guide/communication/)).
- XTest injects synthetic key/button/motion events as though a user produced
  them; the server request path has no root check
  ([XTEST Protocol](https://xorg.freedesktop.org/releases/X11R7.7/doc/xextproto/xtest.html), [`Xext/xtest.c`](https://github.com/XQuartz/xorg-server/blob/master/Xext/xtest.c)).
- XRecord can capture all input device events, including those delivered to no
  client ([X Record Extension Library](https://xorg.freedesktop.org/releases/X11R7.7/doc/libXtst/recordlib.html)).
- `XGrabPointer`/`XGrabKeyboard` give a client exclusive control of a device and
  can fail with `AlreadyGrabbed` if another client already holds it
  ([XGrabPointer(3)](https://xorg.freedesktop.org/archive/current/doc/man/man3/XGrabPointer.3.xhtml), [XGrabKeyboard(3)](https://xorg.freedesktop.org/archive/current/doc/man/man3/XGrabKeyboard.3.xhtml)).
- XTEST and RECORD are both withheld from *untrusted* X clients by the SECURITY
  extension's extension-access rules (only `XC-MISC` and `BIG-REQUESTS` are
  whitelisted), while grabs are core requests with separate untrusted-client
  rules ([`Xext/security.c`](https://github.com/XQuartz/xorg-server/blob/master/Xext/security.c), [Security Extension Specification](https://xorg.freedesktop.org/releases/X11R7.6/doc/xextproto/security.html)).
- `WH_MOUSE_LL`/`WH_KEYBOARD_LL` are global-only hooks scoped to the calling
  thread's desktop and do not require DLL injection into other processes
  ([SetWindowsHookExA](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwindowshookexa), [Low-Level Global Hooks in .NET 2.0](https://learn.microsoft.com/en-us/archive/blogs/srivatsn/low-level-global-hooks-in-net-2-0)).
- Low-level hooks run on the installing thread, which must pump messages, and
  can be silently removed on timeout (max 1000 ms from Windows 10 1709)
  ([LowLevelMouseProc](https://learn.microsoft.com/en-us/windows/win32/winmsg/lowlevelmouseproc), [LowLevelKeyboardProc](https://learn.microsoft.com/en-us/windows/win32/winmsg/lowlevelkeyboardproc)).
- `SendInput` can only inject into applications at equal or lower integrity, and
  UIPI failures are not reported through `GetLastError` or the return value
  ([SendInput](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput)).
- UIPI blocks lower-privilege apps from installing hooks in higher-privilege
  processes; UIAccess is the documented way for a trusted, signed, securely
  installed, manifest-marked app to drive elevated UI with `SendInput` and read
  input at all integrity levels via low-level hooks
  ([UAC: Only elevate UIAccess applications…](https://learn.microsoft.com/en-us/previous-versions/windows/it-pro/windows-server-2012-r2-and-2012/jj852244(v=ws.11)), [Security Considerations for Assistive Technologies](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-securityoverview)).
- Apps normally run as standard user because `explorer.exe` uses the
  standard-user token; elevation requires consent or credentials
  ([How User Account Control works](https://learn.microsoft.com/en-us/windows/security/application-security/application-control/user-account-control/how-it-works)).
- Linux autostart options are XDG `.desktop` files in `~/.config/autostart` and
  systemd `--user` units, with `graphical-session.target` /
  `xdg-desktop-autostart.target` tying services to a graphical session
  ([Autostart Specification](https://specifications.freedesktop.org/autostart/latest/), [systemd.special(7)](https://freedesktop.org/software/systemd/man/latest/systemd.special.html), [bootup(7)](https://freedesktop.org/software/systemd/man/latest/bootup.html)).
- Windows autostart options are the Startup folder, Registry Run/RunOnce keys,
  and Task Scheduler with a logon trigger; interactive input work requires an
  interactive session (`TASK_LOGON_INTERACTIVE_TOKEN` / "Run only when user is
  logged on") ([Microsoft Support](https://support.microsoft.com/en-us/windows/experience/startup-boot/configure-startup-applications-in-windows), [Run and RunOnce keys](https://learn.microsoft.com/en-us/windows/win32/setupapi/run-and-runonce-registry-keys), [Logon Trigger Example](https://learn.microsoft.com/en-us/windows/win32/taskschd/logon-trigger-example--xml-), [TASK_LOGON_TYPE](https://learn.microsoft.com/en-us/windows/win32/api/taskschd/ne-taskschd-task_logon_type), [Task Security Context](https://learn.microsoft.com/en-us/previous-versions/windows/it-pro/windows-server-2008-R2-and-2008/cc722152(v=ws.11))).
