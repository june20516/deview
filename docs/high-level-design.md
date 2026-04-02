# [High-Level Design] Deview: Context-Aware Developer Assistant

> *Digital Psychometry for Developers*

## 1. 개요 (Overview)
**Deview**는 개발자의 코드 작성 배경, 의사결정 히스토리, 기술적 제약 사항을 '맥락(Context)' 단위로 저장하고, LLM 클라이언트가 이를 검색·참조하여 최적의 답변을 제공하도록 돕는 **독립적인 맥락 저장소 서버**입니다.

Deview는 LLM을 직접 호출하지 않습니다. 맥락의 **저장과 검색**에만 집중하며, 답변 생성은 이를 활용하는 클라이언트(Claude Code, Cursor, CI/CD 등)의 책임입니다.

---

## 2. 사용 시나리오 (Use Cases)

### 의사결정 추적 — "왜 이렇게 했지?"
- "이 API가 REST 대신 GraphQL을 쓰는 이유가 뭐야?" → 과거 ADR/커밋 메시지 기반
- "결제 모듈에서 왜 외부 라이브러리 안 쓰고 직접 구현했지?" → 당시 기술 검토 기록
- "이 테이블에 왜 soft delete를 적용했어?" → 관련 마이그레이션 커밋 + 논의 기록
- "이 페이지는 왜 공용컴포넌트를 쓰지 않았지?" → 당시 기획 문서, 커밋 메시지, 커밋 author 정보
- "이 클래스/타입과 유사하게 생긴 저 클래스/타입은 왜 구분된거야?" → 코드 분석 + 과거 논의 + 버전 업데이트 계획

### 컨벤션/패턴 파악 — "여기선 어떻게 해?"
- "이 프로젝트에서 에러 핸들링 컨벤션이 뭐야?" → 기존 코드 패턴 + 문서 기반
- "API 응답 포맷 표준이 있어?" → 기존 구현체 패턴 분석
- "테스트 작성 시 mocking 전략이 어떻게 돼?" → 기존 테스트 코드 패턴

### 히스토리 조회 — "무슨 일이 있었어?"
- "최근 한 달간 인증 모듈에 어떤 변경이 있었어?" → git log 기반 요약
- "이 함수가 3번이나 리팩토링된 이유가 뭐야?" → 커밋 히스토리 + 관련 이슈 연결
- "이 버그 패치 전에 어떤 장애가 있었어?" → Jira 이슈 + 커밋 기록 교차 참조

### 온보딩/인수인계 — "빠르게 파악하고 싶어"
- "이 서비스의 전체 아키텍처를 설명해줘" → 코드 구조 + 문서 + 커밋 히스토리 종합
- "내가 이 모듈 담당자가 됐는데, 주의할 점이 뭐야?" → 과거 장애/버그 기록 + 기술 부채
- "이 프로젝트 의존성 중 주의해야 할 게 있어?" → 과거 업그레이드 이슈 기록

### 팀 협업 — "같이 잘 하고 싶어" (팀 배포 시)
- PR 리뷰 시, 변경이 기존 컨벤션과 맞는지 자동 체크
- 새 팀원의 코드가 에러 핸들링 방식을 따르는지 검증
- 현재 설계가 과거에 실패했던 접근법과 유사하지 않은지 대조

### 기술 부채/리스크 인식
- "이 모듈에서 TODO/FIXME가 달린 것들 중 맥락이 있는 게 뭐야?" → 코드 주석 + 관련 커밋/이슈 연결
- "deprecated된 API를 아직 쓰고 있는 곳이 있어?" → 코드 분석 + 과거 논의

---

## 3. 핵심 개념: Scope (스코프)
데이터를 논리적으로 격리하는 최상위 단위입니다.
- **개별성:** 각 프로젝트나 공부 주제별로 독립된 영역(Scope)을 가집니다.
- **유연성:** 질의 시 특정 Scope만 지정하거나, 전체 Scope를 대상으로 통합 검색이 가능합니다.

---

## 4. 시스템 아키텍처 (System Architecture)

