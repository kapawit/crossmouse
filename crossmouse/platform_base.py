from __future__ import annotations

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
