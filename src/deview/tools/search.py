"""deview_search MCP 도구 핸들러."""
from __future__ import annotations

from deview.embedding.base import EmbeddingProvider
from deview.storage.chroma import ChromaStore


async def handle_search(
    query: str,
    scope: str | None = None,
    top_k: int = 5,
    sort_by: str = "relevance",
    file_path: str | None = None,
    store: ChromaStore | None = None,
    embedding: EmbeddingProvider | None = None,
) -> dict:
    """맥락을 검색하여 결과를 반환한다."""
    assert store is not None
    assert embedding is not None

    query_vector = embedding.embed([query])[0]
    results = store.search(
        query_embedding=query_vector, scope=scope, top_k=top_k, file_path=file_path
    )

    if sort_by == "timestamp":
        results.sort(key=lambda x: x["metadata"].get("timestamp", ""), reverse=True)

    return {
        "results": [
            {
                "content": r["content"],
                "source": r["metadata"].get("source", ""),
                "file_paths": r["metadata"].get("file_paths", "").split(",")
                if r["metadata"].get("file_paths")
                else [],
                "author": r["metadata"].get("author", ""),
                "timestamp": r["metadata"].get("timestamp", ""),
                "score": r["score"],
            }
            for r in results
        ]
    }
