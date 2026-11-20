from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import importlib
import sys
import unittest
from unittest import mock

from crossmouse.platform_base import InputEvent


class FakeFunc:
    def __init__(self) -> None:
        self.argtypes = None
        self.restype = None

    def __call__(self, *args):
        return 0


def deref(value):
    value = getattr(value, "_obj", value)
    return value.contents if hasattr(value, "contents") else value


class FakeDLL:
    def __init__(self, missing=()) -> None:
        self._funcs: dict[str, FakeFunc] = {}
        self._missing = set(missing)

    def __getattr__(self, name: str) -> FakeFunc:
        if name in self._missing:
            raise AttributeError(f"function '{name}' not found")
        if name not in self._funcs:
            self._funcs[name] = FakeFunc()
        return self._funcs[name]


def import_platform_win(dlls: dict[str, FakeDLL]):
    sys.modules.pop("crossmouse.platform_win", None)

    def fake_winfunctype(*args):
        return ctypes.CFUNCTYPE(*args)

    with mock.patch.object(ctypes, "WinDLL", create=True, side_effect=lambda name, **kw: dlls[name]), \
         mock.patch.object(ctypes, "WINFUNCTYPE", create=True, side_effect=fake_winfunctype):
        return importlib.import_module("crossmouse.platform_win")


class RawMouseFixture(ctypes.Structure):
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


class RawInputHeaderFixture(ctypes.Structure):
    _fields_ = [
        ("dwType", wintypes.DWORD),
        ("dwSize", wintypes.DWORD),
        ("hDevice", wintypes.HANDLE),
        ("wParam", wintypes.WPARAM),
    ]


class RawInputDataFixture(ctypes.Union):
    _fields_ = [("mouse", RawMouseFixture)]


class RawInputFixture(ctypes.Structure):
    _fields_ = [
        ("header", RawInputHeaderFixture),
        ("data", RawInputDataFixture),
    ]


def raw_mouse_bytes(dx: int, dy: int, flags: int = 0) -> bytes:
    raw = RawInputFixture(
        header=RawInputHeaderFixture(
            dwType=0,
            dwSize=ctypes.sizeof(RawInputFixture),
            hDevice=None,
            wParam=0,
        ),
        data=RawInputDataFixture(
            mouse=RawMouseFixture(
                usFlags=flags,
                _pad=0,
                usButtonFlags=0,
                usButtonData=0,
                ulRawButtons=0,
                lLastX=dx,
                lLastY=dy,
                ulExtraInformation=0,
            )
        ),
    )
    return bytes(raw)


class FakeShowCursor:
    def __init__(self, results) -> None:
        self.results = list(results)
        self.calls: list[bool] = []
        self.argtypes = None
        self.restype = None

    def __call__(self, show):
        self.calls.append(bool(show))
        return self.results.pop(0) if self.results else -1


def capture_mouse_hook():
    """Install the real Windows capture hooks with a fake user32 and return
    the mouse callback plus the events it forwards."""
    dlls = {"user32": FakeDLL(), "kernel32": FakeDLL()}
    procs = {}
    next_calls = []

    def set_hook(hook_id, proc, module, thread):
        procs[hook_id] = proc
        return 1

    def next_hook(*args):
        next_calls.append(args)
        return 0

    dlls["user32"]._funcs["SetWindowsHookExW"] = set_hook
    dlls["user32"]._funcs["CallNextHookEx"] = next_hook
    dlls["user32"]._funcs["RegisterClassW"] = lambda *args: 1
    dlls["user32"]._funcs["CreateWindowExW"] = lambda *args: 1
    dlls["user32"]._funcs["RegisterRawInputDevices"] = lambda *args: 1
    dlls["user32"]._funcs["GetMessageW"] = lambda *args: 0

    module = import_platform_win(dlls)
    platform = module.WindowsPlatform()
    sink = mock.Mock()
    platform.start_capture(sink)
    platform._thread.join(timeout=1)
    return module, platform, sink, procs[module.WH_MOUSE_LL], next_calls


