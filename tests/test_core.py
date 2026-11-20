from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from crossmouse import crypto, protocol
from crossmouse.config import Config


class ConfigTests(unittest.TestCase):
    def test_from_dict(self):
        c = Config.from_dict({"secret": "s", "peer_ip": "1.2.3.4", "port": 6000, "edge": "left"})
        self.assertEqual(c.peer_ip, "1.2.3.4")
        self.assertEqual(c.port, 6000)
        self.assertEqual(c.edge, "left")
        self.assertTrue(c.clipboard)
        self.assertTrue(c.primary)

    def test_primary_flag(self):
        self.assertFalse(Config.from_dict({"secret": "s", "primary": False}).primary)

    def test_defaults(self):
        c = Config.from_dict({"secret": "s"})
        self.assertEqual(c.port, 52800)
        self.assertEqual(c.edge, "right")
        self.assertFalse(c.debug)

    def test_debug_round_trip(self):
        c = Config.from_dict({"secret": "s", "debug": True})
        self.assertTrue(c.to_dict()["debug"])

    def test_rejects_bad_edge(self):
        with self.assertRaises(ValueError):
            Config.from_dict({"secret": "s", "edge": "diagonal"})

    def test_rejects_empty_secret(self):
        with self.assertRaises(ValueError):
            Config.from_dict({"secret": ""})

    def test_rejects_bad_port(self):
        with self.assertRaises(ValueError):
            Config.from_dict({"secret": "s", "port": 99999})


class ConfigBootstrapTests(unittest.TestCase):
    def test_ensure_config_creates_once(self):
        from crossmouse.main import ensure_config

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "crossmouse" / "config.json"
            ensure_config(path)
            self.assertEqual(Config.from_file(path).port, 52800)
            self.assertTrue(Config.from_file(path).secret)
            first = path.read_text()
            ensure_config(path)
            self.assertEqual(path.read_text(), first)


class LocalIpTests(unittest.TestCase):
    def test_local_ip_uses_lan_address_from_probe_socket(self):
        from crossmouse.main import local_ip_address

        with mock.patch("crossmouse.main.socket.socket") as factory:
            factory.return_value.getsockname.return_value = ("192.168.1.23", 43210)
            self.assertEqual(local_ip_address(), "192.168.1.23")

    def test_local_ip_falls_back_to_loopback_without_network(self):
        from crossmouse.main import local_ip_address

        with mock.patch("crossmouse.main.socket.socket") as factory:
            factory.return_value.connect.side_effect = OSError("no network")
            self.assertEqual(local_ip_address(), "127.0.0.1")


