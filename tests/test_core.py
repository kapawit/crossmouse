from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

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
