from __future__ import annotations

import datetime as dt

import pytest
from pydantic import ValidationError

from pdomain_book_contracts.typography.annotations import TypographyAnnotations
from pdomain_book_contracts.typography.labels import (
    ConfidenceTier,
    KnowledgeState,
    LabelSource,
    StyleLabel,
)
from pdomain_book_contracts.typography.spans import StyleSpan


def _span(
    label: StyleLabel,
    start: int,
    end: int,
    state: KnowledgeState = KnowledgeState.POSITIVE,
) -> StyleSpan:
    return StyleSpan(
        label=label,
        start=start,
        end=end,
        state=state,
        label_source=LabelSource.F2,
        confidence_tier=ConfidenceTier.GOLD,
        source_slices=(),
        rule_ref=None,
        semantic_reason=None,
        warnings=(),
    )


def test_whole_word_labels_are_derived_in_taxonomy_order() -> None:
    annotations = TypographyAnnotations(
        grapheme_count=4,
        spans=[_span(StyleLabel.BOLD, 0, 4), _span(StyleLabel.ITALIC, 0, 4)],
    )
    assert annotations.whole_word_labels == (StyleLabel.ITALIC, StyleLabel.BOLD)


def test_abutting_positive_spans_of_one_label_cover_the_whole_word() -> None:
    annotations = TypographyAnnotations(
        grapheme_count=5,
        spans=[_span(StyleLabel.ITALIC, 3, 5), _span(StyleLabel.ITALIC, 0, 3)],
    )
    assert annotations.whole_word_labels == (StyleLabel.ITALIC,)


def test_overlapping_spans_still_cover_the_whole_word() -> None:
    annotations = TypographyAnnotations(
        grapheme_count=5,
        spans=[_span(StyleLabel.BOLD, 0, 4), _span(StyleLabel.BOLD, 2, 5)],
    )
    assert annotations.whole_word_labels == (StyleLabel.BOLD,)


def test_a_gap_between_spans_is_not_whole_word_coverage() -> None:
    annotations = TypographyAnnotations(
        grapheme_count=5,
        spans=[_span(StyleLabel.ITALIC, 0, 2), _span(StyleLabel.ITALIC, 3, 5)],
    )
    assert annotations.whole_word_labels == ()


def test_a_short_cover_that_stops_before_the_end_is_not_whole_word() -> None:
    annotations = TypographyAnnotations(
        grapheme_count=5, spans=[_span(StyleLabel.ITALIC, 0, 4)]
    )
    assert annotations.whole_word_labels == ()


def test_only_positive_spans_count_toward_whole_word_coverage() -> None:
    annotations = TypographyAnnotations(
        grapheme_count=3,
        spans=[_span(StyleLabel.ITALIC, 0, 3, KnowledgeState.UNKNOWN)],
    )
    assert annotations.whole_word_labels == ()


def test_an_empty_word_has_no_whole_word_labels() -> None:
    assert TypographyAnnotations(spans=[]).whole_word_labels == ()


def test_spans_past_the_grapheme_count_are_rejected() -> None:
    with pytest.raises(ValidationError, match="span end cannot exceed"):
        TypographyAnnotations(grapheme_count=2, spans=[_span(StyleLabel.BOLD, 0, 3)])


def test_supplied_whole_word_labels_must_match_the_derived_ones() -> None:
    spans = [_span(StyleLabel.ITALIC, 0, 2)]
    with pytest.raises(ValidationError, match="complete positive span coverage"):
        TypographyAnnotations(
            grapheme_count=2, spans=spans, whole_word_labels=[StyleLabel.BOLD]
        )
    accepted = TypographyAnnotations(
        grapheme_count=2, spans=spans, whole_word_labels=[StyleLabel.ITALIC]
    )
    assert accepted.whole_word_labels == (StyleLabel.ITALIC,)


def test_lists_are_frozen_into_tuples() -> None:
    annotations = TypographyAnnotations(
        grapheme_count=1, spans=[_span(StyleLabel.BOLD, 0, 1)], warnings=["w"]
    )
    assert isinstance(annotations.spans, tuple)
    assert annotations.warnings == ("w",)


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_confidence_must_be_a_probability(confidence: float) -> None:
    with pytest.raises(ValidationError):
        TypographyAnnotations(spans=[], confidence=confidence)


def test_full_annotations_round_trip_through_canonical_json() -> None:
    original = TypographyAnnotations(
        grapheme_count=3,
        spans=[_span(StyleLabel.ITALIC, 0, 3), _span(StyleLabel.BOLD, 1, 2)],
        source=LabelSource.MODEL,
        model_version="m1",
        confidence=0.75,
        calibration_version="c1",
        reviewer_id="rev",
        reviewed_at=dt.datetime(2026, 1, 2, 3, 4, 5, tzinfo=dt.UTC),
        warnings=["low contrast"],
    )
    restored = TypographyAnnotations.from_json_bytes(original.to_json_bytes())
    assert restored == original
    assert restored.whole_word_labels == (StyleLabel.ITALIC,)
