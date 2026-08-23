"""Context Pack Registry — 2026-08-23 Trait Ontology v2(2.7단계) §1/§2/§6. A 소유
(중앙 파일 소유권, `src/data/context_packs/*.py` 개별 Pack 파일과는 별개).

Context 제작 에이전트는 `src/data/context_packs/`에 자기 Context 하나당 새 파일 하나만
추가하면 된다(`CONTEXT_PACK: ContextPack` 최상위 상수 노출) — 이 파일도, `__init__.py`
도, `src/api/main.py`도 수정할 필요가 없다. `discover_context_packs()`가
`pkgutil.iter_modules()`로 그 디렉터리를 훑어 `CONTEXT_PACK`을 가진 모듈만 자동으로
찾는다(명시적 등록 목록을 두지 않는다 — 공유 파일을 아무도 편집할 필요가 없게 하기
위함).

Fail-Fast 원칙(§1): `ContextPack`의 Cross-field 검증(Anchor 5개, Rationale 필수 등)은
그 모듈을 **import하는 시점에** Pydantic이 즉시 예외를 던진다(각 Pack 파일이
`CONTEXT_PACK = ContextPack(...)`처럼 모듈 최상위에서 즉시 생성하는 기존 관례,
`ANCHOR_BACKUP_QUESTIONS` 등과 동일). 이 Registry는 그 예외를 삼키지 않고
`discovery_errors()`로 그대로 노출하되(CLAUDE.md "예외를 삼키지 않는다"), 한 Context
Pack이 깨졌다고 다른 정상 Pack까지, 나아가 App 전체(main.py)까지 죽이지는 않는다 —
여러 Context 제작 에이전트가 동시에 작업하는 상황에서 한 명의 실수가 전체를 막으면
안 되기 때문이다. 대신 깨진 Pack은 Registry에 아예 등록되지 않는다(Fail-Closed —
"등록 안 됨"과 "검수 안 됨"을 같은 값으로 처리한다).

24개 Trait Ontology 존재 여부·검수 상태(reviewer_1 APPROVED)처럼 Pack 밖의 정본과
비교해야 하는 검증은 여기(서비스 계층)에서 한다 — `src/schemas/context_pack.py`는
Pack 내부의 자기 완결적 구조만 본다(계층 분리, `trait_v2_direct_probe_blueprints.py`
와 동일 원칙)."""

from __future__ import annotations

import importlib
import json
import pkgutil
from pathlib import Path
from types import ModuleType

from src.data import context_packs as _context_packs_package
from src.schemas.context_pack import ContextPack
from src.schemas.v2_direct_probe_review import QuestionReviewEntry
from src.services.trait_ontology_v2 import load_trait_ontology_v2

_REVIEW_STATUS_DIR = Path(__file__).resolve().parents[2] / "data" / "reviews" / "context_packs"

# 2026-08-23 §6 — 다음 활성화 배치. Pack이 등록되고 검수(APPROVED)되기 전까지는
# 이 목록에 있어도 assessment_supported_context_ids()에 포함되지 않는다(Fail-Closed).
CONTEXT_ACTIVATION_BATCHES: dict[int, frozenset[str]] = {
    1: frozenset({"business", "science", "sports"}),
    2: frozenset({"making", "volunteer", "writing", "travel"}),
    3: frozenset({"art_design", "cooking", "fashion_beauty", "history_humanities", "law_politics"}),
}
ALL_BATCH_CONTEXT_IDS: frozenset[str] = frozenset(
    context_id for batch in CONTEXT_ACTIVATION_BATCHES.values() for context_id in batch
)


class ContextPackRegistryError(ValueError):
    """개별 Pack이 아니라 Registry 자체의 구조적 오류(예: CONTEXT_PACK이 ContextPack
    인스턴스가 아님)일 때 — 이건 Fail-Closed 제외가 아니라 즉시 예외로 드러낸다."""


