"""Region roles: what a block of a page means.

Structure lives on the block category. Meaning lives here. Sub-word features
live on word components. The rule governing this list is additive only: no
shipped role string is ever renamed, because several call sites match them
literally.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final


class RegionRole(StrEnum):
    """The meaning a page region carries."""

    # The twenty that ship on Block today, unchanged.
    PARAGRAPH = "paragraph"
    SIDENOTE = "sidenote"
    PAGE_HEADER = "page header"
    PAGE_FOOTER = "page footer"
    PAGE_NUMBER = "page number"
    PRINTERS_MARK = "printers mark"
    BLOCKQUOTE = "blockquote"
    POETRY = "poetry"
    RECOVERED = "recovered"
    ILLUSTRATION = "illustration"
    DECORATION = "decoration"
    CAPTION = "caption"
    FIGURE = "figure"
    TABLE = "table"
    FOOTNOTE = "footnote"
    TITLE = "title"  # pyright: ignore[reportAssignmentType]
    SECTION = "section"
    LIST = "list"
    FORMULA = "formula"
    ARTEFACT = "artefact"

    # The fourteen additions.
    SIGNATURE_MARK = "signature mark"
    CATCHWORD = "catchword"
    PRESS_FIGURE = "press figure"
    RULE = "rule"
    BRACE = "brace"
    BRACKET = "bracket"
    GROUP_LABEL = "group label"
    PLATE = "plate"
    SPEAKER_LABEL = "speaker label"
    STAGE_DIRECTION = "stage direction"
    INTERLINEAR_GLOSS = "interlinear gloss"
    ABANDONED = "abandoned"
    DECORATED_INITIAL = "decorated initial"
    UNKNOWN = "unknown"


ALLOWED_REGION_ROLES: Final[frozenset[str]] = frozenset(
    member.value for member in RegionRole
)

REGION_ROLE_ALIASES: Final[dict[str, str]] = {
    "frontispiece": "plate",
    "signaturemark": "signature mark",
    "pressfigure": "press figure",
    "stagedirection": "stage direction",
    "speakerlabel": "speaker label",
    "grouplabel": "group label",
    "interlineargloss": "interlinear gloss",
    "decoratedinitial": "decorated initial",
}


def _normalize_token(label: str) -> str:
    return " ".join(label.strip().lower().replace("_", " ").replace("-", " ").split())


def normalize_region_role(label: str) -> str:
    """Normalise one region role to a canonical allowed value.

    Accepts case, underscore, and hyphen variants, the compact no-space form of
    any canonical role, and every alias in ``REGION_ROLE_ALIASES``.
    """
    normalized = _normalize_token(label)
    compact = normalized.replace(" ", "")

    if normalized in ALLOWED_REGION_ROLES:
        return normalized

    if compact in REGION_ROLE_ALIASES:
        return REGION_ROLE_ALIASES[compact]

    for allowed in ALLOWED_REGION_ROLES:
        if compact == allowed.replace(" ", ""):
            return allowed

    allowed_list = ", ".join(sorted(ALLOWED_REGION_ROLES))
    raise ValueError(f"Invalid region role '{label}'. Allowed roles: {allowed_list}")
