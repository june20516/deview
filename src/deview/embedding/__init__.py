"""임베딩 프로바이더 팩토리."""
from __future__ import annotations
from deview.config import ProviderConfig
from deview.embedding.base import EmbeddingProvider


def create_provider(name: str, config: ProviderConfig) -> EmbeddingProvider:
    """프로바이더 이름으로 구현체를 생성한다."""
    if name == "voyage":
        from deview.embedding.voyage import VoyageEmbedding
        return VoyageEmbedding(model=config.model, api_key=config.api_key)
    elif name == "openai":
        from deview.embedding.openai import OpenAIEmbedding
        return OpenAIEmbedding(model=config.model, api_key=config.api_key)
    elif name == "local":
        from deview.embedding.local import LocalEmbedding
        return LocalEmbedding(model=config.model)
    elif name == "mistral":
        from deview.embedding.mistral import MistralEmbedding
        return MistralEmbedding(model=config.model, api_key=config.api_key)
    else:
        raise ValueError(f"Unknown embedding provider: {name}")
