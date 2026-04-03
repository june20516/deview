# Phase 2: 증분 인덱싱 + 외부 커넥터 + Git Hook + CLI — 상세 설계

## 1. 목표

Phase 1의 수동 전체 인덱싱을 자동화·효율화하고, 코드 외부의 의사결정 맥락을 수집한다.
- 증분 인덱싱 (Git, Jira, Confluence 공통)
- 외부 커넥터 (Jira/Confluence)로 코드 밖 의사결정 수집
- Git post-merge hook으로 자동 인덱싱
- `deview` CLI 도구 제공

> **Phase 3으로 이동한 항목:** MCP 원격 전송(SSE/Streamable HTTP), REST API — 팀 배포 시점에 구현.

---

## 2. 증분 인덱싱

### 2.1. 공통 패턴

모든 데이터 소스(Git, Jira, Confluence)에 동일한 증분 전략을 적용한다:

```
1. DB에서 해당 scope + source의 최신 timestamp 조회
2. 해당 시점 이후 변경분만 소스에서 가져옴
3. upsert로 저장 (기존 항목은 덮어씀, 신규 항목은 추가)
```

- 별도 상태 파일 불필요 — DB 자체가 "어디까지 했는지"의 기록
- 최초 실행 시(DB에 데이터 없음)는 전체 인덱싱과 동일하게 동작

### 2.2. Git 증분 인덱싱

```
1. store에서 scope의 git 소스 중 최신 commit_hash 조회
2. git log에서 해당 커밋 이후의 새 커밋만 추출
3. 새 커밋만 임베딩 → upsert
```

- `commit_hash`가 없으면(최초) 전체 히스토리 인덱싱
- 기존 Phase 1의 `parse_git_history`에 `since_commit` 파라미터 추가

### 2.3. Jira 증분 동기화

```
1. store에서 scope의 jira 소스 중 최신 timestamp 조회
2. Jira API: updated >= "해당 날짜" 필터로 변경된 이슈만 조회
3. upsert로 저장 (이슈 내용/댓글이 변경되었으면 덮어씀)
```

### 2.4. Confluence 증분 동기화

```
1. store에서 scope의 confluence 소스 중 최신 timestamp 조회
2. Confluence API: lastModified >= "해당 날짜" 필터로 변경된 문서만 조회
3. upsert로 저장
```

### 2.5. ChromaStore 확장

증분 인덱싱을 지원하기 위해 `ChromaStore`에 메서드 추가:

```python
def get_latest_commit_hash(self, scope: str) -> str | None:
    """scope의 git 소스 중 가장 최근 commit_hash를 반환한다."""

def get_latest_timestamp(self, scope: str, source: str) -> str | None:
    """scope + source 조합의 최신 timestamp를 반환한다."""
```

---

## 3. 외부 커넥터

### 3.1. Jira 커넥터

```bash
deview sync --source jira --project PROJ
```

- **수집 대상:** 상태가 Done/Closed인 이슈만
- **청크 단위:** 이슈 1건 (제목 + 설명 + 전체 댓글)
- **파일 연결:** 커밋 메시지의 이슈 키(PROJ-123)로 역방향 연결
- **인증:** Jira API 토큰 (글로벌 설정 `~/.deview/config.yaml`)

**청크 content 예시:**

```
[PROJ-123] API 응답 포맷 통일

설명:
현재 각 API 엔드포인트마다 응답 포맷이 달라서 프론트에서 처리가 복잡합니다.
공통 응답 래퍼를 만들어서 통일합니다.

댓글:
[2025-03-15 김철수] 기존 API 호환성 때문에 v2 엔드포인트로 분리하는게 낫지 않을까요?
[2025-03-16 이영희] v2로 분리하면 유지보수 포인트가 늘어나서, 기존 API에 래퍼를 씌우는 방향으로 결정했습니다.
[2025-03-17 김철수] 확인했습니다. ErrorResponse도 같은 포맷으로 통일해주세요.
```

**metadata:**

```python
{
    "scope": "team/my-project",
    "source": "jira",
    "author": "이영희",  # 이슈 담당자
    "jira_key": "PROJ-123",
    "file_paths": "[]",  # 커밋 연결 시 역방향으로 채워짐
    "timestamp": "2025-03-17",  # 이슈 최종 업데이트일
}
```

### 3.2. Confluence 커넥터

```bash
deview sync --source confluence --space DEV
```

- **수집 대상:** 발행된(Published) 문서
- **청크 단위:** 문서를 적절한 크기로 분할하되, 관련 청크를 그루핑
- **파일 연결:** 없음 — 벡터 유사도 검색에 의존
- **인증:** Confluence API 토큰 (글로벌 설정 `~/.deview/config.yaml`)

**청킹 전략:**

긴 문서는 분할하되, 짧은 문서는 그대로 유지한다:

```
1. 문서 전체 길이 확인
2. 임계값(예: 2000자) 이하 → 문서 전체를 하나의 청크로
3. 임계값 초과 → 헤딩(h1~h3) 기준으로 섹션 분할
4. 분할된 청크에 document_id를 공통 메타데이터로 부여하여 그루핑
```

**metadata:**

```python
{
    "scope": "team/my-project",
    "source": "confluence",
    "author": "박지민",  # 문서 작성자
    "document_id": "confluence-12345",  # 같은 문서의 청크끼리 그루핑
    "document_title": "API 설계 가이드",
    "section": "## 3. 에러 핸들링",  # 분할된 경우 섹션 헤딩
    "file_paths": "[]",
    "timestamp": "2025-10-15",
}
```

### 3.3. 설정 확장

글로벌 설정(`~/.deview/config.yaml`)에 추가:

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

## 4. Git Hook 자동 인덱싱

### 4.1. 트리거

- **post-merge hook**: 로컬에서 `git merge` 또는 `git pull` 시 동작
- 설정된 `target_branch`에 대한 머지일 때만 인덱싱 실행
- Phase 3에서 CI/CD webhook 기반으로 확장

### 4.2. 동작 흐름

```
git pull / git merge
  → post-merge hook 실행
  → 증분 인덱싱 (마지막 인덱싱 이후 새 커밋만)
  → deview CLI를 통해 ingest 호출
```

### 4.3. Hook 설치

```bash
deview hook install    # .git/hooks/post-merge 에 hook 스크립트 생성
deview hook uninstall  # hook 제거
```

### 4.4. Hook 스크립트

```bash
#!/bin/sh
# Deview post-merge hook
# 증분 인덱싱 실행 (백그라운드, 실패해도 merge를 막지 않음)
deview ingest --incremental &
```

---

## 5. CLI 도구

### 5.1. 명령어 구조

```bash
deview status                           # 상태 조회
deview search "질문" [--scope name]     # 맥락 검색
deview ingest [--scope name] [--incremental]  # 인덱싱 (기본: 증분)
deview sync --source jira|confluence    # 외부 소스 동기화
deview hook install|uninstall           # Git hook 관리
```

### 5.2. 구현

- `typer` 라이브러리 사용
- `pyproject.toml`의 `[project.scripts]`로 `deview` 명령어 등록
- 내부적으로 Phase 1의 동일한 모듈(store, embedding, ingestion) 재사용

---

## 6. 추가 의존성

| 패키지 | 용도 |
|:---|:---|
| `typer` | CLI 프레임워크 |
| `atlassian-python-api` | Jira/Confluence API 연동 |
