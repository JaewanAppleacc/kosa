"""v2(24-Trait) Subject-Trait Mapping Evidence 정본 — 2026-08-23 Trait Ontology
v2(2.6단계) §8, 2026-08-25 a/subject-mapping-38-majors 지시서 확장.

`career_build_major_trait_mapping_evidence_v2.py`와 완전히 같은 원칙을 과목 단위로
적용한다: **v2 신규 12개 Trait(`_ALL_V2_TRAIT_IDS - VERTICAL_SLICE_TRAIT_IDS`)는
공식 성취기준을 아직 직접 재확인하지 않았으므로 항상 REVIEW_REQUIRED로 남긴다 —
자동 승격 금지.** 이 규칙은 원래 6개 과목뿐 아니라 이번에 새로 추가하는 모든 과목에도
그대로 적용된다(`tests/test_trait_v2_major_subject_data.py::
test_new_v2_traits_are_review_required`가 파일 전체에 대해 검사한다).

**2026-08-25 확장 전**: 대상 과목은 Vertical Slice 대표 전공 3개(media_communication/
hci_ux/industrial_engineering)에 연결된 6개뿐이었다(Legacy 12-Trait 레코드를 그대로
재사용, mapping_version만 교체).

**2026-08-25 확장 후**: 39개 서비스 Major(`data/master/service_canonical_majors_v2.jsonl`)
전부에 후보 과목을 채우기 위해 두 그룹을 추가한다.

    1. `EXPANDED_LEGACY_SUBJECT_LABELS`(11개): Legacy `subjects.jsonl`에는 이미
       있지만 이번 확장 전에는 v2 Trait 근거가 없던 과목 — Legacy 12-Trait
       레코드를 그대로 재사용한다(기존 6개와 동일한 방식).
    2. `NEW_SUBJECT_TRAIT_EVIDENCE`(24개): Legacy에 아예 없던 신규 과목 — 이번
       라운드가 2022 개정 교육과정 공식 과목 성격·목표를 근거로 **Legacy 12-Trait
       (VERTICAL_SLICE_TRAIT_IDS)만** 사용해 직접 등급을 매겼다(신규 12-Trait는
       절대 EVIDENCED로 매기지 않는다 — 이 파일의 핵심 규칙 위반이기 때문).

두 그룹 다 기존 6개와 동일하게, 신규 12-Trait는 REVIEW_REQUIRED 자리표시 행을
자동으로 채워 넣는다(완전성·감사 가능성을 6개 과목과 동일하게 유지).

실행: PYTHONPATH=. ./.venv/bin/python scripts/career_build_subject_trait_mapping_evidence_v2.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.career_console import use_utf8_stdout  # noqa: E402

from src.data.trait_ontology.vertical_slice_traits import VERTICAL_SLICE_TRAIT_IDS  # noqa: E402
from src.ids import generate_subject_id  # noqa: E402
from src.services.subject_trait_mapping_evidence import (  # noqa: E402
    SubjectTraitCurriculumEvidence,
    SubjectTraitMappingRecord,
    load_subject_trait_mapping_evidence,
)
from src.services.trait_ontology_v2 import load_trait_ontology_v2  # noqa: E402

TARGET_MAJOR_IDS = ("media_communication", "hci_ux", "industrial_engineering")
V2_MAPPING_VERSION = "subject_trait_mapping_v2"
V2_EXPANSION_MAPPING_VERSION = "subject_trait_mapping_v2_39majors"
SUBJECTS_PATH = ROOT / "data" / "master" / "subjects.jsonl"
OUTPUT_PATH = ROOT / "data" / "master" / "subject_trait_mapping_evidence_v2.jsonl"
CURRICULUM_CODE = "2022-33"  # 교육부 고시 제2022-33호 (2022 개정 교육과정)
MOE_URL = "https://www.moe.go.kr/boardCnts/viewRenew.do?boardID=141&lev=0&statusYN=W&s=moe&m=0404&opType=N&boardSeq=93458"

_NEW_TRAIT_NOTE = (
    "v2 신규 Trait — 공식 성취기준을 아직 직접 재확인하지 않았다. 2.6단계 §8 규칙대로 "
    "REVIEW_REQUIRED로 유지하며 자동 승격하지 않는다."
)

# ── 2026-08-25 확장 §1: Legacy `subjects.jsonl`에는 있고 `subject_trait_mapping_
# evidence.jsonl`(v1)에도 실제 레코드가 있는 과목 5개 — 이 5개는 v1 evidence를
# 그대로 재사용한다(기존 6개와 동일 원칙). 나머지 6개(통합과학1/물리학/생명과학/
# 미술 창작/사회문제 탐구/인간과 심리)는 원래 `career_build_subject_profiles.py`의
# `LEGACY_SUBJECTS`(손입력, v1 evidence 파일 자체가 없음)에서 왔으므로 재사용할
# v1 레코드가 없다 — `NEW_SUBJECT_TRAIT_EVIDENCE`에서 신규 과목과 같은 방식(직접
# 저작)으로 다룬다.
EXPANDED_LEGACY_SUBJECT_LABELS: tuple[str, ...] = (
    "공통국어1", "주제 탐구 독서", "공통수학1", "미적분Ⅱ", "창의 공학 설계",
)

# ── 2026-08-25 확장 §2: 신규 과목 24개 + Legacy 손입력 6개의 Trait Evidence
# (Legacy 12-Trait만 사용).
# {label: {trait_id: (grade, course_goal_or_standard, reason)}} — 근거는 각 과목의
# 2022 개정 교육과정 공식 "성격"·"목표" 서술을 사람이 짧게 인용한 것이다(조항 번호까지는
# 이번 라운드 조사 범위 밖이라 지어내지 않는다).
NEW_SUBJECT_TRAIT_EVIDENCE: dict[str, dict[str, tuple[int, str, str]]] = {
    "화학": {
        "causal_analysis": (3, "화학 반응의 규칙성과 원리 탐구", "물질 변화가 일어나는 원인과 규칙을 실험으로 설명하는 과목 목표"),
        "pattern_finding": (2, "주기율과 화학 결합의 규칙성", "원소·화합물의 성질에서 반복되는 패턴을 찾아 일반화하는 활동"),
        "tool_utilization": (2, "정량적 실험 도구 활용", "실험 기구를 정밀하게 다뤄 측정값을 얻는 활동"),
    },
    "지구과학": {
        "causal_analysis": (2, "지구 시스템 각 권역의 상호작용 원리", "대기·수권·지권 변화의 원인을 자료로 설명하는 활동"),
        "information_comparison": (3, "관측 자료 비교·해석", "여러 관측·탐사 자료를 비교해 지구 현상을 해석하는 과목 목표"),
        "pattern_finding": (2, "지질 시대·기상 변화의 주기성", "장기간 자료에서 반복되는 변화 양상을 찾는 활동"),
    },
    "행성우주과학": {
        "causal_analysis": (2, "천체 운동과 우주 현상의 원리", "행성·항성 현상이 일어나는 원인을 물리 법칙으로 설명하는 활동"),
        "pattern_finding": (2, "천체 운동의 주기성", "천체가 반복적으로 보이는 운동 패턴을 찾는 활동"),
        "information_comparison": (2, "관측 자료와 모델 비교", "여러 관측 결과와 이론 모델을 비교해 결론을 조정하는 활동"),
    },
    "기후변화와 지속가능한 세계": {
        "causal_analysis": (3, "기후변화 원인과 영향 분석", "기후변화를 일으키는 자연·인위적 원인을 자료로 규명하는 과목 목표"),
        "opinion_mediation": (2, "지속가능한 해결책에 대한 다양한 입장 조정", "이해관계가 다른 여러 주체의 입장을 조율해 대안을 모색하는 활동"),
        "planning": (2, "지속가능성을 위한 실천 계획 수립", "기후 문제 대응 방안을 계획으로 정리하는 활동"),
    },
    "융합과학 탐구": {
        "causal_analysis": (2, "여러 과학 분야를 아우르는 탐구", "생명·물질·지구 현상을 통합적 관점에서 원인을 탐구하는 과목 목표"),
        "planning": (2, "융합적 탐구 계획 수립", "스스로 탐구 주제와 절차를 계획하는 활동"),
        "pattern_finding": (2, "여러 과학 분야의 공통 원리 탐색", "서로 다른 과학 분야에서 반복되는 원리를 찾는 활동"),
    },
    "대수": {
        "pattern_finding": (3, "수·식의 구조와 규칙성", "다항식·방정식·부등식에서 반복되는 구조를 찾아 일반화하는 과목 목표"),
        "information_comparison": (2, "여러 풀이 방법 비교", "같은 문제를 다른 방법으로 풀어 비교하는 활동"),
    },
    "기하": {
        "pattern_finding": (2, "도형의 성질과 규칙", "평면·공간 도형에서 반복되는 성질을 찾아 증명하는 과목 목표"),
        "visual_expression": (2, "공간 도형의 시각적 표현", "벡터·좌표로 공간 도형을 시각적으로 표현하는 활동"),
        "tool_utilization": (2, "작도 도구 활용", "도구를 이용해 도형을 정확히 작도하는 활동"),
    },
    "인공지능 수학": {
        "pattern_finding": (3, "데이터의 수학적 구조 탐색", "인공지능 알고리즘의 수학적 원리에서 패턴을 찾는 과목 목표"),
        "causal_analysis": (2, "수학적 모델의 동작 원리 이해", "함수·행렬 등으로 모델이 동작하는 원리를 설명하는 활동"),
        "tool_utilization": (2, "수학적 도구로 문제 해결", "행렬·함수 등 수학 도구를 실제 문제에 적용하는 활동"),
    },
    "경제 수학": {
        "information_comparison": (3, "경제 현상의 수학적 분석·비교", "여러 경제 자료를 수학적으로 비교·분석하는 과목 목표"),
        "planning": (2, "합리적 의사결정을 위한 수리적 계획", "제한된 자원에서 최적의 선택을 수리적으로 계획하는 활동"),
    },
    "정치": {
        "opinion_mediation": (3, "서로 다른 정치적 입장 조정", "이해관계가 다른 정치 주체 간 입장을 조율하는 과목 목표"),
        "causal_analysis": (2, "정치 제도와 현상의 원리", "정치 제도가 작동하는 원리와 원인을 분석하는 활동"),
        "information_comparison": (2, "정치 자료 비교", "여러 정치 현상 관련 자료를 비교하는 활동"),
    },
    "법과 사회": {
        "information_comparison": (3, "법 조항과 판례 비교·해석", "관련 법 조항과 실제 사례를 비교해 해석하는 과목 목표"),
        "causal_analysis": (2, "법 원리의 배경 이해", "법 조항이 만들어진 원인과 배경을 이해하는 활동"),
        "opinion_mediation": (2, "법적 해석 차이 조정", "서로 다른 법적 해석 사이에서 공통점을 찾는 활동"),
    },
    "경제": {
        "causal_analysis": (3, "경제 현상의 원인과 결과 분석", "수요·공급 등 경제 현상이 일어나는 원인을 설명하는 과목 목표"),
        "information_comparison": (2, "경제 지표 비교·해석", "여러 경제 지표를 비교해 상황을 판단하는 활동"),
        "planning": (2, "합리적 선택을 위한 계획", "제한된 자원 안에서 우선순위를 정해 선택하는 활동"),
    },
    "국제 관계의 이해": {
        "information_comparison": (2, "국제 사회 여러 행위자의 입장 비교", "국가·국제기구 등 행위자의 입장을 비교하는 활동"),
        "opinion_mediation": (2, "국제 갈등에서 다양한 입장 조정", "서로 다른 국가 간 입장을 조율하는 방안을 탐구하는 과목 목표"),
        "causal_analysis": (2, "국제 이슈의 원인 이해", "국제 이슈가 발생한 배경과 원인을 분석하는 활동"),
    },
    "여행지리": {
        "information_comparison": (2, "지역별 여행 정보 비교·탐색", "여러 지역의 지리·문화 정보를 비교해 탐구하는 활동"),
        "planning": (2, "여행 경로·일정 계획", "스스로 여행 주제와 경로를 계획하는 과목 목표"),
        "change_adaptation": (2, "낯선 지역·환경 적응", "익숙하지 않은 지역과 환경에 적응하며 탐구하는 과목 성격"),
    },
    "인문학과 윤리": {
        "information_comparison": (2, "다양한 사상·관점 비교", "여러 철학자·사상의 관점을 비교해 탐구하는 과목 목표"),
        "opinion_mediation": (2, "서로 다른 사상 사이의 공통점 탐색", "대립하는 사상 사이에서 공통 지점을 찾는 활동"),
        "causal_analysis": (2, "윤리적 딜레마의 배경 이해", "윤리적 딜레마가 발생하는 배경과 원인을 이해하는 활동"),
    },
    "사회와 문화": {
        "information_comparison": (2, "사회·문화 현상 비교 분석", "여러 사회 집단의 문화 현상을 비교해 분석하는 과목 목표"),
        "causal_analysis": (2, "사회 문제의 원인 탐구", "사회 현상이 나타나는 원인을 자료로 설명하는 활동"),
        "opinion_mediation": (2, "문화 다양성에 대한 입장 조정", "서로 다른 문화적 관점 사이에서 공통점을 찾는 활동"),
    },
    "한국지리 탐구": {
        "information_comparison": (2, "지역별 지리 자료 비교", "여러 지역의 지리 정보를 비교·탐구하는 과목 목표"),
        "causal_analysis": (2, "지역 특성의 형성 원인", "지역의 지리적 특성이 형성된 원인을 설명하는 활동"),
        "pattern_finding": (2, "지역 간 반복되는 지리적 패턴", "여러 지역에서 반복되는 지리적 특징을 찾는 활동"),
    },
    "로봇과 공학세계": {
        "tool_utilization": (3, "로봇 설계·제작 도구 활용", "센서·구동장치 등 공학 도구를 다뤄 로봇을 제작하는 과목 목표"),
        "causal_analysis": (2, "로봇 동작 원리 이해", "로봇이 동작하는 원리를 회로·프로그램으로 설명하는 활동"),
        "planning": (2, "설계-제작 계획 수립", "로봇 제작 절차를 계획하고 단계적으로 수행하는 활동"),
    },
    "생활과학 탐구": {
        "information_comparison": (2, "생활 속 과학 현상 자료 비교", "의식주 관련 현상을 자료로 비교·탐구하는 과목 목표"),
        "causal_analysis": (2, "생활 속 현상의 원리 탐구", "일상생활 속 과학적 원리를 실험으로 설명하는 활동"),
        "tool_utilization": (2, "정밀한 실험·측정 도구 활용", "재료·성분을 다루는 실습 도구를 정밀하게 활용하는 활동"),
    },
    "문학": {
        "information_comparison": (2, "작품 간 비교 감상", "여러 작품을 비교하며 감상하는 과목 목표"),
        "emotional_interpretation": (2, "인물의 정서·심리 해석", "작품 속 인물의 감정과 심리를 해석하는 활동"),
        "causal_analysis": (2, "작품 속 사건의 인과관계 파악", "작품 속 사건이 전개되는 원인과 결과를 파악하는 활동"),
    },
    "문학과 영상": {
        "audience_response_prediction": (2, "영상화된 작품의 수용자 반응 탐구", "관객·독자가 작품에 어떻게 반응하는지 탐구하는 활동"),
        "visual_expression": (2, "문학의 영상적 재구성", "문학 작품을 영상 언어로 표현·재구성하는 과목 목표"),
        "information_comparison": (2, "원작과 각색 비교", "원작 문학과 영상화 작품을 비교하는 활동"),
    },
    "영어 발표와 토론": {
        "information_comparison": (2, "발표를 위한 자료 조사·비교", "발표 주제와 관련된 자료를 조사하고 비교하는 활동"),
        "opinion_mediation": (3, "영어 토론에서 입장 조율", "영어로 토론하며 서로 다른 의견 사이 절충점을 찾는 과목 목표"),
    },
    "중국어": {
        "information_comparison": (2, "모국어와 다른 언어 구조 비교", "중국어와 한국어의 표현 구조를 비교하는 활동"),
        "change_adaptation": (2, "새로운 언어·문화 체계 적응", "낯선 언어 체계와 문화에 적응하며 학습하는 과목 성격"),
    },
    "보건": {
        "information_comparison": (2, "보건 정보 비교·판단", "여러 보건 정보를 비교해 신뢰도를 판단하는 활동"),
        "tool_utilization": (2, "응급처치 도구·절차 활용", "응급처치 도구와 절차를 정확히 활용하는 과목 목표"),
        "causal_analysis": (2, "건강 문제의 원인 이해", "질병·건강 문제가 발생하는 원인을 이해하는 활동"),
    },
    # --- Legacy `career_build_subject_profiles.py::LEGACY_SUBJECTS`(손입력, v1
    # evidence 파일 자체가 없던 6개) — 그 손입력 등급·근거를 그대로 옮긴다(재조사하지
    # 않는다, §14 "새로운 과목 대량 수집 안 함"과 같은 정신). Legacy Trait id가 전부
    # VERTICAL_SLICE_TRAIT_IDS 안에 있어 그대로 EVIDENCED로 옮길 수 있다.
    "통합과학1": {
        "causal_analysis": (2, "현상의 원리 관찰·설명", "현상의 원리를 관찰·설명하는 공통과목 목표"),
        "pattern_finding": (2, "통합적 자연 현상의 규칙성", "여러 자연 현상에서 공통 규칙을 찾는 활동"),
    },
    "물리학": {
        "causal_analysis": (3, "실험을 통한 원인-결과 규명", "실험으로 원인-결과를 규명하는 과목 목표"),
        "tool_utilization": (2, "실험 장치 활용", "측정 장치를 다뤄 물리량을 구하는 활동"),
        "pattern_finding": (2, "물리 법칙의 규칙성", "여러 현상에서 공통된 물리 법칙을 찾는 활동"),
    },
    "생명과학": {
        "causal_analysis": (3, "생명 현상의 원인 설명", "관찰 자료에서 규칙을 찾고 원인을 설명하는 과목 목표"),
        "pattern_finding": (3, "생명 현상의 규칙 발견", "생명 현상에서 반복되는 규칙을 찾는 활동"),
        "information_comparison": (2, "생명 관련 자료 비교", "여러 생명과학 자료를 비교·해석하는 활동"),
    },
    "미술 창작": {
        "visual_expression": (3, "시각적 표현 활동", "시각적 표현이 과목 목표 자체인 창작 활동"),
        "audience_response_prediction": (2, "감상자 반응을 고려한 창작", "작품을 볼 사람의 반응을 고려해 창작하는 활동"),
    },
    "사회문제 탐구": {
        "causal_analysis": (3, "사회 현상의 원인 규명", "사회 현상의 원인을 자료로 규명하는 과목 목표"),
        "information_comparison": (3, "사회 자료 비교·탐구", "여러 사회 자료를 비교해 탐구하는 활동"),
        "opinion_mediation": (2, "사회 문제에 대한 입장 조정", "서로 다른 입장 사이에서 공통점을 찾는 활동"),
    },
    "인간과 심리": {
        "emotional_interpretation": (3, "행동·정서 해석", "행동과 정서를 해석하는 과목 목표"),
        "causal_analysis": (2, "심리 현상의 원인 탐구", "심리 현상이 나타나는 원인을 탐구하는 활동"),
        "audience_response_prediction": (2, "타인의 반응 예측", "타인이 특정 상황에 어떻게 반응할지 예측하는 활동"),
    },
}


def _legacy_subjects_index(subjects_path: Path = SUBJECTS_PATH) -> dict[str, dict]:
    subjects = [json.loads(line) for line in subjects_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {s["subject_id"]: s for s in subjects}


def _target_subject_ids(subjects_path: Path = SUBJECTS_PATH) -> list[str]:
    index = _legacy_subjects_index(subjects_path)
    expanded_ids = {generate_subject_id(CURRICULUM_CODE, label) for label in EXPANDED_LEGACY_SUBJECT_LABELS}
    ids = {
        s["subject_id"] for s in index.values()
        if any(m in s.get("related_major_ids", []) for m in TARGET_MAJOR_IDS)
    } | expanded_ids
    return sorted(ids)


def _new_subject_records(all_trait_ids: list[str]) -> list[SubjectTraitMappingRecord]:
    """`NEW_SUBJECT_TRAIT_EVIDENCE`(Legacy에 없던 신규 과목)의 EVIDENCED 행 +
    신규 12-Trait REVIEW_REQUIRED 자리표시 행을 만든다. Legacy 12-Trait만 EVIDENCED로
    쓸 수 있다는 규칙을 Fail-Fast로 강제한다."""

    new_v2_trait_ids = sorted(set(all_trait_ids) - VERTICAL_SLICE_TRAIT_IDS)
    records: list[SubjectTraitMappingRecord] = []
    for label, trait_grades in NEW_SUBJECT_TRAIT_EVIDENCE.items():
        subject_id = generate_subject_id(CURRICULUM_CODE, label)
        forbidden = set(trait_grades) & set(new_v2_trait_ids)
        if forbidden:
            raise SystemExit(
                f"{label}: 신규 v2 Trait({sorted(forbidden)})는 EVIDENCED로 매길 수 없다 — "
                "REVIEW_REQUIRED로만 남겨야 한다(공식 성취기준 재확인 전)"
            )
        for trait_id, (grade, goal, reason) in sorted(trait_grades.items()):
            records.append(
                SubjectTraitMappingRecord(
                    subject_id=subject_id, trait_id=trait_id, mapping_status="EVIDENCED", grade=grade,
                    curriculum_evidence=[
                        SubjectTraitCurriculumEvidence(
                            source_url=MOE_URL, source_type="OFFICIAL_CURRICULUM_MOE_NOTICE",
                            course_goal_or_standard=goal, reason=reason,
                        )
                    ],
                    activity_summary=reason, author_id="worker_a", review_status="draft",
                    mapping_version=V2_EXPANSION_MAPPING_VERSION,
                    note="39개 서비스 Major 확장(a/subject-mapping-38-majors) — 사람 검토 전 draft.",
                )
            )
        for trait_id in new_v2_trait_ids:
            records.append(
                SubjectTraitMappingRecord(
                    subject_id=subject_id, trait_id=trait_id, mapping_status="REVIEW_REQUIRED",
                    grade=None, curriculum_evidence=[], activity_summary="", author_id="worker_a",
                    review_status="draft", mapping_version=V2_EXPANSION_MAPPING_VERSION, note=_NEW_TRAIT_NOTE,
                )
            )
    return records


def build(
    legacy_records: list[SubjectTraitMappingRecord] | None = None,
    all_trait_ids: list[str] | None = None,
    target_subject_ids: list[str] | None = None,
) -> list[SubjectTraitMappingRecord]:
    legacy_records = legacy_records if legacy_records is not None else load_subject_trait_mapping_evidence()
    all_trait_ids = all_trait_ids if all_trait_ids is not None else [t.trait_id for t in load_trait_ontology_v2()]
    target_subject_ids = target_subject_ids if target_subject_ids is not None else _target_subject_ids()

    legacy_by_subject: dict[str, list[SubjectTraitMappingRecord]] = {}
    for record in legacy_records:
        if record.subject_id in target_subject_ids:
            legacy_by_subject.setdefault(record.subject_id, []).append(record)
    for subject_id in target_subject_ids:
        if subject_id not in legacy_by_subject:
            raise SystemExit(
                f"{subject_id}: 기존 subject_trait_mapping_evidence.jsonl에 레코드가 "
                "하나도 없다 — 재사용할 값이 없다"
            )

    new_v2_trait_ids = sorted(set(all_trait_ids) - VERTICAL_SLICE_TRAIT_IDS)

    records: list[SubjectTraitMappingRecord] = []
    for subject_id in target_subject_ids:
        for legacy in sorted(legacy_by_subject.get(subject_id, []), key=lambda r: r.trait_id):
            records.append(legacy.model_copy(update={"mapping_version": V2_MAPPING_VERSION}))

        for trait_id in new_v2_trait_ids:
            records.append(
                SubjectTraitMappingRecord(
                    subject_id=subject_id, trait_id=trait_id, mapping_status="REVIEW_REQUIRED",
                    grade=None, curriculum_evidence=[], activity_summary="", author_id="worker_a",
                    review_status="draft", mapping_version=V2_MAPPING_VERSION, note=_NEW_TRAIT_NOTE,
                )
            )

    records.extend(_new_subject_records(all_trait_ids))
    return records


def main() -> None:
    records = build()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("".join(r.model_dump_json() + "\n" for r in records), encoding="utf-8")
    print(f"{OUTPUT_PATH.relative_to(ROOT)}: {len(records)}행 생성")


if __name__ == "__main__":
    use_utf8_stdout()
    main()
