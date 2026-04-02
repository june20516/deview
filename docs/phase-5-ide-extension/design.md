# Phase 5: IDE 익스텐션 — 상세 설계

## 1. 목표

VS Code 및 JetBrains IDE에서 Deview를 시각적으로 활용할 수 있게 한다.
- 에디터 내 인라인 맥락 표시
- 전용 사이드바/툴 윈도우 패널
- 두 플랫폼 모두 동일한 REST API를 사용하므로 기능 패리티 유지

---

## 2. 에디터 UI 통합

### 2.1. 인라인 맥락 표시

- 파일/함수 위에 CodeLens로 "맥락 보기" 버튼 표시
- 클릭 시 해당 코드와 관련된 Deview 맥락을 팝업/인라인으로 표시
- 맥락이 있는 코드 영역에 거터 아이콘(gutter icon) 표시

### 2.2. 호버 정보

- 코드 위에 마우스를 올리면 관련 맥락 요약을 툴팁으로 표시
- 전체 보기 링크로 사이드바 패널 연결

### 2.3. 컨텍스트 메뉴

- 코드 선택 후 우클릭 → "Deview: 이 코드의 맥락 검색"
- 코드 선택 후 우클릭 → "Deview: 이 결정을 기록"

---

## 3. 사이드바 패널

### 3.1. 검색 탭

- 자유 텍스트 검색
- 현재 열린 파일 기반 자동 검색
- 검색 결과를 타임라인/카드 형태로 표시
- 결과에서 관련 커밋/파일로 바로 이동

### 3.2. 상태 탭

- 현재 scope 정보
- 인덱싱 상태 (청크 수, 소스별 분포, 마지막 인덱싱)
- 인덱싱 실행 버튼

### 3.3. 히스토리 탭

- 현재 파일의 맥락 변화를 시간순으로 표시
- 과거 의사결정 타임라인

---

## 4. 기술 구현

### 4.1. 통신 방식

- Deview REST API를 호출 (Phase 2에서 구현)
- 또는 로컬 MCP 서버에 직접 연결

### 4.2. 기술 스택

**VS Code:**

| 구분 | 선택 |
|:---|:---|
| 언어 | TypeScript |
| UI | VS Code Webview API (사이드바) + CodeLens API (인라인) |
| 빌드 | esbuild |
| 배포 | VS Code Marketplace |

**JetBrains (IntelliJ, WebStorm 등):**

| 구분 | 선택 |
|:---|:---|
| 언어 | Kotlin |
| UI | Tool Window (사이드바) + Inlay Hints (인라인) |
| 빌드 | Gradle + IntelliJ Platform Plugin |
| 배포 | JetBrains Marketplace |

### 4.3. 공통 로직

두 플랫폼 모두 Deview REST API를 호출하므로, API 클라이언트 로직은 동일합니다. IDE별 차이는 UI 레이어뿐입니다.

```
[VS Code 익스텐션]   ──→  Deview REST API  ←──  [JetBrains 플러그인]
     TypeScript                                      Kotlin
     CodeLens                                        Inlay Hints
     Webview                                         Tool Window
```

### 4.4. 설정

**VS Code** — settings.json:
```json
{
  "deview.serverUrl": "http://localhost:8080",
  "deview.apiKey": "",
  "deview.autoSearch": true,
  "deview.showCodeLens": true,
  "deview.showGutterIcons": true
}
```

**JetBrains** — Settings > Tools > Deview:
```
Server URL: http://localhost:8080
API Key: ****
Auto Search: ✅
Show Inlay Hints: ✅
Show Gutter Icons: ✅
```

---

## 5. 우선순위

**Phase 5a: VS Code (먼저)**
1. 사이드바 검색/상태 패널
2. CodeLens "맥락 보기" 버튼
3. 컨텍스트 메뉴
4. 호버 툴팁
5. 거터 아이콘

**Phase 5b: JetBrains (이후)**
1. Tool Window 검색/상태 패널
2. Inlay Hints "맥락 보기"
3. 컨텍스트 메뉴
4. 호버 툴팁
5. 거터 아이콘
