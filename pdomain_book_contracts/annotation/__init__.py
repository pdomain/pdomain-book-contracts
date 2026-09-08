"""Vocabularies describing what a human or a model asserted about a page.

This subpackage owns the words. It knows nothing about geometry, imaging, or the
page model, so every repository can depend on it without pulling either in.
"""

from __future__ import annotations

from pdomain_book_contracts.annotation.page_kind import (
    ALLOWED_PAGE_KINDS,
    PageKind,
    normalize_page_kind,
)
from pdomain_book_contracts.annotation.provenance import (
    ConfidenceTier,
    KnowledgeState,
    LabelSource,
)
from pdomain_book_contracts.annotation.roles import (
    ALLOWED_REGION_ROLES,
    REGION_ROLE_ALIASES,
    RegionRole,
    normalize_region_role,
)

__all__ = [
    "ALLOWED_PAGE_KINDS",
    "ALLOWED_REGION_ROLES",
    "REGION_ROLE_ALIASES",
    "ConfidenceTier",
    "KnowledgeState",
    "LabelSource",
    "PageKind",
    "RegionRole",
    "normalize_page_kind",
    "normalize_region_role",
]
