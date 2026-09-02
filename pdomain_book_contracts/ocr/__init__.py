"""OCR result value types: characters, provenance, and glyph annotations.

Owns ``character.py``, ``glyph_annotations.py``, ``provenance.py``,
``review.py``, ``gt_orphans.py``, and ``blob_protocol.py``, moved from
``pdomain_book_tools.ocr``. Depends on ``geometry`` and ``text``.

``label_normalization.py`` and ``text_normalize.py`` also moved out of
``pdomain_book_tools.ocr`` in this same step, but into ``text`` rather
than here — see that package instead.
"""

from __future__ import annotations

from pdomain_book_contracts.ocr.blob_protocol import BlobStoreProtocol
from pdomain_book_contracts.ocr.character import Character
from pdomain_book_contracts.ocr.glyph_annotations import (
    GlyphAnnotations,
    GlyphSource,
    LigatureKind,
    LigatureMark,
)
from pdomain_book_contracts.ocr.gt_orphans import GtOrphans
from pdomain_book_contracts.ocr.provenance import (
    UNKNOWN_METADATA_VALUE,
    OCRModelProvenance,
    OCRProvenance,
)
from pdomain_book_contracts.ocr.review import ReviewMetadata

__all__ = [
    "UNKNOWN_METADATA_VALUE",
    "BlobStoreProtocol",
    "Character",
    "GlyphAnnotations",
    "GlyphSource",
    "GtOrphans",
    "LigatureKind",
    "LigatureMark",
    "OCRModelProvenance",
    "OCRProvenance",
    "ReviewMetadata",
]
