r"""Shared post-OCR text-normalization helpers.

These utilities live in :mod:`pdomain_book_tools.ocr` so that every
downstream consumer (``pdomain-ocr-cli``, ``pdomain-ocr-simple-gui``, and
future apps) can apply the same canonical cleanups to OCR output without
maintaining its own copy.

Curly-quote glyph keys are written as ``\\uXXXX`` escapes (rather than the
literal Unicode characters) to sidestep ruff's RUF001 ambiguous-character
lint and to match the convention already in use by ``pdomain-ocr-cli``.
"""

from __future__ import annotations

# Keys use \uXXXX escapes so RUF001 / ERA001 heuristics do not flag the
# inline comment text as ambiguous or commented-out code.
_CURLY_TO_STRAIGHT_TRANSLATION = str.maketrans(
    {
        "\u2018": "'",  # LEFT SINGLE QUOTATION MARK
        "\u2019": "'",  # RIGHT SINGLE QUOTATION MARK / apostrophe
        "\u201a": "'",  # SINGLE LOW-9 QUOTATION MARK
        "\u201b": "'",  # SINGLE HIGH-REVERSED-9 QUOTATION MARK
        "\u201c": '"',  # LEFT DOUBLE QUOTATION MARK
        "\u201d": '"',  # RIGHT DOUBLE QUOTATION MARK
        "\u201e": '"',  # DOUBLE LOW-9 QUOTATION MARK
        "\u201f": '"',  # DOUBLE HIGH-REVERSED-9 QUOTATION MARK
    }
)


def normalize_curly_quotes(text: str) -> str:
    """Convert common curly quote variants to straight ASCII quotes."""
    return text.translate(_CURLY_TO_STRAIGHT_TRANSLATION)


def normalize_em_dash(text: str) -> str:
    """Convert em dash (U+2014) to ASCII double hyphen (``--``)."""
    return text.replace("\u2014", "--")


def apply_text_normalizations(
    text: str | None,
    *,
    straight_quotes: bool,
    em_dash_to_double_hyphen: bool,
) -> str:
    """Apply the selected post-OCR text cleanups.

    Tolerates a ``None`` page text (the OCR engine may yield no text on a
    blank page) by returning ``""``.
    """
    if not text:
        return ""
    if straight_quotes:
        text = normalize_curly_quotes(text)
    if em_dash_to_double_hyphen:
        text = normalize_em_dash(text)
    return text


__all__ = [
    "apply_text_normalizations",
    "normalize_curly_quotes",
    "normalize_em_dash",
]
