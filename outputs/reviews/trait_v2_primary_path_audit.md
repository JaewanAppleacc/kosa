# Trait Vector v2 Primary 경로 감사 — 2.6단계 §1

2026-08-23 Trait Ontology v2(2.6단계) 착수 전 실제 코드 기준 감사. 결론부터: **v2
Trait Vector Snapshot은 현재 순수 Shadow Mode다** — `/profile`, `/majors`,
`/subjects` 세 엔드포인트 중 어느 것도 v2 계산 결과를 실제 입력으로 쓰지 않는다.
아래는 파일·함수 단위로 그 정확한 경계를 기록한다.

## Legacy 경로 (현재 실제로 쓰이는 경로)

```text
POST /assessment/answer
  → src/agents/assessment/graph/answer_graph.py::_evidence_update()
    → EvidenceRecord 생성(evidence_origin=PRIMARY_BLUEPRINT, applied_primary_trait_delta 포함)
    → state.evidence_ledger.append(evidence)
  → src/engines/evidence_engine.py::summarize_trait_evidence()
    → EvidenceRecord.applied_primary_trait_delta만 집계(PRIMARY_BLUEPRINT origin만 필터)
    → state.trait_summaries: dict[str, TraitEvidenceSummary]에 저장(AssessmentState)

GET /profile/{session_id}  (src/api/main.py:1230 get_profile)
  → src/agents/assessment/profile_generator.py::generate_career_profile(
        trait_summaries=state.trait_summaries,   # ← Legacy 집계
        all_trait_definitions=TRAIT_DEFINITIONS_BY_ID,   # ← VERTICAL_SLICE_TRAITS, 12개만
    )
    → src/engines/profile_engine.py::select_profile_highlight_traits()
    → CareerProfile 반환 (v2 Snapshot 미참조)

GET /majors/{session_id}  (src/api/main.py:1341 get_majors)
  → src/engines/matching_engine.py::compute_student_trait_states(
        trait_summaries=state.trait_summaries,   # ← Legacy 집계
        TRAIT_DEFINITIONS_BY_ID,                 # ← 12개
    )
  → src/engines/matching_engine.py::compute_major_match() × VERTICAL_SLICE_MAJOR_PROFILES
    → data/master/major_profiles.jsonl (12-Trait 벡터, cosine 아님·가중 충족도)
    → MajorsResponse 반환 (v2 Snapshot 미참조)

GET /subjects/{session_id}  (src/api/main.py:1382 get_subjects)
  → src/services/course_planning_service.py::CoursePlanningService.get_course_profile()
    → 내부적으로 compute_student_trait_states() + subject_matching_engine.compute_subject_recommendations()
    → data/master/subjects.jsonl (12-Trait 벡터)
    → CourseProfile 반환 (v2 Snapshot 미참조)
```

핵심: `state.trait_summaries`(`TraitEvidenceSummary`, Legacy 12-Trait)가 Profile·
Major·Subject 세 곳 모두의 유일한 입력이다. `TRAIT_DEFINITIONS_BY_ID`도
`VERTICAL_SLICE_TRAITS`(12개, `src/data/trait_ontology/vertical_slice_traits.py`)만
가리킨다.

## v2 경로 (현재 계산은 되지만 아무데도 안 쓰임 — Shadow Mode)

```text
POST /assessment/answer (일반 질문, PRIMARY_BLUEPRINT/V2_DIRECT_PROBE 공통)
  → resolve_trait_signals() → AppliedTraitSignal[]
  → EvidenceRecord.applied_trait_signals_v2 에 저장(1단계부터 이미 병행 기록)

GET /profile/{session_id} 응답을 만든 "뒤"에만(main.py:1276)
  → src/api/main.py::_compute_and_store_trait_vector_shadow_snapshot(state)
    → _compute_v2_snapshot(state)
      → src/engines/trait_vector_snapshot_engine.py::compute_trait_vector_snapshot_all(
            state.evidence_ledger, legacy_states, unresolved_conflict_trait_ids,
            CORE_TRAIT_IDS,   # ← 24개(trait_ontology_v2.jsonl 전체)
        )
    → TraitVectorSnapshot(entries=...) 를
      src/services/trait_vector_shadow_repository.py::InMemoryTraitVectorShadowRepository
      에 session_id로 저장
    → LangSmith에 "Trait Vector Shadow Snapshot" Stage로 메타데이터만 기록(§Sanitizer 참고)
```

