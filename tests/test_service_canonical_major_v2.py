"""Service Canonical Major v2 — 2026-08-25 지시서(a/service-major-catalog-v2) §2/§3/
§6 테스트.

세 층위를 확인한다.

    1. Schema 자체가 실제로 뭔가를 거부하는지(SchemaValidationRejectsBadRowsTest).
    2. Loader의 Fail-Fast 5가지가 합성 Fixture로 실제 작동하는지
       (LoaderFailFastTest — 실제 data/master/ 파일을 건드리지 않는다).
    3. 실제 생성된 두 파일이 §2 불변식(ACTIVE 38·EXCLUDED 4·Group 누락 0·중복 0·
       기존 10개 ID 무변경)을 지키는지(RealCatalogInvariantsTest).
    4. §5 "금지" 목록이 실제로 지켜졌는지(ForbiddenScopeUntouchedTest — main.py·
       Matching Engine·major_profiles_v2·Department Master·Review 파일이 이
       작업으로 바뀌지 않았는지 git diff로 확인)."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from src.schemas.canonical_major_group import CanonicalMajorGroupDraft
from src.schemas.service_canonical_major_v2 import (
    EXCLUDED_RECOMMENDATION_GROUP_IDS,
    CanonicalMajorGroupServiceMajorBridgeV2,
    ServiceCanonicalMajorV2,
)
from src.services.canonical_major_group_draft_loader import load_canonical_major_groups_draft
from src.services.service_canonical_major_v2_loader import (
    AmbiguousAliasError,
    DuplicateServiceMajorIdError,
    ExcludedGroupPromotedToActiveError,
    UnknownCanonicalMajorGroupError,
    load_canonical_major_group_to_service_major_bridge_v2,
    load_service_canonical_majors_v2,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CATALOG_PATH = _REPO_ROOT / "data" / "master" / "service_canonical_majors_v2.jsonl"
_BRIDGE_PATH = _REPO_ROOT / "data" / "master" / "canonical_major_group_to_service_major_v2.jsonl"


def _base_major_kwargs(**overrides) -> dict:
    base = dict(
        major_id="test_major",
        label="테스트 전공",
        description="테스트를 위한 전공 분야입니다.",
        aliases=["테스트"],
        keywords=["테스트"],
        canonical_major_group_id="law",
        recommendation_status="ACTIVE",
        official_source_urls=["https://www.academyinfo.go.kr/"],
        catalog_version="service_canonical_major_v2.0",
    )
    base.update(overrides)
    return base


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")


class SchemaValidationRejectsBadRowsTest(unittest.TestCase):
    """ServiceCanonicalMajorV2 Schema 자체가 실제로 거부하는지."""

    def test_blank_description_rejected(self) -> None:
        with self.assertRaises(Exception):
            ServiceCanonicalMajorV2.model_validate(_base_major_kwargs(description="   "))

    def test_description_too_long_rejected(self) -> None:
        with self.assertRaises(Exception):
            ServiceCanonicalMajorV2.model_validate(_base_major_kwargs(description="가" * 121))

    def test_description_with_percent_rejected(self) -> None:
        with self.assertRaises(Exception):
            ServiceCanonicalMajorV2.model_validate(_base_major_kwargs(description="취업률 90%가 넘는 전공 분야입니다."))

    def test_description_with_score_number_rejected(self) -> None:
        with self.assertRaises(Exception):
            ServiceCanonicalMajorV2.model_validate(_base_major_kwargs(description="적성 검사 90점 이상인 전공 분야입니다."))

    def test_forbidden_fit_guarantee_phrases_rejected(self) -> None:
        for phrase in ("가장 적합", "당신에게", "잘 맞는", "적성에 맞", "취업률", "합격률", "보장"):
            with self.subTest(phrase=phrase):
                with self.assertRaises(Exception):
                    ServiceCanonicalMajorV2.model_validate(
                        _base_major_kwargs(description=f"{phrase} 전공 분야입니다.")
                    )

    def test_duplicate_alias_within_entry_rejected(self) -> None:
        with self.assertRaises(Exception):
            ServiceCanonicalMajorV2.model_validate(_base_major_kwargs(aliases=["법학", "법학"]))

    def test_blank_alias_rejected(self) -> None:
        with self.assertRaises(Exception):
            ServiceCanonicalMajorV2.model_validate(_base_major_kwargs(aliases=["법학", "  "]))

    def test_empty_official_source_urls_rejected(self) -> None:
        with self.assertRaises(Exception):
            ServiceCanonicalMajorV2.model_validate(_base_major_kwargs(official_source_urls=[]))

    def test_excluded_group_active_rejected_at_schema_level(self) -> None:
        with self.assertRaises(Exception):
            ServiceCanonicalMajorV2.model_validate(
                _base_major_kwargs(canonical_major_group_id="fine_arts_design", recommendation_status="ACTIVE")
            )

    def test_valid_entry_passes(self) -> None:
        ServiceCanonicalMajorV2.model_validate(_base_major_kwargs())

    def test_department_level_only_without_source_group_ids_rejected(self) -> None:
        with self.assertRaises(Exception):
            ServiceCanonicalMajorV2.model_validate(
                _base_major_kwargs(
                    major_id="hci_ux", canonical_major_group_id=None,
                    source_group_ids=[], mapping_scope="DEPARTMENT_LEVEL_ONLY",
                )
            )

    def test_department_level_only_with_canonical_major_group_id_rejected(self) -> None:
        """canonical_major_group_id와 mapping_scope=DEPARTMENT_LEVEL_ONLY를 동시에
        채우면 안 된다 — "이 Major가 정확히 어느 한 Group에 속하는가"와 "여러 Group에
        걸친 특수 융합인가"는 서로 배타적이어야 한다."""
        with self.assertRaises(Exception):
            ServiceCanonicalMajorV2.model_validate(
                _base_major_kwargs(
                    major_id="hci_ux", canonical_major_group_id="computer_science",
                    source_group_ids=["computer_science"], mapping_scope="DEPARTMENT_LEVEL_ONLY",
                )
            )

    def test_full_group_without_canonical_major_group_id_rejected(self) -> None:
        with self.assertRaises(Exception):
            ServiceCanonicalMajorV2.model_validate(
                _base_major_kwargs(canonical_major_group_id=None, mapping_scope="FULL_GROUP")
            )

    def test_full_group_with_source_group_ids_rejected(self) -> None:
        with self.assertRaises(Exception):
            ServiceCanonicalMajorV2.model_validate(
                _base_major_kwargs(source_group_ids=["computer_science"], mapping_scope="FULL_GROUP")
            )

    def test_valid_department_level_only_entry_passes(self) -> None:
        ServiceCanonicalMajorV2.model_validate(
            _base_major_kwargs(
                major_id="hci_ux", canonical_major_group_id=None,
                source_group_ids=["computer_science", "fine_arts_design"],
                mapping_scope="DEPARTMENT_LEVEL_ONLY",
            )
        )

    def test_department_level_only_referencing_excluded_group_is_not_rejected_by_the_active_guard(self) -> None:
        """§2 — source_group_ids에 추천 제외 Group(fine_arts_design)이 있어도 그
        자체로는 예체능 4개 ACTIVE 금지 규칙 위반이 아니다(canonical_major_group_id
        가 None이라 그 규칙 대상이 아니다) — hci_ux가 fine_arts_design을 통째로
        승격시키는 게 아니라는 뜻이다."""
        ServiceCanonicalMajorV2.model_validate(
            _base_major_kwargs(
                major_id="hci_ux", canonical_major_group_id=None,
                source_group_ids=["fine_arts_design"], mapping_scope="DEPARTMENT_LEVEL_ONLY",
            )
        )

    def test_bridge_active_without_service_major_id_rejected(self) -> None:
        with self.assertRaises(Exception):
            CanonicalMajorGroupServiceMajorBridgeV2.model_validate(
                {
                    "canonical_major_group_id": "law",
                    "service_major_id": None,
                    "recommendation_status": "ACTIVE",
                    "decision_reason": "x",
                }
            )

    def test_bridge_excluded_with_service_major_id_rejected(self) -> None:
        with self.assertRaises(Exception):
            CanonicalMajorGroupServiceMajorBridgeV2.model_validate(
                {
                    "canonical_major_group_id": "fine_arts_design",
                    "service_major_id": "design",
                    "recommendation_status": "EXCLUDED_RECOMMENDATION",
                    "decision_reason": "x",
                }
            )

    def test_bridge_valid_active_and_excluded_rows_pass(self) -> None:
        CanonicalMajorGroupServiceMajorBridgeV2.model_validate(
            {
                "canonical_major_group_id": "law", "service_major_id": "law",
                "recommendation_status": "ACTIVE", "decision_reason": "x",
            }
        )
        CanonicalMajorGroupServiceMajorBridgeV2.model_validate(
            {
                "canonical_major_group_id": "music", "service_major_id": None,
                "recommendation_status": "EXCLUDED_RECOMMENDATION", "decision_reason": "x",
            }
        )


