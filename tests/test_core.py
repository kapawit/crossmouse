from __future__ import annotations

import unittest

from crossmouse import crypto, protocol
from crossmouse.config import Config


class ConfigTests(unittest.TestCase):
    def test_from_dict(self):
        c = Config.from_dict({"secret": "s", "peer_ip": "1.2.3.4", "port": 6000, "edge": "left"})
        self.assertEqual(c.peer_ip, "1.2.3.4")
        self.assertEqual(c.port, 6000)
        self.assertEqual(c.edge, "left")
        self.assertTrue(c.clipboard)

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

    def test_normal_buttons_unchanged(self):
        from crossmouse.platform_linux import button_event

        self.assertEqual(button_event(1, 1).kind, "button")
        self.assertEqual(button_event(3, 1).a, "right")


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
