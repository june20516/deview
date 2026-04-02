"""로컬 임베딩 프로바이더 (sentence-transformers)."""
from __future__ import annotations
from deview.embedding.base import EmbeddingProvider

_DEFAULT_MODEL = "BAAI/bge-large-en-v1.5"
_MODEL_DIMENSIONS: dict[str, int] = {
    "BAAI/bge-large-en-v1.5": 1024,
    "BAAI/bge-base-en-v1.5": 768,
    "sentence-transformers/all-MiniLM-L6-v2": 384,
}


class LocalEmbedding(EmbeddingProvider):
    def __init__(self, model: str = "", api_key: str = "") -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise ImportError(
                "로컬 임베딩을 사용하려면 추가 패키지가 필요합니다: uv sync --extra local"
            ) from e
        self._model_name = model or _DEFAULT_MODEL
        self._model = SentenceTransformer(self._model_name)

    def embed(self, texts: list[str]) -> list[list[float]]:
        embeddings = self._model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()

    def dimension(self) -> int:
        return _MODEL_DIMENSIONS.get(self._model_name, 1024)
