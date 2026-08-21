"""Career Profile 생성 — 설계안 §14. "어떤 Trait를 쓸지"는 engines/profile_engine.py가
결정론적으로 정하고, 여기서는 그 Trait들을 문장으로 표현하는 것만 LLM에 맡긴다.

CLAUDE.md: "LLM은 질문 표현, 제한된 보조 추출, 설명 생성만 담당한다." Highlight 문장·제목·
해시태그는 "설명 생성"에 해당하지만, 어떤 Trait가 선택되는지(§13 상태 판정)는 Python이
이미 정한 뒤 LLM에게 넘긴다.
"""

from __future__ import annotations

from datetime import datetime

from src.engines.profile_engine import (
    HighlightCandidate,
    build_detailed_evidence_by_dimension,
    select_profile_highlight_traits,
)
from src.llm.protocols import ChatLLMClient, LLMCallError
from src.schemas.evidence import EvidenceRecord, TraitEvidenceSummary
from src.schemas.profile import CareerProfile, CareerProfileHighlight, GeneratedCareerProfile
from src.schemas.trait import TraitDefinition

SYSTEM_PROMPT = """당신은 고등학생 진로 탐색 결과를 요약하는 작성기입니다. 다음 규칙을 반드시 지키세요.
- 결과 화면에 그대로 노출됩니다. 1인칭 시점("~해요", "~하는 편이에요")으로, 고등학생이
  스스로에 대해 읽고 공감할 수 있는 자연스러운 한국어로 씁니다.
- 직업명이나 학과명을 직접 언급하지 않습니다("~에 어울려요" 같은 진로 단정도 하지 않습니다).
- 숫자·점수·퍼센트를 문장에 넣지 않습니다(예: "84%", "3회 확인됨" 같은 표현 금지).
- 주어진 Trait의 definition과 positive_indicators를 참고해 그 Trait이 실제로 어떻게
  나타났는지 구체적으로 씁니다 — "분석적이에요" 같은 추상적 라벨만 반복하지 않습니다.
- state가 INSUFFICIENT나 LIMITED인 Trait는 "학생에게 그 능력·경험이 없다"는 뜻이 아니라
  "이번 검사가 그 부분을 충분히 관찰하지 못했다"는 뜻입니다. 관찰 부족은 시스템 쪽 한계이지
  학생의 결핍이 아니므로, "경험이 부족", "능력이 부족", "약하다", "소질이 없다",
  "잘하지 못한다" 같은 표현을 절대 쓰지 않습니다. 이런 Trait를 마치 확정된 강점처럼 쓰지도
  않습니다.
  나쁜 예: "계획을 세우는 데는 아직 경험이 부족해요"
  좋은 예: "이번 답변에서는 계획을 세우는 방식이 충분히 확인되지 않았어요"
- title은 학생의 정체성을 명명하지 않고, "이번 답변에서 관찰된 경향"을 문장으로
  서술합니다. "~형", "~유형", "~타입"은 물론이고, "꼼꼼한 탐색자", "논리적인 분석가",
  "창의적인 설계자", "세심한 관찰자"처럼 사람을 가리키는 명사(~자, ~가 등)로 끝나는
  제목도 전부 금지합니다 — 형태만 다를 뿐 학생을 하나의 고정된 사람 유형으로 규정하는
  건 똑같습니다. title은 반드시 "~보여요", "~나타났어요", "~두드러졌어요", "~확인됐어요"
  처럼 관찰을 서술하는 동사로 끝나야 합니다.
  나쁜 예: "생각을 시각적으로 풀어내고 이유를 파헤치는 탐구자형"
  나쁜 예: "꼼꼼한 탐색자" / "논리적인 분석가" / "창의적인 설계자" / "세심한 관찰자"
  좋은 예: "원인을 깊이 파악하려는 모습이 보여요"
  좋은 예: "시각적으로 표현하려는 경향이 두드러졌어요"
  좋은 예: "답변에서 계획적으로 접근하는 모습이 나타났어요"
  좋은 예: "여러 관점을 비교하려는 경향이 확인됐어요"
- hashtags는 3~6개, 각각 "#"으로 시작하는 짧은 명사구입니다.
- highlights 배열은 주어진 Trait 목록과 정확히 같은 개수·같은 trait_id 순서로 반환합니다.
  각 항목의 trait_id는 입력값을 그대로 씁니다."""


