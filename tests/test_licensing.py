from __future__ import annotations

import importlib.resources

import pytest

from pdomain_book_contracts.licensing import SPDX_VALID_IDS, is_valid_spdx_id


@pytest.mark.parametrize("value", ["MIT", "Apache-2.0", "GPL-3.0-only", "CC0-1.0"])
def test_common_identifiers_are_valid(value: str) -> None:
    assert value in SPDX_VALID_IDS
    assert is_valid_spdx_id(value)


@pytest.mark.parametrize(
    "value", ["apache-2.0", "mit", "Apache 2.0", " MIT", "MIT ", ""]
)
def test_matching_is_exact_and_case_sensitive(value: str) -> None:
    assert not is_valid_spdx_id(value)


@pytest.mark.parametrize("value", [None, 7, b"MIT", ["MIT"], ("MIT",)])
def test_non_strings_are_invalid_rather_than_raising(value: object) -> None:
    assert not is_valid_spdx_id(value)


def test_unknown_identifier_is_invalid() -> None:
    assert not is_valid_spdx_id("Not-A-Real-License-1.0")


def test_every_vendored_entry_is_loaded() -> None:
    raw = (
        importlib.resources.files("pdomain_book_contracts.data")
        .joinpath("spdx_licenses.json")
        .read_text(encoding="utf-8")
    )
    assert len(SPDX_VALID_IDS) == raw.count('"licenseId"')
    assert all(is_valid_spdx_id(i) for i in SPDX_VALID_IDS)
