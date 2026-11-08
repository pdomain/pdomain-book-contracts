"""Textual layout evidence and reviewed structure contracts."""

from __future__ import annotations

import math
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_NonEmptyString = Annotated[str, Field(strict=True, min_length=1)]
_StrictIndex = Annotated[int, Field(strict=True)]
_FiniteFloat = Annotated[float, Field(strict=True)]
_LayoutHintKind = Literal["poetry", "blockquote", "table_candidate", "column_flow"]
_LayoutHintSource = Literal["f2", "gutenberg_html"]
_LayoutStructureKind = Literal["poetry", "blockquote", "table", "column_flow"]


class _LayoutModel(BaseModel):
    """Frozen layout wire model with explicit dictionary conversion."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible mapping without unknown optional fields."""
        return self.model_dump(mode="json", exclude_none=True, exclude_defaults=True)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        """Validate a record from its JSON-compatible mapping."""
        return cls.model_validate(data)


class LayoutTextLine(_LayoutModel):
    """One source-visible line with optional source-relative indentation."""

    text: str
    stanza_index: _StrictIndex | None = None
    indent_hint: str | None = None

    @model_validator(mode="after")
    def _validate_indices(self) -> Self:
        if self.stanza_index is not None and self.stanza_index < 0:
            msg = "stanza_index must be nonnegative"
            raise ValueError(msg)
        return self


class LayoutTextHint(_LayoutModel):
    """Source evidence for a candidate textual layout role."""

    kind: _LayoutHintKind
    source: _LayoutHintSource
    text: _NonEmptyString
    lines: tuple[LayoutTextLine, ...]
    source_ref: _NonEmptyString
    grapheme_range: tuple[_StrictIndex, _StrictIndex] | None = None
    source_byte_range: tuple[_StrictIndex, _StrictIndex] | None = None
    attributes: tuple[tuple[str, str], ...] = ()
    table_rows: tuple[tuple[str, ...], ...] = ()
    warnings: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _validate_ranges(self) -> Self:
        for range_name, value in (
            ("grapheme_range", self.grapheme_range),
            ("source_byte_range", self.source_byte_range),
        ):
            if value is not None and (value[0] < 0 or value[0] >= value[1]):
                msg = f"{range_name} must be a nonempty half-open range"
                raise ValueError(msg)
        return self


class LayoutStructureLine(_LayoutModel):
    """One reviewed text line bound to prepared-bundle word identities."""

    text: str
    word_ids: tuple[_NonEmptyString, ...] = ()
    word_signatures: tuple[_NonEmptyString, ...] = ()
    stanza_index: _StrictIndex | None = None
    indent_hint: str | None = None
    measured_indent: _FiniteFloat | None = None

    @model_validator(mode="after")
    def _validate_reviewed_line(self) -> Self:
        if self.text and not self.word_ids:
            msg = "nonempty reviewed line text requires prepared-bundle word_ids"
            raise ValueError(msg)
        if self.stanza_index is not None and self.stanza_index < 0:
            msg = "stanza_index must be nonnegative"
            raise ValueError(msg)
        _validate_word_snapshots(self.word_ids, self.word_signatures)
        _validate_finite_measurement(self.measured_indent, "measured_indent")
        return self


class LayoutTableCell(_LayoutModel):
    """One reviewed table cell bound to prepared-bundle word identities."""

    text: str
    word_ids: tuple[_NonEmptyString, ...] = ()
    word_signatures: tuple[_NonEmptyString, ...] = ()

    @model_validator(mode="after")
    def _validate_reviewed_cell(self) -> Self:
        if self.text and not self.word_ids:
            msg = "nonempty reviewed table cell text requires prepared-bundle word_ids"
            raise ValueError(msg)
        _validate_word_snapshots(self.word_ids, self.word_signatures)
        return self


class LayoutTableRow(_LayoutModel):
    """One reviewed table row."""

    cells: tuple[LayoutTableCell, ...]

    @field_validator("cells")
    @classmethod
    def _validate_cells(
        cls, value: tuple[LayoutTableCell, ...]
    ) -> tuple[LayoutTableCell, ...]:
        if not value:
            msg = "reviewed table row must contain at least one cell"
            raise ValueError(msg)
        return value


class LayoutStructure(_LayoutModel):
    """Reviewed layout structure for one confirmed region."""

    kind: _LayoutStructureKind
    lines: tuple[LayoutStructureLine, ...] = ()
    column_group_id: str | None = None
    column_index: _StrictIndex | None = None
    reading_order: _StrictIndex | None = None
    measured_indent: _FiniteFloat | None = None
    table_rows: tuple[LayoutTableRow, ...] = ()

    @model_validator(mode="after")
    def _validate_structure(self) -> Self:
        if not (self.lines or self.table_rows or self.column_group_id is not None):
            msg = "layout structure requires lines, table_rows, or column_group_id"
            raise ValueError(msg)
        for index_name, value in (
            ("column_index", self.column_index),
            ("reading_order", self.reading_order),
        ):
            if value is not None and value < 0:
                msg = f"{index_name} must be nonnegative"
                raise ValueError(msg)
        _validate_finite_measurement(self.measured_indent, "measured_indent")
        return self


def _validate_word_snapshots(
    word_ids: tuple[str, ...], word_signatures: tuple[str, ...]
) -> None:
    if word_signatures and len(word_ids) != len(word_signatures):
        msg = "word_signatures must have the same length as word_ids"
        raise ValueError(msg)


def _validate_finite_measurement(value: float | None, name: str) -> None:
    if value is not None and not math.isfinite(value):
        msg = f"{name} must be finite"
        raise ValueError(msg)


__all__ = [
    "LayoutStructure",
    "LayoutStructureLine",
    "LayoutTableCell",
    "LayoutTableRow",
    "LayoutTextHint",
    "LayoutTextLine",
]
