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
    if store is None:
        raise ValueError("store가 초기화되지 않았습니다")
    if embedding is None:
        raise ValueError("embedding provider가 초기화되지 않았습니다")
    if not content or not content.strip():
        raise ValueError("저장할 내용이 비어있습니다")

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
