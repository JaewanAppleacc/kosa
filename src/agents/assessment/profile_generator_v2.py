"""v2 Career Profile 생성 — 2026-08-23 Trait Ontology v2(2.6단계) §5.

`src/agents/assessment/profile_generator.py`(Legacy)와 완전히 같은 LLM+결정론적
Fallback 구조를 따르되, 후보 선정은 `engines/profile_engine_v2.py`(TraitVectorEntry
기반)를 쓴다. 반환 타입은 Legacy와 동일한 `CareerProfile`이다 — §12 "공개 API/OpenAPI
계약 영향 확인" 요구를 그대로 만족하기 위해 새 Schema를 만들지 않는다.

§5 핵심 요구: "LLM이 꺼지거나 실패해도 같은 학생의 v2 Evidence 기반 결정론적 Fallback을
쓴다 — Legacy Mock Profile로 빠지면 안 된다." `llm_client=None`이거나 재생성까지 실패하면
`_fallback_profile_v2()`로 넘어가는데, 이 함수는 항상 이 세션의 실제 `TraitVectorEntry`
값(v2 Evidence 기반)만 사용한다 — 다른 세션·고정 Mock 문구를 절대 섞지 않는다."""

from __future__ import annotations

from datetime import datetime

from src.engines.profile_engine_v2 import (
    HighlightCandidateV2,
    build_detailed_evidence_by_dimension_v2,
    select_profile_highlight_traits_v2,
)
from src.llm.protocols import ChatLLMClient, LLMCallError
from src.schemas.evidence import ContrastResolutionRecord, EvidenceRecord
from src.schemas.profile import CareerProfile, CareerProfileHighlight, GeneratedCareerProfile
from src.schemas.trait import TraitDefinition
from src.schemas.trait_vector_snapshot import TraitVectorEntry

SYSTEM_PROMPT = """당신은 고등학생 진로 탐색 결과를 요약하는 작성기입니다. 다음 규칙을 반드시 지키세요.
- 결과 화면에 그대로 노출됩니다. 1인칭 시점("~해요", "~하는 편이에요")으로, 고등학생이
  스스로에 대해 읽고 공감할 수 있는 자연스러운 한국어로 씁니다.
- 직업명이나 학과명을 직접 언급하지 않습니다("~에 어울려요" 같은 진로 단정도 하지 않습니다).
- 숫자·점수·퍼센트를 문장에 넣지 않습니다.
- state가 NOT_PROBED·HYPOTHESIS·LIMITED인 Trait는 "학생에게 그 능력·경험이 없다"는 뜻이
  아니라 "이번 검사가 그 부분을 충분히 관찰하지 못했다"는 뜻입니다. "경험이 부족",
  "능력이 부족", "약하다", "소질이 없다", "잘하지 못한다" 같은 표현을 절대 쓰지 않습니다.
  나쁜 예: "계획을 세우는 데는 아직 경험이 부족해요"
  좋은 예: "이번 답변에서는 계획을 세우는 방식이 충분히 확인되지 않았어요"
- title은 학생의 정체성을 명명하지 않고, "이번 답변에서 관찰된 경향"을 문장으로
  서술합니다. "~형", "~유형", "~타입", "~자"/"~가"로 끝나는 사람 지칭 표현을 전부
  금지합니다. title은 반드시 "~보여요", "~나타났어요", "~두드러졌어요", "~확인됐어요"
  처럼 관찰을 서술하는 동사로 끝나야 합니다.
- hashtags는 3~6개, 각각 "#"으로 시작하는 짧은 명사구입니다.
- highlights 배열은 주어진 Trait 목록과 정확히 같은 개수·같은 trait_id 순서로 반환합니다.
  각 항목의 trait_id는 입력값을 그대로 씁니다."""


def _describe_status(status: str) -> str:
    return {
        "STRONG": "여러 Context에서 반복 확인됨 — 뚜렷한 강점으로 서술할 것",
        "MODERATE": "확인됐지만 STRONG만큼 반복되진 않음 — 강점으로 서술하되 과장하지 말 것",
        "LIMITED": "Evidence가 있지만 다양성이 부족함 — '이번 답변에서는 ~가 충분히 확인되지 "
        "않았어요'처럼 관찰이 부족했다는 뜻으로 서술할 것",
        "HYPOTHESIS": "확인되지 않은 간접 단서만 있음 — 확정된 강점처럼 서술하지 말고, 아직 더 "
        "탐색이 필요한 영역이라는 뉘앙스로 서술할 것",
        "NOT_PROBED": "이번 검사에서 확인할 기회가 부족했음 — '이번 답변에서는 ~가 충분히 확인되지 "
        "않았어요'처럼 시스템이 아직 관찰하지 못했다는 뜻으로 서술할 것",
    }.get(status, "")


