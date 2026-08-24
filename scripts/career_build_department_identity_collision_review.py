"""department_id identity-key 충돌(16 Group·32행) 감사 패킷 생성 —
a/department-identity-collision-audit.

## 용어 정정 — "Hash Collision"이 아니라 "identity-key Collision"

`department_id`는 `src/ids.py::generate_department_id(schl_id, department_name,
college_name)`로 만든다 — SHA-256을 쓰지만, 이건 우연히 서로 다른 입력이 같은
출력을 낸 암호학적 Hash Collision이 아니다. **입력 자체가 의도적으로
schlMjrId(원본 행 식별자)를 배제한 3-tuple** `(schl_id, department_name,
college_name)`이다(같은 학과가 매년 다른 schlMjrId를 받아도 같은 department_id를
유지하게 하려는 설계 — `academyinfo_identity.py` 모듈 docstring 참고). 그래서 서로
다른 `source_record_id`(다른 원본 행, 다른 schlMjrId)가 우연이 아니라 **구조적으로**
같은 department_id를 받을 수 있다 — 예: 같은 학교·같은 학과명·같은 단과대학인데
이수연한(4년/6년)이나 major_character(일반과정/계약학과)가 다른 두 공식 트랙.

이 스크립트는 국가 규모(24,422행) 정규화 결과에서 실제로 발생한 이런 사례
16 Group·32행 전부를 모아 사람이 검토할 수 있는 Draft 패킷으로 만든다.
**어떤 자동 판정도 내리지 않는다** — 두 후보가 완전히 같은 원본 행의 중복인지
(EXACT_DUPLICATE_SOURCE_RECORD), 진짜 서로 다른 공식 학과인지
(DISTINCT_OFFICIAL_DEPARTMENTS), identity-key 설계 자체가 부족한 것인지
(IDENTITY_KEY_INSUFFICIENT) 등은 전부 `reviewer_1_status=TBD`,
`decision=TBD`로 남겨 사람이 채운다. `department_id` 생성 규칙 자체는 이
스크립트가 바꾸지 않는다.

## 입력

- `departments.normalized.jsonl` — 실제 전국 정규화 결과(24,422행, 명시적 경로
  필수, 자동으로 API를 재호출하지 않는다)
- `classification_results.jsonl` — 위와 짝을 이루는 분류 결과(24,416행)
- `departments.raw.jsonl.gz` — 대학알리미 원본 Snapshot(gz, (schlId, schlMjrId)
  키로 조인해 원본 그대로의 학과명·단과대학명·학과특성·이수연한을 대조한다)

## 출력(전부 `data/academyinfo_work/<year>/packets/` 아래, 결정론적 — 생성 시각을
넣지 않는다)

- `department_identity_collision_review.jsonl` — Group당 한 줄, 16줄
- `department_identity_collision_review.html` — 사람이 읽는 검수 화면
- `department_identity_collision_review_manifest.json` — 입력·출력 Hash, 24,422행
  전체 회계, 계약학과 6건 회계
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import html
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.career_console import use_utf8_stdout  # noqa: E402

# 지시서(a/department-identity-collision-audit) — 사람 검수 decision 6종.
# TBD 이외의 값은 이 스크립트가 절대 채우지 않는다(자동 승인 0건).
DECISION_OPTIONS: tuple[str, ...] = (
    "TBD",
    "EXACT_DUPLICATE_SOURCE_RECORD",
    "DISTINCT_OFFICIAL_DEPARTMENTS",
    "IDENTITY_KEY_INSUFFICIENT",
    "NEEDS_MORE_OFFICIAL_EVIDENCE",
    "HOLD",
)

# Group 내 두 후보를 비교할 필드 — department_id 생성에 실제로 쓰인 3-tuple
# (schl_id, department_name, college_name)을 포함해, "같은 identity-key인데
# 어떤 필드가 다른가"를 그대로 보여준다.
CANDIDATE_COMPARISON_FIELDS: tuple[str, ...] = (
    "source_record_id",
    "schl_id",
    "source_schl_mjr_id",
    "university_name",
    "campus_name",
    "college_name",
    "department_name",
    "major_character_name",
    "course_term",
    "degree_course_name",
    "day_night",
    "department_status",
    "recommendation_scope",
    "exclusion_reason",
)

# 사람이 "별도 편제단위로 볼 공식 근거"를 판단할 때 우선 볼 신호 — 이 스크립트는
# 이 필드들이 다르다는 사실만 표시하고, 그것이 곧 "별도 학과"라고 확정하지 않는다.
DISTINGUISHING_SIGNAL_FIELDS: tuple[str, ...] = (
    "major_character_name",
    "course_term",
    "degree_course_name",
    "day_night",
    "campus_name",
)

_NIGHT_REMOTE_EXCLUSION_REASONS = frozenset(
    {"EXCLUDED_NIGHT_COURSE", "EXCLUDED_DISTANCE_UNIVERSITY", "EXCLUDED_UNKNOWN_DAY_NIGHT"}
)


# ============================== 파일 IO 도우미 ==============================


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hash_or_missing(path: Path) -> str:
    return sha256_file(path) if path.exists() else "MISSING"


def canonical_dumps(row: dict[str, Any]) -> str:
    return json.dumps(row, ensure_ascii=False, sort_keys=True)


def write_jsonl_atomic(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(canonical_dumps(row) + "\n")
    tmp.replace(path)


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    tmp.replace(path)


def load_raw_index(raw_gz_path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    """대학알리미 원본 Snapshot을 (schlId, schlMjrId)로 색인한다 — department_id가
    없는 원본 행이므로 이 키로만 조인할 수 있다."""

    index: dict[tuple[str, str], dict[str, Any]] = {}
    with gzip.open(raw_gz_path, "rt", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            index[(row.get("schlId"), row.get("schlMjrId"))] = row
    return index


# ============================== 후보/Group 조립 ==============================


def _candidate_entry(
    norm_row: dict[str, Any],
    classification_by_department: dict[str, dict[str, Any]],
    raw_index: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    department_id = norm_row["department_id"]
    classification_row = classification_by_department.get(department_id)
    raw_key = (norm_row.get("schl_id"), norm_row.get("source_schl_mjr_id"))
    raw_row = raw_index.get(raw_key)

    candidate_group_ids = list((classification_row or {}).get("candidate_canonical_major_ids") or [])

    entry: dict[str, Any] = {
        "department_id": department_id,
        "source_record_id": norm_row.get("source_record_id"),
        "schl_id": norm_row.get("schl_id"),
        "source_schl_mjr_id": norm_row.get("source_schl_mjr_id"),
        "university_name": norm_row.get("university_name"),
        "campus_name": norm_row.get("campus"),
        "college_name": norm_row.get("college_name"),
        "department_name": norm_row.get("department_name"),
        "major_character_name": norm_row.get("major_character_name"),
        "course_term": norm_row.get("lesson_term_name"),
        "degree_course_name": norm_row.get("degree_course_name"),
        "day_night": norm_row.get("day_night_name"),
        "department_status": norm_row.get("department_status"),
        "recommendation_scope": norm_row.get("recommendation_scope"),
        "exclusion_reason": norm_row.get("exclusion_reason"),
        "classification_result": None
        if classification_row is None
        else {
            "eligibility_status": classification_row.get("eligibility_status"),
            "mapping_status": classification_row.get("mapping_status"),
            "candidate_canonical_major_ids": candidate_group_ids,
            "official_large_series_name": classification_row.get("official_large_series_name"),
            "official_middle_series_name": classification_row.get("official_middle_series_name"),
            "official_small_series_name": classification_row.get("official_small_series_name"),
            "decision_reason": classification_row.get("decision_reason"),
        },
        "canonical_major_group_candidates": candidate_group_ids,
        "raw_snapshot": {
            "found_in_raw_snapshot": raw_row is not None,
            "schlId": (raw_row or {}).get("schlId"),
            "schlMjrId": (raw_row or {}).get("schlMjrId"),
            "svyYr": (raw_row or {}).get("svyYr"),
            "korSchlNm": (raw_row or {}).get("korSchlNm"),
            "korMjrNm": (raw_row or {}).get("korMjrNm"),
            "clgNm": (raw_row or {}).get("clgNm"),
            "schlMjrCharNm": (raw_row or {}).get("schlMjrCharNm"),
            "schlMjrStatNm": (raw_row or {}).get("schlMjrStatNm"),
        },
    }
    return entry


def build_groups(
    normalized_rows: list[dict[str, Any]],
    classification_by_department: dict[str, dict[str, Any]],
    raw_index: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    by_department_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in normalized_rows:
        by_department_id[row["department_id"]].append(row)
    collision_groups = {k: v for k, v in by_department_id.items() if len(v) > 1}

    # career_build_national_department_promotion_dry_run.py::load_inputs()의
    # `by_department_id = {row["department_id"]: row for row in departments}`와
    # 정확히 같은 규칙 — 파일에서 나중에 나오는 행이 evaluated representative로
    # 남고, 먼저 나온 행은 평가 대상에서 조용히 빠진다(삭제는 아니다 — 원본
    # normalized 파일과 이 감사 패킷에는 그대로 남는다).
    last_wins: dict[str, dict[str, Any]] = {}
    for row in normalized_rows:
        last_wins[row["department_id"]] = row

    groups: list[dict[str, Any]] = []
    for department_id in sorted(collision_groups.keys()):
        members = sorted(collision_groups[department_id], key=lambda r: r["source_record_id"])
        candidates = [_candidate_entry(m, classification_by_department, raw_index) for m in members]

        evaluated_source_record_id = last_wins[department_id]["source_record_id"]
        dropped_source_record_ids = [
            c["source_record_id"] for c in candidates if c["source_record_id"] != evaluated_source_record_id
        ]

        a, b = candidates[0], candidates[1]
        same_fields = [f for f in CANDIDATE_COMPARISON_FIELDS if a.get(f) == b.get(f)]
        different_fields = [f for f in CANDIDATE_COMPARISON_FIELDS if a.get(f) != b.get(f)]
        distinguishing_signal_fields = [f for f in DISTINGUISHING_SIGNAL_FIELDS if f in different_fields]

        groups.append(
            {
                "department_id": department_id,
                "candidate_count": len(candidates),
                "candidates": candidates,
                "comparison": {
                    "same_fields": same_fields,
                    "different_fields": different_fields,
                    "source_record_id_same": a["source_record_id"] == b["source_record_id"],
                    "schl_mjr_id_same": a["source_schl_mjr_id"] == b["source_schl_mjr_id"],
                    "differs_in_potential_distinguishing_fields": distinguishing_signal_fields,
                    "note": (
                        "differs_in_potential_distinguishing_fields는 자동 판정이 아니다 — "
                        "decision은 사람이 채운다(review.decision)."
                    ),
                },
                "dry_run_evaluation_audit": {
                    "evaluated_representative_source_record_id": evaluated_source_record_id,
                    "dropped_from_evaluation_source_record_ids": dropped_source_record_ids,
                    "note": (
                        "load_inputs()의 by_department_id 딕셔너리 컴프리헨션은 같은 "
                        "department_id의 원본 행 중 파일에서 나중에 나오는 한 행만 "
                        "evaluate_department()에 넘긴다. dropped 행은 삭제되지 않고 "
                        "departments.normalized.jsonl과 이 감사 패킷에 그대로 보존되지만, "
                        "Dry Run 평가 대상에는 처음부터 들어가지 않는다 — 그래서 "
                        "promotion_candidates.jsonl/promotion_blocked.jsonl 어디에도 "
                        "dropped 행의 source_record_id로는 나타나지 않는다."
                    ),
                },
                "review": {
                    "reviewer_1_status": "TBD",
                    "decision": "TBD",
                    "decision_notes": "",
                    "allowed_decisions": list(DECISION_OPTIONS),
                },
            }
        )
    return groups


# ============================== HTML 렌더 ==============================

_CSS = """
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;margin:0;padding:24px;
background:#0b0f14;color:#dbe4ee;line-height:1.5}
h1{font-size:20px;margin:0 0 4px}
.sub{color:#8ea0b3;font-size:13px;margin-bottom:16px}
.warn{background:#3a2a12;border:1px solid #8a5a1e;padding:10px 14px;border-radius:6px;
font-size:13px;margin-bottom:20px}
.group{background:#131a22;border:1px solid #263140;border-radius:8px;padding:16px;margin-bottom:16px}
.gid{font-family:ui-monospace,monospace;color:#7fb8e6;font-size:13px}
table{border-collapse:collapse;width:100%;margin-top:8px;font-size:12.5px}
th,td{border:1px solid #263140;padding:4px 8px;text-align:left;vertical-align:top}
th{background:#1a2430;color:#9fb3c8}
.diff{background:#3a1414;color:#ffb3b3}
.same{color:#8ea0b3}
.badge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;margin-right:4px}
.b-tbd{background:#3a2a12;color:#e0b060}
.audit{font-size:12px;color:#8ea0b3;margin-top:8px}
code{font-family:ui-monospace,monospace}
"""


def _esc(v: Any) -> str:
    return html.escape("" if v is None else str(v))


def render_html(groups: list[dict[str, Any]], survey_year: int) -> str:
    blocks = []
    for g in groups:
        a, b = g["candidates"]
        different_fields = g["comparison"]["different_fields"]

        def _row_html(field: str) -> str:
            css_class = "diff" if field in different_fields else "same"
            return (
                f"<tr><th>{_esc(field)}</th>"
                f"<td class='{css_class}'>{_esc(a.get(field))}</td>"
                f"<td class='{css_class}'>{_esc(b.get(field))}</td></tr>"
            )

        rows_html = "".join(_row_html(f) for f in CANDIDATE_COMPARISON_FIELDS)
        raw_a = a["raw_snapshot"]
        raw_b = b["raw_snapshot"]
        blocks.append(f"""<div class="group">
<div class="gid">{_esc(g['department_id'])} · candidate_count {g['candidate_count']}</div>
<table><tr><th>필드</th><th>후보 A</th><th>후보 B</th></tr>{rows_html}</table>
<div class="audit">평가 대표(evaluated): <code>{_esc(g['dry_run_evaluation_audit']['evaluated_representative_source_record_id'])}</code>
· 평가 제외(dropped): <code>{_esc(', '.join(g['dry_run_evaluation_audit']['dropped_from_evaluation_source_record_ids']))}</code></div>
<div class="audit">Raw 대조 — A: found={_esc(raw_a['found_in_raw_snapshot'])} ({_esc(raw_a.get('schlMjrCharNm'))})
· B: found={_esc(raw_b['found_in_raw_snapshot'])} ({_esc(raw_b.get('schlMjrCharNm'))})</div>
<div class="audit">별도 편제단위 신호 필드: {_esc(', '.join(g['comparison']['differs_in_potential_distinguishing_fields']) or '(없음)')}</div>
<div><span class="badge b-tbd">reviewer_1_status: TBD</span><span class="badge b-tbd">decision: TBD</span></div>
</div>""")

    return f"""<meta charset="utf-8"><title>department_id identity-key 충돌 검수 패킷 {survey_year}</title>
<style>{_CSS}</style>
<h1>department_id identity-key 충돌 검수 패킷</h1>
<div class="sub">조사연도 {survey_year} · {len(groups)}개 Group · {sum(g['candidate_count'] for g in groups)}행</div>
<div class="warn"><b>이것은 SHA-256 Hash Collision이 아닙니다.</b> department_id는
(schl_id, department_name, college_name) identity-key입니다 — 서로 다른
source_record_id가 이 3-tuple을 공유하면 구조적으로 같은 department_id를
받습니다. 모든 Group이 <code>reviewer_1_status: TBD</code>, <code>decision: TBD</code>
상태입니다. 이 패킷은 어떤 자동 판정도 내리지 않았습니다.</div>
{''.join(blocks)}
"""


# ============================== main ==============================


def main(argv: list[str] | None = None) -> int:
    use_utf8_stdout()
    parser = argparse.ArgumentParser(description="department_id identity-key 충돌 감사 패킷 생성")
    parser.add_argument("--survey-year", type=int, default=2025)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data", help="산출물이 놓일 기준 디렉터리")
    parser.add_argument(
        "--normalized-path", type=Path, required=True,
        help="departments.normalized.jsonl 실제 경로(명시적으로 지정 — 기본값 없음)",
    )
    parser.add_argument(
        "--classification-path", type=Path, required=True,
        help="classification_results.jsonl 실제 경로",
    )
    parser.add_argument(
        "--raw-gz-path", type=Path, required=True,
        help="departments.raw.jsonl.gz 실제 경로",
    )
    parser.add_argument("--output-dir", type=Path, default=None, help="기본값: <data-dir>/academyinfo_work/<year>/packets")
    args = parser.parse_args(argv)

    output_dir = args.output_dir or (args.data_dir / "academyinfo_work" / str(args.survey_year) / "packets")

    for label, path in (
        ("normalized", args.normalized_path),
        ("classification", args.classification_path),
        ("raw gz", args.raw_gz_path),
    ):
        if not path.exists():
            print(f"필수 입력이 없습니다({label}): {path}", file=sys.stderr)
            return 2

    normalized_rows = read_jsonl(args.normalized_path)
    classification_rows = read_jsonl(args.classification_path)
    classification_by_department = {row["department_id"]: row for row in classification_rows}
    raw_index = load_raw_index(args.raw_gz_path)

    groups = build_groups(normalized_rows, classification_by_department, raw_index)

    # ── 행수 회계(지시서 §3) ──────────────────────────────────────────────
    # department_id는 identity-key 충돌 때문에 Set으로 만들면 24,406개로 줄어들고
    # (16개 충돌 Group이 각각 1개로 뭉개진다), normalized/classification 양쪽에서
    # 똑같이 뭉개지므로 department_id 기준 대칭차는 우연히 0이 나온다 — 이것으로
    # "누락 행"을 계산하면 §1에서 이미 확인한 진짜 문제(계약학과 6건 누락)가
    # 가려진다. source_record_id는 이 데이터셋에서 24,422/24,416건 전부 고유함이
    # 이미 확인됐으므로, 이 대칭차는 반드시 source_record_id로 계산한다.
    normalized_ids = {row["department_id"] for row in normalized_rows}
    unique_department_id_count = len(normalized_ids)
    collision_group_count = len(groups)
    collision_row_count = sum(g["candidate_count"] for g in groups)
    dropped_row_count = sum(len(g["dry_run_evaluation_audit"]["dropped_from_evaluation_source_record_ids"]) for g in groups)

    normalized_source_record_ids = {row["source_record_id"] for row in normalized_rows}
    classification_source_record_ids = {row["source_record_id"] for row in classification_rows}
    missing_from_classification_src_ids = normalized_source_record_ids - classification_source_record_ids
    classification_only_src_ids = classification_source_record_ids - normalized_source_record_ids

    missing_rows_by_source_record_id = {
        row["source_record_id"]: row for row in normalized_rows if row["source_record_id"] in missing_from_classification_src_ids
    }
    missing_all_contract = all(
        row.get("exclusion_reason") == "CONTRACT_DEPARTMENT" for row in missing_rows_by_source_record_id.values()
    )

    # department_id 기준 대칭차(참고용 — 위 설명대로 충돌 때문에 왜곡돼 있다는
    # 사실 자체를 보고서에 남기려고 같이 계산한다).
    classification_department_ids = {row["department_id"] for row in classification_rows}
    missing_from_classification_by_department_id_count = len(normalized_ids - classification_department_ids)

    # ── 계약학과 6건 회계(지시서 §4) ──────────────────────────────────────
    last_wins: dict[str, dict[str, Any]] = {}
    for row in normalized_rows:
        last_wins[row["department_id"]] = row
    contract_rows = [row for row in normalized_rows if row.get("exclusion_reason") == "CONTRACT_DEPARTMENT"]
    contract_evaluated = [
        row for row in contract_rows if last_wins[row["department_id"]]["source_record_id"] == row["source_record_id"]
    ]
    contract_dropped = [row for row in contract_rows if row not in contract_evaluated]

    row_accounting = {
        "normalized_input_rows": len(normalized_rows),
        "classification_rows": len(classification_rows),
        "unique_department_id_count": unique_department_id_count,
        "collision_group_count": collision_group_count,
        "collision_row_count": collision_row_count,
        "dropped_from_evaluation_row_count": dropped_row_count,
        "missing_from_classification_count": len(missing_from_classification_src_ids),
        "missing_from_classification_all_contract_department": missing_all_contract,
        "classification_only_id_count": len(classification_only_src_ids),
        "missing_from_classification_by_department_id_count_note": (
            f"department_id 기준으로 계산하면 {missing_from_classification_by_department_id_count}건으로 "
            "나온다 — identity-key 충돌로 왜곡된 값이므로 위 missing_from_classification_count"
            "(source_record_id 기준)가 정본이다."
        ),
    }
    contract_accounting = {
        "contract_department_total": len(contract_rows),
        "contract_department_evaluated_by_dry_run": len(contract_evaluated),
        "contract_department_dropped_from_dry_run_evaluation": len(contract_dropped),
        "contract_department_final_recommendation_exposure": 0,
        "contract_department_preserved_in_normalized_and_audit_packet": len(contract_rows),
        "note": (
            "6건 전부 duplicate_group_size>1(department_id identity-key 충돌 대상)이다. "
            "그중 4건은 evaluate_department()가 실제로 평가해 BLOCKED_CONTRACT_DEPARTMENT로 "
            "나타난다(동시에 BLOCKED_DUPLICATE_ID도 갖는다 — 완전히 겹친다, 부분 겹침이 "
            "아니다). 나머지 2건(서경대 헤어디자인학과·코스메틱뷰티매니지먼트학과)은 "
            "load_inputs()의 by_department_id 충돌 처리로 애초에 평가 대상에서 빠져 "
            "BLOCKED_CONTRACT_DEPARTMENT 사유 자체가 계산되지 않는다 — 6건 전부 "
            "departments.normalized.jsonl 원본과 이 감사 패킷에는 그대로 남아 있다."
        ),
    }

    jsonl_path = output_dir / "department_identity_collision_review.jsonl"
    html_path = output_dir / "department_identity_collision_review.html"
    manifest_path = output_dir / "department_identity_collision_review_manifest.json"

    write_jsonl_atomic(jsonl_path, groups)
    write_text_atomic(html_path, render_html(groups, args.survey_year))

    manifest = {
        "survey_year": args.survey_year,
        # 생성 시각을 넣지 않는다 — 같은 입력이면 항상 같은 Byte가 나와야 한다.
        "input_hashes": {
            "departments.normalized.jsonl": hash_or_missing(args.normalized_path),
            "classification_results.jsonl": hash_or_missing(args.classification_path),
            "departments.raw.jsonl.gz": hash_or_missing(args.raw_gz_path),
        },
        "output_hashes": {
            jsonl_path.name: sha256_file(jsonl_path),
            html_path.name: sha256_file(html_path),
        },
        "row_accounting": row_accounting,
        "contract_department_accounting": contract_accounting,
        "auto_approved_rows": 0,
        "decision_options": list(DECISION_OPTIONS),
        "note": (
            "auto_approved_rows가 0이라는 것이 이 스크립트가 어떤 Group도 자동으로 판정· "
            "병합하지 않았다는 증명이다. 모든 Group이 review.reviewer_1_status=TBD, "
            "review.decision=TBD다. department_id 생성 규칙(src/ids.py::generate_"
            "department_id)은 이 스크립트로 바뀌지 않았다."
        ),
    }
    write_text_atomic(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n")

    print(f"department_id identity-key 충돌 감사 패킷 생성 완료 — 조사연도 {args.survey_year}")
    print(f"  Group {collision_group_count}개 · 행 {collision_row_count}건")
    print(f"  classification 누락 {row_accounting['missing_from_classification_count']}건"
          f"(전부 계약학과={missing_all_contract})")
    print(f"  계약학과 원본 {contract_accounting['contract_department_total']}건 중 "
          f"평가 대상 {contract_accounting['contract_department_evaluated_by_dry_run']}건, "
          f"평가 제외 {contract_accounting['contract_department_dropped_from_dry_run_evaluation']}건")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
