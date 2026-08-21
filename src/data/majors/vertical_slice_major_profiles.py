"""Vertical Slice 대표 전공 3개의 Major Multi-Vector — 설계안 §15.

CLAUDE.md 금지 사항: "검증되지 않은 Trait·전공 Mapping을 확정 데이터로 처리"하지 않는다.
그래서 이 3개 Profile은 `review_status="draft"`로 저장한다 — §15가 요구하는 "최소 2인
독립 검토"(MappingReview)를 아직 거치지 않은, A가 Vertical Slice 배선을 완성하기 위해
직접 채운 1차 초안이다. C가 실제 학과 데이터·공식 출처로 교체하기 전까지 임시로 쓴다.

Vertical Slice Trait Ontology는 12개뿐이고 vector group 분포가 고르지 않다(interest·
environment는 각 1개 Trait뿐) — §16 계산이 이 불균형에서도 깨지지 않는지 확인하는 것도
이 초안의 목적 중 하나다. 등급은 §15 0~3 등급을 그대로 0/.33/.67/1.00로 옮겼다.
"""

from __future__ import annotations

from datetime import datetime

from src.schemas.major import MajorProfile

MEDIA_COMMUNICATION_PROFILE = MajorProfile(
    major_id="media_communication",
    label="미디어커뮤니케이션",
    interest_vector={
        "visual_expression": 1.00,  # 컨텐츠 제작의 핵심 활동
    },
    cognitive_vector={
        "causal_analysis": 0.33,
        "pattern_finding": 0.67,
        "emotional_interpretation": 1.00,  # 스토리텔링·수용자 감정 이해가 핵심 학습활동
        "audience_response_prediction": 1.00,  # 수용자 반응 예측이 핵심 학습활동
        "information_comparison": 0.67,
    },
    work_style_vector={
        "planning": 0.67,
        "immediate_execution": 0.67,
        "change_adaptation": 0.67,
        "collaboration_preference": 0.67,  # 제작은 대체로 협업 기반
        "opinion_mediation": 0.33,
    },
    environment_vector={
        "tool_utilization": 0.67,  # 촬영·편집 도구 활용
    },
    source_ids=[],
    extraction_method="manual",
    review_status="draft",
    profile_version="major_profile_v1_draft",
    updated_at=datetime(2026, 8, 21),
)

HCI_UX_PROFILE = MajorProfile(
    major_id="hci_ux",
    label="HCI·UX",
    interest_vector={
        "visual_expression": 1.00,  # 인터페이스·화면 디자인이 핵심 학습활동
    },
    cognitive_vector={
        "causal_analysis": 0.67,
        "pattern_finding": 0.67,
        "emotional_interpretation": 0.67,
        "audience_response_prediction": 1.00,  # 사용자 반응 예측·리서치가 핵심 학습활동
        "information_comparison": 0.67,
    },
    work_style_vector={
        "planning": 0.67,
        "immediate_execution": 0.33,  # 프로토타입 반복 검증이 즉흥 실행보다 계획적 성격
        "change_adaptation": 0.67,
        "collaboration_preference": 0.67,
        "opinion_mediation": 0.67,  # 이해관계자 의견 조율이 잦음
    },
    environment_vector={
        "tool_utilization": 1.00,  # 디자인·프로토타이핑 도구 활용이 핵심 학습활동
    },
    source_ids=[],
    extraction_method="manual",
    review_status="draft",
    profile_version="major_profile_v1_draft",
    updated_at=datetime(2026, 8, 21),
)

INDUSTRIAL_ENGINEERING_PROFILE = MajorProfile(
    major_id="industrial_engineering",
    label="산업공학",
    interest_vector={
        "visual_expression": 0.33,
    },
    cognitive_vector={
        "causal_analysis": 1.00,  # 원인 분석이 핵심 학습활동(공정·시스템 문제 진단)
        "pattern_finding": 1.00,  # 데이터 패턴 탐색이 핵심 학습활동
        "emotional_interpretation": 0.33,
        "audience_response_prediction": 0.33,
        "information_comparison": 1.00,  # 대안 비교·정량 분석이 핵심 학습활동
    },
    work_style_vector={
        "planning": 1.00,  # 계획·최적화가 핵심 학습활동
        "immediate_execution": 0.33,
        "change_adaptation": 0.67,
        "collaboration_preference": 0.67,
        "opinion_mediation": 0.67,
    },
    environment_vector={
        "tool_utilization": 0.67,
    },
    source_ids=[],
    extraction_method="manual",
    review_status="draft",
    profile_version="major_profile_v1_draft",
    updated_at=datetime(2026, 8, 21),
)

VERTICAL_SLICE_MAJOR_PROFILES: list[MajorProfile] = [
    MEDIA_COMMUNICATION_PROFILE,
    HCI_UX_PROFILE,
    INDUSTRIAL_ENGINEERING_PROFILE,
]
