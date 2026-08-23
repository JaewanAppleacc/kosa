# TRAIL Frontend

고등학생이 관심 Context에서 답한 내용을 바탕으로 전공·과목을 함께 탐색하는 화면.

## 실행

```bash
npm install
npm run dev          # 기본값: Mock 모드 (백엔드 없이 전체 Flow가 돈다)
```

실제 API로 붙일 때는 FastAPI를 띄운 뒤 `.env.local`에서 모드만 바꾼다.

```bash
# 저장소 루트에서
./.venv/bin/uvicorn src.api.main:app --reload

# frontend/.env.local
VITE_API_MODE=live
```

FastAPI에 개발용 CORS 설정이 없어서 브라우저가 `127.0.0.1:8000`을 직접 부르지 않는다.
Vite dev proxy가 `/api/*` → `127.0.0.1:8000/*`로 넘긴다(`vite.config.ts`). 서버는 건드리지 않는다.

## 명령

| 명령 | 하는 일 |
|---|---|
| `npm run dev` | 개발 서버 |
| `npm run build` | 타입 검사 + production 빌드 |
| `npm run typecheck` | 타입 검사만 |
| `npm test` | 전체 테스트 |

`VITE_API_MODE=live npm run build`로 빌드하면 Mock Transport와 `outputs/mock_api` JSON이
번들에서 통째로 빠진다(`import.meta.env` 정적 치환 + 동적 import).

## 디자인

Claude Design 캔버스 초안(14화면: 6a~6f, 8a~8h)의 디자인 언어를 따른다.
토큰과 컴포넌트 규칙은 `src/styles/index.css` 한 곳에 모여 있다.

| 항목 | 값 |
|---|---|
| 포인트색 | `#0088b0` (청록). 자홍 `#d6006c`는 볼터치처럼 아주 조금만 |
| 서체 | Source Serif 4 (제목·본문 공통, 600/400) |
| 버튼 | 항상 필 모양, 기본 높이 52px |
| 라운드 | 카드 24px · 타일 20px · 선택지 18px |
| 그림자 | `0 2px 12px rgba(45,43,43,.07)` 한 단계만 |

로고는 승인된 스위치백 마크를 그대로 쓴다(`src/components/brand/Logo.tsx`). 초안의
"라인의 세 가지 쓰임"을 이 Path 하나로 소화한다 — `mode="draw"`(로고),
`mode="loop"`(로딩, 회전 스피너를 따로 두지 않는다), `mode="static"`(상단 바).
캐릭터나 얼굴은 쓰지 않는다.

## 구조

```
src/
  api/          API 계약(zod) · HTTP 클라이언트 · 오류 · Mock Transport
  config/       API 주소·모드 (여기 한 곳에서만 관리한다)
  session/      전역 세션 상태 · session_id 보관
  hooks/        비동기 상태(useAsync) · 중복 제출 방지(useAction)
  components/   공통 UI · 로고 · 오류 화면
  screens/      단계별 화면
  graph/        관계 그래프 렌더링 · Obsidian Export
```

## 지켜야 하는 규칙

이건 스타일 취향이 아니라 기획·계약상의 제약이다.

- **내부 점수를 화면에 쓰지 않는다.** 정성 Label(`관련성 높음` 등)만 노출한다.
  `relevance_level`(1~3)도 숫자가 아니라 선 굵기·투명도로만 표현한다.
- **유형 라벨을 만들지 않는다.** `CareerProfile.title`은 "~보여요" 형태의 관찰 문장이다.
  유형 뱃지·타입 카드 UI를 전제로 디자인하지 않는다.
- **진행률 퍼센트를 표시하지 않는다.** 질문 수가 Adaptive하게 달라져서 의미가 없다.
  현재 Context명과 완료한 질문 개수만 보여준다.
- **`user_id`를 사용자에게 입력받지 않는다.** 서버가 고정한다.
- **백엔드 계산을 화면에서 다시 하지 않는다.** 과목명 유사도 매칭, 전공 순위, Graph Edge
  생성은 전부 서버 몫이다. 화면은 받은 결과를 그리기만 한다.
- **`is_actually_offered`의 `null`을 `false`로 읽지 않는다.** 미확정과 미개설 확정은 다르다.
- **Context 목록을 프론트에 상수로 두지 않는다.** 항상 `fetchContextCatalog()`로 받는다.

## Context 선택 규칙 (서버가 강제하는 것)

`GET /contexts`의 `selection_policy`를 그대로 쓴다. 개수를 화면에 상수로 박지 않는다.

선호 Context로 고를 수 있는 건 **`assessment_supported`가 true이면서 이미 관심도를 매긴**
Context뿐이다. 둘 중 하나라도 아니면 서버가 422로 거부하므로, 화면에서 미리 선택 불가로 막는다.
최종 확정은 `final_context_min_count`~`final_context_max_count`(현재 2~3) 범위라, Contrast
제안을 받아들이지 않고 고른 2개로만 시작하는 흐름도 정상이다.
