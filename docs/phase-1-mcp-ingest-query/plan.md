# Phase 1: MCP Ingest & Query 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deview MCP 서버를 구현하여 LLM 클라이언트에서 프로젝트 맥락을 저장/검색할 수 있도록 한다.

**Architecture:** Python MCP 서버(FastMCP)가 ChromaDB에 벡터화된 맥락을 저장하고, MCP 도구를 통해 검색 결과를 반환한다. 임베딩은 추상 인터페이스를 통해 Voyage/OpenAI/Mistral/로컬 모델을 교체 가능하게 지원한다.

**Tech Stack:** Python 3.10+, uv, FastMCP (mcp SDK), ChromaDB, VoyageAI, GitPython, PyYAML, pytest

---

## File Structure

| 파일 | 역할 |
|:---|:---|
| `pyproject.toml` | 프로젝트 설정 및 의존성 |
| `src/deview/__init__.py` | 패키지 초기화 |
| `src/deview/config.py` | `.deview.yaml` + 환경변수 로드, 설정 모델 |
| `src/deview/scope.py` | Scope 추론 (git remote URL / yaml / 디렉토리명) |
| `src/deview/embedding/base.py` | 임베딩 추상 인터페이스 |
| `src/deview/embedding/voyage.py` | Voyage API 구현 |
| `src/deview/embedding/openai.py` | OpenAI API 구현 |
| `src/deview/embedding/local.py` | BGE-large 로컬 구현 |
| `src/deview/embedding/__init__.py` | 팩토리 함수 (provider 이름 → 구현체) |
| `src/deview/storage/chroma.py` | ChromaDB CRUD 래퍼 |
| `src/deview/storage/__init__.py` | 패키지 초기화 |
| `src/deview/ingestion/git.py` | Git 히스토리 파싱 + 주석 변경 추출 |
| `src/deview/ingestion/markdown.py` | Markdown 헤딩 기준 분할 |
| `src/deview/ingestion/manual.py` | 수동 메모 저장 |
| `src/deview/ingestion/__init__.py` | 패키지 초기화 |
| `src/deview/tools/search.py` | deview_search MCP 도구 |
| `src/deview/tools/write.py` | deview_write MCP 도구 |
| `src/deview/tools/ingest.py` | deview_ingest MCP 도구 |
| `src/deview/tools/status.py` | deview_status MCP 도구 |
| `src/deview/tools/__init__.py` | 도구 등록 |
| `src/deview/server.py` | MCP 서버 진입점 |
| `tests/test_config.py` | config 테스트 |
| `tests/test_scope.py` | scope 테스트 |
| `tests/test_embedding.py` | 임베딩 추상화 테스트 |
| `tests/test_storage.py` | ChromaDB 래퍼 테스트 |
| `tests/test_ingestion_git.py` | Git 파서 테스트 |
| `tests/test_ingestion_markdown.py` | Markdown 파서 테스트 |
| `tests/test_tools.py` | MCP 도구 통합 테스트 |
| `docs/guides/local-embedding-setup.md` | 로컬 임베딩 설치 가이드 |
| `.deview.yaml.example` | 설정 파일 예시 |

---

### Task 1: 프로젝트 스캐폴딩

**Files:**
- Create: `pyproject.toml`
- Create: `src/deview/__init__.py`

- [ ] **Step 1: uv 프로젝트 초기화**

```bash
cd /Users/bran/personal/Deview
uv init --lib --name deview
```

- [ ] **Step 2: pyproject.toml 작성**

```toml
[project]
name = "deview"
version = "0.1.0"
description = "Digital Psychometry for Developers — Context-aware developer assistant"
requires-python = ">=3.10"
dependencies = [
    "mcp[cli]",
    "chromadb",
    "voyageai",
    "openai",
    "gitpython",
    "pyyaml",
]

[project.optional-dependencies]
local = [
    "sentence-transformers",
    "torch",
]
mistral = [
    "mistralai",
]

[tool.uv]
dev-dependencies = [
    "pytest",
    "pytest-asyncio",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

- [ ] **Step 3: 의존성 설치**

```bash
uv sync
```

Expected: `.venv` 생성, 의존성 설치 완료

- [ ] **Step 4: __init__.py 작성**

`src/deview/__init__.py`:
```python
"""Deview: Digital Psychometry for Developers."""

__version__ = "0.1.0"
```

- [ ] **Step 5: 확인 및 커밋**

```bash
uv run python -c "import deview; print(deview.__version__)"
```

Expected: `0.1.0`

```bash
git init
echo -e "__pycache__/\n*.pyc\n.venv/\n*.egg-info/\n.deview.yaml\n~/.deview/" > .gitignore
git add pyproject.toml src/deview/__init__.py .gitignore uv.lock docs/
git commit -m "chore: init deview project with uv"
```

---

### Task 2: 설정 모듈 (config.py)

**Files:**
- Create: `src/deview/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: config 테스트 작성**

`tests/test_config.py`:
```python
import os
from pathlib import Path
from deview.config import DeviewConfig, load_config


def test_default_config():
    """설정 파일 없이 기본값으로 동작한다."""
    config = DeviewConfig()
    assert config.embedding.provider == "voyage"
    assert config.ingestion.git.target_branch == "main"
    assert config.ingestion.git.max_commits is None


def test_load_from_yaml(tmp_path: Path):
    """yaml 파일에서 설정을 읽는다."""
    yaml_content = """
scope: "my-project"
embedding:
  provider: "openai"
  providers:
    openai:
      model: "text-embedding-3-small"
      api_key: "sk-test-key"
ingestion:
  git:
    target_branch: "develop"
    max_commits: 500
"""
    yaml_file = tmp_path / ".deview.yaml"
    yaml_file.write_text(yaml_content)

    config = load_config(tmp_path)
    assert config.scope == "my-project"
    assert config.embedding.provider == "openai"
    assert config.embedding.providers["openai"].model == "text-embedding-3-small"
    assert config.embedding.providers["openai"].api_key == "sk-test-key"
    assert config.ingestion.git.target_branch == "develop"
    assert config.ingestion.git.max_commits == 500


def test_env_var_substitution(tmp_path: Path, monkeypatch):
    """yaml에서 ${ENV_VAR} 형식의 환경변수를 치환한다."""
    monkeypatch.setenv("VOYAGE_API_KEY", "voy-test-key-123")
    yaml_content = """
embedding:
  provider: "voyage"
  providers:
    voyage:
      api_key: "${VOYAGE_API_KEY}"
"""
    yaml_file = tmp_path / ".deview.yaml"
    yaml_file.write_text(yaml_content)

    config = load_config(tmp_path)
    assert config.embedding.providers["voyage"].api_key == "voy-test-key-123"


def test_missing_yaml_returns_defaults(tmp_path: Path):
    """yaml 파일이 없으면 기본값을 반환한다."""
    config = load_config(tmp_path)
    assert config.scope is None
    assert config.embedding.provider == "voyage"
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
uv run pytest tests/test_config.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'deview.config'`

