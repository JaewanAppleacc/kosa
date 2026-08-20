# B 작업자 핸드오프 번들 — 2026-08-21 (base commit `0110f07`)

이 폴더 하나로 독립 실행됩니다. 전체 저장소를 clone할 필요 없습니다. (단, 이건 특정 시점 스냅샷이라 이후 변경사항은 못 받습니다 — 최신 상태가 필요하면 `https://github.com/JaewanAppleacc/kosa.git` 전체를 보세요.)

**시작 전에 `작업자_B_개발_지시서.md`와 `CLAUDE.md`를 먼저 읽어주세요** — 담당 범위·소유권·완료 조건 전체가 거기 있고, 이 README는 API 계약 사용법만 다룹니다.

## 1. 실행 (Python 3.11~3.13, 버전 고정 설치)

```bash
cd handoff_B
python3.13 -m venv .venv        # 3.11~3.13이면 됩니다. 3.14는 검증 안 됨 — 쓰지 마세요.
./.venv/bin/pip install -r requirements.txt
./.venv/bin/uvicorn src.api.main:app --reload
```

`http://127.0.0.1:8000/docs`에서 실제 동작하는 API 문서를 바로 확인할 수 있습니다.

서버 안 띄우고 정적 파일만 보고 싶으면 `mock_api/` 폴더를 바로 여세요.

## 2. 폴더 구성

```
handoff_B/
├ README.md                      (이 파일 — API 계약 사용법)
├ CLAUDE.md                       B 전용 구현 지침(소유권·불변식·반환 방법)
├ 작업자_B_개발_지시서.md          담당 범위 전체
├ requirements.txt                버전 고정된 의존성
├ mock_api/                       23개 정상·오류·빈결과·Fallback상태 JSON + openapi.json
└ src/
   ├ api/main.py                  실제 동작하는 FastAPI 앱
   ├ api/mock_data.py             Mock 데이터 생성 로직
   ├ memory/session_store.py      In-Memory 세션 저장소(임시, DB 아님)
   ├ ids.py                       ID 생성 규칙
   └ schemas/                     모든 API 요청·응답 타입 (api.py가 핵심)
```

## 3. 지금 뭐가 진짜로 되고, 뭐가 Mock인지

| 단계 | 실제 동작 여부 |
|---|---|
| 세션 생성 / 관심도 평가 / Context 선택·확정 | ✅ 실제 상태 저장·조회 (In-Memory — 서버 재시작하면 날아감) |
| 과목 파일 업로드(`/course/upload`) | ✅ 실제 `multipart/form-data` 파일을 받고 형식(PDF/Excel)을 검증함. 파싱 결과 자체는 Mock |
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
| POST | `/course/upload` | 학교 PDF·Excel 업로드 — **`multipart/form-data`**, `session_id`(Form) + `file`(File) |
| POST | `/course/confirm` | 파싱된 과목 후보 확인·확정 |
| GET | `/subgraph/{session_id}` | 관계 그래프 |
| GET | `/session/{session_id}` | Session 복원 |

`/course/upload` 예시 (curl):
```bash
curl -X POST http://127.0.0.1:8000/course/upload \
  -F "session_id=sess_xxx" \
  -F "file=@curriculum.pdf;type=application/pdf"
```
PDF(`application/pdf`), Excel(`.xlsx`/`.xls`) 외 형식은 422와 `VALIDATION_ERROR`를 반환합니다.

## 5. 화면에서 그대로 써야 하는 상태값

**질문 로딩/Fallback 상태** (`NextQuestionResponse.status`):
`GENERATED` / `REGENERATING` / `CACHE_USED` / `BACKUP_USED` / `CONTEXT_EARLY_TERMINATED`

지금 서버는 `GENERATED`만 실제로 반환합니다(§11 Fallback 로직 미구현). 나머지 4개 상태의 응답 형태는 `mock_api/next_question_*__hand_crafted.json`에서 미리 확인하세요 — 화면은 지금 만들어도 됩니다.

**오류 코드** (404/422 등 에러 응답의 `detail.error_code`):
`VALIDATION_ERROR` / `SESSION_NOT_FOUND` / `LLM_UNAVAILABLE` / `LANGSMITH_UNAVAILABLE` / `INTERNAL_ERROR`

`LLM_UNAVAILABLE` 예시는 `mock_api/error_llm_unavailable__hand_crafted.json` 참고(아직 서버가 실제로 던지진 않음).

**전공 관련도 Label** (`MajorRelevance.relevance_label` — 숫자 필드 자체가 없음):
`"관련성 높음"` / `"함께 탐색해볼 분야"` / `"비교해볼 만한 분야"`

**Evidence 충분성** (`MajorRelevance.evidence_sufficiency`):
`"충분"` / `"보통"` / `"제한적"`

**부분 결과(Evidence 부족) Profile 예시**: `mock_api/profile_partial__hand_crafted.json` — highlights 일부가 "아직 부족해요" 같은 문구인 경우 화면이 어떻게 보여야 하는지 참고하세요.

## 6. 알아둘 것

- `/assessment/session`은 `user_id`를 입력받지 않습니다(보안상 서버 고정) — 화면에서 사용자가 이 값을 입력하게 만들지 마세요.
- 내부 점수(84%, 0.67 같은 숫자)를 노출하는 API는 없습니다. 정성 Label만 옵니다.
- 파일명에 `__hand_crafted`가 붙은 Mock은 실제 서버 응답이 아니라, 아직 서버가 도달 못 하는 상태를 미리 보여주기 위해 손으로 만든 예시입니다. 형태는 신뢰해도 되지만 "이 요청을 보내면 이 응답이 온다"는 아닙니다.

## 7. 작업 반환 시

- B가 만든 `frontend/`, `ui/`, `src/graph/obsidian_exporter.py`, `frontend tests/`만 반환하세요. 이 번들에 참고용으로 들어있는 `src/schemas/`, `src/api/` 등은 수정했더라도 반환하지 않습니다(A가 최신 버전을 갖고 있음).
- Base commit `0110f07` 기준으로 작업했다는 걸 커밋 메시지나 PR 설명에 남겨주세요.
- 문제 발견 시 이 폴더의 코드를 직접 고치지 말고, 재현 가능한 요청/응답과 함께 A에게 전달해주세요.

## 참고 문서

- `작업자_B_개발_지시서.md`, `CLAUDE.md` — 이 폴더에 포함됨
- 최신 저장소: `https://github.com/JaewanAppleacc/kosa.git`
