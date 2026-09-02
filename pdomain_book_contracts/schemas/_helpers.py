"""Shared pydantic-core schema primitives for pdomain-book-tools models.

Internal module — not part of the public API. Other modules import
schema fragments from here to keep per-class ``__get_pydantic_core_schema__``
hooks readable and consistent.

Usage:
    from pdomain_book_tools.schemas._helpers import (
        NUMBER_SCHEMA,
        NULLABLE_STR_SCHEMA,
        STR_LIST_SCHEMA,
        STR_STR_DICT_SCHEMA,
    )
"""

from __future__ import annotations

from pydantic_core import core_schema

# Int-or-float (coordinates, confidences, etc.).
NUMBER_SCHEMA = core_schema.union_schema(
    [
        core_schema.int_schema(),
        core_schema.float_schema(),
    ]
)

# ``str | None`` — used for optional notes / ground-truth fields.
NULLABLE_STR_SCHEMA = core_schema.nullable_schema(core_schema.str_schema())

# ``list[str]`` — used for labels / components.
STR_LIST_SCHEMA = core_schema.list_schema(core_schema.str_schema())

# ``dict[str, str]`` — used for text_style_label_scopes.
STR_STR_DICT_SCHEMA = core_schema.dict_schema(
    keys_schema=core_schema.str_schema(),
    values_schema=core_schema.str_schema(),
)

# ``dict[str, Any]`` — used for free-form metadata bags
# (ground_truth_match_keys, additional_block_attributes).
STR_ANY_DICT_SCHEMA = core_schema.dict_schema(
    keys_schema=core_schema.str_schema(),
)

# ``dict[str, float | str] | None`` — baseline (m, b, source).
NULLABLE_BASELINE_SCHEMA = core_schema.nullable_schema(
    core_schema.dict_schema(
        keys_schema=core_schema.str_schema(),
        values_schema=core_schema.union_schema(
            [
                core_schema.float_schema(),
                core_schema.str_schema(),
            ]
        ),
    )
)

# ``list[tuple[int, str]]`` — used for ``Block.unmatched_ground_truth_words``.
# Runtime type is ``list[tuple[int, str]]``; JSON serialises tuples as arrays,
# so the wire format is ``[[int, str], ...]``.  The schema accepts both the
# Python tuple and the JSON list form via pydantic-core's tuple_schema.
INT_STR_PAIR_LIST_SCHEMA = core_schema.list_schema(
    core_schema.union_schema(
        [
            core_schema.tuple_schema(
                [core_schema.int_schema(), core_schema.str_schema()]
            ),
            core_schema.list_schema(
                core_schema.union_schema(
                    [core_schema.int_schema(), core_schema.str_schema()]
                ),
                min_length=2,
                max_length=2,
            ),
        ]
    )
)

# ``dict[str, Any] | None`` — used for Page provenance fields.
NULLABLE_STR_ANY_DICT_SCHEMA = core_schema.nullable_schema(
    core_schema.dict_schema(
        keys_schema=core_schema.str_schema(),
    )
)
