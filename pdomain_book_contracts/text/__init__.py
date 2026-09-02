"""
Text transformation utilities with no internal package dependencies.

Currently empty. ``normalization.py`` was moved here from
``pdomain_book_tools.typography`` and then moved back to ``typography`` —
it needs ``typography.labels`` and ``typography.spans`` for its own
vocabulary, so it never fit the "no internal dependencies" premise of this
package. ``label_normalization.py`` and ``text_normalize.py`` (moved from
``pdomain_book_tools.ocr`` in a later task) will land here instead: both
import nothing but the standard library, so this package will genuinely
have no internal dependencies once they do.
"""

from __future__ import annotations
