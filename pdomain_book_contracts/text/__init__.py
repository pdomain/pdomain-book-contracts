"""
Text transformation and comparison views used by matching.

Owns ``normalization.py``, moved from ``pdomain_book_tools.typography``. It
builds the comparison views alignment consumes. ``label_normalization.py``
and ``text_normalize.py`` (moved from ``pdomain_book_tools.ocr``) join it in
a later task; they do related work from a different neighbourhood, and none
of it is specific to typography or OCR results.

``matching/`` and ``typography/`` (``records.py``) both import from here, as
the module layout spec intends. ``normalization.py`` itself also imports
``typography.labels`` (``KnowledgeState``, ``StyleLabel``) and
``typography.spans`` (``CanonicalModel``, ``StyleSpan``, ``split_graphemes``)
for its own vocabulary, so the dependency in fact runs both ways between
``text`` and ``typography`` — not the one-way ``typography`` -> ``text`` the
module layout spec's dependency-direction table states. This is a real
mismatch between spec and code, not a bug fixed here; see the Task 4 Step 2
reorganisation commit message.
"""

from __future__ import annotations

from pdomain_book_contracts.text.normalization import (
    ComparisonOperation,
    ComparisonOperationKind,
    ComparisonView,
    build_comparison_view,
    small_caps_ranges_from_spans,
)

__all__ = [
    "ComparisonOperation",
    "ComparisonOperationKind",
    "ComparisonView",
    "build_comparison_view",
    "small_caps_ranges_from_spans",
]
