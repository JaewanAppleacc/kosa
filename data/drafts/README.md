# C 작업자 초안 저장 영역

이 디렉터리는 C가 작성하는 Context·Trait 검토안, Question Blueprint, Major–Trait 및 Subject–Trait Mapping 초안을 저장한다.

```text
context_trait_reviews/
question_blueprints/
major_trait_mappings/
subject_trait_mappings/
```

초안은 A가 소유하는 `src/data/`의 확정 데이터를 직접 덮어쓰지 않는다. 각 파일의 메타데이터는 `src/schemas/review.py`의 `DraftEntry`를 따른다.

```python
from src.schemas.review import DraftEntry, DraftReviewStage

DraftEntry(
    draft_id="...",
    draft_type="major_trait_mapping",  # 또는 context_trait_review / question_blueprint / subject_trait_mapping
    author_id="...",
    review_stage=DraftReviewStage.DRAFT,  # DRAFT → STAGED → PUBLISHED
    source_url="...",
    as_of_date="...",
)
```

`review_stage`는 `MappingReview.agreement_status`(§15, AGREED/REVIEW_REQUIRED/REJECTED)와 다른 개념이다 — 그건 Major-Trait Mapping 하나를 2인이 정식 교차검토하는 절차 전용이고, 이건 이 폴더에 쌓이는 모든 초안이 확정 데이터로 승격되기 전 어느 단계인지 보는 것이다.

A의 검토·승인(`PUBLISHED`)을 받은 데이터만 확정 데이터(`src/data/`)나 실제 Repository 입력으로 승격한다.
