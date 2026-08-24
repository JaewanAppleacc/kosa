# worker-b 프론트 잔여 작업 진행 상태

> 세션이 끊겨도 이어받을 수 있게 남기는 메모. 작업이 끝나면 이 파일을 지운다.

기준 브랜치: `worker-b` (프론트 계약은 `trait-vector-v2`와 동일 — `src/schemas/api.py`,
`outputs/mock_api/` 모두 차이 없음. A 브랜치를 끌어올 필요 없음)

## 할 일

- [x] 1. 반응형 정리 (CSS 좁은 화면 보정 + 구조 테스트) — 커밋됨 — sm:/md:/lg: 분기가 없던 화면 9개
      ResultScreen, ProfileScreen, MajorsScreen, SubjectsScreen, TraitMap,
      DepartmentBrowser, CourseUploadPanel, ContrastProposalScreen, RestoreScreen
- [x] 2. 15 Context / 4+1 정책 대응 (화면 문구는 이미 policy 값 사용, 낡은 주석만 정정) — 커밋됨 — 화면에 박힌 "2개/3개" 문구 제거,
      selection_policy 값으로만 말하게 한다
- [x] 3. 접근성: 각 단계 화면에 sr-only h1 추가 (스크린리더 제목 단계 복구) — 커밋됨
- [ ] 4. 남은 것: 15 Context 활성화 서버(trait-vector-v2)에 붙여 선택 흐름 확인
- [ ] 4. commit & push (worker-b만)

## 백엔드가 막고 있어 못 하는 것 (A에게 요청 필요)

- 이전 Session Profile 비교 — 비교 API 없음(`has_previous_completed_profile` boolean뿐)
- 성적 유사 범위 필터 — AdmissionReference 반환 엔드포인트 없음
- 지나온 질문 복원 — `GET /assessment/history/{session_id}` 없음

## 범위 밖(사용자 지시)

- `src/graph/obsidian_exporter.py` (Python) — 이번엔 프론트만 한다
