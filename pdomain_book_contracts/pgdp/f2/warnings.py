"""Warnings emitted when F2 source cannot safely produce training labels."""

from __future__ import annotations

from enum import StrEnum


class F2ParseWarning(StrEnum):
    """Stable warning codes carried by a parsed typography record."""

    AMBIGUOUS_FONT_CHANGE = "ambiguous_font_change"
    INVALID_CONSTRUCT = "invalid_construct"
    LETTER_SPACE_REMOVED = "letter_space_removed"
    MISMATCHED_CLOSE_TAG = "mismatched_close_tag"
    NOTE_QUARANTINE = "note_quarantine"
    SMALL_CAPS_CASE_NORMALIZED = "small_caps_case_normalized"
    UNAPPROVED_UNDERLINE = "unapproved_underline"
    UNCLOSED_NOTE = "unclosed_note"
    UNCLOSED_BLOCK = "unclosed_block"
    UNCLOSED_TAG = "unclosed_tag"
    UNCLOSED_UNKNOWN_TAG = "unclosed_unknown_tag"
    UNKNOWN_CONSTRUCT = "unknown_construct"
    UNMATCHED_BLOCK = "unmatched_block"
    CROSSED_BLOCK = "crossed_block"


_TRAINING_INELIGIBLE_WARNINGS = frozenset(
    {
        F2ParseWarning.AMBIGUOUS_FONT_CHANGE,
        F2ParseWarning.INVALID_CONSTRUCT,
        F2ParseWarning.MISMATCHED_CLOSE_TAG,
        F2ParseWarning.NOTE_QUARANTINE,
        F2ParseWarning.UNAPPROVED_UNDERLINE,
        F2ParseWarning.UNCLOSED_NOTE,
        F2ParseWarning.UNCLOSED_BLOCK,
        F2ParseWarning.UNCLOSED_TAG,
        F2ParseWarning.UNCLOSED_UNKNOWN_TAG,
        F2ParseWarning.UNKNOWN_CONSTRUCT,
        F2ParseWarning.UNMATCHED_BLOCK,
        F2ParseWarning.CROSSED_BLOCK,
    }
)


def warning_blocks_training(code: str) -> bool:
    """Return whether a parser warning prevents automatic supervision."""
    return code in _TRAINING_INELIGIBLE_WARNINGS
