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
WM_INPUT = 0x00FF
RID_INPUT = 0x10000003
RIM_TYPEMOUSE = 0
RIDEV_INPUTSINK = 0x00000100
HID_USAGE_PAGE_GENERIC = 1
HID_USAGE_GENERIC_MOUSE = 2
MOUSE_MOVE_ABSOLUTE = 0x01
MOUSE_ATTRIBUTES_CHANGED = 0x04
HWND_MESSAGE = wintypes.HWND(-3)

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


# LRESULT is LONG_PTR; ctypes.wintypes does not define it.
LRESULT = ctypes.c_ssize_t
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
WNDPROC = ctypes.WINFUNCTYPE(
    LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
)


class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [
        ("usUsagePage", wintypes.USHORT),
        ("usUsage", wintypes.USHORT),
        ("dwFlags", wintypes.DWORD),
        ("hwndTarget", wintypes.HWND),
    ]


class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [
        ("dwType", wintypes.DWORD),
        ("dwSize", wintypes.DWORD),
        ("hDevice", wintypes.HANDLE),
        ("wParam", wintypes.WPARAM),
    ]


class RAWMOUSE(ctypes.Structure):
    _fields_ = [
        ("usFlags", wintypes.USHORT),
        ("_pad", wintypes.USHORT),
        ("usButtonFlags", wintypes.USHORT),
        ("usButtonData", wintypes.USHORT),
        ("ulRawButtons", ctypes.c_uint32),
        ("lLastX", ctypes.c_int32),
        ("lLastY", ctypes.c_int32),
        ("ulExtraInformation", ctypes.c_uint32),
    ]


class _RAWINPUTDATA(ctypes.Union):
    _fields_ = [("mouse", RAWMOUSE)]


class RAWINPUT(ctypes.Structure):
    _fields_ = [("header", RAWINPUTHEADER), ("data", _RAWINPUTDATA)]


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HCURSOR),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]

# ctypes defaults to 32-bit int for undeclared arguments and results. On 64-bit
# Windows that truncates HMODULE/HHOOK handles and LRESULT values.
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE

user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.GetSystemMetrics.restype = ctypes.c_int
user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
user32.GetCursorPos.restype = wintypes.BOOL
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.SetCursorPos.restype = wintypes.BOOL
user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HMODULE, wintypes.DWORD]
user32.SetWindowsHookExW.restype = wintypes.HHOOK
user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
user32.CallNextHookEx.restype = LRESULT
user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
user32.UnhookWindowsHookEx.restype = wintypes.BOOL
user32.GetMessageW.argtypes = [ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype = wintypes.BOOL
user32.TranslateMessage.argtypes = [ctypes.POINTER(MSG)]
user32.TranslateMessage.restype = wintypes.BOOL
user32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]
user32.DispatchMessageW.restype = LRESULT
user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT
user32.ShowCursor.argtypes = [wintypes.BOOL]
user32.ShowCursor.restype = ctypes.c_int
user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
user32.RegisterClassW.restype = wintypes.ATOM
user32.CreateWindowExW.argtypes = [
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
]
user32.CreateWindowExW.restype = wintypes.HWND
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = LRESULT
user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.DestroyWindow.restype = wintypes.BOOL
user32.UnregisterClassW.argtypes = [wintypes.LPCWSTR, wintypes.HINSTANCE]
user32.UnregisterClassW.restype = wintypes.BOOL
user32.RegisterRawInputDevices.argtypes = [ctypes.POINTER(RAWINPUTDEVICE), wintypes.UINT, wintypes.UINT]
user32.RegisterRawInputDevices.restype = wintypes.BOOL
user32.UnregisterRawInputDevices.argtypes = [ctypes.POINTER(RAWINPUTDEVICE), wintypes.UINT, wintypes.UINT]
user32.UnregisterRawInputDevices.restype = wintypes.BOOL
user32.GetRawInputData.argtypes = [
    wintypes.HANDLE, wintypes.UINT, wintypes.LPVOID,
    ctypes.POINTER(wintypes.UINT), wintypes.UINT,
]
user32.GetRawInputData.restype = wintypes.UINT


