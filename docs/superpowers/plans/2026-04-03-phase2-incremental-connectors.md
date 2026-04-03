# Phase 2: 증분 인덱싱 + 외부 커넥터 + CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 증분 인덱싱, Jira/Confluence 커넥터, Git Hook, CLI를 추가하여 Deview의 데이터 수집을 자동화하고 코드 외부 맥락을 통합한다.

**Architecture:** ChromaStore에 증분 인덱싱 지원 메서드를 추가하고, 기존 ingest 파이프라인에 `since_commit` 파라미터를 추가한다. Jira/Confluence 커넥터는 `ingestion/` 모듈에 새 파일로 추가하며 동일한 Chunk 모델을 사용한다. CLI는 `typer` 기반으로 `cli.py`에 구현하고, Git Hook은 CLI의 `hook` 서브커맨드로 설치/제거한다. 설정은 기존 `config.py`에 integrations 섹션을 확장한다.

**Tech Stack:** Python 3.10+, typer (CLI), atlassian-python-api (Jira/Confluence), ChromaDB, pytest

---

## File Structure

```
src/deview/
├── config.py                    # 수정: IntegrationConfig 추가
├── cli.py                       # 생성: typer CLI 진입점
├── ingestion/
│   ├── __init__.py              # 유지
│   ├── git.py                   # 수정: since_commit 파라미터 추가
│   ├── markdown.py              # 유지
│   ├── manual.py                # 유지
│   ├── jira.py                  # 생성: Jira 커넥터
│   └── confluence.py            # 생성: Confluence 커넥터
├── storage/
│   └── chroma.py                # 수정: get_latest_commit_hash, get_latest_timestamp 추가
├── tools/
│   ├── ingest.py                # 수정: 증분 인덱싱 지원
│   └── sync.py                  # 생성: Jira/Confluence 동기화 핸들러
└── server.py                    # 수정: deview_sync MCP 도구 추가

tests/
├── test_storage.py              # 수정: 새 메서드 테스트 추가
├── test_ingestion_git.py        # 수정: 증분 인덱싱 테스트
├── test_ingestion_jira.py       # 생성
├── test_ingestion_confluence.py # 생성
├── test_tools_sync.py           # 생성
├── test_cli.py                  # 생성

pyproject.toml                   # 수정: typer, atlassian-python-api 추가
```

---

### Task 1: ChromaStore 증분 인덱싱 지원 메서드

**Files:**
- Modify: `src/deview/storage/chroma.py`
- Modify: `tests/test_storage.py`

- [ ] **Step 1: Write failing tests for get_latest_commit_hash and get_latest_timestamp**

```python
# tests/test_storage.py 에 추가

def test_get_latest_commit_hash(store: ChromaStore):
    """scope의 git 소스 중 가장 최근 commit_hash를 반환한다."""
    store.add(
        ids=["g1", "g2"],
        embeddings=[[0.1, 0.2, 0.3]] * 2,
        contents=["first commit", "second commit"],
        metadatas=[
            {"scope": "proj", "source": "git", "commit_hash": "aaa1111", "timestamp": "2025-01-01"},
            {"scope": "proj", "source": "git", "commit_hash": "bbb2222", "timestamp": "2025-06-15"},
        ],
    )
    assert store.get_latest_commit_hash("proj") == "bbb2222"


def test_get_latest_commit_hash_empty(store: ChromaStore):
    """데이터가 없으면 None을 반환한다."""
    assert store.get_latest_commit_hash("nonexistent") is None


def test_get_latest_timestamp(store: ChromaStore):
    """scope + source 조합의 최신 timestamp를 반환한다."""
    store.add(
        ids=["j1", "j2"],
        embeddings=[[0.1, 0.2, 0.3]] * 2,
        contents=["issue 1", "issue 2"],
        metadatas=[
            {"scope": "proj", "source": "jira", "timestamp": "2025-03-01"},
            {"scope": "proj", "source": "jira", "timestamp": "2025-09-20"},
        ],
    )
    assert store.get_latest_timestamp("proj", "jira") == "2025-09-20"


def test_get_latest_timestamp_empty(store: ChromaStore):
    """데이터가 없으면 None을 반환한다."""
    assert store.get_latest_timestamp("proj", "jira") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_storage.py::test_get_latest_commit_hash tests/test_storage.py::test_get_latest_commit_hash_empty tests/test_storage.py::test_get_latest_timestamp tests/test_storage.py::test_get_latest_timestamp_empty -v`
Expected: FAIL with AttributeError

- [ ] **Step 3: Implement get_latest_commit_hash and get_latest_timestamp**

`src/deview/storage/chroma.py`에 두 메서드를 추가한다:

```python
def get_latest_commit_hash(self, scope: str) -> str | None:
    """scope의 git 소스 중 가장 최근 commit_hash를 반환한다."""
    try:
        result = self._collection.get(
            where={"$and": [{"scope": scope}, {"source": "git"}]}
        )
        if not result["metadatas"]:
            return None
        # timestamp가 가장 큰 항목의 commit_hash 반환
        entries = [
            (m.get("timestamp", ""), m.get("commit_hash", ""))
            for m in result["metadatas"]
            if m.get("commit_hash")
        ]
        if not entries:
            return None
        entries.sort(key=lambda x: x[0], reverse=True)
        return entries[0][1]
    except Exception:
        logger.exception("최신 commit_hash 조회 중 오류")
        return None

def get_latest_timestamp(self, scope: str, source: str) -> str | None:
    """scope + source 조합의 최신 timestamp를 반환한다."""
    try:
        result = self._collection.get(
            where={"$and": [{"scope": scope}, {"source": source}]}
        )
        if not result["metadatas"]:
            return None
        timestamps = [
            m.get("timestamp", "")
            for m in result["metadatas"]
            if m.get("timestamp")
        ]
        return max(timestamps) if timestamps else None
    except Exception:
        logger.exception("최신 timestamp 조회 중 오류: source=%s", source)
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_storage.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/deview/storage/chroma.py tests/test_storage.py
git commit -m "feat: ChromaStore에 증분 인덱싱용 조회 메서드 추가"
```

