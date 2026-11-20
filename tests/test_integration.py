from __future__ import annotations

import os
import socket
import threading
import unittest

from crossmouse.link import AuthError, Link


class LinkIntegrationTests(unittest.TestCase):
    def _serve(self, secret, port, out):
        listener = socket.socket()
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", port))
        listener.listen(1)
        try:
            conn, _ = listener.accept()
            try:
                link = Link.accept(conn, secret, (1920, 1080))
                out["msg"] = link.recv(timeout=2)
                link.send("ping", {"n": 1})
            except AuthError as exc:
                out["error"] = str(exc)
            finally:
                conn.close()
        finally:
            listener.close()

    def test_handshake_and_encrypted_exchange(self):
        out = {}
        thread = threading.Thread(target=self._serve, args=("secret", 45301, out))
        thread.start()
        link = Link.connect("127.0.0.1", 45301, "secret", (1000, 800))
        link.send("move", {"x": 5, "y": 6})
        thread.join(3)
        self.assertEqual(out.get("msg"), ("move", {"x": 5, "y": 6}))
        self.assertEqual(link.recv(timeout=2), ("ping", {"n": 1}))
        link.close()

    def test_wrong_secret_is_rejected(self):
        out = {}
        thread = threading.Thread(target=self._serve, args=("secret", 45302, out))
        thread.start()
        with self.assertRaises(AuthError):
            Link.connect("127.0.0.1", 45302, "wrong", (1000, 800))
        thread.join(3)
        self.assertEqual(out.get("error"), "wrong secret")


@unittest.skipUnless(os.environ.get("DISPLAY"), "requires X11")
class ClipboardIntegrationTests(unittest.TestCase):
    def test_x_selection_roundtrip(self):
        from crossmouse.clipboard import LinuxClipboard
        from crossmouse.platform_linux import LinuxPlatform

        platform = LinuxPlatform()
        owner = LinuxClipboard(platform)
        owner.set_text("crossmouse-test")
        self.assertEqual(owner.get_text(), "crossmouse-test")
        reader = LinuxClipboard(platform)
        self.assertEqual(reader.get_text(), "crossmouse-test")
        reader.set_text("from-reader")
        self.assertEqual(owner.get_text(), "from-reader")
        owner.close()
        reader.close()


if __name__ == "__main__":
    unittest.main()
