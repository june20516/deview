# Phase 2: Git Hook + REST API + 외부 커넥터 — 상세 설계

## 1. 목표

Phase 1의 수동 인덱싱을 자동화하고, MCP 외의 환경에서도 Deview에 접근할 수 있게 한다.
- 공용 브랜치 머지 시 자동 인덱싱 (post-merge hook)
- REST API로 전체 기능 노출
- Jira/Confluence CLI 수동 동기화
- `deview` CLI 도구 제공

---

## 2. Git Hook 자동 인덱싱

### 2.1. 트리거

- **post-merge hook**: 로컬에서 `git merge` 또는 `git pull` 시 동작
- 설정된 `target_branch`에 대한 머지일 때만 인덱싱 실행
- Phase 3에서 CI/CD webhook 기반으로 확장

### 2.2. 동작 흐름

```
git pull / git merge
  → post-merge hook 실행
  → 마지막 인덱싱 이후 새로 추가된 커밋만 증분 인덱싱
  → Deview 서버에 ingest 요청 (REST API 또는 직접 호출)
```

### 2.3. Hook 설치

```bash
deview hook install    # .git/hooks/post-merge 에 hook 스크립트 생성
deview hook uninstall  # hook 제거
```

---

## 3. REST API

### 3.1. 설계 원칙

- MCP 도구와 동일한 기능을 HTTP로 노출
- MCP를 사용할 수 없는 환경(CI/CD, 스크립트, 커스텀 도구)을 위한 대안 경로
- 간단한 API 키 인증 (Phase 3에서 OAuth 확장 가능한 구조)

### 3.2. 엔드포인트

| Method | Path | MCP 대응 | 설명 |
|:---|:---|:---|:---|
| POST | `/api/v1/search` | deview_search | 맥락 검색 |
| POST | `/api/v1/write` | deview_write | 수동 맥락 저장 |
| POST | `/api/v1/ingest` | deview_ingest | 인덱싱 실행 |
| GET | `/api/v1/status` | deview_status | 상태 조회 |
| POST | `/api/v1/sync` | (신규) | 외부 소스 동기화 |

### 3.3. 인증

```
Authorization: Bearer <api-key>
```

- API 키는 `.deview.yaml` 또는 환경변수 `DEVIEW_API_KEY`로 설정
- localhost 접근 시에도 인증 필요 (구조를 미리 잡아둠)
- Phase 3에서 OAuth/SSO로 확장

---

## 4. 외부 커넥터

### 4.1. Jira 커넥터

```bash
deview sync --source jira --project PROJ
```

- **수집 대상:** 상태가 Done/Closed인 이슈만
- **청크 단위:** 이슈 1건 (제목 + 설명 + 댓글 요약)
- **파일 연결:** 커밋 메시지의 이슈 키(PROJ-123)로 역방향 연결
- **인증:** Jira API 토큰 (`.deview.yaml`의 `integrations.jira` 섹션)

### 4.2. Confluence 커넥터

```bash
deview sync --source confluence --space DEV
```

- **수집 대상:** 발행된(Published) 문서
- **청크 단위:** 문서 1건 = 청크 1건
- **파일 연결:** 없음 — 벡터 유사도 검색에 의존
- **인증:** Confluence API 토큰 (`.deview.yaml`의 `integrations.confluence` 섹션)

### 4.3. 설정 확장

```yaml
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

---

## 5. CLI 도구

### 5.1. 명령어 구조

```bash
deview status                           # 상태 조회
deview search "질문" [--scope name]     # 맥락 검색
deview ingest <path> [--scope name]     # 수동 인덱싱
deview sync --source jira|confluence    # 외부 소스 동기화
deview hook install|uninstall           # Git hook 관리
deview server start|stop               # REST API 서버 관리
```

### 5.2. 구현

- `click` 또는 `typer` 라이브러리 사용
- `pyproject.toml`의 `[project.scripts]`로 `deview` 명령어 등록

---

## 6. 추가 의존성

| 패키지 | 용도 |
|:---|:---|
| `fastapi` | REST API 서버 |
| `uvicorn` | ASGI 서버 |
| `typer` | CLI 프레임워크 |
| `atlassian-python-api` 또는 `llama-index-readers-confluence/jira` | Jira/Confluence 연동 |
