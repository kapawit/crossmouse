from __future__ import annotations

import unittest

from PySide6 import QtCore, QtWidgets

from crossmouse.config import Config


class FakeApp:
    def __init__(self, status=None):
        self.status_data = status or {
            "connected": False,
            "paused": True,
            "connecting": False,
            "mode": "idle",
            "role": "listener",
            "peer_ip": None,
            "local_ip": "10.0.0.5",
            "port": 52800,
            "edge": "right",
            "clipboard": True,
            "primary": True,
            "debug": False,
            "local_screen": [1920, 1080],
            "peer_screen": [0, 0],
        }
        self.config = Config(secret="test-secret")
        self.calls = []

    def status(self):
        return dict(self.status_data)

    def log_lines(self):
        return ["12:00:00  started"]

    def save_config(self, data):
        self.calls.append(("save_config", data))

    def set_debug(self, enabled):
        self.calls.append(("set_debug", enabled))

    def reconnect(self):
        self.calls.append(("reconnect",))

    def disconnect(self):
        self.calls.append(("disconnect",))

    def handoff(self):
        self.calls.append(("handoff",))

    def stop(self):
        self.calls.append(("stop",))


class NativeUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_status_poll_updates_widgets(self):
        from crossmouse.native_ui import NativeWindow

        app = FakeApp()
        window = NativeWindow(app)
        window.refresh()
        self.assertEqual(
            window.findChild(QtWidgets.QLabel, "link_text").text(), "Disconnected"
        )

    def test_disconnected_state_has_no_details(self):
        from crossmouse.native_ui import NativeWindow

        status = {
            "connected": False,
            "paused": True,
            "role": "listener",
            "local_ip": "10.0.0.5",
            "port": 52800,
        }
        window = NativeWindow(FakeApp(status=status))
        window.refresh()
        self.assertEqual(
            window.findChild(QtWidgets.QLabel, "address_strip").text(),
            "Listening on 10.0.0.5:52800",
        )
        self.assertTrue(window.findChild(QtWidgets.QWidget, "detail_rows").isHidden())

    def test_connect_switch_calls_reconnect(self):
        from crossmouse.native_ui import NativeWindow

        app = FakeApp()
        window = NativeWindow(app)
        window.findChild(QtWidgets.QPushButton, "connect_switch").click()
        self.assertEqual(app.calls, [("reconnect",)])

    def test_selector_disabled_while_connected(self):
        from crossmouse.native_ui import NativeWindow

        app = FakeApp(status={"connected": True, "role": "listener"})
        window = NativeWindow(app)
        window.refresh()
        self.assertFalse(window.findChild(QtWidgets.QPushButton, "role_listener").isEnabled())

    def test_save_config_sends_expected_dict(self):
        from crossmouse.native_ui import NativeWindow

        app = FakeApp()
        window = NativeWindow(app)
        window.open_settings()
        window.findChild(QtWidgets.QLineEdit, "port_field").setText("6000")
        window.findChild(QtWidgets.QPushButton, "save_button").click()
        self.assertEqual(app.calls[-1][0], "save_config")
        self.assertEqual(app.calls[-1][1]["port"], 6000)

    def test_close_hides_window_instead_of_stopping(self):
        from unittest import mock

        from crossmouse.native_ui import NativeWindow

        app = FakeApp()
        with mock.patch.object(
            QtWidgets.QSystemTrayIcon, "isSystemTrayAvailable", return_value=True
        ):
            window = NativeWindow(app)
            window.close()
        self.assertTrue(window.isHidden())
        self.assertNotIn(("stop",), app.calls)

    def test_close_stops_app_without_tray(self):
        from unittest import mock

        from crossmouse.native_ui import NativeWindow

        app = FakeApp()
        with mock.patch.object(
            QtWidgets.QSystemTrayIcon, "isSystemTrayAvailable", return_value=False
        ):
            window = NativeWindow(app)
            window.close()
        self.assertIn(("stop",), app.calls)

    def test_quit_tray_action_stops_app(self):
        from crossmouse.native_ui import NativeWindow

        app = FakeApp()
        window = NativeWindow(app)
        window.quit_from_tray()
        self.assertIn(("stop",), app.calls)

    def test_connecting_switch_cancels_connection(self):
        from crossmouse.native_ui import NativeWindow

        status = {
            "connected": False,
            "connecting": True,
            "paused": False,
            "role": "controller",
            "peer_ip": "1.2.3.4",
        }
        app = FakeApp(status=status)
        window = NativeWindow(app)
        window.refresh()
        window.findChild(QtWidgets.QPushButton, "connect_switch").click()
        self.assertEqual(app.calls, [("disconnect",)])

    def test_connector_role_maps_to_controller_pill(self):
        from crossmouse.native_ui import NativeWindow

        app = FakeApp(status={"connected": True, "role": "connector"})
        window = NativeWindow(app)
        window.refresh()
        self.assertTrue(window.findChild(QtWidgets.QPushButton, "role_controller").isChecked())

    def test_invalid_port_shows_error_and_keeps_sheet_open(self):
        from crossmouse.native_ui import NativeWindow

        app = FakeApp()
        window = NativeWindow(app)
        window.open_settings()
        window.findChild(QtWidgets.QLineEdit, "port_field").setText("abc")
        window.findChild(QtWidgets.QPushButton, "save_button").click()
        error = window.findChild(QtWidgets.QLabel, "config_error")
        self.assertTrue(error.text())
        self.assertEqual(app.calls, [])
        self.assertEqual(window.pages.currentWidget().objectName(), "settings_sheet")

    def test_window_is_frameless_with_stylesheet(self):
        from crossmouse.native_ui import NativeWindow

        window = NativeWindow(FakeApp())
        self.assertTrue(window.windowFlags() & QtCore.Qt.FramelessWindowHint)
        self.assertIn("QPushButton", window.styleSheet())


if __name__ == "__main__":
    unittest.main()