- [ ] **Step 3: config.py 구현**

`src/deview/config.py`:
```python
"""설정 로드: .deview.yaml + 환경변수."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class ProviderConfig:
    model: str = ""
    api_key: str = ""


@dataclass
class EmbeddingConfig:
    provider: str = "voyage"
    providers: dict[str, ProviderConfig] = field(default_factory=dict)


@dataclass
class GitIngestionConfig:
    target_branch: str = "main"
    max_commits: int | None = None


@dataclass
class IngestionConfig:
    git: GitIngestionConfig = field(default_factory=GitIngestionConfig)


@dataclass
class DeviewConfig:
    scope: str | None = None
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    ingestion: IngestionConfig = field(default_factory=IngestionConfig)


_ENV_VAR_PATTERN = re.compile(r"\$\{(\w+)\}")


def _substitute_env_vars(value: str) -> str:
    """${ENV_VAR} 패턴을 환경변수 값으로 치환한다."""
    def replacer(match: re.Match) -> str:
        env_name = match.group(1)
        return os.environ.get(env_name, match.group(0))
    return _ENV_VAR_PATTERN.sub(replacer, value)


def _parse_providers(raw: dict) -> dict[str, ProviderConfig]:
    providers: dict[str, ProviderConfig] = {}
    for name, settings in raw.items():
        if not isinstance(settings, dict):
            continue
        api_key = settings.get("api_key", "")
        if isinstance(api_key, str):
            api_key = _substitute_env_vars(api_key)
        providers[name] = ProviderConfig(
            model=settings.get("model", ""),
            api_key=api_key,
        )
    return providers


def load_config(project_path: Path) -> DeviewConfig:
    """프로젝트 경로에서 .deview.yaml을 읽어 DeviewConfig를 반환한다."""
    yaml_path = project_path / ".deview.yaml"
    if not yaml_path.exists():
        return DeviewConfig()

    with open(yaml_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    embedding_raw = raw.get("embedding", {})
    providers_raw = embedding_raw.get("providers", {})
    embedding = EmbeddingConfig(
        provider=embedding_raw.get("provider", "voyage"),
        providers=_parse_providers(providers_raw),
    )

    git_raw = raw.get("ingestion", {}).get("git", {})
    ingestion = IngestionConfig(
        git=GitIngestionConfig(
            target_branch=git_raw.get("target_branch", "main"),
            max_commits=git_raw.get("max_commits"),
        ),
    )

    return DeviewConfig(
        scope=raw.get("scope"),
        embedding=embedding,
        ingestion=ingestion,
    )
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
uv run pytest tests/test_config.py -v
```

Expected: 4 passed

- [ ] **Step 5: 커밋**

```bash
git add src/deview/config.py tests/test_config.py
git commit -m "feat: add config module with yaml loading and env var substitution"
```

---

### Task 3: Scope 추론 (scope.py)

**Files:**
- Create: `src/deview/scope.py`
- Create: `tests/test_scope.py`

- [ ] **Step 1: scope 테스트 작성**

`tests/test_scope.py`:
```python
from pathlib import Path
from deview.scope import resolve_scope


def test_scope_from_yaml_override():
    """yaml에 scope가 명시되면 그것을 사용한다."""
    result = resolve_scope(
        yaml_scope="my-project",
        project_path=Path("/some/path"),
    )
    assert result == "my-project"


def test_scope_from_ssh_remote(tmp_path: Path):
    """git SSH remote URL에서 scope를 추론한다."""
    _init_git_repo(tmp_path, "git@github.com:team/my-project.git")
    result = resolve_scope(yaml_scope=None, project_path=tmp_path)
    assert result == "team/my-project"


def test_scope_from_https_remote(tmp_path: Path):
    """git HTTPS remote URL에서 scope를 추론한다."""
    _init_git_repo(tmp_path, "https://github.com/team/my-project.git")
    result = resolve_scope(yaml_scope=None, project_path=tmp_path)
    assert result == "team/my-project"


def test_scope_fallback_to_dirname(tmp_path: Path):
    """git이 아닌 경우 디렉토리명으로 fallback한다."""
    result = resolve_scope(yaml_scope=None, project_path=tmp_path)
    assert result == tmp_path.name


def _init_git_repo(path: Path, remote_url: str) -> None:
    """테스트용 git 저장소를 초기화하고 remote를 설정한다."""
    import git
    repo = git.Repo.init(path)
    repo.create_remote("origin", remote_url)
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
uv run pytest tests/test_scope.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'deview.scope'`

- [ ] **Step 3: scope.py 구현**

`src/deview/scope.py`:
```python
"""Scope 추론: yaml > git remote URL > 디렉토리명."""

from __future__ import annotations

import re
from pathlib import Path

import git


_SSH_PATTERN = re.compile(r"git@[^:]+:(.+?)(?:\.git)?$")
_HTTPS_PATTERN = re.compile(r"https?://[^/]+/(.+?)(?:\.git)?$")


def _parse_remote_url(url: str) -> str | None:
    """git remote URL에서 'owner/repo' 형태의 scope를 추출한다."""
    for pattern in (_SSH_PATTERN, _HTTPS_PATTERN):
        match = pattern.match(url)
        if match:
            return match.group(1)
    return None


def _get_git_remote_scope(project_path: Path) -> str | None:
    """프로젝트의 git remote origin URL에서 scope를 추론한다."""
    try:
        repo = git.Repo(project_path, search_parent_directories=True)
        if "origin" not in [r.name for r in repo.remotes]:
            return None
        url = repo.remotes.origin.url
        return _parse_remote_url(url)
    except (git.InvalidGitRepositoryError, git.GitCommandNotFound):
        return None


def resolve_scope(
    yaml_scope: str | None,
    project_path: Path,
) -> str:
    """Scope를 결정한다. 우선순위: yaml > git remote > 디렉토리명."""
    if yaml_scope:
        return yaml_scope

    git_scope = _get_git_remote_scope(project_path)
    if git_scope:
        return git_scope

    return project_path.name
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
uv run pytest tests/test_scope.py -v
```

