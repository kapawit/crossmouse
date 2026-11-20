from __future__ import annotations

import json
import socket
import unittest
from urllib.request import Request, urlopen

from crossmouse.config import Config
from crossmouse.webui import WebUI


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class FakeApp:
    def __init__(self) -> None:
        self.config = Config.from_dict({"secret": "s"})
        self.debug_calls: list[bool] = []

    def status(self) -> dict:
        return {"connected": False, "paused": False, "mode": "idle", "debug": self.config.debug}

    def log_lines(self) -> list[str]:
        return []

    def set_debug(self, enabled: bool) -> None:
        self.debug_calls.append(enabled)
        self.config = Config.from_dict({**self.config.to_dict(), "debug": enabled})


class WebUIDebugEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fake = FakeApp()
        self.ui = WebUI(self.fake, port=_free_port())
        self.ui.start()
        self.base = f"http://127.0.0.1:{self.ui._server.server_address[1]}"

    def tearDown(self) -> None:
        self.ui.stop()

    def test_post_api_debug_enables_logging(self):
        request = Request(
            self.base + "/api/debug",
            data=json.dumps({"enabled": True}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=5) as response:
            body = json.loads(response.read())

        self.assertEqual(self.fake.debug_calls, [True])
        self.assertEqual(body, {"ok": True, "debug": True})


if __name__ == "__main__":
    unittest.main()
