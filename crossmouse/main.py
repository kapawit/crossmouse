from __future__ import annotations

import argparse
import json
import logging
import secrets
import socket
import sys
import threading
import time
import webbrowser
from collections import deque
from pathlib import Path

from .clipboard import make_clipboard
from .config import Config
from .debuglog import DebugLogger, debug_log_path
from .engine import Engine
from .link import AuthError, Link, serve_once
from .platform_base import Platform

log = logging.getLogger("crossmouse")


def default_config_path() -> Path:
    return Path.home() / ".config" / "crossmouse" / "config.json"


def ensure_config(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    default = Config(secret=secrets.token_hex(16))
    path.write_text(json.dumps(default.to_dict(), indent=2) + "\n")
    path.chmod(0o600)
    log.info("Created default config at %s", path)


def make_platform() -> Platform:
    if sys.platform == "win32":
        from .platform_win import WindowsPlatform

        return WindowsPlatform()
    from .platform_linux import LinuxPlatform

    return LinuxPlatform()


def local_ip_address() -> str:
    """Return the LAN IPv4 address used to reach this machine."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("192.0.2.1", 80))
        return str(sock.getsockname()[0])
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def pump_link(engine, link, should_stop) -> None:
    while not should_stop():
        message = link.recv(timeout=0.2)
        if message is None:
            if engine.link is None or not link.alive:
                engine.detach()
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
        self.engine = Engine(
            self.config,
            self.platform,
            self.clipboard,
            debug_sink=self._debug if self.config.debug else None,
        )
        self._debug_logger: DebugLogger | None = None
        self._last_debug_sample = 0.0
        self._lines: deque[str] = deque(maxlen=200)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._reconnect = threading.Event()
        self._paused = False
        self._worker: threading.Thread | None = None
        self.connected = False
        self._last_error: str | None = None
        self.role = "listener"
        self.enable_ui = enable_ui
        self.ui = None
        self._ui_port = ui_port
        self._open_browser = open_browser
        self.platform.start_capture(self.engine.local_event)
        self._log("CrossMouse started")
        if self.config.debug:
            self._start_debug_logging()
            self._debug("Startup with debug logging enabled")
            self._debug_config_summary()

    def _log(self, message: str) -> None:
        with self._lock:
            self._lines.append(time.strftime("%H:%M:%S") + "  " + message)
        log.info(message)

    def _debug(self, message: str) -> None:
        if self._debug_logger is not None:
            self._debug_logger.log(message)

    def _start_debug_logging(self) -> None:
        if self._debug_logger is not None:
            return
        try:
            path = debug_log_path()
            self._debug_logger = DebugLogger(path)
            self._debug(f"Debug log: {path}")
        except OSError as exc:
            self._debug_logger = None
            self._log(f"Debug log unavailable: {exc}")

    def _debug_config_summary(self) -> None:
        config = self.config
        self._debug(
            "config "
            f"peer={config.peer_ip or 'listen'} "
            f"port={config.port} "
            f"edge={config.edge} "
            f"clipboard={config.clipboard} "
            f"primary={config.primary} "
            f"debug={config.debug} "
            "secret=<masked>"
        )

    def set_debug(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if self.config.debug == enabled:
            return
        new = Config.from_dict({**self.config.to_dict(), "debug": enabled})
        self.config_path.write_text(json.dumps(new.to_dict(), indent=2) + "\n")
        self.config = new
        self.engine.config = new
        if enabled:
            self._start_debug_logging()
            self.engine.debug_sink = self._debug if self._debug_logger else None
            self._debug_config_summary()
            self._debug("Debug logging enabled")
        else:
            self._debug("Debug logging disabled")
            if self._debug_logger is not None:
                self._debug_logger.close()
            self._debug_logger = None
            self.engine.debug_sink = None
        self._log(f"Debug logging {'enabled' if enabled else 'disabled'}")

    def log_lines(self) -> list[str]:
        with self._lock:
            return list(self._lines)

    def status(self) -> dict:
        return {
            "connected": self.connected,
            "paused": self._paused,
            "connecting": not self._paused and not self.connected and bool(self.config.peer_ip),
            "last_error": self._last_error,
            "mode": self.engine.mode,
            "role": self.role,
            "peer_ip": self.config.peer_ip,
            "local_ip": local_ip_address(),
            "port": self.config.port,
            "edge": self.config.edge,
            "clipboard": self.config.clipboard,
            "primary": self.config.primary,
            "debug": bool(self.config.debug),
            "local_screen": list(self.engine.local_screen),
            "peer_screen": list(self.engine.peer_screen),
            "ui_port": self._ui_port,
        }

    def save_config(self, data: dict) -> bool:
        restart = False
        current = self.config.to_dict()
        for key in ("secret", "peer_ip", "port", "edge", "clipboard", "primary"):
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
        self._paused = False
        self._last_error = None
        self._reconnect.set()
        return restart

    def reconnect(self) -> None:
        self._paused = False
        self._last_error = None
        self._reconnect.set()
        self._debug("Reconnecting")
        self._log("Reconnecting")

    def _drop_link(self) -> None:
        link = self.engine.link
        if link:
            link.close()
        self.engine.detach()

    def disconnect(self) -> None:
        self._paused = True
        self._last_error = None
        self._drop_link()
        with self._lock:
            self.connected = False
        self._debug("Disconnected")
        self._log("Disconnected")

    def handoff(self) -> None:
        self.engine.request_handoff()
        self._debug("Handoff requested")
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
                if (
                    self.config.debug
                    and time.monotonic() - self._last_debug_sample >= 0.25
                ):
                    self.engine.debug_snapshot("poll")
                    self._last_debug_sample = time.monotonic()
                time.sleep(0.1 if self.config.debug else 0.5)
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
        self.platform.set_pointer_visible(True)
        self.platform.release_all_keys()
        self.clipboard.close()
        self._debug("CrossMouse stopped")
        if self._debug_logger is not None:
            self._debug_logger.close()
            self._debug_logger = None
        self._log("CrossMouse stopped")

    def _on_link(self, link: Link) -> None:
        self.engine.attach(link)
        with self._lock:
            self.connected = True
            self._last_error = None
        self._debug(f"Peer connected ({link.peer_screen[0]}x{link.peer_screen[1]})")
        self._log(f"Peer connected ({link.peer_screen[0]}x{link.peer_screen[1]})")
        pump_link(self.engine, link, lambda: self._stop.is_set())
        self.engine.detach()
        with self._lock:
            self.connected = False
        self._debug("Peer disconnected")
        self._log("Peer disconnected")

    def _network_loop(self) -> None:
        while not self._stop.is_set():
            if self._paused:
                time.sleep(0.2)
                continue
            self._reconnect.clear()
            self._drop_link()
            if self.config.peer_ip:
                self.role = "connector"
                try:
                    link = Link.connect(
                        self.config.peer_ip,
                        self.config.port,
                        self.config.secret,
                        self.platform.screen_size(),
                    )
                except ConnectionRefusedError as exc:
                    retry_requested = self._reconnect.is_set()
                    if not retry_requested:
                        self._paused = True
                        self._last_error = f"Connection refused: {exc}"
                    self._debug(f"Connection refused: {exc}")
                    self._log(f"Connection refused: {exc}")
                    self._wait(2)
                    continue
                except (OSError, AuthError) as exc:
                    self._last_error = f"Connect failed: {exc}"
                    self._debug(f"Connect failed: {exc}")
                    self._log(f"Connect failed: {exc}")
                    self._wait(2)
                    continue
                self._on_link(link)
            else:
                self.role = "listener"
                self._debug(f"Listening on port {self.config.port}")
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
    parser.add_argument("--config", default=None, help="path to config JSON")
    parser.add_argument("--no-ui", action="store_true", help="run headless without the web UI")
    parser.add_argument("--ui-port", type=int, default=7788)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    config_path = Path(args.config) if args.config else default_config_path()
    ensure_config(config_path)

    App(
        config_path=config_path,
        enable_ui=not args.no_ui,
        ui_port=args.ui_port,
        open_browser=not args.no_browser,
    ).start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
