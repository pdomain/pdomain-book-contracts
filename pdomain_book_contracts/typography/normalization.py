from __future__ import annotations

import unicodedata
from enum import StrEnum
from typing import Annotated, Self

from pydantic import Field, model_validator

from pdomain_book_contracts.typography.labels import KnowledgeState, StyleLabel
from pdomain_book_contracts.typography.spans import (
    CanonicalModel,
    StyleSpan,
    split_graphemes,
)

_StrictIndex = Annotated[int, Field(strict=True, ge=0)]

_QUOTE_EQUIVALENTS = {
    "\u2018": "'",
    "\u2019": "'",
    "\u201a": "'",
    "\u201b": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u201e": '"',
    "\u201f": '"',
}
_DASH_EQUIVALENTS = {
    "\u2010": "-",
    "\u2011": "-",
    "\u2012": "-",
    "\u2013": "-",
    "\u2014": "-",
    "\u2015": "-",
}


class ComparisonOperationKind(StrEnum):
    """Comparison-only transformations allowed by the alignment contract."""

    UNICODE_CANONICAL = "unicode_canonical"
    QUOTE_EQUIVALENCE = "quote_equivalence"
    DASH_EQUIVALENCE = "dash_equivalence"
    SMALL_CAPS_CASE_FOLDED = "small_caps_case_folded"
    SOFT_HYPHEN_REMOVED = "soft_hyphen_removed"
    LETTER_SPACE_REMOVED = "letter_space_removed"


class ComparisonOperation(CanonicalModel):
    """One immutable source-to-comparison-view transformation."""

    kind: ComparisonOperationKind
    input_range: tuple[_StrictIndex, _StrictIndex]
    output_range: tuple[_StrictIndex, _StrictIndex]
    original_text: str
    transformed_text: str

    @model_validator(mode="after")
    def _validate_ranges(self) -> Self:
        input_start, input_end = self.input_range
        output_start, output_end = self.output_range
        if input_start >= input_end:
            msg = "normalization input_range must be nonempty"
            raise ValueError(msg)
        if output_start > output_end:
            msg = "normalization output_range must be ordered"
            raise ValueError(msg)
        return self


class ComparisonView(CanonicalModel):
    """A source-preserving normalized grapheme view for matching only."""

    source_text: str
    graphemes: tuple[str, ...]
    source_grapheme_map: tuple[tuple[_StrictIndex, ...], ...]
    operations: tuple[ComparisonOperation, ...]
    small_caps_ranges: tuple[tuple[_StrictIndex, _StrictIndex], ...] = ()
    casefold_all: bool = False

    @property
    def text(self) -> str:
        """Return the normalized comparison text."""
        return "".join(self.graphemes)

    @model_validator(mode="after")
    def _validate_map(self) -> Self:
        if len(self.graphemes) != len(self.source_grapheme_map):
            msg = "comparison graphemes and source_grapheme_map must have equal length"
            raise ValueError(msg)
        if any(not indices for indices in self.source_grapheme_map):
            msg = "every comparison grapheme must map to source graphemes"
            raise ValueError(msg)
        source_count = len(split_graphemes(self.source_text))
        if any(
            index >= source_count
            for indices in self.source_grapheme_map
            for index in indices
        ):
            msg = "comparison source_grapheme_map index exceeds source graphemes"
            raise ValueError(msg)
        previous_index = -1
        for indices in self.source_grapheme_map:
            if tuple(sorted(set(indices))) != indices or indices[0] < previous_index:
                msg = "comparison source_grapheme_map must be monotonic"
                raise ValueError(msg)
            previous_index = indices[-1]
        return self


def _validated_letter_space_indices(
    source_graphemes: tuple[str, ...], ranges: tuple[tuple[int, int], ...]
) -> frozenset[int]:
    removed: set[int] = set()
    for start, end in ranges:
        if start < 0 or start >= end or end > len(source_graphemes):
            msg = "letter_spaced_ranges must be nonempty source grapheme ranges"
            raise ValueError(msg)
        region = source_graphemes[start:end]
        if len(region) < 3 or len(region) % 2 == 0:
            msg = "letter-spaced source ranges must alternate visible graphemes and spaces"
            raise ValueError(msg)
        if any(
            (position % 2 == 0 and grapheme == " ")
            or (position % 2 == 1 and grapheme != " ")
            for position, grapheme in enumerate(region)
        ):
            msg = "letter-spaced source ranges must alternate visible graphemes and spaces"
            raise ValueError(msg)
        removed.update(range(start + 1, end, 2))
    return frozenset(removed)


def _validated_small_caps_indices(
    source_graphemes: tuple[str, ...], ranges: tuple[tuple[int, int], ...]
) -> frozenset[int]:
    indices: set[int] = set()
    for start, end in ranges:
        if start < 0 or start >= end or end > len(source_graphemes):
            msg = "small_caps_ranges must be nonempty source grapheme ranges"
            raise ValueError(msg)
        indices.update(range(start, end))
    return frozenset(indices)


