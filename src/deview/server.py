"""Deview MCP 서버 진입점."""
from __future__ import annotations
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from deview.config import load_config, ProviderConfig
from deview.embedding import create_provider
from deview.scope import resolve_scope
from deview.storage.chroma import ChromaStore
from deview.tools.search import handle_search
from deview.tools.write import handle_write
from deview.tools.ingest import handle_ingest
from deview.tools.status import handle_status

mcp = FastMCP(
    "Deview",
    instructions="Digital Psychometry for Developers — 프로젝트 맥락 저장소",
)

_project_path = Path.cwd()
_config = load_config(_project_path)
_scope = resolve_scope(_config.scope, _project_path)

_provider_name = _config.embedding.provider
_provider_config = _config.embedding.providers.get(
    _provider_name, ProviderConfig()
)
_embedding = create_provider(_provider_name, _provider_config)
_store = ChromaStore()


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
    return await handle_search(
        query=query,
        scope=scope or None,
        top_k=top_k,
        sort_by=sort_by,
        file_path=file_path or None,
        store=_store,
        embedding=_embedding,
    )


@mcp.tool()
async def deview_write(
    content: str,
    scope: str = "",
    file_paths: list[str] | None = None,
) -> dict:
    """사용자가 명시적으로 지시할 때, 중요한 의사결정이나 기술적 맥락을 기록합니다.
    사용자가 '기록해', '저장해', '메모해' 등의 지시를 할 때 호출하세요."""
    return await handle_write(
        content=content,
        scope=scope or _scope,
        file_paths=file_paths,
        store=_store,
        embedding=_embedding,
    )


@mcp.tool()
async def deview_ingest(
    path: str,
    scope: str = "",
    source_type: str = "auto",
    max_commits: int | None = None,
) -> dict:
    """프로젝트의 Git 히스토리 또는 Markdown 문서를 인덱싱합니다.
    최초 사용 시 또는 새로운 데이터를 수동으로 추가할 때 호출하세요."""
    return await handle_ingest(
        path=path,
        scope=scope or _scope,
        source_type=source_type,
        max_commits=max_commits,
        store=_store,
        embedding=_embedding,
        branch=_config.ingestion.git.target_branch,
    )


@mcp.tool()
async def deview_status(
    scope: str = "",
) -> dict:
    """현재 Deview의 상태를 확인합니다.
    Scope 정보, 인덱싱된 청크 수, 마지막 인덱싱 시각 등을 반환합니다."""
    return await handle_status(
        scope=scope or _scope,
        store=_store,
        embedding_provider=_provider_name,
    )
