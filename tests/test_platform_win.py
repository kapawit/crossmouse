from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import importlib
import queue
import sys
import time
import unittest
from unittest import mock


class FakeFunc:
    def __init__(self) -> None:
        self.argtypes = None
        self.restype = None

    def __call__(self, *args):
        return 0


class FakeDLL:
    def __init__(self) -> None:
        self._funcs: dict[str, FakeFunc] = {}

    def __getattr__(self, name: str) -> FakeFunc:
        if name not in self._funcs:
            self._funcs[name] = FakeFunc()
        return self._funcs[name]


def import_platform_win(dlls: dict[str, FakeDLL]):
    sys.modules.pop("crossmouse.platform_win", None)

    def fake_winfunctype(*args):
        return lambda func: func

    with mock.patch.object(ctypes, "WinDLL", create=True, side_effect=lambda name, **kw: dlls[name]), \
         mock.patch.object(ctypes, "WINFUNCTYPE", create=True, side_effect=fake_winfunctype):
        return importlib.import_module("crossmouse.platform_win")


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
    dlls["user32"]._funcs["GetMessageW"] = lambda *args: 0

    module = import_platform_win(dlls)
    platform = module.WindowsPlatform()
    sink = mock.Mock()
    platform.start_capture(sink)
    platform._thread.join(timeout=1)
    return module, platform, sink, procs[module.WH_MOUSE_LL], next_calls


def capture_mouse_hook_with_loop():
    """Capture the hook with a message loop that can be stepped from the test."""
    dlls = {"user32": FakeDLL(), "kernel32": FakeDLL()}
    procs = {}
    set_cursor_calls = []
    messages = queue.Queue()

    def set_hook(hook_id, proc, module, thread):
        procs[hook_id] = proc
        return 1

    def set_cursor(x, y):
        set_cursor_calls.append((x, y))
        return 1

    def get_message(msg, hwnd, min_msg, max_msg):
        return messages.get(timeout=2)

    dlls["user32"]._funcs["SetWindowsHookExW"] = set_hook
    dlls["user32"]._funcs["CallNextHookEx"] = lambda *args: 0
    dlls["user32"]._funcs["SetCursorPos"] = set_cursor
    dlls["user32"]._funcs["GetMessageW"] = get_message

    module = import_platform_win(dlls)
    platform = module.WindowsPlatform()
    platform.start_capture(lambda event: platform.set_pointer(640, 360))
    deadline = time.monotonic() + 2
    while module.WH_MOUSE_LL not in procs and time.monotonic() < deadline:
        time.sleep(0.01)
    return module, platform, procs[module.WH_MOUSE_LL], set_cursor_calls, messages


class WindowsMouseHookTests(unittest.TestCase):
    def test_mouse_move_still_reaches_the_system_while_suppressed(self):
        module, platform, _, mouse_proc, next_calls = capture_mouse_hook()
        platform.set_suppress(True)
        info = module.MSLLHOOKSTRUCT()
        info.pt.x, info.pt.y = 640, 360

        result = mouse_proc(module.HC_ACTION, module.WM_MOUSEMOVE, ctypes.byref(info))

        self.assertEqual(len(next_calls), 1)
        self.assertEqual(result, 0)

    def test_pointer_warp_waits_until_after_hook_processing(self):
        module, platform, mouse_proc, set_cursor_calls, messages = capture_mouse_hook_with_loop()
        info = module.MSLLHOOKSTRUCT()
        info.pt.x, info.pt.y = 100, 200
        try:
            mouse_proc(module.HC_ACTION, module.WM_MOUSEMOVE, ctypes.byref(info))

            self.assertEqual(set_cursor_calls, [])

            messages.put(1)
            deadline = time.monotonic() + 2
            while not set_cursor_calls and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertEqual(set_cursor_calls, [(640, 360)])
        finally:
            messages.put(0)
            platform._thread.join(timeout=2)

    def test_own_pointer_warp_is_not_forwarded_as_user_movement(self):
        module, platform, sink, mouse_proc, _ = capture_mouse_hook()
        platform.set_pointer(640, 360)
        info = module.MSLLHOOKSTRUCT()
        info.pt.x, info.pt.y = 640, 360

        mouse_proc(module.HC_ACTION, module.WM_MOUSEMOVE, ctypes.byref(info))

        sink.assert_not_called()


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


class Windows64BitPrototypeTests(unittest.TestCase):
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
