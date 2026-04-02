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
