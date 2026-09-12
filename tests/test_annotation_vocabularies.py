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


def test_the_twenty_shipped_roles_are_unchanged() -> None:
    from pdomain_book_contracts.annotation import ALLOWED_REGION_ROLES

    shipped = {
        "paragraph",
        "sidenote",
        "page header",
        "page footer",
        "page number",
        "printers mark",
        "blockquote",
        "poetry",
        "recovered",
        "illustration",
        "decoration",
        "caption",
        "figure",
        "table",
        "footnote",
        "title",
        "section",
        "list",
        "formula",
        "artefact",
    }
    assert shipped <= ALLOWED_REGION_ROLES


def test_the_fourteen_additions_are_present() -> None:
    from pdomain_book_contracts.annotation import ALLOWED_REGION_ROLES

    additions = {
        "signature mark",
        "catchword",
        "press figure",
        "rule",
        "brace",
        "bracket",
        "group label",
        "plate",
        "speaker label",
        "stage direction",
        "interlinear gloss",
        "abandoned",
        "decorated initial",
        "unknown",
    }
    assert additions <= ALLOWED_REGION_ROLES
    assert len(ALLOWED_REGION_ROLES) == 34


def test_aliases_fold_to_canonical_roles() -> None:
    from pdomain_book_contracts.annotation import normalize_region_role

    assert normalize_region_role("frontispiece") == "plate"
    assert normalize_region_role("signaturemark") == "signature mark"
    assert normalize_region_role("pressfigure") == "press figure"
    assert normalize_region_role("stagedirection") == "stage direction"
    assert normalize_region_role("speakerlabel") == "speaker label"


def test_normalizer_accepts_case_and_separator_variants() -> None:
    from pdomain_book_contracts.annotation import normalize_region_role

    assert normalize_region_role("Page_Header") == "page header"
    assert normalize_region_role("  PAGE-NUMBER  ") == "page number"


def test_unknown_role_raises() -> None:
    import pytest

    from pdomain_book_contracts.annotation import normalize_region_role

    with pytest.raises(ValueError, match="Invalid region role"):
        normalize_region_role("marginalia")


def test_page_kind_covers_the_body_and_front_matter_cases() -> None:
    from pdomain_book_contracts.annotation import ALLOWED_PAGE_KINDS

    expected = {
        "body",
        "chapter opening",
        "title page",
        "half title",
        "contents",
        "index",
        "dedication",
        "preface",
        "errata",
        "plate",
        "blank",
        "advertisement",
        "colophon",
        "unknown",
    }
    assert expected == ALLOWED_PAGE_KINDS


def test_page_kind_has_an_explicit_unknown() -> None:
    from pdomain_book_contracts.annotation import PageKind

    assert PageKind.UNKNOWN == "unknown"


def test_page_kind_normalizer_folds_variants() -> None:
    from pdomain_book_contracts.annotation import normalize_page_kind

    assert normalize_page_kind("Chapter_Opening") == "chapter opening"
    assert normalize_page_kind("titlepage") == "title page"


def test_page_kind_rejects_a_packaging_value() -> None:
    import pytest

    from pdomain_book_contracts.annotation import normalize_page_kind

    # "skip" and "cover" belong to prep-for-pgdp's PageType, not here.
    with pytest.raises(ValueError, match="Invalid page kind"):
        normalize_page_kind("skip")
