# Phase 3: 팀 배포 — 상세 설계

## 1. 목표

Deview를 팀 공유 인프라로 배포하여, 같은 프로젝트를 작업하는 모든 팀원이 동일한 맥락 저장소를 사용한다.
- Docker 컨테이너 배포
- ChromaDB → Qdrant 전환 (프로덕션 벡터 DB)
- 인증/권한 체계
- CI/CD webhook 기반 자동 인덱싱

---

## 2. 배포 형태

### 2.1. Docker Compose 구성

```yaml
services:
  deview:
    image: deview:latest
    ports:
      - "8080:8080"     # MCP (SSE/Streamable HTTP) + REST API
    environment:
      - DEVIEW_DB_URL=qdrant:6333
    depends_on:
      - qdrant

  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage

volumes:
  qdrant_data:
```

### 2.2. Dockerfile

- Python 3.10+ slim 이미지 기반
- `uv` 사용한 의존성 설치
- MCP 원격 서버(SSE/Streamable HTTP) + REST API 서버 실행

### 2.3. 인터페이스 우선순위

- **MCP (기본):** LLM 클라이언트(Claude Code, Cursor 등)는 원격 MCP로 팀 서버에 접속. 로컬/원격 동일한 인터페이스.
- **REST API (보조):** CI/CD, webhook, 스크립트 등 MCP를 사용할 수 없는 환경용.

---

## 3. Qdrant 전환

### 3.1. Storage 추상화

Phase 1의 `ChromaStore`와 동일한 인터페이스의 `QdrantStore` 구현.
설정으로 전환 가능:

```yaml
storage:
  engine: "qdrant"          # chroma | qdrant
  qdrant:
    url: "http://qdrant:6333"
    api_key: "${QDRANT_API_KEY}"  # Qdrant Cloud 사용 시
```

### 3.2. 데이터 마이그레이션

```bash
deview migrate --from chroma --to qdrant
```

- 기존 ChromaDB 데이터를 읽어서 Qdrant에 재저장
- 임베딩 벡터를 그대로 이전 (재임베딩 불필요)
- 마이그레이션 진행률 표시

---

## 4. 인증/권한

### 4.1. Phase 3 범위

- API 키 기반 인증 (Phase 2에서 구현한 구조 확장)
- 개인별 API 키 발급 기능
- 키별 권한 수준: `read` | `write` | `admin`

### 4.2. 추후 확장 구조

- OAuth/SSO 연동을 위한 인증 미들웨어 추상화
- Phase 3에서는 API 키만 구현하되, 인터페이스는 교체 가능하게

```python
class AuthProvider(ABC):
    @abstractmethod
    async def authenticate(self, request) -> User: ...

class ApiKeyAuth(AuthProvider): ...       # Phase 3
class OAuthAuth(AuthProvider): ...        # 추후
```

---

## 5. CI/CD Webhook

### 5.1. 지원 이벤트

- **PR 머지** (공용 브랜치에 머지된 커밋 자동 인덱싱)
- GitHub, GitLab 지원

### 5.2. 엔드포인트

```
POST /api/v1/webhook/github
POST /api/v1/webhook/gitlab
```

### 5.3. 동작 흐름

```
GitHub PR 머지 → webhook 발송 → Deview 수신
  → 머지 커밋 식별 → 증분 인덱싱
  → Jira 이슈 키 추출 → 기존 Jira 청크에 file_paths 역방향 연결
```

### 5.4. Webhook Secret

```yaml
webhooks:
  github:
    secret: "${GITHUB_WEBHOOK_SECRET}"
  gitlab:
    secret: "${GITLAB_WEBHOOK_SECRET}"
```

---

## 6. 설정 확장

```yaml
storage:
  engine: "qdrant"
  qdrant:
    url: "http://qdrant:6333"

auth:
  type: "api_key"           # api_key | oauth (추후)
  keys:
    - key: "${DEVIEW_ADMIN_KEY}"
      role: "admin"
    - key: "${DEVIEW_READ_KEY}"
      role: "read"

webhooks:
  github:
    secret: "${GITHUB_WEBHOOK_SECRET}"
```
