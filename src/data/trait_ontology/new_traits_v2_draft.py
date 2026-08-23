"""Trait Ontology v2 1단계 — 신규 12개 Trait 초안(DRAFT, 2인 교차검토 전).

CLAUDE.md 지시(2026-08-23 20차 후속): 기존 12개 Trait(`vertical_slice_traits.py`)의
ID·정의·행동 지표는 여기서 하나도 바꾸지 않는다 — 이 파일은 신규 12개만 추가한다.
`career_build_trait_ontology_v2.py`가 이 파일과 `VERTICAL_SLICE_TRAITS`를 합쳐
`data/master/trait_ontology_v2.jsonl`(24개, review 대상 정본)을 만든다.

원칙:
- 공식 근거를 직접 확인하지 못한 Trait는 grounding_type="TEAM_DEFINED"로 남긴다(과장 금지).
- O*NET Work Style 목록(16개 고정 항목)과 항목명이 일치하면 grounding_type="ONET_PARTIAL"로
  두되(기존 change_adaptation/collaboration_preference와 같은 수준 — 항목명은 확인했지만
  공식 정의문 완전 대조는 아직 안 함), "ONET_STRONG"으로 과장하지 않는다.
- `neighboring_trait_ids`/`distinction_notes`로 의미가 겹치는 이웃 Trait와 실제로 뭐가
  다른지 명시한다 — 문서화하지 않으면 나중에 두 Trait가 하나로 합쳐지기 쉽다.
- `personal_goal_priority`는 "이기적임"의 중립적 표현이다 — 타인을 배려하지 않는
  성격으로 단정하지 않고, 공동 목표보다 개인 목표·자율적 기준을 상대적으로 우선하는
  경향으로만 정의한다(2026-08-23 지시서 §2 원칙 3).

발견된 긴장(자동으로 고치지 않고 review 문서에 그대로 보고함, §2 원칙 7):
- `creative_ideation`의 정의가 넓게 잡히면 기존 `visual_expression`이 이미 인용한
  O*NET GWA "Thinking Creatively"(4.A.2.b.2, 원문: "Developing, designing, or creating
  new applications, ideas, relationships, systems, or products, including artistic
  contributions.")와 같은 공식 항목을 다시 가리키게 된다 — `visual_expression`은 이미
  "시각적 형태"로 범위를 좁혀 이 항목을 인용하고 있어서, `creative_ideation`은 매체를
  가리지 않는 "새로운 발상 자체"로 범위를 분리해 같은 항목을 ONET_STRONG으로 중복
  주장하지 않고 TEAM_DEFINED로 남긴다. 이 구분이 실제로 유효한지는 2인 검토 대상이다.
"""

from __future__ import annotations

from src.schemas.trait import TraitDefinition