---

### Task 2: Git 증분 인덱싱

**Files:**
- Modify: `src/deview/ingestion/git.py`
- Modify: `src/deview/tools/ingest.py`
- Modify: `tests/test_tools.py`

- [ ] **Step 1: Write failing test for incremental git ingest**

`tests/test_tools.py`에 추가:

```python
@pytest.mark.asyncio
async def test_ingest_git_incremental(store: ChromaStore, embedding: FakeEmbedding, tmp_path: Path):
    """증분 인덱싱: 이미 인덱싱된 커밋 이후의 새 커밋만 인덱싱한다."""
    import git as gitmodule
    repo_path = tmp_path / "incr_repo"
    repo_path.mkdir()
    repo = gitmodule.Repo.init(repo_path)
    repo.config_writer().set_value("user", "name", "Test").release()
    repo.config_writer().set_value("user", "email", "t@t.com").release()

    # 첫 번째 커밋
    (repo_path / "a.py").write_text("x = 1\n")
    repo.index.add(["a.py"])
    repo.index.commit("first commit")

    # 전체 인덱싱
    result1 = await handle_ingest(
        path=str(repo_path), scope="test/incr", source_type="git",
        store=store, embedding=embedding, branch="master",
    )
    first_count = result1["chunks_indexed"]
    assert first_count >= 1

    # 두 번째 커밋 추가
    (repo_path / "b.py").write_text("y = 2\n")
    repo.index.add(["b.py"])
    repo.index.commit("second commit")

    # 증분 인덱싱
    result2 = await handle_ingest(
        path=str(repo_path), scope="test/incr", source_type="git",
        store=store, embedding=embedding, branch="master",
        incremental=True,
    )
    assert result2["chunks_indexed"] >= 1
    assert result2["chunks_indexed"] < first_count + 1  # 전체보다 적어야 함
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tools.py::test_ingest_git_incremental -v`
Expected: FAIL with TypeError (unexpected keyword argument 'incremental')

- [ ] **Step 3: Add since_commit parameter to parse_git_history**

`src/deview/ingestion/git.py`의 `parse_git_history` 함수에 `since_commit` 파라미터를 추가한다:

```python
def parse_git_history(
    repo_path: Path,
    branch: str = "main",
    scope: str = "",
    max_commits: int | None = None,
    since_commit: str | None = None,
) -> list[Chunk]:
    """git 히스토리를 파싱하여 청크 리스트를 반환한다.

    since_commit이 지정되면 해당 커밋 이후의 새 커밋만 파싱한다.
    """
    repo = git.Repo(repo_path)
    chunks: list[Chunk] = []

    # 지정된 브랜치가 없으면 현재 active branch로 폴백한다
    try:
        ref = branch
        repo.commit(ref)
    except git.BadName:
        ref = repo.active_branch.name
        logger.info("브랜치 '%s'를 찾을 수 없어 '%s'로 폴백", branch, ref)

    iter_kwargs: dict = {"rev": ref}
    if max_commits is not None:
        iter_kwargs["max_count"] = max_commits
    commits = list(repo.iter_commits(**iter_kwargs))

    # since_commit이 지정되면 해당 커밋까지 잘라낸다
    if since_commit:
        filtered = []
        for commit in commits:
            if commit.hexsha.startswith(since_commit):
                break
            filtered.append(commit)
        commits = filtered
        logger.info("증분 인덱싱: %s 이후 %d개 커밋 발견", since_commit, len(commits))

    for commit in commits:
        # ... (기존 커밋 파싱 로직 그대로 유지)
```

기존 for commit in commits: 이하 로직은 변경하지 않는다.

- [ ] **Step 4: Add incremental parameter to handle_ingest**

`src/deview/tools/ingest.py`의 `handle_ingest`에 `incremental` 파라미터를 추가한다:

```python
async def handle_ingest(
    path: str,
    scope: str,
    source_type: str = "auto",
    max_commits: int | None = None,
    store: ChromaStore | None = None,
    embedding: EmbeddingProvider | None = None,
    branch: str = "main",
    incremental: bool = False,
) -> dict:
    """Git 히스토리 또는 Markdown 문서를 인덱싱한다."""
    if store is None:
        raise ValueError("store가 초기화되지 않았습니다")
    if embedding is None:
        raise ValueError("embedding provider가 초기화되지 않았습니다")

    target = Path(path)
    resolved_type = source_type

    if source_type == "auto":
        if (target / ".git").exists():
            resolved_type = "git"
        else:
            resolved_type = "markdown"

    since_commit: str | None = None
    if incremental and resolved_type == "git":
        since_commit = store.get_latest_commit_hash(scope)

    if resolved_type == "git":
        chunks = parse_git_history(
            target, branch=branch, scope=scope,
            max_commits=max_commits, since_commit=since_commit,
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_tools.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add src/deview/ingestion/git.py src/deview/tools/ingest.py tests/test_tools.py
git commit -m "feat: Git 증분 인덱싱 지원 (since_commit)"
```