Expected: 4 passed

- [ ] **Step 5: 커밋**

```bash
git add src/deview/scope.py tests/test_scope.py
git commit -m "feat: add scope resolution from yaml, git remote, dirname"
```

---

### Task 4: 임베딩 추상화

**Files:**
- Create: `src/deview/embedding/__init__.py`
- Create: `src/deview/embedding/base.py`
- Create: `src/deview/embedding/voyage.py`
- Create: `src/deview/embedding/openai.py`
- Create: `src/deview/embedding/local.py`
- Create: `tests/test_embedding.py`

- [ ] **Step 1: 임베딩 테스트 작성**

`tests/test_embedding.py`:
```python
from deview.embedding.base import EmbeddingProvider
from deview.embedding import create_provider
from deview.config import ProviderConfig


def test_base_interface():
    """EmbeddingProvider는 embed()와 dimension()을 요구한다."""
    assert hasattr(EmbeddingProvider, "embed")
    assert hasattr(EmbeddingProvider, "dimension")


def test_create_provider_voyage():
    """voyage provider를 생성할 수 있다."""
    provider = create_provider("voyage", ProviderConfig(
        model="voyage-3.5-lite",
        api_key="test-key",
    ))
    assert isinstance(provider, EmbeddingProvider)
    assert provider.dimension() == 1024


def test_create_provider_openai():
    """openai provider를 생성할 수 있다."""
    provider = create_provider("openai", ProviderConfig(
        model="text-embedding-3-small",
        api_key="test-key",
    ))
    assert isinstance(provider, EmbeddingProvider)
    assert provider.dimension() == 1536


def test_create_provider_unknown():
    """알 수 없는 provider는 ValueError를 발생시킨다."""
    import pytest
    with pytest.raises(ValueError, match="Unknown embedding provider"):
        create_provider("unknown", ProviderConfig())
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
uv run pytest tests/test_embedding.py -v
```

Expected: FAIL

- [ ] **Step 3: base.py 구현**

`src/deview/embedding/base.py`:
```python
"""임베딩 프로바이더 추상 인터페이스."""

from __future__ import annotations

from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """텍스트 리스트를 벡터 리스트로 변환한다."""
        ...

    @abstractmethod
    def dimension(self) -> int:
        """벡터 차원 수를 반환한다."""
        ...
```

- [ ] **Step 4: voyage.py 구현**

`src/deview/embedding/voyage.py`:
```python
"""Voyage AI 임베딩 프로바이더."""

from __future__ import annotations

import voyageai

from deview.embedding.base import EmbeddingProvider

_MODEL_DIMENSIONS: dict[str, int] = {
    "voyage-3.5-lite": 1024,
    "voyage-3.5": 1024,
    "voyage-4-large": 1024,
    "voyage-4": 1024,
    "voyage-4-lite": 512,
    "voyage-code-3": 1024,
}

_DEFAULT_MODEL = "voyage-3.5-lite"
_BATCH_SIZE = 128


class VoyageEmbedding(EmbeddingProvider):
    def __init__(self, model: str = "", api_key: str = "") -> None:
        self._model = model or _DEFAULT_MODEL
        self._client = voyageai.Client(api_key=api_key) if api_key else voyageai.Client()

    def embed(self, texts: list[str]) -> list[list[float]]:
        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), _BATCH_SIZE):
            batch = texts[i : i + _BATCH_SIZE]
            result = self._client.embed(
                batch,
                model=self._model,
                input_type="document",
            )
            all_embeddings.extend(result.embeddings)
        return all_embeddings

    def dimension(self) -> int:
        return _MODEL_DIMENSIONS.get(self._model, 1024)
```

- [ ] **Step 5: openai.py 구현**

`src/deview/embedding/openai.py`:
```python
"""OpenAI 임베딩 프로바이더."""

from __future__ import annotations

from openai import OpenAI

from deview.embedding.base import EmbeddingProvider

_MODEL_DIMENSIONS: dict[str, int] = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}

_DEFAULT_MODEL = "text-embedding-3-small"
_BATCH_SIZE = 2048


class OpenAIEmbedding(EmbeddingProvider):
    def __init__(self, model: str = "", api_key: str = "") -> None:
        self._model = model or _DEFAULT_MODEL
        self._client = OpenAI(api_key=api_key) if api_key else OpenAI()

    def embed(self, texts: list[str]) -> list[list[float]]:
        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), _BATCH_SIZE):
            batch = texts[i : i + _BATCH_SIZE]
            response = self._client.embeddings.create(
                input=batch,
                model=self._model,
            )
            all_embeddings.extend([d.embedding for d in response.data])
        return all_embeddings

    def dimension(self) -> int:
        return _MODEL_DIMENSIONS.get(self._model, 1536)
```

- [ ] **Step 6: local.py 구현**

`src/deview/embedding/local.py`:
```python
"""로컬 임베딩 프로바이더 (sentence-transformers)."""

from __future__ import annotations

from deview.embedding.base import EmbeddingProvider

_DEFAULT_MODEL = "BAAI/bge-large-en-v1.5"

_MODEL_DIMENSIONS: dict[str, int] = {
    "BAAI/bge-large-en-v1.5": 1024,
    "BAAI/bge-base-en-v1.5": 768,
    "sentence-transformers/all-MiniLM-L6-v2": 384,
}


class LocalEmbedding(EmbeddingProvider):
    def __init__(self, model: str = "", api_key: str = "") -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise ImportError(
                "로컬 임베딩을 사용하려면 추가 패키지가 필요합니다: "
                "uv sync --extra local"
            ) from e
        self._model_name = model or _DEFAULT_MODEL
        self._model = SentenceTransformer(self._model_name)

    def embed(self, texts: list[str]) -> list[list[float]]:
        embeddings = self._model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()

    def dimension(self) -> int:
        return _MODEL_DIMENSIONS.get(self._model_name, 1024)
```

- [ ] **Step 7: __init__.py 팩토리 구현**