def discover_context_packs(
    package: ModuleType = _context_packs_package,
) -> tuple[dict[str, ContextPack], dict[str, str]]:
    """`(context_id -> ContextPack, module_name -> 오류 메시지)`를 반환한다. 오류가 난
    모듈은 첫 번째 dict에 들어가지 않는다(Fail-Closed) — 두 번째 dict로 원인을 그대로
    보존한다(조용히 삼키지 않는다)."""

    packs: dict[str, ContextPack] = {}
    errors: dict[str, str] = {}
    package_path = Path(package.__file__).resolve().parent

    for module_info in pkgutil.iter_modules([str(package_path)]):
        if module_info.name.startswith("_"):
            continue  # `_example_pack_builder.py`류 — 실제 Pack이 아니다(모듈 docstring 참고).
        module_full_name = f"{package.__name__}.{module_info.name}"
        try:
            module = importlib.import_module(module_full_name)
            pack = getattr(module, "CONTEXT_PACK", None)
            if pack is None:
                continue  # CONTEXT_PACK을 노출하지 않는 모듈은 자동 발견 대상이 아니다.
            if not isinstance(pack, ContextPack):
                raise ContextPackRegistryError(
                    f"{module_full_name}.CONTEXT_PACK은 ContextPack 인스턴스여야 한다"
                    f"(got {type(pack).__name__})"
                )
            if pack.context_id in packs:
                raise ContextPackRegistryError(
                    f"context_id {pack.context_id!r}가 두 개 이상의 Pack 모듈에서 등록됐다"
                    f"(먼저 등록됨: 알 수 없음, 지금: {module_full_name})"
                )
            packs[pack.context_id] = pack
        except Exception as exc:  # noqa: BLE001 — 한 Pack의 실패가 다른 Pack·App 전체를 막지 않는다.
            errors[module_full_name] = f"{type(exc).__name__}: {exc}"
    return packs, errors