---

### Task 3: 설정에 integrations 섹션 추가

**Files:**
- Modify: `src/deview/config.py`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Write failing test for integrations config**

`tests/test_config.py`에 추가:

```python
def test_load_integrations_from_global(tmp_path: Path):
    """글로벌 설정에서 integrations를 로드한다."""
    global_yaml = tmp_path / "global.yaml"
    global_yaml.write_text(
        "integrations:\n"
        "  jira:\n"
        "    url: 'https://team.atlassian.net'\n"
        "    email: 'user@team.com'\n"
        "    api_token: 'jira-token-123'\n"
        "  confluence:\n"
        "    url: 'https://team.atlassian.net/wiki'\n"
        "    email: 'user@team.com'\n"
        "    api_token: 'conf-token-456'\n"
    )
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    config = load_config(project_dir, global_config_path=global_yaml)
    assert config.integrations.jira.url == "https://team.atlassian.net"
    assert config.integrations.jira.email == "user@team.com"
    assert config.integrations.jira.api_token == "jira-token-123"
    assert config.integrations.confluence.url == "https://team.atlassian.net/wiki"
    assert config.integrations.confluence.api_token == "conf-token-456"


def test_load_integrations_empty(tmp_path: Path):
    """integrations가 없으면 기본값(빈 설정)을 사용한다."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    config = load_config(project_dir, global_config_path=tmp_path / "nonexistent.yaml")
    assert config.integrations.jira.url == ""
    assert config.integrations.confluence.url == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_config.py::test_load_integrations_from_global tests/test_config.py::test_load_integrations_empty -v`
Expected: FAIL with AttributeError

- [ ] **Step 3: Add integration dataclasses and parsing to config.py**

`src/deview/config.py`에 추가:

```python
@dataclass
class JiraConfig:
    url: str = ""
    email: str = ""
    api_token: str = ""


@dataclass
class ConfluenceConfig:
    url: str = ""
    email: str = ""
    api_token: str = ""


@dataclass
class IntegrationsConfig:
    jira: JiraConfig = field(default_factory=JiraConfig)
    confluence: ConfluenceConfig = field(default_factory=ConfluenceConfig)
```

`DeviewConfig`에 필드 추가:

```python
@dataclass
class DeviewConfig:
    scope: str | None = None
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    ingestion: IngestionConfig = field(default_factory=IngestionConfig)
    integrations: IntegrationsConfig = field(default_factory=IntegrationsConfig)
```

`load_config` 함수에 integrations 파싱 추가:

```python
    # 인테그레이션: 글로벌 설정만
    integrations_raw = global_raw.get("integrations", {})
    jira_raw = integrations_raw.get("jira", {})
    confluence_raw = integrations_raw.get("confluence", {})

    integrations = IntegrationsConfig(
        jira=JiraConfig(
            url=jira_raw.get("url", ""),
            email=jira_raw.get("email", ""),
            api_token=_substitute_env_vars(jira_raw.get("api_token", "")),
        ),
        confluence=ConfluenceConfig(
            url=confluence_raw.get("url", ""),
            email=confluence_raw.get("email", ""),
            api_token=_substitute_env_vars(confluence_raw.get("api_token", "")),
        ),
    )

    return DeviewConfig(
        scope=project_raw.get("scope"),
        embedding=embedding,
        ingestion=ingestion,
        integrations=integrations,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_config.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/deview/config.py tests/test_config.py
git commit -m "feat: 설정에 Jira/Confluence integrations 섹션 추가"
```

---

### Task 4: Jira 커넥터

**Files:**
- Create: `src/deview/ingestion/jira.py`
- Create: `tests/test_ingestion_jira.py`

- [ ] **Step 1: Write failing test for Jira parsing**

```python
# tests/test_ingestion_jira.py

import pytest
from deview.ingestion.jira import parse_jira_issues
from deview.ingestion import Chunk


def _make_issue(key: str, summary: str, description: str, assignee: str, updated: str, comments: list[dict]) -> dict:
    """Jira API 응답 형태의 이슈 dict를 만든다."""
    return {
        "key": key,
        "fields": {
            "summary": summary,
            "description": description,
            "assignee": {"displayName": assignee} if assignee else None,
            "updated": updated,
            "comment": {
                "comments": [
                    {
                        "author": {"displayName": c["author"]},
                        "created": c["created"],
                        "body": c["body"],
                    }
                    for c in comments
                ],
            },
        },
    }


def test_parse_jira_issues_basic():
    """Jira 이슈를 청크로 변환한다."""
    issues = [
        _make_issue(
            key="PROJ-123",
            summary="API 응답 포맷 통일",
            description="각 API 엔드포인트마다 응답 포맷이 달라서 통일합니다.",
            assignee="이영희",
            updated="2025-03-17T10:00:00.000+0900",
            comments=[
                {"author": "김철수", "created": "2025-03-15T09:00:00.000+0900", "body": "v2로 분리하는게 낫지 않을까요?"},
                {"author": "이영희", "created": "2025-03-16T14:00:00.000+0900", "body": "기존 API에 래퍼를 씌우는 방향으로 결정했습니다."},
            ],
        ),
    ]

    chunks = parse_jira_issues(issues, scope="team/proj")
    assert len(chunks) == 1
    chunk = chunks[0]
    assert "PROJ-123" in chunk.content
    assert "API 응답 포맷 통일" in chunk.content
    assert "v2로 분리하는게 낫지 않을까요?" in chunk.content
    assert "래퍼를 씌우는 방향으로 결정" in chunk.content
    assert chunk.metadata["source"] == "jira"
    assert chunk.metadata["scope"] == "team/proj"
    assert chunk.metadata["jira_key"] == "PROJ-123"
    assert chunk.metadata["author"] == "이영희"


def test_parse_jira_issues_no_comments():
    """댓글이 없는 이슈도 정상 변환된다."""
    issues = [
        _make_issue(
            key="PROJ-456",
            summary="버그 수정",
            description="로그인 실패 시 에러 메시지 미표시",
            assignee="박지민",
            updated="2025-04-01T10:00:00.000+0900",
            comments=[],
        ),
    ]

    chunks = parse_jira_issues(issues, scope="team/proj")
    assert len(chunks) == 1
    assert "PROJ-456" in chunks[0].content
    assert "댓글" not in chunks[0].content  # 댓글 섹션 없음


def test_parse_jira_issues_no_assignee():
    """담당자가 없는 이슈는 author가 unknown이다."""
    issues = [
        _make_issue(
            key="PROJ-789",
            summary="담당자 미지정 이슈",
            description="설명",
            assignee="",
            updated="2025-04-01T10:00:00.000+0900",
            comments=[],
        ),
    ]

    chunks = parse_jira_issues(issues, scope="team/proj")
    assert chunks[0].metadata["author"] == "unknown"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ingestion_jira.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Implement Jira parser**

```python
# src/deview/ingestion/jira.py

