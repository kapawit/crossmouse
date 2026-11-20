from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest import mock


class FakeRoot:
    def __init__(self) -> None:
        self.pointer_grabs = []
        self.keyboard_grabs = []
        self.show_cursor_calls = 0
        self.hide_cursor_calls = 0

    def grab_pointer(self, *args) -> None:
        self.pointer_grabs.append(args)

    def grab_keyboard(self, *args) -> None:
        self.keyboard_grabs.append(args)

    def xfixes_show_cursor(self) -> None:
        self.show_cursor_calls += 1

    def xfixes_hide_cursor(self) -> None:
        self.hide_cursor_calls += 1


class FakeDisplay:
    def __init__(self, root: FakeRoot) -> None:
        self.root = root
        self.display = mock.Mock()
        self.ungrab_keyboard = mock.Mock()

    def screen(self):
        return SimpleNamespace(root=self.root)

    def flush(self) -> None:
        pass

    def ungrab_pointer(self, *args) -> None:
        pass


class LinuxGrabTests(unittest.TestCase):
    def test_handoff_grabs_keyboard_as_well_as_pointer(self):
        from crossmouse.platform_linux import LinuxPlatform

        root = FakeRoot()
        fake_display = FakeDisplay(root)
        with mock.patch(
            "crossmouse.platform_linux.display.Display", return_value=fake_display
        ):
            platform = LinuxPlatform()

        platform.grab()

        self.assertEqual(len(root.pointer_grabs), 1)
        self.assertEqual(len(root.keyboard_grabs), 1)

        platform.ungrab()

        fake_display.ungrab_keyboard.assert_called_once()

    def test_show_cursor_is_forced_even_if_state_says_visible(self):
        from crossmouse.platform_linux import LinuxPlatform

        root = FakeRoot()
        fake_display = FakeDisplay(root)
        with mock.patch(
            "crossmouse.platform_linux.display.Display", return_value=fake_display
        ):
            platform = LinuxPlatform()

        platform.set_pointer_visible(True)

        self.assertEqual(root.show_cursor_calls, 1)