### 4.0. 핵심 원칙
- Deview는 **맥락의 저장과 검색**만 담당하는 독립 서버입니다.
- LLM 호출, 프롬프트 조립, 답변 생성은 클라이언트의 책임입니다.
- 특정 LLM 클라이언트에 종속되지 않는 **독립적(standalone) 서비스**입니다.
- **확정된 데이터만 수집:** 공용 브랜치에 머지된 커밋, 완료된 이슈, 발행된 문서 등 확정된 맥락만 저장합니다. 작업 중 개인 맥락은 LLM 클라이언트 자체 컨텍스트의 책임입니다.

### 4.1. 인터페이스 레이어 (Interface Layer)
```
Deview (standalone 서버)
  ├── MCP 인터페이스  → Claude Code, Cursor 등 LLM 클라이언트
  ├── REST API       → CI/CD, 리뷰 자동화, 커스텀 도구
  └── CLI            → 관리/디버깅용
```

### 4.2. Ingestion Layer (데이터 수집)
- **수집 조건:** 공용 브랜치에 머지된 커밋만 자동 수집. 외부 소스(Jira/Confluence)는 확정 상태(Done, Published)의 데이터만 수집.
- **Sources:** Git Logs (커밋 메시지 + diff + 주석 변경분), Markdown Documents, Manual Notes (Phase 1) / Confluence, Jira (Phase 2).
- **Chunking 단위:**

    | 소스 | 청크 단위 | 파일 연결 |
    | :--- | :--- | :--- |
    | Git commit | 커밋 1건 (메시지 + diff 요약 + author + 날짜) | 자동 (diff에서 파일 목록 추출) |
    | 코드 주석 변경 | Git diff에서 주석 변경분을 별도 청크로 분리 저장 | 자동 (변경된 파일 자체) |
    | Markdown | 헤딩(##) 기준 섹션 단위 | 자동 (파일 경로) |
    | Manual Note | 1회 저장 = 청크 1건 | 사용자 지정 (선택) |
    | Jira (Phase 2) | 이슈 1건 (제목 + 설명 + 댓글 요약) | 커밋 메시지의 이슈 키로 역방향 연결 |
    | Confluence (Phase 2) | 문서 1건 = 청크 1건 | 연결 없이 저장, 벡터 유사도 검색에 의존 |

- **Process:**
    1. 소스별 청크 단위로 분할.
    2. 해당 데이터에 `--scope` 태그 및 `file_paths` 메타데이터 부착.
    3. 임베딩 모델을 통해 벡터화.

### 4.3. Storage Layer (벡터 데이터베이스)
- **Engine:** ChromaDB (Phase 1, Local) → Qdrant (팀 배포 시)
- **Structure:** 단일 컬렉션 내에서 메타데이터 필터링을 통한 논리적 분리.
- **Schema:**
    - `id`: 고유 식별자 (UUID)
    - `vector`: 고차원 수치 배열
    - `content`: 원본 텍스트
    - `metadata`: `{ "scope": "project_a", "source": "git", "author": "kim", "file_paths": ["src/pages/Product/Button.tsx"], "jira_key": "PROJ-456", "timestamp": "2024-05-20" }`

### 4.4. Retrieval Layer (검색)
- **Search:** 사용자의 질문을 벡터화 후, 지정된 `scope` 내에서 유사도 검색(Cosine Similarity) 수행.
- **Response:** 검색된 상위 K개의 맥락을 클라이언트에 반환.
- 답변 생성(Generation)은 클라이언트의 LLM이 담당합니다.

---

## 5. 주요 기능 모듈 (Core Modules)

### 5.1. MCP Server
- LLM 클라이언트(Claude Code, Cursor 등)에서 자연스럽게 맥락을 검색할 수 있는 MCP 도구 제공.
- 사용자가 별도 명령 없이, LLM이 필요할 때 알아서 Deview를 호출.
- **MCP 도구:**
    - `deview_search`: 과거 의사결정의 이유, 프로젝트 컨벤션, 변경 히스토리, 특정 구현의 배경을 물을 때 맥락을 검색. scope 생략 시 전체 Scope 통합 검색. LLM이 도구 설명을 기반으로 자율 판단하여 호출.
    - `deview_write`: 사용자의 명시적 지시에 의해 맥락을 수동 저장. (자동 수집은 공용 브랜치 머지 시 서버 측에서 처리)
    - `deview_ingest`: 프로젝트의 Git 히스토리 또는 Markdown 문서를 인덱싱.
    - `deview_status`: 현재 Scope 정보, 인덱싱 상태 확인.
    - `deview_review` (Phase 4): PR diff를 분석하여 관련 맥락을 종합 반환.

### 5.2. REST API
- CI/CD 파이프라인, 리뷰 자동화 등 LLM 클라이언트 외의 환경에서 맥락에 접근.
- 팀 단위 배포 시 중앙 맥락 서버로 활용.

### 5.3. CLI (관리용)
- `deview init <scope_name>`: 새로운 영역 생성 및 초기화.
- `deview ingest <path> --scope <name>`: 특정 경로의 데이터를 지정된 영역에 저장.
- `deview query <text> --scope <name>`: 맥락 검색 (디버깅/테스트용).

---

## 6. 기술 스택 (Tech Stack)

| 분류 | 선택 | 이유 |
| :--- | :--- | :--- |
| **Language** | Python 3.10+ | 풍부한 AI/데이터 라이브러리 생태계 |
| **Vector DB** | **ChromaDB** (Phase 1) → **Qdrant** (팀 배포) | 로컬은 간편하게, 확장은 유연하게 |
| **데이터 커넥터** | **LlamaIndex 개별 reader 패키지** | 검증된 커넥터 활용 (코어 프레임워크 비의존) |
| **Embedding (기본)** | Voyage `voyage-3.5-lite` | 무료 200M 토큰, RAG 특화 |
| **Embedding (로컬 대안)** | BGE-large-en-v1.5 | 무료, 오프라인, 상용 수준 품질 |
| **Embedding (교체 가능)** | OpenAI, Mistral 등 | 설정으로 전환 가능한 추상화 구조 |
| **서버** | MCP SDK + FastAPI | MCP 인터페이스 + REST API |

> **참고:** LlamaIndex의 코어 프레임워크(파이프라인, 인덱스, 쿼리엔진)에는 의존하지 않습니다.
> `llama-index-readers-confluence` 등 개별 데이터 로더 패키지만 선택적으로 사용하며,
> 필요 시 언제든 자체 구현으로 교체할 수 있습니다.

---

## 7. 데이터 흐름 (Data Flow)

1. **저장 시:** `Raw Data` → `Connector (Reader)` → `Chunker` → `Embedder` → `Vector DB (with Scope Metadata)`
2. **질의 시:** `Client Query` → `Deview Server` → `Scope Filter` → `Vector Search` → `Context 반환` → `Client LLM이 답변 생성`

---

## 8. 로드맵 (Roadmap)
- **Phase 1 (mcp-ingest-query):** MCP 서버 기반의 기본 Ingest & Query 기능 구현 (ChromaDB + Voyage/BGE Embedding). Scope 자동 추론 (git remote URL/디렉토리명 기반). 임베딩 모델 교체 가능한 추상화 구조. 로컬 임베딩 모델 설치 가이드 포함.
- **Phase 2 (git-hook-rest-api):** Git Hook 연동 (공용 브랜치 머지 시 자동 인덱싱) + REST API + Jira/Confluence 커넥터 (CLI 수동 동기화).
- **Phase 3 (team-deploy):** 팀 배포 지원 (Qdrant 전환, 인증/권한) + PR 머지 Webhook 기반 자동 인덱싱. (Jira/Confluence 자동 동기화는 추후 확장)
- **Phase 4 (review-automation):** 리뷰 자동화 등 팀 협업 기능.
- **Phase 5 (ide-extension):** IDE 익스텐션 개발 및 UI 통합 (VS Code 먼저, JetBrains 이후).
- **Phase 6 (semantic-caching):** 시맨틱 캐싱 도입을 통한 API 호출 최적화.

---
**출처:**
- *Pinecone: Multi-tenancy with Vector Databases*
- *LlamaIndex: Metadata Extraction and Filtering Guide*
- *Architectural Decision Records (ADR) Pattern*
- *Model Context Protocol (MCP) Specification*