`src/deview/embedding/__init__.py`:
```python
"""임베딩 프로바이더 팩토리."""

from __future__ import annotations

from deview.config import ProviderConfig
from deview.embedding.base import EmbeddingProvider


def create_provider(name: str, config: ProviderConfig) -> EmbeddingProvider:
    """프로바이더 이름으로 구현체를 생성한다."""
    if name == "voyage":
        from deview.embedding.voyage import VoyageEmbedding
        return VoyageEmbedding(model=config.model, api_key=config.api_key)
    elif name == "openai":
        from deview.embedding.openai import OpenAIEmbedding
        return OpenAIEmbedding(model=config.model, api_key=config.api_key)
    elif name == "local":
        from deview.embedding.local import LocalEmbedding
        return LocalEmbedding(model=config.model)
    elif name == "mistral":
        raise NotImplementedError("Mistral provider는 Phase 1에서 미구현")
    else:
        raise ValueError(f"Unknown embedding provider: {name}")
```

- [ ] **Step 8: 테스트 통과 확인**

```bash
uv run pytest tests/test_embedding.py -v
```

Expected: 4 passed

- [ ] **Step 9: 커밋**

```bash
git add src/deview/embedding/ tests/test_embedding.py
git commit -m "feat: add embedding abstraction with voyage, openai, local providers"
```

---

### Task 5: ChromaDB 스토리지

**Files:**
- Create: `src/deview/storage/__init__.py`
- Create: `src/deview/storage/chroma.py`
- Create: `tests/test_storage.py`

- [ ] **Step 1: 스토리지 테스트 작성**

`tests/test_storage.py`:
```python
import pytest
from deview.storage.chroma import ChromaStore


@pytest.fixture
def store(tmp_path):
    """테스트용 임시 ChromaDB 스토어."""
    return ChromaStore(persist_dir=str(tmp_path / "chroma"))


def test_add_and_search(store: ChromaStore):
    """청크를 저장하고 검색할 수 있다."""
    store.add(
        ids=["chunk-1"],
        embeddings=[[0.1, 0.2, 0.3]],
        contents=["공용 Button 대신 커스텀 구현"],
        metadatas=[{
            "scope": "team/project",
            "source": "git",
            "author": "kim",
            "file_paths": "src/Button.tsx",
            "timestamp": "2025-11-03",
        }],
    )

    results = store.search(
        query_embedding=[0.1, 0.2, 0.3],
        scope="team/project",
        top_k=5,
    )
    assert len(results) == 1
    assert results[0]["content"] == "공용 Button 대신 커스텀 구현"
    assert results[0]["metadata"]["author"] == "kim"


def test_search_with_file_path_filter(store: ChromaStore):
    """file_path 필터로 관련 청크를 우선 검색한다."""
    store.add(
        ids=["chunk-1", "chunk-2"],
        embeddings=[[0.1, 0.2, 0.3], [0.1, 0.2, 0.3]],
        contents=["Button.tsx 관련 변경", "Header.tsx 관련 변경"],
        metadatas=[
            {"scope": "proj", "source": "git", "file_paths": "src/Button.tsx", "timestamp": "2025-01-01"},
            {"scope": "proj", "source": "git", "file_paths": "src/Header.tsx", "timestamp": "2025-01-01"},
        ],
    )

    results = store.search(
        query_embedding=[0.1, 0.2, 0.3],
        scope="proj",
        top_k=5,
        file_path="src/Button.tsx",
    )
    assert len(results) >= 1
    assert results[0]["content"] == "Button.tsx 관련 변경"


def test_search_empty_scope(store: ChromaStore):
    """존재하지 않는 scope로 검색하면 빈 리스트를 반환한다."""
    results = store.search(
        query_embedding=[0.1, 0.2, 0.3],
        scope="nonexistent",
        top_k=5,
    )
    assert results == []


def test_count_by_scope(store: ChromaStore):
    """scope별 청크 수를 조회한다."""
    store.add(
        ids=["c1", "c2", "c3"],
        embeddings=[[0.1, 0.2, 0.3]] * 3,
        contents=["a", "b", "c"],
        metadatas=[
            {"scope": "proj", "source": "git", "timestamp": "2025-01-01"},
            {"scope": "proj", "source": "markdown", "timestamp": "2025-01-01"},
            {"scope": "proj", "source": "manual", "timestamp": "2025-01-01"},
        ],
    )

    counts = store.count_by_source(scope="proj")
    assert counts == {"git": 1, "markdown": 1, "manual": 1}
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
uv run pytest tests/test_storage.py -v
```

Expected: FAIL

- [ ] **Step 3: chroma.py 구현**

`src/deview/storage/__init__.py`:
```python
```

`src/deview/storage/chroma.py`:
```python
"""ChromaDB 벡터 데이터베이스 래퍼."""

from __future__ import annotations

from pathlib import Path

import chromadb


_COLLECTION_NAME = "deview_contexts"


class ChromaStore:
    def __init__(self, persist_dir: str | None = None) -> None:
        if persist_dir is None:
            persist_dir = str(Path.home() / ".deview" / "data" / "chroma")
        Path(persist_dir).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=persist_dir)
        self._collection = self._client.get_or_create_collection(
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def add(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        contents: list[str],
        metadatas: list[dict],
    ) -> None:
        """청크를 저장한다."""
        self._collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=contents,
            metadatas=metadatas,
        )

    def search(
        self,
        query_embedding: list[float],
        scope: str | None = None,
        top_k: int = 5,
        file_path: str | None = None,
    ) -> list[dict]:
        """scope 내에서 유사도 검색을 수행한다. scope가 None이면 전체 통합 검색."""
        where_filter: dict | None = {"scope": scope} if scope else None

        try:
            query_kwargs: dict = {
                "query_embeddings": [query_embedding],
                "n_results": top_k,
            }
            if where_filter:
                query_kwargs["where"] = where_filter
            results = self._collection.query(**query_kwargs)
        except Exception:
            return []

        if not results["ids"] or not results["ids"][0]:
            return []

        items = []
        for i, doc_id in enumerate(results["ids"][0]):
            item = {
                "id": doc_id,
                "content": results["documents"][0][i] if results["documents"] else "",
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                "score": 1.0 - (results["distances"][0][i] if results["distances"] else 0.0),
            }
            items.append(item)

        if file_path:
            items.sort(
                key=lambda x: (
                    file_path not in x["metadata"].get("file_paths", ""),
                    -x["score"],
                )
            )

        return items

    def count_by_source(self, scope: str) -> dict[str, int]:
        """scope 내 소스별 청크 수를 반환한다."""
        counts: dict[str, int] = {}
        for source in ("git", "markdown", "manual", "comment"):
            try:
                result = self._collection.get(
                    where={"$and": [{"scope": scope}, {"source": source}]},
                )
                count = len(result["ids"]) if result["ids"] else 0
            except Exception:
                count = 0
            if count > 0:
                counts[source] = count
        return counts

    def get_last_indexed(self, scope: str) -> str | None:
        """scope의 마지막 인덱싱 시각을 반환한다."""
        try:
            result = self._collection.get(
                where={"scope": scope},
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
            return None
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
uv run pytest tests/test_storage.py -v
```

