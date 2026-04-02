from deview.embedding.base import EmbeddingProvider
from deview.embedding import create_provider
from deview.config import ProviderConfig


def test_base_interface():
    """EmbeddingProvider는 embed()와 dimension()을 요구한다."""
    assert hasattr(EmbeddingProvider, "embed")
    assert hasattr(EmbeddingProvider, "dimension")


def test_create_provider_voyage():
    """voyage provider를 생성할 수 있다."""
    provider = create_provider("voyage", ProviderConfig(
        model="voyage-3.5-lite",
        api_key="test-key",
    ))
    assert isinstance(provider, EmbeddingProvider)
    assert provider.dimension() == 1024


def test_create_provider_openai():
    """openai provider를 생성할 수 있다."""
    provider = create_provider("openai", ProviderConfig(
        model="text-embedding-3-small",
        api_key="test-key",
    ))
    assert isinstance(provider, EmbeddingProvider)
    assert provider.dimension() == 1536


def test_create_provider_unknown():
    """알 수 없는 provider는 ValueError를 발생시킨다."""
    import pytest
    with pytest.raises(ValueError, match="Unknown embedding provider"):
        create_provider("unknown", ProviderConfig())
