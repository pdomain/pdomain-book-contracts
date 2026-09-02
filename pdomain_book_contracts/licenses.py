"""Shared SPDX license identifier allowlist.

``pdomain_book_tools`` is the foundation library every ``pdomain-*`` repo depends on,
so it is the cheapest single source of truth for license-identifier
validation. Without a shared allowlist each downstream tool hand-rolls its
own subset and they drift — one accepts ``Apache-2.0``, another typos it,
and nothing catches the mismatch.

This module exposes a data-driven allowlist of SPDX license identifiers:

* :data:`SPDX_VALID_IDS` -- a :class:`frozenset` of every valid SPDX
  ``licenseId`` string.
* :func:`is_valid_spdx_id` -- a small validation helper.

The data is vendored as ``pdomain_book_tools/data/spdx_licenses.json`` (sourced
from the SPDX ``license-list-data`` project) rather than hand-curated, and
rather than pulling in a third-party package -- a runtime dependency here
would ripple into every consumer's install closure.

The API is intentionally license-domain-generic (no consumer-specific
naming). Expected consumers include synthetic-data font licensing,
dataset/model-card metadata, and public-domain rights markers on
submission packages.

SPDX identifiers are case-sensitive: ``Apache-2.0`` is valid, ``apache-2.0``
is not. :func:`is_valid_spdx_id` matches exactly.
"""

from __future__ import annotations

import importlib.resources
import json
from typing import TypedDict, cast

__all__ = ["SPDX_VALID_IDS", "is_valid_spdx_id"]


class _SpdxEntry(TypedDict):
    licenseId: str


class _SpdxData(TypedDict):
    licenses: list[_SpdxEntry]


def _load_spdx_ids() -> frozenset[str]:
    """Load the vendored SPDX license list into a frozenset of identifiers."""
    resource = importlib.resources.files("pdomain_book_tools.data").joinpath(
        "spdx_licenses.json"
    )
    data: _SpdxData = cast(
        "_SpdxData", json.loads(resource.read_text(encoding="utf-8"))
    )
    return frozenset(entry["licenseId"] for entry in data["licenses"])


#: Every valid SPDX license identifier, as exact case-sensitive strings.
SPDX_VALID_IDS: frozenset[str] = _load_spdx_ids()


def is_valid_spdx_id(value: object) -> bool:
    """Return ``True`` iff *value* is a valid SPDX license identifier.

    Matching is exact and case-sensitive against the canonical SPDX
    ``licenseId`` strings. Non-string input (e.g. ``None``) returns
    ``False`` rather than raising, so defensive callers can validate
    untrusted input directly.
    """
    if not isinstance(value, str):
        return False
    return value in SPDX_VALID_IDS