Expected: 4 passed

- [ ] **Step 5: 커밋**

```bash
git add src/deview/storage/ tests/test_storage.py
git commit -m "feat: add ChromaDB storage wrapper with scope filtering"
```

---

### Task 6: Git 파서

**Files:**
- Create: `src/deview/ingestion/__init__.py`
- Create: `src/deview/ingestion/git.py`
- Create: `tests/test_ingestion_git.py`

- [ ] **Step 1: Git 파서 테스트 작성**

`tests/test_ingestion_git.py`:
```python
import pytest
from pathlib import Path
from deview.ingestion.git import parse_git_history, Chunk

import git as gitmodule


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """테스트용 git 저장소를 만든다."""
    repo = gitmodule.Repo.init(tmp_path)
    repo.config_writer().set_value("user", "name", "Test User").release()
    repo.config_writer().set_value("user", "email", "test@test.com").release()

    # 첫 번째 커밋: 파일 생성
    (tmp_path / "main.py").write_text("# Main module\ndef hello():\n    pass\n")
    repo.index.add(["main.py"])
    repo.index.commit("feat: add main module")

    # 두 번째 커밋: 주석 추가
    (tmp_path / "main.py").write_text(
        "# Main module\ndef hello():\n    # 인사를 출력한다\n    print('hello')\n"
    )
    repo.index.add(["main.py"])
    repo.index.commit("feat: implement hello function")

    return tmp_path


def test_parse_git_history(git_repo: Path):
    """git 히스토리에서 청크를 추출한다."""
    chunks = parse_git_history(git_repo, branch="master", scope="test/project")
    assert len(chunks) >= 2

    # 모든 청크에 필수 메타데이터가 있다
    for chunk in chunks:
        assert chunk.content
        assert chunk.metadata["scope"] == "test/project"
        assert chunk.metadata["source"] in ("git", "comment")
        assert chunk.metadata["author"]
        assert chunk.metadata["timestamp"]


def test_parse_git_history_max_commits(git_repo: Path):
    """max_commits로 인덱싱 범위를 제한한다."""
    chunks = parse_git_history(
        git_repo, branch="master", scope="test/project", max_commits=1,
    )
    commit_chunks = [c for c in chunks if c.metadata["source"] == "git"]
    assert len(commit_chunks) == 1


def test_comment_extraction(git_repo: Path):
    """주석 변경을 별도 청크로 추출한다."""
    chunks = parse_git_history(git_repo, branch="master", scope="test/project")
    comment_chunks = [c for c in chunks if c.metadata["source"] == "comment"]
    assert len(comment_chunks) >= 1
    assert "인사를 출력한다" in comment_chunks[0].content
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
uv run pytest tests/test_ingestion_git.py -v
```

Expected: FAIL

- [ ] **Step 3: git.py 구현**

`src/deview/ingestion/__init__.py`:
```python
```

`src/deview/ingestion/git.py`:
```python
"""Git 히스토리 파싱 및 청크 생성."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import git


@dataclass
class Chunk:
    content: str
    metadata: dict[str, str] = field(default_factory=dict)


_COMMENT_PATTERNS = [
    re.compile(r"^\+\s*(?:#|//|/\*|\*|<!--)\s*(.+)", re.MULTILINE),
]


def _extract_comment_additions(diff_text: str) -> list[str]:
    """diff에서 추가된 주석 라인을 추출한다."""
    comments: list[str] = []
    for pattern in _COMMENT_PATTERNS:
        for match in pattern.finditer(diff_text):
            comment = match.group(1).strip()
            if comment and len(comment) > 5:
                comments.append(comment)
    return comments


def _extract_file_paths(diff_index) -> list[str]:
    """diff에서 변경된 파일 경로 목록을 추출한다."""
    paths: list[str] = []
    for diff_item in diff_index:
        if diff_item.b_path:
            paths.append(diff_item.b_path)
        elif diff_item.a_path:
            paths.append(diff_item.a_path)
    return paths


def _summarize_diff(diff_index) -> str:
    """diff를 파일별 변경 요약으로 축소한다."""
    summaries: list[str] = []
    for diff_item in diff_index:
        path = diff_item.b_path or diff_item.a_path or "unknown"
        if diff_item.new_file:
            summaries.append(f"{path} (신규)")
        elif diff_item.deleted_file:
            summaries.append(f"{path} (삭제)")
        else:
            summaries.append(f"{path} (수정)")
    return "변경 파일: " + ", ".join(summaries) if summaries else ""


def parse_git_history(
    repo_path: Path,
    branch: str = "main",
    scope: str = "",
    max_commits: int | None = None,
) -> list[Chunk]:
    """git 히스토리를 파싱하여 청크 리스트를 반환한다."""
    repo = git.Repo(repo_path)
    chunks: list[Chunk] = []

    commits = list(repo.iter_commits(branch, max_count=max_commits or 999999))

    for commit in commits:
        author = commit.author.name or "unknown"
        timestamp = commit.committed_datetime.strftime("%Y-%m-%d")
        message = commit.message.strip()

        # diff 계산 (첫 커밋은 부모가 없음)
        if commit.parents:
            diff_index = commit.parents[0].diff(commit)
        else:
            diff_index = commit.diff(git.NULL_TREE)

        file_paths = _extract_file_paths(diff_index)
        diff_summary = _summarize_diff(diff_index)

        # 커밋 청크
        content_parts = [message]
        if diff_summary:
            content_parts.append(diff_summary)
        commit_content = "\n\n".join(content_parts)

        chunks.append(Chunk(
            content=commit_content,
            metadata={
                "scope": scope,
                "source": "git",
                "author": author,
                "file_paths": ",".join(file_paths),
                "commit_hash": commit.hexsha[:7],
                "timestamp": timestamp,
            },
        ))

        # 주석 변경 청크
        for diff_item in diff_index:
            try:
                diff_text = diff_item.diff.decode("utf-8", errors="ignore")
            except Exception:
                continue
            comments = _extract_comment_additions(diff_text)
            if comments:
                comment_file = diff_item.b_path or diff_item.a_path or "unknown"
                chunks.append(Chunk(
                    content="주석 추가: " + " | ".join(comments),
                    metadata={
                        "scope": scope,
                        "source": "comment",
                        "author": author,
                        "file_paths": comment_file,
                        "commit_hash": commit.hexsha[:7],
                        "timestamp": timestamp,
                    },
                ))

    return chunks
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
uv run pytest tests/test_ingestion_git.py -v
```

