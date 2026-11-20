from __future__ import annotations

import json
import re
import socket
import subprocess
import tempfile
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


def _probe(cases, expression):
    """Evaluate a real page function in Node for each state."""
    html = (Path(__file__).parents[1] / "crossmouse" / "ui" / "index.html").read_text()
    script = re.search(r"<script>(.*?)</script>", html, re.S).group(1)
    stub = """
global.document = {
  addEventListener() {},
  activeElement: null,
  getElementById() { return { innerHTML: '', textContent: '', appendChild() {} }; },
  querySelector() { return { innerHTML: '', textContent: '', appendChild() {}, scrollTop: 0 }; },
  createElement() { return { innerHTML: '', textContent: '', appendChild() {} }; }
};
global.window = { isSecureContext: true };
global.navigator = {};
global.fetch = () => new Promise(() => {});
global.setTimeout = () => 0;
global.setInterval = () => 0;
"""
    probes = []
    for name, fields in cases:
        probes.append(
            "Object.assign(state, "
            + json.dumps(fields)
            + "); console.log("
            + json.dumps(name)
            + " + '|' + "
            + expression
            + "());"
        )
    code = stub + script + "\n" + "\n".join(probes)
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "probe.js"
        path.write_text(code, encoding="utf-8")
        result = subprocess.run(
            ["node", str(path)], capture_output=True, text=True, timeout=10
        )
        if result.returncode:
            raise AssertionError(result.stderr)
    outputs = {}
    for line in result.stdout.splitlines():
        name, value = line.split("|", 1)
        outputs[name] = value
    return outputs


def _switch_labels(cases):
    labels = {}
    for name, markup in _probe(cases, "switchHtml").items():
        match = re.search(r'<span class="label">(.*?)</span>', markup)
        labels[name] = match.group(1) if match else markup
    return labels


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
    def test_listener_switch_label_tracks_listening_then_connected(self):
        labels = _switch_labels(
            [
                ("listener_off", {"role": "listener", "connected": False, "paused": True}),
                ("listener_waiting", {"role": "listener", "connected": False, "paused": False}),
                ("listener_linked", {"role": "listener", "connected": True, "paused": False}),
                ("controller_off", {"role": "controller", "connected": False, "paused": True}),
                ("controller_linked", {"role": "controller", "connected": True, "paused": False}),
            ]
        )

        self.assertEqual(
            labels,
            {
                "listener_off": "Connect",
                "listener_waiting": "Listening",
                "listener_linked": "Connected",
                "controller_off": "Connect",
                "controller_linked": "Disconnect",
            },
        )

    def test_listener_toggle_cancels_waiting_instead_of_reconnecting(self):
        actions = _probe(
            [
                ("listener_off", {"role": "listener", "connected": False, "paused": True}),
                ("listener_waiting", {"role": "listener", "connected": False, "paused": False}),
                ("listener_linked", {"role": "listener", "connected": True, "paused": False}),
                ("controller_off", {"role": "controller", "connected": False, "paused": True}),
                ("controller_linked", {"role": "controller", "connected": True, "paused": False}),
            ],
            "toggleAction",
        )

        self.assertEqual(
            actions,
            {
                "listener_off": "connect",
                "listener_waiting": "disconnect",
                "listener_linked": "disconnect",
                "controller_off": "connect",
                "controller_linked": "disconnect",
            },
        )

    def test_toggle_is_bound_to_connection_status(self):
        html = (Path(__file__).parents[1] / "crossmouse" / "ui" / "index.html").read_text()

        self.assertRegex(html, r"state\.connected\s*=\s*!!s\.connected")
        self.assertNotIn("state.active = !s.paused", html)
        self.assertNotIn("press Connect to retry", html)
        self.assertNotIn("state.last_error", html)

    def test_settings_expose_auto_start_option(self):
        html = (Path(__file__).parents[1] / "crossmouse" / "ui" / "index.html").read_text()

        self.assertIn('data-field="auto_start"', html)
        self.assertIn("Turn on at startup", html)
        self.assertIn('data-act="save">Save</button>', html)


if __name__ == "__main__":
    unittest.main()
