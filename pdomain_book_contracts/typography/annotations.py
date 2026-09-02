from __future__ import annotations

import datetime as dt
from typing import Annotated, Self

from pydantic import Field, field_validator, model_validator

from pdomain_book_tools.typography.labels import (
    KnowledgeState,
    LabelSource,
    StyleLabel,
)
from pdomain_book_tools.typography.spans import CanonicalModel, StyleSpan

_StrictIndex = Annotated[int, Field(strict=True, ge=0)]
_Probability = Annotated[float, Field(ge=0.0, le=1.0)]


class TypographyAnnotations(CanonicalModel):
    """Trusted word-level typography annotations and inference metadata."""

    grapheme_count: _StrictIndex = 0
    spans: list[StyleSpan] | tuple[StyleSpan, ...]
    whole_word_labels: list[StyleLabel] | tuple[StyleLabel, ...] | None = None
    source: LabelSource | None = None
    model_version: str | None = None
    confidence: _Probability | None = None
    calibration_version: str | None = None
    reviewer_id: str | None = None
    reviewed_at: dt.datetime | None = None
    warnings: list[str] | tuple[str, ...] = ()

    @field_validator("spans", mode="after")
    @classmethod
    def _freeze_spans(
        cls, spans: list[StyleSpan] | tuple[StyleSpan, ...]
    ) -> tuple[StyleSpan, ...]:
        return tuple(spans)

    @field_validator("warnings", mode="after")
    @classmethod
    def _freeze_warnings(cls, warnings: list[str] | tuple[str, ...]) -> tuple[str, ...]:
        return tuple(warnings)

    @model_validator(mode="after")
    def _derive_whole_word_labels(self) -> Self:
        if any(span.end > self.grapheme_count for span in self.spans):
            msg = "span end cannot exceed grapheme_count"
            raise ValueError(msg)
        derived = tuple(
            label for label in StyleLabel if self._has_complete_positive_coverage(label)
        )
        supplied = self.whole_word_labels
        if supplied is not None and tuple(supplied) != derived:
            msg = "whole_word_labels must equal labels with complete positive span coverage"
            raise ValueError(msg)
        object.__setattr__(self, "whole_word_labels", derived)
        return self

    def _has_complete_positive_coverage(self, label: StyleLabel) -> bool:
        if self.grapheme_count == 0:
            return False
        intervals = sorted(
            (
                (span.start, span.end)
                for span in self.spans
                if span.label is label and span.state is KnowledgeState.POSITIVE
            ),
            key=lambda interval: interval[0],
        )
        cursor = 0
        for start, end in intervals:
            if start > cursor:
                return False
            cursor = max(cursor, end)
        return cursor == self.grapheme_count