def capture_raw_input(payload):
    """Start capture with fake Win32 calls and expose the raw-input window proc."""
    dlls = {
        "user32": FakeDLL(missing={"UnregisterRawInputDevices"}),
        "kernel32": FakeDLL(),
    }
    events = []
    state = {"wndproc": None, "registrations": []}

    def register_class(class_ptr):
        wc = deref(class_ptr)
        state["wndproc"] = wc.lpfnWndProc
        state["class_name"] = wc.lpszClassName
        return 1

    def create_window(*args):
        state["create_args"] = args
        return 1

    def register_raw_devices(devices, count, size):
        device = deref(devices)
        call = (
            device.usUsagePage,
            device.usUsage,
            device.dwFlags,
            device.hwndTarget,
            count,
            size,
        )
        state["registrations"].append(call)
        state["registration"] = call[:3] + call[4:]
        return 1

    def get_raw_input_data(handle, command, buffer, size_ptr, header_size):
        data = payload["data"]
        size_ptr = deref(size_ptr)
        if buffer is None:
            size_ptr.value = len(data)
            return 0
        ctypes.memmove(deref(buffer), data, len(data))
        return len(data)

    def destroy_window(hwnd):
        state["destroyed"] = hwnd
        return 1

    def unregister_class(name, module):
        state["class_unregistered"] = name
        return 1

    dlls["user32"]._funcs["RegisterClassW"] = register_class
    dlls["user32"]._funcs["CreateWindowExW"] = create_window
    dlls["user32"]._funcs["RegisterRawInputDevices"] = register_raw_devices
    dlls["user32"]._funcs["GetRawInputData"] = get_raw_input_data
    dlls["user32"]._funcs["DestroyWindow"] = destroy_window
    dlls["user32"]._funcs["UnregisterClassW"] = unregister_class
    dlls["user32"]._funcs["GetMessageW"] = lambda *args: 0

    module = import_platform_win(dlls)
    platform = module.WindowsPlatform()
    platform.start_capture(events.append)
    platform._thread.join(timeout=1)
    return module, platform, events, state


class WindowsMouseHookTests(unittest.TestCase):
    def test_mouse_move_reaches_system_without_forwarding_while_suppressed(self):
        module, platform, sink, mouse_proc, next_calls = capture_mouse_hook()
        platform.set_suppress(True)
        info = module.MSLLHOOKSTRUCT()
        info.pt.x, info.pt.y = 640, 360

        result = mouse_proc(module.HC_ACTION, module.WM_MOUSEMOVE, ctypes.addressof(info))

        sink.assert_not_called()
        self.assertEqual(len(next_calls), 1)
        self.assertEqual(result, 0)


class WindowsRawInputTests(unittest.TestCase):
    def test_relative_mouse_delta_is_forwarded(self):
        payload = {"data": raw_mouse_bytes(37, -12)}
        module, platform, events, state = capture_raw_input(payload)
        self.assertIsNotNone(state["wndproc"], "raw input window was not registered")

        state["wndproc"](1, 0x00FF, 0, 1)

        self.assertEqual(events, [InputEvent("move_rel", 37, -12)])

    def test_absolute_mouse_delta_is_ignored(self):
        payload = {"data": raw_mouse_bytes(100, 200, flags=0x01)}
        module, platform, events, state = capture_raw_input(payload)
        self.assertIsNotNone(state["wndproc"], "raw input window was not registered")

        state["wndproc"](1, 0x00FF, 0, 1)

        self.assertEqual(events, [])

    def test_raw_mouse_layout_matches_win32_abi(self):
        payload = {"data": raw_mouse_bytes(0, 0)}
        module, platform, events, state = capture_raw_input(payload)

        self.assertEqual(module.RAWMOUSE.usFlags.offset, 0)
        self.assertEqual(module.RAWMOUSE.usButtonFlags.offset, 4)
        self.assertEqual(module.RAWMOUSE.lLastX.offset, 12)
        self.assertEqual(ctypes.sizeof(module.RAWMOUSE), 24)

    def test_mouse_raw_input_device_is_registered_with_input_sink(self):
        payload = {"data": raw_mouse_bytes(0, 0)}
        module, platform, events, state = capture_raw_input(payload)

        self.assertEqual(state["registration"][:3], (1, 2, 0x100))
        self.assertEqual(state["registration"][3], 1)

    def test_stop_capture_unregisters_raw_input_device(self):
        payload = {"data": raw_mouse_bytes(0, 0)}
        module, platform, events, state = capture_raw_input(payload)

        platform.stop_capture()

        self.assertEqual(len(state["registrations"]), 2)
        removal = state["registrations"][1]
        self.assertEqual(removal[:3], (1, 2, module.RIDEV_REMOVE))
        self.assertIsNone(removal[3])


