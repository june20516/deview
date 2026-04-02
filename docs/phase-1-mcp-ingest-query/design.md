# Phase 1: MCP Ingest & Query — 상세 설계

## 1. 목표

Deview의 핵심 가치를 검증하는 최소 구현.
- MCP 서버로 동작하여 LLM 클라이언트에서 자연스럽게 맥락 검색
- Git 히스토리, Markdown, 수동 메모를 인덱싱
- Scope 자동 추론으로 설정 없이 바로 사용 가능

---

## 2. 디렉토리 구조

```
deview/
├── pyproject.toml              # uv 프로젝트 설정
├── README.md
├── docs/
│   ├── high-level-design.md
│   ├── phase-1-mcp-ingest-query/
│   │   └── design.md           # 이 문서
│   └── guides/
│       └── local-embedding-setup.md   # 로컬 임베딩 모델 설치 가이드
├── src/
│   └── deview/
│       ├── __init__.py
│       ├── server.py           # MCP 서버 진입점
│       ├── config.py           # 설정 로드 (.deview.yaml + 환경변수)
│       ├── scope.py            # Scope 추론/관리
│       ├── embedding/
│       │   ├── __init__.py
│       │   ├── base.py         # 임베딩 추상 인터페이스
│       │   ├── voyage.py       # Voyage API 구현
│       │   ├── openai.py       # OpenAI API 구현
│       │   └── local.py        # BGE-large 로컬 구현
│       ├── ingestion/
│       │   ├── __init__.py
│       │   ├── git.py          # Git 히스토리 파싱 + 주석 변경 추출
│       │   ├── markdown.py     # Markdown 헤딩 기준 분할
│       │   └── manual.py       # 수동 메모 저장
│       ├── storage/
│       │   ├── __init__.py
│       │   └── chroma.py       # ChromaDB 연동
│       └── tools/
│           ├── __init__.py
│           ├── search.py       # deview_search MCP 도구
│           ├── write.py        # deview_write MCP 도구
│           ├── ingest.py       # deview_ingest MCP 도구
│           └── status.py       # deview_status MCP 도구
├── tests/
│   ├── __init__.py
│   ├── test_scope.py
│   ├── test_embedding.py
│   ├── test_ingestion.py
│   ├── test_storage.py
│   └── test_tools.py
└── .deview.yaml.example        # 설정 파일 예시
```

---

## 3. 설정 구조

### 3.1. `.deview.yaml`

```yaml
# 선택사항 — 없으면 모두 기본값으로 동작
scope: "my-project"                    # 생략 시 git remote URL에서 자동 추론

embedding:
  provider: "voyage"                   # 사용할 provider 지정 (필수 아님, 기본 voyage)
  providers:                           # 사용 가능한 provider 등록 (여러 개 가능)
    voyage:
      model: "voyage-3.5-lite"         # 생략 시 기본 모델
      api_key: "${VOYAGE_API_KEY}"     # 환경변수 참조 또는 직접 입력
    openai:
      model: "text-embedding-3-small"
      api_key: "${OPENAI_API_KEY}"
    mistral:
      model: "mistral-embed"
      api_key: "${MISTRAL_API_KEY}"
    local:
      model: "BGE-large-en-v1.5"      # API 키 불필요

ingestion:
  git:
    target_branch: "main"              # 인덱싱 대상 브랜치
    max_commits: null                  # null = 전체, 숫자 = 최근 N개 제한
```

이렇게 하면 provider들을 미리 등록해두고 `embedding.provider` 값만 바꿔서 전환할 수 있습니다.

### 3.2. 환경변수

| 변수 | 용도 | 비고 |
|:---|:---|:---|
| `VOYAGE_API_KEY` | Voyage 임베딩 API | yaml에서 `${VOYAGE_API_KEY}`로 참조 |
| `OPENAI_API_KEY` | OpenAI 임베딩 API | yaml에서 `${OPENAI_API_KEY}`로 참조 |
| `MISTRAL_API_KEY` | Mistral 임베딩 API | yaml에서 `${MISTRAL_API_KEY}`로 참조 |
| (없음) | 로컬 임베딩 | provider가 local이면 API 키 불필요 |

> yaml에 API 키를 직접 입력할 수도 있지만, 환경변수 참조를 권장합니다. `.deview.yaml`을 git에 커밋할 경우 키 노출 방지.

### 3.3. 설정 우선순위

환경변수 > `.deview.yaml` > 기본값

