"""Mistral AI 임베딩 프로바이더."""
from __future__ import annotations

from mistralai import Mistral

from deview.embedding.base import EmbeddingProvider

_MODEL_DIMENSIONS: dict[str, int] = {
    "mistral-embed": 1024,
}
_DEFAULT_MODEL = "mistral-embed"
_BATCH_SIZE = 128


class MistralEmbedding(EmbeddingProvider):
    def __init__(self, model: str = "", api_key: str = "") -> None:
        self._model = model or _DEFAULT_MODEL
        self._client = Mistral(api_key=api_key) if api_key else Mistral()

    def embed(self, texts: list[str]) -> list[list[float]]:
        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), _BATCH_SIZE):
            batch = texts[i : i + _BATCH_SIZE]
            result = self._client.embeddings.create(model=self._model, inputs=batch)
            all_embeddings.extend([d.embedding for d in result.data])
        return all_embeddings

    def dimension(self) -> int:
        return _MODEL_DIMENSIONS.get(self._model, 1024)