Expected: 3 passed

- [ ] **Step 5: 커밋**

```bash
git add src/deview/ingestion/ tests/test_ingestion_git.py
git commit -m "feat: add git history parser with comment extraction"
```

---

### Task 7: Markdown 파서

**Files:**
- Create: `src/deview/ingestion/markdown.py`
- Create: `tests/test_ingestion_markdown.py`

- [ ] **Step 1: Markdown 파서 테스트 작성**

`tests/test_ingestion_markdown.py`:
```python
from pathlib import Path
from deview.ingestion.markdown import parse_markdown_files, Chunk


def test_parse_single_file(tmp_path: Path):
    """Markdown 파일을 헤딩 기준으로 분할한다."""
    md_file = tmp_path / "design.md"
    md_file.write_text("""# 프로젝트 설계

## 아키텍처
마이크로서비스 기반 구조를 사용한다.

## 데이터베이스
PostgreSQL을 메인 DB로 사용한다.
""")

    chunks = parse_markdown_files(tmp_path, scope="test/project")
    assert len(chunks) == 2
    assert "마이크로서비스" in chunks[0].content
    assert "PostgreSQL" in chunks[1].content
    assert chunks[0].metadata["section"] == "## 아키텍처"
    assert chunks[0].metadata["source"] == "markdown"


def test_parse_directory(tmp_path: Path):
    """디렉토리 내 모든 .md 파일을 파싱한다."""
    (tmp_path / "a.md").write_text("## 섹션A\n내용A\n")
    (tmp_path / "b.md").write_text("## 섹션B\n내용B\n")
    (tmp_path / "skip.txt").write_text("이건 무시")

    chunks = parse_markdown_files(tmp_path, scope="test/project")
    assert len(chunks) == 2
    contents = {c.content for c in chunks}
    assert any("내용A" in c for c in contents)
    assert any("내용B" in c for c in contents)


def test_parse_no_headings(tmp_path: Path):
    """헤딩이 없는 파일은 전체를 하나의 청크로 처리한다."""
    md_file = tmp_path / "notes.md"
    md_file.write_text("그냥 메모입니다.\n여러 줄.\n")

    chunks = parse_markdown_files(tmp_path, scope="test/project")
    assert len(chunks) == 1
    assert "그냥 메모" in chunks[0].content
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
uv run pytest tests/test_ingestion_markdown.py -v
```

Expected: FAIL

- [ ] **Step 3: markdown.py 구현**

`src/deview/ingestion/markdown.py`:
```python
"""Markdown 파일 파싱 및 청크 생성."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from deview.ingestion.git import Chunk

_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


def _split_by_headings(text: str) -> list[tuple[str, str]]:
    """Markdown 텍스트를 헤딩 기준으로 (헤딩, 내용) 쌍으로 분할한다."""
    matches = list(_HEADING_PATTERN.finditer(text))

    if not matches:
        stripped = text.strip()
        if stripped:
            return [("", stripped)]
        return []

    sections: list[tuple[str, str]] = []
    for i, match in enumerate(matches):
        heading = match.group(0)
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        if content:
            sections.append((heading, content))

    return sections


def parse_markdown_files(
    path: Path,
    scope: str = "",
) -> list[Chunk]:
    """경로에서 .md 파일을 찾아 청크 리스트를 반환한다."""
    if path.is_file():
        files = [path] if path.suffix == ".md" else []
    else:
        files = sorted(path.rglob("*.md"))

    chunks: list[Chunk] = []
    for md_file in files:
        text = md_file.read_text(encoding="utf-8")
        mtime = datetime.fromtimestamp(md_file.stat().st_mtime).strftime("%Y-%m-%d")

        sections = _split_by_headings(text)
        for heading, content in sections:
            chunks.append(Chunk(
                content=f"{heading}\n{content}" if heading else content,
                metadata={
                    "scope": scope,
                    "source": "markdown",
                    "file_paths": str(md_file),
                    "section": heading,
                    "timestamp": mtime,
                },
            ))

    return chunks
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
uv run pytest tests/test_ingestion_markdown.py -v
```

Expected: 3 passed

- [ ] **Step 5: 커밋**

```bash
git add src/deview/ingestion/markdown.py tests/test_ingestion_markdown.py
git commit -m "feat: add markdown parser with heading-based chunking"
```

---

### Task 8: Manual Note 저장

**Files:**
- Create: `src/deview/ingestion/manual.py`

- [ ] **Step 1: manual.py 구현**

`src/deview/ingestion/manual.py`:
```python
"""수동 메모 청크 생성."""

from __future__ import annotations

import uuid
from datetime import datetime

from deview.ingestion.git import Chunk


def create_manual_chunk(
    content: str,
    scope: str,
    file_paths: list[str] | None = None,
) -> Chunk:
    """수동 메모를 청크로 변환한다."""
    return Chunk(
        content=content,
        metadata={
            "scope": scope,
            "source": "manual",
            "file_paths": ",".join(file_paths) if file_paths else "",
            "timestamp": datetime.now().strftime("%Y-%m-%d"),
        },
    )


def generate_chunk_id() -> str:
    """청크 ID를 생성한다."""
    return f"manual-{uuid.uuid4().hex[:12]}"
```

- [ ] **Step 2: 커밋**

```bash
git add src/deview/ingestion/manual.py
git commit -m "feat: add manual note chunk creation"
```

---

### Task 9: MCP 도구 구현

**Files:**
- Create: `src/deview/tools/__init__.py`
- Create: `src/deview/tools/search.py`
- Create: `src/deview/tools/write.py`
- Create: `src/deview/tools/ingest.py`
- Create: `src/deview/tools/status.py`
- Create: `tests/test_tools.py`

