from __future__ import annotations

import pytest
from pydantic import ValidationError

from pdomain_book_contracts.typography.labels import (
    ConfidenceTier,
    KnowledgeState,
    LabelSource,
    StyleLabel,
)
from pdomain_book_contracts.typography.spans import (
    SourceSlice,
    StyleSpan,
    TypographySpans,
    split_graphemes,
)

SHA = "ab" * 32


def _span(
    label: StyleLabel, start: int, end: int, *, slices: tuple[SourceSlice, ...] = ()
) -> StyleSpan:
    return StyleSpan(
        label=label,
        start=start,
        end=end,
        state=KnowledgeState.POSITIVE,
        label_source=LabelSource.F2,
        confidence_tier=ConfidenceTier.GOLD,
        source_slices=slices,
        rule_ref=None,
        semantic_reason=None,
        warnings=(),
    )


def test_split_graphemes_keeps_combining_marks_and_emoji_clusters_whole() -> None:
    text = "éa\U0001f469‍\U0001f4bbz"
    assert split_graphemes(text) == ("é", "a", "\U0001f469‍\U0001f4bb", "z")


def test_source_slice_round_trips_and_lowercases_the_hash() -> None:
    original = SourceSlice(artifact_sha256="AB" * 32, byte_start=3, byte_end=9)
    assert original.artifact_sha256 == SHA
    restored = SourceSlice.from_json_bytes(original.to_json_bytes())
    assert restored == original


def test_canonical_json_is_compact_sorted_and_keeps_non_ascii() -> None:
    payload = SourceSlice(artifact_sha256=SHA, byte_start=0, byte_end=1).to_json_bytes()
    assert payload == (
        b'{"artifact_sha256":"' + SHA.encode() + b'","byte_end":1,"byte_start":0}'
    )
    span = _span(StyleLabel.ITALIC, 0, 1)
    reason = StyleSpan.model_validate({**span.model_dump(), "semantic_reason": "café"})
    assert "café".encode() in reason.to_json_bytes()


@pytest.mark.parametrize("bad_hash", ["", "ab" * 31, "zz" * 32, "ab" * 33])
def test_source_slice_rejects_malformed_hashes(bad_hash: str) -> None:
    with pytest.raises(ValidationError, match="64-character hexadecimal"):
        SourceSlice(artifact_sha256=bad_hash, byte_start=0, byte_end=1)


@pytest.mark.parametrize(("start", "end"), [(2, 2), (5, 3), (-1, 4)])
def test_source_slice_rejects_empty_reversed_and_negative_ranges(
    start: int, end: int
) -> None:
    with pytest.raises(ValidationError, match="nonempty half-open byte range"):
        SourceSlice(artifact_sha256=SHA, byte_start=start, byte_end=end)


def test_models_are_strict_frozen_and_forbid_extra_fields() -> None:
    sl = SourceSlice(artifact_sha256=SHA, byte_start=0, byte_end=1)
    with pytest.raises(ValidationError):
        sl.byte_end = 2
    with pytest.raises(ValidationError, match="Extra inputs"):
        SourceSlice.model_validate(
            {"artifact_sha256": SHA, "byte_start": 0, "byte_end": 1, "extra": 1}
        )
    with pytest.raises(ValidationError):
        SourceSlice.model_validate_json(
            f'{{"artifact_sha256":"{SHA}","byte_start":"0","byte_end":1}}'
        )


@pytest.mark.parametrize(("start", "end"), [(3, 3), (4, 2), (-1, 2)])
def test_style_span_rejects_degenerate_ranges(start: int, end: int) -> None:
    with pytest.raises(ValidationError, match="nonempty half-open grapheme range"):
        _span(StyleLabel.BOLD, start, end)


def test_style_span_round_trips_with_source_slices() -> None:
    sl = SourceSlice(artifact_sha256=SHA, byte_start=4, byte_end=8)
    span = _span(StyleLabel.SMALL_CAPS, 1, 3, slices=(sl,))
    restored = StyleSpan.from_json_bytes(span.to_json_bytes())
    assert restored == span
    assert restored.source_slices == (sl,)


def test_typography_spans_freezes_a_list_into_a_tuple_and_round_trips() -> None:
    spans = TypographySpans(
        grapheme_count=4,
        spans=[_span(StyleLabel.ITALIC, 0, 2), _span(StyleLabel.BOLD, 1, 4)],
    )
    assert isinstance(spans.spans, tuple)
    assert TypographySpans.from_json_bytes(spans.to_json_bytes()) == spans


def test_typography_spans_rejects_a_span_past_the_grapheme_count() -> None:
    with pytest.raises(ValidationError, match="cannot exceed grapheme_count"):
        TypographySpans(grapheme_count=2, spans=[_span(StyleLabel.ITALIC, 0, 3)])


def test_typography_spans_rejects_negative_grapheme_count() -> None:
    with pytest.raises(ValidationError, match="grapheme_count must be nonnegative"):
        TypographySpans(grapheme_count=-1, spans=[])


def test_labels_at_reports_independent_overlapping_styles_with_half_open_ends() -> None:
    spans = TypographySpans(
        grapheme_count=5,
        spans=[_span(StyleLabel.ITALIC, 0, 3), _span(StyleLabel.BOLD, 2, 4)],
    )
    assert spans.labels_at(0) == {StyleLabel.ITALIC}
    assert spans.labels_at(2) == {StyleLabel.ITALIC, StyleLabel.BOLD}
    assert spans.labels_at(3) == {StyleLabel.BOLD}
    assert spans.labels_at(4) == set()


@pytest.mark.parametrize("index", [-1, 5])
def test_labels_at_rejects_indices_outside_the_sequence(index: int) -> None:
    spans = TypographySpans(grapheme_count=5, spans=[])
    with pytest.raises(IndexError, match="outside"):
        spans.labels_at(index)
