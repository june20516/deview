"""deview_ingest MCP 도구 핸들러."""
from __future__ import annotations

import uuid
from pathlib import Path

from deview.embedding.base import EmbeddingProvider
from deview.ingestion.git import parse_git_history
from deview.ingestion.markdown import parse_markdown_files
from deview.storage.chroma import ChromaStore


async def handle_ingest(
    path: str,
    scope: str,
    source_type: str = "auto",
    max_commits: int | None = None,
    store: ChromaStore | None = None,
    embedding: EmbeddingProvider | None = None,
    branch: str = "main",
) -> dict:
    """Git 히스토리 또는 Markdown 문서를 인덱싱한다."""
    assert store is not None
    assert embedding is not None

    target = Path(path)
    resolved_type = source_type

    if source_type == "auto":
        if (target / ".git").exists():
            resolved_type = "git"
        else:
            resolved_type = "markdown"

    if resolved_type == "git":
        chunks = parse_git_history(
            target, branch=branch, scope=scope, max_commits=max_commits
        )
    elif resolved_type == "markdown":
        chunks = parse_markdown_files(target, scope=scope)
    else:
        return {"scope": scope, "chunks_indexed": 0, "source_type": resolved_type}

    if not chunks:
        return {"scope": scope, "chunks_indexed": 0, "source_type": resolved_type}

    ids = [f"{resolved_type}-{uuid.uuid4().hex[:12]}" for _ in chunks]
    contents = [c.content for c in chunks]
    metadatas = [c.metadata for c in chunks]
    vectors = embedding.embed(contents)
    store.add(ids=ids, embeddings=vectors, contents=contents, metadatas=metadatas)

    return {"scope": scope, "chunks_indexed": len(chunks), "source_type": resolved_type}
