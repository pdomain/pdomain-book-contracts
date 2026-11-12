from __future__ import annotations

import pytest

from pdomain_book_contracts.annotation.roles import (
    ALLOWED_REGION_ROLES,
    normalize_region_role,
)


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("pageheader", "page header"),
        ("PageNumber", "page number"),
        ("printersmark", "printers mark"),
        ("decorated_initial", "decorated initial"),
        ("  Page-Footer ", "page footer"),
    ],
)
def test_compact_and_variant_spellings_fold_to_the_canonical_role(
    label: str, expected: str
) -> None:
    assert normalize_region_role(label) == expected


def test_every_allowed_role_is_a_fixed_point() -> None:
    for role in ALLOWED_REGION_ROLES:
        assert normalize_region_role(role) == role
        assert normalize_region_role(role.replace(" ", "")) == role


def test_unknown_role_lists_the_allowed_ones() -> None:
    with pytest.raises(ValueError, match="Invalid region role 'nonsense'") as excinfo:
        normalize_region_role("nonsense")
    assert "page header" in str(excinfo.value)