- [ ] **Step 1: MCP 도구 통합 테스트 작성**

`tests/test_tools.py`:
```python
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from deview.tools.search import handle_search
from deview.tools.write import handle_write
from deview.tools.ingest import handle_ingest
from deview.tools.status import handle_status
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
async def test_write_and_search(store: ChromaStore, embedding: FakeEmbedding):
    """write로 저장한 맥락을 search로 검색할 수 있다."""
    write_result = await handle_write(
        content="ORM 대신 raw query 사용 결정",
        scope="test/proj",
        file_paths=["src/db.py"],
        store=store,
        embedding=embedding,
    )
    assert write_result["id"]
    assert write_result["scope"] == "test/proj"

    search_result = await handle_search(
        query="왜 raw query를 쓰나요",
        scope="test/proj",
        top_k=5,
        sort_by="relevance",
        store=store,
        embedding=embedding,
    )
    assert len(search_result["results"]) == 1
    assert "raw query" in search_result["results"][0]["content"]


@pytest.mark.asyncio
async def test_ingest_git(store: ChromaStore, embedding: FakeEmbedding, tmp_path: Path):
    """git 저장소를 인덱싱할 수 있다."""
    import git
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    repo = git.Repo.init(repo_path)
    repo.config_writer().set_value("user", "name", "Test").release()
    repo.config_writer().set_value("user", "email", "t@t.com").release()
    (repo_path / "app.py").write_text("print('hello')\n")
    repo.index.add(["app.py"])
    repo.index.commit("init: add app")

    result = await handle_ingest(
        path=str(repo_path),
        scope="test/proj",
        source_type="git",
        max_commits=None,
        store=store,
        embedding=embedding,
        branch="master",
    )
    assert result["chunks_indexed"] >= 1
    assert result["source_type"] == "git"


@pytest.mark.asyncio
async def test_status(store: ChromaStore, embedding: FakeEmbedding):
    """status로 현재 상태를 조회한다."""
    await handle_write(
        content="테스트 메모",
        scope="test/proj",
        store=store,
        embedding=embedding,
    )

    result = await handle_status(scope="test/proj", store=store, embedding_provider="voyage")
    assert result["scope"] == "test/proj"
    assert result["total_chunks"] >= 1
    assert result["embedding_provider"] == "voyage"
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
uv run pytest tests/test_tools.py -v
```

Expected: FAIL

- [ ] **Step 3: search.py 구현**

`src/deview/tools/search.py`:
```python
"""deview_search MCP 도구 핸들러."""

from __future__ import annotations

from deview.embedding.base import EmbeddingProvider
from deview.storage.chroma import ChromaStore


async def handle_search(
    query: str,
    scope: str,
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
        query_embedding=query_vector,
        scope=scope,
        top_k=top_k,
        file_path=file_path,
    )

    if sort_by == "timestamp":
        results.sort(key=lambda x: x["metadata"].get("timestamp", ""), reverse=True)

    return {
        "results": [
            {
                "content": r["content"],
                "source": r["metadata"].get("source", ""),
                "file_paths": r["metadata"].get("file_paths", "").split(",") if r["metadata"].get("file_paths") else [],
                "author": r["metadata"].get("author", ""),
                "timestamp": r["metadata"].get("timestamp", ""),
                "score": r["score"],
            }
            for r in results
        ]
    }
```

- [ ] **Step 4: write.py 구현**

`src/deview/tools/write.py`:
```python
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
```

- [ ] **Step 5: ingest.py 구현**

`src/deview/tools/ingest.py`:
```python
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
            target, branch=branch, scope=scope, max_commits=max_commits,
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

    return {
        "scope": scope,
        "chunks_indexed": len(chunks),
        "source_type": resolved_type,
    }
```

- [ ] **Step 6: status.py 구현**

`src/deview/tools/status.py`:
```python
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
```

- [ ] **Step 7: tools/__init__.py 작성**

`src/deview/tools/__init__.py`:
```python
```

- [ ] **Step 8: 테스트 통과 확인**

```bash
uv run pytest tests/test_tools.py -v
```

Expected: 4 passed

- [ ] **Step 9: 커밋**

```bash
git add src/deview/tools/ tests/test_tools.py
git commit -m "feat: add MCP tool handlers for search, write, ingest, status"
```

---

### Task 10: MCP 서버 진입점

**Files:**
- Create: `src/deview/server.py`

- [ ] **Step 1: server.py 구현**

`src/deview/server.py`:
```python
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
    description="Digital Psychometry for Developers — 프로젝트 맥락 저장소",
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
    사용자가 '왜', '어떻게', '언제', '누가' 등 맥락을 물을 때 호출하세요."""
    return await handle_search(
        query=query,
        scope=scope or _scope,
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
```

- [ ] **Step 2: 서버 실행 테스트**

```bash
uv run mcp dev src/deview/server.py
```

Expected: MCP Inspector가 열리고, 4개 도구가 등록된 것을 확인

- [ ] **Step 3: 커밋**

```bash
git add src/deview/server.py
git commit -m "feat: add MCP server entrypoint with FastMCP"
```

---

### Task 11: 설정 예시 및 로컬 임베딩 가이드

**Files:**
- Create: `.deview.yaml.example`
- Create: `docs/guides/local-embedding-setup.md`

- [ ] **Step 1: .deview.yaml.example 작성**

`.deview.yaml.example`:
```yaml
# Deview 프로젝트 설정 (선택사항)
# 이 파일이 없어도 기본값으로 동작합니다.
# 프로젝트 루트에 .deview.yaml 으로 복사하여 사용하세요.

# Scope: 생략 시 git remote URL에서 자동 추론
# scope: "team/my-project"

# 임베딩 설정
embedding:
  # 사용할 provider (voyage | openai | mistral | local)
  provider: "voyage"

  # Provider별 설정 (여러 개 등록 가능, provider 값만 바꿔서 전환)
  providers:
    voyage:
      model: "voyage-3.5-lite"
      api_key: "${VOYAGE_API_KEY}"
    openai:
      model: "text-embedding-3-small"
      api_key: "${OPENAI_API_KEY}"
    mistral:
      model: "mistral-embed"
      api_key: "${MISTRAL_API_KEY}"
    local:
      model: "BAAI/bge-large-en-v1.5"
      # API 키 불필요

# 인덱싱 설정
ingestion:
  git:
    target_branch: "main"
    # max_commits: 1000  # 전체 히스토리 대신 최근 N개만 인덱싱
```