def _describe_state(judgment_state: str) -> str:
    return {
        "STRONG": "여러 Context에서 반복 확인됨 — 뚜렷한 강점으로 서술할 것",
        "MODERATE": "확인됐지만 STRONG만큼 반복되진 않음 — 강점으로 서술하되 과장하지 말 것",
        "LIMITED": "Evidence가 있지만 다양성이 부족함 — '이번 답변에서는 ~가 충분히 확인되지 "
        "않았어요'처럼 관찰이 부족했다는 뜻으로 서술할 것(학생의 결핍으로 서술하지 말 것)",
        "CONFLICTING": "서로 다른 상황에서 상반된 선택이 나옴 — 한쪽으로 단정하지 말고 두 면이 다 있다는 식으로 서술할 것",
        "INSUFFICIENT": "이번 검사에서 확인할 기회가 부족했음 — '이번 답변에서는 ~가 충분히 "
        "확인되지 않았어요'처럼 시스템이 아직 관찰하지 못했다는 뜻으로 서술할 것(학생의 결핍으로 "
        "서술하지 말 것)",
    }.get(judgment_state, "")


def _build_user_prompt(candidates: list[HighlightCandidate]) -> str:
    trait_blocks = []
    for c in candidates:
        trait_blocks.append(
            f"""- trait_id: {c.trait_definition.trait_id}
  label: {c.trait_definition.label}
  definition: {c.trait_definition.definition}
  긍정 지표: {', '.join(c.trait_definition.positive_indicators)}
  상태: {c.judgment.state.value} — {_describe_state(c.judgment.state.value)}"""
        )
    trait_list = "\n".join(trait_blocks)
    return f"""[이번에 문장으로 표현해야 할 Trait 목록 — 정확히 이 순서·이 개수로 반환할 것]
{trait_list}

title 필드에는 이 학생 전체를 요약하는 짧은 별명을, highlights 필드에는 각 Trait마다
trait_id와 그 Trait을 표현한 한 문장을, hashtags 필드에는 이 학생을 나타내는 짧은
해시태그 3~6개를 반환하세요."""


def _fallback_profile(
    session_id: str,
    user_id: str,
    candidates: list[HighlightCandidate],
    detailed_evidence_by_dimension: dict,
) -> CareerProfile:
    """LLM 생성이 재생성까지 실패했을 때의 마지막 경로. §11 Fallback과 같은 원칙 —
    문장은 덜 다듬어지지만 실제 계산된 Trait·상태는 그대로 정직하게 반영한다(Mock으로
    다른 학생의 내용을 보여주지 않는다)."""

    highlights = []
    for c in candidates:
        if c.judgment.state.value in ("INSUFFICIENT", "CONFLICTING", "LIMITED"):
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


def generate_career_profile(
    *,
    session_id: str,
    user_id: str,
    trait_summaries: dict[str, TraitEvidenceSummary],
    all_trait_definitions: dict[str, TraitDefinition],
    evidence_ledger: list[EvidenceRecord],
    unresolved_conflict_trait_ids: set[str],
    llm_client: ChatLLMClient,
    max_regenerations: int = 1,
) -> CareerProfile:
    candidates = select_profile_highlight_traits(
        trait_summaries, all_trait_definitions, unresolved_conflict_trait_ids
    )
    detailed_evidence = build_detailed_evidence_by_dimension(candidates, evidence_ledger)
    requested_trait_ids = [c.trait_definition.trait_id for c in candidates]

    user_prompt = _build_user_prompt(candidates)

    for _ in range(max_regenerations + 1):
        try:
            result = llm_client.complete_structured(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
                response_model=GeneratedCareerProfile,
            )
        except LLMCallError:
            continue

        returned_ids = [h.trait_id for h in result.highlights]
        if returned_ids != requested_trait_ids:
            # LLM이 Trait를 빠뜨렸거나 순서를 바꿨거나 새 trait_id를 만들어냈다 — 거부.
            continue

        highlights = [
            CareerProfileHighlight(text=h.text, supporting_trait_ids=[h.trait_id])
            for h in result.highlights
        ]
        try:
            return CareerProfile(
                session_id=session_id,
                user_id=user_id,
                title=result.title,
                highlights=highlights,
                hashtags=result.hashtags,
                detailed_evidence_by_dimension=detailed_evidence,
                generated_at=datetime.now(),
            )
        except ValueError:
            continue

    return _fallback_profile(session_id, user_id, candidates, detailed_evidence)
