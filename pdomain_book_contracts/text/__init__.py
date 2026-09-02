"""Text transformation utilities with no internal package dependencies.

Owns ``label_normalization.py`` and ``text_normalize.py``, moved from
``pdomain_book_tools.ocr``. Both import nothing but the standard library,
so this package genuinely has no internal dependencies.

``typography/normalization.py`` was moved here and then moved back to
``typography`` — it needs ``typography.labels`` and ``typography.spans``
for its own vocabulary, so it never fit this package's "no internal
dependencies" premise. See ``typography`` instead.
"""

from __future__ import annotations

from pdomain_book_contracts.text.label_normalization import (
    ALLOWED_COMPONENTS,
    ALLOWED_TEXT_STYLE_LABEL_SCOPES,
    ALLOWED_TEXT_STYLE_LABELS,
    normalize_character_component,
    normalize_character_components,
    normalize_text_style_label,
    normalize_text_style_label_scope,
    normalize_text_style_label_scopes,
    normalize_text_style_labels,
    normalize_word_component,
    normalize_word_components,
)
from pdomain_book_contracts.text.text_normalize import (
    apply_text_normalizations,
    normalize_curly_quotes,
    normalize_em_dash,
)

__all__ = [
    "ALLOWED_COMPONENTS",
    "ALLOWED_TEXT_STYLE_LABELS",
    "ALLOWED_TEXT_STYLE_LABEL_SCOPES",
    "apply_text_normalizations",
    "normalize_character_component",
    "normalize_character_components",
    "normalize_curly_quotes",
    "normalize_em_dash",
    "normalize_text_style_label",
    "normalize_text_style_label_scope",
    "normalize_text_style_label_scopes",
    "normalize_text_style_labels",
    "normalize_word_component",
    "normalize_word_components",
]
