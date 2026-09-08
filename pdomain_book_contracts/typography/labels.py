from __future__ import annotations

from enum import StrEnum

from pdomain_book_contracts.annotation.provenance import (
    ConfidenceTier,
    KnowledgeState,
    LabelSource,
)


class StyleLabel(StrEnum):
    """Visible typography labels in the canonical interchange contract."""

    ITALIC = "italic"
    BOLD = "bold"
    SMALL_CAPS = "small_caps"
    LETTER_SPACED = "letter_spaced"
    SUPERSCRIPT = "superscript"
    SUBSCRIPT = "subscript"
    UNDERLINE = "underline"
    FONT_BLACKLETTER = "font_blackletter"
    FONT_ANTIQUA = "font_antiqua"
    FONT_UPRIGHT_IN_ITALIC = "font_upright_in_italic"
    FONT_OTHER_REVIEWED = "font_other_reviewed"


__all__ = [
    "ConfidenceTier",
    "KnowledgeState",
    "LabelSource",
    "StyleLabel",
]
