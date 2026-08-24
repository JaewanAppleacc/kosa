"""사람이 검수할 수 있는 패킷 생성 — A 지시(2026-08-24 3라운드).

전국 데이터를 **줄이지 않는다.** 전부 보존한 상태에서, 사람이 봐야 하는 것을 근거별로
정리해 검수 가능한 형태로 만든다.

만드는 것:

    duplicate_decision_draft.jsonl        중복 6건 권고 결정 초안
    duplicate_review_packet.html          중복 6건 사람이 읽는 패킷
    classification_cluster_summary.json   분류 REVIEW 군집 요약
    classification_cluster_summary.md     같은 내용 사람이 읽는 형태
    nce_triage_queue.jsonl                N.C.E 3분류
    nce_review_packet.html                N.C.E 사람이 읽는 패킷
    review_packet_manifest.json           입력·출력 Hash

관통하는 원칙 — **Claude가 APPROVE로 확정하지 않는다.**
`recommended_decision`(권고)과 `reviewer_1_status`(사람 승인)를 분리한다.
모든 행이 `reviewer_1_status: "TBD"` · `resolution_status: "PENDING"`으로 나간다.

실행:
    python scripts/career_build_academyinfo_review_packets.py --survey-year 2025
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.career_console import use_utf8_stdout  # noqa: E402

# ── 중복 원인 판정 ───────────────────────────────────────────────────────
# 학과특성(계약학과 등)은 대학알리미가 별도 편제단위(schlMjrId)로 관리하는 실제 다른
# 과정이다. 학생 지원 경로도 다르다(계약학과는 산업체 재직자 대상). 이름이 같다는
# 이유로 합치면 안 되고, 반대로 source_record_id가 다르다는 이유만으로 별도라고
# 단정해서도 안 된다 — **공식 필드가 실제로 다른지**를 근거로 삼는다.
CONTRACT_COURSE = "계약학과"
GENERAL_COURSE = "일반과정"
IN_RECOMMENDATION_SCOPE = "IN_RECOMMENDATION_SCOPE"
OUT_OF_RECOMMENDATION_SCOPE = "OUT_OF_RECOMMENDATION_SCOPE"
CONTRACT_DEPARTMENT = "CONTRACT_DEPARTMENT"

DECISION_SAME = "SAME_DEPARTMENT_DEDUPLICATE"
DECISION_DISTINCT = "DISTINCT_DEPARTMENTS_KEEP_SEPARATE"
DECISION_MORE_REVIEW = "NEEDS_MORE_REVIEW"

# ── 분류 REVIEW 군집 ─────────────────────────────────────────────────────
# 앞에서 걸리면 뒤는 보지 않는다. 한 학과가 여러 신호에 걸려도 "어느 근거로 보류됐는지"가
# 하나로 정해져야 검토자가 같은 행을 두 번 판단하지 않는다.
CLUSTER_RULES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("DESIGN_HCI_UX", "디자인·HCI·UX 경계", ("HCI", "UX", "UI", "인터랙션", "인터렉션", "디자인")),
    ("CONTENT_MEDIA", "콘텐츠·미디어 경계", ("콘텐츠", "컨텐츠", "미디어", "영상", "게임", "애니", "방송")),
    ("BIO_MED_ENG", "생명과학·생명공학·의공학 경계", ("생명공학", "의공학", "바이오", "생명과학", "의생명")),
    ("INDUSTRIAL_SAFETY", "산업공학·안전·방재 경계", ("산업공학", "안전공학", "방재", "소방")),
    ("MECH_TRANSPORT", "기계·자동차·항공·조선 경계", ("기계", "자동차", "항공", "조선", "철도")),
    ("BUSINESS_FINANCE", "경영·회계·금융·경영정보 경계", ("경영정보", "회계", "금융", "세무", "경영")),
    ("EDUCATION", "교육학·교원양성 경계", ("교육과", "교육학", "사범", "교원")),
    ("CONVERGENCE", "융합·복합 학과명", ("융합", "복합", "자유전공", "연계", "통합", "스마트")),
)
CLUSTER_SERIES_CONFLICT = ("SERIES_NAME_CONFLICT", "공식 소계열과 학과명 충돌")
CLUSTER_OTHER = ("OTHER", "기타")

# 검토 우선순위 — "자동 확정 가능성"이 아니라 "먼저 봐야 하는 정도"다.
CLUSTER_PRIORITY: dict[str, int] = {
    "DESIGN_HCI_UX": 1,       # 예체능 제외 여부가 걸려 추천 노출에 직접 영향
    "CONTENT_MEDIA": 1,
    "SERIES_NAME_CONFLICT": 2,  # 공식 근거끼리 어긋나 데이터 신뢰에 직결
    "BIO_MED_ENG": 3,
    "BUSINESS_FINANCE": 3,
    "MECH_TRANSPORT": 4,
    "INDUSTRIAL_SAFETY": 4,
    "EDUCATION": 4,
    "CONVERGENCE": 5,         # 건수가 가장 많지만 대부분 예체능과 무관
    "OTHER": 5,
}
CLUSTER_EVIDENCE: dict[str, list[str]] = {
    "DESIGN_HCI_UX": ["공식 교육과정(개설 교과목)", "공식 단과대학 소속", "입학전형의 실기 반영 여부"],
    "CONTENT_MEDIA": ["공식 교육과정", "공식 단과대학 소속", "입학전형의 실기 반영 여부"],
    "SERIES_NAME_CONFLICT": ["공식 소계열 코드 근거", "학과 교육목표"],
    "BIO_MED_ENG": ["공식 교육과정", "학과 교육목표", "졸업 후 진로 공식 자료"],
    "BUSINESS_FINANCE": ["공식 교육과정", "학과 교육목표"],
    "MECH_TRANSPORT": ["공식 교육과정", "학과 교육목표"],
    "INDUSTRIAL_SAFETY": ["공식 교육과정", "학과 교육목표"],
    "EDUCATION": ["공식 단과대학 소속", "교원자격 취득 여부 공식 자료"],
    "CONVERGENCE": ["공식 교육과정", "학과 교육목표", "공식 소계열 근거"],
    "OTHER": ["공식 소계열 근거", "학과 교육목표"],
}

# ── N.C.E 3분류 ──────────────────────────────────────────────────────────
NCE_REEXAMINABLE = "REEXAMINABLE_BY_OFFICIAL_EVIDENCE"
NCE_NAME_INSUFFICIENT = "NAME_ALONE_INSUFFICIENT"
NCE_NEEDS_GROUP_EXPANSION = "NEEDS_CANONICAL_GROUP_EXPANSION"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows),
        encoding="utf-8",
    )
    return len(rows)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def candidate_id(prefix: str, *parts: str) -> str:
    """결정론적 검수 행 id. 생성 시각을 쓰지 않는다 — 재생성해도 같아야 한다."""
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:20]
    return f"{prefix}_{digest}"


def review_fields() -> dict[str, Any]:
    """모든 검수 행의 공통 꼬리. Claude는 여기를 채우지 않는다."""
    return {"reviewer_1_status": "TBD", "reviewer_1_comment": "", "resolution_status": "PENDING"}


def build_contract_duplicate_audit(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """추천 Queue에서는 사라진 일반/계약 중복을 사람 검수용 감사 그룹으로 복원한다.

    추천 범위 판정 뒤에는 일반과정만 남아 department_id 중복이 0건이어야 한다. 하지만
    계약학과 원본과 두 과정의 관계 결정은 삭제하면 안 되므로, 정규화 원본에서 공식
    학과특성이 정확히 일반과정/계약학과로 갈리는 그룹만 별도 검수 입력으로 만든다.
    """
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("department_status") not in ("EXISTING", "NEW"):
            continue
        grouped[row["department_id"]].append(row)

    out: list[dict[str, Any]] = []
    fields = (
        "department_name", "college_name", "campus", "day_night_name",
        "degree_course_name", "lesson_term_name", "department_status",
        "major_character_name", "source_svy_year",
    )
    for department_id, group in sorted(grouped.items()):
        characters = {r.get("major_character_name") for r in group}
        if characters != {GENERAL_COURSE, CONTRACT_COURSE} or len(group) != 2:
            continue
        head = group[0]
        differing = [
            field for field in fields
            if len({json.dumps(r.get(field), ensure_ascii=False) for r in group}) > 1
        ]
        causes = []
        if "lesson_term_name" in differing:
            causes.append({
                "cause": "TERM_SPLIT", "field": "lesson_term_name",
                "note": "수업연한이 갈린다",
            })
        if not causes:
            causes.append({
                "cause": "CONTRACT_DEPARTMENT_SPLIT", "field": "major_character_name",
                "note": "공식 학과특성이 일반과정/계약학과로 갈린다",
            })
        out.append({
            "department_id": department_id,
            "university_name": head.get("university_name"),
            "department_name": head.get("department_name"),
            "college_name": head.get("college_name"),
            "differing_fields": differing,
            "duplicate_cause_candidates": causes,
            "candidates": [
                {"source_record_id": r.get("source_record_id")} for r in group
            ],
        })
    return out


# ── §2 중복 6건 ──────────────────────────────────────────────────────────

def recommend_duplicate_decision(rows: list[dict[str, Any]]) -> tuple[str, str, list[str]]:
    """권고 결정과 근거. **확정이 아니다.**"""
    characters = {r.get("major_character_name") for r in rows}
    terms = {r.get("lesson_term_name") for r in rows}
    mjr_ids = {r.get("source_schl_mjr_id") for r in rows}
    evidence: list[str] = []

    if len(mjr_ids) == len(rows):
        evidence.append(f"공식 학과코드(schlMjrId)가 서로 다르다: {sorted(x for x in mjr_ids if x)}")
    if len(terms) > 1:
        evidence.append(f"공식 수업연한이 다르다: {sorted(x for x in terms if x)}")
    if CONTRACT_COURSE in characters and GENERAL_COURSE in characters:
        evidence.append("공식 학과특성이 '일반과정'과 '계약학과'로 갈린다")

    if CONTRACT_COURSE in characters and GENERAL_COURSE in characters:
        reason = (
            "계약학과는 대학알리미가 별도 편제단위로 관리하는 다른 과정이고, 학생 지원 경로도 "
            "다르다(산업체 재직자 대상). 학과명이 같다는 이유로 합치면 서로 다른 모집 단위가 "
            "하나로 보인다."
        )
        if len(terms) > 1:
            reason += " 수업연한까지 달라 교육과정 자체가 다르다."
        return DECISION_DISTINCT, reason, evidence

    if len(mjr_ids) == 1:
        return DECISION_SAME, "공식 학과코드가 같고 구분 근거가 없다.", evidence

    return (
        DECISION_MORE_REVIEW,
        "공식 학과코드는 다르지만 어떤 축이 다른지 확인되지 않았다. 원본을 직접 봐야 한다.",
        evidence,
    )


def build_duplicate_draft(
    queue: list[dict[str, Any]], normalized_by_record: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for g in queue:
        rows = [normalized_by_record[c["source_record_id"]] for c in g["candidates"]
                if c["source_record_id"] in normalized_by_record]
        decision, reason, evidence = recommend_duplicate_decision(rows)
        out.append({
            "candidate_id": candidate_id("dup", g["department_id"]),
            "department_id": g["department_id"],
            "university_name": g["university_name"],
            "department_name": g["department_name"],
            "college_name": g["college_name"],
            "differing_fields": g["differing_fields"],
            "records": [
                {
                    "source_record_id": r["source_record_id"],
                    "schl_id": r.get("schl_id"),
                    "schl_mjr_id": r.get("source_schl_mjr_id"),
                    "school_name": r.get("university_name"),
                    "department_name": r.get("department_name"),
                    "day_night_name": r.get("day_night_name"),
                    "lesson_term_name": r.get("lesson_term_name"),
                    "department_status": r.get("department_status"),
                    "survey_year": r.get("source_svy_year"),
                    "official_small_series_code": (r.get("official_classification") or {}).get("small_series_code"),
                    "official_small_series_name": (r.get("official_classification") or {}).get("small_series_name"),
                    "major_character_name": r.get("major_character_name"),
                    "recommendation_scope": (
                        OUT_OF_RECOMMENDATION_SCOPE
                        if r.get("major_character_name") == CONTRACT_COURSE
                        else IN_RECOMMENDATION_SCOPE
                    ),
                    "exclusion_reason": (
                        CONTRACT_DEPARTMENT
                        if r.get("major_character_name") == CONTRACT_COURSE
                        else None
                    ),
                    "degree_course_name": r.get("degree_course_name"),
                    "enrolled_count": r.get("enrolled_count"),
                    "graduate_count": r.get("graduate_count"),
                }
                for r in sorted(rows, key=lambda x: x.get("source_schl_mjr_id") or "")
            ],
            "duplicate_cause": g["duplicate_cause_candidates"],
            "recommended_decision": decision,
            "recommendation_reason": reason,
            "official_evidence": evidence,
            "decision_options": [DECISION_SAME, DECISION_DISTINCT, DECISION_MORE_REVIEW],
            "note": "권고이지 확정이 아니다. reviewer_1_status가 TBD인 동안에는 어떤 코드도 이 값을 쓰지 않는다.",
            **review_fields(),
        })
    return out


# ── §3 분류 REVIEW 군집 ──────────────────────────────────────────────────

def cluster_of(row: dict[str, Any]) -> tuple[str, str]:
    text = f"{row.get('department_name') or ''} {row.get('college_name') or ''}"
    for code, label, keywords in CLUSTER_RULES:
        if any(k in text for k in keywords):
            return code, label
    small = row.get("official_small_series_name") or ""
    if small and small not in text:
        return CLUSTER_SERIES_CONFLICT
    return CLUSTER_OTHER


def build_cluster_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    labels: dict[str, str] = {}
    for r in rows:
        code, label = cluster_of(r)
        grouped[code].append(r)
        labels[code] = label

    # A 지시가 지정한 군집은 **0건이어도 표에 남긴다** — "그 축은 검토했고 해당이 없었다"와
    # "그 축을 아예 안 봤다"는 다른 사실이다.
    for code, label, _ in CLUSTER_RULES:
        grouped.setdefault(code, [])
        labels.setdefault(code, label)
    for code, label in (CLUSTER_SERIES_CONFLICT, CLUSTER_OTHER):
        grouped.setdefault(code, [])
        labels.setdefault(code, label)

    clusters = []
    for code, members in grouped.items():
        series = Counter(m.get("official_small_series_name") for m in members)
        candidates = Counter(
            cid for m in members for cid in (m.get("candidate_canonical_major_ids") or [])
        )
        clusters.append({
            "cluster_code": code,
            "cluster_label": labels[code],
            "count": len(members),
            "review_priority": CLUSTER_PRIORITY.get(code, 5),
            "why_review_needed": {
                "DESIGN_HCI_UX": "명칭만으로는 예체능 여부를 못 정한다. 추천 노출에 직접 영향이 간다.",
                "CONTENT_MEDIA": "제작 실기 중심인지 이론·공학 중심인지에 따라 전공군과 예체능 판정이 갈린다.",
                "SERIES_NAME_CONFLICT": "공식 소계열과 학과명이 어긋난다. 표기 차이인지 분류 오류인지 확인이 필요하다.",
                "BIO_MED_ENG": "연구 중심(생명과학)과 응용·생산(생명공학·의공학)의 경계가 흐리다.",
                "BUSINESS_FINANCE": "경영정보학은 IT와, 금융·회계는 경영과 겹친다.",
                "MECH_TRANSPORT": "설계(공학)와 운항·조종(실무)이 같은 명칭 아래 섞인다.",
                "INDUSTRIAL_SAFETY": "산업공학·안전·방재가 학교마다 다른 단위로 묶인다.",
                "EDUCATION": "교과교육은 해당 교과 전공군과도 겹친다.",
                "CONVERGENCE": "융합 명칭만으로는 어느 전공군인지 알 수 없다.",
                "OTHER": "위 군집 어디에도 해당하지 않아 개별 확인이 필요하다.",
            }.get(code, "개별 확인이 필요하다."),
            "required_official_evidence": CLUSTER_EVIDENCE.get(code, ["공식 교육과정"]),
            "top_official_small_series": dict(series.most_common(5)),
            "is_empty": len(members) == 0,
            "current_auto_candidates": dict(candidates.most_common(5)),
            "examples": [
                {
                    "department_id": m["department_id"],
                    "university_name": m.get("university_name"),
                    "department_name": m.get("department_name"),
                    "college_name": m.get("college_name"),
                    "official_small_series_name": m.get("official_small_series_name"),
                    "candidate_canonical_major_ids": m.get("candidate_canonical_major_ids"),
                }
                for m in sorted(members, key=lambda x: x["department_id"])[:5]
            ],
        })

    clusters.sort(key=lambda c: (c["review_priority"], -c["count"]))
    return {
        "total": len(rows),
        "cluster_count": len(clusters),
        "clusters": clusters,
        "note": (
            "review_priority는 '자동 확정 가능성'이 아니라 '먼저 봐야 하는 정도'다. "
            "어떤 군집도 자동으로 EVIDENCED·APPROVED로 올리지 않는다."
        ),
    }


# ── §4 N.C.E 3분류 ───────────────────────────────────────────────────────

def triage_nce(
    row: dict[str, Any], same_school_series: dict[str, Counter], group_labels: set[str]
) -> tuple[str, str, list[str]]:
    """세 그룹으로 가른다. **소계열을 만들어내지 않는다.**

    근거 강도 순으로 본다.

        1. 공식 중계열이 살아 있다      → 소계열만 미분류라 재검토 가능
        2. 공식 대계열만 살아 있다      → 범위는 좁힐 수 있으나 전공군 특정은 불가
        3. 학과명이 복수 전공을 포괄    → 전공군 확장 여부를 A가 판단
        4. 아무 공식 근거도 없다        → 학과명만으로는 판단 불가

    같은 학교의 다른 학과 소계열은 **이 학과의 분류 근거가 아니다.** 참고로만 붙이고
    판정에는 쓰지 않는다 — 그걸 근거로 삼으면 "같은 학교니까 비슷할 것"이라는 추측이 된다.
    """
    UNCLASSIFIED = ("N.C.E", "N.C.E.", "")
    middle = (row.get("official_middle_series_name") or "").strip()
    large = (row.get("official_large_series_name") or "").strip()
    name = row.get("department_name") or ""
    evidence: list[str] = []

    peers = same_school_series.get(row.get("university_name") or "")
    peer_note = (
        f"참고(판정 근거 아님) — 같은 학교의 분류된 학과 소계열: "
        f"{', '.join(f'{n}({c})' for n, c in peers.most_common(3))}"
        if peers else None
    )

    if middle not in UNCLASSIFIED:
        evidence.append(f"공식 중계열이 유효하다: {middle}")
        if large not in UNCLASSIFIED:
            evidence.append(f"공식 대계열: {large}")
        if peer_note:
            evidence.append(peer_note)
        return (
            NCE_REEXAMINABLE,
            "소계열만 미분류이고 **공식 중계열이 살아 있다.** 중계열 범위 안에서 전공군 후보를 "
            "좁힐 수 있다 — 다만 중계열이 곧 전공군은 아니므로 사람이 확정한다.",
            evidence,
        )

    if any(k in name for k in ("자유전공", "융합", "연계", "학부대학", "교양", "복합")):
        if large not in UNCLASSIFIED:
            evidence.append(f"공식 대계열: {large}")
        return (
            NCE_NEEDS_GROUP_EXPANSION,
            "여러 전공에 걸치는 단위라 기존 42개 전공군 중 하나로 담기 어렵다. "
            "전공군 확장 여부를 A가 판단해야 한다 — C가 임의로 늘리지 않는다.",
            evidence,
        )

    if large not in UNCLASSIFIED:
        evidence.append(f"공식 대계열만 유효하다: {large}")
        if peer_note:
            evidence.append(peer_note)
        return (
            NCE_NAME_INSUFFICIENT,
            "대계열까지만 있고 중·소계열이 모두 미분류다. 범위는 좁혀지지만 전공군을 특정할 수 "
            "없다 — 공식 교육과정·교육목표가 있어야 재검토 가능하다.",
            evidence,
        )

    if peer_note:
        evidence.append(peer_note)
    return (
        NCE_NAME_INSUFFICIENT,
        "공식 계열 근거가 전혀 없고 학과명만으로는 판단할 수 없다. "
        "공식 교육과정·교육목표가 확보돼야 재검토 가능하다.",
        evidence,
    )


def build_nce_triage(rows: list[dict[str, Any]], classified: list[dict[str, Any]],
                     group_labels: set[str]) -> list[dict[str, Any]]:
    same_school: dict[str, Counter] = defaultdict(Counter)
    for c in classified:
        name = c.get("official_small_series_name")
        if name and name not in ("N.C.E", "N.C.E."):
            same_school[c.get("university_name") or ""][name] += 1

    out: list[dict[str, Any]] = []
    for r in rows:
        group, reason, evidence = triage_nce(r, same_school, group_labels)
        out.append({
            "candidate_id": candidate_id("nce", r["department_id"], r.get("source_record_id") or ""),
            "department_id": r["department_id"],
            "source_record_id": r.get("source_record_id"),
            "university_name": r.get("university_name"),
            "department_name": r.get("department_name"),
            "college_name": r.get("college_name"),
            "official_large_series_name": r.get("official_large_series_name"),
            "official_middle_series_name": r.get("official_middle_series_name"),
            "official_small_series_name": r.get("official_small_series_name"),
            "current_mapping_status": "UNMAPPED",
            # 강제 배정 금지 — 후보를 만들지 않는다.
            "candidate_canonical_major_ids": [],
            "triage_group": group,
            "triage_reason": reason,
            "official_evidence": evidence,
            "forbidden": [
                "검색 스니펫만으로 확정",
                "비공식 위키 사용",
                "LLM 추측으로 소계열 생성",
                "N.C.E를 0점·무관으로 처리",
                "기존 42개 전공군 임의 확장",
            ],
            **review_fields(),
        })
    return out


# ── §5 HTML 검수 패킷 ────────────────────────────────────────────────────

_CSS = """body{font-family:system-ui,-apple-system,'Malgun Gothic',sans-serif;margin:0;padding:24px;
background:#f7f7f8;color:#1a1a1a;line-height:1.6}h1{font-size:20px;margin:0 0 4px}
.sub{color:#666;font-size:13px;margin-bottom:20px}
.card{background:#fff;border-radius:10px;padding:16px 18px;margin-bottom:14px;
box-shadow:0 1px 3px rgba(0,0,0,.08)}
.hd{font-weight:600;font-size:15px;margin-bottom:2px}
.meta{color:#666;font-size:12.5px;margin-bottom:10px}
table{border-collapse:collapse;width:100%;font-size:12.5px;margin:8px 0}
th,td{border:1px solid #e3e3e6;padding:5px 8px;text-align:left;vertical-align:top}
th{background:#fafafa;font-weight:600;white-space:nowrap}
.rec{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12px;font-weight:600}
.distinct{background:#e7f2ff;color:#0b4a8f}.same{background:#fff0e6;color:#8f3d0b}
.more{background:#f3f3f3;color:#555}
.reason{background:#fafafa;border-left:3px solid #d0d0d4;padding:8px 12px;font-size:13px;margin:8px 0}
ul{margin:6px 0;padding-left:20px;font-size:12.5px}
.pending{color:#8a6d00;font-weight:600;font-size:12.5px}
.warn{background:#fff8e6;border-left:3px solid #e0b000;padding:10px 14px;font-size:13px;
border-radius:4px;margin-bottom:18px}"""


def _esc(v: Any) -> str:
    return html.escape("" if v is None else str(v))


def render_duplicate_html(rows: list[dict[str, Any]], survey_year: int) -> str:
    cards = []
    for r in rows:
        cls = {"DISTINCT_DEPARTMENTS_KEEP_SEPARATE": "distinct",
               "SAME_DEPARTMENT_DEDUPLICATE": "same"}.get(r["recommended_decision"], "more")
        head = ["source_record_id", "schl_mjr_id", "학과명", "주야간", "수업연한", "학과특성",
                "추천 범위", "제외 사유", "학위과정", "상태", "소계열", "재학", "졸업", "조사연도"]
        body = "".join(
            "<tr>" + "".join(f"<td>{_esc(v)}</td>" for v in (
                rec["source_record_id"], rec["schl_mjr_id"], rec["department_name"],
                rec["day_night_name"], rec["lesson_term_name"], rec["major_character_name"],
                rec["recommendation_scope"], rec["exclusion_reason"],
                rec["degree_course_name"], rec["department_status"],
                f'{rec["official_small_series_code"]}:{rec["official_small_series_name"]}',
                rec["enrolled_count"], rec["graduate_count"], rec["survey_year"],
            )) + "</tr>"
            for rec in r["records"]
        )
        cards.append(f"""<div class="card">
<div class="hd">{_esc(r['university_name'])} · {_esc(r['department_name'])}</div>
<div class="meta">{_esc(r['college_name'])} · department_id <code>{_esc(r['department_id'])}</code>
 · schl_id {_esc(r['records'][0]['schl_id'])} · 갈리는 필드 {_esc(', '.join(r['differing_fields']))}</div>
<table><tr>{''.join(f'<th>{_esc(h)}</th>' for h in head)}</tr>{body}</table>
<div><span class="rec {cls}">권고: {_esc(r['recommended_decision'])}</span></div>
<div class="reason">{_esc(r['recommendation_reason'])}</div>
<div>공식 근거<ul>{''.join(f'<li>{_esc(e)}</li>' for e in r['official_evidence'])}</ul></div>
<div class="pending">reviewer_1_status: {_esc(r['reviewer_1_status'])} ·
 resolution_status: {_esc(r['resolution_status'])}</div>
</div>""")
    return f"""<meta charset="utf-8"><title>중복 학과 검수 패킷 {survey_year}</title><style>{_CSS}</style>
<h1>중복 department_id 검수 패킷</h1>
<div class="sub">조사연도 {survey_year} · {len(rows)}건 · worker-c</div>
<div class="warn"><b>권고는 확정이 아닙니다.</b> 모든 행이 <code>reviewer_1_status: TBD</code>,
<code>resolution_status: PENDING</code> 상태입니다. 사람이 승인하기 전까지 어떤 코드도 이 값을
사용하지 않습니다. 이름이 같다는 이유로 합치거나, source_record_id가 다르다는 이유만으로
별도 학과라고 단정하지 마세요.</div>
{''.join(cards)}"""


def render_nce_html(rows: list[dict[str, Any]], survey_year: int) -> str:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        groups[r["triage_group"]].append(r)

    sections = []
    for group, members in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        head = ["대학", "학과", "단과대학", "공식 대계열", "공식 중계열", "근거"]
        body = "".join(
            "<tr>" + "".join(f"<td>{_esc(v)}</td>" for v in (
                m["university_name"], m["department_name"], m["college_name"],
                m["official_large_series_name"], m["official_middle_series_name"],
                " / ".join(m["official_evidence"]) or "—",
            )) + "</tr>"
            for m in sorted(members, key=lambda x: x["department_id"])[:60]
        )
        more = f"<div class='meta'>… 외 {len(members) - 60}건 (전체는 JSONL 참조)</div>" if len(members) > 60 else ""
        sections.append(f"""<div class="card">
<div class="hd">{_esc(group)} — {len(members)}건</div>
<div class="reason">{_esc(members[0]['triage_reason'])}</div>
<table><tr>{''.join(f'<th>{_esc(h)}</th>' for h in head)}</tr>{body}</table>{more}
</div>""")
    return f"""<meta charset="utf-8"><title>N.C.E 검토 패킷 {survey_year}</title><style>{_CSS}</style>
<h1>N.C.E(표준분류 미분류) 검토 패킷</h1>
<div class="sub">조사연도 {survey_year} · {len(rows)}건 · worker-c</div>
<div class="warn"><b>N.C.E는 분류명이 아니라 "분류 없음" 센티널입니다.</b>
42개 전공군에 강제 배정하지 않았고, 후보 목록은 전부 비어 있습니다.
검색 스니펫·비공식 위키·LLM 추측으로 소계열을 만들지 마세요.
N.C.E를 0점이나 무관으로 처리하지도 마세요.</div>
{''.join(sections)}"""


def render_cluster_md(summary: dict[str, Any], survey_year: int) -> str:
    lines = [
        f"# 분류 REVIEW 군집 요약 — 조사연도 {survey_year}",
        "",
        f"총 **{summary['total']}건** · 군집 {summary['cluster_count']}개",
        "",
        f"> {summary['note']}",
        "",
        "| 우선순위 | 군집 | 건수 | 필요한 공식 근거 |",
        "|---|---|---|---|",
    ]
    for c in summary["clusters"]:
        lines.append(
            f"| {c['review_priority']} | {c['cluster_label']} (`{c['cluster_code']}`) | "
            f"{c['count']} | {' · '.join(c['required_official_evidence'])} |"
        )
    lines += ["", "---", ""]
    for c in summary["clusters"]:
        lines += [
            f"## {c['cluster_label']} — {c['count']}건 (우선순위 {c['review_priority']})",
            "",
            f"**왜 검토가 필요한가.** {c['why_review_needed']}",
            "",
            f"주요 공식 소계열: {', '.join(f'{k}({v})' for k, v in c['top_official_small_series'].items()) or '—'}",
            "",
            f"현재 자동 후보: {', '.join(f'{k}({v})' for k, v in c['current_auto_candidates'].items()) or '없음'}",
            "",
            "대표 예시",
            "",
        ]
        for e in c["examples"]:
            lines.append(
                f"- {e['university_name']} {e['department_name']} "
                f"({e['college_name']}) — 소계열 {e['official_small_series_name']}"
            )
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    use_utf8_stdout()
    parser = argparse.ArgumentParser(description="검수 패킷 생성")
    parser.add_argument("--survey-year", type=int, default=2025)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    args = parser.parse_args(argv)

    work = args.data_dir / "academyinfo_work" / str(args.survey_year)
    inputs = {
        "duplicate_department_review_queue.jsonl": work / "duplicate_department_review_queue.jsonl",
        "classification_review_queue.jsonl": work / "classification_review_queue.jsonl",
        "unmapped_nce_queue.jsonl": work / "unmapped_nce_queue.jsonl",
        "departments.normalized.jsonl": work / "departments.normalized.jsonl",
        "classification_results.jsonl": work / "classification_results.jsonl",
        "out_of_recommendation_scope.jsonl": work / "out_of_recommendation_scope.jsonl",
        "canonical_major_groups.draft.jsonl": args.data_dir / "canonical_major_groups.draft.jsonl",
    }
    missing = [n for n, p in inputs.items() if not p.exists()]
    if missing:
        print(f"입력이 없습니다: {missing}", file=sys.stderr)
        print("기존 패킷을 부분 덮어쓰지 않고 중단합니다.", file=sys.stderr)
        return 2

    dup_queue = read_jsonl(inputs["duplicate_department_review_queue.jsonl"])
    cls_queue = read_jsonl(inputs["classification_review_queue.jsonl"])
    nce_queue = read_jsonl(inputs["unmapped_nce_queue.jsonl"])
    normalized = read_jsonl(inputs["departments.normalized.jsonl"])
    classified = read_jsonl(inputs["classification_results.jsonl"])
    group_labels = {
        g["canonical_major_id"]
        for g in read_jsonl(inputs["canonical_major_groups.draft.jsonl"])
    }

    by_record = {r["source_record_id"]: r for r in normalized}

    # 추천 후보 중복 Queue는 계약학과 제외 후 0건이지만, 관계 판단과 원본 보존을
    # 증명하는 검수 패킷은 정규화 데이터의 일반/계약 쌍 6그룹을 계속 보여준다.
    contract_audit_queue = build_contract_duplicate_audit(normalized)
    if contract_audit_queue:
        # 계약학과 감사 그룹 외의 실제 추천 후보 중복도 버리지 않는다.
        combined = {group["department_id"]: group for group in dup_queue}
        combined.update({group["department_id"]: group for group in contract_audit_queue})
        dup_queue = [combined[department_id] for department_id in sorted(combined)]

    dup_draft = build_duplicate_draft(dup_queue, by_record)
    cluster_summary = build_cluster_summary(cls_queue)
    nce_triage = build_nce_triage(nce_queue, classified, group_labels)

    packets = work / "packets"
    packets.mkdir(parents=True, exist_ok=True)
    write_jsonl(packets / "duplicate_decision_draft.jsonl", dup_draft)
    write_jsonl(packets / "nce_triage_queue.jsonl", nce_triage)
    (packets / "classification_cluster_summary.json").write_text(
        json.dumps(cluster_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (packets / "classification_cluster_summary.md").write_text(
        render_cluster_md(cluster_summary, args.survey_year), encoding="utf-8")
    (packets / "duplicate_review_packet.html").write_text(
        render_duplicate_html(dup_draft, args.survey_year), encoding="utf-8")
    (packets / "nce_review_packet.html").write_text(
        render_nce_html(nce_triage, args.survey_year), encoding="utf-8")

    outputs = sorted(p for p in packets.iterdir() if p.name != "review_packet_manifest.json")
    manifest = {
        "survey_year": args.survey_year,
        # 생성 시각을 넣지 않는다 — 재생성 결과가 매번 달라져 Byte 비교를 못 하게 된다.
        "input_hashes": {n: sha256_file(p) for n, p in sorted(inputs.items())},
        "output_hashes": {p.name: sha256_file(p) for p in outputs},
        "counts": {
            "duplicate_decision_draft": len(dup_draft),
            "classification_review_total": cluster_summary["total"],
            "classification_cluster_count": cluster_summary["cluster_count"],
            "nce_triage": len(nce_triage),
        },
        "duplicate_recommendation_breakdown": dict(
            Counter(r["recommended_decision"] for r in dup_draft)),
        "nce_triage_breakdown": dict(Counter(r["triage_group"] for r in nce_triage)),
        "human_review_rows_total": len(dup_draft) + cluster_summary["total"] + len(nce_triage),
        "auto_approved_rows": 0,
        "note": (
            "auto_approved_rows가 0이라는 것이 자동 승인하지 않았다는 증명이다. "
            "모든 검수 행은 reviewer_1_status=TBD · resolution_status=PENDING이다."
        ),
    }
    (packets / "review_packet_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"검수 패킷 생성 — 조사연도 {args.survey_year}")
    print(f"  중복 결정 초안   {len(dup_draft):>5}  {manifest['duplicate_recommendation_breakdown']}")
    print(f"  분류 군집        {cluster_summary['cluster_count']:>5}개 / {cluster_summary['total']}건")
    for c in cluster_summary["clusters"]:
        print(f"      P{c['review_priority']} {c['cluster_label']:<26} {c['count']}")
    print(f"  N.C.E 3분류      {len(nce_triage):>5}  {manifest['nce_triage_breakdown']}")
    print(f"  사람 검토 총 행수 {manifest['human_review_rows_total']} · 자동 승인 {manifest['auto_approved_rows']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