---

## 4. Scope 추론

```python
# 우선순위
1. .deview.yaml의 scope 필드 (명시적 오버라이드)
2. git remote URL 파싱
   - "git@github.com:team/my-project.git" → "team/my-project"
   - "https://github.com/team/my-project.git" → "team/my-project"
3. 현재 디렉토리명 (git이 아닌 경우 fallback)
```

---

## 5. MCP 도구 상세

### 5.1. `deview_search`

```
description: "프로젝트의 과거 의사결정, 컨벤션, 변경 히스토리,
특정 구현의 배경을 검색합니다. 사용자가 '왜', '어떻게',
'언제', '누가' 등 맥락을 물을 때 호출하세요."

parameters:
  query: string (필수) — 검색 질문
  scope: string (선택) — 생략 시 전체 Scope 통합 검색. 특정 scope 지정 가능.
  file_path: string (선택) — 특정 파일 관련 맥락 우선 검색
  top_k: int (선택, 기본 5) — 반환할 맥락 수
  sort_by: string (선택, 기본 "relevance") — "relevance" (유사도순) | "timestamp" (시간순)

returns:
  results: [
    {
      content: string,       # 맥락 원문
      source: string,        # "git" | "markdown" | "manual"
      file_paths: [string],  # 관련 파일 경로
      author: string,        # 작성자
      timestamp: string,     # 날짜
      score: float           # 유사도 점수
    }
  ]
```

### 5.2. `deview_write`

```
description: "사용자가 명시적으로 지시할 때, 중요한 의사결정이나
기술적 맥락을 기록합니다. 자동 수집이 아닌 수동 저장용입니다.
사용자가 '기록해', '저장해', '메모해' 등의 지시를 할 때 호출하세요."

parameters:
  content: string (필수) — 저장할 맥락 내용
  scope: string (선택) — 생략 시 현재 프로젝트 scope
  file_paths: [string] (선택) — 관련 파일 경로

returns:
  id: string,               # 저장된 청크 ID
  scope: string
```

### 5.3. `deview_ingest`

```
description: "프로젝트의 Git 히스토리 또는 Markdown 문서를 인덱싱합니다.
최초 사용 시 또는 새로운 데이터를 수동으로 추가할 때 호출하세요."

parameters:
  path: string (필수) — 인덱싱할 경로 (git 저장소 또는 파일/디렉토리)
  scope: string (선택) — 생략 시 자동 추론
  source_type: string (선택) — "git" | "markdown" | "auto" (기본 auto)
  max_commits: int (선택) — git 인덱싱 시 최근 N개 제한

returns:
  scope: string,
  chunks_indexed: int,       # 인덱싱된 청크 수
  source_type: string
```

### 5.4. `deview_status`

```
description: "현재 Deview의 상태를 확인합니다.
Scope 정보, 인덱싱된 청크 수, 마지막 인덱싱 시각 등을 반환합니다."

parameters:
  scope: string (선택) — 생략 시 현재 프로젝트 scope

returns:
  scope: string,
  total_chunks: int,
  sources: {
    git: int,
    markdown: int,
    manual: int
  },
  last_indexed: string,      # ISO 8601
  embedding_provider: string
```

---

## 6. 임베딩 추상화

```python
# base.py
class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """텍스트 리스트를 벡터 리스트로 변환"""
        ...

    @abstractmethod
    def dimension(self) -> int:
        """벡터 차원 수 반환"""
        ...
```

| Provider | 모델 | 차원 | 비용 |
|:---|:---|:---|:---|
| `voyage` (기본) | `voyage-3.5-lite` | 1024 | 무료 200M 토큰, 이후 $0.02/MTok |
| `openai` | `text-embedding-3-small` | 1536 | $0.02/MTok |
| `mistral` | `mistral-embed` | 1024 | $0.01/MTok |
| `local` | `BGE-large-en-v1.5` | 1024 | 무료 |

> **주의:** 임베딩 모델을 변경하면 기존 인덱스와 호환되지 않습니다. 모델 변경 시 재인덱싱이 필요하며, 이를 `deview_status`에서 경고합니다.

---

## 7. Ingestion 상세

### 7.1. Git 파서