class AppStatusTests(unittest.TestCase):
    def test_status_exposes_local_ip_for_listener_address(self):
        from crossmouse.main import App

        app = App.__new__(App)
        app.connected = False
        app._paused = False
        app._last_error = None
        app.role = "listener"
        app.config = Config.from_dict({"secret": "s"})
        app.engine = SimpleNamespace(mode="idle", local_screen=(1920, 1080), peer_screen=(0, 0))
        app._ui_port = 7788

        with mock.patch("crossmouse.main.local_ip_address", return_value="192.168.1.23"):
            status = app.status()

        self.assertEqual(status["local_ip"], "192.168.1.23")

    def test_status_includes_debug_flag(self):
        from crossmouse.main import App

        app = App.__new__(App)
        app.connected = False
        app._paused = False
        app._last_error = None
        app.role = "listener"
        app.config = Config.from_dict({"secret": "s", "debug": True})
        app.engine = SimpleNamespace(mode="idle", local_screen=(1920, 1080), peer_screen=(0, 0))
        app._ui_port = 7788

        with mock.patch("crossmouse.main.local_ip_address", return_value="127.0.0.1"):
            status = app.status()

        self.assertTrue(status["debug"])

    def test_status_distinguishes_connected_from_connecting(self):
        from crossmouse.main import App

        app = App.__new__(App)
        app.connected = False
        app._paused = False
        app.role = "controller"
        app.config = Config.from_dict({"secret": "s", "peer_ip": "192.168.1.5"})
        app.engine = SimpleNamespace(mode="idle", local_screen=(1920, 1080), peer_screen=(0, 0))
        app._ui_port = 7788
        app._last_error = None

        with mock.patch("crossmouse.main.local_ip_address", return_value="192.168.1.10"):
            status = app.status()

        self.assertFalse(status["connected"])
        self.assertFalse(status["paused"])
        self.assertTrue(status["connecting"])

    def test_status_exposes_last_connect_error(self):
        from crossmouse.main import App

        app = App.__new__(App)
        app.connected = False
        app._paused = True
        app.role = "controller"
        app.config = Config.from_dict({"secret": "s", "peer_ip": "192.168.1.5"})
        app.engine = SimpleNamespace(mode="idle", local_screen=(1920, 1080), peer_screen=(0, 0))
        app._ui_port = 7788
        app._last_error = "Connection refused"

        with mock.patch("crossmouse.main.local_ip_address", return_value="192.168.1.10"):
            status = app.status()

        self.assertEqual(status["last_error"], "Connection refused")

    def test_status_reports_listener_as_not_connecting(self):
        from crossmouse.main import App

        app = App.__new__(App)
        app.connected = False
        app._paused = False
        app._last_error = None
        app.role = "listener"
        app.config = Config.from_dict({"secret": "s"})
        app.engine = SimpleNamespace(mode="idle", local_screen=(1920, 1080), peer_screen=(0, 0))
        app._ui_port = 7788

        with mock.patch("crossmouse.main.local_ip_address", return_value="192.168.1.10"):
            status = app.status()

        self.assertFalse(status["connecting"])


