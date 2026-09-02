"""
Text transformation and comparison views used by matching.

Will own ``normalization.py``, ``label_normalization.py``, and
``text_normalize.py`` (moved from ``pdomain_book_tools.typography`` and
``pdomain_book_tools.ocr``), which build the comparison views that alignment
and label matching consume. None of it is specific to typography or OCR
results; ``matching/`` imports from here, and the reverse never happens.

Empty pending the code move in a later task.
"""

from __future__ import annotations