class ContextPackRegistry:
    """Pack 발견·검증·검수 상태 조회를 한 곳에서 담당한다. `main.py`는 이 클래스의
    인스턴스 하나만 앱 시작 시 만들어 쓴다(Department/Subject Repository와 같은 패턴)."""

    def __init__(
        self, *, known_context_ids: frozenset[str], known_trait_ids: frozenset[str] | None = None,
        review_status_dir: Path | None = None,
        _discovered: tuple[dict[str, ContextPack], dict[str, str]] | None = None,
    ) -> None:
        """`_discovered`는 테스트 전용 주입 지점이다(실제 `src/data/context_packs/`
        디렉터리를 훑지 않고 미리 구성한 Pack 집합으로 Ontology·검수 검증만 단위
        테스트하기 위함) — 운영 코드(main.py)는 이 인자를 절대 넘기지 않는다."""

        self._known_context_ids = known_context_ids
        self._known_trait_ids = (
            known_trait_ids if known_trait_ids is not None
            else frozenset(t.trait_id for t in load_trait_ontology_v2())
        )
        self._review_status_dir = review_status_dir or _REVIEW_STATUS_DIR
        packs, discovery_errors = _discovered if _discovered is not None else discover_context_packs()
        self._packs = dict(packs)
        self._discovery_errors = dict(discovery_errors)
        self._ontology_errors: dict[str, str] = {}
        for context_id, pack in list(self._packs.items()):
            error = self._validate_against_ontology(pack)
            if error is not None:
                self._ontology_errors[context_id] = error
                del self._packs[context_id]

    def _validate_against_ontology(self, pack: ContextPack) -> str | None:
        if pack.context_id not in self._known_context_ids:
            return f"context_id {pack.context_id!r}가 CONTEXT_DEFINITIONS(known context)에 없다"

        trait_ids: set[str] = set()
        for seed in pack.seed_anchor_variants:
            for option in seed.question.options:
                trait_ids.update(option.primary_trait_delta)
        for backup in pack.anchor_backup_questions:
            for option in backup.question.options:
                trait_ids.update(option.primary_trait_delta)
        for probe in pack.direct_probe_candidates:
            trait_ids.add(probe.trait_id)
            for mapping in probe.option_mappings:
                trait_ids.update(s.trait_id for s in mapping.trait_signals)

        unknown = trait_ids - self._known_trait_ids
        if unknown:
            return f"24개 Trait Ontology에 없는 trait_id: {sorted(unknown)}"
        return None

    def discovery_errors(self) -> dict[str, str]:
        """Pack 파싱·구조 오류(모듈 import 시점) — Ontology 오류와 구분해 별도로 노출한다."""

        return dict(self._discovery_errors)

    def ontology_errors(self) -> dict[str, str]:
        """구조는 정상이지만 24개 Trait Ontology와 어긋나는 Pack — context_id 기준."""

        return dict(self._ontology_errors)

    def all_packs(self) -> list[ContextPack]:
        return list(self._packs.values())

    def get_pack(self, context_id: str) -> ContextPack | None:
        return self._packs.get(context_id)

    def review_status_path_for(self, context_id: str) -> Path:
        return self._review_status_dir / f"{context_id}_review_status.json"

    def required_review_keys(self, pack: ContextPack) -> set[str]:
        """§1 "Review 상태는 최초 전부 DRAFT" — 이 Pack이 실제 서비스에 쓰이려면
        검수돼야 하는 질문 단위 Key 전체(질문 단위만, Option 단위는 이번 계약 범위
        밖 — §11 한계로 보고)."""

        keys = {f"{pack.context_id}::routing::{pack.routing_blueprint.blueprint_id}"}
        keys.update(f"{pack.context_id}::seed::{s.anchor_id}" for s in pack.seed_anchor_variants)
        keys.update(f"{pack.context_id}::anchor_backup::{b.anchor_id}" for b in pack.anchor_backup_questions)
        keys.update(f"{pack.context_id}::direct_probe::{p.blueprint_id}" for p in pack.direct_probe_candidates)
        return keys

    def is_pack_review_approved(self, context_id: str) -> bool:
        """Fail-Closed — Pack이 없거나, 검수 상태 파일이 없거나, 필요한 Key 중
        하나라도 APPROVED가 아니면 False다. Claude가 이 파일을 대신 채우지 않는다
        (§1/§6 — 검수 결과는 사람이 직접 채운다, 기존 reviewer_1 정책과 동일)."""

        pack = self.get_pack(context_id)
        if pack is None:
            return False
        path = self.review_status_path_for(context_id)
        if not path.exists():
            return False
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            entries = {row["blueprint_id"]: QuestionReviewEntry.model_validate(row) for row in raw}
        except Exception:  # noqa: BLE001 — 파일이 깨져 있어도 Fail-Closed(승인 안 됨)일 뿐 죽지 않는다.
            return False

        required = self.required_review_keys(pack)
        return all(
            key in entries and entries[key].final_status == "APPROVED" for key in required
        )

    def assessment_supported_context_ids(self, base_supported_context_ids: list[str]) -> list[str]:
        """§6 — 기존 Vertical Slice 3개(game/media/school_life, Pack 없이도 항상
        지원)에 배치 Context 중 실제로 등록·검수된 것만 더한다. Pack이 없거나
        검수되지 않은 Context는 항상 제외된다(Fail-Closed) — Claude가 자동 APPROVE
        하지 않으므로 새 Pack이 merge돼도 사람이 검수하기 전까지는 이 목록이 그대로
        바뀌지 않는다."""

        supported = list(base_supported_context_ids)
        for batch_id in sorted(CONTEXT_ACTIVATION_BATCHES):
            for context_id in sorted(CONTEXT_ACTIVATION_BATCHES[batch_id]):
                if context_id in supported:
                    continue
                if self.is_pack_review_approved(context_id):
                    supported.append(context_id)
        return supported
