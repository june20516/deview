"""임베딩 프로바이더 추상 인터페이스."""
from __future__ import annotations
from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """텍스트 리스트를 벡터 리스트로 변환한다."""
        ...

    @abstractmethod
    def dimension(self) -> int:
        """벡터 차원 수를 반환한다."""
        ...
