"""인제스션 모듈 공통 모델."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Chunk:
    content: str
    metadata: dict[str, str] = field(default_factory=dict)
