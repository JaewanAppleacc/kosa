# B 작업자 핸드오프 번들 — 2026-08-21

이 폴더 하나로 독립 실행됩니다. 전체 저장소를 clone할 필요 없습니다. (단, 이건 특정 시점 스냅샷이라 이후 변경사항은 못 받습니다 — 최신 상태가 필요하면 `https://github.com/JaewanAppleacc/kosa.git` 전체를 보세요.)

## 1. 실행

```bash
cd handoff_B
python3 -m venv .venv
./.venv/bin/pip install fastapi uvicorn pydantic
./.venv/bin/uvicorn src.api.main:app --reload
```

`http://127.0.0.1:8000/docs`에서 실제 동작하는 API 문서를 바로 확인할 수 있습니다.

서버 안 띄우고 정적 파일만 보고 싶으면 `mock_api/` 폴더를 바로 여세요.

## 2. 폴더 구성

```
handoff_B/
├ README.md               (이 파일)
├ mock_api/                14개 정상·오류·빈 결과 JSON + openapi.json
└ src/
   ├ api/main.py            실제 동작하는 FastAPI 앱 (18개 route: 14개 Endpoint + Swagger UI 등)
   ├ api/mock_data.py        Mock 데이터 생성 로직
   ├ memory/session_store.py In-Memory 세션 저장소(임시, DB 아님)
   ├ ids.py                  ID 생성 규칙
   └ schemas/                모든 API 요청·응답 타입 (api.py가 핵심)
```

## 3. 지금 뭐가 진짜로 되고, 뭐가 Mock인지

| 단계 | 실제 동작 여부 |
|---|---|
| 세션 생성 / 관심도 평가 / Context 선택·확정 | ✅ 실제 상태 저장·조회 (In-Memory — 서버 재시작하면 날아감) |
| 다음 질문 받기 / 답변 제출 | ⚠️ 응답 형태는 최종본, 내용은 고정 Mock |
| Profile / Majors / Departments / Subjects / Subgraph 조회 | ⚠️ 전부 고정 Mock |

Mock을 실제 값으로 바꿔도 응답 Schema(필드 이름·타입)는 유지되도록 설계했으니 지금 화면을 만들어도 나중에 크게 안 깨집니다.

## 4. Endpoint 목록

| Method | Path | 용도 |
|---|---|---|
| POST | `/assessment/session` | 세션 생성 (user_id는 서버가 demo_user_01로 자동 고정) |
| POST | `/assessment/interest-rating` | 15개 Context 관심도(1~5) 제출 |
| POST | `/assessment/context-select` | 선호 Context 4개 제출 → Contrast Context 제안받음 |
| POST | `/assessment/context-confirm` | 최종 Context 확정 (Vertical Slice는 3개: game/media/school_life) |
| POST | `/assessment/next-question` | 다음 질문 받기 |
| POST | `/assessment/answer` | 답변 제출 |
| GET | `/profile/{session_id}` | Career Profile 결과 카드 |
| GET | `/majors/{session_id}` | 전공 관련도 목록 |
| GET | `/departments/{major_id}` | 실제 학과 목록 |
| GET | `/subjects/{session_id}` | 과목 추천 결과 |
| POST | `/course/upload` | 학교 PDF·Excel 업로드 |
| POST | `/course/confirm` | 파싱된 과목 후보 확인·확정 |
| GET | `/subgraph/{session_id}` | 관계 그래프 |
| GET | `/session/{session_id}` | Session 복원 |

## 5. 화면에서 그대로 써야 하는 상태값

**질문 로딩/Fallback 상태** (`NextQuestionResponse.status`):
`GENERATED` / `REGENERATING` / `CACHE_USED` / `BACKUP_USED` / `CONTEXT_EARLY_TERMINATED`

**오류 코드** (404 등 에러 응답의 `detail.error_code`):
`VALIDATION_ERROR` / `SESSION_NOT_FOUND` / `LLM_UNAVAILABLE` / `LANGSMITH_UNAVAILABLE` / `INTERNAL_ERROR`

**전공 관련도 Label** (`MajorRelevance.relevance_label` — 숫자 필드 자체가 없음):
`"관련성 높음"` / `"함께 탐색해볼 분야"` / `"비교해볼 만한 분야"`

**Evidence 충분성** (`MajorRelevance.evidence_sufficiency`):
`"충분"` / `"보통"` / `"제한적"`

## 6. 알아둘 것

- `/assessment/session`은 `user_id`를 입력받지 않습니다(보안상 서버 고정) — 화면에서 사용자가 이 값을 입력하게 만들지 마세요.
- 내부 점수(84%, 0.67 같은 숫자)를 노출하는 API는 없습니다. 정성 Label만 옵니다.
- 문제 발견 시 이 폴더의 코드를 직접 고치지 말고, 재현 가능한 요청/응답과 함께 A에게 전달해주세요.
