"""Page kinds: what a page is.

Distinct from two vocabularies that already ship and are not merged with this
one. ``PageClass`` in pdomain-pgdp-measure records which fitted template a
page's text block matches, and is a measured signal that feeds a page kind
proposal. ``PageType`` in pdomain-prep-for-pgdp records what the packager does
with a leaf, and is derived from page kind plus policy.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final


class PageKind(StrEnum):
    """What a page is."""

    BODY = "body"
    CHAPTER_OPENING = "chapter opening"
    TITLE_PAGE = "title page"
    HALF_TITLE = "half title"
    CONTENTS = "contents"
    INDEX = "index"
    DEDICATION = "dedication"
    PREFACE = "preface"
    ERRATA = "errata"
    PLATE = "plate"
    BLANK = "blank"
    ADVERTISEMENT = "advertisement"
    COLOPHON = "colophon"
    UNKNOWN = "unknown"


ALLOWED_PAGE_KINDS: Final[frozenset[str]] = frozenset(
    member.value for member in PageKind
)


def _normalize_token(label: str) -> str:
    return " ".join(label.strip().lower().replace("_", " ").replace("-", " ").split())


def normalize_page_kind(label: str) -> str:
    """Normalise one page kind to a canonical allowed value."""
    normalized = _normalize_token(label)
    if normalized in ALLOWED_PAGE_KINDS:
        return normalized

    compact = normalized.replace(" ", "")
    for allowed in ALLOWED_PAGE_KINDS:
        if compact == allowed.replace(" ", ""):
            return allowed

    allowed_list = ", ".join(sorted(ALLOWED_PAGE_KINDS))
    raise ValueError(f"Invalid page kind '{label}'. Allowed kinds: {allowed_list}")
