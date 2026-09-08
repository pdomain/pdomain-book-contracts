# tests/test_annotation_vocabularies.py
from __future__ import annotations


def test_provenance_enums_import_from_annotation() -> None:
    from pdomain_book_contracts.annotation import (
        ConfidenceTier,
        KnowledgeState,
        LabelSource,
    )

    assert KnowledgeState.VERIFIED_NEGATIVE == "verified_negative"
    assert KnowledgeState.CONFLICT == "conflict"
    assert LabelSource.HUMAN == "human"
    assert ConfidenceTier.QUARANTINE == "quarantine"


def test_a_model_can_be_named_as_the_source() -> None:
    """The five shipped values are document sources and a person.

    Nothing among them can say a model proposed something, which is the claim
    the labeling track exists to record.
    """
    from pdomain_book_contracts.annotation import LabelSource

    assert LabelSource.MODEL == "model"


def test_the_f2_parser_s_source_is_unchanged() -> None:
    from pdomain_book_contracts.annotation import LabelSource

    # Additive only: the one existing consumer must keep working.
    assert LabelSource.F2 == "f2"


def test_typography_labels_still_re_export_them() -> None:
    from pdomain_book_contracts.annotation import KnowledgeState as Moved
    from pdomain_book_contracts.typography.labels import KnowledgeState as ReExported

    assert Moved is ReExported
