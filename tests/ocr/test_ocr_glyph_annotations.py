from __future__ import annotations

from dataclasses import dataclass

import pytest

from pdomain_book_contracts.ocr.glyph_annotations import (
    GlyphAnnotations,
    GlyphSource,
    LigatureKind,
    LigatureMark,
)


@dataclass
class _Word:
    ground_truth_text: str


def test_ligature_mark_round_trip_with_span() -> None:
    mark = LigatureMark(kind=LigatureKind.FFI, char_span=(1, 4))
    assert mark.to_dict() == {"kind": "FFI", "char_span": [1, 4]}
    assert LigatureMark.from_dict(mark.to_dict()) == mark


def test_ligature_mark_round_trip_without_span() -> None:
    mark = LigatureMark(kind=LigatureKind.CT)
    assert mark.to_dict() == {"kind": "CT", "char_span": None}
    assert LigatureMark.from_dict(mark.to_dict()) == mark


def test_ligature_mark_missing_span_key_means_unknown_location() -> None:
    assert LigatureMark.from_dict({"kind": "FI"}).char_span is None


@pytest.mark.parametrize(
    ("legacy", "expected"),
    [
        ("fi", LigatureKind.FI),
        ("ffl", LigatureKind.FFL),
        ("long_s_t", LigatureKind.LONG_ST),
        ("LONG_S_T", LigatureKind.LONG_ST),
        ("long_s_s", LigatureKind.LONG_S_S),
        ("qu", LigatureKind.QU),
        ("OE", LigatureKind.OE),
    ],
)
def test_ligature_mark_migrates_legacy_kind_strings(
    legacy: str, expected: LigatureKind
) -> None:
    assert LigatureMark.from_dict({"kind": legacy}).kind is expected


def test_ligature_mark_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError, match="swirl"):
        LigatureMark.from_dict({"kind": "swirl"})


def test_glyph_annotations_default_means_reviewed_and_empty() -> None:
    assert GlyphAnnotations().to_dict() == {
        "ligatures": [],
        "long_s_positions": [],
        "swash": False,
        "source": "human",
    }


def test_glyph_annotations_round_trip() -> None:
    annotations = GlyphAnnotations(
        ligatures=[
            LigatureMark(LigatureKind.FI, (0, 2)),
            LigatureMark(LigatureKind.ST),
        ],
        long_s_positions=[3],
        swash=True,
        source="human_confirmed",
    )
    assert GlyphAnnotations.from_dict(annotations.to_dict()) == annotations


def test_glyph_annotations_from_empty_dict_uses_defaults() -> None:
    assert GlyphAnnotations.from_dict({}) == GlyphAnnotations()


def test_glyph_annotations_from_dict_treats_null_lists_as_empty() -> None:
    parsed = GlyphAnnotations.from_dict({"ligatures": None, "long_s_positions": None})
    assert parsed == GlyphAnnotations()


def test_glyph_annotations_from_dict_propagates_unknown_ligature_kind() -> None:
    with pytest.raises(ValueError, match="nope"):
        GlyphAnnotations.from_dict({"ligatures": [{"kind": "nope"}]})


@pytest.mark.parametrize("source", ["human", "predicted", "human_confirmed"])
def test_glyph_annotations_accepts_each_provenance(source: GlyphSource) -> None:
    assert GlyphAnnotations(source=source).source == source


def test_glyph_annotations_rejects_unknown_source_from_dict() -> None:
    with pytest.raises(ValueError, match="not a recognised provenance"):
        GlyphAnnotations.from_dict({"source": "robot"})


def test_validate_accepts_consistent_annotations() -> None:
    annotations = GlyphAnnotations(
        ligatures=[
            LigatureMark(LigatureKind.FI, (0, 2)),
            LigatureMark(LigatureKind.CT),
        ],
        long_s_positions=[2, 5],
    )
    annotations.validate(_Word("fisstS"))


def test_validate_accepts_span_covering_whole_word() -> None:
    GlyphAnnotations(ligatures=[LigatureMark(LigatureKind.FI, (0, 2))]).validate(
        _Word("fi")
    )


@pytest.mark.parametrize(
    "banned",
    [
        "\N{LATIN SMALL LIGATURE FF}",
        "\N{LATIN SMALL LIGATURE FI}",
        "\N{LATIN SMALL LIGATURE FL}",
        "\N{LATIN SMALL LIGATURE FFI}",
        "\N{LATIN SMALL LIGATURE FFL}",
        "\N{LATIN SMALL LIGATURE LONG S T}",
        "\N{LATIN SMALL LIGATURE ST}",
        "\N{LATIN SMALL LETTER LONG S}",
    ],
)
def test_validate_rejects_ligature_and_long_s_codepoints_in_gt(banned: str) -> None:
    with pytest.raises(ValueError, match=f"banned codepoint U\\+{ord(banned):04X}"):
        GlyphAnnotations().validate(_Word(f"a{banned}b"))


def test_validate_treats_empty_gt_as_empty_string() -> None:
    GlyphAnnotations().validate(_Word(""))


@pytest.mark.parametrize("span", [(-1, 2), (2, 2), (3, 2), (0, 5)])
def test_validate_rejects_bad_ligature_spans(span: tuple[int, int]) -> None:
    annotations = GlyphAnnotations(ligatures=[LigatureMark(LigatureKind.FI, span)])
    with pytest.raises(ValueError, match=r"ligatures\[0\]\.char_span"):
        annotations.validate(_Word("fish"))


def test_validate_reports_index_of_the_bad_ligature() -> None:
    annotations = GlyphAnnotations(
        ligatures=[
            LigatureMark(LigatureKind.FI, (0, 2)),
            LigatureMark(LigatureKind.FL, (3, 9)),
        ]
    )
    with pytest.raises(ValueError, match=r"ligatures\[1\]"):
        annotations.validate(_Word("fish"))


@pytest.mark.parametrize("idx", [-1, 4])
def test_validate_rejects_out_of_range_long_s_position(idx: int) -> None:
    with pytest.raises(ValueError, match="out of range"):
        GlyphAnnotations(long_s_positions=[idx]).validate(_Word("fish"))


def test_validate_rejects_long_s_position_not_pointing_at_s() -> None:
    with pytest.raises(ValueError, match="not 's' or 'S'"):
        GlyphAnnotations(long_s_positions=[0]).validate(_Word("fish"))
