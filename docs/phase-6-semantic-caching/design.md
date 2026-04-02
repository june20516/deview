# Phase 6: 시맨틱 캐싱 — 상세 설계

## 1. 목표

반복적인 임베딩 호출과 유사한 검색 요청의 비용/지연을 줄인다.
- 임베딩 결과 캐싱 (동일 텍스트 재호출 방지)
- 검색 결과 캐싱 (유사 질문의 결과 재사용)

---

## 2. 임베딩 캐싱

### 2.1. 동작

```
embed("공용 버튼 커스텀 구현")
  → 캐시 확인 (텍스트 해시 기반)
  → 캐시 히트: 저장된 벡터 반환
  → 캐시 미스: API 호출 → 결과 캐싱 → 벡터 반환
```

### 2.2. 캐시 키

- 텍스트의 SHA-256 해시 + provider 이름 + 모델명
- 동일 텍스트라도 모델이 다르면 별도 캐싱

### 2.3. 저장소

- 로컬: SQLite (간단한 key-value)
- 팀 배포: Redis 또는 Qdrant의 별도 컬렉션

### 2.4. 효과

- Git 히스토리 재인덱싱 시 변경되지 않은 커밋의 임베딩을 재호출하지 않음
- 대규모 인덱싱 시 비용 절감

---

## 3. 검색 결과 캐싱

### 3.1. 동작

```
search("왜 커스텀 버튼을 썼어?")
  → 질문 임베딩 생성
  → 캐시에서 유사 질문 검색 (코사인 유사도 ≥ 0.95)
  → 캐시 히트: 이전 검색 결과 반환
  → 캐시 미스: 벡터 DB 검색 → 결과 캐싱 → 반환
```

### 3.2. 유사도 판단

- 질문 임베딩 간 코사인 유사도 ≥ 0.95를 캐시 히트로 판단
- 임계값은 설정으로 조정 불가 (고정값)

### 3.3. 캐시 무효화

- 새로운 데이터가 인덱싱되면 해당 scope의 검색 캐시 전체 무효화
- TTL 기반 만료 (기본 24시간)

---

## 4. 설정

```yaml
cache:
  enabled: true
  embedding:
    backend: "sqlite"          # sqlite | redis
    max_entries: 100000
  search:
    backend: "sqlite"          # sqlite | redis
    ttl_hours: 24
    similarity_threshold: 0.95
  redis:                       # redis 사용 시
    url: "${REDIS_URL}"
```

---

## 5. 캐시 관리 CLI

```bash
deview cache status            # 캐시 히트율, 크기 등 통계
deview cache clear             # 전체 캐시 삭제
deview cache clear --scope X   # 특정 scope 캐시만 삭제
```

---

## 6. 구현 방식

- 임베딩 추상 인터페이스(`EmbeddingProvider`)를 래핑하는 `CachedEmbeddingProvider` 데코레이터
- 기존 코드 변경 최소화 — 캐싱 레이어만 추가

```python
class CachedEmbeddingProvider(EmbeddingProvider):
    def __init__(self, inner: EmbeddingProvider, cache: CacheBackend):
        self._inner = inner
        self._cache = cache

    def embed(self, texts: list[str]) -> list[list[float]]:
        results = []
        uncached_texts = []
        uncached_indices = []

        for i, text in enumerate(texts):
            cached = self._cache.get(text)
            if cached is not None:
                results.append((i, cached))
            else:
                uncached_texts.append(text)
                uncached_indices.append(i)

        if uncached_texts:
            new_embeddings = self._inner.embed(uncached_texts)
            for idx, emb in zip(uncached_indices, new_embeddings):
                self._cache.set(texts[idx], emb)
                results.append((idx, emb))

        results.sort(key=lambda x: x[0])
        return [r[1] for r in results]
```