"""Jira 이슈 파싱 및 청크 생성."""
from __future__ import annotations

import json
import logging

from deview.ingestion import Chunk

logger = logging.getLogger(__name__)


def parse_jira_issues(issues: list[dict], scope: str = "") -> list[Chunk]:
    """Jira API 응답의 이슈 목록을 청크 리스트로 변환한다.

    각 이슈는 제목 + 설명 + 전체 댓글을 하나의 청크로 만든다.
    """
    chunks: list[Chunk] = []

    for issue in issues:
        key = issue["key"]
        fields = issue["fields"]
        summary = fields.get("summary", "")
        description = fields.get("description") or ""
        assignee_obj = fields.get("assignee")
        author = assignee_obj["displayName"] if assignee_obj and assignee_obj.get("displayName") else "unknown"
        updated = fields.get("updated", "")
        # "2025-03-17T10:00:00.000+0900" → "2025-03-17"
        timestamp = updated[:10] if updated else ""

        # content 조립
        parts = [f"[{key}] {summary}"]
        if description:
            parts.append(f"\n설명:\n{description}")

        comment_entries = fields.get("comment", {}).get("comments", [])
        if comment_entries:
            comment_lines = []
            for c in comment_entries:
                c_author = c.get("author", {}).get("displayName", "unknown")
                c_created = c.get("created", "")[:10]
                c_body = c.get("body", "")
                comment_lines.append(f"[{c_created} {c_author}] {c_body}")
            parts.append("\n댓글:\n" + "\n".join(comment_lines))

        content = "\n".join(parts)

        chunks.append(Chunk(
            content=content,
            metadata={
                "scope": scope,
                "source": "jira",
                "author": author,
                "jira_key": key,
                "file_paths": "[]",
                "timestamp": timestamp,
            },
        ))

    logger.info("Jira 이슈 파싱 완료: %d개 청크 생성", len(chunks))
    return chunks
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ingestion_jira.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/deview/ingestion/jira.py tests/test_ingestion_jira.py
git commit -m "feat: Jira 커넥터 — 이슈를 청크로 변환하는 파서 추가"
```

---

### Task 5: Confluence 커넥터

**Files:**
- Create: `src/deview/ingestion/confluence.py`
- Create: `tests/test_ingestion_confluence.py`

- [ ] **Step 1: Write failing test for Confluence parsing**

```python
# tests/test_ingestion_confluence.py

import pytest
from deview.ingestion.confluence import parse_confluence_pages
from deview.ingestion import Chunk


def _make_page(page_id: str, title: str, body: str, author: str, modified: str) -> dict:
    """Confluence API 응답 형태의 페이지 dict를 만든다."""
    return {
        "id": page_id,
        "title": title,
        "body": {"storage": {"value": body}},
        "version": {"by": {"displayName": author}, "when": modified},
    }


def test_parse_short_page():
    """짧은 문서는 하나의 청크로 만든다."""
    pages = [
        _make_page(
            page_id="12345",
            title="코딩 컨벤션",
            body="<p>변수명은 camelCase를 사용합니다.</p>",
            author="박지민",
            modified="2025-10-15T10:00:00.000Z",
        ),
    ]

    chunks = parse_confluence_pages(pages, scope="team/proj")
    assert len(chunks) == 1
    assert "코딩 컨벤션" in chunks[0].content
    assert "camelCase" in chunks[0].content
    assert chunks[0].metadata["source"] == "confluence"
    assert chunks[0].metadata["document_id"] == "confluence-12345"
    assert chunks[0].metadata["document_title"] == "코딩 컨벤션"
    assert chunks[0].metadata["author"] == "박지민"


