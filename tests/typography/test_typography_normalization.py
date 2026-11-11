from __future__ import annotations

import pytest
from pydantic import ValidationError

from pdomain_book_contracts.typography.labels import (
    ConfidenceTier,
    KnowledgeState,
    LabelSource,
    StyleLabel,
)
from pdomain_book_contracts.typography.normalization import (
    ComparisonOperation,
    ComparisonOperationKind,
    ComparisonView,
    build_comparison_view,
    small_caps_ranges_from_spans,
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


def _kinds(view: ComparisonView) -> list[ComparisonOperationKind]:
    return [operation.kind for operation in view.operations]


def test_plain_text_is_unchanged_and_maps_one_to_one() -> None:
    view = build_comparison_view("abc")
    assert view.text == "abc"
    assert view.source_grapheme_map == ((0,), (1,), (2,))
    assert view.operations == ()


def test_curly_quotes_and_dashes_are_folded_for_comparison_only() -> None:
    source = "\u201cit\u2019s\u201d \u2014 a\u2013b"
    view = build_comparison_view(source)
    assert view.text == '"it\'s" - a-b'
    assert view.source_text == source
    assert _kinds(view).count(ComparisonOperationKind.QUOTE_EQUIVALENCE) == 3
    assert _kinds(view).count(ComparisonOperationKind.DASH_EQUIVALENCE) == 2
    quote = view.operations[0]
    assert (quote.original_text, quote.transformed_text) == ("“", '"')
    assert quote.input_range == (0, 1)
    assert quote.output_range == (0, 1)


def test_soft_hyphen_is_dropped_and_later_graphemes_keep_source_indices() -> None:
    view = build_comparison_view("ab­cd")
    assert view.text == "abcd"
    assert view.source_grapheme_map == ((0,), (1,), (3,), (4,))
    removal = view.operations[0]
    assert removal.kind is ComparisonOperationKind.SOFT_HYPHEN_REMOVED
    assert removal.input_range == (2, 3)
    assert removal.output_range == (2, 2)


def test_decomposed_accents_are_canonicalised_to_one_grapheme() -> None:
    view = build_comparison_view("café")
    assert view.text == "café"
    assert view.source_grapheme_map[-1] == (3,)
    operation = view.operations[0]
    assert operation.kind is ComparisonOperationKind.UNICODE_CANONICAL
    assert operation.original_text == "é"
    assert operation.transformed_text == "é"


def test_casefold_all_folds_everything_and_records_each_change() -> None:
    view = build_comparison_view("AbC", casefold_all=True)
    assert view.text == "abc"
    assert _kinds(view) == [ComparisonOperationKind.SMALL_CAPS_CASE_FOLDED] * 2
    assert view.casefold_all is True


def test_small_caps_range_folds_only_the_selected_graphemes() -> None:
    view = build_comparison_view("ABCD", small_caps_ranges=((1, 3),))
    assert view.text == "AbcD"
    assert view.small_caps_ranges == ((1, 3),)


def test_casefold_that_expands_keeps_every_output_mapped_to_its_source() -> None:
    view = build_comparison_view("AßB", casefold_all=True)
    assert view.text == "assb"
    assert view.source_grapheme_map == ((0,), (1,), (1,), (2,))
    folded = view.operations[1]
    assert folded.original_text == "ß"
    assert folded.transformed_text == "ss"
    assert folded.output_range == (1, 3)


def test_letter_spaced_range_collapses_to_the_visible_letters() -> None:
    view = build_comparison_view("a b c d", letter_spaced_ranges=((2, 7),))
    assert view.text == "a bcd"
    assert view.source_grapheme_map == ((0,), (1,), (2,), (4,), (6,))
    removal = view.operations[-1]
    assert removal.kind is ComparisonOperationKind.LETTER_SPACE_REMOVED
    assert removal.input_range == (2, 7)
    assert removal.output_range == (2, 5)
    assert removal.original_text == "b c d"
    assert removal.transformed_text == "bcd"


@pytest.mark.parametrize(
    "ranges",
    [((0, 2),), ((0, 4),), ((1, 4),), ((0, 9),), ((-1, 3),), ((3, 3),)],
)
def test_letter_spaced_ranges_must_alternate_letters_and_spaces(
    ranges: tuple[tuple[int, int], ...],
) -> None:
    with pytest.raises(ValueError, match="letter"):
        build_comparison_view("a b c", letter_spaced_ranges=ranges)


def test_letter_spaced_range_with_a_space_in_a_letter_slot_is_rejected() -> None:
    with pytest.raises(ValueError, match="alternate visible graphemes"):
        build_comparison_view("a  b", letter_spaced_ranges=((0, 3),))


@pytest.mark.parametrize("ranges", [((2, 2),), ((-1, 1),), ((0, 4),)])
def test_small_caps_ranges_must_lie_inside_the_source(
    ranges: tuple[tuple[int, int], ...],
) -> None:
    with pytest.raises(ValueError, match="small_caps_ranges"):
        build_comparison_view("abc", small_caps_ranges=ranges)


def test_small_caps_ranges_come_only_from_positive_small_caps_spans() -> None:
    spans = (
        _span(StyleLabel.SMALL_CAPS, 0, 2),
        _span(StyleLabel.ITALIC, 1, 3),
        _span(StyleLabel.SMALL_CAPS, 3, 4, KnowledgeState.UNKNOWN),
        _span(StyleLabel.SMALL_CAPS, 5, 7),
    )
    assert small_caps_ranges_from_spans(spans, grapheme_count=8) == ((0, 2), (5, 7))


def test_small_caps_span_past_the_source_is_rejected() -> None:
    with pytest.raises(ValueError, match="cannot exceed comparison source"):
        small_caps_ranges_from_spans(
            (_span(StyleLabel.SMALL_CAPS, 0, 5),), grapheme_count=4
        )


def test_derived_small_caps_ranges_drive_the_comparison_fold() -> None:
    spans = (_span(StyleLabel.SMALL_CAPS, 0, 3),)
    ranges = small_caps_ranges_from_spans(spans, grapheme_count=6)
    view = build_comparison_view("THEEnd", small_caps_ranges=ranges)
    assert view.text == "theEnd"


def test_comparison_view_round_trips_through_canonical_json() -> None:
    original = build_comparison_view(
        "\u201cA b c\u201d\u00ad!", letter_spaced_ranges=((1, 6),), casefold_all=True
    )
    restored = ComparisonView.from_json_bytes(original.to_json_bytes())
    assert restored == original
    assert restored.text == original.text


def _op(
    input_range: tuple[int, int], output_range: tuple[int, int]
) -> dict[str, object]:
    return {
        "kind": "quote_equivalence",
        "input_range": input_range,
        "output_range": output_range,
        "original_text": "x",
        "transformed_text": "y",
    }


def test_operation_rejects_an_empty_input_range() -> None:
    with pytest.raises(ValidationError, match="input_range must be nonempty"):
        ComparisonOperation.model_validate(_op((2, 2), (0, 1)))


def test_operation_rejects_a_reversed_output_range_but_allows_an_empty_one() -> None:
    with pytest.raises(ValidationError, match="output_range must be ordered"):
        ComparisonOperation.model_validate(_op((0, 1), (3, 2)))
    assert ComparisonOperation.model_validate(_op((0, 1), (2, 2))).output_range == (
        2,
        2,
    )


def _view(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "source_text": "ab",
        "graphemes": ("a", "b"),
        "source_grapheme_map": ((0,), (1,)),
        "operations": (),
    }
    return {**base, **overrides}


def test_view_accepts_a_consistent_payload() -> None:
    assert ComparisonView.model_validate(_view()).text == "ab"


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"source_grapheme_map": ((0,),)}, "equal length"),
        ({"source_grapheme_map": ((0,), ())}, "must map to source graphemes"),
        ({"source_grapheme_map": ((0,), (2,))}, "exceeds source graphemes"),
        ({"source_grapheme_map": ((1,), (0,))}, "monotonic"),
        ({"source_grapheme_map": ((0,), (1, 0))}, "monotonic"),
    ],
)
def test_view_rejects_inconsistent_source_maps(
    overrides: dict[str, object], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        ComparisonView.model_validate(_view(**overrides))