def _describe_resolution(resolution_role: str | None) -> str:
    return {
        "preferred": "확인 질문에서 이 성향 쪽을 선택함 — 상대적으로 더 자주 선택하는 경향으로 "
        "서술할 것(다른 성향이 아예 없다고 단정하지는 말 것)",
        "deprioritized": "확인 질문에서 반대 성향을 선택함 — 이 성향이 없다는 뜻이 아니라 상대적으로 "
        "덜 선택하는 경향이라는 뉘앙스로 서술할 것(결핍처럼 쓰지 말 것)",
        "context_dependent": "확인 질문에서 '상황에 따라 다르다'를 선택함 — 반드시 "
        "'상황에 따라 다르게 나타나요'처럼 상황 의존적으로 서술할 것(한쪽으로 단정하지 말 것)",
    }.get(resolution_role or "", "")


def _build_user_prompt(candidates: list[HighlightCandidateV2]) -> str:
    trait_blocks = []
    for c in candidates:
        resolution_note = _describe_resolution(c.resolution_role)
        resolution_line = f"\n  확인 질문 답변: {resolution_note}" if resolution_note else ""
        trait_blocks.append(
            f"""- trait_id: {c.trait_definition.trait_id}
  label: {c.trait_definition.label}
  definition: {c.trait_definition.definition}
  긍정 지표: {', '.join(c.trait_definition.positive_indicators)}
  상태: {c.entry.status} — {_describe_status(c.entry.status)}{resolution_line}"""
        )
    trait_list = "\n".join(trait_blocks)
    return f"""[이번에 문장으로 표현해야 할 Trait 목록 — 정확히 이 순서·이 개수로 반환할 것]
{trait_list}

title 필드에는 이 학생 전체를 요약하는 짧은 문장을, highlights 필드에는 각 Trait마다
trait_id와 그 Trait을 표현한 한 문장을, hashtags 필드에는 이 학생을 나타내는 짧은
해시태그 3~6개를 반환하세요."""


def _fallback_profile_v2(
    session_id: str,
    user_id: str,
    candidates: list[HighlightCandidateV2],
    detailed_evidence_by_dimension: dict,
) -> CareerProfile:
    """§5 핵심 요구 — LLM이 없거나 실패해도 항상 이 세션의 실제 `TraitVectorEntry`
    값만으로 문장을 만든다. Legacy Mock Profile이나 다른 세션 값을 섞지 않는다."""

    highlights = []
    for c in candidates:
        if c.resolution_role == "context_dependent":
            text = f"{c.trait_definition.label}은(는) 상황에 따라 다르게 나타나요."
        elif c.resolution_role == "deprioritized":
            text = f"{c.trait_definition.definition} 다만 확인 질문에서는 다른 방식을 상대적으로 더 자주 선택했어요."
        elif c.entry.status in ("NOT_PROBED", "HYPOTHESIS", "LIMITED"):
            text = f"이번 답변에서는 {c.trait_definition.label}이(가) 충분히 확인되지 않았어요."
        else:
            text = f"{c.trait_definition.definition}"
        highlights.append(CareerProfileHighlight(text=text, supporting_trait_ids=[c.trait_definition.trait_id]))

    hashtags = [f"#{c.trait_definition.label}" for c in candidates[:5]]

    return CareerProfile(
        session_id=session_id,
        user_id=user_id,
        title="지금까지의 답변을 바탕으로 한 요약",
        highlights=highlights,
        hashtags=hashtags,
        detailed_evidence_by_dimension=detailed_evidence_by_dimension,
        generated_at=datetime.now(),
    )


def generate_career_profile_v2(
    *,
    session_id: str,
    user_id: str,
    snapshot_entries: dict[str, TraitVectorEntry],
    all_trait_definitions: dict[str, TraitDefinition],
    evidence_ledger: list[EvidenceRecord],
    llm_client: ChatLLMClient | None,
    max_regenerations: int = 1,
    resolutions: dict[str, ContrastResolutionRecord] | None = None,
) -> CareerProfile:
    """§5 — `evidence_ledger`는 호출하는 쪽이 이미 Fail-Closed 게이트를 통과시킨
    목록이어야 한다(이 함수는 검수 상태를 재판정하지 않는다). `llm_client`가 None이거나
    재생성까지 실패하면 `_fallback_profile_v2()`로 즉시 넘어간다."""

    candidates = select_profile_highlight_traits_v2(snapshot_entries, all_trait_definitions, resolutions)
    detailed_evidence = build_detailed_evidence_by_dimension_v2(candidates, evidence_ledger)
    requested_trait_ids = [c.trait_definition.trait_id for c in candidates]

    if llm_client is None:
        return _fallback_profile_v2(session_id, user_id, candidates, detailed_evidence)

    user_prompt = _build_user_prompt(candidates)

    for _ in range(max_regenerations + 1):
        try:
            result = llm_client.complete_structured(
                system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt, response_model=GeneratedCareerProfile,
            )
        except LLMCallError:
            continue

        returned_ids = [h.trait_id for h in result.highlights]
        if returned_ids != requested_trait_ids:
            continue

        highlights = [
            CareerProfileHighlight(text=h.text, supporting_trait_ids=[h.trait_id])
            for h in result.highlights
        ]
        try:
            return CareerProfile(
                session_id=session_id, user_id=user_id, title=result.title, highlights=highlights,
                hashtags=result.hashtags, detailed_evidence_by_dimension=detailed_evidence,
                generated_at=datetime.now(),
            )
        except ValueError:
            continue

    return _fallback_profile_v2(session_id, user_id, candidates, detailed_evidence)
