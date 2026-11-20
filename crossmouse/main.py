from __future__ import annotations

import argparse
import json
import logging
import sys
import threading
import time
import webbrowser
from collections import deque
from pathlib import Path

from .clipboard import make_clipboard
from .config import Config
from .engine import Engine
from .link import AuthError, Link, serve_once
from .platform_base import Platform

log = logging.getLogger("crossmouse")


def make_platform() -> Platform:
    if sys.platform == "win32":
        from .platform_win import WindowsPlatform

        return WindowsPlatform()
    from .platform_linux import LinuxPlatform

    return LinuxPlatform()


def pump_link(engine, link, should_stop) -> None:
    while not should_stop():
        message = link.recv(timeout=0.2)
        if message is None:
            if engine.link is None:
                break
        else:
            engine.remote_message(*message)
        engine.poll_clipboard()


class App:
    def __init__(
        self,
        config_path: str,
        enable_ui: bool = True,
        ui_port: int = 7788,
        open_browser: bool = True,
    ) -> None:
        self.config_path = Path(config_path)
        self.config = Config.from_file(self.config_path)
        self.platform = make_platform()
        self.clipboard = make_clipboard(self.platform)
        self.engine = Engine(self.config, self.platform, self.clipboard)
        self._lines: deque[str] = deque(maxlen=200)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._reconnect = threading.Event()
        self._worker: threading.Thread | None = None
        self.connected = False
        self.role = "listener"
        self.enable_ui = enable_ui
        self.ui = None
        self._ui_port = ui_port
        self._open_browser = open_browser
        self.platform.start_capture(self.engine.local_event)
        self._log("CrossMouse started")

    def _log(self, message: str) -> None:
        with self._lock:
            self._lines.append(time.strftime("%H:%M:%S") + "  " + message)
        log.info(message)

    def log_lines(self) -> list[str]:
        with self._lock:
            return list(self._lines)

    def status(self) -> dict:
        return {
            "connected": self.connected,
            "mode": self.engine.mode,
            "role": self.role,
            "peer_ip": self.config.peer_ip,
            "port": self.config.port,
            "edge": self.config.edge,
            "clipboard": self.config.clipboard,
            "local_screen": list(self.engine.local_screen),
            "peer_screen": list(self.engine.peer_screen),
            "ui_port": self._ui_port,
        }

    def save_config(self, data: dict) -> bool:
        restart = False
        current = self.config.to_dict()
        for key in ("secret", "peer_ip", "port", "edge", "clipboard"):
            if key in data and data[key] != current[key]:
                restart = True
        try:
            new = Config.from_dict({**current, **data})
        except (ValueError, KeyError) as exc:
            raise ValueError(str(exc)) from exc
        self.config_path.write_text(json.dumps(new.to_dict(), indent=2) + "\n")
        self.config = new
        self.engine.config = new
        self._log("Configuration saved")
        self._reconnect.set()
        return restart

    def reconnect(self) -> None:
        self._reconnect.set()
        self._log("Reconnecting")

    def disconnect(self) -> None:
        link = self.engine.link
        if link:
            link.close()
        self.engine.detach()
        self._log("Disconnected")

    def handoff(self) -> None:
        self.engine.request_handoff()
        self._log("Handoff requested")

    def start(self) -> None:
        if self.enable_ui:
            from .webui import WebUI

            self.ui = WebUI(self, port=self._ui_port)
            self.ui.start()
            if self._open_browser:
                webbrowser.open(f"http://127.0.0.1:{self._ui_port}/")
        self._worker = threading.Thread(target=self._network_loop, daemon=True)
        self._worker.start()
        try:
            while not self._stop.is_set():
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def stop(self) -> None:
        self._stop.set()
        self.disconnect()
        if self.ui:
            self.ui.stop()
        self.platform.stop_capture()
        self.platform.ungrab()
        self.platform.release_all_keys()
        self.clipboard.close()
        self._log("CrossMouse stopped")

    def _on_link(self, link: Link) -> None:
        self.engine.attach(link)
        with self._lock:
            self.connected = True
        self._log(f"Peer connected ({link.peer_screen[0]}x{link.peer_screen[1]})")
        pump_link(self.engine, link, lambda: self._stop.is_set())
        self.engine.detach()
        with self._lock:
            self.connected = False
        self._log("Peer disconnected")

    def _network_loop(self) -> None:
        while not self._stop.is_set():
            self._reconnect.clear()
            self.disconnect()
            if self.config.peer_ip:
                self.role = "connector"
                try:
                    link = Link.connect(
                        self.config.peer_ip,
                        self.config.port,
                        self.config.secret,
                        self.platform.screen_size(),
                    )
                except (OSError, AuthError) as exc:
                    self._log(f"Connect failed: {exc}")
                    self._wait(2)
                    continue
                self._on_link(link)
            else:
                self.role = "listener"
                self._log(f"Listening on port {self.config.port}")
                serve_once(
                    self.config.port,
                    self.config.secret,
                    self.platform.screen_size(),
                    self._on_link,
                    should_stop=lambda: self._stop.is_set() or self._reconnect.is_set(),
                )

    def _wait(self, seconds: float) -> None:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline and not self._stop.is_set():
            if self._reconnect.is_set():
                return
            time.sleep(0.1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CrossMouse - share one mouse and keyboard over LAN")
    parser.add_argument("--config", default="config.json", help="path to config JSON")
    parser.add_argument("--no-ui", action="store_true", help="run headless without the web UI")
    parser.add_argument("--ui-port", type=int, default=7788)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    App(
        config_path=args.config,
        enable_ui=not args.no_ui,
        ui_port=args.ui_port,
        open_browser=not args.no_browser,
    ).start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