def small_caps_ranges_from_spans(
    spans: tuple[StyleSpan, ...], *, grapheme_count: int
) -> tuple[tuple[int, int], ...]:
    """Derive comparison-only case-fold ranges from positive small-cap spans."""
    ranges: list[tuple[int, int]] = []
    for span in spans:
        if span.label is not StyleLabel.SMALL_CAPS:
            continue
        if span.state is not KnowledgeState.POSITIVE:
            continue
        if span.end > grapheme_count:
            msg = "small-cap span cannot exceed comparison source grapheme count"
            raise ValueError(msg)
        ranges.append((span.start, span.end))
    return tuple(ranges)


def build_comparison_view(
    source_text: str,
    *,
    small_caps_ranges: tuple[tuple[int, int], ...] = (),
    casefold_all: bool = False,
    letter_spaced_ranges: tuple[tuple[int, int], ...] = (),
) -> ComparisonView:
    """Build an immutable comparison view without changing canonical source text."""
    source_graphemes = split_graphemes(source_text)
    letter_space_indices = _validated_letter_space_indices(
        source_graphemes, letter_spaced_ranges
    )
    small_caps_indices = _validated_small_caps_indices(
        source_graphemes, small_caps_ranges
    )
    graphemes: list[str] = []
    source_map: list[tuple[int, ...]] = []
    operations: list[ComparisonOperation] = []

    for index, source_grapheme in enumerate(source_graphemes):
        output_start = len(graphemes)
        if source_grapheme == "\u00ad":
            operations.append(
                ComparisonOperation(
                    kind=ComparisonOperationKind.SOFT_HYPHEN_REMOVED,
                    input_range=(index, index + 1),
                    output_range=(output_start, output_start),
                    original_text=source_grapheme,
                    transformed_text="",
                )
            )
            continue
        if index in letter_space_indices:
            continue

        transformed = unicodedata.normalize("NFC", source_grapheme)
        transformed_graphemes = split_graphemes(transformed)
        output_end = output_start + len(transformed_graphemes)
        if transformed != source_grapheme:
            operations.append(
                ComparisonOperation(
                    kind=ComparisonOperationKind.UNICODE_CANONICAL,
                    input_range=(index, index + 1),
                    output_range=(output_start, output_end),
                    original_text=source_grapheme,
                    transformed_text=transformed,
                )
            )
        quote = _QUOTE_EQUIVALENTS.get(transformed)
        if quote is not None:
            operations.append(
                ComparisonOperation(
                    kind=ComparisonOperationKind.QUOTE_EQUIVALENCE,
                    input_range=(index, index + 1),
                    output_range=(output_start, output_end),
                    original_text=transformed,
                    transformed_text=quote,
                )
            )
            transformed = quote
        dash = _DASH_EQUIVALENTS.get(transformed)
        if dash is not None:
            operations.append(
                ComparisonOperation(
                    kind=ComparisonOperationKind.DASH_EQUIVALENCE,
                    input_range=(index, index + 1),
                    output_range=(output_start, output_end),
                    original_text=transformed,
                    transformed_text=dash,
                )
            )
            transformed = dash
        if casefold_all or index in small_caps_indices:
            folded = transformed.casefold()
            if folded != transformed:
                transformed_graphemes = split_graphemes(folded)
                output_end = output_start + len(transformed_graphemes)
                operations.append(
                    ComparisonOperation(
                        kind=ComparisonOperationKind.SMALL_CAPS_CASE_FOLDED,
                        input_range=(index, index + 1),
                        output_range=(output_start, output_end),
                        original_text=transformed,
                        transformed_text=folded,
                    )
                )
                transformed = folded
        transformed_graphemes = split_graphemes(transformed)
        for transformed_grapheme in transformed_graphemes:
            graphemes.append(transformed_grapheme)
            source_map.append((index,))

    for start, end in letter_spaced_ranges:
        output_indices = [
            output_index
            for output_index, indices in enumerate(source_map)
            if start <= indices[0] < end
        ]
        operations.append(
            ComparisonOperation(
                kind=ComparisonOperationKind.LETTER_SPACE_REMOVED,
                input_range=(start, end),
                output_range=(min(output_indices), max(output_indices) + 1),
                original_text="".join(source_graphemes[start:end]),
                transformed_text="".join(graphemes[index] for index in output_indices),
            )
        )
    return ComparisonView(
        source_text=source_text,
        graphemes=tuple(graphemes),
        source_grapheme_map=tuple(source_map),
        operations=tuple(operations),
        small_caps_ranges=small_caps_ranges,
        casefold_all=casefold_all,
    )
