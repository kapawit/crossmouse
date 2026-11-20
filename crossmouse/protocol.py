from __future__ import annotations

import json
import struct

HEADER = struct.Struct("!I")

HELLO = "hello"
AUTH = "auth"
AUTH_OK = "auth_ok"
AUTH_FAIL = "auth_fail"
MOVE = "move"
BUTTON = "button"
SCROLL = "scroll"
KEY = "key"
CLIPBOARD = "clipboard"
HANDOFF = "handoff"
PING = "ping"

MAX_FRAME = 1 << 20


def frame(payload: bytes) -> bytes:
    if len(payload) > MAX_FRAME:
        raise ValueError("payload too large")
    return HEADER.pack(len(payload)) + payload


def unframe(buffer: bytearray) -> bytes | None:
    if len(buffer) < HEADER.size:
        return None
    (length,) = HEADER.unpack_from(buffer)
    if length > MAX_FRAME:
        raise ValueError("frame too large")
    if len(buffer) < HEADER.size + length:
        return None
    payload = bytes(buffer[HEADER.size : HEADER.size + length])
    del buffer[: HEADER.size + length]
    return payload


def encode(kind: str, data: dict | None = None) -> bytes:
    return frame(json.dumps({"t": kind, "d": data or {}}).encode("utf-8"))


def decode(payload: bytes) -> tuple[str, dict]:
    obj = json.loads(payload.decode("utf-8"))
    return obj["t"], obj.get("d", {})
