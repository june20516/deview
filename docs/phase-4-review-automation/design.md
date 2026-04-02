# Phase 4: 리뷰 자동화 — 상세 설계

## 1. 목표

PR 리뷰 시 Deview에 축적된 맥락을 활용하여, 리뷰어가 더 정확하고 빠른 판단을 내릴 수 있도록 보조한다.
- PR diff 기반 관련 맥락 자동 수집 도구 (`deview_review`)
- 리뷰어의 MCP 클라이언트를 통한 질의 보조

---

## 2. 핵심 기능: `deview_review` MCP 도구

### 2.1. 역할

PR diff를 입력받아, 변경된 파일/코드와 관련된 맥락을 한번에 모아서 반환한다.
리뷰어가 개별 `deview_search`를 여러 번 호출할 필요 없이, 리뷰에 필요한 맥락을 한 호출로 얻는다.

### 2.2. 도구 스펙

```
tool: deview_review

description: "PR diff를 분석하여 관련 맥락을 종합적으로 반환합니다.
변경된 파일의 과거 의사결정, 컨벤션, 유사 변경 이력을 한번에 제공합니다.
PR 리뷰 시 호출하세요."

parameters:
  diff: string (필수) — PR diff 텍스트 또는 커밋 해시
  scope: string (선택)

returns:
  files_analyzed: [string]        # 분석된 파일 목록
  contexts: [
    {
      file_path: string,          # 관련 파일
      category: string,           # "convention" | "decision" | "history" | "risk"
      content: string,            # 맥락 원문
      source: string,
      timestamp: string,
      relevance_score: float
    }
  ]
```

### 2.3. 맥락 수집 로직

```
1. diff에서 변경된 파일 목록 추출
2. 파일별로 deview_search 수행:
   a. 해당 파일의 과거 의사결정 (decision)
   b. 관련 컨벤션/패턴 (convention)
   c. 유사한 과거 변경 이력 (history)
   d. 과거 실패/장애 관련 기록 (risk)
3. 결과를 카테고리별로 분류하여 반환
```

---

## 3. 사용 흐름

```
리뷰어 (Claude Code / Cursor 등):
  "이 PR을 리뷰하려는데, 관련 맥락을 알려줘"

LLM 클라이언트:
  → deview_review 호출 (diff 전달)
  ← 파일별 맥락 반환

LLM 클라이언트:
  "Button.tsx는 2025년 11월에 공용컴포넌트 미지원으로 커스텀 구현된 이력이 있습니다.
   이번 변경이 그 결정과 충돌하지 않는지 확인이 필요합니다.
   또한 이 프로젝트의 에러 핸들링 컨벤션은 ... 입니다."
```

---

## 4. 추가 의존성

- 기존 모듈을 조합하므로 새로운 외부 의존성 없음
- `deview_search`의 내부 로직을 재사용
