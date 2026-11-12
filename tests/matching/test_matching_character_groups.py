from __future__ import annotations

import pytest

from pdomain_book_contracts.matching.character_groups import CharacterGroups


def _chars(*code_points: int) -> list[str]:
    return [chr(code_point) for code_point in code_points]


_HYPHEN, _EN_DASH, _EM_DASH, _FIGURE_DASH = _chars(0x2D, 0x2013, 0x2014, 0x2012)
_TWO_EM, _THREE_EM, _BAR, _NB_HYPHEN, _MINUS = _chars(
    0x2E3A, 0x2E3B, 0x2015, 0x2011, 0x2212
)
_LEFT_SINGLE, _RIGHT_SINGLE, _LEFT_DOUBLE, _RIGHT_DOUBLE = _chars(
    0x2018, 0x2019, 0x201C, 0x201D
)
_PRIME, _DOUBLE_PRIME = _chars(0x2032, 0x2033)


@pytest.mark.parametrize(
    "character",
    [
        _HYPHEN,
        _EN_DASH,
        _EM_DASH,
        _FIGURE_DASH,
        _TWO_EM,
        _THREE_EM,
        _BAR,
        _NB_HYPHEN,
        _MINUS,
    ],
)
def test_every_dash_variant_is_in_the_dash_group(character: str) -> None:
    assert character in CharacterGroups.DASHES


@pytest.mark.parametrize("character", ["a", "'", _PRIME, "", "--"])
def test_non_dash_characters_are_not_in_the_dash_group(character: str) -> None:
    assert character not in CharacterGroups.DASHES


def test_curly_and_straight_quotes_share_the_quote_groups() -> None:
    assert "'" in CharacterGroups.SINGLE_QUOTE
    assert _RIGHT_SINGLE in CharacterGroups.SINGLE_QUOTE
    assert '"' in CharacterGroups.DOUBLE_QUOTE
    assert _RIGHT_DOUBLE in CharacterGroups.DOUBLE_QUOTE
    assert _LEFT_DOUBLE not in CharacterGroups.SINGLE_QUOTE
    assert all(
        quote in CharacterGroups.QUOTES
        for quote in (
            "'",
            _LEFT_SINGLE,
            _RIGHT_SINGLE,
            '"',
            _LEFT_DOUBLE,
            _RIGHT_DOUBLE,
        )
    )


def test_primes_join_quotes_only_in_the_combined_group() -> None:
    assert _PRIME in CharacterGroups.PRIMES
    assert _DOUBLE_PRIME in CharacterGroups.PRIMES
    assert _PRIME not in CharacterGroups.QUOTES
    assert _PRIME in CharacterGroups.QUOTES_AND_PRIMES
    assert _LEFT_SINGLE in CharacterGroups.QUOTES_AND_PRIMES


def test_combined_groups_list_each_character_once_in_a_stable_order() -> None:
    dashes = CharacterGroups.DASHES.value
    assert len(dashes) == len(set(dashes))
    assert dashes[:2] == [_HYPHEN, _EN_DASH]
    combined = CharacterGroups.QUOTES_AND_PRIMES.value
    assert len(combined) == len(set(combined))
    assert set(combined) == set(CharacterGroups.QUOTES.value) | set(
        CharacterGroups.PRIMES.value
    )