```
입력: git 저장소 경로 + target_branch

처리:
  1. target_branch의 커밋 목록 조회
  2. 커밋마다:
     a. 메시지 + author + 날짜 추출
     b. diff에서 변경 파일 목록 추출 → file_paths 메타데이터
     c. diff에서 주석 변경분 감지 → 별도 청크로 분리
     d. diff 요약 생성 (큰 diff는 파일별 변경 요약으로 축소)
  3. 각 청크를 임베딩 → ChromaDB 저장

청크 예시 (커밋):
  content: "feat: ProductPage 공용 Button 대신 커스텀 버튼 구현\n\n
            디자인 시안의 ripple 애니메이션을 공용컴포넌트가 지원하지 못해 별도 구현.\n
            변경 파일: src/pages/Product/Button.tsx (+142), src/styles/ripple.css (+38)"
  metadata: {
    scope: "team/my-project",
    source: "git",
    author: "김철수",
    file_paths: ["src/pages/Product/Button.tsx", "src/styles/ripple.css"],
    commit_hash: "a1b2c3d",
    timestamp: "2025-11-03"
  }

청크 예시 (주석 변경):
  content: "주석 추가: // 공용 Button의 ripple 효과가 디자인 요구사항과 달라서
            커스텀 구현. 공용컴포넌트 업데이트 시 전환 검토 필요 (PROJ-456 참고)"
  metadata: {
    scope: "team/my-project",
    source: "comment",
    author: "김철수",
    file_paths: ["src/pages/Product/Button.tsx"],
    commit_hash: "a1b2c3d",
    timestamp: "2025-11-03"
  }
```

### 7.2. Markdown 파서

```
입력: 파일 또는 디렉토리 경로

처리:
  1. .md 파일 탐색
  2. 헤딩(##) 기준으로 섹션 분할
  3. 각 섹션을 청크로 저장

metadata: {
  scope: "team/my-project",
  source: "markdown",
  file_paths: ["docs/architecture.md"],
  section: "## 3. 데이터베이스 설계",
  timestamp: "2025-10-15"  # 파일 수정일
}
```

### 7.3. Manual Note

```
deview_write로 저장되는 수동 메모.

metadata: {
  scope: "team/my-project",
  source: "manual",
  file_paths: [],  # 또는 사용자가 지정한 경로
  timestamp: "2026-04-02"
}
```

---

## 8. 검색 흐름

```
1. query 텍스트를 임베딩 → 벡터화
2. ChromaDB 검색:
   - where: { scope: "team/my-project" }
   - file_path가 제공되면 → 해당 파일 관련 청크 우선 (가중치 부스트)
   - 유사도 기준 상위 top_k개 반환
3. 결과를 score 내림차순으로 정렬하여 클라이언트에 반환
```

---

## 9. 데이터 저장 경로

```
~/.deview/
├── config.yaml          # 글로벌 설정 (선택)
└── data/
    └── chroma/          # ChromaDB 영속 저장소
```

프로젝트별 `.deview.yaml`은 해당 프로젝트 루트에 위치.

---

## 10. Phase 1 작업 범위 요약

| 구분 | 포함 | 제외 |
|:---|:---|:---|
| **인터페이스** | MCP 서버 | REST API, CLI (Phase 2) |
| **데이터 소스** | Git, Markdown, Manual Note | Jira, Confluence (Phase 2) |
| **벡터 DB** | ChromaDB (로컬) | Qdrant (Phase 3) |
| **임베딩** | Voyage, OpenAI, Mistral, 로컬(BGE) | — |
| **Scope** | 자동 추론 + yaml 오버라이드 + 통합 검색 | — |
| **문서** | 로컬 임베딩 설치 가이드 | — |
| **Git 인덱싱** | 전체 히스토리 (N개 제한 옵션) | 자동 인덱싱/Git Hook (Phase 2) |

---

## 11. 의존성

```toml
[project]
name = "deview"
requires-python = ">=3.10"

dependencies = [
    "mcp",                    # MCP 서버 SDK
    "chromadb",               # 벡터 데이터베이스
    "voyageai",               # Voyage 임베딩 (기본)
    "openai",                 # OpenAI 임베딩 (선택)
    "gitpython",              # Git 히스토리 파싱
    "pyyaml",                 # 설정 파일 로드
]

[project.optional-dependencies]
local = [
    "sentence-transformers",  # BGE-large 로컬 임베딩
    "torch",                  # PyTorch (sentence-transformers 의존)
]
mistral = [
    "mistralai",              # Mistral 임베딩
]

[tool.uv]
dev-dependencies = [
    "pytest",
    "pytest-asyncio",
]
```