def test_parse_long_page_split_by_headings():
    """긴 문서는 헤딩 기준으로 분할하고 document_id로 그루핑한다."""
    long_body = (
        "<h2>1. 개요</h2><p>이 문서는 API 설계 가이드입니다.</p>"
        "<h2>2. 인증</h2><p>" + "인증 관련 상세 내용입니다. " * 200 + "</p>"
        "<h2>3. 에러 핸들링</h2><p>" + "에러 핸들링 상세 내용입니다. " * 200 + "</p>"
    )
    pages = [
        _make_page(
            page_id="67890",
            title="API 설계 가이드",
            body=long_body,
            author="김철수",
            modified="2025-11-01T10:00:00.000Z",
        ),
    ]

    chunks = parse_confluence_pages(pages, scope="team/proj")
    assert len(chunks) >= 2  # 분할되었음
    # 모든 청크가 같은 document_id를 가짐
    doc_ids = {c.metadata["document_id"] for c in chunks}
    assert len(doc_ids) == 1
    assert "confluence-67890" in doc_ids
    # 분할된 청크에 section 메타데이터가 있음
    sections = [c.metadata.get("section", "") for c in chunks]
    assert any("개요" in s for s in sections)


def test_parse_page_html_stripped():
    """HTML 태그가 제거된 텍스트가 content에 들어간다."""
    pages = [
        _make_page(
            page_id="11111",
            title="테스트",
            body="<p>일반 텍스트</p><ul><li>항목 1</li><li>항목 2</li></ul>",
            author="테스터",
            modified="2025-12-01T10:00:00.000Z",
        ),
    ]

    chunks = parse_confluence_pages(pages, scope="team/proj")
    assert "<p>" not in chunks[0].content
    assert "일반 텍스트" in chunks[0].content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ingestion_confluence.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Implement Confluence parser**

```python
# src/deview/ingestion/confluence.py

"""Confluence 페이지 파싱 및 청크 생성."""
from __future__ import annotations

import json
import logging
import re
from html.parser import HTMLParser

from deview.ingestion import Chunk

logger = logging.getLogger(__name__)

_CHUNK_THRESHOLD = 2000  # 이 글자 수 이하면 분할하지 않음


class _HTMLTextExtractor(HTMLParser):
    """HTML에서 텍스트만 추출한다."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._current_heading: str = ""
        self._in_heading: bool = False
        self._heading_positions: list[tuple[str, int]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if re.match(r"h[1-3]", tag):
            self._in_heading = True
            self._current_heading = ""

    def handle_endtag(self, tag: str) -> None:
        if re.match(r"h[1-3]", tag) and self._in_heading:
            self._in_heading = False
            pos = len("".join(self._parts))
            self._heading_positions.append((self._current_heading.strip(), pos))

    def handle_data(self, data: str) -> None:
        self._parts.append(data)
        if self._in_heading:
            self._current_heading += data

    def get_text(self) -> str:
        return "".join(self._parts).strip()

    def get_heading_positions(self) -> list[tuple[str, int]]:
        return self._heading_positions


def _strip_html(html: str) -> tuple[str, list[tuple[str, int]]]:
    """HTML에서 텍스트와 헤딩 위치를 추출한다."""
    extractor = _HTMLTextExtractor()
    extractor.feed(html)
    return extractor.get_text(), extractor.get_heading_positions()


def _split_by_headings(text: str, heading_positions: list[tuple[str, int]]) -> list[tuple[str, str]]:
    """텍스트를 헤딩 위치 기준으로 (헤딩, 내용) 쌍으로 분할한다."""
    if not heading_positions:
        return [("", text)]

    sections: list[tuple[str, str]] = []
    for i, (heading, pos) in enumerate(heading_positions):
        end = heading_positions[i + 1][1] if i + 1 < len(heading_positions) else len(text)
        content = text[pos:end].strip()
        # 헤딩 텍스트 자체가 content 시작에 포함되어 있으므로 제거
        if content.startswith(heading):
            content = content[len(heading):].strip()
        if content:
            sections.append((heading, content))

    return sections


def parse_confluence_pages(pages: list[dict], scope: str = "") -> list[Chunk]:
    """Confluence API 응답의 페이지 목록을 청크 리스트로 변환한다.

    짧은 문서는 통째로, 긴 문서는 헤딩 기준으로 분할하되 document_id로 그루핑한다.
    """
    chunks: list[Chunk] = []

    for page in pages:
        page_id = page["id"]
        title = page.get("title", "")
        body_html = page.get("body", {}).get("storage", {}).get("value", "")
        version = page.get("version", {})
        author = version.get("by", {}).get("displayName", "unknown")
        modified = version.get("when", "")
        timestamp = modified[:10] if modified else ""
        document_id = f"confluence-{page_id}"

        text, heading_positions = _strip_html(body_html)

        if len(text) <= _CHUNK_THRESHOLD or not heading_positions:
            # 짧은 문서: 통째로 하나의 청크
            chunks.append(Chunk(
                content=f"{title}\n\n{text}" if text else title,
                metadata={
                    "scope": scope,
                    "source": "confluence",
                    "author": author,
                    "document_id": document_id,
                    "document_title": title,
                    "section": "",
                    "file_paths": "[]",
                    "timestamp": timestamp,
                },
            ))
        else:
            # 긴 문서: 헤딩 기준 분할 + document_id 그루핑
            sections = _split_by_headings(text, heading_positions)
            for heading, content in sections:
                chunks.append(Chunk(
                    content=f"{title} > {heading}\n\n{content}" if heading else f"{title}\n\n{content}",
                    metadata={
                        "scope": scope,
                        "source": "confluence",
                        "author": author,
                        "document_id": document_id,
                        "document_title": title,
                        "section": heading,
                        "file_paths": "[]",
                        "timestamp": timestamp,
                    },
                ))

    logger.info("Confluence 페이지 파싱 완료: %d개 청크 생성", len(chunks))
    return chunks
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ingestion_confluence.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/deview/ingestion/confluence.py tests/test_ingestion_confluence.py
git commit -m "feat: Confluence 커넥터 — 페이지를 청크로 변환하는 파서 추가"
```

