from __future__ import annotations

import json
import string
from typing import Annotated, Self

import regex
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from pdomain_book_contracts.typography.labels import (
    ConfidenceTier,
    KnowledgeState,
    LabelSource,
    StyleLabel,
)

GRAPHEME_SEGMENTATION_VERSION = f"regex-{regex.__version__}-unicode-extended-\\X"
_StrictIndex = Annotated[int, Field(strict=True)]


def split_graphemes(text: str) -> tuple[str, ...]:
    """Split text with the contract's versioned Unicode grapheme implementation."""
    return tuple(regex.findall(r"\X", text))


class CanonicalModel(BaseModel):
    """Strict immutable model with a stable compact JSON representation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    def to_json_bytes(self) -> bytes:
        """Serialize to the canonical compact UTF-8 JSON form."""
        data = self.model_dump(mode="json")
        return json.dumps(
            data,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()

    @classmethod
    def from_json_bytes(cls, payload: bytes) -> Self:
        """Validate a canonical model from UTF-8 JSON bytes."""
        return cls.model_validate_json(payload)


class SourceSlice(CanonicalModel):
    """A half-open byte range in a source artifact."""

    artifact_sha256: str
    byte_start: _StrictIndex
    byte_end: _StrictIndex

    @field_validator("artifact_sha256")
    @classmethod
    def _validate_artifact_hash(cls, value: str) -> str:
        if len(value) != 64 or any(char not in string.hexdigits for char in value):
            msg = "artifact_sha256 must be a 64-character hexadecimal SHA-256"
            raise ValueError(msg)
        return value.lower()

    @model_validator(mode="after")
    def _validate_range(self) -> Self:
        if self.byte_start < 0 or self.byte_start >= self.byte_end:
            msg = "source slice must be a nonempty half-open byte range"
            raise ValueError(msg)
        return self


class StyleSpan(CanonicalModel):
    """One independent style over a half-open grapheme range."""

    label: StyleLabel
    start: _StrictIndex
    end: _StrictIndex
    state: KnowledgeState
    label_source: LabelSource
    confidence_tier: ConfidenceTier
    source_slices: tuple[SourceSlice, ...]
    rule_ref: str | None
    semantic_reason: str | None
    warnings: tuple[str, ...]

    @model_validator(mode="after")
    def _validate_range(self) -> Self:
        if self.start < 0 or self.start >= self.end:
            msg = "style span must be a nonempty half-open grapheme range"
            raise ValueError(msg)
        return self


class TypographySpans(CanonicalModel):
    """Independent style spans over a known grapheme sequence length."""

    grapheme_count: _StrictIndex
    spans: list[StyleSpan] | tuple[StyleSpan, ...]

    @field_validator("spans", mode="after")
    @classmethod
    def _freeze_spans(
        cls, spans: list[StyleSpan] | tuple[StyleSpan, ...]
    ) -> tuple[StyleSpan, ...]:
        return tuple(spans)

    @model_validator(mode="after")
    def _validate_ranges(self) -> Self:
        if self.grapheme_count < 0:
            msg = "grapheme_count must be nonnegative"
            raise ValueError(msg)
        if any(span.end > self.grapheme_count for span in self.spans):
            msg = "style span end cannot exceed grapheme_count"
            raise ValueError(msg)
        return self

    def labels_at(self, index: int) -> set[StyleLabel]:
        """Return every independent style active at one grapheme index."""
        if not 0 <= index < self.grapheme_count:
            msg = f"grapheme index {index} is outside [0, {self.grapheme_count})"
            raise IndexError(msg)
        return {span.label for span in self.spans if span.start <= index < span.end}
