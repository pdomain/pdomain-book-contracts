from __future__ import annotations

import pytest

from pdomain_book_contracts.sources.pgdp.rounds import PGDPResults


@pytest.mark.parametrize(
    ("markup", "expected"),
    [
        ("['N]", "\N{LATIN CAPITAL LETTER N WITH ACUTE}"),
        ("['n]", "\N{LATIN SMALL LETTER N WITH ACUTE}"),
        ("[`N]", "\N{LATIN CAPITAL LETTER N WITH GRAVE}"),
        ("[`n]", "\N{LATIN SMALL LETTER N WITH GRAVE}"),
    ],
)
def test_n_markup_uses_the_accent_it_names(markup: str, expected: str) -> None:
    assert PGDPResults.fix_pgdp_diacritics(markup) == expected
