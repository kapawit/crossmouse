from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import Callable

EventSink = Callable[["InputEvent"], None]


@dataclass(frozen=True)
class InputEvent:
    kind: str
    a: int | str = 0
    b: int = 0

    def to_dict(self) -> dict:
        return {"k": self.kind, "a": self.a, "b": self.b}

    @classmethod
    def from_dict(cls, data: dict) -> "InputEvent":
        return cls(kind=data["k"], a=data["a"], b=data.get("b", 0))


class Platform:
    def screen_size(self) -> tuple[int, int]:
        raise NotImplementedError

    def pointer_position(self) -> tuple[int, int]:
        raise NotImplementedError

    def set_pointer(self, x: int, y: int) -> None:
        raise NotImplementedError

    def grab(self) -> None:
        raise NotImplementedError

    def ungrab(self) -> None:
        raise NotImplementedError

    def start_capture(self, sink: EventSink) -> None:
        raise NotImplementedError

    def stop_capture(self) -> None:
        raise NotImplementedError

    def inject(self, event: InputEvent) -> None:
        raise NotImplementedError

    def release_all_keys(self) -> None:
        raise NotImplementedError

    def set_suppress(self, value: bool) -> None:
        pass

    def remember_injection(self, event: InputEvent) -> None:
        injected = getattr(self, "_injected", None)
        if injected is None:
            injected = self._injected = deque()
        injected.append((event.kind, event.a, event.b, time.monotonic()))

    def is_own_injection(self, event: InputEvent) -> bool:
        injected = getattr(self, "_injected", None)
        if not injected:
            return False
        now = time.monotonic()
        while injected and now - injected[0][3] > 1.0:
            injected.popleft()
        for index, (kind, a, b, _) in enumerate(injected):
            if (kind, a, b) == (event.kind, event.a, event.b):
                del injected[index]
                return True
        return False
