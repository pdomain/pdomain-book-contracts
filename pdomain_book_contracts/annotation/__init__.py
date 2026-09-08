"""Vocabularies describing what a human or a model asserted about a page.

This subpackage owns the words. It knows nothing about geometry, imaging, or the
page model, so every repository can depend on it without pulling either in.
"""

from __future__ import annotations

from pdomain_book_contracts.annotation.provenance import (
    ConfidenceTier,
    KnowledgeState,
    LabelSource,
)

__all__ = [
    "ConfidenceTier",
    "KnowledgeState",
    "LabelSource",
]