class WindowsPointerVisibilityTests(unittest.TestCase):
    def test_hide_cursor_repeats_until_cursor_counter_is_negative(self):
        dlls = {"user32": FakeDLL(), "kernel32": FakeDLL()}
        show = FakeShowCursor([0, -1])
        dlls["user32"]._funcs["ShowCursor"] = show
        module = import_platform_win(dlls)

        platform = module.WindowsPlatform()
        platform.set_pointer_visible(False)

        self.assertEqual(show.calls, [False, False])
        self.assertTrue(platform._pointer_hidden)
        self.assertEqual(show.argtypes, [wintypes.BOOL])
        self.assertIs(show.restype, ctypes.c_int)

    def test_hide_cursor_replaces_system_cursors_and_restores_them(self):
        cursor_ids = [
            32512, 32513, 32514, 32515, 32516,
            32642, 32643, 32644, 32645, 32646, 32648, 32649, 32650,
        ]
        dlls = {"user32": FakeDLL(), "kernel32": FakeDLL()}
        dlls["user32"]._funcs["ShowCursor"] = FakeShowCursor([0, -1, 0])
        calls = []

        def load_cursor(instance, cursor_id):
            calls.append(("load", cursor_id))
            return 1000 + cursor_id

        def copy_icon(handle):
            calls.append(("copy", handle))
            return 5000 + handle

        def create_cursor(*args):
            calls.append(("blank", args))
            return 9000

        def set_system_cursor(handle, cursor_id):
            calls.append(("set", cursor_id, handle))

        dlls["user32"]._funcs["LoadCursorW"] = load_cursor
        dlls["user32"]._funcs["CopyIcon"] = copy_icon
        dlls["user32"]._funcs["CreateCursor"] = create_cursor
        dlls["user32"]._funcs["SetSystemCursor"] = set_system_cursor

        module = import_platform_win(dlls)
        platform = module.WindowsPlatform()

        platform.set_pointer_visible(False)

        self.assertEqual(
            [call[1] for call in calls if call[0] == "load"],
            cursor_ids,
        )
        hidden = [call for call in calls if call[0] == "set"]
        self.assertEqual([call[1] for call in hidden], cursor_ids)
        self.assertTrue(all(call[2] == 9000 for call in hidden))

        platform.set_pointer_visible(True)

        restored = [call for call in calls if call[0] == "set"][len(cursor_ids):]
        self.assertEqual(
            [call[2] for call in restored],
            [5000 + 1000 + cursor_id for cursor_id in cursor_ids],
        )

    def test_show_cursor_repeats_until_cursor_counter_is_non_negative(self):
        dlls = {"user32": FakeDLL(), "kernel32": FakeDLL()}
        show = FakeShowCursor([-1, 0])
        dlls["user32"]._funcs["ShowCursor"] = show
        module = import_platform_win(dlls)

        platform = module.WindowsPlatform()
        platform._pointer_hidden = True
        platform.set_pointer_visible(True)

        self.assertEqual(show.calls, [True, True])
        self.assertFalse(platform._pointer_hidden)


class WindowsModuleImportTests(unittest.TestCase):
    def test_platform_win_imports_without_wintypes_lresult(self):
        module = import_platform_win({"user32": FakeDLL(), "kernel32": FakeDLL()})
        self.assertTrue(callable(module.HOOKPROC))

    def test_platform_win_imports_without_unexported_raw_input_api(self):
        dlls = {
            "user32": FakeDLL(missing={"UnregisterRawInputDevices"}),
            "kernel32": FakeDLL(),
        }

        module = import_platform_win(dlls)

        self.assertEqual(module.RIDEV_REMOVE, 0x00000001)


class Windows64BitPrototypeTests(unittest.TestCase):
    def test_wndclass_cursor_field_uses_portable_handle(self):
        module = import_platform_win({"user32": FakeDLL(), "kernel32": FakeDLL()})
        fields = dict(module.WNDCLASSW._fields_)
        self.assertIs(fields["hCursor"], wintypes.HANDLE)

    def test_pointer_sized_results_have_pointer_sized_restypes(self):
        dlls = {"user32": FakeDLL(), "kernel32": FakeDLL()}
        import_platform_win(dlls)

        self.assertIs(dlls["kernel32"].GetModuleHandleW.restype, wintypes.HMODULE)
        self.assertIs(dlls["user32"].SetWindowsHookExW.restype, wintypes.HHOOK)
        self.assertIs(dlls["user32"].CallNextHookEx.restype, ctypes.c_ssize_t)
        self.assertIs(dlls["user32"].DispatchMessageW.restype, ctypes.c_ssize_t)

    def test_handle_arguments_are_declared(self):
        dlls = {"user32": FakeDLL(), "kernel32": FakeDLL()}
        import_platform_win(dlls)

        self.assertEqual(dlls["kernel32"].GetModuleHandleW.argtypes, [wintypes.LPCWSTR])
        self.assertEqual(dlls["user32"].SetWindowsHookExW.argtypes[2], wintypes.HMODULE)
        self.assertEqual(dlls["user32"].CallNextHookEx.argtypes[0], wintypes.HHOOK)
        self.assertEqual(dlls["user32"].UnhookWindowsHookEx.argtypes, [wintypes.HHOOK])


if __name__ == "__main__":
    unittest.main()