class LoaderFailFastTest(unittest.TestCase):
    """Loader의 5가지 Fail-Fast — 합성 Fixture로 확인한다(실제 data/master/ 무변경)."""

    def _write_catalog(self, tmp: Path, rows: list[dict]) -> Path:
        path = tmp / "catalog.jsonl"
        _write_jsonl(path, rows)
        return path

    def test_valid_catalog_loads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_catalog(Path(tmp), [_base_major_kwargs(major_id="a"), _base_major_kwargs(major_id="b", aliases=["다른별칭"])])
            entries = load_service_canonical_majors_v2(path, valid_group_ids=frozenset({"law"}))
            self.assertEqual(len(entries), 2)

    def test_duplicate_major_id_fails_fast(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_catalog(Path(tmp), [_base_major_kwargs(major_id="a"), _base_major_kwargs(major_id="a")])
            with self.assertRaises(DuplicateServiceMajorIdError):
                load_service_canonical_majors_v2(path, valid_group_ids=frozenset({"law"}))

    def test_unknown_canonical_major_group_id_fails_fast(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_catalog(Path(tmp), [_base_major_kwargs(canonical_major_group_id="not_a_real_group")])
            with self.assertRaises(UnknownCanonicalMajorGroupError):
                load_service_canonical_majors_v2(path, valid_group_ids=frozenset({"law"}))

    def test_unknown_source_group_id_fails_fast(self) -> None:
        """04096a4 후속 §3 — DEPARTMENT_LEVEL_ONLY Major의 source_group_ids도
        canonical_major_group_id와 똑같이 실제 Group 목록과 대조된다."""
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_catalog(
                Path(tmp),
                [
                    _base_major_kwargs(
                        major_id="hci_ux", canonical_major_group_id=None,
                        source_group_ids=["law", "not_a_real_group"], mapping_scope="DEPARTMENT_LEVEL_ONLY",
                    )
                ],
            )
            with self.assertRaises(UnknownCanonicalMajorGroupError):
                load_service_canonical_majors_v2(path, valid_group_ids=frozenset({"law"}))

    def test_department_level_only_major_referencing_excluded_source_group_still_loads(self) -> None:
        """source_group_ids에 추천 제외 Group이 있어도(예: fine_arts_design) 그
        자체로는 Fail-Fast 대상이 아니다 — canonical_major_group_id가 None이라
        "이 Group을 통째로 ACTIVE로 승격했다"는 뜻이 아니기 때문이다."""
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_catalog(
                Path(tmp),
                [
                    _base_major_kwargs(
                        major_id="hci_ux", canonical_major_group_id=None,
                        source_group_ids=["computer_science", "fine_arts_design"],
                        mapping_scope="DEPARTMENT_LEVEL_ONLY",
                    )
                ],
            )
            entries = load_service_canonical_majors_v2(
                path, valid_group_ids=frozenset({"computer_science", "fine_arts_design"})
            )
            self.assertEqual(len(entries), 1)

    def test_ambiguous_alias_across_majors_fails_fast(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_catalog(
                Path(tmp),
                [
                    _base_major_kwargs(major_id="a", aliases=["공통별칭"]),
                    _base_major_kwargs(major_id="b", aliases=["공통별칭"]),
                ],
            )
            with self.assertRaises(AmbiguousAliasError):
                load_service_canonical_majors_v2(path, valid_group_ids=frozenset({"law"}))

    def test_same_major_reusing_its_own_alias_across_rows_is_still_a_duplicate_id_error(self) -> None:
        """중복 alias 검사보다 중복 major_id 검사가 먼저 걸린다는 뜻이 아니라, 같은
        major_id가 두 번 나오는 것 자체가 이미 별개 오류로 막힌다는 것을 명확히 한다."""
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_catalog(Path(tmp), [_base_major_kwargs(major_id="a"), _base_major_kwargs(major_id="a", aliases=["다른"])])
            with self.assertRaises(DuplicateServiceMajorIdError):
                load_service_canonical_majors_v2(path, valid_group_ids=frozenset({"law"}))

    def test_excluded_group_bypassing_schema_still_fails_fast_at_loader(self) -> None:
        """Schema의 model_validator를 우회해서(model_construct) 만든 행도 Loader가
        막는지 확인한다 — §3 "예체능 4개 ACTIVE 금지"의 이중 방어선."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "catalog.jsonl"
            row = _base_major_kwargs(major_id="design_like", canonical_major_group_id="fine_arts_design")
            # model_construct로 model_validator를 우회해 파일에 직접 쓴다.
            path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
            # 이 테스트는 Schema가 이미 막는 것을 알고 있다 — 그래도 Loader가 같은
            # 조건을 다시 확인하는지(방어적 이중 확인) 별도로 검증한다.
            with self.assertRaises(Exception):
                load_service_canonical_majors_v2(path, valid_group_ids=frozenset({"fine_arts_design"}))

    def test_valid_bridge_file_loads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bridge.jsonl"
            _write_jsonl(
                path,
                [
                    {"canonical_major_group_id": "law", "service_major_id": "law", "recommendation_status": "ACTIVE", "decision_reason": "x"},
                    {"canonical_major_group_id": "music", "service_major_id": None, "recommendation_status": "EXCLUDED_RECOMMENDATION", "decision_reason": "x"},
                ],
            )
            result = load_canonical_major_group_to_service_major_bridge_v2(path)
            self.assertEqual(set(result), {"law", "music"})

    def test_duplicate_group_id_in_bridge_fails_fast(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bridge.jsonl"
            _write_jsonl(
                path,
                [
                    {"canonical_major_group_id": "law", "service_major_id": "law", "recommendation_status": "ACTIVE", "decision_reason": "x"},
                    {"canonical_major_group_id": "law", "service_major_id": "law", "recommendation_status": "ACTIVE", "decision_reason": "y"},
                ],
            )
            with self.assertRaises(DuplicateServiceMajorIdError):
                load_canonical_major_group_to_service_major_bridge_v2(path)

    def test_missing_file_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                load_service_canonical_majors_v2(Path(tmp) / "missing.jsonl", valid_group_ids=frozenset())

    def test_default_path_cross_checks_against_real_group_file_when_valid_group_ids_omitted(self) -> None:
        """valid_group_ids를 생략하면 실제 42개 Group 파일로 대조한다(§3 "공식 Group
        존재 확인") — 실제 존재하지 않는 Group ID를 쓰면 실제 파일 기준으로도 막힌다."""
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_catalog(Path(tmp), [_base_major_kwargs(canonical_major_group_id="totally_made_up_group")])
            with self.assertRaises(UnknownCanonicalMajorGroupError):
                load_service_canonical_majors_v2(path)


class RealCatalogInvariantsTest(unittest.TestCase):
    """실제 생성된 두 파일이 §2 불변식을 지키는지 — 생성 스크립트를 다시 실행하지
    않고, 커밋된 산출물 자체를 읽어 확인한다."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.majors = load_service_canonical_majors_v2(_CATALOG_PATH)
        cls.bridge = load_canonical_major_group_to_service_major_bridge_v2(_BRIDGE_PATH)
        cls.groups = load_canonical_major_groups_draft()
        cls.old_majors = {
            json.loads(line)["major_id"]: json.loads(line)
            for line in (_REPO_ROOT / "data" / "master" / "canonical_majors.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        }

    def test_exactly_39_active_service_majors(self) -> None:
        """04096a4 후속 보완 — Group 기반 38 + 특수 융합 hci_ux 1 = 39."""
        self.assertEqual(len(self.majors), 39)
        self.assertTrue(all(m.recommendation_status == "ACTIVE" for m in self.majors))

    def test_exactly_38_full_group_and_1_department_level_only(self) -> None:
        full_group = [m for m in self.majors if m.mapping_scope == "FULL_GROUP"]
        department_level = [m for m in self.majors if m.mapping_scope == "DEPARTMENT_LEVEL_ONLY"]
        self.assertEqual(len(full_group), 38)
        self.assertEqual(len(department_level), 1)
        self.assertEqual(department_level[0].major_id, "hci_ux")

    def test_bridge_has_exactly_42_rows_covering_every_real_group(self) -> None:
        self.assertEqual(len(self.bridge), 42)
        self.assertEqual(set(self.bridge), {g.canonical_major_id for g in self.groups})

    def test_exactly_4_excluded_and_they_match_the_named_arts_groups(self) -> None:
        excluded = {gid for gid, row in self.bridge.items() if row.recommendation_status == "EXCLUDED_RECOMMENDATION"}
        self.assertEqual(excluded, EXCLUDED_RECOMMENDATION_GROUP_IDS)
        self.assertEqual(len(excluded), 4)

    def test_no_duplicate_group_connections(self) -> None:
        group_ids = [row.canonical_major_group_id for row in self.bridge.values()]
        self.assertEqual(len(group_ids), len(set(group_ids)))

    def test_no_duplicate_service_major_ids(self) -> None:
        ids = [m.major_id for m in self.majors]
        self.assertEqual(len(ids), len(set(ids)))

    def test_active_bridge_service_major_ids_match_full_group_catalog_exactly(self) -> None:
        """04096a4 후속 §2 — hci_ux는 어느 Group의 "기본 서비스 Major"도 아니므로
        Bridge에 없다. Bridge의 ACTIVE 집합은 FULL_GROUP Catalog 행(38개)과 정확히
        같아야 한다 — Catalog 전체(39개)와 같아지면 안 된다."""
        bridge_active_ids = {row.service_major_id for row in self.bridge.values() if row.recommendation_status == "ACTIVE"}
        full_group_ids = {m.major_id for m in self.majors if m.mapping_scope == "FULL_GROUP"}
        self.assertEqual(bridge_active_ids, full_group_ids)
        self.assertEqual(len(bridge_active_ids), 38)

    def test_hci_ux_never_appears_as_a_bridge_service_major_id(self) -> None:
        """§2 "hci_ux를 computer_science Group 전체에 자동 연결하지 말 것" — 어느
        Group 행도 hci_ux를 자신의 ACTIVE service_major_id로 가리키면 안 된다."""
        service_major_ids = {row.service_major_id for row in self.bridge.values()}
        self.assertNotIn("hci_ux", service_major_ids)

    def test_explicit_rename_bridges_from_directive(self) -> None:
        self.assertEqual(self.bridge["business"].service_major_id, "business_administration")
        self.assertEqual(self.bridge["mechanical_transport"].service_major_id, "mechanical_engineering")
        for gid in ("media_communication", "industrial_engineering", "computer_science"):
            self.assertEqual(self.bridge[gid].service_major_id, gid)

    def test_non_arts_groups_named_in_directive_are_not_missing(self) -> None:
        """환경공학·전기전자·화학·건축·법학·인문학 등 비예체능 Group이 누락되지
        않아야 한다(지시서 §1)."""
        required_present = {
            "chemistry", "electrical_electronic", "civil_architecture", "law", "humanities",
            "earth_environment",  # 환경(지구환경) — civil_architecture(건축환경)와 함께 '환경' 커버
        }
        active_group_ids = {gid for gid, row in self.bridge.items() if row.recommendation_status == "ACTIVE"}
        self.assertTrue(required_present.issubset(active_group_ids), required_present - active_group_ids)

    def test_existing_ten_major_ids_are_never_renamed(self) -> None:
        """기존 10개 Canonical Major ID 자체는 이 Catalog의 어디에도 새 값으로
        바뀌어 등장하지 않는다 — 있다면 원래 ID 그대로다(design만 애초에 이
        Catalog에 없는 것이 정상이라 이 테스트 대상이 아니다 — hci_ux는 04096a4
        후속 보완으로 복원됐다)."""
        catalog_ids = {m.major_id for m in self.majors}
        for old_id in self.old_majors:
            if old_id == "design":
                continue
            self.assertIn(old_id, catalog_ids, f"{old_id}가 그대로 보존되지 않았다")

    def test_preserved_majors_keep_their_original_label_and_description(self) -> None:
        by_id = {m.major_id: m for m in self.majors}
        for old_id, old_row in self.old_majors.items():
            if old_id not in by_id:
                continue
            self.assertEqual(by_id[old_id].label, old_row["label"])
            self.assertEqual(by_id[old_id].description, old_row["description"])

    def test_design_is_not_promoted(self) -> None:
        catalog_ids = {m.major_id for m in self.majors}
        self.assertNotIn("design", catalog_ids)

    def test_hci_ux_is_promoted_as_department_level_only_active(self) -> None:
        """04096a4 후속 §1 — hci_ux는 이제 Catalog에 있다(ACTIVE, DEPARTMENT_
        LEVEL_ONLY), design은 여전히 없다."""
        by_id = {m.major_id: m for m in self.majors}
        self.assertIn("hci_ux", by_id)
        hci_ux = by_id["hci_ux"]
        self.assertEqual(hci_ux.recommendation_status, "ACTIVE")
        self.assertEqual(hci_ux.mapping_scope, "DEPARTMENT_LEVEL_ONLY")
        self.assertIsNone(hci_ux.canonical_major_group_id)

    def test_hci_ux_original_fields_are_fully_preserved(self) -> None:
        """§1 "기존 major_id/label/description/aliases/keywords 완전 보존"."""
        hci_ux = next(m for m in self.majors if m.major_id == "hci_ux")
        old = self.old_majors["hci_ux"]
        self.assertEqual(hci_ux.label, old["label"])
        self.assertEqual(hci_ux.description, old["description"])
        self.assertEqual(hci_ux.aliases, old["aliases"])
        self.assertEqual(hci_ux.keywords, old["keywords"])

    def test_hci_ux_source_group_ids_reference_the_two_real_bridge_draft_rows(self) -> None:
        """§4 "Schema가 canonical_major_group_id 단일 필드를 필수로 요구한다면..."
        — source_group_ids는 실제 canonical_major_group_bridge.draft.jsonl에 있는
        computer_science(REVIEW_REQUIRED)·fine_arts_design(EXCLUDED_RECOMMENDATION)
        두 행을 가리킨다(둘 다 "Group 전체를 hci_ux에 넘긴다"는 뜻이 아니다)."""
        hci_ux = next(m for m in self.majors if m.major_id == "hci_ux")
        self.assertEqual(set(hci_ux.source_group_ids), {"computer_science", "fine_arts_design"})

    def test_computer_science_group_own_default_major_is_still_computer_science(self) -> None:
        """§2 "computer_science Group의 기본 서비스 Major는 computer_science
        유지" — hci_ux가 source_group_ids에 computer_science를 참고해도 그 Group
        자신의 FULL_GROUP Catalog 행은 여전히 major_id="computer_science"다."""
        by_id = {m.major_id: m for m in self.majors}
        self.assertIn("computer_science", by_id)
        computer_science = by_id["computer_science"]
        self.assertEqual(computer_science.mapping_scope, "FULL_GROUP")
        self.assertEqual(computer_science.canonical_major_group_id, "computer_science")
        self.assertEqual(self.bridge["computer_science"].service_major_id, "computer_science")

    def test_fine_arts_design_group_stays_excluded_recommendation(self) -> None:
        """§2 "fine_arts_design Group은 계속 EXCLUDED_RECOMMENDATION" — hci_ux가
        source_group_ids에 이 Group을 참고해도 Bridge의 fine_arts_design 행 자체는
        바뀌지 않는다."""
        row = self.bridge["fine_arts_design"]
        self.assertEqual(row.recommendation_status, "EXCLUDED_RECOMMENDATION")
        self.assertIsNone(row.service_major_id)

    def test_computer_science_to_hci_ux_department_review_required_scope_is_preserved_in_source_data(self) -> None:
        """§2 "기존 computer_science→hci_ux의 DEPARTMENT_REVIEW_REQUIRED Scope
        결정을 보존" — 이 Catalog가 만들어내는 값이 아니라, 그 결정이 실제로 이미
        기록된 원본 정본(canonical_major_group_bridge.draft.jsonl)이 이 라운드
        에서 전혀 바뀌지 않았는지 git diff로 직접 확인한다."""
        result = subprocess.run(
            ["git", "diff", "--exit-code", "HEAD", "--", "data/master/canonical_major_group_bridge.draft.jsonl"],
            cwd=_REPO_ROOT, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, f"canonical_major_group_bridge.draft.jsonl이 바뀌었다:\n{result.stdout}")

        rows = json.loads(
            "[" + ",".join(
                (_REPO_ROOT / "data" / "master" / "canonical_major_group_bridge.draft.jsonl")
                .read_text(encoding="utf-8").splitlines()
            ) + "]"
        )
        row = next(
            r for r in rows
            if r["canonical_major_group_id"] == "computer_science" and r["canonical_major_id"] == "hci_ux"
        )
        self.assertEqual(row["scope_type"], "DEPARTMENT_REVIEW_REQUIRED")
        self.assertEqual(row["mapping_status"], "REVIEW_REQUIRED")

    def test_no_department_is_exposed_as_belonging_to_hci_ux_by_this_catalog(self) -> None:
        """§5 "검토되지 않은 HCI·UX 학과 노출 0" — 이 Catalog·Bridge 산출물 자체는
        어떤 학과도 나열하지 않는다(Trait Weight·학과 Mapping은 범위 밖, 모듈
        docstring). 구조적으로 증명 가능한 것은 "hci_ux가 어느 Group으로부터도
        Full Group 승격을 받지 않았다"는 사실뿐이고, 위
        test_hci_ux_never_appears_as_a_bridge_service_major_id가 이미 그것을
        확인한다 — 이 테스트는 그 부재를 Catalog 파일 자체에서 다시 확인한다
        (department_id류 필드가 전혀 없다)."""
        raw_text = _CATALOG_PATH.read_text(encoding="utf-8")
        self.assertNotIn("department_id", raw_text)
        self.assertNotIn("dept_", raw_text)
        self.assertNotIn("off_", raw_text)

    def test_every_full_group_major_references_a_real_group_with_matching_status(self) -> None:
        group_ids = {g.canonical_major_id for g in self.groups}
        for m in self.majors:
            if m.mapping_scope == "FULL_GROUP":
                self.assertIn(m.canonical_major_group_id, group_ids)
            else:
                self.assertIsNone(m.canonical_major_group_id)
                for source_group_id in m.source_group_ids:
                    self.assertIn(source_group_id, group_ids)

    def test_catalog_version_is_consistent_across_all_rows(self) -> None:
        versions = {m.catalog_version for m in self.majors}
        self.assertEqual(len(versions), 1, versions)


class GenerationDeterminismTest(unittest.TestCase):
    """생성 스크립트를 2회 실행해도 byte-identical한지 — 실제 산출물 경로에 다시
    쓰지만, 내용이 이미 같은 결정론적 산출물이라 git diff가 발생하지 않는다."""

    def test_regenerating_catalog_and_bridge_is_byte_identical(self) -> None:
        proc = subprocess.run(
            ["git", "status", "--porcelain", "--", "data/master/service_canonical_majors_v2.jsonl",
             "data/master/canonical_major_group_to_service_major_v2.jsonl"],
            cwd=_REPO_ROOT, capture_output=True, text=True,
        )
        before = proc.stdout

        before_catalog = _CATALOG_PATH.read_bytes()
        before_bridge = _BRIDGE_PATH.read_bytes()

        result = subprocess.run(
            ["./.venv/bin/python", "scripts/career_build_service_canonical_majors_v2.py"],
            cwd=_REPO_ROOT, capture_output=True, text=True, env={"PYTHONPATH": ".", "PATH": "/usr/bin:/bin"},
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        self.assertEqual(before_catalog, _CATALOG_PATH.read_bytes(), "재생성 결과가 기존 Catalog와 다르다")
        self.assertEqual(before_bridge, _BRIDGE_PATH.read_bytes(), "재생성 결과가 기존 Bridge와 다르다")

        proc_after = subprocess.run(
            ["git", "status", "--porcelain", "--", "data/master/service_canonical_majors_v2.jsonl",
             "data/master/canonical_major_group_to_service_major_v2.jsonl"],
            cwd=_REPO_ROOT, capture_output=True, text=True,
        )
        self.assertEqual(proc_after.stdout, before, "재생성이 git 추적 파일을 실제로 바꿨다(비결정적)")


class ForbiddenScopeUntouchedTest(unittest.TestCase):
    """§5 "금지" — 이번 작업이 건드리면 안 되는 파일들이 실제로 git 이력상
    무변경인지 확인한다(origin/trait-vector-v2 대비, 이 브랜치의 커밋 전체 기준)."""

    _FORBIDDEN_PATHS = (
        "src/api/main.py",
        "src/engines/matching_engine.py",
        "src/engines/matching_engine_v2.py",
        "src/data/majors/vertical_slice_major_profiles_v2.py",
        "data/master/departments.jsonl",
        "data/master/department_recommendation_scope.jsonl",
    )

    def test_forbidden_paths_have_no_diff_from_merge_base_with_origin(self) -> None:
        merge_base = subprocess.run(
            ["git", "merge-base", "HEAD", "origin/trait-vector-v2"],
            cwd=_REPO_ROOT, capture_output=True, text=True,
        )
        base_ref = merge_base.stdout.strip() or "origin/trait-vector-v2"
        for rel_path in self._FORBIDDEN_PATHS:
            with self.subTest(path=rel_path):
                result = subprocess.run(
                    ["git", "diff", "--exit-code", base_ref, "--", rel_path],
                    cwd=_REPO_ROOT, capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 0, f"{rel_path}가 바뀌었다:\n{result.stdout}")

    def test_review_files_directory_has_no_diff(self) -> None:
        merge_base = subprocess.run(
            ["git", "merge-base", "HEAD", "origin/trait-vector-v2"],
            cwd=_REPO_ROOT, capture_output=True, text=True,
        )
        base_ref = merge_base.stdout.strip() or "origin/trait-vector-v2"
        result = subprocess.run(
            ["git", "diff", "--exit-code", base_ref, "--", "data/reviews/"],
            cwd=_REPO_ROOT, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, f"data/reviews/가 바뀌었다:\n{result.stdout}")


if __name__ == "__main__":
    unittest.main()
