# B 작업자 핸드오프 — 2026-08-21

이 저장소(`kosa`)를 clone하면 바로 프론트엔드 개발을 시작할 수 있습니다. B 작업자는 별도 ZIP이나 `CLAUDE.md` 없이 이 문서를 시작점으로 사용합니다. 필요한 API 계약과 Mock 예시는 아래 경로에서 확인할 수 있습니다.

## 1. 빠른 시작

```bash
git clone https://github.com/JaewanAppleacc/kosa.git
cd kosa
python3 -m venv .venv
./.venv/bin/pip install -r requirements-lock.txt
./.venv/bin/uvicorn src.api.main:app --reload
```

- `http://127.0.0.1:8000/docs` — 실제 동작하는 API 문서(Swagger UI). 여기서 바로 요청 날려볼 수 있습니다.
- 서버 안 띄우고 정적 파일만 보고 싶으면 `outputs/mock_api/`를 참고하세요.

## 2. 지금 뭐가 진짜로 되고, 뭐가 Mock인지

| 단계 | 실제 동작 여부 |
|---|---|
| 세션 생성 / 관심도 평가 / Context 선택·확정 | ✅ 실제 상태 저장·조회 (단, In-Memory — 서버 재시작하면 날아감, DB 아님) |
| 다음 질문 받기 / 답변 제출 | ⚠️ 응답 형태는 최종본이지만 내용은 고정 Mock (LLM 질문 생성 미구현) |
| Profile / Majors / Departments / Subjects / Subgraph 조회 | ⚠️ 전부 고정 Mock (Evidence 집계·Matching Engine 미구현) |

**즉 지금은 "화면과 상태 흐름을 만들 수 있는 단계"지, "진짜 계산 결과를 보여줄 단계"는 아닙니다.** Mock을 실제 값으로 바꿔도 응답 Schema(필드 이름·타입)는 안 바뀌도록 설계했으니, 화면 코드는 지금 만들어도 나중에 크게 안 깨집니다.

## 3. Endpoint 목록

| Method | Path | 용도 |
|---|---|---|
| POST | `/assessment/session` | 세션 생성 (user_id는 서버가 자동으로 demo_user_01로 고정, 클라이언트가 지정 못 함) |
| POST | `/assessment/interest-rating` | 15개 Context 관심도(1~5) 제출 |
| POST | `/assessment/context-select` | 선호 Context 4개 제출 → Contrast Context 1개 제안받음 |
| POST | `/assessment/context-confirm` | 최종 Context 확정 (Vertical Slice는 3개: game/media/school_life) |
| POST | `/assessment/next-question` | 다음 질문 받기 |
| POST | `/assessment/answer` | 답변 제출 |
| GET | `/profile/{session_id}` | Career Profile 결과 카드 |
| GET | `/majors/{session_id}` | 전공 관련도 목록 |
| GET | `/departments/{major_id}` | 실제 학과 목록 |
| GET | `/subjects/{session_id}` | 과목 추천 결과 |
| POST | `/course/upload` | 학교 PDF·Excel 업로드 — `multipart/form-data`, `session_id`(Form) + `file`(File). PDF/Excel 외 형식은 422 `VALIDATION_ERROR` |
| POST | `/course/confirm` | 파싱된 과목 후보 확인·확정 |
| GET | `/subgraph/{session_id}` | 관계 그래프 (Trait–전공–학과–과목) |
| GET | `/session/{session_id}` | Session 복원 |

## 4. 화면에서 써야 하는 상태값 (하드코딩하지 말고 이 목록을 그대로 쓰세요)

**질문 로딩/Fallback 상태** (`NextQuestionResponse.status`):
`GENERATED` / `REGENERATING` / `CACHE_USED` / `BACKUP_USED` / `CONTEXT_EARLY_TERMINATED`

**오류 코드** (`APIError.error_code`, 404 등에서 `detail`에 담겨 옴):
`VALIDATION_ERROR` / `SESSION_NOT_FOUND` / `LLM_UNAVAILABLE` / `LANGSMITH_UNAVAILABLE` / `INTERNAL_ERROR`

**전공 관련도 정성 Label** (`MajorRelevance.relevance_label` — 절대 숫자 아님, 숫자 필드 자체가 없음):
`"관련성 높음"` / `"함께 탐색해볼 분야"` / `"비교해볼 만한 분야"`

**Evidence 충분성** (`MajorRelevance.evidence_sufficiency`):
`"충분"` / `"보통"` / `"제한적"`

## 5. Mock JSON (서버 안 띄워도 되는 정적 파일)

`outputs/mock_api/`에 정상·오류·빈 결과 예시와 `openapi.json`이 있습니다. Schema가 바뀌면 아래 명령으로 재생성됩니다(재생성됐는지 커밋 로그로 확인하세요):

```bash
PYTHONPATH=. ./.venv/bin/python scripts/generate_mock_json.py
```

## 6. Schema 원본 위치 (타입 확인하고 싶을 때)

- `src/schemas/api.py` — 모든 Endpoint의 Request/Response
- `src/schemas/profile.py` — CareerProfile
- `src/schemas/major.py` — MajorProfile, Department, MajorRelevance
- `src/schemas/course.py` — CourseProfile, ParsedSubjectCandidate
- `src/schemas/graph.py` — SubgraphNode/SubgraphEdge

## 7. 알아둘 것

- Session은 In-Memory라 서버 재시작하면 다 날아갑니다. 새로고침 후 복원 UI는 만들어도 되지만, 서버 재시작까지 버티는 지속성은 아직 없습니다.
- `/assessment/session`은 `user_id`를 받지 않습니다(보안상 서버가 고정) — 화면에서 이 값을 사용자가 입력하게 만들지 마세요.
- 화면에 내부 점수(예: 84%, 0.67 같은 숫자)를 노출하는 API는 애초에 없습니다. 정성 Label만 옵니다.

## 8. 문제 발견 시

데이터 표현이 이상하면 A의 파일을 직접 고치지 말고, 재현 가능한 API 요청/응답과 함께 전달해주세요.

## 브랜치 전용 `CLAUDE.md` 처리

`worker-b`의 루트 `CLAUDE.md`는 B 작업 중에만 사용하는 브랜치 전용 파일입니다. `main` PR에는 포함하지 않습니다.

- PR을 만들기 직전에 `worker-b`에서 루트 `CLAUDE.md`를 삭제하는 마무리 커밋을 추가하거나, A가 구현 커밋만 선택적으로 Cherry-pick합니다.
- PR 전 `python scripts/check_no_worker_claude.py`를 실행해 루트 `CLAUDE.md`가 최종 변경에 남지 않았는지 확인합니다.

## 참고 문서

- `outputs/work_assignments/작업자_B_개발_지시서.md` — 원래 담당 범위 전체
- `outputs/context_definition_table_draft.md`, `outputs/trait_ontology_draft.md` — Context 15개·Trait 12개 정의 (아직 검토 확정 전 초안 상태)
