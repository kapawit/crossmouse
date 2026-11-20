from __future__ import annotations

import select
import struct
import threading
import time

from .platform_base import Platform


class Clipboard:
    def get_text(self) -> str:
        raise NotImplementedError

    def set_text(self, text: str) -> None:
        raise NotImplementedError

    def close(self) -> None:
        pass


class LinuxClipboard(Clipboard):
    def __init__(
        self,
        platform: Platform,
        display_name: str | None = None,
        selection_name: str = "CLIPBOARD",
    ) -> None:
        from Xlib import X, display
        from Xlib.protocol import event, request

        self._x = display.Display(display_name)
        self._screen = self._x.screen()
        self._selection = self._x.intern_atom(selection_name)
        self._utf8 = self._x.intern_atom("UTF8_STRING")
        self._targets = self._x.intern_atom("TARGETS")
        self._atom_type = self._x.intern_atom("ATOM")
        self._string = self._x.intern_atom("STRING")
        self._prop = self._x.intern_atom("CROSSMOUSE_CLIP")
        self._request = request
        self._event = event
        self._X = X
        self._text = ""
        self._owner = False
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._win = self._screen.root.create_window(
            0,
            0,
            1,
            1,
            0,
            self._screen.root_depth,
            X.InputOutput,
            X.CopyFromParent,
            override_redirect=True,
        )
        self._x.sync()

    def get_text(self) -> str:
        if self._owner:
            return self._text
        owner = self._x.get_selection_owner(self._selection)
        owner_id = owner if isinstance(owner, int) else owner.id
        if owner_id == 0:
            return ""
        self._win.change_attributes(event_mask=self._X.PropertyChangeMask)
        self._x.sync()
        deadline = time.monotonic() + 3.0
        next_request = 0.0
        while time.monotonic() < deadline:
            prop = self._win.get_full_property(self._prop, self._utf8)
            if prop and prop.value:
                self._win.delete_property(self._prop)
                self._x.sync()
                return bytes(prop.value).decode("utf-8", "replace")
            if time.monotonic() >= next_request:
                self._request.ConvertSelection(
                    display=self._x.display,
                    selection=self._selection,
                    target=self._utf8,
                    property=self._prop,
                    requestor=self._win,
                    time=self._X.CurrentTime,
                )
                self._x.sync()
                next_request = time.monotonic() + 0.4
            ready, _, _ = select.select([self._x.fileno()], [], [], 0.1)
            if ready:
                self._x.next_event()
        return ""

    def set_text(self, text: str) -> None:
        self._text = text
        if not self._owner:
            self._request.SetSelectionOwner(
                display=self._x.display,
                window=self._win,
                selection=self._selection,
                time=self._X.CurrentTime,
            )
            self._x.sync()
            self._owner = True
            self._thread = threading.Thread(target=self._serve, daemon=True)
            self._thread.start()

    def _serve(self) -> None:
        request, event, X = self._request, self._event, self._X
        while not self._stop.is_set():
            try:
                ev = self._x.next_event()
            except Exception:
                break
            if isinstance(ev, event.SelectionClear):
                self._owner = False
                break
            if not isinstance(ev, event.SelectionRequest):
                continue
            if ev.target == self._targets:
                data = struct.pack("!II", self._utf8, self._targets)
                request.ChangeProperty(
                    display=self._x.display,
                    window=ev.requestor,
                    property=ev.property,
                    type=self._atom_type,
                    mode=X.PropModeReplace,
                    data=(32, data),
                )
            elif ev.target in (self._utf8, self._string):
                request.ChangeProperty(
                    display=self._x.display,
                    window=ev.requestor,
                    property=ev.property,
                    type=ev.target,
                    mode=X.PropModeReplace,
                    data=(8, self._text.encode("utf-8")),
                )
            else:
                ev.property = 0
            self._x.send_event(
                ev.requestor,
                event.SelectionNotify(
                    time=ev.time,
                    requestor=ev.requestor,
                    selection=ev.selection,
                    target=ev.target,
                    property=ev.property,
                ),
                event_mask=0,
            )
            self._x.sync()

    def close(self) -> None:
        self._stop.set()
        if self._owner:
            try:
                self._request.SetSelectionOwner(
                    display=self._x.display,
                    window=self._X.NONE,
                    selection=self._selection,
                    time=self._X.CurrentTime,
                )
            except Exception:
                pass
            self._owner = False
        try:
            self._win.destroy()
        except Exception:
            pass


class WindowsClipboard(Clipboard):
    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002

    def __init__(self) -> None:
        import ctypes
        from ctypes import wintypes

        self._u = ctypes.WinDLL("user32", use_last_error=True)
        self._k = ctypes.WinDLL("kernel32", use_last_error=True)
        self._ctypes = ctypes
        self._wintypes = wintypes
        self._text = ""

    def get_text(self) -> str:
        if not self._u.OpenClipboard(None):
            return self._text
        try:
            handle = self._u.GetClipboardData(self.CF_UNICODETEXT)
            if not handle:
                return self._text
            ptr = self._k.GlobalLock(handle)
            if not ptr:
                return self._text
            try:
                return self._ctypes.c_wchar_p(ptr).value or ""
            finally:
                self._k.GlobalUnlock(handle)
        finally:
            self._u.CloseClipboard()

    def set_text(self, text: str) -> None:
        self._text = text
        if not self._u.OpenClipboard(None):
            return
        try:
            self._u.EmptyClipboard()
            data = text.encode("utf-16-le") + b"\x00\x00"
            handle = self._k.GlobalAlloc(self.GMEM_MOVEABLE, len(data))
            if not handle:
                return
            ptr = self._k.GlobalLock(handle)
            self._ctypes.memmove(ptr, data, len(data))
            self._k.GlobalUnlock(handle)
            self._u.SetClipboardData(self.CF_UNICODETEXT, handle)
        finally:
            self._u.CloseClipboard()


def make_clipboard(platform: Platform) -> Clipboard:
    import sys

    if sys.platform == "win32":
        return WindowsClipboard()
    return LinuxClipboard(platform)
