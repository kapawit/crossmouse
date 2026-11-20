from __future__ import annotations

import json
import socket
import unittest
from pathlib import Path
from urllib.error import HTTPError
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
        self.debug_error: OSError | None = None

    def status(self) -> dict:
        return {"connected": False, "paused": False, "mode": "idle", "debug": self.config.debug}

    def log_lines(self) -> list[str]:
        return []

    def set_debug(self, enabled: bool) -> None:
        self.debug_calls.append(enabled)
        if self.debug_error is not None:
            raise self.debug_error
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

    def test_post_api_debug_reports_persist_failure(self):
        self.fake.debug_error = OSError("disk full")
        request = Request(
            self.base + "/api/debug",
            data=json.dumps({"enabled": True}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with self.assertRaises(HTTPError) as caught:
            urlopen(request, timeout=5)

        self.assertEqual(caught.exception.code, 500)
        self.assertEqual(json.loads(caught.exception.read()), {"error": "could not persist debug setting"})


class WebUIPageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ui = WebUI(FakeApp(), port=_free_port())
        self.ui.start()
        self.base = f"http://127.0.0.1:{self.ui._server.server_address[1]}"

    def tearDown(self) -> None:
        self.ui.stop()

    def test_settings_page_exposes_debug_toggle(self):
        with urlopen(self.base + "/", timeout=5) as response:
            html = response.read().decode("utf-8")

        self.assertIn('data-field="debug"', html)
        self.assertIn("Debug logging", html)


class WebUIConnectionToggleTests(unittest.TestCase):
    def test_toggle_is_bound_to_connection_status(self):
        html = (Path(__file__).parents[1] / "crossmouse" / "ui" / "index.html").read_text()

        self.assertRegex(html, r"state\.connected\s*=\s*!!s\.connected")
        self.assertNotIn("state.active = !s.paused", html)


if __name__ == "__main__":
    unittest.main()
