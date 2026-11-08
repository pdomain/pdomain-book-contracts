from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from pdomain_book_contracts.layout.text_hints import (
    LayoutStructure,
    LayoutStructureLine,
    LayoutTableCell,
    LayoutTableRow,
    LayoutTextHint,
    LayoutTextLine,
)


def test_text_hint_round_trip_omits_unknown_ranges() -> None:
    hint = LayoutTextHint(
        kind="poetry",
        source="f2",
        text="First\\nSecond",
        lines=(
            LayoutTextLine(text="First", stanza_index=0, indent_hint="  "),
            LayoutTextLine(text="Second", stanza_index=0),
        ),
        source_ref="rounds/F2.json#page-1",
        grapheme_range=(4, 16),
        attributes=(("class", "poetry"),),
    )

    wire = hint.to_dict()

    assert wire == {
        "kind": "poetry",
        "source": "f2",
        "text": "First\\nSecond",
        "lines": [
            {"text": "First", "stanza_index": 0, "indent_hint": "  "},
            {"text": "Second", "stanza_index": 0},
        ],
        "source_ref": "rounds/F2.json#page-1",
        "grapheme_range": [4, 16],
        "attributes": [["class", "poetry"]],
    }
    assert LayoutTextHint.from_dict(wire) == hint


@pytest.mark.parametrize("field", ["grapheme_range", "source_byte_range"])
def test_text_hint_rejects_invalid_half_open_range(field: str) -> None:
    kwargs: dict[str, object] = {
        "kind": "blockquote",
        "source": "gutenberg_html",
        "text": "Quoted",
        "lines": (LayoutTextLine(text="Quoted"),),
        "source_ref": "source.html",
        field: (3, 3),
    }

    with pytest.raises(ValidationError, match="half-open"):
        LayoutTextHint.model_validate(kwargs)


def test_text_hint_from_dict_rejects_coerced_index() -> None:
    with pytest.raises(ValidationError, match="valid integer"):
        LayoutTextHint.from_dict(
            {
                "kind": "poetry",
                "source": "f2",
                "text": "Line",
                "lines": [{"text": "Line"}],
                "source_ref": "rounds/F2.json#page-1",
                "grapheme_range": ["0", 4],
            }
        )


def test_reviewed_structure_round_trip_preserves_word_ids() -> None:
    structure = LayoutStructure(
        kind="poetry",
        lines=(
            LayoutStructureLine(
                text="First line",
                word_ids=("word-1", "word-2"),
                word_signatures=("word-1@1,2,3,4", "word-2@5,6,7,8"),
                stanza_index=0,
                indent_hint="2em",
                measured_indent=12.5,
            ),
        ),
        column_group_id="column-0",
        column_index=0,
        reading_order=0,
        table_rows=(
            LayoutTableRow(cells=(LayoutTableCell(text="Cell", word_ids=("word-3",)),)),
        ),
    )

    wire = structure.to_dict()

    assert structure.lines[0].word_ids == ("word-1", "word-2")
    assert structure.lines[0].word_signatures == (
        "word-1@1,2,3,4",
        "word-2@5,6,7,8",
    )
    assert LayoutStructure.from_dict(wire) == structure


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("column_index", -1, "nonnegative"),
        ("measured_indent", math.inf, "finite"),
    ],
)
def test_reviewed_structure_rejects_invalid_indices_and_measurements(
    field: str, value: float, message: str
) -> None:
    kwargs: dict[str, object] = {
        "kind": "column_flow",
        "column_group_id": "column-0",
        field: value,
    }

    with pytest.raises(ValidationError, match=message):
        LayoutStructure.model_validate(kwargs)


def test_nonempty_reviewed_line_requires_prepared_word_ids() -> None:
    with pytest.raises(ValidationError, match="word_ids"):
        LayoutStructureLine(text="Unbound")


def test_word_signatures_are_snapshots_not_extra_join_keys() -> None:
    with pytest.raises(ValidationError, match="same length"):
        LayoutStructureLine(
            text="Bound",
            word_ids=("word-1",),
            word_signatures=("word-1@0,0,1,1", "word-2@2,0,3,1"),
        )
