"""deview_write MCP 도구 핸들러."""
from __future__ import annotations

from deview.embedding.base import EmbeddingProvider
from deview.ingestion.manual import create_manual_chunk, generate_chunk_id
from deview.storage.chroma import ChromaStore


async def handle_write(
    content: str,
    scope: str,
    file_paths: list[str] | None = None,
    store: ChromaStore | None = None,
    embedding: EmbeddingProvider | None = None,
) -> dict:
    """수동 맥락을 저장한다."""
    assert store is not None
    assert embedding is not None

    chunk = create_manual_chunk(content, scope, file_paths)
    chunk_id = generate_chunk_id()
    vector = embedding.embed([chunk.content])[0]
    store.add(
        ids=[chunk_id],
        embeddings=[vector],
        contents=[chunk.content],
        metadatas=[chunk.metadata],
    )
    return {"id": chunk_id, "scope": scope}
