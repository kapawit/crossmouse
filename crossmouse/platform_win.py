from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes

from .platform_base import EventSink, InputEvent, Platform

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
KEYEVENTF_KEYUP = 0x0002
WH_MOUSE_LL = 14
WH_KEYBOARD_LL = 13
HC_ACTION = 0
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN, WM_LBUTTONUP = 0x0201, 0x0202
WM_RBUTTONDOWN, WM_RBUTTONUP = 0x0204, 0x0205
WM_MBUTTONDOWN, WM_MBUTTONUP = 0x0207, 0x0208
WM_MOUSEWHEEL = 0x020A
WM_KEYDOWN, WM_KEYUP = 0x0100, 0x0101
WM_SYSKEYDOWN, WM_SYSKEYUP = 0x0104, 0x0105

_VK = {
    "ctrl": 0x11, "shift": 0x10, "alt": 0x12, "super": 0x5B,
    "enter": 0x0D, "esc": 0x1B, "escape": 0x1B, "space": 0x20,
    "backspace": 0x08, "delete": 0x2E, "tab": 0x09,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22,
}
for _c in "abcdefghijklmnopqrstuvwxyz":
    _VK[_c] = ord(_c.upper())
for _i in range(1, 13):
    _VK[f"f{_i}"] = 0x6F + _i
for _c in "0123456789":
    _VK[_c] = ord(_c)

_BUTTON_FLAGS = {
    "left": (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
    "right": (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
    "middle": (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
}


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG), ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_ulonglong),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_ulonglong),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", POINT), ("mouseData", wintypes.DWORD), ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_ulonglong),
    ]


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD), ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD), ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_ulonglong),
    ]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND), ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM), ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD), ("pt", POINT),
    ]


HOOKPROC = ctypes.WINFUNCTYPE(wintypes.LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)


class WindowsPlatform(Platform):
    def __init__(self) -> None:
        self._sink: EventSink | None = None
        self._thread: threading.Thread | None = None
        self._hooks: list = []
        self._pressed: set[int] = set()

    def screen_size(self) -> tuple[int, int]:
        return (
            user32.GetSystemMetrics(0),
            user32.GetSystemMetrics(1),
        )

    def pointer_position(self) -> tuple[int, int]:
        p = POINT()
        user32.GetCursorPos(ctypes.byref(p))
        return p.x, p.y

    def set_pointer(self, x: int, y: int) -> None:
        user32.SetCursorPos(int(x), int(y))

    def grab(self) -> None:
        pass

    def ungrab(self) -> None:
        pass

    def start_capture(self, sink: EventSink) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._sink = sink
        self._thread = threading.Thread(target=self._pump, daemon=True)
        self._thread.start()

    def _pump(self) -> None:
        module = kernel32.GetModuleHandleW(None)

        @HOOKPROC
        def mouse_proc(code, wparam, lparam):
            if code == HC_ACTION and self._sink:
                info = ctypes.cast(lparam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                if wparam == WM_MOUSEMOVE:
                    self._sink(InputEvent("move", info.pt.x, info.pt.y))
                elif wparam in (WM_LBUTTONDOWN, WM_LBUTTONUP):
                    self._sink(InputEvent("button", "left", int(wparam == WM_LBUTTONDOWN)))
                elif wparam in (WM_RBUTTONDOWN, WM_RBUTTONUP):
                    self._sink(InputEvent("button", "right", int(wparam == WM_RBUTTONDOWN)))
                elif wparam in (WM_MBUTTONDOWN, WM_MBUTTONUP):
                    self._sink(InputEvent("button", "middle", int(wparam == WM_MBUTTONDOWN)))
                elif wparam == WM_MOUSEWHEEL:
                    delta = ctypes.c_short(info.mouseData >> 16).value
                    self._sink(InputEvent("scroll", 0, 1 if delta > 0 else -1))
            return user32.CallNextHookEx(None, code, wparam, lparam)

        @HOOKPROC
        def keyboard_proc(code, wparam, lparam):
            if code == HC_ACTION and self._sink:
                info = ctypes.cast(lparam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                key = _vk_name(info.vkCode)
                if key:
                    down = wparam in (WM_KEYDOWN, WM_SYSKEYDOWN)
                    self._sink(InputEvent("key", key, int(down)))
            return user32.CallNextHookEx(None, code, wparam, lparam)

        self._hooks = [
            user32.SetWindowsHookExW(WH_MOUSE_LL, mouse_proc, module, 0),
            user32.SetWindowsHookExW(WH_KEYBOARD_LL, keyboard_proc, module, 0),
        ]
        msg = MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def stop_capture(self) -> None:
        for hook in self._hooks:
            if hook:
                user32.UnhookWindowsHookEx(hook)
        self._hooks = []
        self._sink = None

    def inject(self, event: InputEvent) -> None:
        items = []
        if event.kind == "move":
            w, h = self.screen_size()
            x = max(0, min(w - 1, int(event.a)))
            y = max(0, min(h - 1, int(event.b)))
            item = INPUT(type=INPUT_MOUSE)
            item.mi = MOUSEINPUT(
                int(x * 65535 / max(1, w - 1)),
                int(y * 65535 / max(1, h - 1)),
                0, MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, 0, 0,
            )
            items.append(item)
        elif event.kind == "button":
            down, up = _BUTTON_FLAGS.get(str(event.a), _BUTTON_FLAGS["left"])
            item = INPUT(type=INPUT_MOUSE)
            item.mi = MOUSEINPUT(0, 0, 0, down if event.b else up, 0, 0)
            items.append(item)
        elif event.kind == "scroll":
            item = INPUT(type=INPUT_MOUSE)
            item.mi = MOUSEINPUT(0, 0, 120 * int(event.b), MOUSEEVENTF_WHEEL, 0, 0)
            items.append(item)
        elif event.kind == "key":
            vk = _VK.get(str(event.a).lower())
            if vk:
                if event.b:
                    self._pressed.add(vk)
                else:
                    self._pressed.discard(vk)
                item = INPUT(type=INPUT_KEYBOARD)
                item.ki = KEYBDINPUT(vk, 0, 0 if event.b else KEYEVENTF_KEYUP, 0, 0)
                items.append(item)
        if items:
            user32.SendInput(len(items), (INPUT * len(items))(*items), ctypes.sizeof(INPUT))

    def release_all_keys(self) -> None:
        for vk in list(self._pressed):
            item = INPUT(type=INPUT_KEYBOARD)
            item.ki = KEYBDINPUT(vk, 0, KEYEVENTF_KEYUP, 0, 0)
            user32.SendInput(1, ctypes.byref(item), ctypes.sizeof(INPUT))
        self._pressed.clear()


def _vk_name(vk: int) -> str | None:
    for name, code in _VK.items():
        if code == vk:
            return name
    if 0x30 <= vk <= 0x39 or 0x41 <= vk <= 0x5A:
        return chr(vk).lower()
    return None
