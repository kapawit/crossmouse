from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import importlib
import sys
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
