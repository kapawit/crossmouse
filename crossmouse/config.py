from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path

EDGES = ("left", "right", "top", "bottom")


@dataclass(frozen=True)
class Config:
    secret: str
    peer_ip: str | None = None
    port: int = 52800
    edge: str = "right"
    clipboard: bool = True

    def __post_init__(self) -> None:
        if not self.secret:
            raise ValueError("secret must not be empty")
        if self.edge not in EDGES:
            raise ValueError(f"edge must be one of {EDGES}")
        if not 1 <= self.port <= 65535:
            raise ValueError("port must be between 1 and 65535")

    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        return cls(
            secret=data["secret"],
            peer_ip=data.get("peer_ip"),
            port=int(data.get("port", 52800)),
            edge=data.get("edge", "right"),
            clipboard=bool(data.get("clipboard", True)),
        )

    @classmethod
    def from_file(cls, path: str | Path) -> "Config":
        return cls.from_dict(json.loads(Path(path).read_text()))

    def to_dict(self) -> dict:
        return asdict(self)
