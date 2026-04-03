"""Deview MCP 서버 진입점."""
from __future__ import annotations

import logging
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from deview.config import load_config, DeviewConfig, ProviderConfig
from deview.embedding import create_provider
from deview.embedding.base import EmbeddingProvider
from deview.scope import resolve_scope
from deview.storage.chroma import ChromaStore
from deview.tools.search import handle_search
from deview.tools.write import handle_write
from deview.tools.ingest import handle_ingest
from deview.tools.status import handle_status
from deview.tools.sync import handle_sync

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "Deview",
    instructions="Digital Psychometry for Developers — 프로젝트 맥락 저장소",
)

_store: ChromaStore | None = None
_embedding: EmbeddingProvider | None = None
_scope: str = ""
_provider_name: str = ""
_config_branch: str = "main"
_config: DeviewConfig | None = None


def _ensure_initialized() -> tuple[ChromaStore, EmbeddingProvider, str, str, str, "DeviewConfig"]:
    """최초 호출 시 설정을 로드하고 컴포넌트를 초기화한다."""
    global _store, _embedding, _scope, _provider_name, _config_branch, _config

    if _store is not None and _embedding is not None and _config is not None:
        return _store, _embedding, _scope, _provider_name, _config_branch, _config

    project_path = Path(os.environ.get("DEVIEW_PROJECT_PATH", Path.cwd()))
    config = load_config(project_path)
    _config = config
    _scope = resolve_scope(config.scope, project_path)
    _provider_name = config.embedding.provider
    _config_branch = config.ingestion.git.target_branch

    provider_config = config.embedding.providers.get(_provider_name, ProviderConfig())
    _embedding = create_provider(_provider_name, provider_config)
    _store = ChromaStore()

    logger.info("Deview 초기화 완료: scope=%s, provider=%s", _scope, _provider_name)
    return _store, _embedding, _scope, _provider_name, _config_branch, _config


@mcp.tool()
async def deview_search(
    query: str,
    scope: str = "",
    file_path: str = "",
    top_k: int = 5,
    sort_by: str = "relevance",
) -> dict:
    """프로젝트의 과거 의사결정, 컨벤션, 변경 히스토리, 특정 구현의 배경을 검색합니다.
    사용자가 '왜', '어떻게', '언제', '누가' 등 맥락을 물을 때 호출하세요.
    scope를 생략하면 전체 Scope를 통합 검색합니다."""
    store, embedding, default_scope, _, _, _ = _ensure_initialized()
    return await handle_search(
        query=query,
        scope=scope or None,
        top_k=top_k,
        sort_by=sort_by,
        file_path=file_path or None,
        store=store,
        embedding=embedding,
    )


@mcp.tool()
async def deview_write(
    content: str,
    scope: str = "",
    file_paths: list[str] | None = None,
) -> dict:
    """사용자가 명시적으로 지시할 때, 중요한 의사결정이나 기술적 맥락을 기록합니다.
    사용자가 '기록해', '저장해', '메모해' 등의 지시를 할 때 호출하세요."""
    store, embedding, default_scope, _, _, _ = _ensure_initialized()
    return await handle_write(
        content=content,
        scope=scope or default_scope,
        file_paths=file_paths,
        store=store,
        embedding=embedding,
    )


@mcp.tool()
async def deview_ingest(
    scope: str = "",
    source_type: str = "auto",
    max_commits: int | None = None,
    incremental: bool = True,
) -> dict:
    """프로젝트의 Git 히스토리 또는 Markdown 문서를 인덱싱합니다.
    최초 사용 시 또는 새로운 데이터를 수동으로 추가할 때 호출하세요.
    incremental=True(기본)이면 마지막 인덱싱 이후 새 데이터만 추가합니다."""
    store, embedding, default_scope, _, branch, _ = _ensure_initialized()
    resolved_path = os.environ.get("DEVIEW_PROJECT_PATH", str(Path.cwd()))
    return await handle_ingest(
        path=resolved_path,
        scope=scope or default_scope,
        source_type=source_type,
        max_commits=max_commits,
        store=store,
        embedding=embedding,
        branch=branch,
        incremental=incremental,
    )


@mcp.tool()
async def deview_status(
    scope: str = "",
) -> dict:
    """현재 Deview의 상태를 확인합니다.
    Scope 정보, 인덱싱된 청크 수, 마지막 인덱싱 시각 등을 반환합니다."""
    store, _, default_scope, provider_name, _, _ = _ensure_initialized()
    return await handle_status(
        scope=scope or default_scope,
        store=store,
        embedding_provider=provider_name,
    )


@mcp.tool()
async def deview_sync(
    source: str,
    scope: str = "",
    project: str = "",
    space: str = "",
) -> dict:
    """외부 소스(Jira, Confluence)의 데이터를 동기화합니다.
    source='jira'이면 project 파라미터(Jira 프로젝트 키)가 필요하고,
    source='confluence'이면 space 파라미터(Confluence 스페이스 키)가 필요합니다."""
    store, embedding, default_scope, _, _, config = _ensure_initialized()
    resolved_scope = scope or default_scope

    jira_cfg = config.integrations.jira
    conf_cfg = config.integrations.confluence

    return await handle_sync(
        source=source,
        scope=resolved_scope,
        store=store,
        embedding=embedding,
        jira_url=jira_cfg.url,
        jira_email=jira_cfg.email,
        jira_token=jira_cfg.api_token,
        jira_project=project,
        confluence_url=conf_cfg.url,
        confluence_email=conf_cfg.email,
        confluence_token=conf_cfg.api_token,
        confluence_space=space,
    )


if __name__ == "__main__":
    mcp.run()
