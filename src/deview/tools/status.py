"""deview_status MCP 도구 핸들러."""
from __future__ import annotations

from deview.storage.chroma import ChromaStore


async def handle_status(
    scope: str,
    store: ChromaStore | None = None,
    embedding_provider: str = "",
) -> dict:
    """현재 Deview 상태를 반환한다."""
    assert store is not None

    sources = store.count_by_source(scope)
    total = sum(sources.values())
    last_indexed = store.get_last_indexed(scope)

    return {
        "scope": scope,
        "total_chunks": total,
        "sources": sources,
        "last_indexed": last_indexed,
        "embedding_provider": embedding_provider,
    }
