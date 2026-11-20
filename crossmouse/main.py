from __future__ import annotations

import argparse
import json
import logging
import secrets
import socket
import sys
import threading
import time
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
    def __init__(self, config_path: str) -> None:
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
        self._paused = not self.config.auto_start
        self._worker: threading.Thread | None = None
        self.connected = False
        self.role = "connector" if self.config.peer_ip else "listener"
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
            f"auto_start={config.auto_start} "
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

    def set_role(self, role: str) -> None:
        normalized = "connector" if role in ("controller", "connector") else role
        if normalized not in ("listener", "connector"):
            raise ValueError(f"unknown role: {role}")
        if self.connected or getattr(self.engine, "link", None) or self.role == normalized:
            return
        self.role = normalized
        self._debug(f"Role set to {self.role}")
        self._log(f"Role set to {self.role}")
        self._reconnect.set()

    def log_lines(self) -> list[str]:
        with self._lock:
            return list(self._lines)

    def status(self) -> dict:
        return {
            "connected": self.connected,
            "paused": self._paused,
            "connecting": not self._paused and not self.connected and self.role == "connector",
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
        }

    def save_config(self, data: dict) -> bool:
        restart = False
        current = self.config.to_dict()
        peer_changed = "peer_ip" in data and data["peer_ip"] != current["peer_ip"]
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
        if peer_changed:
            self.role = "connector" if new.peer_ip else "listener"
        self._log("Configuration saved")
        self._paused = not new.auto_start
        if self._paused and (self.connected or getattr(self.engine, "link", None)):
            self._drop_link()
            with self._lock:
                self.connected = False
            self._log("Disconnected")
        else:
            self._reconnect.set()
        return restart

    def reconnect(self) -> None:
        self._paused = False
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
        self._drop_link()
        with self._lock:
            self.connected = False
        self._debug("Disconnected")
        self._log("Disconnected")

    def handoff(self) -> None:
        self.engine.request_handoff()
        self._debug("Handoff requested")
        self._log("Handoff requested")

    def start_background(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        self._worker = threading.Thread(target=self._network_loop, daemon=True)
        self._worker.start()

    def start(self) -> None:
        self.start_background()
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
        self._debug(f"Peer connected ({link.peer_screen[0]}x{link.peer_screen[1]})")
        self._log(f"Peer connected ({link.peer_screen[0]}x{link.peer_screen[1]})")
        pump_link(self.engine, link, lambda: self._stop.is_set())
        self.engine.detach()
        with self._lock:
            self.connected = False
        if not self.config.auto_start:
            self._paused = True
        self._debug("Peer disconnected")
        self._log("Peer disconnected")

    def _network_loop(self) -> None:
        while not self._stop.is_set():
            if self._paused:
                time.sleep(0.2)
                continue
            self._reconnect.clear()
            self._drop_link()
            if self.role == "connector":
                if not self.config.peer_ip:
                    self._debug("Controller role needs a peer IP")
                    self._log("Controller role needs a peer IP")
                    self._paused = True
                    continue
                try:
                    link = Link.connect(
                        self.config.peer_ip,
                        self.config.port,
                        self.config.secret,
                        self.platform.screen_size(),
                    )
                except ConnectionRefusedError as exc:
                    if not self._reconnect.is_set():
                        self._paused = True
                    self._debug(f"Connection refused: {exc}")
                    self._log(f"Connection refused: {exc}")
                    self._wait(2)
                    continue
                except (OSError, AuthError) as exc:
                    self._debug(f"Connect failed: {exc}")
                    self._log(f"Connect failed: {exc}")
                    self._wait(2)
                    continue
                self._on_link(link)
            else:
                self._debug(f"Listening on port {self.config.port}")
                self._log(f"Listening on port {self.config.port}")
                serve_once(
                    self.config.port,
                    self.config.secret,
                    self.platform.screen_size(),
                    self._on_link,
                    should_stop=lambda: (
                        self._stop.is_set() or self._reconnect.is_set() or self._paused
                    ),
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
    parser.add_argument("--no-ui", action="store_true", help="run headless without the native UI")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    config_path = Path(args.config) if args.config else default_config_path()
    ensure_config(config_path)

    app = App(config_path=config_path)
    if args.no_ui:
        app.start()
    else:
        from .native_ui import NativeUI

        NativeUI.start(app)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
