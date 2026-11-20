from __future__ import annotations

import logging
import time
from collections.abc import Callable

from . import protocol
from .clipboard import Clipboard
from .config import Config
from .link import Link
from .platform_base import InputEvent, Platform

log = logging.getLogger("crossmouse.engine")

OPPOSITE = {"left": "right", "right": "left", "top": "bottom", "bottom": "top"}


def entry_point(edge: str, width: int, height: int) -> tuple[int, int]:
    if edge == "left":
        return 0, height // 2
    if edge == "right":
        return width - 1, height // 2
    if edge == "top":
        return width // 2, 0
    return width // 2, height - 1


def at_edge(edge: str, x: int, y: int, width: int, height: int) -> bool:
    if edge == "left":
        return x <= 0
    if edge == "right":
        return x >= width - 1
    if edge == "top":
        return y <= 0
    return y >= height - 1


def moving_outward(edge: str, x: int, y: int, px: int, py: int) -> bool:
    if edge == "left":
        return x < px
    if edge == "right":
        return x > px
    if edge == "top":
        return y < py
    return y > py


def beyond_edge(edge: str, x: int, y: int, width: int, height: int, px: int, py: int) -> bool:
    if edge == "left":
        return x <= 0 and px > 0
    if edge == "right":
        return x >= width - 1 and px < width - 1
    if edge == "top":
        return y <= 0 and py > 0
    return y >= height - 1 and py < height - 1


