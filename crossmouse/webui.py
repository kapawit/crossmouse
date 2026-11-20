from __future__ import annotations

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

log = logging.getLogger("crossmouse.webui")

UI_DIR = Path(__file__).parent / "ui"


class WebUI:
    def __init__(self, app, host: str = "127.0.0.1", port: int = 7788) -> None:
        self.app = app
        self.host = host
        self.port = port
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        app = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "CrossMouse/1.0"

            def log_message(self, fmt, *args):
                pass

            def _send(self, status: int, body: bytes, ctype: str) -> None:
                self.send_response(status)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def _json(self, obj, status: int = 200) -> None:
                self._send(
                    status,
                    json.dumps(obj).encode("utf-8"),
                    "application/json; charset=utf-8",
                )

            def do_GET(self):
                path = self.path.split("?", 1)[0]
                if path in ("/", "/index.html"):
                    self._send(
                        200, (UI_DIR / "index.html").read_bytes(), "text/html; charset=utf-8"
                    )
                elif path == "/api/status":
                    self._json(app.app.status())
                elif path == "/api/config":
                    self._json(app.app.config.to_dict())
                elif path == "/api/log":
                    self._json({"lines": app.app.log_lines()})
                else:
                    self._json({"error": "not found"}, 404)

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                try:
                    data = json.loads(self.rfile.read(length) or b"{}")
                except ValueError:
                    self._json({"error": "invalid json"}, 400)
                    return
                path = self.path.split("?", 1)[0]
                if path == "/api/config":
                    result = app.app.save_config(data)
                    self._json({"ok": True, "restart_required": result})
                elif path == "/api/debug":
                    try:
                        app.app.set_debug(bool(data.get("enabled")))
                    except (OSError, ValueError):
                        self._json({"error": "could not persist debug setting"}, 500)
                        return
                    self._json({"ok": True, "debug": bool(app.app.config.debug)})
                elif path == "/api/action":
                    action = data.get("action")
                    if action == "connect":
                        app.app.reconnect()
                    elif action == "disconnect":
                        app.app.disconnect()
                    elif action == "handoff":
                        app.app.handoff()
                    else:
                        self._json({"error": "unknown action"}, 400)
                        return
                    self._json({"ok": True})
                else:
                    self._json({"error": "not found"}, 404)

        self._server = ThreadingHTTPServer((self.host, self.port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        log.info("UI at http://%s:%d", self.host, self.port)

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
        log.info("UI stopped")