이 Snapshot을 **읽는 코드는 현재 이 저장소 전체에서 존재하지 않는다** — `grep -rn
"trait_vector_shadow_repository\." src/` 결과 `main.py`의 `.save(...)` 호출 1곳과
Repository 자체 정의뿐이며, `.load(...)`/`.get(...)`를 호출하는 곳이 없다. 즉
`InMemoryTraitVectorShadowRepository`는 "저장은 되지만 아무도 조회하지 않는" 순수
진단용 부산물이다. `/profile`·`/majors`·`/subjects` 응답 생성 코드 경로 어디에도
`compute_trait_vector_snapshot_all`·`TraitVectorSnapshot`·
`trait_vector_shadow_repository`에 대한 참조가 없다(대상 3개 함수 본문을 각각
확인함 — 위 Legacy 경로 인용 참고).

## 정확한 분리 지점 (파일·함수·라인)

| 구분 | 파일 | 함수/지점 |
|---|---|---|
| Legacy Evidence 집계 | `src/engines/evidence_engine.py` | `summarize_trait_evidence()` — `applied_primary_trait_delta`만 사용 |
| Legacy Profile 입력 | `src/api/main.py:1250` | `generate_career_profile(trait_summaries=state.trait_summaries, ...)` |
| Legacy Major 입력 | `src/api/main.py:1350` | `compute_student_trait_states(state.trait_summaries, TRAIT_DEFINITIONS_BY_ID, ...)` |
| Legacy Subject 입력 | `src/services/course_planning_service.py` | 내부에서 동일하게 `compute_student_trait_states()` 재사용 |
| v2 계산 트리거 | `src/api/main.py:1276` | `_compute_and_store_trait_vector_shadow_snapshot(state)` — **`/profile` 응답 확정 후에만** 호출(Fail-Open, try/except로 감싸짐) |
| v2 계산 엔진 | `src/engines/trait_vector_snapshot_engine.py` | `compute_trait_vector_snapshot_all()` |
| v2 저장 | `src/services/trait_vector_shadow_repository.py` | `InMemoryTraitVectorShadowRepository.save()` — `.load()` 호출자 없음(감사로 확인) |
| v2 소비자 | (없음) | Profile/Major/Subject 코드 경로 어디서도 import·호출 없음 |

## 2.6단계가 새로 만들어야 하는 것

1. `ENABLE_TRAIT_VECTOR_V2_PRIMARY` Flag ON일 때만 위 표의 "v2 계산 트리거"를
   `/profile`뿐 아니라 `/majors`·`/subjects` 이전 시점으로 옮기고, 그 결과를
   Legacy 대신 **입력**으로 쓰는 새 경로.
2. `TraitVectorShadowRepository`를 Primary 계산 결과 조회용으로도 재사용(추가
   Repository를 새로 만들지 않는다 — 이미 session_id 키로 저장·조회하는 구조가
   있다).
3. Fail-Closed 검수 게이트(§3) — 지금은 Shadow 계산이 `evidence_ledger` 전체(검수
   여부 무관)를 그대로 쓴다. Primary 계산은 검수되지 않은 질문에서 나온 Signal을
   제외한 **별도로 필터링된 evidence_ledger**를 같은 엔진에 넣어야 한다(엔진 자체는
   변경하지 않고 입력만 필터링 — 아래 구현 절 참고).