---

### Task 6: 동기화 핸들러 (Jira/Confluence API 호출 + 증분)

**Files:**
- Create: `src/deview/tools/sync.py`
- Create: `tests/test_tools_sync.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Add atlassian-python-api dependency**

`pyproject.toml`의 `[project.optional-dependencies]`에 추가:

```toml
[project.optional-dependencies]
local = [
    "sentence-transformers",
    "torch",
]
mistral = [
    "mistralai",
]
connectors = [
    "atlassian-python-api",
]
```

Run: `uv sync --extra connectors`

- [ ] **Step 2: Write failing test for sync handler**

```python
# tests/test_tools_sync.py

import pytest
from unittest.mock import MagicMock, patch
from deview.tools.sync import handle_sync
from deview.storage.chroma import ChromaStore
from deview.embedding.base import EmbeddingProvider


class FakeEmbedding(EmbeddingProvider):
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]

    def dimension(self) -> int:
        return 3


@pytest.fixture
def store(tmp_path):
    return ChromaStore(persist_dir=str(tmp_path / "chroma"))


@pytest.fixture
def embedding():
    return FakeEmbedding()


@pytest.mark.asyncio
async def test_sync_jira(store: ChromaStore, embedding: FakeEmbedding):
    """Jira 동기화로 이슈를 인덱싱한다."""
    mock_jira = MagicMock()
    mock_jira.jql.return_value = {
        "issues": [
            {
                "key": "PROJ-1",
                "fields": {
                    "summary": "테스트 이슈",
                    "description": "설명입니다",
                    "assignee": {"displayName": "김철수"},
                    "updated": "2025-03-17T10:00:00.000+0900",
                    "comment": {"comments": []},
                },
            },
        ],
    }

    with patch("deview.tools.sync._create_jira_client", return_value=mock_jira):
        result = await handle_sync(
            source="jira",
            scope="team/proj",
            store=store,
            embedding=embedding,
            jira_url="https://team.atlassian.net",
            jira_email="user@team.com",
            jira_token="token",
            jira_project="PROJ",
        )

    assert result["source"] == "jira"
    assert result["chunks_indexed"] == 1


@pytest.mark.asyncio
async def test_sync_confluence(store: ChromaStore, embedding: FakeEmbedding):
    """Confluence 동기화로 페이지를 인덱싱한다."""
    mock_confluence = MagicMock()
    mock_confluence.get_all_pages_from_space.return_value = [
        {
            "id": "12345",
            "title": "가이드",
            "body": {"storage": {"value": "<p>내용입니다</p>"}},
            "version": {"by": {"displayName": "박지민"}, "when": "2025-10-15T10:00:00.000Z"},
        },
    ]

    with patch("deview.tools.sync._create_confluence_client", return_value=mock_confluence):
        result = await handle_sync(
            source="confluence",
            scope="team/proj",
            store=store,
            embedding=embedding,
            confluence_url="https://team.atlassian.net/wiki",
            confluence_email="user@team.com",
            confluence_token="token",
            confluence_space="DEV",
        )

    assert result["source"] == "confluence"
    assert result["chunks_indexed"] == 1


@pytest.mark.asyncio
async def test_sync_jira_incremental(store: ChromaStore, embedding: FakeEmbedding):
    """증분 동기화: 기존 데이터의 최신 timestamp 이후만 가져온다."""
    # 기존 데이터 삽입
    store.add(
        ids=["jira-existing"],
        embeddings=[[0.1, 0.2, 0.3]],
        contents=["기존 이슈"],
        metadatas=[{"scope": "team/proj", "source": "jira", "timestamp": "2025-03-01"}],
    )

    mock_jira = MagicMock()
    mock_jira.jql.return_value = {"issues": []}

    with patch("deview.tools.sync._create_jira_client", return_value=mock_jira):
        result = await handle_sync(
            source="jira",
            scope="team/proj",
            store=store,
            embedding=embedding,
            jira_url="https://team.atlassian.net",
            jira_email="user@team.com",
            jira_token="token",
            jira_project="PROJ",
        )

    # jql 호출 시 updated >= "2025-03-01" 조건이 포함되었는지 확인
    jql_call = mock_jira.jql.call_args[0][0]
    assert "2025-03-01" in jql_call
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_tools_sync.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 4: Implement sync handler**

```python
# src/deview/tools/sync.py

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

    # 증분: 기존 데이터의 최신 timestamp 이후만 가져옴
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

    # jira_key 기반 ID로 upsert (같은 이슈는 덮어씀)
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

    # 증분: 기존 데이터의 최신 timestamp 이후에 수정된 페이지만
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

    # document_id 기반 ID로 upsert
    ids = []
    for c in chunks:
        section = c.metadata.get("section", "")
        base_id = c.metadata["document_id"]
        if section:
            # 섹션별 고유 ID
            ids.append(f"{base_id}-{hash(section) % 100000:05d}")
        else:
            ids.append(base_id)

    contents = [c.content for c in chunks]
    metadatas = [c.metadata for c in chunks]
    vectors = embedding.embed(contents)
    store.add(ids=ids, embeddings=vectors, contents=contents, metadatas=metadatas)

    return {"source": "confluence", "scope": scope, "chunks_indexed": len(chunks)}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_tools_sync.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add src/deview/tools/sync.py tests/test_tools_sync.py pyproject.toml
git commit -m "feat: Jira/Confluence 동기화 핸들러 (증분 지원)"
```