- [ ] **Step 2: 로컬 임베딩 설치 가이드 작성**

`docs/guides/local-embedding-setup.md`:
```markdown
# 로컬 임베딩 모델 설치 가이드

API 키 없이 오프라인에서 임베딩을 수행하려면 로컬 모델을 설치합니다.

## 설치

```bash
# Deview 프로젝트에서
uv sync --extra local
```

이 명령은 `sentence-transformers`와 `torch`를 설치합니다.

## 설정

프로젝트의 `.deview.yaml`에서 provider를 `local`로 설정합니다:

```yaml
embedding:
  provider: "local"
  providers:
    local:
      model: "BAAI/bge-large-en-v1.5"
```

## 지원 모델

| 모델 | 차원 | 크기 | 특징 |
|:---|:---|:---|:---|
| `BAAI/bge-large-en-v1.5` (기본) | 1024 | ~1.3GB | 상용 수준 품질 |
| `BAAI/bge-base-en-v1.5` | 768 | ~440MB | 품질/속도 균형 |
| `sentence-transformers/all-MiniLM-L6-v2` | 384 | ~80MB | 가볍고 빠름 |

## 첫 실행

최초 실행 시 모델을 자동 다운로드합니다 (인터넷 필요).
이후에는 캐시된 모델을 사용하므로 오프라인에서도 동작합니다.

캐시 위치: `~/.cache/huggingface/hub/`

## 주의사항

- 임베딩 모델을 변경하면 기존 인덱스와 호환되지 않습니다. 모델 변경 후 재인덱싱이 필요합니다.
- GPU가 있으면 자동으로 활용합니다. CPU만으로도 동작하지만 속도가 느립니다.
```

- [ ] **Step 3: 커밋**

```bash
git add .deview.yaml.example docs/guides/
git commit -m "docs: add deview.yaml example and local embedding setup guide"
```

---

### Task 12: 전체 통합 테스트

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: 통합 테스트 작성**

`tests/test_integration.py`:
```python
"""End-to-end: git 인덱싱 → 검색 → 결과 확인."""

import pytest
from pathlib import Path

import git as gitmodule

from deview.config import load_config, ProviderConfig
from deview.embedding import create_provider
from deview.embedding.base import EmbeddingProvider
from deview.scope import resolve_scope
from deview.storage.chroma import ChromaStore
from deview.tools.ingest import handle_ingest
from deview.tools.search import handle_search
from deview.tools.write import handle_write
from deview.tools.status import handle_status


class FakeEmbedding(EmbeddingProvider):
    """테스트용: 텍스트 길이 기반의 결정론적 임베딩."""
    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            length = len(text) % 100 / 100.0
            vectors.append([length, length * 0.5, length * 0.3])
        return vectors

    def dimension(self) -> int:
        return 3


@pytest.fixture
def test_repo(tmp_path: Path) -> Path:
    repo_path = tmp_path / "project"
    repo_path.mkdir()
    repo = gitmodule.Repo.init(repo_path)
    repo.create_remote("origin", "git@github.com:team/test-project.git")
    repo.config_writer().set_value("user", "name", "Kim").release()
    repo.config_writer().set_value("user", "email", "kim@test.com").release()

    (repo_path / "button.tsx").write_text(
        "// 공용 Button의 ripple이 미지원이라 커스텀\n"
        "export function CustomButton() {}\n"
    )
    repo.index.add(["button.tsx"])
    repo.index.commit("feat: 공용 Button 대신 커스텀 버튼 구현")

    return repo_path


@pytest.fixture
def store(tmp_path: Path) -> ChromaStore:
    return ChromaStore(persist_dir=str(tmp_path / "chroma"))


@pytest.fixture
def embedding() -> FakeEmbedding:
    return FakeEmbedding()


@pytest.mark.asyncio
async def test_full_flow(test_repo: Path, store: ChromaStore, embedding: FakeEmbedding):
    """전체 흐름: scope 추론 → 인덱싱 → 수동 기록 → 검색 → 상태 확인."""

    # 1. Scope 추론
    scope = resolve_scope(yaml_scope=None, project_path=test_repo)
    assert scope == "team/test-project"

    # 2. Git 인덱싱
    ingest_result = await handle_ingest(
        path=str(test_repo),
        scope=scope,
        source_type="git",
        store=store,
        embedding=embedding,
        branch="master",
    )
    assert ingest_result["chunks_indexed"] >= 1

    # 3. 수동 메모 저장
    write_result = await handle_write(
        content="공용 Button v2 출시 후 전환 예정",
        scope=scope,
        file_paths=["button.tsx"],
        store=store,
        embedding=embedding,
    )
    assert write_result["id"]

    # 4. 검색
    search_result = await handle_search(
        query="버튼을 왜 커스텀으로 만들었나",
        scope=scope,
        top_k=5,
        sort_by="relevance",
        store=store,
        embedding=embedding,
    )
    assert len(search_result["results"]) >= 1

    # 5. 상태 확인
    status_result = await handle_status(
        scope=scope,
        store=store,
        embedding_provider="fake",
    )
    assert status_result["total_chunks"] >= 2
    assert status_result["scope"] == "team/test-project"
```

- [ ] **Step 2: 통합 테스트 통과 확인**

```bash
uv run pytest tests/test_integration.py -v
```

Expected: 1 passed

- [ ] **Step 3: 전체 테스트 실행**

```bash
uv run pytest tests/ -v
```

Expected: 모든 테스트 passed

- [ ] **Step 4: 커밋**

```bash
git add tests/test_integration.py
git commit -m "test: add end-to-end integration test"
```

---

## Execution Checklist

| Task | 설명 | 예상 소요 |
|:---|:---|:---|
| 1 | 프로젝트 스캐폴딩 | 5분 |
| 2 | 설정 모듈 | 10분 |
| 3 | Scope 추론 | 10분 |
| 4 | 임베딩 추상화 | 15분 |
| 5 | ChromaDB 스토리지 | 10분 |
| 6 | Git 파서 | 15분 |
| 7 | Markdown 파서 | 10분 |
| 8 | Manual Note | 5분 |
| 9 | MCP 도구 구현 | 15분 |
| 10 | MCP 서버 진입점 | 10분 |
| 11 | 설정 예시 + 가이드 | 5분 |
| 12 | 통합 테스트 | 10분 |