class WindowsPlatform(Platform):
    def __init__(self) -> None:
        self._sink: EventSink | None = None
        self._thread: threading.Thread | None = None
        self._hooks: list = []
        self._pressed: set[int] = set()
        self._suppress = False
        self._pointer_hidden = False
        self._window = None
        self._class_name = None
        self._raw_device: RAWINPUTDEVICE | None = None
        self._mouse_proc = None
        self._keyboard_proc = None
        self._window_proc = None

    def set_suppress(self, value: bool) -> None:
        self._suppress = value

    def set_pointer_visible(self, visible: bool) -> None:
        if self._pointer_hidden != (not visible):
            if visible:
                while user32.ShowCursor(True) < 0:
                    pass
            else:
                while user32.ShowCursor(False) >= 0:
                    pass
            self._pointer_hidden = not visible

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
            out = None
            if code == HC_ACTION and self._sink:
                info = ctypes.cast(lparam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                if wparam == WM_MOUSEMOVE:
                    # While controlling, relative movement comes from Raw Input;
                    # absolute hook coordinates are only used for edge detection.
                    if not self._suppress:
                        out = InputEvent("move", info.pt.x, info.pt.y)
                elif wparam in (WM_LBUTTONDOWN, WM_LBUTTONUP):
                    out = InputEvent("button", "left", int(wparam == WM_LBUTTONDOWN))
                elif wparam in (WM_RBUTTONDOWN, WM_RBUTTONUP):
                    out = InputEvent("button", "right", int(wparam == WM_RBUTTONDOWN))
                elif wparam in (WM_MBUTTONDOWN, WM_MBUTTONUP):
                    out = InputEvent("button", "middle", int(wparam == WM_MBUTTONDOWN))
                elif wparam == WM_MOUSEWHEEL:
                    delta = ctypes.c_short(info.mouseData >> 16).value
                    out = InputEvent("scroll", 0, 1 if delta > 0 else -1)
                if out is not None and self.is_own_injection(out):
                    out = None
                if out is not None:
                    self._sink(out)
            if self._suppress and wparam != WM_MOUSEMOVE:
                return 1
            return user32.CallNextHookEx(None, code, wparam, lparam)

        @HOOKPROC
        def keyboard_proc(code, wparam, lparam):
            if code == HC_ACTION and self._sink:
                info = ctypes.cast(lparam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                key = _vk_name(info.vkCode)
                if key:
                    down = wparam in (WM_KEYDOWN, WM_SYSKEYDOWN)
                    out = InputEvent("key", key, int(down))
                    if not self.is_own_injection(out):
                        self._sink(out)
            if self._suppress:
                return 1
            return user32.CallNextHookEx(None, code, wparam, lparam)

        @WNDPROC
        def window_proc(hwnd, msg, wparam, lparam):
            if msg == WM_INPUT and self._sink:
                self._handle_raw_input(lparam)
                return 0
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        # Keep callbacks alive for as long as the hooks and window are installed.
        self._mouse_proc = mouse_proc
        self._keyboard_proc = keyboard_proc
        self._window_proc = window_proc

        wc = WNDCLASSW()
        wc.lpfnWndProc = window_proc
        wc.hInstance = module
        wc.lpszClassName = f"CrossMouseRawInput-{id(self)}"
        if not user32.RegisterClassW(ctypes.byref(wc)):
            return
        self._class_name = wc.lpszClassName
        self._window = user32.CreateWindowExW(
            0, self._class_name, "", 0, 0, 0, 0, 0,
            HWND_MESSAGE, None, module, None,
        )
        if not self._window:
            user32.UnregisterClassW(self._class_name, module)
            self._class_name = None
            return
        device = RAWINPUTDEVICE(
            HID_USAGE_PAGE_GENERIC,
            HID_USAGE_GENERIC_MOUSE,
            RIDEV_INPUTSINK,
            self._window,
        )
        if not user32.RegisterRawInputDevices(
            ctypes.byref(device), 1, ctypes.sizeof(device)
        ):
            user32.DestroyWindow(self._window)
            self._window = None
            user32.UnregisterClassW(self._class_name, module)
            self._class_name = None
            return
        self._raw_device = device

        self._hooks = [
            user32.SetWindowsHookExW(WH_MOUSE_LL, mouse_proc, module, 0),
            user32.SetWindowsHookExW(WH_KEYBOARD_LL, keyboard_proc, module, 0),
        ]
        msg = MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def _handle_raw_input(self, handle) -> None:
        size = wintypes.UINT()
        header_size = ctypes.sizeof(RAWINPUTHEADER)
        result = user32.GetRawInputData(
            handle, RID_INPUT, None, ctypes.byref(size), header_size
        )
        if result == 0xFFFFFFFF or size.value == 0:
            return
        buffer = ctypes.create_string_buffer(size.value)
        copied = user32.GetRawInputData(
            handle, RID_INPUT, buffer, ctypes.byref(size), header_size
        )
        if copied in (0, 0xFFFFFFFF):
            return
        raw = ctypes.cast(buffer, ctypes.POINTER(RAWINPUT)).contents
        if raw.header.dwType != RIM_TYPEMOUSE:
            return
        mouse = raw.data.mouse
        if mouse.usFlags & (MOUSE_MOVE_ABSOLUTE | MOUSE_ATTRIBUTES_CHANGED):
            return
        dx, dy = mouse.lLastX, mouse.lLastY
        if dx or dy:
            self._sink(InputEvent("move_rel", dx, dy))

    def stop_capture(self) -> None:
        if self._raw_device is not None:
            user32.UnregisterRawInputDevices(
                ctypes.byref(self._raw_device),
                1,
                ctypes.sizeof(self._raw_device),
            )
            self._raw_device = None
        if self._window:
            user32.DestroyWindow(self._window)
            self._window = None
        if self._class_name:
            user32.UnregisterClassW(
                self._class_name, kernel32.GetModuleHandleW(None)
            )
            self._class_name = None
        for hook in self._hooks:
            if hook:
                user32.UnhookWindowsHookEx(hook)
        self._hooks = []
        self._sink = None
        self._mouse_proc = None
        self._keyboard_proc = None
        self._window_proc = None

    def inject(self, event: InputEvent) -> None:
        if event.kind == "scroll":
            self.remember_injection(
                InputEvent("scroll", 0, 1 if int(event.b) > 0 else -1)
            )
        else:
            self.remember_injection(event)
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
