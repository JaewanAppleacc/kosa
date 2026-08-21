# C 작업자 초안 저장 영역

이 디렉터리는 C가 작성하는 Context·Trait 검토안, Question Blueprint, Major–Trait 및 Subject–Trait Mapping 초안을 저장한다.

```text
context_trait_reviews/
question_blueprints/
major_trait_mappings/
subject_trait_mappings/
```

초안은 A가 소유하는 `src/data/`의 확정 데이터를 직접 덮어쓰지 않는다. 각 파일에는 가능한 범위에서 다음 메타데이터를 포함한다.

```text
source_url
as_of_date
author_id
review_status: draft
```

A의 검토·승인을 받은 데이터만 확정 데이터나 실제 Repository 입력으로 승격한다.
