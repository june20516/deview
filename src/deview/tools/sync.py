"""Jira/Confluence 동기화 핸들러."""
from __future__ import annotations

import logging
import uuid

from deview.embedding.base import EmbeddingProvider
from deview.ingestion.jira import parse_jira_issues
from deview.ingestion.confluence import parse_confluence_pages
from deview.storage.chroma import ChromaStore

logger = logging.getLogger(__name__)


def _create_jira_client(url: str, email: str, token: str):
    """Jira API 클라이언트를 생성한다."""
    from atlassian import Jira
    return Jira(url=url, username=email, password=token)


def _create_confluence_client(url: str, email: str, token: str):
    """Confluence API 클라이언트를 생성한다."""
    from atlassian import Confluence
    return Confluence(url=url, username=email, password=token)


async def handle_sync(
    source: str,
    scope: str,
    store: ChromaStore,
    embedding: EmbeddingProvider,
    jira_url: str = "",
    jira_email: str = "",
    jira_token: str = "",
    jira_project: str = "",
    confluence_url: str = "",
    confluence_email: str = "",
    confluence_token: str = "",
    confluence_space: str = "",
) -> dict:
    """외부 소스를 동기화한다."""
    if source == "jira":
        return await _sync_jira(
            scope=scope, store=store, embedding=embedding,
            url=jira_url, email=jira_email, token=jira_token, project=jira_project,
        )
    elif source == "confluence":
        return await _sync_confluence(
            scope=scope, store=store, embedding=embedding,
            url=confluence_url, email=confluence_email, token=confluence_token, space=confluence_space,
        )
    else:
        raise ValueError(f"지원하지 않는 소스: {source}")


async def _sync_jira(
    scope: str,
    store: ChromaStore,
    embedding: EmbeddingProvider,
    url: str,
    email: str,
    token: str,
    project: str,
) -> dict:
    """Jira 이슈를 동기화한다."""
    client = _create_jira_client(url, email, token)

    latest = store.get_latest_timestamp(scope, "jira")
    jql = f'project = "{project}" AND status in (Done, Closed)'
    if latest:
        jql += f' AND updated >= "{latest}"'
    jql += " ORDER BY updated ASC"

    result = client.jql(jql)
    issues = result.get("issues", [])

    if not issues:
        return {"source": "jira", "scope": scope, "chunks_indexed": 0}

    chunks = parse_jira_issues(issues, scope=scope)
    if not chunks:
        return {"source": "jira", "scope": scope, "chunks_indexed": 0}

    ids = [f"jira-{c.metadata['jira_key']}" for c in chunks]
    contents = [c.content for c in chunks]
    metadatas = [c.metadata for c in chunks]
    vectors = embedding.embed(contents)
    store.add(ids=ids, embeddings=vectors, contents=contents, metadatas=metadatas)

    return {"source": "jira", "scope": scope, "chunks_indexed": len(chunks)}


async def _sync_confluence(
    scope: str,
    store: ChromaStore,
    embedding: EmbeddingProvider,
    url: str,
    email: str,
    token: str,
    space: str,
) -> dict:
    """Confluence 페이지를 동기화한다."""
    client = _create_confluence_client(url, email, token)

    pages = client.get_all_pages_from_space(
        space, start=0, limit=500, expand="body.storage,version",
    )

    latest = store.get_latest_timestamp(scope, "confluence")
    if latest:
        pages = [
            p for p in pages
            if p.get("version", {}).get("when", "")[:10] >= latest
        ]

    if not pages:
        return {"source": "confluence", "scope": scope, "chunks_indexed": 0}

    chunks = parse_confluence_pages(pages, scope=scope)
    if not chunks:
        return {"source": "confluence", "scope": scope, "chunks_indexed": 0}

    ids = []
    for c in chunks:
        section = c.metadata.get("section", "")
        base_id = c.metadata["document_id"]
        if section:
            ids.append(f"{base_id}-{hash(section) % 100000:05d}")
        else:
            ids.append(base_id)

    contents = [c.content for c in chunks]
    metadatas = [c.metadata for c in chunks]
    vectors = embedding.embed(contents)
    store.add(ids=ids, embeddings=vectors, contents=contents, metadatas=metadatas)

    return {"source": "confluence", "scope": scope, "chunks_indexed": len(chunks)}