---

### Task 7: MCP 도구에 deview_sync 추가

**Files:**
- Modify: `src/deview/server.py`
- Modify: `src/deview/config.py` (IntegrationsConfig export 확인)

- [ ] **Step 1: Add deview_sync tool to server.py**

`src/deview/server.py`에 추가:

```python
from deview.tools.sync import handle_sync
```

`_ensure_initialized` 반환 타입을 확장하여 config 자체를 반환하도록 수정:

```python
_config: DeviewConfig | None = None

def _ensure_initialized() -> tuple[ChromaStore, EmbeddingProvider, str, str, str, DeviewConfig]:
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
```

기존 4개 도구의 `_ensure_initialized()` 호출부도 언패킹 수정:

```python
@mcp.tool()
async def deview_search(...) -> dict:
    store, embedding, default_scope, _, _, _ = _ensure_initialized()
    # ...

@mcp.tool()
async def deview_write(...) -> dict:
    store, embedding, default_scope, _, _, _ = _ensure_initialized()
    # ...

@mcp.tool()
async def deview_ingest(...) -> dict:
    store, embedding, default_scope, _, branch, _ = _ensure_initialized()
    # ...

@mcp.tool()
async def deview_status(...) -> dict:
    store, _, default_scope, provider_name, _, _ = _ensure_initialized()
    # ...
```

새 도구 추가:

```python
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
```

- [ ] **Step 2: Run all existing tests to verify nothing broke**

Run: `uv run pytest -v`
Expected: ALL PASS (기존 테스트가 깨지지 않음)

- [ ] **Step 3: Commit**

```bash
git add src/deview/server.py
git commit -m "feat: deview_sync MCP 도구 추가 (Jira/Confluence 동기화)"
```

---

### Task 8: CLI 기본 구조 + ingest/status/search 명령어

**Files:**
- Create: `src/deview/cli.py`
- Create: `tests/test_cli.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Add typer dependency and script entry point**

`pyproject.toml`에 추가:

```toml
dependencies = [
    "mcp[cli]",
    "chromadb",
    "voyageai",
    "openai",
    "gitpython",
    "pyyaml",
    "typer",
]

[project.scripts]
deview = "deview.cli:app"
```

Run: `uv sync`

- [ ] **Step 2: Write failing test for CLI**

```python
# tests/test_cli.py

import pytest
from typer.testing import CliRunner
from deview.cli import app

runner = CliRunner()


def test_cli_status_help():
    """status 명령어의 --help가 동작한다."""
    result = runner.invoke(app, ["status", "--help"])
    assert result.exit_code == 0
    assert "상태" in result.stdout or "status" in result.stdout.lower()


def test_cli_search_help():
    """search 명령어의 --help가 동작한다."""
    result = runner.invoke(app, ["search", "--help"])
    assert result.exit_code == 0


def test_cli_ingest_help():
    """ingest 명령어의 --help가 동작한다."""
    result = runner.invoke(app, ["ingest", "--help"])
    assert result.exit_code == 0


def test_cli_sync_help():
    """sync 명령어의 --help가 동작한다."""
    result = runner.invoke(app, ["sync", "--help"])
    assert result.exit_code == 0
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 4: Implement CLI**

```python
# src/deview/cli.py

"""Deview CLI 도구."""
from __future__ import annotations

import asyncio
import json
import os
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
    jira_cfg = config.integrations.jira
    conf_cfg = config.integrations.confluence

    result = asyncio.run(handle_sync(
        source=source,
        scope=scope or default_scope,
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
    ))
    typer.echo(f"동기화 완료: {result['chunks_indexed']}개 청크 ({result['source']})")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add src/deview/cli.py tests/test_cli.py pyproject.toml
git commit -m "feat: typer 기반 CLI 도구 (status, search, ingest, sync)"
```

---

### Task 9: Git Hook 설치/제거

**Files:**
- Modify: `src/deview/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing test for hook commands**

`tests/test_cli.py`에 추가:

```python
def test_cli_hook_install(tmp_path: Path):
    """hook install이 post-merge 스크립트를 생성한다."""
    import git
    repo_path = tmp_path / "hook_repo"
    repo_path.mkdir()
    git.Repo.init(repo_path)

    result = runner.invoke(app, ["hook", "install"], env={"DEVIEW_PROJECT_PATH": str(repo_path)})
    assert result.exit_code == 0

    hook_path = repo_path / ".git" / "hooks" / "post-merge"
    assert hook_path.exists()
    content = hook_path.read_text()
    assert "deview ingest" in content


def test_cli_hook_uninstall(tmp_path: Path):
    """hook uninstall이 post-merge 스크립트를 제거한다."""
    import git
    repo_path = tmp_path / "hook_repo"
    repo_path.mkdir()
    git.Repo.init(repo_path)

    # 먼저 설치
    runner.invoke(app, ["hook", "install"], env={"DEVIEW_PROJECT_PATH": str(repo_path)})

    # 제거
    result = runner.invoke(app, ["hook", "uninstall"], env={"DEVIEW_PROJECT_PATH": str(repo_path)})
    assert result.exit_code == 0

    hook_path = repo_path / ".git" / "hooks" / "post-merge"
    assert not hook_path.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli.py::test_cli_hook_install tests/test_cli.py::test_cli_hook_uninstall -v`
Expected: FAIL

- [ ] **Step 3: Add hook subcommand to CLI**

`src/deview/cli.py`에 추가:

```python
import stat

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
```

`import stat`을 파일 상단 import 섹션에 추가.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/deview/cli.py tests/test_cli.py
git commit -m "feat: Git post-merge hook 설치/제거 CLI 명령어"
```

