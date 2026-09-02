from __future__ import annotations

from enum import StrEnum


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


class KnowledgeState(StrEnum):
    """How much is known about one label assignment."""

    POSITIVE = "positive"
    VERIFIED_NEGATIVE = "verified_negative"
    UNKNOWN = "unknown"
    CONFLICT = "conflict"


class LabelSource(StrEnum):
    """Evidence sources that can assign a canonical label."""

    F2 = "f2"
    GUTENBERG_HTML = "gutenberg_html"
    SE_COMPUTED_CSS = "se_computed_css"
    HUMAN = "human"
    SYNTHETIC = "synthetic"


class ConfidenceTier(StrEnum):
    """Reviewed confidence tiers for label evidence."""

    GOLD = "gold"
    SILVER = "silver"
    BRONZE = "bronze"
    QUARANTINE = "quarantine"
