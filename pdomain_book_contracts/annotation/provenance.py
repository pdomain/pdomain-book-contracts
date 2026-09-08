"""Provenance vocabularies shared by every annotation level.

These describe how one assertion about a page got there: which source made it,
how much is known about it, and how far it is trusted. They apply to page kinds,
regions, style spans, words, and glyph annotations alike.
"""

from __future__ import annotations

from enum import StrEnum


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
    # New. The five values above are four document sources and a person, because
    # this enum was built to record which transcription asserted a style. None of
    # them can say that a model proposed something, which is the claim the whole
    # labeling track exists to record. The model's identity and version live on
    # the proposal run record, so this member only names the category.
    MODEL = "model"


class ConfidenceTier(StrEnum):
    """Reviewed confidence tiers for label evidence."""

    GOLD = "gold"
    SILVER = "silver"
    BRONZE = "bronze"
    QUARANTINE = "quarantine"
