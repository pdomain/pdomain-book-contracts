# tests/test_review_metadata_provenance.py
from __future__ import annotations


def test_defaults_keep_existing_records_valid() -> None:
    from pdomain_book_contracts.annotation import KnowledgeState
    from pdomain_book_contracts.ocr import ReviewMetadata

    review = ReviewMetadata()
    assert review.source is None
    assert review.state == KnowledgeState.UNKNOWN


def test_source_and_state_round_trip() -> None:
    from pdomain_book_contracts.annotation import KnowledgeState, LabelSource
    from pdomain_book_contracts.ocr import ReviewMetadata

    review = ReviewMetadata(
        validated=True,
        source=LabelSource.HUMAN,
        state=KnowledgeState.POSITIVE,
    )
    restored = ReviewMetadata.from_dict(review.to_dict())
    assert restored == review
    assert restored.source == LabelSource.HUMAN
    assert restored.state == KnowledgeState.POSITIVE


def test_a_rejection_is_expressible() -> None:
    from pdomain_book_contracts.annotation import KnowledgeState, LabelSource
    from pdomain_book_contracts.ocr import ReviewMetadata

    rejected = ReviewMetadata(
        source=LabelSource.HUMAN, state=KnowledgeState.VERIFIED_NEGATIVE
    )
    assert (
        ReviewMetadata.from_dict(rejected.to_dict()).state
        == KnowledgeState.VERIFIED_NEGATIVE
    )


def test_an_f2_supplied_answer_is_distinguishable_from_a_typed_one() -> None:
    from pdomain_book_contracts.annotation import LabelSource
    from pdomain_book_contracts.ocr import ReviewMetadata

    aligned = ReviewMetadata(source=LabelSource.F2)
    typed = ReviewMetadata(source=LabelSource.HUMAN)
    assert aligned.source != typed.source


def test_a_legacy_dict_without_the_new_keys_still_loads() -> None:
    from pdomain_book_contracts.annotation import KnowledgeState
    from pdomain_book_contracts.ocr import ReviewMetadata

    legacy = {"validated": True, "reviewer_note": None, "flagged_for_attention": False}
    restored = ReviewMetadata.from_dict(legacy)
    assert restored.validated is True
    assert restored.source is None
    assert restored.state == KnowledgeState.UNKNOWN
