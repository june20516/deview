"""OpenAI 임베딩 프로바이더."""
from __future__ import annotations
from openai import OpenAI
from deview.embedding.base import EmbeddingProvider

_MODEL_DIMENSIONS: dict[str, int] = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}
_DEFAULT_MODEL = "text-embedding-3-small"
_BATCH_SIZE = 2048


class OpenAIEmbedding(EmbeddingProvider):
    def __init__(self, model: str = "", api_key: str = "") -> None:
        self._model = model or _DEFAULT_MODEL
        self._client = OpenAI(api_key=api_key) if api_key else OpenAI()

    def embed(self, texts: list[str]) -> list[list[float]]:
        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), _BATCH_SIZE):
            batch = texts[i : i + _BATCH_SIZE]
            response = self._client.embeddings.create(input=batch, model=self._model)
            all_embeddings.extend([d.embedding for d in response.data])
        return all_embeddings

    def dimension(self) -> int:
        return _MODEL_DIMENSIONS.get(self._model, 1536)
