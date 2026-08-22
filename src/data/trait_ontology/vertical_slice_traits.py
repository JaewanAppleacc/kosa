"""Vertical Slice Trait Ontology — 12개, 2026-08-20 확정.

출처: outputs/trait_ontology_draft.md (팀 검토 진행 중, 이 파일이 검토 완료 시 정본이 된다).
O*NET/Holland 그라운딩 결과와 팀 결정(prioritization→planning 통합,
immediate_execution/opinion_mediation/audience_response_prediction 팀 정의 확정,
change_adaptation 신규 추가)을 그대로 반영했다.
"""

from __future__ import annotations

from src.schemas.trait import TraitDefinition

VERTICAL_SLICE_TRAITS: list[TraitDefinition] = [
    TraitDefinition(
        trait_id="causal_analysis",
        label="원인 분석",
        parent_dimension="분석과 구조화",
        definition="결과나 현상이 발생한 이유를 파고들어 확인하려는 경향",
        positive_indicators=["예상과 다른 결과가 나왔을 때 원인을 먼저 짚어보는 선택"],
        conflicting_indicators=["원인 파악 없이 바로 다른 방법을 시도하거나 넘어감"],
        aliases=[],
        source_references=[
            "강함 — O*NET GWA 'Analyzing Data or Information' (4.A.2.a.4): "
            "https://www.onetonline.org/find/descriptor/result/4.A.2.a.4"
        ],
        trait_scope="shared",
        minimum_context_count=2,
        primary_vector_group="cognitive",
        grounding_type="ONET_STRONG",
    ),
    TraitDefinition(
        trait_id="pattern_finding",
        label="패턴 탐색",
        parent_dimension="분석과 구조화",
        definition="여러 사례·정보에서 공통된 규칙이나 흐름을 찾아내려는 경향",
        positive_indicators=["여러 선택지·사례를 비교해 공통점을 정리하는 선택"],
        conflicting_indicators=["사례를 개별적으로만 보고 규칙화하지 않음"],
        aliases=[],
        source_references=[
            "보통 — Holland 'Investigative' 유형(항목 단위 대응 아님, 유형 설명 수준): "
            "https://self-directed-search.com/riasec-theory/"
        ],
        trait_scope="shared",
        minimum_context_count=2,
        primary_vector_group="cognitive",
        grounding_type="RIASEC_REFERENCE",
    ),
    TraitDefinition(
        trait_id="planning",
        label="계획·우선순위 수립",
        parent_dimension="계획과 실행",
        definition=(
            "행동하기 전에 전체 절차나 방법을 미리 구상하고, "
            "제한된 시간·자원에서 무엇을 먼저 할지 기준을 세워 정하는 경향"
        ),
        positive_indicators=[
            "새로운 과제·도구가 주어졌을 때 먼저 방법을 구상하는 선택",
            "'제한된 시간에는 무엇을 우선하는가' 질문에 명확한 기준으로 답함",
        ],
        conflicting_indicators=["구상·순서 없이 닥치는 대로 바로 시도"],
        aliases=["우선순위 판단"],
        source_references=[
            "보통 — O*NET GWA 'Organizing, Planning, and Prioritizing Work' (4.A.2.b.6), "
            "2026-08-20 prioritization 통합: "
            "https://www.onetonline.org/find/descriptor/result/4.A.2.b.6"
        ],
        trait_scope="shared",
        minimum_context_count=2,
        primary_vector_group="work_style",
        grounding_type="ONET_PARTIAL",
    ),
    TraitDefinition(
        trait_id="immediate_execution",
        label="즉시 실행",
        parent_dimension="계획과 실행",
        definition="계획을 오래 세우기보다 일단 시도하며 방법을 찾는 경향",
        positive_indicators=["새로운 도구·상황에서 바로 시도해보는 선택"],
        conflicting_indicators=["시도 전에 충분히 계획부터 세움"],
        aliases=[],
        source_references=["팀 정의 — O*NET/Holland 대응 항목 없음, 2026-08-20 조사"],
        trait_scope="shared",
        minimum_context_count=2,
        primary_vector_group="work_style",
        grounding_type="TEAM_DEFINED",
    ),
    TraitDefinition(
        trait_id="change_adaptation",
        label="변화 대응",
        parent_dimension="계획과 실행",
        definition="예상과 다른 상황이 생겼을 때 유연하게 대응 방식을 바꾸는 경향",
        positive_indicators=["'결과가 예상과 다르면 어떻게 수정하는가' 질문에서 새 방법을 시도하는 선택"],
        conflicting_indicators=["원래 방식을 고수하며 바꾸지 않음"],
        aliases=[],
        source_references=[
            "보통 — O*NET Work Style 'Adaptability' (Proactive and Growth Oriented, 2024 개편판, "
            "항목명만 확인·정의문 미확인): https://www.onetonline.org/find/descriptor/browse/1.D"
        ],
        trait_scope="shared",
        minimum_context_count=2,
        primary_vector_group="work_style",
        grounding_type="ONET_PARTIAL",
    ),
    TraitDefinition(
        trait_id="collaboration_preference",
        label="협업 선호",
        parent_dimension="협업과 조정",
        definition="혼자보다 다른 사람과 함께 일하는 것을 선호하는 경향",
        positive_indicators=["팀 활동에서 역할을 나누거나 함께 결정하는 선택"],
        conflicting_indicators=["혼자 처리하는 방식을 선호"],
        aliases=[],
        source_references=[
            "보통 — O*NET Work Style 'Cooperation' (Interpersonally Oriented, "
            "항목명 확인·정의문은 구버전 인용): https://www.onetonline.org/find/descriptor/browse/1.D"
        ],
        trait_scope="shared",
        minimum_context_count=2,
        primary_vector_group="work_style",
        grounding_type="ONET_PARTIAL",
    ),
    TraitDefinition(
        trait_id="opinion_mediation",
        label="의견 조정",
        parent_dimension="협업과 조정",
        definition="여러 의견이 충돌할 때 기준을 세워 조율하려는 경향",
        positive_indicators=["'여러 의견이 충돌하면 무엇을 기준으로 결정하는가' 질문에 조정 기준을 제시"],
        conflicting_indicators=["충돌을 피하거나 한쪽 의견을 그대로 따름"],
        aliases=[],
        source_references=["팀 정의 — O*NET/Holland 대응 항목 없음, 2026-08-20 조사"],
        trait_scope="shared",
        minimum_context_count=2,
        primary_vector_group="work_style",
        grounding_type="TEAM_DEFINED",
    ),
    TraitDefinition(
        trait_id="emotional_interpretation",
        label="타인의 감정 해석",
        parent_dimension="인간과 관계 탐구",
        definition="다른 사람의 감정이나 반응을 관찰해 이해하려는 경향",
        positive_indicators=["친구·캐릭터·시청자의 감정 변화를 언급하며 선택"],
        conflicting_indicators=["감정보다 사실·결과 자체에만 집중"],
        aliases=[],
        source_references=[
            "보통 — O*NET Work Style 'Empathy' (2024 신설 항목, 항목명만 확인): "
            "https://www.onetonline.org/find/descriptor/browse/1.D"
        ],
        trait_scope="shared",
        minimum_context_count=2,
        primary_vector_group="cognitive",
        grounding_type="ONET_PARTIAL",
    ),
    TraitDefinition(
        trait_id="audience_response_prediction",
        label="사용자 반응 예측",
        parent_dimension="사용자·타인 관점",
        definition="결과물·행동에 대해 다른 사람이 어떻게 받아들일지 미리 고려하는 경향",
        positive_indicators=["결과물을 만들 때 '보는 사람이 어떻게 느낄지'를 기준으로 선택"],
        conflicting_indicators=["자신의 기준만 고려하고 상대 반응은 고려하지 않음"],
        aliases=[],
        source_references=["팀 정의 — O*NET/Holland 대응 항목 없음, 2026-08-20 조사"],
        trait_scope="shared",
        minimum_context_count=2,
        primary_vector_group="cognitive",
        grounding_type="TEAM_DEFINED",
    ),
    TraitDefinition(
        trait_id="visual_expression",
        label="시각적 표현",
        parent_dimension="창의적 표현",
        definition="생각·느낌을 이미지·영상 등 시각적 형태로 표현하는 것에 대한 관심",
        positive_indicators=["편집·구성·이미지 관련 선택지를 선호"],
        conflicting_indicators=["시각적 요소보다 글이나 말로 표현하는 것을 선호"],
        aliases=[],
        source_references=[
            "강함 — O*NET GWA 'Thinking Creatively' + Holland 'Artistic': "
            "https://self-directed-search.com/riasec-theory/"
        ],
        trait_scope="domain_specific",
        minimum_context_count=1,
        primary_vector_group="interest",
        grounding_type="ONET_STRONG",
    ),
    TraitDefinition(
        trait_id="information_comparison",
        label="정보 비교·탐색",
        parent_dimension="정보 탐색과 비교",
        definition="결정 전에 여러 정보나 선택지를 찾아보고 비교하는 경향",
        positive_indicators=["결정 전에 여러 자료·사례를 찾아보는 선택"],
        conflicting_indicators=["정보 탐색 없이 직관적으로 바로 결정"],
        aliases=[],
        source_references=[
            "보통 — O*NET GWA 'Getting Information' ('비교' 뉘앙스는 팀이 추가): "
            "https://www.onetonline.org/find/descriptor/browse/4.A"
        ],
        trait_scope="domain_specific",
        minimum_context_count=1,
        primary_vector_group="cognitive",
        grounding_type="ONET_PARTIAL",
    ),
    TraitDefinition(
        trait_id="tool_utilization",
        label="도구 활용",
        parent_dimension="도구 활용과 제작",
        definition="도구·장비를 다뤄 결과물을 직접 만들거나 조작하는 것을 선호하는 경향",
        positive_indicators=["아이템·장비·편집 도구 등을 직접 다루는 선택"],
        conflicting_indicators=["도구를 다루기보다 아이디어·구상 단계에 머무름"],
        aliases=[],
        source_references=[
            "보통 — Holland 'Realistic' 유형: https://self-directed-search.com/riasec-theory/"
        ],
        trait_scope="domain_specific",
        minimum_context_count=1,
        primary_vector_group="environment",
        grounding_type="RIASEC_REFERENCE",
    ),
]

VERTICAL_SLICE_TRAIT_IDS: set[str] = {t.trait_id for t in VERTICAL_SLICE_TRAITS}
