from __future__ import annotations

import logging
import time

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
    ) -> None:
        self.config = config
        self.platform = platform
        self.clipboard = clipboard
        self._clock = clock
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

    def attach(self, link: Link) -> None:
        self.link = link
        self.peer_screen = link.peer_screen
        log.info("peer attached, screen %s", self.peer_screen)

    def request_handoff(self) -> None:
        if self.link is None or not self.config.primary:
            return
        if self.mode == "idle":
            self._begin_controlling(*self.platform.pointer_position())
        elif self.mode == "controlled":
            self.platform.release_all_keys()
            self._idle_last = None
            self.mode = "idle"
            self._send(protocol.HANDOFF, {"from": "controlled"})

    def detach(self) -> None:
        self.platform.ungrab()
        self.platform.set_suppress(False)
        self.platform.release_all_keys()
        self._idle_last = None
        self.mode = "idle"
        self.link = None

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
                    self._begin_controlling(x, y)
        elif self.mode == "controlling":
            self._forward(event)
        elif self.mode == "controlled" and event.kind in ("key", "button"):
            if event.kind == "key" and event.b:
                self.platform.release_all_keys()
                self.platform.set_suppress(False)
                self._idle_last = None
                self._send(protocol.HANDOFF, {"from": "controlled"})
                self.mode = "idle"

    def _begin_controlling(self, x: int, y: int) -> None:
        w, h = self.local_screen
        pw, ph = self.peer_screen or (w, h)
        self._vx, self._vy = entry_point(OPPOSITE[self.config.edge], pw, ph)
        center = (w // 2, h // 2)
        self.platform.grab()
        self.platform.set_suppress(True)
        self.platform.set_pointer(*center)
        self._last_pointer = center
        self._idle_last = None
        self.mode = "controlling"
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
        self.platform.release_all_keys()
        self._idle_last = None
        self.mode = "idle"
        self._send(protocol.HANDOFF, {"from": "controlled"})
        log.info("control returned locally")

    def remote_message(self, kind: str, data: dict) -> None:
        if kind == protocol.HANDOFF:
            if data.get("from") == "controlling":
                self.mode = "controlled"
                self._remote_first = True
                self.platform.release_all_keys()
                log.info("peer is controlling us")
            else:
                self.mode = "idle"
                self.platform.set_suppress(False)
                self.platform.release_all_keys()
                self._idle_last = None
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
                    self.platform.release_all_keys()
                    self._idle_last = None
                    self._send(protocol.HANDOFF, {"from": "controlled"})
                    self._last_remote_x, self._last_remote_y = x, y
                    return
                self.platform.inject(InputEvent("move", x, y))
                self._last_remote_x, self._last_remote_y = x, y
            elif kind == protocol.BUTTON:
                self.platform.inject(InputEvent.from_dict(data))
            elif kind == protocol.SCROLL:
                self.platform.inject(InputEvent.from_dict(data))
            elif kind == protocol.KEY:
                self.platform.inject(InputEvent.from_dict(data))
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
                log.warning("failed to send %s", kind)