---

### Task 10: MCP deview_ingest에 incremental 파라미터 추가 + Docker 재빌드

**Files:**
- Modify: `src/deview/server.py`

- [ ] **Step 1: Update deview_ingest MCP tool**

`src/deview/server.py`의 `deview_ingest` 도구에 `incremental` 파라미터를 추가:

```python
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
```

- [ ] **Step 2: Run all tests**

Run: `uv run pytest -v`
Expected: ALL PASS

- [ ] **Step 3: Rebuild Docker image**

Run: `docker build -t deview:latest .`

- [ ] **Step 4: Commit**

```bash
git add src/deview/server.py
git commit -m "feat: deview_ingest MCP 도구에 incremental 파라미터 추가"
```

---

### Task 11: config.yaml.example 및 설계 문서 업데이트

**Files:**
- Modify: `config.yaml.example`
- Modify: `docs/phase-2-git-hook-rest-api/design.md` (필요 시)

- [ ] **Step 1: Update config.yaml.example with integrations section**

```yaml
# ~/.deview/config.yaml — Deview 글로벌 설정 예시

embedding:
  provider: "voyage"
  providers:
    voyage:
      model: "voyage-3.5-lite"
      api_key: "pa-..."
    openai:
      model: "text-embedding-3-small"
      api_key: "${OPENAI_API_KEY}"

integrations:
  jira:
    url: "https://team.atlassian.net"
    email: "user@team.com"
    api_token: "${JIRA_API_TOKEN}"
  confluence:
    url: "https://team.atlassian.net/wiki"
    email: "user@team.com"
    api_token: "${CONFLUENCE_API_TOKEN}"
```

- [ ] **Step 2: Commit**

```bash
git add config.yaml.example
git commit -m "docs: config.yaml.example에 integrations 섹션 추가"
```

---

### Task 12: 전체 통합 테스트

**Files:**
- Modify: `tests/test_integration.py`

- [ ] **Step 1: Write integration test covering end-to-end flow**

```python
# tests/test_integration.py 에 추가

@pytest.mark.asyncio
async def test_incremental_ingest_only_adds_new_commits(tmp_path: Path):
    """증분 인덱싱이 기존 커밋을 건너뛰고 새 커밋만 추가하는지 검증한다."""
    import git as gitmodule

    store = ChromaStore(persist_dir=str(tmp_path / "chroma"))
    embedding = FakeEmbedding()

    # git repo 생성 + 커밋 2개
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    repo = gitmodule.Repo.init(repo_path)
    repo.config_writer().set_value("user", "name", "Test").release()
    repo.config_writer().set_value("user", "email", "t@t.com").release()

    (repo_path / "a.py").write_text("x = 1\n")
    repo.index.add(["a.py"])
    repo.index.commit("commit 1")

    (repo_path / "b.py").write_text("y = 2\n")
    repo.index.add(["b.py"])
    repo.index.commit("commit 2")

    # 전체 인덱싱
    result1 = await handle_ingest(
        path=str(repo_path), scope="test/e2e", source_type="git",
        store=store, embedding=embedding, branch="master",
    )
    total_first = result1["chunks_indexed"]

    # 커밋 1개 추가
    (repo_path / "c.py").write_text("z = 3\n")
    repo.index.add(["c.py"])
    repo.index.commit("commit 3")

    # 증분 인덱싱
    result2 = await handle_ingest(
        path=str(repo_path), scope="test/e2e", source_type="git",
        store=store, embedding=embedding, branch="master",
        incremental=True,
    )
    incremental_count = result2["chunks_indexed"]

    # 증분은 새 커밋 1개만 (+ 가능한 주석 청크)
    assert incremental_count >= 1
    assert incremental_count < total_first

    # 전체 검색하면 모든 커밋의 데이터가 있음
    from deview.tools.status import handle_status
    status = await handle_status(scope="test/e2e", store=store)
    assert status["total_chunks"] == total_first + incremental_count
```

- [ ] **Step 2: Run the full test suite**

Run: `uv run pytest -v`
Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: 증분 인덱싱 통합 테스트 추가"
```

---

## Self-Review

**1. Spec coverage:**
- [x] 증분 인덱싱 공통 패턴 (Task 1, 2) — DB 기반 since_commit/latest_timestamp
- [x] Git 증분 인덱싱 (Task 2)
- [x] Jira 증분 동기화 (Task 4, 6)
- [x] Confluence 증분 동기화 (Task 5, 6)
- [x] Jira 청크: 제목+설명+전체 댓글 (Task 4)
- [x] Confluence 청크: 짧으면 통째로, 길면 헤딩 분할+그루핑 (Task 5)
- [x] 설정 integrations 섹션 (Task 3)
- [x] CLI: status, search, ingest, sync (Task 8)
- [x] Git Hook install/uninstall (Task 9)
- [x] MCP deview_sync 도구 (Task 7)
- [x] MCP deview_ingest incremental 파라미터 (Task 10)
- [x] config.yaml.example 업데이트 (Task 11)

**2. Placeholder scan:** No TBD, TODO, or vague steps found.

**3. Type consistency:** `handle_ingest`의 `incremental` 파라미터가 Task 2(구현), Task 8(CLI), Task 10(MCP), Task 12(테스트)에서 일관됨. `handle_sync`의 시그니처가 Task 6(구현), Task 7(MCP), Task 8(CLI)에서 일관됨.