NEW_TRAITS_V2_DRAFT: list[TraitDefinition] = [
    # --- 사고·분석 ---
    TraitDefinition(
        trait_id="systems_thinking",
        label="구조적 사고",
        parent_dimension="분석과 구조화",
        definition="여러 요소가 서로 어떻게 영향을 주고받는지 전체 구조로 파악하려는 경향",
        positive_indicators=[
            "한 부분을 바꾸면 다른 부분에 어떤 영향이 가는지부터 생각하는 선택",
            "개별 사건보다 그것들을 만드는 전체 흐름·구조를 먼저 살피는 선택",
        ],
        conflicting_indicators=["당장 눈앞의 항목 하나만 보고 판단하며 전체 연결은 신경 쓰지 않음"],
        aliases=["시스템 사고"],
        source_references=[
            "보통 — O*NET Skill 'Systems Analysis'(2.B.5.a) 항목명 확인, 공식 정의문 완전 대조는 "
            "아직 아님: https://www.onetonline.org/find/descriptor/result/2.B.5.a"
        ],
        trait_scope="shared",
        minimum_context_count=2,
        primary_vector_group="cognitive",
        grounding_type="ONET_PARTIAL",
        neighboring_trait_ids=["causal_analysis", "pattern_finding"],
        distinction_notes=(
            "causal_analysis는 '이 결과가 왜 생겼는가' 하나의 원인을 깊게 파는 것이고, "
            "pattern_finding은 여러 사례에서 반복되는 규칙을 찾는 것이다. systems_thinking은 "
            "그 둘과 달리 '이 요소를 바꾸면 다른 요소가 어떻게 같이 움직이는가'라는 요소 간 "
            "상호작용·전체 구조에 초점을 둔다 — 원인 하나·규칙 하나가 아니라 관계망 전체를 본다."
        ),
        review_status="draft",
    ),
    # --- 창의·표현 ---
    TraitDefinition(
        trait_id="creative_ideation",
        label="아이디어 발상",
        parent_dimension="창의적 표현",
        definition="기존에 없던 아이디어나 접근 방식을 매체와 무관하게 새롭게 떠올리는 경향",
        positive_indicators=[
            "정해진 방법이 있어도 다른 방식이 없을지 스스로 새 안을 내는 선택",
            "'이런 것도 가능하지 않을까'하는 아이디어 자체를 제시하는 선택",
        ],
        conflicting_indicators=["기존에 있던 방법·형식을 그대로 따르고 새 안을 내지 않음"],
        aliases=[],
        source_references=[
            "팀 정의 — visual_expression이 이미 인용한 O*NET GWA 'Thinking Creatively'"
            "(4.A.2.b.2)와 정의가 겹칠 위험이 있어 같은 항목을 다시 ONET_STRONG으로 "
            "주장하지 않는다(이 파일 상단 docstring '발견된 긴장' 참고): "
            "https://www.onetonline.org/find/descriptor/result/4.A.2.b.2"
        ],
        trait_scope="shared",
        minimum_context_count=2,
        primary_vector_group="cognitive",
        grounding_type="TEAM_DEFINED",
        neighboring_trait_ids=["visual_expression", "verbal_expression"],
        distinction_notes=(
            "visual_expression/verbal_expression은 '표현 형태'(시각/언어)에 대한 관심이고, "
            "creative_ideation은 형태와 무관하게 '새로운 발상 자체'를 떠올리는 경향이다 — "
            "예를 들어 새로운 게임 규칙을 떠올리는 것도 creative_ideation이지만 시각적이거나 "
            "언어적인 표현 형태와는 무관할 수 있다."
        ),
        review_status="draft",
    ),
    TraitDefinition(
        trait_id="verbal_expression",
        label="언어적 표현",
        parent_dimension="창의적 표현",
        definition="생각·느낌을 말이나 글로 표현하는 것에 대한 관심",
        positive_indicators=["글을 쓰거나 말로 설명·전달하는 선택지를 선호"],
        conflicting_indicators=["언어보다 이미지·행동 등 다른 방식으로 표현하는 것을 선호"],
        aliases=[],
        source_references=[
            "약함 — Holland 'Artistic' 유형(항목 단위 대응 아님, 글쓰기·언어 표현도 "
            "포함되는 넓은 유형 설명 수준): https://self-directed-search.com/riasec-theory/"
        ],
        trait_scope="shared",
        minimum_context_count=2,
        primary_vector_group="interest",
        grounding_type="RIASEC_REFERENCE",
        neighboring_trait_ids=["visual_expression", "opinion_expression"],
        distinction_notes=(
            "visual_expression은 이미지·영상 등 시각 형태 표현에 대한 관심이고, "
            "verbal_expression은 말·글 형태 표현에 대한 관심이다(표현 매체 차이). "
            "opinion_expression은 표현 형태가 아니라 '자기 의견을 명확히 드러내는가'라는 "
            "주장의 유무를 본다 — 잘 쓰거나 말하는 것 자체와 의견을 관철하는 것은 다르다."
        ),
        review_status="draft",
    ),
    TraitDefinition(
        trait_id="aesthetic_sensitivity",
        label="심미적 감식",
        parent_dimension="창의적 표현",
        definition="색·형태·구성 등 미적 요소의 좋고 나쁨 차이를 민감하게 알아차리는 경향",
        positive_indicators=["색감·구도·배치가 조금만 달라져도 그 차이를 짚어내는 선택"],
        conflicting_indicators=["미적 요소의 차이보다 기능·내용에만 집중"],
        aliases=[],
        source_references=[
            "약함 — Holland 'Artistic' 유형(항목 단위 대응 아님): "
            "https://self-directed-search.com/riasec-theory/"
        ],
        trait_scope="shared",
        minimum_context_count=2,
        primary_vector_group="interest",
        grounding_type="RIASEC_REFERENCE",
        neighboring_trait_ids=["visual_expression"],
        distinction_notes=(
            "visual_expression은 '내가 직접 시각적으로 표현하고 싶다'는 제작 욕구이고, "
            "aesthetic_sensitivity는 '무엇이 더 나은 미적 결과물인지 알아차린다'는 감식·평가 "
            "능력이다 — 표현하고 싶어 하지 않아도 미적 차이에는 민감할 수 있다(둘은 독립적)."
        ),
        review_status="draft",
    ),
    # --- 실행·관리 ---
    TraitDefinition(
        trait_id="persistence_completion",
        label="지속·완수",
        parent_dimension="계획과 실행",
        definition="어려움이나 지루함이 있어도 시작한 일을 끝까지 마무리하려는 경향",
        positive_indicators=["뜻대로 안 돼도 포기하지 않고 끝까지 마무리하는 선택"],
        conflicting_indicators=["어려워지면 다른 일로 넘어가고 마무리를 미룸"],
        aliases=[],
        source_references=[
            "보통 — O*NET Work Style 'Persistence' 항목명 확인, 공식 정의문 완전 대조는 "
            "아직 아님: https://www.onetonline.org/find/descriptor/browse/1.D"
        ],
        trait_scope="shared",
        minimum_context_count=2,
        primary_vector_group="work_style",
        grounding_type="ONET_PARTIAL",
        neighboring_trait_ids=["planning", "detail_orientation"],
        distinction_notes=(
            "planning은 '시작하기 전에 순서를 미리 구상하는가'이고, persistence_completion은 "
            "'시작한 뒤 어려워져도 끝까지 가는가'다 — 계획을 잘 세우는 것과 끝까지 완수하는 "
            "것은 서로 다른 시점의 행동이다."
        ),
        review_status="draft",
    ),
    TraitDefinition(
        trait_id="detail_orientation",
        label="세부 주의",
        parent_dimension="계획과 실행",
        definition="작은 오차나 세부 사항까지 꼼꼼하게 확인하려는 경향",
        positive_indicators=["전체가 끝난 뒤에도 세부 항목을 다시 점검하는 선택"],
        conflicting_indicators=["세부 확인 없이 전체 흐름만 보고 넘어감"],
        aliases=[],
        source_references=[
            "보통 — O*NET Work Style 'Attention to Detail' 항목명 확인, 공식 정의문 완전 "
            "대조는 아직 아님: https://www.onetonline.org/find/descriptor/browse/1.D"
        ],
        trait_scope="shared",
        minimum_context_count=2,
        primary_vector_group="work_style",
        grounding_type="ONET_PARTIAL",
        neighboring_trait_ids=["persistence_completion", "information_comparison"],
        distinction_notes=(
            "persistence_completion은 '끝까지 가는가'(지속성)이고, detail_orientation은 "
            "'세부까지 꼼꼼히 보는가'(정확성)다 — 끝까지는 가지만 세부는 대충 볼 수도 있고, "
            "반대로 세부는 꼼꼼하지만 끝까지 못 갈 수도 있어 독립적이다."
        ),
        review_status="draft",
    ),
    # --- 변화·도전 ---
    TraitDefinition(
        trait_id="novelty_seeking",
        label="새로움 추구",
        parent_dimension="변화와 도전",
        definition="이미 익숙한 것보다 새롭고 낯선 것을 스스로 적극적으로 찾아 시도하려는 경향",
        positive_indicators=["익숙한 방법이 있어도 새로운 것을 직접 찾아보고 시도하는 선택"],
        conflicting_indicators=["익숙하고 검증된 방식을 그대로 유지하는 것을 선호"],
        aliases=[],
        source_references=["팀 정의 — O*NET/Holland 대응 항목 없음, 2026-08-23 조사"],
        trait_scope="shared",
        minimum_context_count=2,
        primary_vector_group="work_style",
        grounding_type="TEAM_DEFINED",
        neighboring_trait_ids=["change_adaptation", "challenge_seeking"],
        distinction_notes=(
            "change_adaptation은 '이미 벌어진 예상 밖 상황'에 유연하게 대응하는 수동적·반응적 "
            "경향이고, novelty_seeking은 그런 상황이 없어도 스스로 새로운 것을 찾아 나서는 "
            "능동적 경향이다 — 대응(수동) vs 탐색(능동)의 차이. challenge_seeking과는 "
            "'새로움'과 '어려움'이라는 서로 다른 축을 본다(새롭지만 쉬운 것도, 어렵지만 "
            "익숙한 것도 있을 수 있다)."
        ),
        review_status="draft",
    ),
    TraitDefinition(
        trait_id="uncertainty_tolerance",
        label="불확실성 감내",
        parent_dimension="변화와 도전",
        definition="결과나 정보가 확실하지 않아도 불안해하지 않고 그대로 진행하는 경향",
        positive_indicators=["결과를 100% 확신할 수 없어도 일단 진행하는 선택"],
        conflicting_indicators=["확실한 정보나 결과가 보장돼야만 진행함"],
        aliases=[],
        source_references=[
            "약함 — O*NET Work Style 'Stress Tolerance'와 개념이 인접하나 완전히 같지 않음"
            "(Stress Tolerance는 고강도 스트레스 상황에 침착하게 대응하는 것이고, "
            "uncertainty_tolerance는 정보·결과가 불확실한 상태 자체를 견디는 것이라 범위가 "
            "다르다): https://www.onetonline.org/find/descriptor/browse/1.D"
        ],
        trait_scope="shared",
        minimum_context_count=2,
        primary_vector_group="work_style",
        grounding_type="TEAM_DEFINED",
        neighboring_trait_ids=["change_adaptation"],
        distinction_notes=(
            "change_adaptation은 '예상과 다른 결과가 나온 뒤' 대응 방식을 바꾸는 것이고, "
            "uncertainty_tolerance는 결과가 나오기 '전' 불확실한 상태 자체를 견디는 것이다 — "
            "시점이 다르다(사후 대응 vs 사전 감내)."
        ),
        review_status="draft",
    ),
    TraitDefinition(
        trait_id="challenge_seeking",
        label="도전 선호",
        parent_dimension="변화와 도전",
        definition="쉬운 길보다 어렵고 도전적인 과제를 상대적으로 선호하는 경향",
        positive_indicators=["더 쉬운 선택지가 있어도 더 어려운 쪽을 고르는 선택"],
        conflicting_indicators=["난이도가 낮고 확실한 방법을 선호"],
        aliases=[],
        source_references=[
            "보통 — O*NET Work Style 'Achievement/Effort' 항목명 확인, 공식 정의문 완전 "
            "대조는 아직 아님: https://www.onetonline.org/find/descriptor/browse/1.D"
        ],
        trait_scope="shared",
        minimum_context_count=2,
        primary_vector_group="work_style",
        grounding_type="ONET_PARTIAL",
        neighboring_trait_ids=["novelty_seeking", "persistence_completion"],
        distinction_notes=(
            "novelty_seeking은 '새로운가'를 보고, challenge_seeking은 '어려운가'를 본다 — "
            "새롭지만 쉬운 것, 익숙하지만 어려운 것이 둘 다 있을 수 있어 서로 다른 축이다."
        ),
        review_status="draft",
    ),
    # --- 자율·의사결정 ---
    TraitDefinition(
        trait_id="independent_judgment",
        label="독립적 판단",
        parent_dimension="자율과 의사결정",
        definition="다른 사람의 지시나 의견에 기대지 않고 스스로 판단하고 실행하는 경향",
        positive_indicators=["도움을 구하기보다 스스로 방법을 정해 진행하는 선택"],
        conflicting_indicators=["다른 사람의 의견이나 지시를 먼저 구하고 그에 따름"],
        aliases=[],
        source_references=[
            "보통 — O*NET Work Style 'Independence' 항목명 확인, 공식 정의문 완전 대조는 "
            "아직 아님: https://www.onetonline.org/find/descriptor/browse/1.D"
        ],
        trait_scope="shared",
        minimum_context_count=2,
        primary_vector_group="work_style",
        grounding_type="ONET_PARTIAL",
        neighboring_trait_ids=["opinion_expression", "personal_goal_priority", "collaboration_preference"],
        distinction_notes=(
            "collaboration_preference의 반대말이 아니다 — collaboration_preference는 "
            "'혼자 vs 함께 일하는 것'에 대한 선호이고, independent_judgment는 함께 일하더라도 "
            "'판단은 스스로 내리는가'를 본다(협업하면서도 독립적으로 판단할 수 있다). "
            "opinion_expression은 판단을 '표현·주장'하는 것이고, independent_judgment는 "
            "판단을 '내리는 과정' 자체를 본다."
        ),
        review_status="draft",
    ),
    TraitDefinition(
        trait_id="opinion_expression",
        label="의견 표명",
        parent_dimension="자율과 의사결정",
        definition="자신의 생각이나 의견을 다른 사람 앞에서 명확하게 드러내어 말하는 경향",
        positive_indicators=["생각이 있으면 먼저 나서서 말하거나 제안하는 선택"],
        conflicting_indicators=["의견이 있어도 먼저 나서서 말하지 않고 다른 사람에게 맡김"],
        aliases=[],
        source_references=["팀 정의 — O*NET/Holland에 '주장성' 자체를 다루는 공식 항목 없음, 2026-08-23 조사"],
        trait_scope="shared",
        minimum_context_count=2,
        primary_vector_group="work_style",
        grounding_type="TEAM_DEFINED",
        neighboring_trait_ids=["independent_judgment", "opinion_mediation"],
        distinction_notes=(
            "opinion_mediation은 '여러 의견이 충돌할 때 조율 기준을 세우는 것'이고, "
            "opinion_expression은 조율 여부와 무관하게 '자기 의견 자체를 드러내는가'를 본다 — "
            "의견을 안 드러내도 조율은 할 수 있고, 의견은 강하게 드러내도 조율은 안 할 수 있다."
        ),
        review_status="draft",
    ),
    TraitDefinition(
        trait_id="personal_goal_priority",
        label="개인 목표 우선",
        parent_dimension="자율과 의사결정",
        definition="공동의 목표보다 자신의 목표나 기준을 상대적으로 우선하는 경향",
        positive_indicators=["공동 목표와 개인 목표가 갈릴 때 자신의 기준을 우선하는 선택"],
        conflicting_indicators=["개인 목표보다 공동·팀의 목표를 우선함"],
        aliases=[],
        source_references=["팀 정의 — O*NET/Holland 대응 항목 없음, 2026-08-23 조사"],
        trait_scope="shared",
        minimum_context_count=2,
        primary_vector_group="work_style",
        grounding_type="TEAM_DEFINED",
        neighboring_trait_ids=["independent_judgment", "collaboration_preference"],
        distinction_notes=(
            "2026-08-23 지시서 §2 원칙 3: 이 Trait는 '이기적임'의 중립적 표현이다 — 타인을 "
            "배려하지 않는 성격으로 단정하지 않는다. collaboration_preference(혼자 vs 함께 "
            "일하는 방식 선호)와는 다른 축이다 — 함께 일하는 것을 선호하면서도(협업 선호 "
            "높음) 목표 우선순위는 개인 기준을 앞세울 수 있다(독립적 차원). "
            "independent_judgment(판단을 스스로 내리는가)와도 다르다 — 판단은 남에게 맡기면서 "
            "목표만 개인 우선일 수도 있다."
        ),
        review_status="draft",
    ),
]

NEW_TRAIT_IDS_V2: set[str] = {t.trait_id for t in NEW_TRAITS_V2_DRAFT}
