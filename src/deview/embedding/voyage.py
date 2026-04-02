"""Voyage AI 임베딩 프로바이더."""
from __future__ import annotations
import voyageai
from deview.embedding.base import EmbeddingProvider

_MODEL_DIMENSIONS: dict[str, int] = {
    "voyage-3.5-lite": 1024,
    "voyage-3.5": 1024,
    "voyage-4-large": 1024,
    "voyage-4": 1024,
    "voyage-4-lite": 512,
    "voyage-code-3": 1024,
}
_DEFAULT_MODEL = "voyage-3.5-lite"
_BATCH_SIZE = 128


class VoyageEmbedding(EmbeddingProvider):
    def __init__(self, model: str = "", api_key: str = "") -> None:
        self._model = model or _DEFAULT_MODEL
        self._client = voyageai.Client(api_key=api_key) if api_key else voyageai.Client()

    def embed(self, texts: list[str]) -> list[list[float]]:
        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), _BATCH_SIZE):
            batch = texts[i : i + _BATCH_SIZE]
            result = self._client.embed(batch, model=self._model, input_type="document")
            all_embeddings.extend(result.embeddings)
        return all_embeddings

    def dimension(self) -> int:
        return _MODEL_DIMENSIONS.get(self._model, 1024)
