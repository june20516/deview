"""Deview CLI 도구."""
from __future__ import annotations

import asyncio
import json
import os
import stat
from pathlib import Path

import typer

from deview.config import load_config, ProviderConfig
from deview.embedding import create_provider
from deview.scope import resolve_scope
from deview.storage.chroma import ChromaStore

app = typer.Typer(help="Deview — Digital Psychometry for Developers")


def _get_components():
    """설정을 로드하고 컴포넌트를 초기화한다."""
    project_path = Path(os.environ.get("DEVIEW_PROJECT_PATH", Path.cwd()))
    config = load_config(project_path)
    scope = resolve_scope(config.scope, project_path)
    provider_name = config.embedding.provider
    provider_config = config.embedding.providers.get(provider_name, ProviderConfig())
    embedding = create_provider(provider_name, provider_config)
    store = ChromaStore()
    return store, embedding, scope, config


@app.command()
def status(
    scope: str = typer.Option("", help="조회할 scope (생략 시 자동 추론)"),
):
    """현재 Deview 상태를 조회한다."""
    from deview.tools.status import handle_status

    store, _, default_scope, config = _get_components()
    result = asyncio.run(handle_status(
        scope=scope or default_scope,
        store=store,
        embedding_provider=config.embedding.provider,
    ))
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


@app.command()
def search(
    query: str = typer.Argument(..., help="검색 질문"),
    scope: str = typer.Option("", help="검색할 scope"),
    top_k: int = typer.Option(5, help="반환할 결과 수"),
):
    """맥락을 검색한다."""
    from deview.tools.search import handle_search

    store, embedding, default_scope, _ = _get_components()
    result = asyncio.run(handle_search(
        query=query,
        scope=scope or None,
        top_k=top_k,
        store=store,
        embedding=embedding,
    ))
    for r in result["results"]:
        typer.echo(f"[{r['score']:.2f}] {r['source']} | {r['timestamp']} | {r['author']}")
        typer.echo(f"  {r['content'][:200]}")
        typer.echo()


@app.command()
def ingest(
    scope: str = typer.Option("", help="인덱싱할 scope"),
    source_type: str = typer.Option("auto", help="git | markdown | auto"),
    incremental: bool = typer.Option(True, help="증분 인덱싱 (기본 True)"),
):
    """프로젝트를 인덱싱한다."""
    from deview.tools.ingest import handle_ingest

    store, embedding, default_scope, config = _get_components()
    resolved_path = os.environ.get("DEVIEW_PROJECT_PATH", str(Path.cwd()))
    result = asyncio.run(handle_ingest(
        path=resolved_path,
        scope=scope or default_scope,
        source_type=source_type,
        store=store,
        embedding=embedding,
        branch=config.ingestion.git.target_branch,
        incremental=incremental,
    ))
    typer.echo(f"인덱싱 완료: {result['chunks_indexed']}개 청크 ({result['source_type']})")


@app.command()
def sync(
    source: str = typer.Argument(..., help="동기화 소스 (jira | confluence)"),
    project: str = typer.Option("", help="Jira 프로젝트 키"),
    space: str = typer.Option("", help="Confluence 스페이스 키"),
    scope: str = typer.Option("", help="scope"),
):
    """외부 소스(Jira, Confluence)를 동기화한다."""
    from deview.tools.sync import handle_sync

    store, embedding, default_scope, config = _get_components()
    integ = config.integrations

    result = asyncio.run(handle_sync(
        source=source,
        scope=scope or default_scope,
        store=store,
        embedding=embedding,
        atlassian_url=integ.jira_url,
        atlassian_email=integ.email,
        atlassian_token=integ.api_token,
        jira_project=project,
        confluence_space=space,
    ))
    typer.echo(f"동기화 완료: {result['chunks_indexed']}개 청크 ({result['source']})")


# Git Hook 서브커맨드
hook_app = typer.Typer(help="Git hook 관리")
app.add_typer(hook_app, name="hook")

_HOOK_SCRIPT = """\
#!/bin/sh
# Deview post-merge hook — 증분 인덱싱 실행
# 실패해도 merge를 막지 않음
deview ingest --incremental 2>/dev/null &
"""


@hook_app.command()
def install():
    """post-merge hook을 설치한다."""
    project_path = Path(os.environ.get("DEVIEW_PROJECT_PATH", Path.cwd()))
    hooks_dir = project_path / ".git" / "hooks"
    if not hooks_dir.exists():
        typer.echo("Error: .git/hooks 디렉토리를 찾을 수 없습니다.", err=True)
        raise typer.Exit(1)

    hook_path = hooks_dir / "post-merge"
    hook_path.write_text(_HOOK_SCRIPT)
    hook_path.chmod(hook_path.stat().st_mode | stat.S_IEXEC)
    typer.echo(f"Hook 설치 완료: {hook_path}")


@hook_app.command()
def uninstall():
    """post-merge hook을 제거한다."""
    project_path = Path(os.environ.get("DEVIEW_PROJECT_PATH", Path.cwd()))
    hook_path = project_path / ".git" / "hooks" / "post-merge"

    if hook_path.exists():
        hook_path.unlink()
        typer.echo(f"Hook 제거 완료: {hook_path}")
    else:
        typer.echo("Hook이 설치되어 있지 않습니다.")