class Engine:
    def __init__(
        self,
        config: Config,
        platform: Platform,
        clipboard: Clipboard,
        clock=time.monotonic,
        debug_sink: Callable[[str], None] | None = None,
    ) -> None:
        self.config = config
        self.platform = platform
        self.clipboard = clipboard
        self._clock = clock
        self.debug_sink = debug_sink
        self.link: Link | None = None
        self.mode = "idle"
        self.local_screen = platform.screen_size()
        self.peer_screen: tuple[int, int] = (0, 0)
        self._vx = 0
        self._vy = 0
        self._last_pointer: tuple[int, int] | None = None
        self._idle_last: tuple[int, int] | None = None
        self._last_remote_x = 0
        self._last_remote_y = 0
        self._remote_first = True
        self._last_clip = ""
        self._clip_poll = 0.0

    def _debug(self, message: str) -> None:
        if self.debug_sink is not None:
            self.debug_sink(message)

    def _inject(self, event: InputEvent) -> None:
        try:
            self.platform.inject(event)
        except Exception as exc:
            self._debug(f"inject failed kind={event.kind}: {exc}")
            log.warning("inject failed: %s", exc)

    def debug_snapshot(self, reason: str) -> None:
        if self.debug_sink is None:
            return
        x, y = self.platform.pointer_position()
        role = "controller" if self.config.peer_ip else "listener"
        self._debug(
            f"pointer reason={reason} "
            f"mode={self.mode} "
            f"role={role} "
            f"link={'on' if self.link is not None else 'off'} "
            f"local=({x},{y}) "
            f"virtual=({self._vx},{self._vy}) "
            f"local_screen={self.local_screen[0]}x{self.local_screen[1]} "
            f"peer_screen={self.peer_screen[0]}x{self.peer_screen[1]} "
            f"edge={self.config.edge}"
        )

    def attach(self, link: Link) -> None:
        self.link = link
        self.peer_screen = link.peer_screen
        self.debug_snapshot("link-attached")
        log.info("peer attached, screen %s", self.peer_screen)

    def request_handoff(self) -> None:
        if self.link is None or not self.config.primary:
            return
        if self.mode == "idle":
            self._begin_controlling(*self.platform.pointer_position())
        elif self.mode == "controlled":
            self.platform.release_all_keys()
            self.platform.set_pointer_visible(True)
            self._idle_last = None
            self.mode = "idle"
            self._debug("pointer shown; suppression off; hidden=no")
            self._send(protocol.HANDOFF, {"from": "controlled"})

    def detach(self) -> None:
        self.platform.ungrab()
        self.platform.set_suppress(False)
        self.platform.set_pointer_visible(True)
        self.platform.release_all_keys()
        self._idle_last = None
        self.mode = "idle"
        self.link = None
        self.debug_snapshot("link-detached")
        self._debug("pointer shown; suppression off; hidden=no")

    def local_event(self, event: InputEvent) -> None:
        link = self.link
        if link is None or not self.config.primary:
            return
        if self.mode == "idle":
            if event.kind == "move":
                w, h = self.local_screen
                x, y = int(event.a), int(event.b)
                previous = self._idle_last
                self._idle_last = (x, y)
                if previous is None:
                    return
                dx, dy = x - previous[0], y - previous[1]
                if dx == 0 and dy == 0:
                    return
                if at_edge(self.config.edge, x, y, w, h) and (
                    not at_edge(self.config.edge, previous[0], previous[1], w, h)
                    or moving_outward(self.config.edge, x, y, *previous)
                ):
                    self._debug(
                        f"edge trigger edge={self.config.edge} "
                        f"local=({x},{y}) previous=({previous[0]},{previous[1]})"
                    )
                    self._begin_controlling(x, y)
        elif self.mode == "controlling":
            self._forward(event)
        elif self.mode == "controlled" and event.kind in ("key", "button"):
            if event.kind == "key" and event.b:
                self.platform.release_all_keys()
                self.platform.set_suppress(False)
                self.platform.set_pointer_visible(True)
                self._idle_last = None
                self._send(protocol.HANDOFF, {"from": "controlled"})
                self.mode = "idle"
                self._debug("pointer shown; suppression off; hidden=no")

    def _begin_controlling(self, x: int, y: int) -> None:
        w, h = self.local_screen
        pw, ph = self.peer_screen or (w, h)
        self._vx, self._vy = entry_point(OPPOSITE[self.config.edge], pw, ph)
        center = (w // 2, h // 2)
        self.platform.grab()
        self.platform.set_suppress(True)
        self.platform.set_pointer_visible(False)
        self.platform.set_pointer(*center)
        self._last_pointer = center
        self._idle_last = None
        self.mode = "controlling"
        self.debug_snapshot("handoff-start")
        self._debug("pointer grabbed; local input suppressed; hidden=yes")
        self._send(protocol.HANDOFF, {"from": "controlling"})
        self._send(protocol.MOVE, {"x": self._vx, "y": self._vy})
        log.info("controlling peer")

    def _forward(self, event: InputEvent) -> None:
        if event.kind == "move":
            x, y = int(event.a), int(event.b)
            last = self._last_pointer or (x, y)
            dx, dy = x - last[0], y - last[1]
            w, h = self.local_screen
            center = (w // 2, h // 2)
            self.platform.set_pointer(*center)
            self._last_pointer = center
            pw, ph = self.peer_screen
            prev_x, prev_y = self._vx, self._vy
            self._vx = max(0, min(pw - 1, self._vx + dx))
            self._vy = max(0, min(ph - 1, self._vy + dy))
            if beyond_edge(
                OPPOSITE[self.config.edge],
                self._vx,
                self._vy,
                pw,
                ph,
                prev_x,
                prev_y,
            ):
                self._end_controlling()
                return
            self._send(protocol.MOVE, {"x": self._vx, "y": self._vy})
        else:
            self._send(event.kind, event.to_dict())

    def _end_controlling(self) -> None:
        self.platform.ungrab()
        self.platform.set_suppress(False)
        self.platform.set_pointer_visible(True)
        self.platform.release_all_keys()
        self._idle_last = None
        self.mode = "idle"
        self.debug_snapshot("handoff-end")
        self._debug("pointer released; suppression off; hidden=no")
        self._send(protocol.HANDOFF, {"from": "controlled"})
        log.info("control returned locally")

    def remote_message(self, kind: str, data: dict) -> None:
        if kind == protocol.HANDOFF:
            if data.get("from") == "controlling":
                self.mode = "controlled"
                self._remote_first = True
                self.platform.release_all_keys()
                self.platform.set_pointer_visible(True)
                self.debug_snapshot("remote-controlling")
                self._debug("pointer shown; hidden=no")
                log.info("peer is controlling us")
            else:
                self.mode = "idle"
                self.platform.set_suppress(False)
                self.platform.set_pointer_visible(True)
                self.platform.release_all_keys()
                self._idle_last = None
                self.debug_snapshot("remote-resumed")
                self._debug("pointer shown; suppression off; hidden=no")
                log.info("peer resumed local control")
        elif self.mode == "controlled":
            if kind == protocol.MOVE:
                x, y = int(data["x"]), int(data["y"])
                edge = self.config.edge
                pw, ph = self.local_screen
                if self._remote_first:
                    self._remote_first = False
                elif beyond_edge(
                    edge, x, y, pw, ph, self._last_remote_x, self._last_remote_y
                ):
                    self.mode = "idle"
                    self.platform.set_suppress(False)
                    self.platform.set_pointer_visible(True)
                    self.platform.release_all_keys()
                    self._idle_last = None
                    self.debug_snapshot("remote-handoff-back")
                    self._debug("pointer shown; suppression off; hidden=no")
                    self._send(protocol.HANDOFF, {"from": "controlled"})
                    self._last_remote_x, self._last_remote_y = x, y
                    return
                self._inject(InputEvent("move", x, y))
                self._last_remote_x, self._last_remote_y = x, y
            elif kind == protocol.BUTTON:
                self._inject(InputEvent.from_dict(data))
            elif kind == protocol.SCROLL:
                self._inject(InputEvent.from_dict(data))
            elif kind == protocol.KEY:
                self._inject(InputEvent.from_dict(data))
            elif kind == protocol.CLIPBOARD:
                text = data.get("text", "")
                self.clipboard.set_text(text)
                self._last_clip = text

    def poll_clipboard(self) -> None:
        if not self.config.clipboard or self.link is None:
            return
        now = self._clock()
        if now - self._clip_poll < 0.4:
            return
        self._clip_poll = now
        text = self.clipboard.get_text()
        if text and text != self._last_clip:
            self._last_clip = text
            self._send(protocol.CLIPBOARD, {"text": text})

    def _send(self, kind: str, data: dict | None = None) -> None:
        if self.link is not None:
            try:
                self.link.send(kind, data)
            except OSError:
                self._debug(f"send failed kind={kind}")
                log.warning("failed to send %s", kind)
