from __future__ import annotations

import pytest

from pdomain_book_contracts.text.text_normalize import (
    apply_text_normalizations,
    normalize_curly_quotes,
    normalize_em_dash,
)


def test_curly_quotes_become_straight_quotes() -> None:
    text = "\N{LEFT SINGLE QUOTATION MARK}a\N{RIGHT SINGLE QUOTATION MARK} \N{SINGLE LOW-9 QUOTATION MARK}b\N{SINGLE HIGH-REVERSED-9 QUOTATION MARK} \N{LEFT DOUBLE QUOTATION MARK}c\N{RIGHT DOUBLE QUOTATION MARK} \N{DOUBLE LOW-9 QUOTATION MARK}d\N{DOUBLE HIGH-REVERSED-9 QUOTATION MARK}"
    assert normalize_curly_quotes(text) == "'a' 'b' \"c\" \"d\""


def test_curly_quotes_leave_other_text_alone() -> None:
    text = "plain \N{EM DASH} text \N{LATIN SMALL LETTER E WITH ACUTE}"
    assert normalize_curly_quotes(text) == text


def test_em_dash_becomes_double_hyphen_only_for_em_dash() -> None:
    assert normalize_em_dash("a\N{EM DASH}b\N{EN DASH}c") == "a--b\N{EN DASH}c"


@pytest.mark.parametrize("text", [None, ""])
def test_empty_or_missing_text_returns_empty_string(text: str | None) -> None:
    result = apply_text_normalizations(
        text, straight_quotes=True, em_dash_to_double_hyphen=True
    )
    assert result == ""


@pytest.mark.parametrize(
    ("straight", "dash", "expected"),
    [
        (
            False,
            False,
            "\N{LEFT DOUBLE QUOTATION MARK}x\N{RIGHT DOUBLE QUOTATION MARK}\N{EM DASH}y",
        ),
        (True, False, '"x"\N{EM DASH}y'),
        (
            False,
            True,
            "\N{LEFT DOUBLE QUOTATION MARK}x\N{RIGHT DOUBLE QUOTATION MARK}--y",
        ),
        (True, True, '"x"--y'),
    ],
)
def test_each_option_is_applied_independently(
    straight: bool, dash: bool, expected: str
) -> None:
    result = apply_text_normalizations(
        "\N{LEFT DOUBLE QUOTATION MARK}x\N{RIGHT DOUBLE QUOTATION MARK}\N{EM DASH}y",
        straight_quotes=straight,
        em_dash_to_double_hyphen=dash,
    )
    assert result == expected