class AppDebugTests(unittest.TestCase):
    def _app(self, directory: str) -> "App":
        from crossmouse.main import App

        app = App.__new__(App)
        app.config_path = Path(directory) / "config.json"
        app.config = Config.from_dict({"secret": "s"})
        app.config_path.write_text(json.dumps(app.config.to_dict()))
        app.engine = SimpleNamespace(config=app.config)
        app._reconnect = mock.Mock()
        app._debug_logger = None
        app._log = mock.Mock()
        return app

    def test_set_debug_persists_without_reconnect(self):
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            app = self._app(directory)
            log_path = Path(directory) / "debug.log"
            with mock.patch("crossmouse.main.debug_log_path", return_value=log_path):
                app.set_debug(True)
            try:
                self.assertTrue(json.loads(app.config_path.read_text())["debug"])
                self.assertTrue(app.config.debug)
                self.assertTrue(app.engine.config.debug)
                self.assertIsNotNone(app._debug_logger)
                app._reconnect.set.assert_not_called()
            finally:
                if app._debug_logger:
                    app._debug_logger.close()

    def test_set_debug_off_closes_logger(self):
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            app = self._app(directory)
            logger = mock.Mock()
            app._debug_logger = logger
            app.config = Config.from_dict({"secret": "s", "debug": True})
            app.engine.config = app.config
            app.config_path.write_text(json.dumps(app.config.to_dict()))

            app.set_debug(False)

            logger.close.assert_called_once_with()
            self.assertIsNone(app._debug_logger)
            self.assertFalse(json.loads(app.config_path.read_text())["debug"])

    def test_save_config_preserves_debug(self):
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            app = self._app(directory)
            app.config = Config.from_dict({"secret": "s", "debug": True})
            app.engine.config = app.config
            app.config_path.write_text(json.dumps(app.config.to_dict()))

            app.save_config({"peer_ip": "1.2.3.4"})

            self.assertTrue(json.loads(app.config_path.read_text())["debug"])
            self.assertTrue(app.config.debug)

    def test_toggling_off_stops_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            app = self._app(directory)
            log_path = Path(directory) / "debug.log"
            with mock.patch("crossmouse.main.debug_log_path", return_value=log_path):
                app.set_debug(True)
            try:
                app._debug("while-on")
                app.set_debug(False)
                app._debug("after-off")
                text = log_path.read_text()
                self.assertIn("while-on", text)
                self.assertNotIn("after-off", text)
            finally:
                if app._debug_logger:
                    app._debug_logger.close()

    def test_set_debug_updates_engine_sink(self):
        with tempfile.TemporaryDirectory() as directory:
            app = self._app(directory)
            log_path = Path(directory) / "debug.log"
            with mock.patch("crossmouse.main.debug_log_path", return_value=log_path):
                app.set_debug(True)
            try:
                self.assertIsNotNone(app.engine.debug_sink)
                app.set_debug(False)
                self.assertIsNone(app.engine.debug_sink)
            finally:
                if app._debug_logger:
                    app._debug_logger.close()

    def test_set_debug_write_failure_preserves_state(self):
        with tempfile.TemporaryDirectory() as directory:
            app = self._app(directory)
            original = json.loads(app.config_path.read_text())
            with mock.patch.object(Path, "write_text", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    app.set_debug(True)
            self.assertEqual(json.loads(app.config_path.read_text()), original)
            self.assertFalse(app.config.debug)

    def test_startup_with_persisted_debug_opens_log(self):
        from crossmouse.main import App

        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.json"
            config_path.write_text(json.dumps({"secret": "s", "debug": True}))
            log_path = Path(directory) / "debug.log"
            platform = mock.Mock()
            platform.screen_size.return_value = (800, 600)
            engine = SimpleNamespace(
                config=None,
                mode="idle",
                local_screen=(800, 600),
                peer_screen=(0, 0),
                local_event=mock.Mock(),
                debug_snapshot=mock.Mock(),
            )
            with (
                mock.patch("crossmouse.main.make_platform", return_value=platform),
                mock.patch("crossmouse.main.make_clipboard", return_value=mock.Mock()),
                mock.patch("crossmouse.main.Engine", return_value=engine),
                mock.patch("crossmouse.main.debug_log_path", return_value=log_path),
            ):
                app = App(config_path, enable_ui=False, open_browser=False)
            try:
                self.assertIsNotNone(app._debug_logger)
                self.assertIn("Startup with debug logging enabled", log_path.read_text())
            finally:
                if app._debug_logger:
                    app._debug_logger.close()

    def test_startup_with_unavailable_debug_log_still_starts(self):
        from crossmouse.main import App

        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.json"
            config_path.write_text(json.dumps({"secret": "s", "debug": True}))
            platform = mock.Mock()
            platform.screen_size.return_value = (800, 600)
            engine = SimpleNamespace(
                config=None,
                mode="idle",
                local_screen=(800, 600),
                peer_screen=(0, 0),
                local_event=mock.Mock(),
                debug_snapshot=mock.Mock(),
            )
            with (
                mock.patch("crossmouse.main.make_platform", return_value=platform),
                mock.patch("crossmouse.main.make_clipboard", return_value=mock.Mock()),
                mock.patch("crossmouse.main.Engine", return_value=engine),
                mock.patch("crossmouse.main.debug_log_path", side_effect=OSError("no log")),
            ):
                app = App(config_path, enable_ui=False, open_browser=False)
            self.assertIsNone(app._debug_logger)

    def test_connect_failure_is_written_to_debug_log(self):
        with tempfile.TemporaryDirectory() as directory:
            app = self._app(directory)
            app.config = Config.from_dict({"secret": "s", "peer_ip": "1.2.3.4"})
            app.engine.config = app.config
            app.engine.link = None
            app.engine.detach = mock.Mock()
            app.platform = mock.Mock()
            app.platform.screen_size.return_value = (800, 600)
            app._drop_link = mock.Mock()
            app._stop = threading.Event()
            app._paused = False
            app._wait = mock.Mock(side_effect=lambda _: app._stop.set())
            logger = mock.Mock()
            app._debug_logger = logger

            with mock.patch("crossmouse.main.Link.connect", side_effect=OSError("no route")):
                app._network_loop()

            self.assertTrue(
                any("Connect failed: no route" in str(c) for c in logger.log.call_args_list)
            )

    def test_active_refusal_stops_reconnecting(self):
        with tempfile.TemporaryDirectory() as directory:
            app = self._app(directory)
            app.config = Config.from_dict({"secret": "s", "peer_ip": "1.2.3.4"})
            app.engine.config = app.config
            app.engine.link = None
            app.engine.detach = mock.Mock()
            app.engine.mode = "idle"
            app.engine.local_screen = (800, 600)
            app.engine.peer_screen = (0, 0)
            app.platform = mock.Mock()
            app.platform.screen_size.return_value = (800, 600)
            app._drop_link = mock.Mock()
            app._stop = threading.Event()
            app._reconnect = threading.Event()
            app._paused = False
            app.connected = False
            app.role = "controller"
            app._last_error = None
            app._ui_port = 7788
            app._wait = mock.Mock()
            logger = mock.Mock()
            app._debug_logger = logger

            sleeps = []

            def stop_after_idle(_seconds):
                sleeps.append(_seconds)
                if len(sleeps) >= 2:
                    app._stop.set()

            connect = mock.Mock(side_effect=ConnectionRefusedError("actively refused"))
            with mock.patch("crossmouse.main.time.sleep", side_effect=stop_after_idle):
                with mock.patch("crossmouse.main.Link.connect", connect):
                    app._network_loop()

            self.assertEqual(connect.call_count, 1)
            self.assertGreaterEqual(len(sleeps), 2)
            with mock.patch("crossmouse.main.local_ip_address", return_value="127.0.0.1"):
                status = app.status()
            self.assertTrue(status["paused"])
            self.assertFalse(status["connected"])
            self.assertFalse(status["connecting"])
            self.assertIn("actively refused", status["last_error"])
            self.assertTrue(
                any("Connection refused" in str(c) for c in logger.log.call_args_list)
            )

    def test_disconnect_clears_connected_immediately(self):
        with tempfile.TemporaryDirectory() as directory:
            app = self._app(directory)
            app._lock = threading.Lock()
            app._drop_link = mock.Mock()
            app.connected = True
            app._paused = False
            app._last_error = "Connection refused"

            app.disconnect()

            self.assertFalse(app.connected)
            self.assertTrue(app._paused)
            self.assertIsNone(app._last_error)

    def test_connect_pressed_during_refused_attempt_is_not_lost(self):
        with tempfile.TemporaryDirectory() as directory:
            app = self._app(directory)
            app.config = Config.from_dict({"secret": "s", "peer_ip": "1.2.3.4"})
            app.engine.config = app.config
            app.engine.link = None
            app.engine.detach = mock.Mock()
            app.engine.mode = "idle"
            app.engine.local_screen = (800, 600)
            app.engine.peer_screen = (0, 0)
            app.platform = mock.Mock()
            app.platform.screen_size.return_value = (800, 600)
            app._drop_link = mock.Mock()
            app._stop = threading.Event()
            app._reconnect = threading.Event()
            app._paused = False
            app.connected = False
            app.role = "controller"
            app._last_error = None
            app._wait = mock.Mock()

            attempts = []

            def connect_and_refuse(*_args):
                attempts.append(1)
                if len(attempts) == 1:
                    app.reconnect()
                else:
                    app._stop.set()
                raise ConnectionRefusedError("actively refused")

            sleeps = []

            def stop_after_sleep(_seconds):
                sleeps.append(1)
                if len(sleeps) >= 3:
                    app._stop.set()

            with mock.patch("crossmouse.main.time.sleep", side_effect=stop_after_sleep):
                with mock.patch("crossmouse.main.Link.connect", side_effect=connect_and_refuse):
                    app._network_loop()

            self.assertEqual(len(attempts), 2)


class CryptoTests(unittest.TestCase):
    def test_derive_key_is_deterministic(self):
        salt = b"0" * 16
        self.assertEqual(crypto.derive_key("secret", salt), crypto.derive_key("secret", salt))
        self.assertNotEqual(crypto.derive_key("secret", salt), crypto.derive_key("other", salt))

    def test_seal_open_roundtrip(self):
        key = crypto.derive_key("secret", b"1" * 16)
        blob = crypto.seal(key, b"hello")
        self.assertEqual(crypto.open_sealed(key, blob), b"hello")
        self.assertNotEqual(blob[:12], crypto.seal(key, b"hello")[:12])

    def test_open_with_wrong_key_fails(self):
        k1 = crypto.derive_key("secret", b"1" * 16)
        k2 = crypto.derive_key("wrong", b"1" * 16)
        with self.assertRaises(Exception):
            crypto.open_sealed(k2, crypto.seal(k1, b"hello"))

    def test_probe(self):
        key = crypto.derive_key("secret", b"2" * 16)
        self.assertTrue(crypto.verify_probe(key, crypto.make_probe(key)))
        self.assertFalse(crypto.verify_probe(crypto.derive_key("x", b"2" * 16), crypto.make_probe(key)))


class LinuxButtonTests(unittest.TestCase):
    def test_wheel_maps_to_scroll(self):
        from crossmouse.platform_linux import button_event

        self.assertEqual(button_event(4, 1).kind, "scroll")
        self.assertEqual(button_event(4, 1).b, 1)
        self.assertEqual(button_event(5, 1).b, -1)
        self.assertIsNone(button_event(4, 0))

    def test_special_keysyms_map_to_canonical_names(self):
        from Xlib import XK

        from crossmouse.platform_linux import keysym_to_key

        for name, expected in (
            ("BackSpace", "backspace"),
            ("Return", "enter"),
            ("Tab", "tab"),
            ("Escape", "escape"),
            ("Left", "left"),
            ("F1", "f1"),
            ("a", "a"),
        ):
            self.assertEqual(keysym_to_key(XK.string_to_keysym(name)), expected)

    def test_own_warp_is_filtered_once(self):
        import time
        from collections import deque

        from crossmouse.platform_linux import LinuxPlatform

        platform = LinuxPlatform.__new__(LinuxPlatform)
        platform._warp_targets = deque([(960, 540, time.monotonic())])
        self.assertTrue(platform._is_own_warp(960, 540))
        self.assertFalse(platform._is_own_warp(960, 540))

    def test_normal_buttons_unchanged(self):
        from crossmouse.platform_linux import button_event

        self.assertEqual(button_event(1, 1).kind, "button")
        self.assertEqual(button_event(3, 1).a, "right")


class InjectionFilterTests(unittest.TestCase):
    def test_injected_event_consumed_once(self):
        from crossmouse.platform_base import InputEvent, Platform

        platform = Platform()
        platform.remember_injection(InputEvent("key", "a", 1))
        self.assertTrue(platform.is_own_injection(InputEvent("key", "a", 1)))
        self.assertFalse(platform.is_own_injection(InputEvent("key", "a", 1)))
        self.assertFalse(platform.is_own_injection(InputEvent("key", "b", 1)))


class ProtocolTests(unittest.TestCase):
    def test_frame_unframe_partial(self):
        raw = protocol.encode(protocol.MOVE, {"x": 1})
        body = protocol.unframe(bytearray(raw))
        buffer = bytearray(raw[:5])
        self.assertIsNone(protocol.unframe(buffer))
        buffer.extend(raw[5:])
        self.assertEqual(protocol.unframe(buffer), body)
        self.assertEqual(buffer, bytearray())

    def test_encode_decode(self):
        raw = protocol.encode(protocol.CLIPBOARD, {"text": "hi"})
        payload = protocol.unframe(bytearray(raw))
        self.assertEqual(protocol.decode(payload), (protocol.CLIPBOARD, {"text": "hi"}))

    def test_rejects_oversize(self):
        with self.assertRaises(ValueError):
            protocol.frame(b"x" * (protocol.MAX_FRAME + 1))


if __name__ == "__main__":
    unittest.main()
